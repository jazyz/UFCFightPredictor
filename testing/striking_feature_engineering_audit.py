#!/usr/bin/env python3
"""Feature-engineering audit for fight-interpretable striking variants.

The frozen striking-core policy uses weighted count differentials for raw
significant strikes and head strikes. This audit keeps the same market-aware
rolling protocol, reconstructs pace-adjusted striking alternatives from the
chronological source, and checks whether those alternatives improve the edge
case without adding an event cap.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
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
    market_null_simulation,
    run_observed_predictions,
)
from testing.market_residual_meta_audit import event_bootstrap_delta, iter_folds  # noqa: E402
from testing.statistical_edge_audit import binary_log_loss, brier_score  # noqa: E402
from testing.striking_core_betting_calibration_audit import (  # noqa: E402
    add_bet_rows,
    attach_odds,
)
from testing.striking_core_predeclared_backtest import (  # noqa: E402
    event_bootstrap_profit,
    market_null_bets,
)
from testing.striking_feature_forensics_audit import (  # noqa: E402
    canonical_fighter_key,
    chronological_source_rows,
    feature_queues,
    lookup_key,
    parse_date,
    safe_float,
    source_result,
    sqr_sum,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_feature_engineering_audit"
EDGE_THRESHOLD = 0.02
RATE_BASES = (
    "Sig. str.",
    "Head",
    "Body",
    "Leg",
    "Distance",
    "Clinch",
    "Ground",
    "Total str.",
)
COUNT_DIFF_BASES = ("KD", "Td")
CURRENT_CORE = (
    "market_logit",
    "Sig. str.% differential oppdiff",
    "Sig. str. differential oppdiff",
    "Head differential oppdiff",
)


@dataclass
class PaceState:
    totalfights: int = 0
    sums: dict[str, float] = field(default_factory=lambda: defaultdict(float))


def parse_args():
    parser = argparse.ArgumentParser(description="Audit pace-adjusted striking feature variants")
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
    parser.add_argument("--c", type=float, default=0.1)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=200)
    parser.add_argument("--bet-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_units(value) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


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


def elapsed_minutes(row: pd.Series) -> float | None:
    round_number = safe_float(row.get("Round"))
    time_value = safe_float(row.get("Time"))
    if round_number is None or time_value is None:
        return None
    elapsed = (round_number - 1.0) * 5.0 + time_value
    if elapsed <= 0.0 or not np.isfinite(elapsed):
        return None
    return float(elapsed)


def state_value(state: PaceState, feature: str) -> float | None:
    denominator = sqr_sum(state.totalfights)
    if denominator <= 0:
        return None
    return float(state.sums[feature] / denominator)


def oppdiff_value(states: dict[str, PaceState], red_key: str, blue_key: str, feature: str) -> float | None:
    red_value = state_value(states[red_key], feature)
    blue_value = state_value(states[blue_key], feature)
    if red_value is None or blue_value is None:
        return None
    return float(red_value - blue_value)


def update_pace_state(states: defaultdict[str, PaceState], row: pd.Series) -> None:
    red_key = canonical_fighter_key(row["Red Fighter"])
    blue_key = canonical_fighter_key(row["Blue Fighter"])
    red_state = states[red_key]
    blue_state = states[blue_key]
    red_state.totalfights += 1
    blue_state.totalfights += 1
    red_weight = red_state.totalfights**2
    blue_weight = blue_state.totalfights**2
    minutes = elapsed_minutes(row)

    for base in RATE_BASES:
        red_value = safe_float(row.get(f"Red {base}"))
        blue_value = safe_float(row.get(f"Blue {base}"))
        if red_value is None or blue_value is None or minutes is None:
            continue
        red_for_pm = red_value / minutes
        blue_for_pm = blue_value / minutes
        red_state.sums[f"{base} for_pm"] += red_for_pm * red_weight
        blue_state.sums[f"{base} for_pm"] += blue_for_pm * blue_weight
        red_state.sums[f"{base} against_pm"] += blue_for_pm * red_weight
        blue_state.sums[f"{base} against_pm"] += red_for_pm * blue_weight
        red_state.sums[f"{base} differential_pm"] += (red_for_pm - blue_for_pm) * red_weight
        blue_state.sums[f"{base} differential_pm"] += (blue_for_pm - red_for_pm) * blue_weight

    for base in COUNT_DIFF_BASES:
        red_value = safe_float(row.get(f"Red {base}"))
        blue_value = safe_float(row.get(f"Blue {base}"))
        if red_value is None or blue_value is None:
            continue
        red_state.sums[f"{base} differential_pf"] += (red_value - blue_value) * red_weight
        blue_state.sums[f"{base} differential_pf"] += (blue_value - red_value) * blue_weight


def pace_feature_values(states: dict[str, PaceState], red_key: str, blue_key: str) -> dict:
    record = {}
    for base in RATE_BASES:
        record[f"{base} for_pm oppdiff"] = oppdiff_value(
            states,
            red_key,
            blue_key,
            f"{base} for_pm",
        )
        record[f"{base} against_pm oppdiff"] = oppdiff_value(
            states,
            red_key,
            blue_key,
            f"{base} against_pm",
        )
        record[f"{base} differential_pm oppdiff"] = oppdiff_value(
            states,
            red_key,
            blue_key,
            f"{base} differential_pm",
        )
    for base in COUNT_DIFF_BASES:
        record[f"{base} differential_pf oppdiff"] = oppdiff_value(
            states,
            red_key,
            blue_key,
            f"{base} differential_pf",
        )
    return record


def build_current_pace_features(
    source: pd.DataFrame,
    feature_rows: pd.DataFrame,
    through_date=None,
) -> pd.DataFrame:
    states: defaultdict[str, PaceState] = defaultdict(PaceState)
    cutoff = pd.Timestamp(through_date).normalize() if through_date else None
    for source_row in chronological_source_rows(source):
        event_date = parse_date(source_row.get("Date"))
        if cutoff is not None and event_date is not None and event_date > cutoff:
            continue
        update_pace_state(states, source_row)

    records = []
    for _, row in feature_rows.iterrows():
        red_key = canonical_fighter_key(row.get("Red Fighter", ""))
        blue_key = canonical_fighter_key(row.get("Blue Fighter", ""))
        records.append(pace_feature_values(states, red_key, blue_key))
    return pd.DataFrame(records, index=feature_rows.index)


def build_pace_features(source: pd.DataFrame, features: pd.DataFrame, tolerance: float = 1e-8) -> tuple[pd.DataFrame, dict]:
    queues = feature_queues(features)
    states: defaultdict[str, PaceState] = defaultdict(PaceState)
    records = []
    used_indices = set()
    expected_feature_rows = 0
    matched_feature_rows = 0
    missing_feature_rows = 0
    side_rate_checks = 0
    side_rate_mismatches = 0
    side_rate_max_abs_error = 0.0

    for source_row in chronological_source_rows(source):
        event_date = parse_date(source_row.get("Date"))
        red_source_key = canonical_fighter_key(source_row["Red Fighter"])
        blue_source_key = canonical_fighter_key(source_row["Blue Fighter"])
        result = source_result(source_row)
        eligible = (
            result in {"win", "loss"}
            and event_date is not None
            and states[red_source_key].totalfights >= 2
            and states[blue_source_key].totalfights >= 2
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
                record = {
                    "_audit_row_key": feature_row_key(feature_row),
                    "Date": feature_row["Date"],
                    "Title": feature_row["Title"],
                    "Red Fighter": feature_row["Red Fighter"],
                    "Blue Fighter": feature_row["Blue Fighter"],
                }

                record.update(pace_feature_values(states, feature_red_key, feature_blue_key))
                for base in RATE_BASES:
                    for_pm_feature = f"{base} for_pm"
                    for side, fighter_key in (("Red", feature_red_key), ("Blue", feature_blue_key)):
                        expected = state_value(states[fighter_key], for_pm_feature)
                        actual = safe_float(feature_row.get(f"{side} {base}"))
                        if expected is None or actual is None:
                            continue
                        side_rate_checks += 1
                        error = abs(actual - expected)
                        side_rate_max_abs_error = max(side_rate_max_abs_error, float(error))
                        if error > tolerance:
                            side_rate_mismatches += 1

                records.append(record)

        update_pace_state(states, source_row)

    derived = pd.DataFrame(records)
    return derived, {
        "source_rows": int(len(source)),
        "feature_rows": int(len(features)),
        "expected_supervised_rows": int(expected_feature_rows),
        "matched_supervised_rows": int(matched_feature_rows),
        "missing_feature_rows": int(missing_feature_rows),
        "extra_feature_rows": int(len(features) - len(used_indices)),
        "side_rate_checks": int(side_rate_checks),
        "side_rate_mismatches": int(side_rate_mismatches),
        "side_rate_max_abs_error": float(side_rate_max_abs_error),
        "derived_feature_rows": int(len(derived)),
    }


def add_pace_features(aligned: pd.DataFrame, pace_features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    working = aligned.copy()
    working["_audit_row_key"] = working.apply(feature_row_key, axis=1)
    duplicate_keys = int(pace_features["_audit_row_key"].duplicated().sum()) if not pace_features.empty else 0
    pace_unique = pace_features.drop_duplicates("_audit_row_key", keep="last")
    feature_columns = [column for column in pace_unique.columns if column not in {"_audit_row_key", "Date", "Title", "Red Fighter", "Blue Fighter"}]
    merged = working.merge(
        pace_unique[["_audit_row_key", *feature_columns]],
        on="_audit_row_key",
        how="left",
        validate="many_to_one",
    )
    missing_rows = int(merged[feature_columns].isna().all(axis=1).sum()) if feature_columns else len(merged)
    merged = merged.drop(columns=["_audit_row_key"])
    return merged, {
        "pace_feature_columns": feature_columns,
        "pace_feature_duplicate_keys": duplicate_keys,
        "aligned_rows_missing_pace_features": missing_rows,
    }


def build_variants() -> list[VariantSpec]:
    return [
        VariantSpec("market_recalibrated", ("market_logit",), "market logit recalibration only"),
        VariantSpec(
            "current_mixed_core",
            CURRENT_CORE,
            "frozen current count-differential mixed striking core",
        ),
        VariantSpec(
            "current_sigpct_head",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
            ),
            "frozen challenger-style count-differential sigpct/head core",
        ),
        VariantSpec(
            "pace_adjusted_mixed_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential_pm oppdiff",
                "Head differential_pm oppdiff",
            ),
            "replace raw significant/head count differentials with per-minute differentials",
        ),
        VariantSpec(
            "rate_volume_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. for_pm oppdiff",
                "Sig. str. differential_pm oppdiff",
                "Head differential_pm oppdiff",
            ),
            "pace-adjusted efficiency plus own significant-strike volume",
        ),
        VariantSpec(
            "location_rate_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential_pm oppdiff",
                "Body differential_pm oppdiff",
                "Leg differential_pm oppdiff",
            ),
            "pace-adjusted head/body/leg differential mix",
        ),
        VariantSpec(
            "position_rate_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Distance differential_pm oppdiff",
                "Clinch differential_pm oppdiff",
                "Ground differential_pm oppdiff",
            ),
            "pace-adjusted distance/clinch/ground differential mix",
        ),
        VariantSpec(
            "damage_rate_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "KD differential_pf oppdiff",
                "Head differential_pm oppdiff",
            ),
            "knockdown differential plus pace-adjusted head striking",
        ),
    ]


def summarize_probability(predictions: pd.DataFrame, variant_name: str) -> dict:
    subset = predictions[predictions["variant"].eq(variant_name)]
    y = subset["red_won"].astype(float).to_numpy()
    market = subset["market_probability"].astype(float).to_numpy()
    candidate = subset["candidate_probability"].astype(float).to_numpy()
    return {
        "variant": variant_name,
        "fights": int(len(subset)),
        "market_log_loss": binary_log_loss(y, market),
        "candidate_log_loss": binary_log_loss(y, candidate),
        "delta_log_loss": binary_log_loss(y, market) - binary_log_loss(y, candidate),
        "delta_brier": brier_score(y, market) - brier_score(y, candidate),
        "accuracy": float(np.mean((candidate >= 0.5) == y)),
        "mean_abs_move": float(np.mean(np.abs(candidate - market))),
    }


def summarize_prediction_frame(
    frame: pd.DataFrame,
    label: str,
    bootstrap_iterations: int,
    rng,
) -> dict:
    if frame.empty:
        return {
            "variant": label,
            "fights": 0,
            "market_log_loss": None,
            "candidate_log_loss": None,
            "delta_log_loss": None,
            "delta_brier": None,
            "accuracy": None,
            "mean_abs_move": None,
            "positive_folds": 0,
            "folds": 0,
            "bootstrap_p_delta_le_zero": None,
        }
    y = frame["red_won"].astype(float).to_numpy()
    market = frame["market_probability"].astype(float).to_numpy()
    candidate = frame["candidate_probability"].astype(float).to_numpy()
    fold_deltas = []
    for _, fold_subset in frame.groupby("fold", sort=True):
        fold_y = fold_subset["red_won"].astype(float).to_numpy()
        fold_deltas.append(
            binary_log_loss(
                fold_y,
                fold_subset["market_probability"].astype(float).to_numpy(),
            )
            - binary_log_loss(
                fold_y,
                fold_subset["candidate_probability"].astype(float).to_numpy(),
            )
        )
    bootstrap_input = frame.rename(columns={"candidate_probability": "meta_probability"})
    bootstrap = event_bootstrap_delta(bootstrap_input, bootstrap_iterations, rng)
    return {
        "variant": label,
        "fights": int(len(frame)),
        "market_log_loss": binary_log_loss(y, market),
        "candidate_log_loss": binary_log_loss(y, candidate),
        "delta_log_loss": binary_log_loss(y, market) - binary_log_loss(y, candidate),
        "delta_brier": brier_score(y, market) - brier_score(y, candidate),
        "accuracy": float(np.mean((candidate >= 0.5) == y)),
        "mean_abs_move": float(np.mean(np.abs(candidate - market))),
        "positive_folds": int(np.sum(np.asarray(fold_deltas) > 0.0)),
        "folds": int(len(fold_deltas)),
        "bootstrap_p_delta_le_zero": None if bootstrap is None else bootstrap["prob_delta_le_zero"],
    }


def rolling_prior_probability_selection(
    predictions: pd.DataFrame,
    candidate_names: list[str],
    min_prior_rows: int = 80,
) -> tuple[pd.DataFrame, list[dict]]:
    selected_parts = []
    path = []
    folds = sorted(int(value) for value in predictions["fold"].unique())
    for fold in folds[1:]:
        prior = predictions[
            predictions["fold"].lt(fold) & predictions["variant"].isin(candidate_names)
        ].copy()
        scores = []
        for name in candidate_names:
            subset = prior[prior["variant"].eq(name)]
            if len(subset) < min_prior_rows:
                continue
            y = subset["red_won"].astype(float).to_numpy()
            delta = binary_log_loss(
                y,
                subset["market_probability"].astype(float).to_numpy(),
            ) - binary_log_loss(
                y,
                subset["candidate_probability"].astype(float).to_numpy(),
            )
            scores.append(
                {
                    "variant": name,
                    "prior_rows": int(len(subset)),
                    "prior_delta_log_loss": float(delta),
                }
            )
        if not scores:
            continue
        selected = max(scores, key=lambda row: row["prior_delta_log_loss"])
        eval_rows = predictions[
            predictions["fold"].eq(fold) & predictions["variant"].eq(selected["variant"])
        ].copy()
        if eval_rows.empty:
            continue
        eval_y = eval_rows["red_won"].astype(float).to_numpy()
        eval_delta = binary_log_loss(
            eval_y,
            eval_rows["market_probability"].astype(float).to_numpy(),
        ) - binary_log_loss(
            eval_y,
            eval_rows["candidate_probability"].astype(float).to_numpy(),
        )
        eval_rows["selected_source_variant"] = selected["variant"]
        eval_rows["variant"] = "rolling_prior_probability_delta"
        selected_parts.append(eval_rows)
        path.append(
            {
                **selected,
                "fold": int(fold),
                "eval_rows": int(len(eval_rows)),
                "eval_delta_log_loss": float(eval_delta),
            }
        )
    selected_frame = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    return selected_frame, path


def summarize_bets_for_variant(
    predictions: pd.DataFrame,
    aligned: pd.DataFrame,
    variant_name: str,
    bootstrap_iterations: int,
    null_iterations: int,
    rng,
) -> tuple[pd.DataFrame, dict]:
    subset = predictions[predictions["variant"].eq(variant_name)].copy()
    with_odds = attach_odds(subset, aligned)
    bets = add_bet_rows(with_odds, EDGE_THRESHOLD)
    if bets.empty:
        return bets, {
            "variant": variant_name,
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_minus_market": None,
            "positive_folds": 0,
            "folds": 0,
            "bootstrap_p_profit_le_zero": None,
            "market_null_p": None,
        }
    bets["variant"] = variant_name
    fold_profit = bets.groupby("fold", sort=True)["profit"].sum()
    bootstrap = event_bootstrap_profit(bets, bootstrap_iterations, rng)
    null = market_null_bets(bets, null_iterations, rng)
    return bets, {
        "variant": variant_name,
        "bets": int(len(bets)),
        "events": int(pd.to_datetime(bets["event_date"]).nunique()),
        "profit": float(bets["profit"].astype(float).sum()),
        "roi": float(bets["profit"].astype(float).mean()),
        "actual_minus_market": float(
            bets["bet_won"].astype(float).mean()
            - bets["market_probability"].astype(float).mean()
        ),
        "positive_folds": int((fold_profit > 0.0).sum()),
        "folds": int(len(fold_profit)),
        "bootstrap_p_profit_le_zero": None if bootstrap is None else bootstrap["prob_profit_le_zero"],
        "market_null_p": None if null is None else null["p_value_observed_or_better"],
    }


def summarize_bet_frame(
    bets: pd.DataFrame,
    label: str,
    bootstrap_iterations: int,
    null_iterations: int,
    rng,
) -> dict:
    if bets.empty:
        return {
            "variant": label,
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_minus_market": None,
            "positive_folds": 0,
            "folds": 0,
            "bootstrap_p_profit_le_zero": None,
            "market_null_p": None,
        }
    fold_profit = bets.groupby("fold", sort=True)["profit"].sum()
    bootstrap = event_bootstrap_profit(bets, bootstrap_iterations, rng)
    null = market_null_bets(bets, null_iterations, rng)
    return {
        "variant": label,
        "bets": int(len(bets)),
        "events": int(pd.to_datetime(bets["event_date"]).nunique()),
        "profit": float(bets["profit"].astype(float).sum()),
        "roi": float(bets["profit"].astype(float).mean()),
        "actual_minus_market": float(
            bets["bet_won"].astype(float).mean()
            - bets["market_probability"].astype(float).mean()
        ),
        "positive_folds": int((fold_profit > 0.0).sum()),
        "folds": int(len(fold_profit)),
        "bootstrap_p_profit_le_zero": None if bootstrap is None else bootstrap["prob_profit_le_zero"],
        "market_null_p": None if null is None else null["p_value_observed_or_better"],
    }


def rolling_prior_profit_selection(
    bets: pd.DataFrame,
    candidate_names: list[str],
    min_prior_bets: int = 25,
) -> tuple[pd.DataFrame, list[dict]]:
    if bets.empty:
        return pd.DataFrame(), []
    selected_parts = []
    path = []
    folds = sorted(int(value) for value in bets["fold"].unique())
    for fold in folds[1:]:
        prior = bets[bets["fold"].lt(fold) & bets["variant"].isin(candidate_names)].copy()
        scores = []
        for name in candidate_names:
            subset = prior[prior["variant"].eq(name)]
            if len(subset) < min_prior_bets:
                continue
            scores.append(
                {
                    "variant": name,
                    "prior_bets": int(len(subset)),
                    "prior_profit": float(subset["profit"].astype(float).sum()),
                    "prior_roi": float(subset["profit"].astype(float).mean()),
                }
            )
        if not scores:
            continue
        selected = max(scores, key=lambda row: (row["prior_profit"], row["prior_roi"]))
        eval_rows = bets[bets["fold"].eq(fold) & bets["variant"].eq(selected["variant"])].copy()
        if eval_rows.empty:
            continue
        selected_parts.append(eval_rows.assign(selected_source_variant=selected["variant"]))
        path.append(
            {
                **selected,
                "fold": int(fold),
                "eval_bets": int(len(eval_rows)),
                "eval_profit": float(eval_rows["profit"].astype(float).sum()),
                "eval_roi": float(eval_rows["profit"].astype(float).mean()),
            }
        )
    selected_frame = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    if not selected_frame.empty:
        selected_frame["variant"] = "rolling_prior_profit"
    return selected_frame, path


def probability_table(rows: list[dict], market_null: dict | None, summary: dict) -> list[str]:
    lines = [
        "| Variant | Features | Fights | Delta LL | Delta Brier | Accuracy | Mean Abs Move | Positive Folds | Boot P(delta<=0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(rows, key=lambda item: item["delta_log_loss"], reverse=True):
        variant_summary = summary[row["variant"]]
        bootstrap = variant_summary.get("event_bootstrap") or {}
        null = (market_null or {}).get(row["variant"], {})
        lines.append(
            "| {variant} | {features} | {fights} | {delta_ll} | {delta_brier} | {accuracy} | {move} | {pos} / {folds} | {boot} | {null_p} |".format(
                variant=f"`{row['variant']}`",
                features=len(variant_summary["feature_columns"]),
                fights=row["fights"],
                delta_ll=fmt_float(row["delta_log_loss"]),
                delta_brier=fmt_float(row["delta_brier"]),
                accuracy=fmt_pct(row["accuracy"]),
                move=fmt_pct(row["mean_abs_move"]),
                pos=variant_summary["positive_folds"],
                folds=variant_summary["folds"],
                boot=fmt_p(bootstrap.get("prob_delta_le_zero")),
                null_p=fmt_p(null.get("p_value_observed_or_better")),
            )
        )
    return lines


def rolling_probability_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Selector | Fights | Delta LL | Delta Brier | Accuracy | Mean Abs Move | Positive Folds | Boot P(delta<=0) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| `{variant}` | {fights} | {delta_ll} | {delta_brier} | {accuracy} | {move} | {pos} / {folds} | {boot} |".format(
                variant=row["variant"],
                fights=row["fights"],
                delta_ll=fmt_float(row["delta_log_loss"]),
                delta_brier=fmt_float(row["delta_brier"]),
                accuracy=fmt_pct(row["accuracy"]),
                move=fmt_pct(row["mean_abs_move"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(row["bootstrap_p_delta_le_zero"]),
            )
        )
    return lines


def selection_path_table(rows: list[dict], score_key: str, eval_key: str, count_key: str) -> list[str]:
    lines = [
        "| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {fold} | `{variant}` | {prior_count} | {prior_score} | {eval_count} | {eval_score} |".format(
                fold=row["fold"],
                variant=row["variant"],
                prior_count=row.get("prior_rows", row.get("prior_bets")),
                prior_score=fmt_float(row[score_key]) if "delta" in score_key else fmt_units(row[score_key]),
                eval_count=row[count_key],
                eval_score=fmt_float(row[eval_key]) if "delta" in eval_key else fmt_units(row[eval_key]),
            )
        )
    return lines


def bet_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Variant | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(rows, key=lambda item: item["profit"], reverse=True):
        lines.append(
            "| {variant} | {bets} | {events} | {profit} | {roi} | {actual_market} | {pos} / {folds} | {boot} | {null_p} |".format(
                variant=f"`{row['variant']}`",
                bets=row["bets"],
                events=row["events"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(row["bootstrap_p_profit_le_zero"]),
                null_p=fmt_p(row["market_null_p"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    probability_rows = result["probability_rows"]
    bet_rows = result["bet_rows"]
    best_probability = max(probability_rows, key=lambda row: row["delta_log_loss"])
    best_bet = max(bet_rows, key=lambda row: row["profit"])
    lines = [
        "# Striking Feature Engineering Audit",
        "",
        "This audit tests whether more fight-interpretable pace-adjusted striking",
        "features improve the market-aware striking-core signal. It keeps the",
        "same rolling date folds and no event cap.",
        "",
        "## Protocol",
        "",
        f"- aligned men-only feature/odds rows: `{result['metadata']['aligned_rows']}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- first holdout start: `{result['parameters']['first_holdout_start']}`",
        f"- last holdout end: `{result['parameters']['last_holdout_end']}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- fixed betting threshold: `{fmt_pct(EDGE_THRESHOLD)}`",
        "- event cap: none",
        "",
        "## Feature Reconstruction",
        "",
        "| Check | Value |",
        "| --- | ---: |",
    ]
    for key, value in result["pace_reconstruction"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "The current side rate columns such as `Red Sig. str.` reconstruct as",
            "weighted prior per-minute rates. The frozen raw differential columns",
            "remain weighted count differentials per fight; the `*_differential_pm`",
            "columns created here are the pace-adjusted alternatives.",
            "",
            "## Probability Results",
            "",
            *probability_table(
                probability_rows,
                result.get("market_null"),
                result["summary"],
            ),
            "",
            "## Fixed 2% Positive-Edge PnL",
            "",
            *bet_table(bet_rows),
            "",
            "## Rolling Prior-Fold Selection Diagnostics",
            "",
            "These selectors are diagnostic only. They choose among the inspected",
            "feature variants using prior folds, then score the next fold. The",
            "market-null p-values above do not adjust for this rolling selection.",
            "",
            *rolling_probability_table(result["rolling_probability_rows"]),
            "",
            "Probability selection path:",
            "",
            *selection_path_table(
                result["rolling_probability_selection_path"],
                "prior_delta_log_loss",
                "eval_delta_log_loss",
                "eval_rows",
            ),
            "",
            "Betting selection path:",
            "",
            *selection_path_table(
                result["rolling_profit_selection_path"],
                "prior_profit",
                "eval_profit",
                "eval_bets",
            ),
            "",
            "Rolling selected betting result:",
            "",
            *bet_table(result["rolling_bet_rows"]),
            "",
            "## Variants",
            "",
            "| Variant | Feature Columns | Note |",
            "| --- | --- | --- |",
        ]
    )
    for variant in result["variants"]:
        lines.append(
            "| `{name}` | `{features}` | {note} |".format(
                name=variant["name"],
                features="`, `".join(variant["feature_columns"]),
                note=variant["note"],
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Best probability variant: `{best_probability['variant']}` with Delta LL `{fmt_float(best_probability['delta_log_loss'])}`.",
            f"- Best uncapped PnL variant: `{best_bet['variant']}` with `{fmt_units(best_bet['profit'])}` at `{fmt_pct(best_bet['roi'])}` ROI.",
        ]
    )
    if best_probability["variant"] in {"current_mixed_core", "current_sigpct_head"}:
        lines.append("- The current count-differential variants remain best or effectively tied on probability diagnostics.")
    else:
        lines.append("- A pace-adjusted variant beat the current count-differential variants on raw probability diagnostics, but this is a discovery result.")
    lines.append(
        "- Do not change the frozen paper policy from this audit alone; these variants were designed after seeing the striking-core evidence and need selection-adjusted validation or future paper evidence."
    )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
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
    aligned, metadata = aligned_market_feature_frame(align_args)
    aligned, pace_metadata = add_pace_features(aligned, pace_features)
    variants = build_variants()
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
    predictions, coefficients, fold_rows = run_observed_predictions(
        aligned,
        folds,
        variants,
        args.c,
    )
    summary = aggregate_predictions(predictions, variants, args.bootstrap_iterations, rng)
    market_null = market_null_simulation(
        aligned,
        folds,
        variants,
        summary,
        args.c,
        args.market_null_iterations,
        rng,
    )
    probability_rows = [summarize_probability(predictions, variant.name) for variant in variants]
    candidate_names = [variant.name for variant in variants if variant.name != "market_recalibrated"]
    rolling_probability_predictions, rolling_probability_path = rolling_prior_probability_selection(
        predictions,
        candidate_names,
    )
    rolling_probability_rows = [
        summarize_prediction_frame(
            rolling_probability_predictions,
            "rolling_prior_probability_delta",
            args.bootstrap_iterations,
            rng,
        )
    ]

    bet_frames = []
    bet_rows = []
    for variant in variants:
        bets, row = summarize_bets_for_variant(
            predictions,
            aligned,
            variant.name,
            args.bootstrap_iterations,
            args.bet_null_iterations,
            rng,
        )
        if not bets.empty:
            bet_frames.append(bets)
        bet_rows.append(row)

    all_bets = pd.concat(bet_frames, ignore_index=True) if bet_frames else pd.DataFrame()
    rolling_profit_bets, rolling_profit_path = rolling_prior_profit_selection(
        all_bets,
        candidate_names,
    )
    rolling_bet_rows = [
        summarize_bet_frame(
            rolling_profit_bets,
            "rolling_prior_profit",
            args.bootstrap_iterations,
            args.bet_null_iterations,
            rng,
        )
    ]

    return {
        "parameters": {
            "source_fights": args.source_fights,
            "features": args.features,
            "odds": args.odds,
            "fight_details_source": args.fight_details_source,
            "first_holdout_start": args.first_holdout_start,
            "last_holdout_end": args.last_holdout_end,
            "dev_days": args.dev_days,
            "holdout_days": args.holdout_days,
            "step_days": args.step_days,
            "min_dev_fights": args.min_dev_fights,
            "min_holdout_fights": args.min_holdout_fights,
            "c": args.c,
            "edge_threshold": EDGE_THRESHOLD,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "bet_null_iterations": args.bet_null_iterations,
            "seed": args.seed,
        },
        "metadata": {**metadata, **pace_metadata},
        "pace_reconstruction": pace_reconstruction,
        "variants": [
            {
                "name": variant.name,
                "feature_columns": list(variant.feature_columns),
                "note": variant.note,
            }
            for variant in variants
        ],
        "folds": fold_rows,
        "coefficients": coefficients,
        "summary": summary,
        "market_null": market_null,
        "probability_rows": probability_rows,
        "bet_rows": bet_rows,
        "rolling_probability_rows": rolling_probability_rows,
        "rolling_probability_selection_path": rolling_probability_path,
        "rolling_bet_rows": rolling_bet_rows,
        "rolling_profit_selection_path": rolling_profit_path,
        "_predictions": predictions,
        "_bets": all_bets,
        "_pace_features": pace_features,
    }


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run_audit(args)

    predictions = result.pop("_predictions")
    bets = result.pop("_bets")
    pace_features = result.pop("_pace_features")

    predictions_path = output_dir / "striking_feature_engineering_predictions.csv"
    bets_path = output_dir / "striking_feature_engineering_edge02_bets.csv"
    pace_path = output_dir / "source_derived_pace_features.csv"
    json_path = output_dir / "striking_feature_engineering_audit.json"
    md_path = output_dir / "striking_feature_engineering_audit.md"

    predictions.to_csv(predictions_path, index=False)
    bets.to_csv(bets_path, index=False)
    pace_features.to_csv(pace_path, index=False)
    result["outputs"] = {
        "predictions_csv": str(predictions_path),
        "bets_csv": str(bets_path),
        "pace_features_csv": str(pace_path),
        "summary_json": str(json_path),
        "report_md": str(md_path),
    }
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
