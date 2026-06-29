#!/usr/bin/env python3
"""Integrity and context audit for the frozen sigpct/head/raw-pm policy.

This script does not select a new policy. It checks whether the exact feature
columns in the frozen `sigpct_head_raw_pm` challenger are chronological,
correctly signed, and contextually coherent after market control.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_aware_feature_audit import (  # noqa: E402
    VariantSpec,
    aggregate_predictions,
    aligned_market_feature_frame,
    run_observed_predictions,
    summarize_coefficients,
)
from testing.market_residual_meta_audit import iter_folds  # noqa: E402
from testing.statistical_edge_audit import binary_log_loss, brier_score  # noqa: E402
from testing.striking_feature_engineering_audit import (  # noqa: E402
    add_pace_features,
    build_pace_features,
)
from testing.striking_feature_forensics_audit import (  # noqa: E402
    audit_reconstruction,
    canonical_fighter_key,
    chronological_source_rows,
    feature_queues,
    lookup_key,
    parse_date,
    source_result,
)


DEFAULT_POLICY = (
    "test_results/frozen_sigpct_head_raw_pm_challenger_paper_policy/"
    "frozen_sigpct_head_raw_pm_challenger_paper_policy.json"
)
DEFAULT_OUTPUT_DIR = "test_results/striking_policy_feature_context_audit"
EXPECTED_POSITIVE_FEATURES = (
    "market_logit",
    "Sig. str.% differential oppdiff",
    "Head differential oppdiff",
    "Head differential_pm oppdiff",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit exact frozen sigpct/head/raw-pm feature integrity"
    )
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--odds", default="data/fight_results_with_odds.csv")
    parser.add_argument("--fight-details-source", default="data/fight_details_date.csv")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--first-holdout-start", default="2023-01-01")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=200)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--c", type=float, default=None)
    parser.add_argument("--bins", type=int, default=5)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


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


def load_policy(path: str) -> dict:
    with Path(path).open() as file:
        policy = json.load(file)
    feature_columns = tuple(policy["policy"]["feature_columns"])
    if feature_columns != EXPECTED_POSITIVE_FEATURES:
        raise SystemExit(
            "This audit is scoped to the frozen sigpct/head/raw-pm policy; "
            f"got feature columns: {feature_columns}"
        )
    return policy


def strict_prior_date_counts(source: pd.DataFrame) -> dict[str, np.ndarray]:
    rows_by_fighter: dict[str, list[np.datetime64]] = defaultdict(list)
    for row in chronological_source_rows(source):
        date = parse_date(row.get("Date"))
        if date is None:
            continue
        event_day = np.datetime64(date.date())
        rows_by_fighter[canonical_fighter_key(row["Red Fighter"])].append(event_day)
        rows_by_fighter[canonical_fighter_key(row["Blue Fighter"])].append(event_day)
    return {
        fighter: np.array(sorted(days), dtype="datetime64[D]")
        for fighter, days in rows_by_fighter.items()
    }


def count_before_day(indexed: dict[str, np.ndarray], fighter: str, event_day: np.datetime64) -> int:
    days = indexed.get(canonical_fighter_key(fighter))
    if days is None:
        return 0
    return int(np.searchsorted(days, event_day, side="left"))


def audit_chronology(source: pd.DataFrame, features: pd.DataFrame, aligned: pd.DataFrame) -> dict:
    queues = feature_queues(features)
    strict_counts = strict_prior_date_counts(source)
    state_counts: dict[str, int] = defaultdict(int)
    used_indices = set()
    aligned_keys = set(aligned.apply(feature_row_key, axis=1))

    eligible_rows = 0
    matched_rows = 0
    missing_rows = 0
    state_total_checks = 0
    state_total_mismatches = 0
    same_day_prior_feature_sides = 0
    same_day_prior_aligned_sides = 0
    same_day_examples = []
    mismatch_examples = []

    for source_row in chronological_source_rows(source):
        date = parse_date(source_row.get("Date"))
        red_key = canonical_fighter_key(source_row["Red Fighter"])
        blue_key = canonical_fighter_key(source_row["Blue Fighter"])
        result = source_result(source_row)
        eligible = (
            result in {"win", "loss"}
            and date is not None
            and state_counts[red_key] >= 2
            and state_counts[blue_key] >= 2
        )

        if eligible:
            eligible_rows += 1
            queue = queues.get(lookup_key(source_row))
            feature_index = queue.popleft() if queue else None
            if feature_index is None:
                missing_rows += 1
            else:
                matched_rows += 1
                used_indices.add(feature_index)
                feature_row = features.loc[feature_index]
                row_key = feature_row_key(feature_row)
                is_aligned = row_key in aligned_keys
                event_day = np.datetime64(date.date())
                for side in ("Red", "Blue"):
                    fighter = feature_row[f"{side} Fighter"]
                    fighter_key = canonical_fighter_key(fighter)
                    expected_total = state_counts[fighter_key]
                    processed_total = safe_float(feature_row.get(f"{side} totalfights"))
                    if processed_total is not None:
                        state_total_checks += 1
                        if abs(processed_total - expected_total) > 1e-9:
                            state_total_mismatches += 1
                            if len(mismatch_examples) < 20:
                                mismatch_examples.append(
                                    {
                                        "date": date.date().isoformat(),
                                        "title": str(feature_row.get("Title", "")),
                                        "fighter": str(fighter),
                                        "side": side,
                                        "processed_totalfights": processed_total,
                                        "expected_prior_source_order": int(expected_total),
                                    }
                                )

                    strict_total = count_before_day(strict_counts, fighter, event_day)
                    same_day_prior = expected_total - strict_total
                    if same_day_prior > 0:
                        same_day_prior_feature_sides += 1
                        if is_aligned:
                            same_day_prior_aligned_sides += 1
                        if len(same_day_examples) < 20:
                            same_day_examples.append(
                                {
                                    "date": date.date().isoformat(),
                                    "title": str(feature_row.get("Title", "")),
                                    "fighter": str(fighter),
                                    "side": side,
                                    "prior_source_order_total": int(expected_total),
                                    "strict_prior_date_total": int(strict_total),
                                    "same_day_prior_fights": int(same_day_prior),
                                    "aligned_with_market": bool(is_aligned),
                                }
                            )

        state_counts[red_key] += 1
        state_counts[blue_key] += 1

    return {
        "eligible_supervised_rows_from_source": int(eligible_rows),
        "matched_feature_rows": int(matched_rows),
        "missing_feature_rows": int(missing_rows),
        "extra_feature_rows": int(len(features) - len(used_indices)),
        "state_total_checks": int(state_total_checks),
        "state_total_mismatches": int(state_total_mismatches),
        "same_day_prior_feature_sides": int(same_day_prior_feature_sides),
        "same_day_prior_aligned_sides": int(same_day_prior_aligned_sides),
        "same_day_examples": same_day_examples,
        "state_total_mismatch_examples": mismatch_examples,
    }


def feature_row_key(row: pd.Series) -> str:
    date = parse_date(row.get("Date"))
    return "|".join(
        [
            "" if date is None else date.date().isoformat(),
            str(row.get("Title", "")),
            canonical_fighter_key(row.get("Red Fighter", "")),
            canonical_fighter_key(row.get("Blue Fighter", "")),
        ]
    )


def audit_sign_symmetry(aligned: pd.DataFrame, feature_columns: tuple[str, ...]) -> dict:
    rows = []
    for column in feature_columns:
        if column == "market_logit":
            values = pd.to_numeric(aligned[column], errors="coerce")
            rows.append(
                {
                    "feature": column,
                    "rows": int(values.notna().sum()),
                    "mean": float(values.mean()),
                    "std": float(values.std(ddof=0)),
                    "min": float(values.min()),
                    "p01": float(values.quantile(0.01)),
                    "p50": float(values.quantile(0.50)),
                    "p99": float(values.quantile(0.99)),
                    "max": float(values.max()),
                    "missing": int(values.isna().sum()),
                    "oppdiff_reconstruction_mismatches": None,
                }
            )
            continue

        values = pd.to_numeric(aligned[column], errors="coerce")
        mismatches = None
        if column.endswith(" oppdiff"):
            base = column[: -len(" oppdiff")]
            red_col = f"Red {base}"
            blue_col = f"Blue {base}"
            if red_col in aligned.columns and blue_col in aligned.columns:
                red = pd.to_numeric(aligned[red_col], errors="coerce")
                blue = pd.to_numeric(aligned[blue_col], errors="coerce")
                reconstructed = red - blue
                valid = reconstructed.notna() & values.notna()
                mismatches = int((reconstructed[valid] - values[valid]).abs().gt(1e-8).sum())

        rows.append(
            {
                "feature": column,
                "rows": int(values.notna().sum()),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
                "min": float(values.min()),
                "p01": float(values.quantile(0.01)),
                "p50": float(values.quantile(0.50)),
                "p99": float(values.quantile(0.99)),
                "max": float(values.max()),
                "missing": int(values.isna().sum()),
                "oppdiff_reconstruction_mismatches": mismatches,
            }
        )
    return {"features": rows}


def feature_bins(aligned: pd.DataFrame, column: str, bins: int) -> list[dict]:
    values = pd.to_numeric(aligned[column], errors="coerce")
    residual = aligned["red_won"].astype(float) - pd.to_numeric(
        aligned["red_market_probability"],
        errors="coerce",
    )
    work = aligned[values.notna() & residual.notna()].copy()
    if work.empty:
        return []
    work["_feature_value"] = values.loc[work.index]
    work["_market_residual"] = residual.loc[work.index]
    ranks = work["_feature_value"].rank(method="first")
    work["_bin"] = pd.qcut(ranks, q=min(bins, len(work)), labels=False, duplicates="drop")

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


def audit_residual_shape(aligned: pd.DataFrame, feature_columns: tuple[str, ...], bins: int) -> dict:
    result = {}
    residual = aligned["red_won"].astype(float) - pd.to_numeric(
        aligned["red_market_probability"],
        errors="coerce",
    )
    for column in feature_columns:
        if column == "market_logit":
            continue
        values = pd.to_numeric(aligned[column], errors="coerce")
        valid = values.notna() & residual.notna()
        bin_rows = feature_bins(aligned, column, bins)
        low = bin_rows[0]["actual_minus_market"] if bin_rows else None
        high = bin_rows[-1]["actual_minus_market"] if bin_rows else None
        result[column] = {
            "rows": int(valid.sum()),
            "pearson_to_actual_minus_market": float(values[valid].corr(residual[valid], method="pearson")),
            "spearman_to_actual_minus_market": float(values[valid].corr(residual[valid], method="spearman")),
            "lowest_bin_actual_minus_market": low,
            "highest_bin_actual_minus_market": high,
            "high_minus_low_actual_minus_market": None
            if low is None or high is None
            else float(high - low),
            "bins": bin_rows,
        }
    return result


def coefficient_sign_summary(coefficient_rows: list[dict]) -> dict:
    base = summarize_coefficients(coefficient_rows)
    sign_rows = {}
    for row in coefficient_rows:
        coefficients = row.get("coefficients")
        if coefficients is None:
            continue
        for feature, value in zip(row["feature_columns"], coefficients):
            sign_rows.setdefault(feature, []).append(float(value))

    for feature, values in sign_rows.items():
        array = np.asarray(values, dtype=float)
        expected_positive = feature in EXPECTED_POSITIVE_FEATURES
        base.setdefault("sigpct_head_raw_pm", {}).setdefault(feature, {})
        base["sigpct_head_raw_pm"][feature].update(
            {
                "positive_folds": int(np.sum(array > 0.0)),
                "negative_folds": int(np.sum(array < 0.0)),
                "expected_positive_direction": bool(expected_positive),
                "direction_consistent_folds": int(np.sum(array > 0.0))
                if expected_positive
                else int(np.sum(array < 0.0)),
            }
        )
    return base


def summarize_policy_prediction(predictions: pd.DataFrame) -> dict:
    y = predictions["red_won"].astype(float).to_numpy()
    market = predictions["market_probability"].astype(float).to_numpy()
    candidate = predictions["candidate_probability"].astype(float).to_numpy()
    rows = []
    for fold, subset in predictions.groupby("fold", sort=True):
        fold_y = subset["red_won"].astype(float).to_numpy()
        fold_market = subset["market_probability"].astype(float).to_numpy()
        fold_candidate = subset["candidate_probability"].astype(float).to_numpy()
        rows.append(
            {
                "fold": int(fold),
                "rows": int(len(subset)),
                "market_log_loss": binary_log_loss(fold_y, fold_market),
                "candidate_log_loss": binary_log_loss(fold_y, fold_candidate),
                "delta_log_loss": binary_log_loss(fold_y, fold_market)
                - binary_log_loss(fold_y, fold_candidate),
                "delta_brier": brier_score(fold_y, fold_market)
                - brier_score(fold_y, fold_candidate),
            }
        )
    return {
        "rows": int(len(predictions)),
        "market_log_loss": binary_log_loss(y, market),
        "candidate_log_loss": binary_log_loss(y, candidate),
        "delta_log_loss": binary_log_loss(y, market) - binary_log_loss(y, candidate),
        "market_brier": brier_score(y, market),
        "candidate_brier": brier_score(y, candidate),
        "delta_brier": brier_score(y, market) - brier_score(y, candidate),
        "folds": rows,
    }


def compact_reconstruction(raw_reconstruction: dict) -> dict:
    target_features = {
        key: value
        for key, value in raw_reconstruction["target_features"].items()
        if key in {"Sig. str.%", "Head"}
    }
    side_mismatches = sum(row["side_mismatches"] for row in target_features.values())
    oppdiff_mismatches = sum(row["oppdiff_mismatches"] for row in target_features.values())
    return {
        "source_rows": raw_reconstruction["source_rows"],
        "feature_rows": raw_reconstruction["feature_rows"],
        "nonbinary_source_rows": raw_reconstruction["nonbinary_source_rows"],
        "expected_feature_rows_from_source": raw_reconstruction["expected_feature_rows_from_source"],
        "matched_feature_rows": raw_reconstruction["matched_feature_rows"],
        "missing_feature_rows": raw_reconstruction["missing_feature_rows"],
        "extra_feature_rows": raw_reconstruction["extra_feature_rows"],
        "rows_with_prior_nonbinary_state": raw_reconstruction["rows_with_prior_nonbinary_state"],
        "target_features": target_features,
        "side_mismatches": int(side_mismatches),
        "oppdiff_mismatches": int(oppdiff_mismatches),
        "hard_failures": int(
            raw_reconstruction["missing_feature_rows"] + side_mismatches + oppdiff_mismatches
        ),
    }


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    policy = load_policy(args.policy)
    policy_cfg = policy["policy"]
    feature_columns = tuple(policy_cfg["feature_columns"])
    c_value = float(policy_cfg["logistic_l2_c"] if args.c is None else args.c)

    source = pd.read_csv(args.source_fights)
    features = pd.read_csv(args.features)
    pace_features, pace_reconstruction = build_pace_features(source, features)

    align_args = argparse.Namespace(
        features=args.features,
        odds=args.odds,
        fight_details_source=args.fight_details_source,
        min_training_date=args.min_training_date,
        last_holdout_end=args.last_holdout_end,
        include_womens_fights=False,
    )
    aligned, alignment_metadata = aligned_market_feature_frame(align_args)
    aligned, pace_metadata = add_pace_features(aligned, pace_features)

    missing_policy_columns = [column for column in feature_columns if column not in aligned.columns]
    if missing_policy_columns:
        raise SystemExit(f"Missing policy feature columns after augmentation: {missing_policy_columns}")

    folds = iter_folds(
        aligned,
        args.first_holdout_start,
        args.last_holdout_end,
        args.dev_days,
        args.holdout_days,
        args.step_days,
        args.min_dev_fights,
        args.min_holdout_fights,
    )
    if not folds:
        raise SystemExit("No folds met the minimum fight constraints")

    variant = VariantSpec(
        "sigpct_head_raw_pm",
        feature_columns,
        "frozen sigpct/head/raw-head plus source-derived head pace challenger",
    )
    predictions, coefficients, fold_rows = run_observed_predictions(
        aligned,
        folds,
        [variant],
        c_value,
    )
    summary = aggregate_predictions(
        predictions,
        [variant],
        args.bootstrap_iterations,
        rng,
    )

    return {
        "policy_path": args.policy,
        "source_fights": args.source_fights,
        "features": args.features,
        "odds": args.odds,
        "fight_details_source": args.fight_details_source,
        "policy": {
            "name": policy_cfg["name"],
            "feature_columns": list(feature_columns),
            "logistic_l2_c": c_value,
            "include_womens_fights": policy_cfg.get("include_womens_fights"),
            "event_cap": policy_cfg.get("event_cap"),
            "min_edge": policy_cfg.get("min_edge"),
            "stake_units": policy_cfg.get("stake_units"),
        },
        "alignment_metadata": {**alignment_metadata, **pace_metadata},
        "pace_reconstruction": pace_reconstruction,
        "raw_reconstruction": compact_reconstruction(audit_reconstruction(source, features)),
        "chronology": audit_chronology(source, features, aligned),
        "sign_symmetry": audit_sign_symmetry(aligned, feature_columns),
        "market_residual_shape": audit_residual_shape(aligned, feature_columns, args.bins),
        "policy_prediction_summary": summarize_policy_prediction(
            predictions[predictions["variant"].eq(variant.name)].copy()
        ),
        "aggregate_summary": summary,
        "coefficient_summary": coefficient_sign_summary(coefficients),
        "folds": fold_rows,
        "bootstrap_iterations": args.bootstrap_iterations,
        "seed": args.seed,
    }


def markdown_report(result: dict) -> str:
    policy = result["policy"]
    pace = result["pace_reconstruction"]
    raw = result["raw_reconstruction"]
    chronology = result["chronology"]
    prediction = result["policy_prediction_summary"]
    summary = result["aggregate_summary"]["sigpct_head_raw_pm"]
    bootstrap = summary.get("event_bootstrap") or {}
    coefficients = result["coefficient_summary"]["sigpct_head_raw_pm"]

    hard_failures = (
        raw["hard_failures"]
        + pace["missing_feature_rows"]
        + pace["side_rate_mismatches"]
        + result["alignment_metadata"]["aligned_rows_missing_pace_features"]
        + chronology["state_total_mismatches"]
    )

    lines = [
        "# Striking Policy Feature Context Audit",
        "",
        "This audit checks the exact frozen `sigpct_head_raw_pm` challenger inputs.",
        "It is a diagnostic for feature correctness and context, not a new policy",
        "selection run.",
        "",
        "## Frozen Policy Checked",
        "",
        f"- policy: `{policy['name']}`",
        f"- logistic L2 C: `{policy['logistic_l2_c']}`",
        f"- event cap: `{policy['event_cap']}`",
        f"- min edge: `{policy['min_edge']}`",
        "- features: `" + "`, `".join(policy["feature_columns"]) + "`",
        "",
        "## Integrity Checks",
        "",
        "| Check | Value |",
        "| --- | ---: |",
        f"| hard failures | {hard_failures} |",
        f"| raw source rows | {raw['source_rows']} |",
        f"| supervised feature rows matched from source | {raw['matched_feature_rows']} |",
        f"| raw sig/head side mismatches | {raw['side_mismatches']} |",
        f"| raw sig/head oppdiff mismatches | {raw['oppdiff_mismatches']} |",
        f"| rows with prior non-binary state | {raw['rows_with_prior_nonbinary_state']} |",
        f"| source-derived pace rows | {pace['derived_feature_rows']} |",
        f"| pace side-rate checks | {pace['side_rate_checks']} |",
        f"| pace side-rate mismatches | {pace['side_rate_mismatches']} |",
        f"| aligned rows missing pace features | {result['alignment_metadata']['aligned_rows_missing_pace_features']} |",
        f"| totalfights chronology checks | {chronology['state_total_checks']} |",
        f"| totalfights chronology mismatches | {chronology['state_total_mismatches']} |",
        f"| same-day prior feature sides | {chronology['same_day_prior_feature_sides']} |",
        f"| same-day prior market-aligned sides | {chronology['same_day_prior_aligned_sides']} |",
        "",
        "Same-day prior rows mean the chronological source order included an earlier",
        "fight on the same calendar day for that fighter. The market-aligned count",
        "is the relevant leakage risk for this policy's evaluated odds universe.",
        "",
        "## Feature Sign And Reconstruction",
        "",
        "| Feature | Rows | Missing | Mean | p01 | p50 | p99 | Oppdiff Mismatches |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in result["sign_symmetry"]["features"]:
        lines.append(
            "| `{feature}` | {rows} | {missing} | {mean} | {p01} | {p50} | {p99} | {mismatches} |".format(
                feature=row["feature"],
                rows=row["rows"],
                missing=row["missing"],
                mean=fmt_float(row["mean"]),
                p01=fmt_float(row["p01"]),
                p50=fmt_float(row["p50"]),
                p99=fmt_float(row["p99"]),
                mismatches="" if row["oppdiff_reconstruction_mismatches"] is None else row["oppdiff_reconstruction_mismatches"],
            )
        )

    lines.extend(
        [
            "",
            "## Coefficient Stability",
            "",
            "Coefficients are from standardized, median-imputed, mirrored logistic folds.",
            "Positive direction is expected for all four policy inputs.",
            "",
            "| Feature | Mean Coef | Std | Min | Max | Positive Folds | Direction Consistent |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for feature in policy["feature_columns"]:
        row = coefficients[feature]
        lines.append(
            "| `{feature}` | {mean} | {std} | {minv} | {maxv} | {pos}/{folds} | {direction}/{folds} |".format(
                feature=feature,
                mean=fmt_float(row["mean"], 4),
                std=fmt_float(row["std"], 4),
                minv=fmt_float(row["min"], 4),
                maxv=fmt_float(row["max"], 4),
                pos=row["positive_folds"],
                direction=row["direction_consistent_folds"],
                folds=row["folds"],
            )
        )

    lines.extend(
        [
            "",
            "## Policy Probability Check",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| evaluated rows | {prediction['rows']} |",
            f"| market log loss | {fmt_float(prediction['market_log_loss'])} |",
            f"| candidate log loss | {fmt_float(prediction['candidate_log_loss'])} |",
            f"| delta log loss | {fmt_float(prediction['delta_log_loss'])} |",
            f"| market Brier | {fmt_float(prediction['market_brier'])} |",
            f"| candidate Brier | {fmt_float(prediction['candidate_brier'])} |",
            f"| delta Brier | {fmt_float(prediction['delta_brier'])} |",
            f"| positive folds | {summary['positive_folds']} / {summary['folds']} |",
            f"| event-bootstrap P(delta <= 0) | {fmt_float(bootstrap.get('prob_delta_le_zero'), 4)} |",
            "",
            "## Feature Residual Shape",
            "",
            "| Feature | Rows | Spearman vs Actual-Market | Low Bin A-M | High Bin A-M | High-Low |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for feature, row in result["market_residual_shape"].items():
        lines.append(
            "| `{feature}` | {rows} | {spearman} | {low} | {high} | {spread} |".format(
                feature=feature,
                rows=row["rows"],
                spearman=fmt_float(row["spearman_to_actual_minus_market"]),
                low=fmt_pct(row["lowest_bin_actual_minus_market"]),
                high=fmt_pct(row["highest_bin_actual_minus_market"]),
                spread=fmt_pct(row["high_minus_low_actual_minus_market"]),
            )
        )

    for feature, row in result["market_residual_shape"].items():
        lines.extend(
            [
                "",
                f"### `{feature}` Bins",
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

    lines.extend(["", "## Interpretation", ""])
    if hard_failures:
        lines.append(
            "- Hard feature integrity failures were found; do not treat the current edge claim as reliable until they are explained."
        )
    else:
        lines.append(
            "- The exact frozen policy inputs passed the direct reconstruction and chronology checks in this audit."
        )
    if chronology["same_day_prior_aligned_sides"] == 0:
        lines.append(
            "- No same-day source-order prior fights were detected in the feature rows or market-aligned evaluated universe."
        )
    else:
        lines.append(
            "- Same-day source ordering appears inside the market-aligned universe; this needs a stricter event-order review before promotion."
        )
    lines.append(
        "- Non-binary outcomes still matter as prior fighter state, but they are absent from supervised win/loss labels."
    )
    direction_bad = [
        feature
        for feature in policy["feature_columns"]
        if coefficients[feature]["direction_consistent_folds"] != coefficients[feature]["folds"]
    ]
    if direction_bad:
        lines.append(
            "- Some standardized coefficients did not match the simple expected positive direction: "
            + ", ".join(f"`{feature}`" for feature in direction_bad)
            + "."
        )
        if "Head differential_pm oppdiff" in direction_bad:
            lines.append(
                "- In this raw-plus-pace policy, `Head differential_pm oppdiff` behaves like a conditional pace-normalizer rather than a standalone 'more head pace is better' feature."
            )
    else:
        lines.append(
            "- All standardized policy coefficients were positive in every fold, matching the intended fight-context direction."
        )
    lines.append(
        "- Residual-shape bins are descriptive; they support feature sanity, not a fresh live-staking claim."
    )
    lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_policy_feature_context_audit.json"
    md_path = output_dir / "striking_policy_feature_context_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
