#!/usr/bin/env python3
"""Walk-forward audit for fight features after controlling for the market.

This script asks a narrower question than the standalone no-leakage model:
given de-vigged market probability before the fight, do pre-fight model
features add out-of-sample log-loss signal?
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_residual_meta_audit import (  # noqa: E402
    EPS,
    FoldSpec,
    event_bootstrap_delta,
    iter_folds,
    logit,
    per_row_loss,
    score_probabilities,
)
from testing.no_leakage_backtest import (  # noqa: E402
    DEFAULT_EXCLUDED_TITLE_PATTERNS,
    TARGET_COLUMN,
    build_excluded_fight_index,
    build_feature_index,
    fight_pair_key,
    load_feature_data,
    load_known_women_fighter_keys,
    load_odds_data,
    normalize_name,
    odds_to_prob,
    parse_odds,
    swap_column_name,
    swap_feature_frame,
)
from testing.statistical_edge_audit import binary_log_loss, brier_score  # noqa: E402


DEFAULT_TOP_IMPORTANCE_PATH = "test_results/regularized_lgbm_feature_importance.csv"

ELO_EXPERIENCE_FEATURES = (
    "oppelo oppdiff",
    "elo oppdiff",
    "wins oppdiff",
    "totalfights oppdiff",
    "avg age oppdiff",
    "winstreak oppdiff",
    "losestreak oppdiff",
    "titlewins oppdiff",
)

AGE_RECENCY_FEATURES = (
    "age oppdiff",
    "last_fight oppdiff",
)

COMBAT_STAT_FEATURES = (
    "Clinch oppdiff",
    "KD differential oppdiff",
    "Sig. str.% differential oppdiff",
    "Body% differential oppdiff",
    "Td% defense oppdiff",
    "Distance% defense oppdiff",
    "Sub. att oppdiff",
    "Td differential oppdiff",
    "Head differential oppdiff",
    "Ctrl oppdiff",
)


@dataclass(frozen=True)
class VariantSpec:
    name: str
    feature_columns: tuple[str, ...]
    note: str


def parse_args():
    parser = argparse.ArgumentParser(description="Audit fight features after market control")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--odds", default="data/fight_results_with_odds.csv")
    parser.add_argument("--fight-details-source", default="data/fight_details_date.csv")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--first-holdout-start", default="2024-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=200)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--c", type=float, default=0.1)
    parser.add_argument("--top-importance-path", default=DEFAULT_TOP_IMPORTANCE_PATH)
    parser.add_argument("--top-importance-count", type=int, default=20)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--include-womens-fights", action="store_true")
    parser.add_argument("--output-dir", default="test_results/market_aware_feature_audit")
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def expand_side_pairs(columns: list[str], available_columns: set[str]) -> list[str]:
    selected = []
    seen = set()
    for column in columns:
        if column not in available_columns or column in seen:
            continue
        selected.append(column)
        seen.add(column)

        if "oppdiff" in column:
            continue
        counterpart = swap_column_name(column)
        if counterpart != column and counterpart in available_columns and counterpart not in seen:
            selected.append(counterpart)
            seen.add(counterpart)
    return selected


def load_top_importance_features(path: str, count: int, available_columns: set[str]) -> list[str]:
    importance_path = Path(path)
    if not importance_path.exists() or count <= 0:
        return []

    df = pd.read_csv(importance_path)
    if "feature" not in df.columns:
        return []
    raw = [str(value) for value in df["feature"].head(count).tolist()]
    return expand_side_pairs(raw, available_columns)


def build_variants(df: pd.DataFrame, args) -> list[VariantSpec]:
    available = set(df.columns)

    def with_market(columns: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        expanded = expand_side_pairs(list(columns), available)
        return tuple(["market_logit", *expanded])

    top_features = load_top_importance_features(
        args.top_importance_path,
        args.top_importance_count,
        available,
    )

    variants = [
        VariantSpec("market_recalibrated", ("market_logit",), "logistic recalibration of market logit only"),
        VariantSpec(
            "market_plus_elo_experience",
            with_market(ELO_EXPERIENCE_FEATURES),
            "market plus Elo, experience, streak, and title-count deltas",
        ),
        VariantSpec(
            "market_plus_age_recency",
            with_market(AGE_RECENCY_FEATURES),
            "market plus age and layoff deltas",
        ),
        VariantSpec(
            "market_plus_combat_stats",
            with_market(COMBAT_STAT_FEATURES),
            "market plus selected historical striking/grappling stat deltas",
        ),
    ]
    if top_features:
        variants.append(
            VariantSpec(
                "market_plus_top_importance",
                tuple(["market_logit", *top_features]),
                f"market plus top {len(top_features)} retrained-LGBM importance features",
            )
        )
    return variants


def aligned_market_feature_frame(args) -> tuple[pd.DataFrame, dict]:
    women_fighter_keys = load_known_women_fighter_keys(args.fight_details_source)
    features_df = load_feature_data(args.features, args.min_training_date)

    excluded_title_patterns = [] if args.include_womens_fights else list(DEFAULT_EXCLUDED_TITLE_PATTERNS)
    excluded_fight_keys, excluded_dates_by_pair, excluded_fighter_keys = build_excluded_fight_index(
        args.fight_details_source,
        excluded_title_patterns,
    )

    odds_df, odds_date_repairs = load_odds_data(
        args.odds,
        args.min_training_date,
        args.last_holdout_end,
        features_df=features_df,
        return_repairs=True,
        excluded_fight_keys=excluded_fight_keys,
        excluded_dates_by_pair=excluded_dates_by_pair,
        excluded_fighter_keys=excluded_fighter_keys,
    )

    feature_index, duplicate_feature_keys, duplicate_feature_count = build_feature_index(
        features_df,
        args.min_training_date,
        args.last_holdout_end,
    )
    rows = []
    skipped_missing = 0
    skipped_duplicate = 0
    skipped_bad_odds = 0
    skipped_orientation = 0

    for _, odds_row in odds_df.iterrows():
        event_date = odds_row["event_date"].date()
        key = (
            event_date,
            fight_pair_key(odds_row["fighter1_name"], odds_row["fighter2_name"]),
        )
        if key in duplicate_feature_keys:
            skipped_duplicate += 1
            continue
        feature_row_index = feature_index.get(key)
        if feature_row_index is None:
            skipped_missing += 1
            continue

        feature_row = features_df.loc[feature_row_index]
        odds1 = parse_odds(odds_row["fighter1_odds"])
        odds2 = parse_odds(odds_row["fighter2_odds"])
        if odds1 is None or odds2 is None:
            skipped_bad_odds += 1
            continue

        raw1 = odds_to_prob(odds1)
        raw2 = odds_to_prob(odds2)
        vig_sum = raw1 + raw2
        if not np.isfinite(vig_sum) or vig_sum <= 0:
            skipped_bad_odds += 1
            continue
        p1 = raw1 / vig_sum
        p2 = raw2 / vig_sum

        red_key = normalize_name(feature_row["Red Fighter"])
        fighter1_key = normalize_name(odds_row["fighter1_name"])
        fighter2_key = normalize_name(odds_row["fighter2_name"])
        if red_key == fighter1_key:
            red_market = p1
        elif red_key == fighter2_key:
            red_market = p2
        else:
            skipped_orientation += 1
            continue

        row = feature_row.to_dict()
        row.update(
            {
                "event_date": pd.Timestamp(event_date),
                "fight_key": "|".join(
                    [
                        event_date.isoformat(),
                        *sorted([fighter1_key, fighter2_key]),
                    ]
                ),
                "title": feature_row["Title"],
                "red_fighter": feature_row["Red Fighter"],
                "blue_fighter": feature_row["Blue Fighter"],
                "winner_name": feature_row["Red Fighter"]
                if feature_row[TARGET_COLUMN] == "win"
                else feature_row["Blue Fighter"],
                "red_won": feature_row[TARGET_COLUMN] == "win",
                "red_market_probability": float(red_market),
                "market_logit": float(logit(red_market)),
                "odds_fighter1_name": odds_row["fighter1_name"],
                "odds_fighter2_name": odds_row["fighter2_name"],
                "fighter1_odds": odds1,
                "fighter2_odds": odds2,
            }
        )
        rows.append(row)

    aligned = pd.DataFrame(rows)
    if aligned.empty:
        raise SystemExit("No aligned feature/odds rows were available")

    aligned = aligned.sort_values(["event_date", "red_fighter", "blue_fighter"]).reset_index(drop=True)

    metadata = {
        "features_path": args.features,
        "odds_path": args.odds,
        "fight_details_source": args.fight_details_source,
        "excluded_title_patterns": excluded_title_patterns,
        "feature_rows": int(len(features_df)),
        "odds_rows": int(len(odds_df)),
        "aligned_rows": int(len(aligned)),
        "duplicate_feature_keys": int(duplicate_feature_count),
        "odds_rows_date_repaired": int(len(odds_date_repairs)),
        "odds_rows_excluded_universe": int(odds_df.attrs.get("excluded_universe_rows", 0)),
        "odds_rows_non_binary_excluded": int(odds_df.attrs.get("non_binary_rows", 0)),
        "skipped_missing_features": int(skipped_missing),
        "skipped_duplicate_features": int(skipped_duplicate),
        "skipped_bad_odds": int(skipped_bad_odds),
        "skipped_orientation_mismatch": int(skipped_orientation),
    }
    return aligned, metadata


def numeric_variant_frame(df: pd.DataFrame, columns: tuple[str, ...], swapped: bool) -> pd.DataFrame:
    data = {}
    fight_columns = [column for column in columns if column != "market_logit"]
    if fight_columns:
        if swapped:
            swapped_frame = swap_feature_frame(df, fight_columns)
            for column in fight_columns:
                data[column] = pd.to_numeric(swapped_frame[column], errors="coerce")
        else:
            for column in fight_columns:
                data[column] = pd.to_numeric(df[column], errors="coerce") if column in df.columns else np.nan

    if "market_logit" in columns:
        market = pd.to_numeric(df["market_logit"], errors="coerce")
        data["market_logit"] = -market if swapped else market

    return pd.DataFrame(data, index=df.index)[list(columns)]


def fit_predict_variant(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    y_train: np.ndarray,
    columns: tuple[str, ...],
    c_value: float,
) -> tuple[np.ndarray, dict]:
    y_train = np.asarray(y_train, dtype=int)
    train_direct = numeric_variant_frame(train_df, columns, swapped=False)
    train_swapped = numeric_variant_frame(train_df, columns, swapped=True)
    x_train = pd.concat([train_direct, train_swapped], ignore_index=True)
    y_extended = np.concatenate([y_train, 1 - y_train])

    eval_direct = numeric_variant_frame(eval_df, columns, swapped=False)
    eval_swapped = numeric_variant_frame(eval_df, columns, swapped=True)

    if len(np.unique(y_extended)) < 2:
        probability = float(np.clip(np.mean(y_extended), EPS, 1.0 - EPS))
        return np.full(len(eval_df), probability), {
            "constant_fallback": True,
            "intercept": float(logit(probability)),
            "coefficients": None,
        }

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=c_value, penalty="l2", solver="liblinear", max_iter=300),
    )
    model.fit(x_train, y_extended)
    direct = np.clip(model.predict_proba(eval_direct)[:, 1], EPS, 1.0 - EPS)
    swapped = np.clip(model.predict_proba(eval_swapped)[:, 1], EPS, 1.0 - EPS)
    probability = np.clip((direct + (1.0 - swapped)) / 2.0, EPS, 1.0 - EPS)

    logistic = model.named_steps["logisticregression"]
    return probability, {
        "constant_fallback": False,
        "intercept": float(logistic.intercept_[0]),
        "coefficients": [float(value) for value in logistic.coef_[0]],
    }


def run_observed_predictions(
    df: pd.DataFrame,
    folds: list[FoldSpec],
    variants: list[VariantSpec],
    c_value: float,
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    y = df["red_won"].astype(int).to_numpy()
    prediction_rows = []
    coefficient_rows = []
    fold_rows = []

    for fold in folds:
        holdout_df = df.iloc[fold.holdout_indices]
        fold_row = {
            "fold": fold.fold_index,
            "dev_start": fold.dev_start.date().isoformat(),
            "dev_end": fold.dev_end.date().isoformat(),
            "holdout_start": fold.holdout_start.date().isoformat(),
            "holdout_end": fold.holdout_end.date().isoformat(),
            "dev_fights": int(len(fold.dev_indices)),
            "holdout_fights": int(len(fold.holdout_indices)),
            "market_log_loss": binary_log_loss(
                y[fold.holdout_indices],
                holdout_df["red_market_probability"].astype(float).to_numpy(),
            ),
        }

        for variant in variants:
            probabilities, fit_info = fit_predict_variant(
                df.iloc[fold.dev_indices],
                holdout_df,
                y[fold.dev_indices],
                variant.feature_columns,
                c_value,
            )
            holdout_y = y[fold.holdout_indices]
            variant_loss = binary_log_loss(holdout_y, probabilities)
            fold_row[f"{variant.name}_log_loss"] = variant_loss
            fold_row[f"{variant.name}_delta_log_loss"] = fold_row["market_log_loss"] - variant_loss
            coefficient_rows.append(
                {
                    "fold": fold.fold_index,
                    "variant": variant.name,
                    "intercept": fit_info["intercept"],
                    "constant_fallback": fit_info["constant_fallback"],
                    "feature_columns": list(variant.feature_columns),
                    "coefficients": fit_info["coefficients"],
                }
            )

            for row_index, probability in zip(fold.holdout_indices, probabilities):
                source = df.iloc[row_index]
                prediction_rows.append(
                    {
                        "fold": fold.fold_index,
                        "variant": variant.name,
                        "event_date": source["event_date"].date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "winner_name": source["winner_name"],
                        "red_won": bool(y[row_index]),
                        "market_probability": float(source["red_market_probability"]),
                        "candidate_probability": float(probability),
                    }
                )
        fold_rows.append(fold_row)

    return pd.DataFrame(prediction_rows), coefficient_rows, fold_rows


def summarize_coefficients(coefficient_rows: list[dict]) -> dict:
    values = {}
    for row in coefficient_rows:
        variant = row["variant"]
        values.setdefault(variant, {}).setdefault("intercept", []).append(row["intercept"])
        coefficients = row.get("coefficients")
        if coefficients is None:
            continue
        for feature, coefficient in zip(row["feature_columns"], coefficients):
            values.setdefault(variant, {}).setdefault(feature, []).append(coefficient)

    summary = {}
    for variant, feature_values in values.items():
        summary[variant] = {}
        for feature, entries in feature_values.items():
            array = np.asarray(entries, dtype=float)
            summary[variant][feature] = {
                "folds": int(len(array)),
                "mean": float(np.mean(array)),
                "std": float(np.std(array)),
                "min": float(np.min(array)),
                "max": float(np.max(array)),
            }
    return summary


def aggregate_predictions(
    predictions: pd.DataFrame,
    variants: list[VariantSpec],
    bootstrap_iterations: int,
    rng,
) -> dict:
    result = {}
    for variant in variants:
        subset = predictions[predictions["variant"] == variant.name].copy()
        y = subset["red_won"].astype(float).to_numpy()
        market = subset["market_probability"].astype(float).to_numpy()
        candidate = subset["candidate_probability"].astype(float).to_numpy()
        market_score = score_probabilities(y, market)
        candidate_score = score_probabilities(y, candidate)
        market_loss = per_row_loss(y, market)
        candidate_loss = per_row_loss(y, candidate)
        fold_deltas = []
        for _, fold_subset in subset.groupby("fold", sort=True):
            fold_y = fold_subset["red_won"].astype(float).to_numpy()
            fold_delta = binary_log_loss(
                fold_y,
                fold_subset["market_probability"].astype(float).to_numpy(),
            ) - binary_log_loss(
                fold_y,
                fold_subset["candidate_probability"].astype(float).to_numpy(),
            )
            fold_deltas.append(float(fold_delta))

        bootstrap_input = subset.rename(columns={"candidate_probability": "meta_probability"})
        result[variant.name] = {
            "note": variant.note,
            "feature_columns": list(variant.feature_columns),
            "market": market_score,
            "candidate": candidate_score,
            "market_minus_candidate_log_loss": float(market_score["log_loss"] - candidate_score["log_loss"]),
            "market_minus_candidate_brier": float(market_score["brier"] - candidate_score["brier"]),
            "mean_row_loss_delta": float(np.mean(market_loss - candidate_loss)),
            "positive_folds": int(np.sum(np.asarray(fold_deltas) > 0.0)),
            "folds": int(len(fold_deltas)),
            "fold_log_loss_deltas": fold_deltas,
            "event_bootstrap": event_bootstrap_delta(bootstrap_input, bootstrap_iterations, rng),
        }
    return result


def run_pipeline_for_labels(
    df: pd.DataFrame,
    folds: list[FoldSpec],
    variants: list[VariantSpec],
    labels: np.ndarray,
    c_value: float,
) -> dict[str, float]:
    parts = {variant.name: {"y": [], "market": [], "candidate": []} for variant in variants}
    for fold in folds:
        train_df = df.iloc[fold.dev_indices]
        eval_df = df.iloc[fold.holdout_indices]
        for variant in variants:
            probability, _ = fit_predict_variant(
                train_df,
                eval_df,
                labels[fold.dev_indices],
                variant.feature_columns,
                c_value,
            )
            bucket = parts[variant.name]
            bucket["y"].append(labels[fold.holdout_indices])
            bucket["market"].append(eval_df["red_market_probability"].astype(float).to_numpy())
            bucket["candidate"].append(probability)

    deltas = {}
    for variant in variants:
        bucket = parts[variant.name]
        y = np.concatenate(bucket["y"])
        market = np.concatenate(bucket["market"])
        candidate = np.concatenate(bucket["candidate"])
        deltas[variant.name] = binary_log_loss(y, market) - binary_log_loss(y, candidate)
    return deltas


def market_null_simulation(
    df: pd.DataFrame,
    folds: list[FoldSpec],
    variants: list[VariantSpec],
    observed: dict,
    c_value: float,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    values = {variant.name: np.empty(iterations, dtype=float) for variant in variants}
    for iteration in range(iterations):
        labels = (rng.random(len(df)) < market).astype(int)
        deltas = run_pipeline_for_labels(df, folds, variants, labels, c_value)
        for variant in variants:
            values[variant.name][iteration] = deltas[variant.name]

    result = {}
    for variant in variants:
        observed_delta = observed[variant.name]["market_minus_candidate_log_loss"]
        null_values = values[variant.name]
        result[variant.name] = {
            "iterations": int(iterations),
            "observed_market_minus_candidate_log_loss": float(observed_delta),
            "null_mean_delta": float(np.mean(null_values)),
            "null_delta_ci_95": [float(value) for value in np.percentile(null_values, [2.5, 97.5])],
            "p_value_observed_or_better": float(
                (np.sum(null_values >= observed_delta) + 1) / (iterations + 1)
            ),
            "prob_null_delta_positive": float(np.mean(null_values > 0.0)),
        }
    return result


def markdown_report(result: dict) -> str:
    null = result.get("market_null") or {}
    lines = [
        "# Market-Aware Feature Audit",
        "",
        "This audit asks whether pre-fight feature groups add log-loss signal after",
        "controlling for de-vigged market probability. Positive `Delta LL` means",
        "the candidate probability beat the market probability.",
        "",
        "## Protocol",
        "",
        f"- feature table: `{result['features_path']}`",
        f"- odds table: `{result['odds_path']}`",
        f"- aligned feature/odds rows: `{result['aligned_rows']}`",
        f"- evaluated holdout fights: `{result['holdout_fights']}`",
        f"- folds evaluated: `{result['folds_evaluated']}`",
        f"- first holdout start: `{result['first_holdout_start']}`",
        f"- last holdout end: `{result['last_holdout_end']}`",
        f"- development window: `{result['dev_days']}` days",
        f"- holdout window: `{result['holdout_days']}` days",
        f"- logistic L2 C: `{result['c']}`",
        f"- bootstrap iterations: `{result['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        "",
        "The logistic candidates are trained only on prior development folds. Training",
        "rows are red/blue mirrored so the model sees each fight from both sides;",
        "holdout probabilities average direct and mirrored orientations.",
        "",
        "## Results",
        "",
        "| Variant | Features | Fights | Market LL | Candidate LL | Delta LL | Accuracy | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in sorted(
        result["summary"].items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
        reverse=True,
    ):
        bootstrap = summary.get("event_bootstrap") or {}
        null_summary = null.get(name) or {}
        lines.append(
            "| {name} | {features} | {fights} | {market_ll} | {candidate_ll} | {delta} | {acc} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                features=len(summary["feature_columns"]),
                fights=summary["candidate"]["fights"],
                market_ll=fmt_float(summary["market"]["log_loss"]),
                candidate_ll=fmt_float(summary["candidate"]["log_loss"]),
                delta=fmt_float(summary["market_minus_candidate_log_loss"]),
                acc=fmt_pct(summary["candidate"]["accuracy"]),
                pos=summary["positive_folds"],
                folds=summary["folds"],
                boot=fmt_p(bootstrap.get("prob_delta_le_zero")),
                null_p=fmt_p(null_summary.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Variants",
            "",
            "| Variant | Note | Feature Columns |",
            "| --- | --- | --- |",
        ]
    )
    for variant in result["variants"]:
        lines.append(
            "| {name} | {note} | `{features}` |".format(
                name=variant["name"],
                note=variant["note"],
                features="`, `".join(variant["feature_columns"]),
            )
        )

    lines.extend(
        [
            "",
            "## Fold Deltas",
            "",
            "| Fold | Holdout | Market LL | "
            + " | ".join(variant["name"] for variant in result["variants"])
            + " |",
            "| ---: | --- | ---: | "
            + " | ".join("---:" for _ in result["variants"])
            + " |",
        ]
    )
    for fold in result["folds"]:
        cells = [
            str(fold["fold"]),
            f"{fold['holdout_start']} to {fold['holdout_end']}",
            fmt_float(fold["market_log_loss"]),
        ]
        for variant in result["variants"]:
            cells.append(fmt_float(fold.get(f"{variant['name']}_delta_log_loss")))
        lines.append("| " + " | ".join(cells) + " |")

    best_name, best_summary = max(
        result["summary"].items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
    )
    best_null = (result.get("market_null") or {}).get(best_name, {})
    best_bootstrap = best_summary.get("event_bootstrap") or {}

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"Best raw candidate: `{best_name}` with Delta LL `{fmt_float(best_summary['market_minus_candidate_log_loss'])}`.",
            f"Its event-bootstrap `P(delta <= 0)` was `{fmt_p(best_bootstrap.get('prob_delta_le_zero'))}` and its market-null p-value was `{fmt_p(best_null.get('p_value_observed_or_better'))}`.",
        ]
    )
    if best_summary["market_minus_candidate_log_loss"] <= 0:
        lines.append("No tested feature group beat the market on aggregate log loss.")
    elif (best_null.get("p_value_observed_or_better") or 1.0) > 0.05:
        lines.append(
            "The result is useful diagnostics, but not strong enough to promote a new market-aware feature model."
        )
    else:
        lines.append(
            "This clears the unadjusted market-null check, but still needs correction for tested variants and fresh paper tracking before it can support staking."
        )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- `{result['outputs']['predictions_csv']}`",
            f"- `{result['outputs']['summary_json']}`",
            f"- `{result['outputs']['report_md']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, metadata = aligned_market_feature_frame(args)
    variants = build_variants(df, args)
    folds = iter_folds(
        df,
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

    predictions, coefficient_rows, fold_rows = run_observed_predictions(
        df,
        folds,
        variants,
        args.c,
    )
    summary = aggregate_predictions(predictions, variants, args.bootstrap_iterations, rng)
    market_null = market_null_simulation(
        df,
        folds,
        variants,
        summary,
        args.c,
        args.market_null_iterations,
        rng,
    )
    coefficient_summary = summarize_coefficients(coefficient_rows)

    predictions_path = output_dir / "market_aware_feature_predictions.csv"
    summary_path = output_dir / "market_aware_feature_audit.json"
    report_path = output_dir / "market_aware_feature_audit.md"
    predictions.to_csv(predictions_path, index=False)

    result = {
        **metadata,
        "first_holdout_start": args.first_holdout_start,
        "last_holdout_end": args.last_holdout_end,
        "dev_days": args.dev_days,
        "holdout_days": args.holdout_days,
        "step_days": args.step_days,
        "min_dev_fights": args.min_dev_fights,
        "min_holdout_fights": args.min_holdout_fights,
        "c": args.c,
        "seed": args.seed,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "folds_evaluated": len(folds),
        "holdout_fights": int(
            sum(len(fold.holdout_indices) for fold in folds)
        ),
        "variants": [
            {
                "name": variant.name,
                "note": variant.note,
                "feature_columns": list(variant.feature_columns),
            }
            for variant in variants
        ],
        "folds": fold_rows,
        "summary": summary,
        "market_null": market_null,
        "coefficients": coefficient_summary,
        "outputs": {
            "predictions_csv": str(predictions_path),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
        },
    }

    with open(summary_path, "w") as file:
        json.dump(result, file, indent=2)
    report_path.write_text(markdown_report(result))

    best_name, best_summary = max(
        summary.items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
    )
    best_null = (market_null or {}).get(best_name, {})
    print(
        f"Best variant {best_name}: delta LL "
        f"{best_summary['market_minus_candidate_log_loss']:.4f}, "
        f"market-null p {fmt_p(best_null.get('p_value_observed_or_better'))}"
    )
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
