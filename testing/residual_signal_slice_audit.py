#!/usr/bin/env python3
"""Slice diagnostics for the residual market/meta signal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


EPS = 1e-12


def parse_args():
    parser = argparse.ArgumentParser(description="Audit residual meta signal slices")
    parser.add_argument(
        "--predictions",
        default="test_results/market_residual_meta_audit/holdout_meta_predictions.csv",
        help="holdout meta predictions CSV from market_residual_meta_audit.py",
    )
    parser.add_argument("--variant", default="market_plus_regularized_lgbm")
    parser.add_argument(
        "--bets",
        default="test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv",
        help="fixed residual-meta paper-policy selected bets CSV",
    )
    parser.add_argument("--output-dir", default="test_results/residual_signal_slice_audit")
    return parser.parse_args()


def loss_delta(y_true, market_probability, meta_probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    market = np.clip(np.asarray(market_probability, dtype=float), EPS, 1.0 - EPS)
    meta = np.clip(np.asarray(meta_probability, dtype=float), EPS, 1.0 - EPS)
    market_loss = -(y * np.log(market) + (1.0 - y) * np.log(1.0 - market))
    meta_loss = -(y * np.log(meta) + (1.0 - y) * np.log(1.0 - meta))
    return market_loss - meta_loss


def brier_delta(y_true, market_probability, meta_probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    market = np.asarray(market_probability, dtype=float)
    meta = np.asarray(meta_probability, dtype=float)
    return (market - y) ** 2 - (meta - y) ** 2


def bin_series(series: pd.Series, bins: list[float], labels: list[str] | None = None) -> pd.Series:
    if labels is None:
        labels = [f"{left:.2f}-{right:.2f}" for left, right in zip(bins[:-1], bins[1:])]
    return pd.cut(series.astype(float), bins=bins, labels=labels, include_lowest=True, right=False)


def title_group(title: str) -> str:
    text = str(title)
    if "Women" in text:
        return "women"
    if "Heavyweight" in text or "Light Heavyweight" in text:
        return "heavy_or_lhw"
    if "Middleweight" in text or "Welterweight" in text:
        return "middle_or_welter"
    if "Lightweight" in text or "Featherweight" in text:
        return "light_or_feather"
    if "Bantamweight" in text or "Flyweight" in text:
        return "bantam_or_fly"
    if "Catch" in text or "Open" in text:
        return "catch_or_open"
    return "other"


def summarize_prediction_slice(df: pd.DataFrame, group_column: str) -> list[dict]:
    rows = []
    for group, subset in df.groupby(group_column, dropna=False, observed=False, sort=True):
        if subset.empty:
            continue
        rows.append(
            {
                "slice": str(group),
                "fights": int(len(subset)),
                "market_log_loss": float(subset["market_loss"].mean()),
                "meta_log_loss": float(subset["meta_loss"].mean()),
                "market_minus_meta_log_loss": float(subset["loss_delta"].mean()),
                "market_minus_meta_brier": float(subset["brier_delta"].mean()),
                "mean_market_probability": float(subset["market_probability"].mean()),
                "mean_meta_probability": float(subset["meta_probability"].mean()),
                "actual_rate": float(subset["red_won"].astype(float).mean()),
                "share_of_total_delta": float(subset["loss_delta"].sum() / df["loss_delta"].sum())
                if abs(df["loss_delta"].sum()) > EPS
                else None,
            }
        )
    return rows


def summarize_bet_slice(df: pd.DataFrame, group_column: str) -> list[dict]:
    rows = []
    for group, subset in df.groupby(group_column, dropna=False, observed=False, sort=True):
        if subset.empty:
            continue
        profit = subset["flat_profit"].astype(float)
        market = subset["selected_market_probability"].astype(float)
        actual = subset["selected_won"].astype(float)
        rows.append(
            {
                "slice": str(group),
                "bets": int(len(subset)),
                "profit": float(profit.sum()),
                "roi": float(profit.mean()),
                "actual_win_rate": float(actual.mean()),
                "mean_market_probability": float(market.mean()),
                "actual_minus_market": float(actual.mean() - market.mean()),
                "mean_edge": float(subset["selected_edge"].astype(float).mean()),
                "events": int(subset["event_date"].nunique()),
            }
        )
    return rows


def prepare_predictions(path: str, variant: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["variant"] == variant].copy()
    if df.empty:
        raise SystemExit(f"No rows found for variant {variant!r} in {path}")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["year"] = df["event_date"].dt.year.astype(str)
    df["red_edge"] = df["meta_probability"].astype(float) - df["market_probability"].astype(float)
    df["abs_edge"] = df["red_edge"].abs()
    y = df["red_won"].astype(float)
    market = np.clip(df["market_probability"].astype(float), EPS, 1.0 - EPS)
    meta = np.clip(df["meta_probability"].astype(float), EPS, 1.0 - EPS)
    df["market_loss"] = -(y * np.log(market) + (1.0 - y) * np.log(1.0 - market))
    df["meta_loss"] = -(y * np.log(meta) + (1.0 - y) * np.log(1.0 - meta))
    df["loss_delta"] = loss_delta(y, market, meta)
    df["brier_delta"] = brier_delta(y, market, meta)
    df["market_bin"] = bin_series(
        df["market_probability"],
        [0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.000001],
        ["<0.40", "0.40-0.50", "0.50-0.60", "0.60-0.70", "0.70-0.80", ">=0.80"],
    )
    df["abs_edge_bin"] = bin_series(
        df["abs_edge"],
        [0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 1.000001],
        ["<0.01", "0.01-0.02", "0.02-0.03", "0.03-0.05", "0.05-0.08", ">=0.08"],
    )
    df["edge_direction"] = np.where(df["red_edge"] >= 0.0, "meta_up_on_red", "meta_down_on_red")
    df["market_side"] = np.where(df["market_probability"] >= 0.5, "red_market_favorite", "red_market_underdog")
    df["title_group"] = df["title"].map(title_group)
    return df


def prepare_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        raise SystemExit(f"No selected bets found in {path}")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["year"] = df["event_date"].dt.year.astype(str)
    df["market_bin"] = bin_series(
        df["selected_market_probability"],
        [0.0, 0.5, 0.6, 0.7, 0.8, 1.000001],
        ["<0.50", "0.50-0.60", "0.60-0.70", "0.70-0.80", ">=0.80"],
    )
    df["edge_bin"] = bin_series(
        df["selected_edge"],
        [0.0, 0.02, 0.03, 0.05, 0.08, 1.000001],
        ["<0.02", "0.02-0.03", "0.03-0.05", "0.05-0.08", ">=0.08"],
    )
    df["probability_bin"] = bin_series(
        df["selected_probability"],
        [0.0, 0.6, 0.65, 0.7, 0.8, 1.000001],
        ["<0.60", "0.60-0.65", "0.65-0.70", "0.70-0.80", ">=0.80"],
    )
    df["odds_side"] = np.where(df["selected_odds"].astype(float) < 0.0, "favorite", "underdog")
    df["title_group"] = df["title"].map(title_group)
    return df


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.2%}"


def prediction_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Slice | Fights | Market LL | Meta LL | Delta LL | Actual | Market P | Meta P |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {slice} | {fights} | {market_ll} | {meta_ll} | {delta} | {actual} | {market_p} | {meta_p} |".format(
                slice=row["slice"],
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                meta_ll=fmt_float(row["meta_log_loss"]),
                delta=fmt_float(row["market_minus_meta_log_loss"]),
                actual=fmt_pct(row["actual_rate"]),
                market_p=fmt_pct(row["mean_market_probability"]),
                meta_p=fmt_pct(row["mean_meta_probability"]),
            )
        )
    return lines


def bet_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Slice | Bets | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {slice} | {bets} | {profit} | {roi} | {actual} | {market_p} | {edge_actual} | {mean_edge} |".format(
                slice=row["slice"],
                bets=row["bets"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual=fmt_pct(row["actual_win_rate"]),
                market_p=fmt_pct(row["mean_market_probability"]),
                edge_actual=fmt_pct(row["actual_minus_market"]),
                mean_edge=fmt_pct(row["mean_edge"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    prediction = result["prediction"]
    betting = result["betting"]
    lines = [
        "# Residual Signal Slice Audit",
        "",
        f"Prediction variant: `{result['variant']}`",
        f"Prediction file: `{result['prediction_path']}`",
        f"Bet file: `{result['bet_path']}`",
        "",
        "## Prediction Signal",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| fights | {prediction['aggregate']['fights']} |",
        f"| market log loss | {fmt_float(prediction['aggregate']['market_log_loss'])} |",
        f"| meta log loss | {fmt_float(prediction['aggregate']['meta_log_loss'])} |",
        f"| market - meta log loss | {fmt_float(prediction['aggregate']['market_minus_meta_log_loss'])} |",
        "",
        "### By Market Probability",
        "",
        *prediction_table(prediction["by_market_bin"]),
        "",
        "### By Absolute Residual Edge",
        "",
        *prediction_table(prediction["by_abs_edge_bin"]),
        "",
        "### By Year",
        "",
        *prediction_table(prediction["by_year"]),
        "",
        "### By Title Group",
        "",
        *prediction_table(prediction["by_title_group"]),
        "",
        "## Fixed Paper-Policy Bets",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| bets | {betting['aggregate']['bets']} |",
        f"| profit | {fmt_units(betting['aggregate']['profit'])} |",
        f"| ROI | {fmt_pct(betting['aggregate']['roi'])} |",
        f"| actual - market | {fmt_pct(betting['aggregate']['actual_minus_market'])} |",
        "",
        "### Bets By Market Probability",
        "",
        *bet_table(betting["by_market_bin"]),
        "",
        "### Bets By Residual Edge",
        "",
        *bet_table(betting["by_edge_bin"]),
        "",
        "### Bets By Odds Side",
        "",
        *bet_table(betting["by_odds_side"]),
        "",
        "### Bets By Year",
        "",
        *bet_table(betting["by_year"]),
        "",
        "## Interpretation",
        "",
        "This audit is diagnostic only. It identifies where the residual signal",
        "has historically appeared, and where the fixed paper policy was fragile.",
        "It should not be used to tune the frozen paper policy after the fact.",
        "",
    ]
    return "\n".join(lines)


def main():
    args = parse_args()
    predictions = prepare_predictions(args.predictions, args.variant)
    bets = prepare_bets(args.bets)

    prediction_aggregate = {
        "fights": int(len(predictions)),
        "market_log_loss": float(predictions["market_loss"].mean()),
        "meta_log_loss": float(predictions["meta_loss"].mean()),
        "market_minus_meta_log_loss": float(predictions["loss_delta"].mean()),
        "market_minus_meta_brier": float(predictions["brier_delta"].mean()),
    }
    betting_aggregate = {
        "bets": int(len(bets)),
        "profit": float(bets["flat_profit"].astype(float).sum()),
        "roi": float(bets["flat_profit"].astype(float).mean()),
        "actual_win_rate": float(bets["selected_won"].astype(float).mean()),
        "mean_market_probability": float(bets["selected_market_probability"].astype(float).mean()),
        "actual_minus_market": float(
            bets["selected_won"].astype(float).mean()
            - bets["selected_market_probability"].astype(float).mean()
        ),
    }

    result = {
        "variant": args.variant,
        "prediction_path": args.predictions,
        "bet_path": args.bets,
        "prediction": {
            "aggregate": prediction_aggregate,
            "by_market_bin": summarize_prediction_slice(predictions, "market_bin"),
            "by_abs_edge_bin": summarize_prediction_slice(predictions, "abs_edge_bin"),
            "by_edge_direction": summarize_prediction_slice(predictions, "edge_direction"),
            "by_market_side": summarize_prediction_slice(predictions, "market_side"),
            "by_year": summarize_prediction_slice(predictions, "year"),
            "by_title_group": summarize_prediction_slice(predictions, "title_group"),
        },
        "betting": {
            "aggregate": betting_aggregate,
            "by_market_bin": summarize_bet_slice(bets, "market_bin"),
            "by_edge_bin": summarize_bet_slice(bets, "edge_bin"),
            "by_probability_bin": summarize_bet_slice(bets, "probability_bin"),
            "by_odds_side": summarize_bet_slice(bets, "odds_side"),
            "by_year": summarize_bet_slice(bets, "year"),
            "by_title_group": summarize_bet_slice(bets, "title_group"),
        },
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_signal_slice_audit.json"
    md_path = output_dir / "residual_signal_slice_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    print(f"Prediction delta LL: {prediction_aggregate['market_minus_meta_log_loss']:.4f}")
    print(f"Fixed policy profit: {fmt_units(betting_aggregate['profit'])}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
