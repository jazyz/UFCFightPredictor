#!/usr/bin/env python3
"""Feature-regime diagnostics for recent residual drift.

This audit does not retrain a model or select a new policy. It merges the
saved residual-shrinkage holdout probabilities with the production feature
table, then asks which market, residual, title, and top-feature regimes explain
the recent decay of the model-after-market residual signal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
DEFAULT_FEATURES = "data/detailed_fights.csv"
DEFAULT_IMPORTANCE = "test_results/regularized_lgbm_feature_importance.csv"
DEFAULT_OUTPUT_DIR = "test_results/residual_feature_drift_audit"

EPS = 1e-6
POLICIES = {
    "selected_shrinkage": "selected_probability",
    "fixed_half_residual": "fixed_half_probability",
    "unshrunk_meta": "unshrunk_probability",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Audit residual drift by feature regimes")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--importance", default=DEFAULT_IMPORTANCE)
    parser.add_argument("--top-features", type=int, default=25)
    parser.add_argument("--min-bin-fights", type=int, default=30)
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


def binary_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def parse_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="mixed", errors="coerce")


def fight_key(date_value, red_fighter, blue_fighter) -> str:
    date = pd.Timestamp(date_value).date().isoformat()
    fighters = sorted([canonical_name(red_fighter), canonical_name(blue_fighter)])
    return f"{date}|{fighters[0]}|{fighters[1]}"


def load_predictions(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "fight_key",
        "event_date",
        "title",
        "red_fighter",
        "blue_fighter",
        "red_won",
        "market_probability",
        *POLICIES.values(),
    }
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing prediction columns: {sorted(missing)}")
    return df.copy()


def load_feature_rows(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"Date", "Red Fighter", "Blue Fighter", "Title"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing feature columns: {sorted(missing)}")
    df["event_date"] = parse_date_series(df["Date"])
    df = df.dropna(subset=["event_date"]).copy()
    df["fight_key"] = [
        fight_key(date, red, blue)
        for date, red, blue in zip(df["event_date"], df["Red Fighter"], df["Blue Fighter"])
    ]
    return df


def merge_predictions_features(predictions: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    duplicate_keys = features["fight_key"].duplicated().sum()
    if duplicate_keys:
        features = features.sort_values(["event_date", "fight_key"]).drop_duplicates("fight_key", keep="last")
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


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["red_won"] = df["red_won"].astype(float)
    df["market_loss"] = binary_loss(df["red_won"], df["market_probability"])
    df["selected_loss"] = binary_loss(df["red_won"], df["selected_probability"])
    df["fixed_half_loss"] = binary_loss(df["red_won"], df["fixed_half_probability"])
    df["unshrunk_loss"] = binary_loss(df["red_won"], df["unshrunk_probability"])
    df["selected_delta_ll"] = df["market_loss"] - df["selected_loss"]
    df["fixed_half_delta_ll"] = df["market_loss"] - df["fixed_half_loss"]
    df["unshrunk_delta_ll"] = df["market_loss"] - df["unshrunk_loss"]
    df["selected_adjustment"] = df["selected_probability"] - df["market_probability"]
    df["realized_market_residual"] = df["red_won"] - df["market_probability"]
    df["selected_policy_gap"] = df["red_won"] - df["selected_probability"]
    df["period"] = np.select(
        [
            df["event_date"].dt.year.eq(2024),
            df["event_date"].dt.year.eq(2025),
            df["event_date"].dt.year.eq(2026),
        ],
        ["2024", "2025", "2026"],
        default="other",
    )
    latest_fold = int(df["fold"].max())
    df["is_latest_fold"] = df["fold"].astype(int).eq(latest_fold)
    max_date = df["event_date"].max()
    df["is_last_365d"] = df["event_date"] >= max_date - pd.Timedelta(days=365)
    return df


def summarize_subset(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "fights": 0,
            "events": 0,
            "market_log_loss": None,
            "selected_log_loss": None,
            "selected_delta_log_loss": None,
            "fixed_half_delta_log_loss": None,
            "unshrunk_delta_log_loss": None,
            "actual_rate": None,
            "mean_market_probability": None,
            "mean_selected_probability": None,
            "mean_selected_adjustment": None,
            "realized_market_residual": None,
            "selected_policy_gap": None,
        }
    return {
        "fights": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "market_log_loss": float(df["market_loss"].mean()),
        "selected_log_loss": float(df["selected_loss"].mean()),
        "selected_delta_log_loss": float(df["selected_delta_ll"].mean()),
        "fixed_half_delta_log_loss": float(df["fixed_half_delta_ll"].mean()),
        "unshrunk_delta_log_loss": float(df["unshrunk_delta_ll"].mean()),
        "actual_rate": float(df["red_won"].mean()),
        "mean_market_probability": float(df["market_probability"].mean()),
        "mean_selected_probability": float(df["selected_probability"].mean()),
        "mean_selected_adjustment": float(df["selected_adjustment"].mean()),
        "realized_market_residual": float(df["realized_market_residual"].mean()),
        "selected_policy_gap": float(df["selected_policy_gap"].mean()),
    }


def period_summary(df: pd.DataFrame) -> list[dict]:
    specs = [
        ("aggregate", pd.Series(True, index=df.index)),
        ("2024", df["period"].eq("2024")),
        ("2025", df["period"].eq("2025")),
        ("2026", df["period"].eq("2026")),
        ("2025-2026", df["period"].isin(["2025", "2026"])),
        ("last 365 days", df["is_last_365d"]),
        (f"latest fold {int(df['fold'].max())}", df["is_latest_fold"]),
    ]
    rows = []
    for label, mask in specs:
        row = summarize_subset(df[mask])
        row["period"] = label
        rows.append(row)
    return rows


def title_group(title: str) -> str:
    value = str(title).lower()
    if "heavyweight" in value and "light heavyweight" not in value:
        return "heavyweight"
    if "light heavyweight" in value:
        return "light_heavyweight"
    if "middleweight" in value:
        return "middleweight"
    if "welterweight" in value:
        return "welterweight"
    if "lightweight" in value and "heavyweight" not in value:
        return "lightweight"
    if "featherweight" in value:
        return "featherweight"
    if "bantamweight" in value:
        return "bantamweight"
    if "flyweight" in value:
        return "flyweight"
    if "catch" in value:
        return "catchweight"
    return "other"


def add_regime_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["title_group"] = df["title"].map(title_group)
    df["market_probability_bin"] = pd.cut(
        df["market_probability"],
        bins=[0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0],
        labels=["<0.40", "0.40-0.50", "0.50-0.60", "0.60-0.70", "0.70-0.80", ">=0.80"],
        include_lowest=True,
        right=False,
    )
    df["selected_adjustment_bin"] = pd.cut(
        df["selected_adjustment"],
        bins=[-np.inf, -0.05, -0.02, 0.02, 0.05, np.inf],
        labels=["<= -5%", "-5% to -2%", "-2% to +2%", "+2% to +5%", ">= +5%"],
    )
    df["adjustment_direction"] = np.where(
        df["selected_adjustment"] >= 0.0,
        "meta_up_on_red",
        "meta_down_on_red",
    )
    return df


def grouped_rows(df: pd.DataFrame, column: str, label: str, min_fights: int) -> list[dict]:
    rows = []
    for value, subset in df.groupby(column, observed=True, dropna=True):
        if len(subset) < min_fights:
            continue
        row = summarize_subset(subset)
        row["slice_family"] = label
        row["slice"] = str(value)
        rows.append(row)
    return sorted(rows, key=lambda item: item["selected_delta_log_loss"])


def regime_summary(df: pd.DataFrame, min_fights: int) -> dict:
    recent = df[df["period"].isin(["2025", "2026"])].copy()
    latest = df[df["is_latest_fold"]].copy()
    return {
        "aggregate": [
            *grouped_rows(df, "market_probability_bin", "market_probability", min_fights),
            *grouped_rows(df, "selected_adjustment_bin", "selected_adjustment", min_fights),
            *grouped_rows(df, "adjustment_direction", "adjustment_direction", min_fights),
            *grouped_rows(df, "title_group", "title_group", min_fights),
        ],
        "recent_2025_2026": [
            *grouped_rows(recent, "market_probability_bin", "market_probability", min_fights),
            *grouped_rows(recent, "selected_adjustment_bin", "selected_adjustment", min_fights),
            *grouped_rows(recent, "adjustment_direction", "adjustment_direction", min_fights),
            *grouped_rows(recent, "title_group", "title_group", min_fights),
        ],
        "latest_fold": [
            *grouped_rows(latest, "market_probability_bin", "market_probability", max(10, min_fights // 2)),
            *grouped_rows(latest, "selected_adjustment_bin", "selected_adjustment", max(10, min_fights // 2)),
            *grouped_rows(latest, "adjustment_direction", "adjustment_direction", max(10, min_fights // 2)),
            *grouped_rows(latest, "title_group", "title_group", max(10, min_fights // 2)),
        ],
    }


def load_top_features(path: str, feature_df: pd.DataFrame, count: int) -> list[str]:
    importance_path = Path(path)
    if not importance_path.exists() or count <= 0:
        return []
    importance = pd.read_csv(importance_path)
    if "feature" not in importance.columns:
        return []
    available = set(feature_df.columns)
    numeric = set(feature_df.select_dtypes(include=[np.number]).columns)
    features = []
    for feature in importance["feature"].astype(str).tolist():
        if feature in available and feature in numeric and feature not in features:
            features.append(feature)
        if len(features) >= count:
            break
    return features


def feature_bin_labels(series: pd.Series) -> pd.Series | None:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() < 40 or numeric.nunique(dropna=True) < 4:
        return None
    try:
        return pd.qcut(numeric, q=4, labels=["q1_low", "q2", "q3", "q4_high"], duplicates="drop")
    except ValueError:
        return None


def feature_bin_audit(df: pd.DataFrame, features: list[str], min_fights: int) -> list[dict]:
    rows = []
    for feature in features:
        labels = feature_bin_labels(df[feature])
        if labels is None:
            continue
        work = df.assign(_feature_bin=labels)
        for bin_label, subset in work.groupby("_feature_bin", observed=True):
            recent = subset[subset["period"].isin(["2025", "2026"])]
            if len(recent) < min_fights:
                continue
            baseline = subset[subset["period"].eq("2024")]
            latest = subset[subset["is_latest_fold"]]
            row = summarize_subset(recent)
            row.update(
                {
                    "feature": feature,
                    "bin": str(bin_label),
                    "range_min": float(pd.to_numeric(subset[feature], errors="coerce").min()),
                    "range_max": float(pd.to_numeric(subset[feature], errors="coerce").max()),
                    "aggregate_fights": int(len(subset)),
                    "baseline_2024_fights": int(len(baseline)),
                    "baseline_2024_delta_log_loss": (
                        float(baseline["selected_delta_ll"].mean()) if not baseline.empty else None
                    ),
                    "latest_fold_fights": int(len(latest)),
                    "latest_fold_delta_log_loss": (
                        float(latest["selected_delta_ll"].mean()) if not latest.empty else None
                    ),
                    "recent_share_of_bin": float(len(recent) / len(subset)),
                }
            )
            row["delta_vs_2024"] = (
                None
                if row["baseline_2024_delta_log_loss"] is None
                else row["selected_delta_log_loss"] - row["baseline_2024_delta_log_loss"]
            )
            rows.append(row)
    return sorted(rows, key=lambda item: item["selected_delta_log_loss"])


def feature_distribution_shift(df: pd.DataFrame, features: list[str]) -> list[dict]:
    rows = []
    baseline = df[df["period"].eq("2024")]
    recent = df[df["period"].isin(["2025", "2026"])]
    latest = df[df["is_latest_fold"]]
    for feature in features:
        series = pd.to_numeric(df[feature], errors="coerce")
        base_values = pd.to_numeric(baseline[feature], errors="coerce").dropna()
        recent_values = pd.to_numeric(recent[feature], errors="coerce").dropna()
        latest_values = pd.to_numeric(latest[feature], errors="coerce").dropna()
        if len(base_values) < 20 or len(recent_values) < 20:
            continue
        pooled_std = float(series.std(ddof=0))
        if not np.isfinite(pooled_std) or pooled_std <= 0:
            continue
        row_delta_corr = np.corrcoef(
            series.fillna(series.median()).to_numpy(dtype=float),
            df["selected_delta_ll"].to_numpy(dtype=float),
        )[0, 1]
        row_adj_corr = np.corrcoef(
            series.fillna(series.median()).to_numpy(dtype=float),
            df["selected_adjustment"].to_numpy(dtype=float),
        )[0, 1]
        rows.append(
            {
                "feature": feature,
                "baseline_2024_mean": float(base_values.mean()),
                "recent_2025_2026_mean": float(recent_values.mean()),
                "latest_fold_mean": float(latest_values.mean()) if len(latest_values) else None,
                "recent_minus_2024_std": float((recent_values.mean() - base_values.mean()) / pooled_std),
                "latest_minus_2024_std": (
                    float((latest_values.mean() - base_values.mean()) / pooled_std)
                    if len(latest_values)
                    else None
                ),
                "corr_with_selected_delta_ll": float(row_delta_corr) if np.isfinite(row_delta_corr) else None,
                "corr_with_selected_adjustment": float(row_adj_corr) if np.isfinite(row_adj_corr) else None,
            }
        )
    return sorted(rows, key=lambda item: abs(item["recent_minus_2024_std"]), reverse=True)


def top_feature_bins(rows: list[dict], limit: int = 12) -> list[dict]:
    return rows[:limit]


def top_breaking_bins(rows: list[dict], limit: int = 12) -> list[dict]:
    candidates = [
        row
        for row in rows
        if row.get("baseline_2024_delta_log_loss") is not None
        and row["baseline_2024_fights"] >= 15
        and row["selected_delta_log_loss"] < 0
    ]
    candidates.sort(key=lambda item: (item["delta_vs_2024"], item["selected_delta_log_loss"]))
    return candidates[:limit]


def as_table_period(rows: list[dict]) -> list[str]:
    lines = [
        "| Period | Fights | Actual | Market P | Selected P | Adj | Realized Residual | Delta LL | Fixed-Half Delta LL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {period} | {fights} | {actual} | {market} | {selected} | {adj} | {realized} | {delta} | {half} |".format(
                period=row["period"],
                fights=row["fights"],
                actual=fmt_pct(row["actual_rate"]),
                market=fmt_pct(row["mean_market_probability"]),
                selected=fmt_pct(row["mean_selected_probability"]),
                adj=fmt_pct(row["mean_selected_adjustment"]),
                realized=fmt_pct(row["realized_market_residual"]),
                delta=fmt_float(row["selected_delta_log_loss"]),
                half=fmt_float(row["fixed_half_delta_log_loss"]),
            )
        )
    return lines


def as_table_regime(rows: list[dict], limit: int = 16) -> list[str]:
    lines = [
        "| Family | Slice | Fights | Actual - Market | Adj | Selected Delta LL | Fixed-Half Delta LL |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:limit]:
        lines.append(
            "| {family} | {slice} | {fights} | {realized} | {adj} | {delta} | {half} |".format(
                family=row["slice_family"],
                slice=row["slice"],
                fights=row["fights"],
                realized=fmt_pct(row["realized_market_residual"]),
                adj=fmt_pct(row["mean_selected_adjustment"]),
                delta=fmt_float(row["selected_delta_log_loss"]),
                half=fmt_float(row["fixed_half_delta_log_loss"]),
            )
        )
    return lines


def as_table_feature_bins(rows: list[dict], limit: int = 12) -> list[str]:
    lines = [
        "| Feature | Bin | Range | Recent Fights | Recent Delta LL | 2024 Delta LL | Delta vs 2024 | Latest Fights | Latest Delta LL | Actual - Market | Adj |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:limit]:
        lines.append(
            "| {feature} | {bin} | {low} to {high} | {fights} | {delta} | {base} | {diff} | {latest_fights} | {latest_delta} | {realized} | {adj} |".format(
                feature=row["feature"],
                bin=row["bin"],
                low=fmt_float(row["range_min"], 2),
                high=fmt_float(row["range_max"], 2),
                fights=row["fights"],
                delta=fmt_float(row["selected_delta_log_loss"]),
                base=fmt_float(row["baseline_2024_delta_log_loss"]),
                diff=fmt_float(row["delta_vs_2024"]),
                latest_fights=row["latest_fold_fights"],
                latest_delta=fmt_float(row["latest_fold_delta_log_loss"]),
                realized=fmt_pct(row["realized_market_residual"]),
                adj=fmt_pct(row["mean_selected_adjustment"]),
            )
        )
    return lines


def as_table_shifts(rows: list[dict], limit: int = 12) -> list[str]:
    lines = [
        "| Feature | 2024 Mean | 2025-2026 Mean | Std Shift | Latest Mean | Latest Std Shift | Corr Delta LL | Corr Adj |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:limit]:
        lines.append(
            "| {feature} | {base} | {recent} | {shift} | {latest} | {latest_shift} | {corr_delta} | {corr_adj} |".format(
                feature=row["feature"],
                base=fmt_float(row["baseline_2024_mean"], 3),
                recent=fmt_float(row["recent_2025_2026_mean"], 3),
                shift=fmt_float(row["recent_minus_2024_std"], 3),
                latest=fmt_float(row["latest_fold_mean"], 3),
                latest_shift=fmt_float(row["latest_minus_2024_std"], 3),
                corr_delta=fmt_float(row["corr_with_selected_delta_ll"], 3),
                corr_adj=fmt_float(row["corr_with_selected_adjustment"], 3),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Feature Drift Audit",
        "",
        "This audit merges residual-shrinkage holdout probabilities with the",
        "production feature table. It is diagnostic only: no model is retrained,",
        "no threshold is selected, and no new betting policy is proposed.",
        "",
        "## Inputs",
        "",
        f"- predictions: `{result['paths']['predictions']}`",
        f"- features: `{result['paths']['features']}`",
        f"- feature importance: `{result['paths']['importance']}`",
        f"- merged fights: `{result['merged_fights']}`",
        f"- top features inspected: `{len(result['top_features'])}`",
        "",
        "## Period Drift",
        "",
        *as_table_period(result["period_summary"]),
        "",
        "## Worst Recent Regime Slices",
        "",
        "These are market/residual/title slices in 2025-2026 with enough fights",
        "to be meaningful diagnostics.",
        "",
        *as_table_regime(result["regime_summary"]["recent_2025_2026"]),
        "",
        "## Latest-Fold Regime Slices",
        "",
        *as_table_regime(result["regime_summary"]["latest_fold"]),
        "",
        "## Worst Recent Top-Feature Bins",
        "",
        "Feature bins use quartiles computed on the full residual holdout, then",
        "score only 2025-2026 rows. This is not a selection protocol; it is a",
        "root-cause diagnostic.",
        "",
        *as_table_feature_bins(result["worst_recent_feature_bins"]),
        "",
        "## Feature Bins That Broke Versus 2024",
        "",
        *as_table_feature_bins(result["feature_bins_broke_vs_2024"]),
        "",
        "## Largest Top-Feature Distribution Shifts",
        "",
        *as_table_shifts(result["feature_distribution_shift"]),
        "",
        "## Interpretation",
        "",
        *result["interpretation"],
        "",
    ]
    return "\n".join(lines)


def interpretation(result: dict) -> list[str]:
    rows = []
    period_by_name = {row["period"]: row for row in result["period_summary"]}
    latest = result["period_summary"][-1]
    recent = period_by_name.get("2025-2026")
    if recent:
        rows.append(
            "- The recent 2025-2026 residual is weak: selected-shrinkage Delta LL is `{}` with realized market residual `{}`.".format(
                fmt_float(recent["selected_delta_log_loss"]),
                fmt_pct(recent["realized_market_residual"]),
            )
        )
    rows.append(
        "- The latest fold remains the cleanest warning sign: selected-shrinkage Delta LL is `{}` while the model still adjusts red probability by `{}` on average.".format(
            fmt_float(latest["selected_delta_log_loss"]),
            fmt_pct(latest["mean_selected_adjustment"]),
        )
    )
    worst_regime = result["regime_summary"]["recent_2025_2026"][:1]
    if worst_regime:
        row = worst_regime[0]
        rows.append(
            "- The worst recent simple regime is `{}` / `{}` with Delta LL `{}` and realized market residual `{}`.".format(
                row["slice_family"],
                row["slice"],
                fmt_float(row["selected_delta_log_loss"]),
                fmt_pct(row["realized_market_residual"]),
            )
        )
    worst_feature = result["worst_recent_feature_bins"][:1]
    if worst_feature:
        row = worst_feature[0]
        rows.append(
            "- The worst recent top-feature bin is `{}` `{}` with Delta LL `{}` over `{}` recent fights; treat this as a drift clue, not a tradable rule.".format(
                row["feature"],
                row["bin"],
                fmt_float(row["selected_delta_log_loss"]),
                row["fights"],
            )
        )
    rows.append(
        "- This audit does not justify adding capacity or a new hand-picked feature yet. The next feature work should target drift explanations that can be predeclared, then validated in rolling folds or future paper tracking."
    )
    return rows


def audit(args) -> dict:
    predictions = load_predictions(args.predictions)
    features = load_feature_rows(args.features)
    merged = merge_predictions_features(predictions, features)
    merged = add_regime_columns(add_metrics(merged))
    top_features = load_top_features(args.importance, merged, args.top_features)
    feature_bins = feature_bin_audit(merged, top_features, args.min_bin_fights)
    result = {
        "paths": {
            "predictions": args.predictions,
            "features": args.features,
            "importance": args.importance,
        },
        "merged_fights": int(len(merged)),
        "top_features": top_features,
        "period_summary": period_summary(merged),
        "regime_summary": regime_summary(merged, args.min_bin_fights),
        "feature_bin_summary": feature_bins,
        "worst_recent_feature_bins": top_feature_bins(feature_bins),
        "feature_bins_broke_vs_2024": top_breaking_bins(feature_bins),
        "feature_distribution_shift": feature_distribution_shift(merged, top_features),
    }
    result["interpretation"] = interpretation(result)
    return result


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_feature_drift_audit.json"
    md_path = output_dir / "residual_feature_drift_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Merged fights: {result['merged_fights']}")


if __name__ == "__main__":
    main()
