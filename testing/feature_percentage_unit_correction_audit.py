#!/usr/bin/env python3
"""Audit and test unit-corrected percentage side features.

The historical generator time-scales side percentage columns, e.g. `Red Leg%`,
by fight elapsed minutes. Their differentials and defense counterparts are not
time-scaled. This audit reconstructs pre-fight percentage state, creates a
feature-table variant where side percentage values are weighted percentages
instead of percentage-per-minute proxies, and runs leak-safe regularized
backtests against that variant.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.feature_semantic_ablation_audit import summarize_ledger  # noqa: E402
from utils.name_matching import lookup_keys, normalize_name  # noqa: E402


ID_COLUMNS = {"Result", "Red Fighter", "Blue Fighter", "Title", "Date"}
WINDOWS = {
    "1y": ("2025-06-27", "2026-06-27"),
    "2y": ("2024-06-27", "2026-06-27"),
}
BASELINE_LEDGER_DIRS = {
    "1y": "test_results/regularized_lgbm_1y",
    "2y": "test_results/regularized_lgbm_2y",
}
TOLERANCE = 1e-8


@dataclass
class PercentState:
    totalfights: int = 0
    scaled_side_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    unit_side_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    differential_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    defense_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))


def parse_args():
    parser = argparse.ArgumentParser(description="Audit unit-corrected percentage features")
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--params", default="test_results/regularized_lgbm_params.json")
    parser.add_argument("--feature-importance", default="test_results/regularized_lgbm_feature_importance.csv")
    parser.add_argument("--output-dir", default="test_results/feature_percentage_unit_correction_audit")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def canonical_fighter_key(name) -> str:
    keys = lookup_keys(name)
    return keys[-1] if keys else normalize_name(name)


def parse_date(value) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, format="mixed", errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).normalize()


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
    return "draw"


def elapsed_minutes(row: pd.Series) -> float | None:
    round_number = safe_float(row.get("Round"))
    time_value = safe_float(row.get("Time"))
    if round_number is None or time_value is None:
        return None
    elapsed = (round_number - 1.0) * 5.0 + time_value
    return elapsed if elapsed > 0 else None


def sqr_sum(n: int) -> int:
    return n * (n + 1) * (2 * n + 1) // 6


def percentage_bases(source: pd.DataFrame) -> list[str]:
    bases = []
    for column in source.columns:
        if column.startswith("Red "):
            base = column[len("Red ") :]
            if "%" in base and f"Blue {base}" in source.columns:
                bases.append(base)
    return bases


def load_importance(path: str) -> dict[str, float]:
    importance_path = Path(path)
    if not importance_path.exists():
        return {}
    df = pd.read_csv(importance_path)
    if "feature" not in df.columns or "importance" not in df.columns:
        return {}
    return {str(row["feature"]): float(row["importance"]) for _, row in df.iterrows()}


def update_percent_state(states: defaultdict[str, PercentState], row: pd.Series, bases: list[str]) -> None:
    red_key = canonical_fighter_key(row["Red Fighter"])
    blue_key = canonical_fighter_key(row["Blue Fighter"])
    red_state = states[red_key]
    blue_state = states[blue_key]
    red_state.totalfights += 1
    blue_state.totalfights += 1
    red_weight = red_state.totalfights**2
    blue_weight = blue_state.totalfights**2
    elapsed = elapsed_minutes(row)

    for base in bases:
        red_value = safe_float(row.get(f"Red {base}"))
        blue_value = safe_float(row.get(f"Blue {base}"))
        if red_value is None or blue_value is None:
            continue

        red_state.unit_side_sum[base] += red_value * red_weight
        blue_state.unit_side_sum[base] += blue_value * blue_weight
        if elapsed is not None:
            red_state.scaled_side_sum[base] += red_value * red_weight / elapsed
            blue_state.scaled_side_sum[base] += blue_value * blue_weight / elapsed

        red_state.differential_sum[base] += (red_value - blue_value) * red_weight
        blue_state.differential_sum[base] += (blue_value - red_value) * blue_weight
        red_state.defense_sum[base] += (1.0 - blue_value) * red_weight
        blue_state.defense_sum[base] += (1.0 - red_value) * blue_weight


def summarize_unit_differences(records: list[dict], importance: dict[str, float]) -> list[dict]:
    df = pd.DataFrame(records)
    rows = []
    if df.empty:
        return rows
    for feature, subset in df.groupby("feature", sort=True):
        current = subset["current_scaled"].to_numpy(dtype=float)
        corrected = subset["unit_corrected"].to_numpy(dtype=float)
        difference = corrected - current
        if len(subset) > 1:
            corr = float(np.corrcoef(current, corrected)[0, 1])
        else:
            corr = None
        rows.append(
            {
                "feature": str(feature),
                "importance_red": float(importance.get(f"Red {feature}", 0.0)),
                "importance_blue": float(importance.get(f"Blue {feature}", 0.0)),
                "importance_oppdiff": float(importance.get(f"{feature} oppdiff", 0.0)),
                "rows": int(len(subset)),
                "current_mean": float(np.mean(current)),
                "corrected_mean": float(np.mean(corrected)),
                "mean_abs_difference": float(np.mean(np.abs(difference))),
                "median_abs_difference": float(np.median(np.abs(difference))),
                "max_abs_difference": float(np.max(np.abs(difference))),
                "correlation": corr,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["importance_red"] + row["importance_blue"] + row["importance_oppdiff"],
            row["mean_abs_difference"],
        ),
        reverse=True,
    )


def build_corrected_features(
    source: pd.DataFrame,
    features: pd.DataFrame,
    bases: list[str],
    output_path: Path,
    importance: dict[str, float],
) -> dict:
    corrected = features.copy()
    queues = feature_queues(features)
    states: defaultdict[str, PercentState] = defaultdict(PercentState)
    records = []
    scaled_match_checks = scaled_mismatches = 0
    differential_checks = differential_mismatches = 0
    defense_checks = defense_mismatches = 0
    matched_rows = 0
    missing_rows = 0

    for source_row in chronological_source_rows(source):
        event_date = parse_date(source_row.get("Date"))
        red_key = canonical_fighter_key(source_row["Red Fighter"])
        blue_key = canonical_fighter_key(source_row["Blue Fighter"])
        if (
            source_result(source_row) in {"win", "loss"}
            and event_date is not None
            and states[red_key].totalfights >= 2
            and states[blue_key].totalfights >= 2
        ):
            row_queue = queues.get(lookup_key(source_row))
            feature_index = row_queue.popleft() if row_queue else None
            if feature_index is None:
                missing_rows += 1
            else:
                matched_rows += 1
                feature_row = features.loc[feature_index]
                for side in ("Red", "Blue"):
                    fighter_key = canonical_fighter_key(feature_row[f"{side} Fighter"])
                    state = states[fighter_key]
                    denominator = sqr_sum(state.totalfights)
                    if denominator <= 0:
                        continue
                    for base in bases:
                        side_col = f"{side} {base}"
                        diff_col = f"{side} {base} differential"
                        defense_col = f"{side} {base} defense"
                        current_expected = state.scaled_side_sum[base] / denominator
                        unit_corrected = state.unit_side_sum[base] / denominator
                        actual = safe_float(feature_row.get(side_col))
                        if actual is not None:
                            scaled_match_checks += 1
                            if abs(actual - current_expected) > TOLERANCE:
                                scaled_mismatches += 1
                            corrected.at[feature_index, side_col] = unit_corrected
                            records.append(
                                {
                                    "feature": base,
                                    "side": side,
                                    "current_scaled": actual,
                                    "unit_corrected": unit_corrected,
                                }
                            )

                        actual_diff = safe_float(feature_row.get(diff_col))
                        if actual_diff is not None:
                            differential_checks += 1
                            expected_diff = state.differential_sum[base] / denominator
                            if abs(actual_diff - expected_diff) > TOLERANCE:
                                differential_mismatches += 1

                        actual_defense = safe_float(feature_row.get(defense_col))
                        if actual_defense is not None:
                            defense_checks += 1
                            expected_defense = state.defense_sum[base] / denominator
                            if abs(actual_defense - expected_defense) > TOLERANCE:
                                defense_mismatches += 1

                for base in bases:
                    red_col = f"Red {base}"
                    blue_col = f"Blue {base}"
                    oppdiff_col = f"{base} oppdiff"
                    if red_col in corrected.columns and blue_col in corrected.columns and oppdiff_col in corrected.columns:
                        corrected.at[feature_index, oppdiff_col] = (
                            safe_float(corrected.at[feature_index, red_col])
                            - safe_float(corrected.at[feature_index, blue_col])
                        )

        update_percent_state(states, source_row, bases)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    corrected.to_csv(output_path, index=False)
    return {
        "corrected_features_path": str(output_path),
        "percentage_bases": bases,
        "matched_feature_rows": matched_rows,
        "missing_feature_rows": missing_rows,
        "scaled_side_checks": scaled_match_checks,
        "scaled_side_mismatches": scaled_mismatches,
        "differential_checks": differential_checks,
        "differential_mismatches": differential_mismatches,
        "defense_checks": defense_checks,
        "defense_mismatches": defense_mismatches,
        "unit_difference_summaries": summarize_unit_differences(records, importance),
    }


def command_env() -> dict:
    env = os.environ.copy()
    mpl_dir = Path("/tmp/ufc_mplconfig")
    mpl_dir.mkdir(parents=True, exist_ok=True)
    env.setdefault("MPLCONFIGDIR", str(mpl_dir))
    return env


def run_backtest(features_path: str, params_path: str, output_dir: Path, start_date: str, end_date: str, force: bool) -> None:
    summary_path = output_dir / "no_leakage_backtest_summary.json"
    csv_path = output_dir / "no_leakage_backtest.csv"
    if summary_path.exists() and csv_path.exists() and not force:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "testing/no_leakage_backtest.py",
            "--features",
            features_path,
            "--params",
            params_path,
            "--start-date",
            start_date,
            "--end-date",
            end_date,
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
        env=command_env(),
    )


def fmt_float(value, digits=4) -> str:
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


def markdown_report(result: dict) -> str:
    correction = result["correction"]
    lines = [
        "# Feature Percentage Unit Correction Audit",
        "",
        "This audit tests a surgical feature redesign: side percentage columns",
        "such as `Red Leg%` are rebuilt as weighted percentages instead of the",
        "current percentage-per-minute proxy. Existing differential and defense",
        "percentage features are checked but left unchanged.",
        "",
        "## Reconstruction Checks",
        "",
        "| Check | Value |",
        "| --- | ---: |",
        f"| percentage bases | {len(correction['percentage_bases'])} |",
        f"| matched feature rows | {correction['matched_feature_rows']} |",
        f"| missing feature rows | {correction['missing_feature_rows']} |",
        f"| current scaled side checks | {correction['scaled_side_checks']} |",
        f"| current scaled side mismatches | {correction['scaled_side_mismatches']} |",
        f"| percentage differential checks | {correction['differential_checks']} |",
        f"| percentage differential mismatches | {correction['differential_mismatches']} |",
        f"| percentage defense checks | {correction['defense_checks']} |",
        f"| percentage defense mismatches | {correction['defense_mismatches']} |",
        "",
        "Largest active/imported percentage unit shifts:",
        "",
        "| Feature | Importance Sum | Current Mean | Corrected Mean | Mean Abs Diff | Corr |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in correction["unit_difference_summaries"][:12]:
        importance_sum = row["importance_red"] + row["importance_blue"] + row["importance_oppdiff"]
        lines.append(
            "| `{feature}` | {importance:.0f} | {current} | {corrected} | {mad} | {corr} |".format(
                feature=row["feature"],
                importance=importance_sum,
                current=fmt_float(row["current_mean"]),
                corrected=fmt_float(row["corrected_mean"]),
                mad=fmt_float(row["mean_abs_difference"]),
                corr=fmt_float(row["correlation"]),
            )
        )

    lines.extend(
        [
            "",
            "## Leak-Safe Backtests",
            "",
            "| Window | Variant | Fights | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["summaries"]:
        lines.append(
            "| {window} | {label} | {fights} | {acc} | {model_ll} | {market_ll} | {delta} | {profit} | {bets} |".format(
                window=row["window"],
                label=row["label"],
                fights=row["fights"],
                acc=fmt_pct(row["accuracy"]),
                model_ll=fmt_float(row["model_log_loss"]),
                market_ll=fmt_float(row["market_log_loss"]),
                delta=fmt_float(row["model_minus_market_log_loss"]),
                profit=fmt_pct((row["profit_pct"] or 0.0) / 100.0),
                bets=row["bets"],
            )
        )

    lines.extend(["", "## Interpretation", ""])
    for window in WINDOWS:
        rows = [row for row in result["summaries"] if row["window"] == window]
        baseline = next(row for row in rows if row["label"] == "current_regularized")
        corrected = next(row for row in rows if row["label"] == "pct_unit_corrected")
        lines.append(
            "- {window}: unit correction changed model LL from {base_ll} to {corr_ll} and PnL from {base_pnl} to {corr_pnl}.".format(
                window=window,
                base_ll=fmt_float(baseline["model_log_loss"]),
                corr_ll=fmt_float(corrected["model_log_loss"]),
                base_pnl=fmt_pct((baseline["profit_pct"] or 0.0) / 100.0),
                corr_pnl=fmt_pct((corrected["profit_pct"] or 0.0) / 100.0),
            )
        )
    lines.append(
        "- This is a direct test of one feature-unit hypothesis. It should not be promoted unless it improves both probability evidence and downstream nested validation."
    )
    lines.append("")
    return "\n".join(lines)


def audit(args) -> dict:
    output_dir = Path(args.output_dir)
    importance = load_importance(args.feature_importance)
    source = pd.read_csv(args.source_fights)
    features = pd.read_csv(args.features)
    bases = percentage_bases(source)
    corrected_path = output_dir / "features" / "detailed_fights_pct_unit_corrected.csv"
    correction = build_corrected_features(source, features, bases, corrected_path, importance)

    summaries = []
    for window, ledger_dir in BASELINE_LEDGER_DIRS.items():
        summaries.append(summarize_ledger("current_regularized", window, ledger_dir))
    for window, (start_date, end_date) in WINDOWS.items():
        ledger_dir = output_dir / "pct_unit_corrected" / window
        run_backtest(str(corrected_path), args.params, ledger_dir, start_date, end_date, args.force)
        summaries.append(summarize_ledger("pct_unit_corrected", window, ledger_dir))

    return {
        "source_fights": args.source_fights,
        "features": args.features,
        "params": args.params,
        "feature_importance": args.feature_importance,
        "correction": correction,
        "summaries": sorted(summaries, key=lambda row: (row["window"], row["label"])),
    }


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "feature_percentage_unit_correction_audit.json"
    md_path = output_dir / "feature_percentage_unit_correction_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
