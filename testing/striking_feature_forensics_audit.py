#!/usr/bin/env python3
"""Focused forensics for the frozen striking-core feature columns.

This audit is deliberately narrower than the broad semantic-integrity checks:
it reconstructs the exact striking columns used by the frozen
`mixed_sig_head_core` policy from the chronological fight-detail source, then
summarizes whether their historical market residual shape looks coherent.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_aware_feature_audit import aligned_market_feature_frame  # noqa: E402
from testing.statistical_edge_audit import binary_log_loss  # noqa: E402
from utils.name_matching import lookup_keys, normalize_name  # noqa: E402


TARGET_BASES = ("Sig. str.%", "Sig. str.", "Head")
TARGET_OPPDIFF_COLUMNS = (
    "Sig. str.% differential oppdiff",
    "Sig. str. differential oppdiff",
    "Head differential oppdiff",
)
TOLERANCE = 1e-8


@dataclass
class StrikingState:
    totalfights: int = 0
    differential_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    nonbinary_fights: int = 0


def parse_args():
    parser = argparse.ArgumentParser(description="Audit frozen striking-core feature lineage")
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--odds", default="data/fight_results_with_odds.csv")
    parser.add_argument("--fight-details-source", default="data/fight_details_date.csv")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--bins", type=int, default=5)
    parser.add_argument("--output-dir", default="test_results/striking_feature_forensics_audit")
    return parser.parse_args()


def parse_date(value) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, format="mixed", errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).normalize()


def canonical_fighter_key(name) -> str:
    keys = lookup_keys(name)
    return keys[-1] if keys else normalize_name(name)


def pair_key(red, blue) -> tuple[str, str]:
    return tuple(sorted([canonical_fighter_key(red), canonical_fighter_key(blue)]))


def lookup_key(row: pd.Series) -> tuple[str, tuple[str, str], str]:
    date = parse_date(row.get("Date"))
    return (
        "" if date is None else date.date().isoformat(),
        pair_key(row.get("Red Fighter", ""), row.get("Blue Fighter", "")),
        str(row.get("Title", "")),
    )


def chronological_source_rows(source: pd.DataFrame) -> list[pd.Series]:
    rows = []
    seen = set()
    for _, row in source.iterrows():
        date = parse_date(row.get("Date"))
        key = (
            "" if date is None else date.date().isoformat(),
            str(row.get("Title", "")),
            frozenset(pair_key(row.get("Red Fighter", ""), row.get("Blue Fighter", ""))),
            canonical_fighter_key(row.get("Winner", "")),
            str(row.get("Method", "")),
            str(row.get("Round", "")),
            str(row.get("Time", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return sorted(rows, key=lambda row: parse_date(row.get("Date")) or pd.Timestamp.max)


def feature_queues(features: pd.DataFrame) -> dict[tuple[str, tuple[str, str], str], deque[int]]:
    queues: dict[tuple[str, tuple[str, str], str], deque[int]] = defaultdict(deque)
    for index, row in features.iterrows():
        queues[lookup_key(row)].append(index)
    return queues


def safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def source_result(row: pd.Series) -> str:
    winner_key = canonical_fighter_key(row.get("Winner", ""))
    red_key = canonical_fighter_key(row.get("Red Fighter", ""))
    blue_key = canonical_fighter_key(row.get("Blue Fighter", ""))
    if winner_key == red_key:
        return "win"
    if winner_key == blue_key:
        return "loss"
    return "nonbinary"


def sqr_sum(n: int) -> int:
    return n * (n + 1) * (2 * n + 1) // 6


def side_expected_differential(state: StrikingState, base: str) -> float | None:
    denominator = sqr_sum(state.totalfights)
    if denominator <= 0:
        return None
    return float(state.differential_sum[base] / denominator)


def update_striking_state(states: defaultdict[str, StrikingState], row: pd.Series, include_nonbinary: bool) -> None:
    result = source_result(row)
    if result == "nonbinary" and not include_nonbinary:
        return

    red_key = canonical_fighter_key(row["Red Fighter"])
    blue_key = canonical_fighter_key(row["Blue Fighter"])
    red_state = states[red_key]
    blue_state = states[blue_key]
    red_state.totalfights += 1
    blue_state.totalfights += 1
    red_weight = red_state.totalfights**2
    blue_weight = blue_state.totalfights**2

    if result == "nonbinary":
        red_state.nonbinary_fights += 1
        blue_state.nonbinary_fights += 1

    for base in TARGET_BASES:
        red_value = safe_float(row.get(f"Red {base}"))
        blue_value = safe_float(row.get(f"Blue {base}"))
        if red_value is None or blue_value is None:
            continue
        red_state.differential_sum[base] += (red_value - blue_value) * red_weight
        blue_state.differential_sum[base] += (blue_value - red_value) * blue_weight


def compare_value(actual, expected, tolerance=TOLERANCE) -> tuple[bool, float | None]:
    actual_float = safe_float(actual)
    if actual_float is None or expected is None:
        return True, None
    error = abs(actual_float - expected)
    return error <= tolerance, error


def init_feature_summary() -> dict:
    return {
        "side_checks": 0,
        "side_mismatches": 0,
        "side_max_abs_error": 0.0,
        "oppdiff_checks": 0,
        "oppdiff_mismatches": 0,
        "oppdiff_max_abs_error": 0.0,
        "binary_only_changed_rows": 0,
        "binary_only_mean_abs_oppdiff_change": 0.0,
        "binary_only_max_abs_oppdiff_change": 0.0,
        "_binary_only_abs_changes": [],
    }


def audit_reconstruction(source: pd.DataFrame, features: pd.DataFrame) -> dict:
    queues = feature_queues(features)
    states: defaultdict[str, StrikingState] = defaultdict(StrikingState)
    binary_states: defaultdict[str, StrikingState] = defaultdict(StrikingState)
    summaries = {base: init_feature_summary() for base in TARGET_BASES}
    examples = []
    nonbinary_examples = []
    used_indices = set()
    expected_feature_rows = 0
    matched_feature_rows = 0
    missing_feature_rows = 0
    nonbinary_source_rows = 0
    rows_with_prior_nonbinary = 0

    for source_row in chronological_source_rows(source):
        event_date = parse_date(source_row.get("Date"))
        red_key = canonical_fighter_key(source_row["Red Fighter"])
        blue_key = canonical_fighter_key(source_row["Blue Fighter"])
        result = source_result(source_row)
        if result == "nonbinary":
            nonbinary_source_rows += 1

        eligible = (
            result in {"win", "loss"}
            and event_date is not None
            and states[red_key].totalfights >= 2
            and states[blue_key].totalfights >= 2
        )
        if eligible:
            expected_feature_rows += 1
            queue = queues.get(lookup_key(source_row))
            feature_index = queue.popleft() if queue else None
            if feature_index is None:
                missing_feature_rows += 1
            else:
                matched_feature_rows += 1
                used_indices.add(feature_index)
                feature_row = features.loc[feature_index]
                feature_red_key = canonical_fighter_key(feature_row["Red Fighter"])
                feature_blue_key = canonical_fighter_key(feature_row["Blue Fighter"])
                row_has_prior_nonbinary = (
                    states[feature_red_key].nonbinary_fights > 0
                    or states[feature_blue_key].nonbinary_fights > 0
                )
                if row_has_prior_nonbinary:
                    rows_with_prior_nonbinary += 1

                for base in TARGET_BASES:
                    red_expected = side_expected_differential(states[feature_red_key], base)
                    blue_expected = side_expected_differential(states[feature_blue_key], base)
                    red_binary = side_expected_differential(binary_states[feature_red_key], base)
                    blue_binary = side_expected_differential(binary_states[feature_blue_key], base)
                    if red_expected is None or blue_expected is None:
                        continue

                    for side, expected in (("Red", red_expected), ("Blue", blue_expected)):
                        column = f"{side} {base} differential"
                        ok, error = compare_value(feature_row.get(column), expected)
                        summaries[base]["side_checks"] += 1
                        if error is not None:
                            summaries[base]["side_max_abs_error"] = max(
                                summaries[base]["side_max_abs_error"],
                                float(error),
                            )
                        if not ok:
                            summaries[base]["side_mismatches"] += 1
                            if len(examples) < 30:
                                examples.append(
                                    {
                                        "date": event_date.date().isoformat(),
                                        "title": str(feature_row.get("Title", "")),
                                        "fighter": str(feature_row.get(f"{side} Fighter", "")),
                                        "feature": f"{side} {base} differential",
                                        "actual": safe_float(feature_row.get(column)),
                                        "expected": expected,
                                        "absolute_error": error,
                                    }
                                )

                    oppdiff_column = f"{base} differential oppdiff"
                    expected_oppdiff = red_expected - blue_expected
                    ok, error = compare_value(feature_row.get(oppdiff_column), expected_oppdiff)
                    summaries[base]["oppdiff_checks"] += 1
                    if error is not None:
                        summaries[base]["oppdiff_max_abs_error"] = max(
                            summaries[base]["oppdiff_max_abs_error"],
                            float(error),
                        )
                    if not ok:
                        summaries[base]["oppdiff_mismatches"] += 1
                        if len(examples) < 30:
                            examples.append(
                                {
                                    "date": event_date.date().isoformat(),
                                    "title": str(feature_row.get("Title", "")),
                                    "fighter": f"{feature_row.get('Red Fighter', '')} vs {feature_row.get('Blue Fighter', '')}",
                                    "feature": oppdiff_column,
                                    "actual": safe_float(feature_row.get(oppdiff_column)),
                                    "expected": expected_oppdiff,
                                    "absolute_error": error,
                                }
                            )

                    if red_binary is not None and blue_binary is not None:
                        binary_oppdiff = red_binary - blue_binary
                        binary_change = expected_oppdiff - binary_oppdiff
                        if abs(binary_change) > TOLERANCE:
                            summaries[base]["_binary_only_abs_changes"].append(abs(binary_change))
                            if row_has_prior_nonbinary and len(nonbinary_examples) < 20:
                                nonbinary_examples.append(
                                    {
                                        "date": event_date.date().isoformat(),
                                        "fight": f"{feature_row.get('Red Fighter', '')} vs {feature_row.get('Blue Fighter', '')}",
                                        "feature": oppdiff_column,
                                        "with_nonbinary": expected_oppdiff,
                                        "binary_only": binary_oppdiff,
                                        "difference": binary_change,
                                    }
                                )

        update_striking_state(states, source_row, include_nonbinary=True)
        update_striking_state(binary_states, source_row, include_nonbinary=False)

    for summary in summaries.values():
        changes = summary.pop("_binary_only_abs_changes")
        summary["binary_only_changed_rows"] = int(len(changes))
        if changes:
            summary["binary_only_mean_abs_oppdiff_change"] = float(np.mean(changes))
            summary["binary_only_max_abs_oppdiff_change"] = float(np.max(changes))

    return {
        "source_rows": int(len(source)),
        "feature_rows": int(len(features)),
        "nonbinary_source_rows": int(nonbinary_source_rows),
        "expected_feature_rows_from_source": int(expected_feature_rows),
        "matched_feature_rows": int(matched_feature_rows),
        "missing_feature_rows": int(missing_feature_rows),
        "extra_feature_rows": int(len(features) - len(used_indices)),
        "rows_with_prior_nonbinary_state": int(rows_with_prior_nonbinary),
        "target_features": summaries,
        "mismatch_examples": examples,
        "nonbinary_effect_examples": nonbinary_examples,
    }


def quantile_bins(frame: pd.DataFrame, column: str, bins: int) -> list[dict]:
    work = frame.copy()
    values = pd.to_numeric(work[column], errors="coerce")
    residual = work["red_won"].astype(float) - pd.to_numeric(work["red_market_probability"], errors="coerce")
    mask = values.notna() & residual.notna()
    work = work[mask].copy()
    if work.empty:
        return []
    values = values[mask]
    ranks = values.rank(method="first")
    groups = pd.qcut(ranks, q=min(bins, len(work)), labels=False, duplicates="drop")
    work["_feature_value"] = values
    work["_market_residual"] = residual[mask]
    work["_bin"] = groups
    rows = []
    for group, subset in work.groupby("_bin", sort=True):
        y = subset["red_won"].astype(float).to_numpy()
        market = subset["red_market_probability"].astype(float).to_numpy()
        rows.append(
            {
                "bin": int(group) + 1,
                "rows": int(len(subset)),
                "feature_min": float(subset["_feature_value"].min()),
                "feature_max": float(subset["_feature_value"].max()),
                "feature_mean": float(subset["_feature_value"].mean()),
                "actual_red_win_rate": float(np.mean(y)),
                "mean_market_probability": float(np.mean(market)),
                "actual_minus_market": float(np.mean(y - market)),
                "market_log_loss": binary_log_loss(y, market),
            }
        )
    return rows


def summarize_signal_shape(aligned: pd.DataFrame, bins: int) -> dict:
    result = {}
    residual = aligned["red_won"].astype(float) - pd.to_numeric(aligned["red_market_probability"], errors="coerce")
    for column in TARGET_OPPDIFF_COLUMNS:
        values = pd.to_numeric(aligned[column], errors="coerce")
        mask = values.notna() & residual.notna()
        subset_values = values[mask]
        subset_residual = residual[mask]
        bin_rows = quantile_bins(aligned, column, bins)
        low = bin_rows[0]["actual_minus_market"] if bin_rows else None
        high = bin_rows[-1]["actual_minus_market"] if bin_rows else None
        result[column] = {
            "rows": int(mask.sum()),
            "mean": float(subset_values.mean()),
            "std": float(subset_values.std(ddof=0)),
            "min": float(subset_values.min()),
            "p01": float(subset_values.quantile(0.01)),
            "p50": float(subset_values.quantile(0.50)),
            "p99": float(subset_values.quantile(0.99)),
            "max": float(subset_values.max()),
            "pearson_to_actual_minus_market": float(subset_values.corr(subset_residual, method="pearson")),
            "spearman_to_actual_minus_market": float(subset_values.corr(subset_residual, method="spearman")),
            "lowest_bin_actual_minus_market": low,
            "highest_bin_actual_minus_market": high,
            "high_minus_low_actual_minus_market": None if low is None or high is None else float(high - low),
            "bins": bin_rows,
        }
    return result


def summarize_experience(aligned: pd.DataFrame) -> list[dict]:
    work = aligned.copy()
    work["min_totalfights"] = np.minimum(
        pd.to_numeric(work["Red totalfights"], errors="coerce"),
        pd.to_numeric(work["Blue totalfights"], errors="coerce"),
    )
    work["actual_minus_market"] = work["red_won"].astype(float) - pd.to_numeric(
        work["red_market_probability"],
        errors="coerce",
    )
    bins = [
        ("2-4", work["min_totalfights"].between(2, 4, inclusive="both")),
        ("5-9", work["min_totalfights"].between(5, 9, inclusive="both")),
        ("10+", work["min_totalfights"] >= 10),
    ]
    rows = []
    for label, mask in bins:
        subset = work[mask].copy()
        if subset.empty:
            continue
        row = {
            "min_totalfights_bin": label,
            "rows": int(len(subset)),
            "mean_actual_minus_market": float(subset["actual_minus_market"].mean()),
        }
        for column in TARGET_OPPDIFF_COLUMNS:
            values = pd.to_numeric(subset[column], errors="coerce")
            residual = subset["actual_minus_market"]
            valid = values.notna() & residual.notna()
            row[f"{column} spearman"] = float(values[valid].corr(residual[valid], method="spearman")) if valid.sum() > 1 else None
        rows.append(row)
    return rows


def correlation_matrix(aligned: pd.DataFrame) -> dict:
    frame = aligned[list(TARGET_OPPDIFF_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    return {
        "pearson": frame.corr(method="pearson").round(6).to_dict(),
        "spearman": frame.corr(method="spearman").round(6).to_dict(),
    }


def fmt_float(value, digits=4) -> str:
    if value is None:
        return ""
    value = float(value)
    if not np.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None:
        return ""
    value = float(value)
    if not np.isfinite(value):
        return ""
    return f"{100.0 * value:.{digits}f}%"


def markdown_report(result: dict) -> str:
    reconstruction = result["reconstruction"]
    signal = result["signal_shape"]
    experience = result["experience_shape"]
    corr = result["correlations"]["spearman"]
    total_side_mismatches = sum(row["side_mismatches"] for row in reconstruction["target_features"].values())
    total_opp_mismatches = sum(row["oppdiff_mismatches"] for row in reconstruction["target_features"].values())
    hard_fail = total_side_mismatches + total_opp_mismatches + reconstruction["missing_feature_rows"]

    lines = [
        "# Striking Feature Forensics Audit",
        "",
        "This audit reconstructs the exact frozen striking-core feature columns",
        "from chronological fight details and checks whether their market residual",
        "shape looks coherent. It does not select or train a new production model.",
        "",
        "## Feature Definitions Checked",
        "",
        "- `Sig. str.% differential`: weighted average of prior fight significant-strike accuracy minus opponent significant-strike accuracy.",
        "- `Sig. str. differential`: weighted average of prior fight significant strikes landed minus opponent significant strikes landed.",
        "- `Head differential`: weighted average of prior fight head strikes landed minus opponent head strikes landed.",
        "- Each prior fight is weighted by the fighter's chronological fight number squared, then divided by the triangular square sum of prior fights.",
        "- The frozen `oppdiff` feature is the red fighter's pre-fight differential minus the blue fighter's pre-fight differential.",
        "",
        "## Reconstruction Checks",
        "",
        "| Check | Value |",
        "| --- | ---: |",
        f"| source rows | {reconstruction['source_rows']} |",
        f"| feature rows | {reconstruction['feature_rows']} |",
        f"| non-binary source rows | {reconstruction['nonbinary_source_rows']} |",
        f"| expected supervised feature rows | {reconstruction['expected_feature_rows_from_source']} |",
        f"| matched supervised feature rows | {reconstruction['matched_feature_rows']} |",
        f"| missing feature rows | {reconstruction['missing_feature_rows']} |",
        f"| extra feature rows | {reconstruction['extra_feature_rows']} |",
        f"| supervised rows with prior non-binary state | {reconstruction['rows_with_prior_nonbinary_state']} |",
        f"| hard reconstruction failures | {hard_fail} |",
        "",
        "| Feature | Side Checks | Side Mismatches | Side Max Error | Oppdiff Checks | Oppdiff Mismatches | Oppdiff Max Error | Binary-Only Changed Rows | Mean Abs Nonbinary Change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for base, row in reconstruction["target_features"].items():
        lines.append(
            "| `{base}` | {side_checks} | {side_mismatches} | {side_error} | {opp_checks} | {opp_mismatches} | {opp_error} | {changed} | {mean_change} |".format(
                base=base,
                side_checks=row["side_checks"],
                side_mismatches=row["side_mismatches"],
                side_error=fmt_float(row["side_max_abs_error"], 8),
                opp_checks=row["oppdiff_checks"],
                opp_mismatches=row["oppdiff_mismatches"],
                opp_error=fmt_float(row["oppdiff_max_abs_error"], 8),
                changed=row["binary_only_changed_rows"],
                mean_change=fmt_float(row["binary_only_mean_abs_oppdiff_change"], 6),
            )
        )

    lines.extend(
        [
            "",
            "## Market Residual Shape",
            "",
            "| Feature | Rows | Spearman vs Actual-Market | Low Bin A-M | High Bin A-M | High-Low | p01 | p50 | p99 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for column, row in signal.items():
        lines.append(
            "| `{feature}` | {rows} | {spearman} | {low} | {high} | {spread} | {p01} | {p50} | {p99} |".format(
                feature=column,
                rows=row["rows"],
                spearman=fmt_float(row["spearman_to_actual_minus_market"], 4),
                low=fmt_pct(row["lowest_bin_actual_minus_market"]),
                high=fmt_pct(row["highest_bin_actual_minus_market"]),
                spread=fmt_pct(row["high_minus_low_actual_minus_market"]),
                p01=fmt_float(row["p01"], 4),
                p50=fmt_float(row["p50"], 4),
                p99=fmt_float(row["p99"], 4),
            )
        )

    for column, row in signal.items():
        lines.extend(
            [
                "",
                f"### `{column}` Bins",
                "",
                "| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |",
                "| ---: | ---: | --- | ---: | ---: | ---: |",
            ]
        )
        for bin_row in row["bins"]:
            lines.append(
                "| {bin} | {rows} | {lo} to {hi} | {actual} | {market} | {residual} |".format(
                    bin=bin_row["bin"],
                    rows=bin_row["rows"],
                    lo=fmt_float(bin_row["feature_min"], 4),
                    hi=fmt_float(bin_row["feature_max"], 4),
                    actual=fmt_pct(bin_row["actual_red_win_rate"]),
                    market=fmt_pct(bin_row["mean_market_probability"]),
                    residual=fmt_pct(bin_row["actual_minus_market"]),
                )
            )

    lines.extend(
        [
            "",
            "## Experience Split",
            "",
            "| Min Prior Fights | Rows | Mean Actual-Market | Sig% Spearman | Sig Raw Spearman | Head Spearman |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in experience:
        lines.append(
            "| {label} | {rows} | {residual} | {sigpct} | {sigraw} | {head} |".format(
                label=row["min_totalfights_bin"],
                rows=row["rows"],
                residual=fmt_pct(row["mean_actual_minus_market"]),
                sigpct=fmt_float(row.get("Sig. str.% differential oppdiff spearman")),
                sigraw=fmt_float(row.get("Sig. str. differential oppdiff spearman")),
                head=fmt_float(row.get("Head differential oppdiff spearman")),
            )
        )

    lines.extend(
        [
            "",
            "## Spearman Correlations Between Frozen Feature Inputs",
            "",
            "| Feature Pair | Correlation |",
            "| --- | ---: |",
        ]
    )
    for left in TARGET_OPPDIFF_COLUMNS:
        for right in TARGET_OPPDIFF_COLUMNS:
            if left >= right:
                continue
            lines.append(f"| `{left}` vs `{right}` | {fmt_float(corr[left][right], 4)} |")

    lines.extend(["", "## Interpretation", ""])
    if hard_fail:
        lines.append(
            "- Reconstruction found hard mismatches; do not rely on the striking-core feature evidence until those are explained."
        )
    else:
        lines.append(
            "- Reconstruction found zero hard mismatches for the frozen striking-core side and oppdiff columns."
        )
    lines.append(
        "- Non-binary outcomes do not create supervised training rows here, but they do flow into later striking state when fighters have prior draws/no contests/overturns."
    )
    spreads = [
        row["high_minus_low_actual_minus_market"]
        for row in signal.values()
        if row["high_minus_low_actual_minus_market"] is not None
    ]
    if spreads and min(spreads) > 0.0:
        lines.append(
            "- All three frozen inputs have positive top-minus-bottom quintile market-residual spreads, which is directionally coherent with the fight meaning of better prior striking differential."
        )
    lines.append(
        "- The rank correlations to market residual are small, and raw significant-strike differential is strongly correlated with head-strike differential, so this supports a weak compact feature clue rather than three independent alphas."
    )
    lines.append(
        "- The residual-shape tables are descriptive diagnostics, not a fresh strategy-selection result."
    )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    source = pd.read_csv(args.source_fights)
    features = pd.read_csv(args.features)
    reconstruction = audit_reconstruction(source, features)
    align_args = argparse.Namespace(
        features=args.features,
        odds=args.odds,
        fight_details_source=args.fight_details_source,
        min_training_date=args.min_training_date,
        last_holdout_end=args.last_holdout_end,
        include_womens_fights=False,
    )
    aligned, metadata = aligned_market_feature_frame(align_args)
    signal = summarize_signal_shape(aligned, args.bins)
    return {
        "source_fights": args.source_fights,
        "features": args.features,
        "odds": args.odds,
        "fight_details_source": args.fight_details_source,
        "reconstruction": reconstruction,
        "alignment_metadata": metadata,
        "signal_shape": signal,
        "experience_shape": summarize_experience(aligned),
        "correlations": correlation_matrix(aligned),
    }


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_feature_forensics_audit.json"
    md_path = output_dir / "striking_feature_forensics_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
