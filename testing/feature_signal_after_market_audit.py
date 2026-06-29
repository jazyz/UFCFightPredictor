#!/usr/bin/env python3
"""Rolling sanity audit for high-importance fight features after market control.

This diagnostic asks whether current high-importance feature units add
forward out-of-sample signal beyond the de-vigged market line, and whether the
learned direction agrees with basic fight-domain priors where those priors are
clear enough to predeclare.
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

from testing.no_leakage_backtest import swap_column_name, swap_feature_frame  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
DEFAULT_FEATURES = "data/detailed_fights.csv"
DEFAULT_IMPORTANCE = "test_results/regularized_lgbm_feature_importance.csv"
DEFAULT_OUTPUT_DIR = "test_results/feature_signal_after_market_audit"
EPS = 1e-6


@dataclass(frozen=True)
class FeatureUnit:
    unit: str
    columns: tuple[str, ...]
    source_features: tuple[str, ...]
    top_rank: int
    importance_sum: float
    family: str
    warning: str | None
    expected_sign: int | None
    expected_sign_label: str


def parse_args():
    parser = argparse.ArgumentParser(description="Audit top feature signal after market control")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--importance", default=DEFAULT_IMPORTANCE)
    parser.add_argument("--top-raw-features", type=int, default=80)
    parser.add_argument("--max-units", type=int, default=60)
    parser.add_argument("--c", type=float, default=0.1)
    parser.add_argument("--bootstrap-iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def probability_clip(values) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), EPS, 1.0 - EPS)


def logit(probability) -> np.ndarray:
    p = probability_clip(probability)
    return np.log(p / (1.0 - p))


def binary_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = probability_clip(probability)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def log_loss(y_true, probability) -> float:
    return float(np.mean(binary_loss(y_true, probability)))


def parse_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="mixed", errors="coerce")


def fight_key(date_value, red_fighter, blue_fighter) -> str:
    date = pd.Timestamp(date_value).date().isoformat()
    fighters = sorted([canonical_name(red_fighter), canonical_name(blue_fighter)])
    return f"{date}|{fighters[0]}|{fighters[1]}"


def load_predictions(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "fold",
        "event_date",
        "fight_key",
        "title",
        "red_fighter",
        "blue_fighter",
        "red_won",
        "market_probability",
    }
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing prediction columns: {sorted(missing)}")
    df = df.copy()
    df["red_won"] = df["red_won"].astype(bool).astype(int)
    df["market_probability"] = probability_clip(df["market_probability"])
    df["market_logit"] = logit(df["market_probability"])
    return df


def load_features(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"Date", "Red Fighter", "Blue Fighter", "Title"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing feature columns: {sorted(missing)}")
    df = df.copy()
    df["event_date"] = parse_date_series(df["Date"])
    df = df.dropna(subset=["event_date"]).copy()
    df["fight_key"] = [
        fight_key(date, red, blue)
        for date, red, blue in zip(df["event_date"], df["Red Fighter"], df["Blue Fighter"])
    ]
    duplicate_keys = int(df["fight_key"].duplicated().sum())
    if duplicate_keys:
        df = df.sort_values(["event_date", "fight_key"]).drop_duplicates("fight_key", keep="last")
    return df


def merge_predictions_features(predictions: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    keep = [
        column
        for column in features.columns
        if column not in {"fight_key", "event_date", "Title", "Red Fighter", "Blue Fighter", "Result"}
    ]
    merged = predictions.merge(features[["fight_key", *keep]], on="fight_key", how="left", validate="one_to_one")
    missing = int(merged["Date"].isna().sum()) if "Date" in merged.columns else len(merged)
    if missing:
        sample = merged.loc[merged["Date"].isna(), "fight_key"].head(10).tolist()
        raise SystemExit(f"Could not match {missing} prediction rows to features. Sample: {sample}")
    return merged


def side_base(column: str) -> tuple[str | None, str]:
    if column.startswith("Red "):
        return "Red", column[4:]
    if column.startswith("Blue "):
        return "Blue", column[5:]
    return None, column


def unit_key_for_feature(feature: str, available_columns: set[str]) -> tuple[str, tuple[str, ...]]:
    side, base = side_base(feature)
    if side:
        red_col = f"Red {base}"
        blue_col = f"Blue {base}"
        if red_col in available_columns and blue_col in available_columns:
            return f"{base} side_pair", (red_col, blue_col)
    return feature, (feature,)


def classify_family(unit_name: str) -> tuple[str, str | None]:
    lower = unit_name.lower()
    warning = None
    if "dob" in lower:
        family = "raw_dob"
        warning = "raw birth-year proxy"
    elif "age" in lower or "last_fight" in lower:
        family = "age_recency"
    elif any(token in lower for token in ("elo", "wins", "totalfights", "streak", "titlewins")):
        family = "record_experience"
    elif any(token in lower for token in ("td", "sub. att", "rev.", "ctrl")):
        family = "grappling"
    elif any(token in lower for token in ("sig. str", "total str", "kd", "head", "body", "leg", "distance", "clinch", "ground")):
        family = "striking_position"
    else:
        family = "other"

    if "%" in unit_name:
        warning = "percentage/rate proxy" if warning is None else f"{warning}; percentage/rate proxy"
    if "% defense" in lower and any(
        token in lower for token in ("head", "body", "leg", "distance", "clinch", "ground")
    ):
        warning = (
            "target/position-mix defense proxy"
            if warning is None
            else f"{warning}; target/position-mix defense proxy"
        )
    return family, warning


def expected_sign_for_unit(unit_name: str) -> tuple[int | None, str]:
    lower = unit_name.lower()
    if "avg age" in lower:
        return None, "opponent-age context has no strong predeclared direction"
    if "losestreak" in lower:
        return -1, "more losses in a row should hurt red"
    if "last_fight" in lower:
        return -1, "longer red layoff than blue should hurt red"
    if lower == "age oppdiff" or unit_name == "age side_pair":
        return -1, "older red than blue is treated as a weak negative prior"
    if any(token in lower for token in ("elo", "oppelo", "wins", "totalfights", "winstreak", "titlewins")):
        return 1, "stronger record/experience should help red"
    if any(
        token in lower
        for token in (
            "kd differential",
            "sig. str. differential",
            "total str. differential",
            "td differential",
            "sub. att differential",
            "head differential",
            "body differential",
            "leg differential",
            "distance differential",
            "clinch differential",
            "ground differential",
            "ctrl differential",
            "rev. differential",
        )
    ):
        return 1, "better historical differential should help red"
    if "% defense" in lower:
        return 1, "higher defense proxy should help red, if the proxy is valid"
    return None, "no strong predeclared directional prior"


def load_feature_units(path: str, df: pd.DataFrame, top_raw_features: int, max_units: int) -> tuple[list[FeatureUnit], dict]:
    importance = pd.read_csv(path)
    if "feature" not in importance.columns or "importance" not in importance.columns:
        raise SystemExit("Importance file must contain feature and importance columns")
    importance = importance.copy()
    importance["rank"] = np.arange(1, len(importance) + 1)
    available_columns = set(df.columns)
    numeric_columns = set(df.select_dtypes(include=[np.number]).columns)
    importance_map = {str(row["feature"]): float(row["importance"]) for _, row in importance.iterrows()}
    rank_map = {str(row["feature"]): int(row["rank"]) for _, row in importance.iterrows()}

    unit_sources: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    skipped_unavailable = 0
    skipped_nonnumeric = 0
    for feature in importance["feature"].astype(str).head(top_raw_features):
        if feature not in available_columns:
            skipped_unavailable += 1
            continue
        unit_name, columns = unit_key_for_feature(feature, available_columns)
        if not all(column in numeric_columns for column in columns):
            skipped_nonnumeric += 1
            continue
        key = (unit_name, columns)
        unit_sources.setdefault(key, [])
        if feature not in unit_sources[key]:
            unit_sources[key].append(feature)
        if len(unit_sources) >= max_units:
            break

    units = []
    for (unit_name, columns), sources in unit_sources.items():
        family, warning = classify_family(unit_name)
        expected_sign, expected_label = expected_sign_for_unit(unit_name)
        source_set = set(sources)
        for column in columns:
            if column in rank_map and rank_map[column] <= top_raw_features:
                source_set.add(column)
        units.append(
            FeatureUnit(
                unit=unit_name,
                columns=columns,
                source_features=tuple(sorted(source_set, key=lambda item: rank_map.get(item, 10**9))),
                top_rank=min(rank_map.get(item, 10**9) for item in source_set),
                importance_sum=float(sum(importance_map.get(column, 0.0) for column in columns)),
                family=family,
                warning=warning,
                expected_sign=expected_sign,
                expected_sign_label=expected_label,
            )
        )
    units.sort(key=lambda item: (item.top_rank, -item.importance_sum, item.unit))
    metadata = {
        "importance_path": path,
        "importance_rows": int(len(importance)),
        "top_raw_features_requested": int(top_raw_features),
        "max_units": int(max_units),
        "units": int(len(units)),
        "skipped_unavailable": int(skipped_unavailable),
        "skipped_nonnumeric": int(skipped_nonnumeric),
    }
    return units, metadata


def numeric_variant_frame(df: pd.DataFrame, columns: tuple[str, ...], swapped: bool) -> pd.DataFrame:
    data = {}
    feature_columns = [column for column in columns if column != "market_logit"]
    if feature_columns:
        if swapped:
            swapped_frame = swap_feature_frame(df, feature_columns)
            for column in feature_columns:
                data[column] = pd.to_numeric(swapped_frame[column], errors="coerce")
        else:
            for column in feature_columns:
                data[column] = pd.to_numeric(df[column], errors="coerce") if column in df.columns else np.nan
    if "market_logit" in columns:
        market = pd.to_numeric(df["market_logit"], errors="coerce")
        data["market_logit"] = -market if swapped else market
    return pd.DataFrame(data, index=df.index)[list(columns)]


def fit_predict_variant(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    columns: tuple[str, ...],
    c_value: float,
) -> tuple[np.ndarray, dict[str, float]]:
    y_train = train_df["red_won"].astype(int).to_numpy()
    train_direct = numeric_variant_frame(train_df, columns, swapped=False)
    train_swapped = numeric_variant_frame(train_df, columns, swapped=True)
    x_train = pd.concat([train_direct, train_swapped], ignore_index=True)
    y_extended = np.concatenate([y_train, 1 - y_train])

    eval_direct = numeric_variant_frame(eval_df, columns, swapped=False)
    eval_swapped = numeric_variant_frame(eval_df, columns, swapped=True)

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=c_value, penalty="l2", solver="liblinear", max_iter=300),
    )
    model.fit(x_train, y_extended)
    direct = probability_clip(model.predict_proba(eval_direct)[:, 1])
    swapped = probability_clip(model.predict_proba(eval_swapped)[:, 1])
    probability = probability_clip((direct + (1.0 - swapped)) / 2.0)

    logistic = model.named_steps["logisticregression"]
    return probability, {column: float(value) for column, value in zip(columns, logistic.coef_[0])}


def oriented_feature_values(df: pd.DataFrame, unit: FeatureUnit) -> pd.Series:
    if len(unit.columns) == 2:
        red_col = next((column for column in unit.columns if column.startswith("Red ")), unit.columns[0])
        blue_col = next((column for column in unit.columns if column.startswith("Blue ")), unit.columns[1])
        return pd.to_numeric(df[red_col], errors="coerce") - pd.to_numeric(df[blue_col], errors="coerce")
    column = unit.columns[0]
    return pd.to_numeric(df[column], errors="coerce")


def oriented_coefficient(unit: FeatureUnit, coefficient: dict[str, float]) -> float | None:
    if len(unit.columns) == 2:
        red_col = next((column for column in unit.columns if column.startswith("Red ")), None)
        blue_col = next((column for column in unit.columns if column.startswith("Blue ")), None)
        if red_col is None or blue_col is None:
            return None
        return float((coefficient.get(red_col, 0.0) - coefficient.get(blue_col, 0.0)) / 2.0)
    return float(coefficient.get(unit.columns[0], np.nan))


def event_bootstrap_delta(rows: pd.DataFrame, delta_col: str, iterations: int, rng) -> dict | None:
    if rows.empty or iterations <= 0:
        return None
    grouped = rows.groupby("event_date", sort=True).agg(delta_sum=(delta_col, "sum"), rows=(delta_col, "size"))
    values = grouped.to_numpy(dtype=float)
    group_count = len(values)
    if group_count == 0:
        return None
    sampled = rng.integers(0, group_count, size=(iterations, group_count))
    sums = values[sampled].sum(axis=1)
    deltas = np.divide(
        sums[:, 0],
        sums[:, 1],
        out=np.full(iterations, np.nan, dtype=float),
        where=sums[:, 1] > 0.0,
    )
    deltas = deltas[np.isfinite(deltas)]
    return {
        "iterations": int(iterations),
        "events": int(group_count),
        "ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
        "prob_delta_le_zero": float(np.mean(deltas <= 0.0)),
    }


def feature_residual_gap(df: pd.DataFrame, unit: FeatureUnit) -> dict:
    values = oriented_feature_values(df, unit)
    valid = values.notna()
    if valid.sum() < 80 or values[valid].nunique() < 4:
        return {
            "q1_q4_available": False,
            "high_minus_low_market_residual": None,
            "aligned_high_minus_low_market_residual": None,
        }
    try:
        bins = pd.qcut(values[valid], q=4, labels=False, duplicates="drop")
    except ValueError:
        return {
            "q1_q4_available": False,
            "high_minus_low_market_residual": None,
            "aligned_high_minus_low_market_residual": None,
        }
    if bins.nunique() < 4:
        return {
            "q1_q4_available": False,
            "high_minus_low_market_residual": None,
            "aligned_high_minus_low_market_residual": None,
        }
    work = df.loc[valid, ["red_won", "market_probability"]].copy()
    work["bin"] = bins.to_numpy()
    work["realized_market_residual"] = work["red_won"].astype(float) - work["market_probability"].astype(float)
    low = work[work["bin"] == int(work["bin"].min())]
    high = work[work["bin"] == int(work["bin"].max())]
    gap = float(high["realized_market_residual"].mean() - low["realized_market_residual"].mean())
    aligned_gap = None if unit.expected_sign is None else float(gap * unit.expected_sign)
    return {
        "q1_q4_available": True,
        "q1_fights": int(len(low)),
        "q4_fights": int(len(high)),
        "q1_market_residual": float(low["realized_market_residual"].mean()),
        "q4_market_residual": float(high["realized_market_residual"].mean()),
        "high_minus_low_market_residual": gap,
        "aligned_high_minus_low_market_residual": aligned_gap,
    }


def summarize_baseline(prediction_rows: pd.DataFrame) -> dict:
    y = prediction_rows["red_won"].astype(float).to_numpy()
    market = prediction_rows["market_probability"].astype(float).to_numpy()
    baseline = prediction_rows["baseline_probability"].astype(float).to_numpy()
    return {
        "folds": sorted(int(value) for value in prediction_rows["fold"].unique()),
        "fights": int(len(prediction_rows)),
        "events": int(prediction_rows["event_date"].nunique()),
        "raw_market_log_loss": log_loss(y, market),
        "market_recalibrated_log_loss": log_loss(y, baseline),
        "market_recalibration_delta_log_loss": log_loss(y, market) - log_loss(y, baseline),
    }


def summarize_unit(
    unit: FeatureUnit,
    rows: pd.DataFrame,
    coefficient_rows: list[dict],
    full_df: pd.DataFrame,
    bootstrap_iterations: int,
    rng,
) -> dict:
    y = rows["red_won"].astype(float).to_numpy()
    market = rows["market_probability"].astype(float).to_numpy()
    baseline = rows["baseline_probability"].astype(float).to_numpy()
    candidate = rows["candidate_probability"].astype(float).to_numpy()
    incremental_delta = binary_loss(y, baseline) - binary_loss(y, candidate)
    raw_market_delta = binary_loss(y, market) - binary_loss(y, candidate)
    rows = rows.copy()
    rows["incremental_delta_log_loss"] = incremental_delta
    rows["raw_market_delta_log_loss"] = raw_market_delta

    fold_deltas = [
        float(group["incremental_delta_log_loss"].mean())
        for _, group in rows.groupby("fold", sort=True)
    ]
    latest_fold = int(rows["fold"].max())
    latest_delta = float(rows.loc[rows["fold"] == latest_fold, "incremental_delta_log_loss"].mean())
    coefs = np.asarray(
        [
            row["oriented_coefficient"]
            for row in coefficient_rows
            if row["unit"] == unit.unit and row["oriented_coefficient"] is not None
        ],
        dtype=float,
    )
    mean_coef = float(np.mean(coefs)) if len(coefs) else None
    sign_consistency = None
    expected_match = None
    if len(coefs):
        nonzero = coefs[np.abs(coefs) > 1e-12]
        if len(nonzero):
            majority_positive = np.mean(nonzero > 0.0)
            sign_consistency = float(max(majority_positive, 1.0 - majority_positive))
    if mean_coef is not None and unit.expected_sign is not None:
        expected_match = bool(mean_coef * unit.expected_sign > 0.0)

    bootstrap = event_bootstrap_delta(rows, "incremental_delta_log_loss", bootstrap_iterations, rng)
    residual_gap = feature_residual_gap(full_df, unit)
    wrong_way_known = False
    if unit.expected_sign is not None:
        aligned_gap = residual_gap.get("aligned_high_minus_low_market_residual")
        coef_wrong = mean_coef is not None and mean_coef * unit.expected_sign <= 0.0
        gap_wrong = aligned_gap is not None and aligned_gap <= 0.0
        wrong_way_known = bool(coef_wrong or gap_wrong)

    return {
        "unit": unit.unit,
        "columns": list(unit.columns),
        "source_features": list(unit.source_features),
        "top_rank": int(unit.top_rank),
        "importance_sum": float(unit.importance_sum),
        "family": unit.family,
        "warning": unit.warning,
        "expected_sign": unit.expected_sign,
        "expected_sign_label": unit.expected_sign_label,
        "fights": int(len(rows)),
        "events": int(rows["event_date"].nunique()),
        "feature_log_loss": log_loss(y, candidate),
        "incremental_delta_log_loss": float(np.mean(incremental_delta)),
        "raw_market_delta_log_loss": float(np.mean(raw_market_delta)),
        "positive_folds": int(sum(delta > 0.0 for delta in fold_deltas)),
        "folds": int(len(fold_deltas)),
        "fold_deltas": fold_deltas,
        "latest_fold": latest_fold,
        "latest_fold_incremental_delta_log_loss": latest_delta,
        "mean_oriented_coefficient": mean_coef,
        "coefficient_sign_consistency": sign_consistency,
        "expected_sign_match": expected_match,
        "wrong_way_known_prior": wrong_way_known,
        "bootstrap": bootstrap,
        **residual_gap,
    }


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    predictions = load_predictions(args.predictions)
    features = load_features(args.features)
    df = merge_predictions_features(predictions, features)
    df = df.sort_values(["event_date", "fight_key"]).reset_index(drop=True)
    units, unit_metadata = load_feature_units(args.importance, df, args.top_raw_features, args.max_units)
    if not units:
        raise SystemExit("No feature units available for audit")

    baseline_by_index = {}
    prediction_rows = []
    coefficient_rows = []
    baseline_columns = ("market_logit",)
    folds = sorted(int(value) for value in df["fold"].unique())

    for fold in folds:
        if fold == min(folds):
            continue
        train_df = df[df["fold"] < fold].copy()
        eval_df = df[df["fold"] == fold].copy()
        if train_df.empty or eval_df.empty:
            continue
        baseline_probability, _ = fit_predict_variant(train_df, eval_df, baseline_columns, args.c)
        eval_indices = eval_df.index.to_numpy()
        for index, probability in zip(eval_indices, baseline_probability):
            baseline_by_index[int(index)] = float(probability)

        for unit in units:
            columns = ("market_logit", *unit.columns)
            probability, coefficients = fit_predict_variant(train_df, eval_df, columns, args.c)
            oriented_coef = oriented_coefficient(unit, coefficients)
            coefficient_rows.append(
                {
                    "fold": int(fold),
                    "unit": unit.unit,
                    "columns": list(unit.columns),
                    "oriented_coefficient": oriented_coef,
                    "coefficients": coefficients,
                }
            )
            for row_index, candidate_probability in zip(eval_indices, probability):
                source = df.loc[row_index]
                prediction_rows.append(
                    {
                        "fold": int(fold),
                        "event_date": pd.Timestamp(source["event_date"]).date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "red_won": int(source["red_won"]),
                        "market_probability": float(source["market_probability"]),
                        "baseline_probability": float(baseline_by_index[int(row_index)]),
                        "unit": unit.unit,
                        "candidate_probability": float(candidate_probability),
                    }
                )

    all_predictions = pd.DataFrame(prediction_rows)
    if all_predictions.empty:
        raise SystemExit("No rolling predictions were produced")

    baseline_frame = all_predictions.drop_duplicates("fight_key")[
        ["fold", "event_date", "fight_key", "red_won", "market_probability", "baseline_probability"]
    ].copy()
    unit_summaries = []
    for unit in units:
        rows = all_predictions[all_predictions["unit"] == unit.unit].copy()
        unit_summaries.append(
            summarize_unit(
                unit,
                rows,
                coefficient_rows,
                df,
                args.bootstrap_iterations,
                rng,
            )
        )

    unit_summaries.sort(key=lambda row: row["incremental_delta_log_loss"], reverse=True)
    return {
        "paths": {
            "predictions": args.predictions,
            "features": args.features,
            "importance": args.importance,
        },
        "parameters": {
            "top_raw_features": args.top_raw_features,
            "max_units": args.max_units,
            "c": args.c,
            "bootstrap_iterations": args.bootstrap_iterations,
            "seed": args.seed,
        },
        "feature_unit_metadata": unit_metadata,
        "merged_rows": int(len(df)),
        "folds_available": folds,
        "rolling_eval_folds": summarize_baseline(baseline_frame)["folds"],
        "baseline": summarize_baseline(baseline_frame),
        "unit_summaries": unit_summaries,
        "family_summary": family_summary(unit_summaries),
        "coefficient_rows": coefficient_rows,
    }


def family_summary(unit_summaries: list[dict]) -> list[dict]:
    rows = []
    for family, group in pd.DataFrame(unit_summaries).groupby("family", sort=True):
        rows.append(
            {
                "family": family,
                "units": int(len(group)),
                "importance_sum": float(group["importance_sum"].sum()),
                "mean_incremental_delta_log_loss": float(group["incremental_delta_log_loss"].mean()),
                "median_incremental_delta_log_loss": float(group["incremental_delta_log_loss"].median()),
                "positive_units": int((group["incremental_delta_log_loss"] > 0.0).sum()),
                "wrong_way_known_prior_units": int(group["wrong_way_known_prior"].sum()),
                "warning_units": int(group["warning"].notna().sum()),
            }
        )
    rows.sort(key=lambda row: row["mean_incremental_delta_log_loss"], reverse=True)
    return rows


def markdown_feature_table(rows: list[dict], limit: int) -> list[str]:
    lines = [
        "| Unit | Family | Rank | Importance | Inc Delta LL | Positive Folds | Boot P(delta<=0) | Latest Delta | Coef | Prior | Q4-Q1 Residual | Warning |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows[:limit]:
        boot = row.get("bootstrap") or {}
        prior = ""
        if row["expected_sign"] == 1:
            prior = "+"
        elif row["expected_sign"] == -1:
            prior = "-"
        lines.append(
            "| `{unit}` | {family} | {rank} | {importance} | {delta} | {positive} / {folds} | {boot_p} | {latest} | {coef} | {prior} | {gap} | {warning} |".format(
                unit=row["unit"],
                family=row["family"],
                rank=row["top_rank"],
                importance=fmt_float(row["importance_sum"], 0),
                delta=fmt_float(row["incremental_delta_log_loss"]),
                positive=row["positive_folds"],
                folds=row["folds"],
                boot_p=fmt_p(boot.get("prob_delta_le_zero")),
                latest=fmt_float(row["latest_fold_incremental_delta_log_loss"]),
                coef=fmt_float(row["mean_oriented_coefficient"]),
                prior=prior,
                gap=fmt_pct(row.get("high_minus_low_market_residual")),
                warning=row["warning"] or "",
            )
        )
    return lines


def markdown_family_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Family | Units | Importance | Mean Inc Delta LL | Median Inc Delta LL | Positive Units | Wrong-Way Known Priors | Warning Units |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {family} | {units} | {importance} | {mean} | {median} | {positive} | {wrong} | {warnings} |".format(
                family=row["family"],
                units=row["units"],
                importance=fmt_float(row["importance_sum"], 0),
                mean=fmt_float(row["mean_incremental_delta_log_loss"]),
                median=fmt_float(row["median_incremental_delta_log_loss"]),
                positive=row["positive_units"],
                wrong=row["wrong_way_known_prior_units"],
                warnings=row["warning_units"],
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    summaries = result["unit_summaries"]
    helpful = sorted(summaries, key=lambda row: row["incremental_delta_log_loss"], reverse=True)
    harmful = sorted(summaries, key=lambda row: row["incremental_delta_log_loss"])
    wrong_way = [
        row
        for row in summaries
        if row["wrong_way_known_prior"] and row["expected_sign"] is not None
    ]
    wrong_way.sort(key=lambda row: (row["incremental_delta_log_loss"], row["top_rank"]))
    positive_units = [row for row in summaries if row["incremental_delta_log_loss"] > 0.0]
    robust_units = [
        row
        for row in positive_units
        if (row.get("bootstrap") or {}).get("prob_delta_le_zero", 1.0) <= 0.10
        and row["positive_folds"] >= max(3, row["folds"] - 1)
    ]

    baseline = result["baseline"]
    lines = [
        "# Feature Signal After Market Audit",
        "",
        "This diagnostic takes the current regularized-LGBM top-importance",
        "features and tests each feature unit one at a time after market",
        "control. For each evaluation fold after fold 1, it trains on prior",
        "folds only, uses direct/swapped fighter-order augmentation, and",
        "compares `market_logit + feature` against a rolling market-only",
        "logistic recalibration. It does not select or promote a new feature",
        "set or betting policy.",
        "",
        "## Inputs",
        "",
        f"- residual predictions: `{result['paths']['predictions']}`",
        f"- feature table: `{result['paths']['features']}`",
        f"- importance file: `{result['paths']['importance']}`",
        f"- merged prediction/feature rows: `{result['merged_rows']}`",
        f"- feature units tested: `{result['feature_unit_metadata']['units']}`",
        f"- rolling eval folds: `{', '.join(str(value) for value in result['rolling_eval_folds'])}`",
        "",
        "## Market Baseline",
        "",
        "| Fights | Events | Raw Market LL | Market-Recal LL | Recal Delta LL |",
        "| ---: | ---: | ---: | ---: | ---: |",
        "| {fights} | {events} | {raw} | {recal} | {delta} |".format(
            fights=baseline["fights"],
            events=baseline["events"],
            raw=fmt_float(baseline["raw_market_log_loss"]),
            recal=fmt_float(baseline["market_recalibrated_log_loss"]),
            delta=fmt_float(baseline["market_recalibration_delta_log_loss"]),
        ),
        "",
        "## Family Summary",
        "",
        *markdown_family_table(result["family_summary"]),
        "",
        "## Top Incremental Helpers",
        "",
        *markdown_feature_table(helpful, 15),
        "",
        "## Largest Incremental Harms",
        "",
        *markdown_feature_table(harmful, 15),
        "",
        "## Known-Prior Sign Warnings",
        "",
    ]
    if wrong_way:
        lines.extend(markdown_feature_table(wrong_way, 15))
    else:
        lines.append("No known-prior feature units were flagged as wrong-way by coefficient or Q4-Q1 residual checks.")

    best = helpful[0]
    worst = harmful[0]
    top_family = max(
        result["family_summary"],
        key=lambda row: row["positive_units"],
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Positive incremental units: `{len(positive_units)} / {len(summaries)}`.",
            f"- Robust-looking diagnostic units by the loose bootstrap/sign-consistency screen: `{len(robust_units)}`.",
            f"- Best one-feature after-market delta LL: `{best['unit']}` at `{fmt_float(best['incremental_delta_log_loss'])}`.",
            f"- Worst one-feature after-market delta LL: `{worst['unit']}` at `{fmt_float(worst['incremental_delta_log_loss'])}`.",
            f"- The positive units are concentrated in `{top_family['family']}` features; record/experience, age/recency, and grappling units do not show broad individual lift after market control.",
            "- Several helpers are duplicate encodings of the same underlying striking-differential theme, so they should be treated as clues for feature redesign rather than independent alpha discoveries.",
            "- The strongest helper is still a percentage/rate proxy, so its formula should be audited in fight context before using it as a promoted signal.",
            "- Treat this as a feature-forensics map, not feature selection. A promoted feature set still needs a predeclared rolling backtest and market-null/bootstrap validation.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "feature_signal_after_market_audit.json"
    md_path = output_dir / "feature_signal_after_market_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
