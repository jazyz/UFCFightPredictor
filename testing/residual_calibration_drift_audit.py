#!/usr/bin/env python3
"""Calibration and drift diagnostics for residual probability policies.

The recent-stress audits show the residual edge decayed in 2025-2026. This
diagnostic asks whether that happened because the residual adjustment stopped
aligning with realized market residuals, or because calibration drift made the
same adjustment too aggressive.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
EPS = 1e-6

POLICY_COLUMNS = (
    ("selected_shrinkage", "selected_probability"),
    ("fixed_half_residual", "fixed_half_probability"),
    ("unshrunk_meta", "unshrunk_probability"),
)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit residual probability calibration drift")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--output-dir", default="test_results/residual_calibration_drift_audit")
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def logit(probability) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def binary_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def brier(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probability, dtype=float)
    return (p - y) ** 2


def calibration_ece(y_true, probability, bins=8) -> float | None:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probability, dtype=float)
    mask = np.isfinite(y) & np.isfinite(p)
    y = y[mask]
    p = p[mask]
    if len(y) == 0:
        return None
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for index in range(bins):
        lo = edges[index]
        hi = edges[index + 1]
        if index == bins - 1:
            in_bin = (p >= lo) & (p <= hi)
        else:
            in_bin = (p >= lo) & (p < hi)
        count = int(in_bin.sum())
        if count:
            ece += (count / len(y)) * abs(float(y[in_bin].mean()) - float(p[in_bin].mean()))
    return float(ece)


def period_masks(df: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    return [
        ("aggregate", "aggregate", np.ones(len(df), dtype=bool)),
        ("2024", "calendar 2024", (df["event_date"].dt.year == 2024).to_numpy()),
        ("2025", "calendar 2025", (df["event_date"].dt.year == 2025).to_numpy()),
        ("2026", "calendar 2026", (df["event_date"].dt.year == 2026).to_numpy()),
        ("post_2024", "2025-2026 only", (df["event_date"].dt.year >= 2025).to_numpy()),
        ("last_365d", "last 365 days", (df["event_date"] >= pd.Timestamp("2025-06-28")).to_numpy()),
        ("latest_fold", f"latest fold {int(df['fold'].max())}", (df["fold"] == df["fold"].max()).to_numpy()),
    ]


def summarize_policy_period(df: pd.DataFrame, mask: np.ndarray, policy_name: str, policy_col: str) -> dict:
    subset = df[mask].copy()
    if subset.empty:
        return {
            "policy": policy_name,
            "fights": 0,
            "events": 0,
            "market_log_loss": None,
            "policy_log_loss": None,
            "delta_log_loss": None,
            "market_brier": None,
            "policy_brier": None,
            "delta_brier": None,
            "actual_rate": None,
            "mean_market_probability": None,
            "mean_policy_probability": None,
            "mean_probability_adjustment": None,
            "mean_realized_market_residual": None,
            "mean_policy_calibration_gap": None,
            "market_ece": None,
            "policy_ece": None,
        }

    y = subset["red_won"].astype(float).to_numpy()
    market = subset["market_probability"].astype(float).to_numpy()
    policy = subset[policy_col].astype(float).to_numpy()
    market_loss = binary_loss(y, market)
    policy_loss = binary_loss(y, policy)
    market_brier = brier(y, market)
    policy_brier = brier(y, policy)
    return {
        "policy": policy_name,
        "fights": int(len(subset)),
        "events": int(subset["event_date"].nunique()),
        "market_log_loss": float(market_loss.mean()),
        "policy_log_loss": float(policy_loss.mean()),
        "delta_log_loss": float(market_loss.mean() - policy_loss.mean()),
        "market_brier": float(market_brier.mean()),
        "policy_brier": float(policy_brier.mean()),
        "delta_brier": float(market_brier.mean() - policy_brier.mean()),
        "actual_rate": float(y.mean()),
        "mean_market_probability": float(market.mean()),
        "mean_policy_probability": float(policy.mean()),
        "mean_probability_adjustment": float((policy - market).mean()),
        "mean_abs_probability_adjustment": float(np.abs(policy - market).mean()),
        "mean_realized_market_residual": float((y - market).mean()),
        "mean_policy_calibration_gap": float((y - policy).mean()),
        "market_ece": calibration_ece(y, market),
        "policy_ece": calibration_ece(y, policy),
    }


def summarize_adjustment_direction(df: pd.DataFrame, mask: np.ndarray, policy_col: str) -> list[dict]:
    subset = df[mask].copy()
    if subset.empty:
        return []
    y = subset["red_won"].astype(float).to_numpy()
    market = subset["market_probability"].astype(float).to_numpy()
    policy = subset[policy_col].astype(float).to_numpy()
    adjustment = policy - market
    realized = y - market
    subset = subset.assign(
        adjustment=adjustment,
        realized_market_residual=realized,
        direction=np.where(adjustment >= 0.0, "meta_up_on_red", "meta_down_on_red"),
        directional_hit=np.where(adjustment >= 0.0, realized > 0.0, realized < 0.0),
        delta_loss=binary_loss(y, market) - binary_loss(y, policy),
    )
    rows = []
    for direction, group in subset.groupby("direction", sort=True):
        rows.append(
            {
                "direction": str(direction),
                "fights": int(len(group)),
                "events": int(group["event_date"].nunique()),
                "mean_adjustment": float(group["adjustment"].mean()),
                "mean_abs_adjustment": float(group["adjustment"].abs().mean()),
                "mean_realized_market_residual": float(group["realized_market_residual"].mean()),
                "directional_hit_rate": float(group["directional_hit"].mean()),
                "delta_log_loss": float(group["delta_loss"].mean()),
            }
        )
    return rows


def residual_coefficients(df: pd.DataFrame, mask: np.ndarray, policy_col: str) -> dict:
    subset = df[mask].copy()
    if len(subset) < 60:
        return {
            "fights": int(len(subset)),
            "market_logit_coef": None,
            "adjustment_logit_coef": None,
            "intercept": None,
            "note": "fewer than 60 fights",
        }
    y = subset["red_won"].astype(int).to_numpy()
    if len(np.unique(y)) < 2:
        return {
            "fights": int(len(subset)),
            "market_logit_coef": None,
            "adjustment_logit_coef": None,
            "intercept": None,
            "note": "one class",
        }
    market_logit = logit(subset["market_probability"].astype(float).to_numpy())
    adjustment_logit = logit(subset[policy_col].astype(float).to_numpy()) - market_logit
    x = np.column_stack([market_logit, adjustment_logit])
    model = LogisticRegression(C=1000.0, penalty="l2", solver="lbfgs", max_iter=1000)
    model.fit(x, y)
    return {
        "fights": int(len(subset)),
        "market_logit_coef": float(model.coef_[0][0]),
        "adjustment_logit_coef": float(model.coef_[0][1]),
        "intercept": float(model.intercept_[0]),
        "note": "diagnostic in-sample coefficient",
    }


def audit(args) -> dict:
    df = pd.read_csv(args.predictions, parse_dates=["event_date"])
    periods = period_masks(df)
    summaries = []
    direction_rows = []
    coefficient_rows = []
    for period_name, period_label, mask in periods:
        for policy_name, policy_col in POLICY_COLUMNS:
            summary = summarize_policy_period(df, mask, policy_name, policy_col)
            summary["period"] = period_name
            summary["period_label"] = period_label
            summaries.append(summary)
        selected_col = "selected_probability"
        for row in summarize_adjustment_direction(df, mask, selected_col):
            row["period"] = period_name
            row["period_label"] = period_label
            row["policy"] = "selected_shrinkage"
            direction_rows.append(row)
        coef = residual_coefficients(df, mask, selected_col)
        coef["period"] = period_name
        coef["period_label"] = period_label
        coef["policy"] = "selected_shrinkage"
        coefficient_rows.append(coef)

    return {
        "predictions_path": args.predictions,
        "policies": [{"name": name, "column": column} for name, column in POLICY_COLUMNS],
        "period_summaries": summaries,
        "selected_shrinkage_direction_summaries": direction_rows,
        "selected_shrinkage_residual_coefficients": coefficient_rows,
    }


def find_summary(result: dict, period: str, policy: str) -> dict:
    for row in result["period_summaries"]:
        if row["period"] == period and row["policy"] == policy:
            return row
    raise KeyError((period, policy))


def selected_period_table(result: dict) -> list[str]:
    lines = [
        "| Period | Fights | Actual | Market P | Selected P | Adj | Realized Residual | Policy Gap | Market LL | Selected LL | Delta LL | Market ECE | Selected ECE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    order = ["aggregate", "2024", "2025", "2026", "post_2024", "last_365d", "latest_fold"]
    for period in order:
        row = find_summary(result, period, "selected_shrinkage")
        lines.append(
            "| {period} | {fights} | {actual} | {market_p} | {policy_p} | {adj} | {realized} | {gap} | {market_ll} | {policy_ll} | {delta} | {market_ece} | {policy_ece} |".format(
                period=row["period_label"],
                fights=row["fights"],
                actual=fmt_pct(row["actual_rate"]),
                market_p=fmt_pct(row["mean_market_probability"]),
                policy_p=fmt_pct(row["mean_policy_probability"]),
                adj=fmt_pct(row["mean_probability_adjustment"]),
                realized=fmt_pct(row["mean_realized_market_residual"]),
                gap=fmt_pct(row["mean_policy_calibration_gap"]),
                market_ll=fmt_float(row["market_log_loss"]),
                policy_ll=fmt_float(row["policy_log_loss"]),
                delta=fmt_float(row["delta_log_loss"]),
                market_ece=fmt_pct(row["market_ece"]),
                policy_ece=fmt_pct(row["policy_ece"]),
            )
        )
    return lines


def policy_comparison_table(result: dict) -> list[str]:
    lines = [
        "| Period | Policy | Fights | Delta LL | Delta Brier | Mean Adj | Policy ECE |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    order = ["aggregate", "2025", "2026", "last_365d", "latest_fold"]
    for period in order:
        for policy, _ in POLICY_COLUMNS:
            row = find_summary(result, period, policy)
            lines.append(
                "| {period} | {policy} | {fights} | {delta_ll} | {delta_brier} | {adj} | {ece} |".format(
                    period=row["period_label"],
                    policy=policy,
                    fights=row["fights"],
                    delta_ll=fmt_float(row["delta_log_loss"]),
                    delta_brier=fmt_float(row["delta_brier"]),
                    adj=fmt_pct(row["mean_probability_adjustment"]),
                    ece=fmt_pct(row["policy_ece"]),
                )
            )
    return lines


def direction_table(result: dict) -> list[str]:
    lines = [
        "| Period | Direction | Fights | Mean Adj | Realized Residual | Directional Hit | Delta LL |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    keep_periods = {"aggregate", "2024", "2025", "2026", "last_365d", "latest_fold"}
    rows = [
        row
        for row in result["selected_shrinkage_direction_summaries"]
        if row["period"] in keep_periods
    ]
    rows = sorted(rows, key=lambda row: (row["period"], row["direction"]))
    label_by_period = {
        "aggregate": "aggregate",
        "2024": "calendar 2024",
        "2025": "calendar 2025",
        "2026": "calendar 2026",
        "last_365d": "last 365 days",
        "latest_fold": next(
            row["period_label"]
            for row in result["selected_shrinkage_direction_summaries"]
            if row["period"] == "latest_fold"
        ),
    }
    order = ["aggregate", "2024", "2025", "2026", "last_365d", "latest_fold"]
    rows = sorted(rows, key=lambda row: (order.index(row["period"]), row["direction"]))
    for row in rows:
        lines.append(
            "| {period} | {direction} | {fights} | {adj} | {realized} | {hit} | {delta} |".format(
                period=label_by_period[row["period"]],
                direction=row["direction"],
                fights=row["fights"],
                adj=fmt_pct(row["mean_adjustment"]),
                realized=fmt_pct(row["mean_realized_market_residual"]),
                hit=fmt_pct(row["directional_hit_rate"]),
                delta=fmt_float(row["delta_log_loss"]),
            )
        )
    return lines


def coefficient_table(result: dict) -> list[str]:
    lines = [
        "| Period | Fights | Market Logit Coef | Residual Adjustment Coef | Intercept |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    order = ["aggregate", "2024", "2025", "2026", "post_2024", "last_365d", "latest_fold"]
    rows = sorted(
        result["selected_shrinkage_residual_coefficients"],
        key=lambda row: order.index(row["period"]),
    )
    for row in rows:
        lines.append(
            "| {period} | {fights} | {market_coef} | {resid_coef} | {intercept} |".format(
                period=row["period_label"],
                fights=row["fights"],
                market_coef=fmt_float(row["market_logit_coef"]),
                resid_coef=fmt_float(row["adjustment_logit_coef"]),
                intercept=fmt_float(row["intercept"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Calibration Drift Audit",
        "",
        "This diagnostic asks why the residual edge decayed recently. It compares",
        "market probabilities against selected-shrinkage, fixed-half, and unshrunk",
        "residual probabilities by period, then checks whether selected-shrinkage",
        "adjustments still align with realized market residuals.",
        "",
        "## Input",
        "",
        f"- predictions: `{result['predictions_path']}`",
        "",
        "## Selected-Shrinkage Calibration By Period",
        "",
        *selected_period_table(result),
        "",
        "## Policy Comparison",
        "",
        *policy_comparison_table(result),
        "",
        "## Adjustment Direction",
        "",
        *direction_table(result),
        "",
        "## In-Sample Residual Coefficient Diagnostic",
        "",
        "Each row fits `outcome ~ market_logit + selected_residual_logit_adjustment`",
        "inside the same period. This is diagnostic only, not a validation test.",
        "",
        *coefficient_table(result),
        "",
        "## Interpretation",
        "",
        "- The selected residual adjustment is positive on average in every period, but realized market residuals turn negative in 2026 and the latest fold.",
        "- In 2026, the market already overestimates red-side outcomes on this aligned sample; the residual layer nudges probabilities further upward on average, worsening calibration and log loss.",
        "- The residual adjustment direction is not reliably informative recently: latest-fold upward adjustments have negative realized residuals and negative log-loss contribution.",
        "- This points to residual/model drift rather than a simple staking-threshold problem. Future work should require fresh post-freeze evidence or a genuinely pre-registered drift-aware transform.",
        "",
    ]
    return "\n".join(lines)


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_calibration_drift_audit.json"
    md_path = output_dir / "residual_calibration_drift_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    latest = find_summary(result, "latest_fold", "selected_shrinkage")
    print(
        "Latest selected-shrinkage delta LL {delta:.4f}, mean adjustment {adj:+.2%}, realized residual {realized:+.2%}".format(
            delta=latest["delta_log_loss"],
            adj=latest["mean_probability_adjustment"],
            realized=latest["mean_realized_market_residual"],
        )
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
