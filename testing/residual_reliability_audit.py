#!/usr/bin/env python3
"""Reliability audit for model residual adjustments after market control.

The core alpha claim is that candidate probabilities improve market prices by
moving in the direction of true market error. This audit estimates that
directly: realized market residual (`outcome - market_probability`) is regressed
on candidate adjustment (`candidate_probability - market_probability`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
POLICIES = (
    ("selected_shrinkage", "selected_probability"),
    ("fixed_half_residual", "fixed_half_probability"),
    ("unshrunk_meta", "unshrunk_probability"),
)
EPS = 1e-6


def parse_args():
    parser = argparse.ArgumentParser(description="Audit residual adjustment reliability")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_reliability_audit")
    return parser.parse_args()


def probability_clip(values) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), EPS, 1.0 - EPS)


def binary_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = probability_clip(probability)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


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


def metric_arrays(
    df: pd.DataFrame,
    policy_col: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    y = df["red_won"].astype(float).to_numpy()
    market = df["market_probability"].astype(float).to_numpy()
    candidate = df[policy_col].astype(float).to_numpy()
    adjustment = candidate - market
    realized_market_residual = y - market
    loss_delta = binary_loss(y, market) - binary_loss(y, candidate)
    return y, market, candidate, adjustment, realized_market_residual, loss_delta


def slope_origin(adjustment: np.ndarray, realized_market_residual: np.ndarray) -> float | None:
    denom = float(np.sum(adjustment * adjustment))
    if denom <= 0.0:
        return None
    return float(np.sum(adjustment * realized_market_residual) / denom)


def slope_with_intercept(adjustment: np.ndarray, realized_market_residual: np.ndarray) -> tuple[float | None, float | None]:
    if len(adjustment) < 2 or float(np.std(adjustment)) <= 0.0:
        return None, None
    x = np.column_stack([np.ones(len(adjustment)), adjustment])
    intercept, slope = np.linalg.lstsq(x, realized_market_residual, rcond=None)[0]
    return float(intercept), float(slope)


def correlation(adjustment: np.ndarray, realized_market_residual: np.ndarray) -> float | None:
    if len(adjustment) < 2:
        return None
    if float(np.std(adjustment)) <= 0.0 or float(np.std(realized_market_residual)) <= 0.0:
        return None
    return float(np.corrcoef(adjustment, realized_market_residual)[0, 1])


def summarize_rows(df: pd.DataFrame, policy_name: str, policy_col: str) -> dict:
    if df.empty:
        return {
            "policy": policy_name,
            "fights": 0,
            "events": 0,
        }
    y, market, candidate, adjustment, realized, loss_delta = metric_arrays(df, policy_col)
    intercept, slope = slope_with_intercept(adjustment, realized)
    abs_mask = np.abs(adjustment) >= 0.02
    directional_hit = None
    if abs_mask.any():
        directional_hit = float(
            np.mean(
                np.where(
                    adjustment[abs_mask] >= 0.0,
                    realized[abs_mask] > 0.0,
                    realized[abs_mask] < 0.0,
                )
            )
        )
    return {
        "policy": policy_name,
        "fights": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "mean_adjustment": float(np.mean(adjustment)),
        "mean_abs_adjustment": float(np.mean(np.abs(adjustment))),
        "mean_realized_market_residual": float(np.mean(realized)),
        "mean_actual_minus_candidate": float(np.mean(y - candidate)),
        "slope_origin": slope_origin(adjustment, realized),
        "intercept": intercept,
        "slope_with_intercept": slope,
        "correlation": correlation(adjustment, realized),
        "delta_log_loss": float(np.mean(loss_delta)),
        "directional_hit_abs_ge_2pp": directional_hit,
        "adjusted_fights_abs_ge_2pp": int(abs_mask.sum()),
    }


def period_frames(df: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    return [
        ("aggregate", "aggregate", df),
        ("2024", "calendar 2024", df[df["event_date"].dt.year == 2024]),
        ("2025_2026", "2025-2026", df[df["event_date"].dt.year >= 2025]),
        ("last_365d", "last 365 days", df[df["event_date"] >= pd.Timestamp("2025-06-28")]),
        ("latest_fold", f"latest fold {int(df['fold'].max())}", df[df["fold"] == df["fold"].max()]),
    ]


def event_bootstrap(df: pd.DataFrame, policy_col: str, iterations: int, rng) -> dict | None:
    if df.empty or iterations <= 0:
        return None
    y, market, candidate, adjustment, realized, loss_delta = metric_arrays(df, policy_col)
    work = df[["event_date"]].copy()
    work["numerator"] = adjustment * realized
    work["denominator"] = adjustment * adjustment
    work["loss_delta_sum"] = loss_delta
    work["rows"] = 1
    grouped = work.groupby("event_date", sort=True)[["numerator", "denominator", "loss_delta_sum", "rows"]].sum()
    values = grouped.to_numpy(dtype=float)
    group_count = len(grouped)
    if group_count == 0:
        return None
    sampled = rng.integers(0, group_count, size=(iterations, group_count))
    sums = values[sampled].sum(axis=1)
    slopes = np.divide(
        sums[:, 0],
        sums[:, 1],
        out=np.full(iterations, np.nan, dtype=float),
        where=sums[:, 1] > 0.0,
    )
    deltas = np.divide(
        sums[:, 2],
        sums[:, 3],
        out=np.full(iterations, np.nan, dtype=float),
        where=sums[:, 3] > 0.0,
    )
    slopes = slopes[np.isfinite(slopes)]
    deltas = deltas[np.isfinite(deltas)]
    return {
        "iterations": int(iterations),
        "events": int(group_count),
        "slope_origin_ci_95": [float(value) for value in np.percentile(slopes, [2.5, 97.5])],
        "prob_slope_le_zero": float(np.mean(slopes <= 0.0)),
        "prob_slope_ge_one": float(np.mean(slopes >= 1.0)),
        "delta_log_loss_ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
        "prob_delta_le_zero": float(np.mean(deltas <= 0.0)),
    }


def market_null(df: pd.DataFrame, policy_col: str, observed: dict, iterations: int, rng) -> dict | None:
    if df.empty or iterations <= 0:
        return None
    y, market, candidate, adjustment, _, _ = metric_arrays(df, policy_col)
    denominator = float(np.sum(adjustment * adjustment))
    if denominator <= 0.0:
        return None
    simulated_y = (rng.random((iterations, len(df))) < market).astype(float)
    simulated_realized = simulated_y - market[None, :]
    slopes = simulated_realized @ adjustment / denominator
    market_loss = binary_loss(simulated_y, market[None, :])
    candidate_loss = binary_loss(simulated_y, candidate[None, :])
    deltas = np.mean(market_loss - candidate_loss, axis=1)
    obs_slope = observed.get("slope_origin")
    obs_delta = observed.get("delta_log_loss")
    return {
        "iterations": int(iterations),
        "slope_origin_null_mean": float(np.mean(slopes)),
        "slope_origin_null_ci_95": [float(value) for value in np.percentile(slopes, [2.5, 97.5])],
        "p_slope_observed_or_better": None
        if obs_slope is None
        else float((np.sum(slopes >= obs_slope) + 1) / (iterations + 1)),
        "delta_log_loss_null_mean": float(np.mean(deltas)),
        "delta_log_loss_null_ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
        "p_delta_observed_or_better": None
        if obs_delta is None
        else float((np.sum(deltas >= obs_delta) + 1) / (iterations + 1)),
        "prob_null_delta_positive": float(np.mean(deltas > 0.0)),
    }


def signed_buckets(df: pd.DataFrame, policy_col: str) -> list[dict]:
    work = df.copy()
    y, market, candidate, adjustment, realized, loss_delta = metric_arrays(work, policy_col)
    work["adjustment"] = adjustment
    work["realized_market_residual"] = realized
    work["candidate_gap"] = y - candidate
    work["loss_delta"] = loss_delta
    bins = [-np.inf, -0.05, -0.02, 0.02, 0.05, np.inf]
    labels = ["<= -5%", "-5% to -2%", "-2% to +2%", "+2% to +5%", ">= +5%"]
    work["bucket"] = pd.cut(work["adjustment"], bins=bins, labels=labels)
    rows = []
    for bucket, subset in work.groupby("bucket", observed=True):
        rows.append(
            {
                "bucket": str(bucket),
                "fights": int(len(subset)),
                "events": int(subset["event_date"].nunique()),
                "mean_adjustment": float(subset["adjustment"].mean()),
                "realized_market_residual": float(subset["realized_market_residual"].mean()),
                "actual_minus_candidate": float(subset["candidate_gap"].mean()),
                "delta_log_loss": float(subset["loss_delta"].mean()),
                "positive_folds": int(
                    sum(group["loss_delta"].mean() > 0.0 for _, group in subset.groupby("fold"))
                ),
                "folds": int(subset["fold"].nunique()),
            }
        )
    return rows


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    df = pd.read_csv(args.predictions, parse_dates=["event_date"])
    policy_summaries = []
    period_summaries = []
    bucket_tables = {}
    for policy_name, policy_col in POLICIES:
        aggregate = summarize_rows(df, policy_name, policy_col)
        aggregate["event_bootstrap"] = event_bootstrap(
            df,
            policy_col,
            args.bootstrap_iterations,
            rng,
        )
        aggregate["market_null"] = market_null(
            df,
            policy_col,
            aggregate,
            args.market_null_iterations,
            rng,
        )
        policy_summaries.append(aggregate)

        for period_name, period_label, frame in period_frames(df):
            row = summarize_rows(frame, policy_name, policy_col)
            row["period"] = period_name
            row["period_label"] = period_label
            period_summaries.append(row)

        bucket_tables[policy_name] = signed_buckets(df, policy_col)

    return {
        "predictions": args.predictions,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "policies": [{"name": name, "column": column} for name, column in POLICIES],
        "policy_summaries": policy_summaries,
        "period_summaries": period_summaries,
        "signed_buckets": bucket_tables,
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Reliability Audit",
        "",
        "This audit tests the residual alpha claim directly. It compares each",
        "candidate probability adjustment (`candidate - market`) against the",
        "realized market residual (`outcome - market`). A slope near `1` means",
        "the adjustment size was calibrated; a slope near `0` means the residual",
        "direction carried little realized market-error information.",
        "",
        "## Aggregate Reliability",
        "",
        "| Policy | Fights | Mean Adj | Realized Market Residual | Slope Origin | Slope 95% CI | P(slope<=0) | Market-Null p(slope) | Delta LL | Bootstrap P(delta<=0) | Market-Null p(delta) |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in result["policy_summaries"]:
        boot = row.get("event_bootstrap") or {}
        null = row.get("market_null") or {}
        slope_ci = boot.get("slope_origin_ci_95") or [None, None]
        lines.append(
            "| {policy} | {fights} | {adj} | {realized} | {slope} | {lo} to {hi} | {p_slope} | {null_slope} | {delta} | {p_delta_boot} | {null_delta} |".format(
                policy=row["policy"],
                fights=row["fights"],
                adj=fmt_pct(row.get("mean_adjustment")),
                realized=fmt_pct(row.get("mean_realized_market_residual")),
                slope=fmt_float(row.get("slope_origin")),
                lo=fmt_float(slope_ci[0]),
                hi=fmt_float(slope_ci[1]),
                p_slope=fmt_p(boot.get("prob_slope_le_zero")),
                null_slope=fmt_p(null.get("p_slope_observed_or_better")),
                delta=fmt_float(row.get("delta_log_loss")),
                p_delta_boot=fmt_p(boot.get("prob_delta_le_zero")),
                null_delta=fmt_p(null.get("p_delta_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Selected-Shrinkage Period Reliability",
            "",
            "| Period | Fights | Mean Adj | Realized Market Residual | Slope Origin | Delta LL | Directional Hit >=2pp |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["period_summaries"]:
        if row["policy"] != "selected_shrinkage":
            continue
        lines.append(
            "| {period} | {fights} | {adj} | {realized} | {slope} | {delta} | {hit} |".format(
                period=row["period_label"],
                fights=row["fights"],
                adj=fmt_pct(row.get("mean_adjustment")),
                realized=fmt_pct(row.get("mean_realized_market_residual")),
                slope=fmt_float(row.get("slope_origin")),
                delta=fmt_float(row.get("delta_log_loss")),
                hit=fmt_pct(row.get("directional_hit_abs_ge_2pp")),
            )
        )

    lines.extend(
        [
            "",
            "## Selected-Shrinkage Signed Buckets",
            "",
            "| Adjustment Bucket | Fights | Mean Adj | Realized Market Residual | Actual - Candidate | Delta LL | Positive Folds |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["signed_buckets"]["selected_shrinkage"]:
        lines.append(
            "| {bucket} | {fights} | {adj} | {realized} | {gap} | {delta} | {pos} / {folds} |".format(
                bucket=row["bucket"],
                fights=row["fights"],
                adj=fmt_pct(row["mean_adjustment"]),
                realized=fmt_pct(row["realized_market_residual"]),
                gap=fmt_pct(row["actual_minus_candidate"]),
                delta=fmt_float(row["delta_log_loss"]),
                pos=row["positive_folds"],
                folds=row["folds"],
            )
        )

    selected = next(row for row in result["policy_summaries"] if row["policy"] == "selected_shrinkage")
    latest = next(
        row
        for row in result["period_summaries"]
        if row["policy"] == "selected_shrinkage" and row["period"] == "latest_fold"
    )
    recent = next(
        row
        for row in result["period_summaries"]
        if row["policy"] == "selected_shrinkage" and row["period"] == "2025_2026"
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Aggregate selected-shrinkage slope is `{fmt_float(selected['slope_origin'])}`, which looks calibrated in full sample, with Delta LL `{fmt_float(selected['delta_log_loss'])}`.",
            f"- That aggregate masks drift: selected-shrinkage slope falls to `{fmt_float(recent['slope_origin'])}` in 2025-2026 and `{fmt_float(latest['slope_origin'])}` in the latest fold.",
            "- The residual remains a weak historical signal, but recent reliability is not strong enough for a live edge claim.",
            "- A future transform should be judged on forward reliability slope and recent Delta LL, not just aggregate log-loss gain.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_reliability_audit.json"
    md_path = output_dir / "residual_reliability_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
