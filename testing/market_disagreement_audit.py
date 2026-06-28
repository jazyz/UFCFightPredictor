#!/usr/bin/env python3
"""Audit whether model-vs-market disagreement pockets look stable.

This does not train or select a new model. It reads saved leak-safe ledgers and
asks whether sides where the model assigns more probability than the de-vigged
market actually win more often than the market implies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import implied_prob, net_odds, parse_odds  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


EPS = 1e-12
DEFAULT_EDGE_BINS = [-1.0, 0.0, 0.02, 0.05, 0.08, 0.12, 1.0]
DEFAULT_THRESHOLDS = [0.0, 0.02, 0.05, 0.08, 0.12]
DEFAULT_MIN_PROBABILITIES = [0.5, 0.55, 0.6, 0.65]


def parse_args():
    parser = argparse.ArgumentParser(description="Audit model-vs-market disagreement")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="model label and no_leakage_backtest.csv path",
    )
    parser.add_argument("--output-dir", default="test_results/market_disagreement_audit")
    parser.add_argument(
        "--edge-bin",
        action="append",
        type=float,
        help="custom bin edge; repeat in ascending order",
    )
    parser.add_argument(
        "--threshold",
        action="append",
        type=float,
        help="custom minimum edge threshold; repeat as needed",
    )
    parser.add_argument(
        "--min-probability",
        action="append",
        type=float,
        help="custom minimum selected model probability; repeat as needed",
    )
    return parser.parse_args()


def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def load_ledger(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    rows = []
    for _, row in df.iterrows():
        event_date = pd.to_datetime(row.get("event_date"), errors="coerce")
        winner = canonical_name(row.get("winner_name", ""))
        fighter1 = canonical_name(row.get("odds_fighter1_name", ""))
        fighter2 = canonical_name(row.get("odds_fighter2_name", ""))
        red = canonical_name(row.get("red_fighter", ""))

        odds1 = parse_odds(row.get("fighter1_odds"))
        odds2 = parse_odds(row.get("fighter2_odds"))
        raw1 = implied_prob(odds1)
        raw2 = implied_prob(odds2)
        overround = raw1 + raw2 if np.isfinite(raw1) and np.isfinite(raw2) else np.nan
        if not np.isfinite(overround) or overround <= 0:
            continue

        market1 = raw1 / overround
        market2 = raw2 / overround
        model1 = safe_float(row.get("fighter1_win_probability"))
        model2 = safe_float(row.get("fighter2_win_probability"))
        if not np.isfinite(model1) or not np.isfinite(model2):
            continue

        red_model = safe_float(row.get("red_win_probability"))
        red_market = np.nan
        if red == fighter1:
            red_market = market1
        elif red == fighter2:
            red_market = market2

        sides = [
            {
                "side": 1,
                "fighter": row.get("odds_fighter1_name", ""),
                "fighter_key": fighter1,
                "odds": odds1,
                "model_probability": model1,
                "market_probability": market1,
                "won": winner == fighter1,
            },
            {
                "side": 2,
                "fighter": row.get("odds_fighter2_name", ""),
                "fighter_key": fighter2,
                "odds": odds2,
                "model_probability": model2,
                "market_probability": market2,
                "won": winner == fighter2,
            },
        ]
        for side in sides:
            side["edge"] = side["model_probability"] - side["market_probability"]

        selected = max(sides, key=lambda item: item["edge"])
        rows.append(
            {
                "model_label": label,
                "event_date": event_date,
                "period": event_date.to_period("Y").year if pd.notna(event_date) else None,
                "red_model_probability": red_model,
                "red_market_probability": red_market,
                "red_won": winner == red,
                "selected_side": selected["side"],
                "selected_fighter": selected["fighter"],
                "selected_odds": selected["odds"],
                "selected_model_probability": selected["model_probability"],
                "selected_market_probability": selected["market_probability"],
                "selected_edge": selected["edge"],
                "selected_won": selected["won"],
                "flat_profit": flat_profit(selected["odds"], selected["won"]),
            }
        )

    return pd.DataFrame(rows)


def flat_profit(odds, won: bool) -> float:
    if odds is None or not np.isfinite(odds):
        return np.nan
    return net_odds(odds) if won else -1.0


def summarize_predictions(df: pd.DataFrame) -> dict:
    comparable = df.dropna(subset=["red_model_probability", "red_market_probability", "red_won"])
    if comparable.empty:
        return {}
    y = comparable["red_won"].astype(int).to_numpy()
    model = np.clip(comparable["red_model_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    market = np.clip(comparable["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    return {
        "fights": int(len(comparable)),
        "model_accuracy": float(accuracy_score(y, model >= 0.5)),
        "market_favorite_accuracy": float(accuracy_score(y, market >= 0.5)),
        "model_log_loss": float(log_loss(y, model, labels=[0, 1])),
        "market_log_loss": float(log_loss(y, market, labels=[0, 1])),
        "market_minus_model_log_loss": float(
            log_loss(y, market, labels=[0, 1]) - log_loss(y, model, labels=[0, 1])
        ),
    }


def bin_label(left: float, right: float) -> str:
    if left <= -1.0:
        return f"<= {right:.2f}"
    if right >= 1.0:
        return f"> {left:.2f}"
    return f"{left:.2f} to {right:.2f}"


def summarize_subset(subset: pd.DataFrame) -> dict:
    if subset.empty:
        return {
            "fights": 0,
            "mean_edge": None,
            "mean_model_probability": None,
            "mean_market_probability": None,
            "actual_win_rate": None,
            "actual_minus_market": None,
            "flat_profit_per_1u": 0.0,
            "flat_roi": None,
        }
    profit = subset["flat_profit"].astype(float)
    return {
        "fights": int(len(subset)),
        "mean_edge": float(subset["selected_edge"].astype(float).mean()),
        "mean_model_probability": float(subset["selected_model_probability"].astype(float).mean()),
        "mean_market_probability": float(subset["selected_market_probability"].astype(float).mean()),
        "actual_win_rate": float(subset["selected_won"].astype(float).mean()),
        "actual_minus_market": float(
            subset["selected_won"].astype(float).mean()
            - subset["selected_market_probability"].astype(float).mean()
        ),
        "flat_profit_per_1u": float(profit.sum()),
        "flat_roi": float(profit.mean()),
    }


def summarize_bins(df: pd.DataFrame, bins: list[float]) -> list[dict]:
    rows = []
    for left, right in zip(bins[:-1], bins[1:]):
        subset = df[(df["selected_edge"] > left) & (df["selected_edge"] <= right)]
        rows.append({"edge_bin": bin_label(left, right), **summarize_subset(subset)})
    return rows


def summarize_thresholds(df: pd.DataFrame, thresholds: list[float]) -> list[dict]:
    return [
        {"min_edge": threshold, **summarize_subset(df[df["selected_edge"] >= threshold])}
        for threshold in thresholds
    ]


def summarize_periods(df: pd.DataFrame, thresholds: list[float]) -> list[dict]:
    rows = []
    for threshold in thresholds:
        subset = df[df["selected_edge"] >= threshold]
        for period, period_df in subset.groupby("period", sort=True):
            if pd.isna(period):
                continue
            rows.append(
                {
                    "min_edge": threshold,
                    "period": str(int(period)),
                    **summarize_subset(period_df),
                }
            )
    return rows


def summarize_probability_edge_thresholds(
    df: pd.DataFrame,
    thresholds: list[float],
    min_probabilities: list[float],
) -> list[dict]:
    rows = []
    for min_probability in min_probabilities:
        for threshold in thresholds:
            subset = df[
                (df["selected_edge"] >= threshold)
                & (df["selected_model_probability"] >= min_probability)
            ]
            rows.append(
                {
                    "min_probability": min_probability,
                    "min_edge": threshold,
                    **summarize_subset(subset),
                }
            )
    return rows


def summarize_probability_edge_periods(
    df: pd.DataFrame,
    thresholds: list[float],
    min_probability: float,
) -> list[dict]:
    rows = []
    for threshold in thresholds:
        subset = df[
            (df["selected_edge"] >= threshold)
            & (df["selected_model_probability"] >= min_probability)
        ]
        for period, period_df in subset.groupby("period", sort=True):
            if pd.isna(period):
                continue
            rows.append(
                {
                    "min_probability": min_probability,
                    "min_edge": threshold,
                    "period": str(int(period)),
                    **summarize_subset(period_df),
                }
            )
    return rows


def markdown_report(result: dict) -> str:
    lines = [
        "# Market Disagreement Audit",
        "",
        "This audit asks whether the side with the largest model edge over the",
        "de-vigged market actually outperforms market-implied probability.",
        "",
        "## Prediction Summary",
        "",
        "| Model | Fights | Model Acc | Market Acc | Model LL | Market LL | Market - Model LL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in result["models"]:
        pred = item["prediction_summary"]
        lines.append(
            "| {label} | {fights} | {model_acc:.2%} | {market_acc:.2%} | {model_ll:.4f} | {market_ll:.4f} | {edge:.4f} |".format(
                label=item["label"],
                fights=pred.get("fights", 0),
                model_acc=pred.get("model_accuracy", float("nan")),
                market_acc=pred.get("market_favorite_accuracy", float("nan")),
                model_ll=pred.get("model_log_loss", float("nan")),
                market_ll=pred.get("market_log_loss", float("nan")),
                edge=pred.get("market_minus_model_log_loss", float("nan")),
            )
        )

    lines.extend(["", "## Edge Thresholds", ""])
    for item in result["models"]:
        lines.extend(
            [
                f"### {item['label']}",
                "",
                "| Min Edge | Fights | Actual Win | Market P | Actual - Market | Flat Profit | Flat ROI |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in item["threshold_summary"]:
            lines.append(
                "| {edge:.2f} | {fights} | {actual} | {market} | {gap} | {profit:.2f} | {roi} |".format(
                    edge=row["min_edge"],
                    fights=row["fights"],
                    actual=fmt_pct(row["actual_win_rate"]),
                    market=fmt_pct(row["mean_market_probability"]),
                    gap=fmt_pct(row["actual_minus_market"]),
                    profit=row["flat_profit_per_1u"],
                    roi=fmt_pct(row["flat_roi"]),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Edge + Probability Floors",
            "",
            "These slices require the selected side to clear both a model edge",
            "threshold and a minimum model probability. They are closer to the",
            "frozen policy shape than edge-only slices.",
            "",
        ]
    )
    for item in result["models"]:
        lines.extend(
            [
                f"### {item['label']}",
                "",
                "| Min P | Min Edge | Fights | Actual Win | Market P | Actual - Market | Flat Profit | Flat ROI |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in item["probability_edge_summary"]:
            lines.append(
                "| {minp:.2f} | {edge:.2f} | {fights} | {actual} | {market} | {gap} | {profit:.2f} | {roi} |".format(
                    minp=row["min_probability"],
                    edge=row["min_edge"],
                    fights=row["fights"],
                    actual=fmt_pct(row["actual_win_rate"]),
                    market=fmt_pct(row["mean_market_probability"]),
                    gap=fmt_pct(row["actual_minus_market"]),
                    profit=row["flat_profit_per_1u"],
                    roi=fmt_pct(row["flat_roi"]),
                )
            )
        lines.append("")

    period_edge = 0.08 if 0.08 in result["thresholds"] else result["thresholds"][0]
    lines.extend(
        [
            "## Period Stability at Min P 0.60",
            "",
            f"These rows hold the minimum model probability at `0.60` and show the `min_edge = {period_edge:.2f}` slice by calendar year.",
            "",
        ]
    )
    for item in result["models"]:
        lines.extend(
            [
                f"### {item['label']}",
                "",
                "| Year | Fights | Actual Win | Market P | Actual - Market | Flat Profit | Flat ROI |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        rows = [
            row
            for row in item["probability_edge_period_summary"]
            if abs(row["min_edge"] - period_edge) < EPS
        ]
        for row in rows:
            lines.append(
                "| {period} | {fights} | {actual} | {market} | {gap} | {profit:.2f} | {roi} |".format(
                    period=row["period"],
                    fights=row["fights"],
                    actual=fmt_pct(row["actual_win_rate"]),
                    market=fmt_pct(row["mean_market_probability"]),
                    gap=fmt_pct(row["actual_minus_market"]),
                    profit=row["flat_profit_per_1u"],
                    roi=fmt_pct(row["flat_roi"]),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Decision Note",
            "",
            "A positive threshold row is useful only if it is stable across time and",
            "does not rely on post-hoc threshold picking. This audit is diagnostic;",
            "it does not replace the frozen forward paper-tracking policy.",
            "",
        ]
    )
    return "\n".join(lines)


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:.2%}"


def main():
    args = parse_args()
    bins = args.edge_bin or DEFAULT_EDGE_BINS
    thresholds = args.threshold or DEFAULT_THRESHOLDS
    min_probabilities = args.min_probability or DEFAULT_MIN_PROBABILITIES
    if sorted(bins) != bins:
        raise SystemExit("--edge-bin values must be in ascending order")

    output = {
        "edge_bins": bins,
        "thresholds": thresholds,
        "min_probabilities": min_probabilities,
        "ledgers": [{"label": label, "csv_path": path} for label, path in args.ledger],
        "models": [],
    }
    for label, path in args.ledger:
        df = load_ledger(Path(path), label)
        output["models"].append(
            {
                "label": label,
                "csv_path": path,
                "prediction_summary": summarize_predictions(df),
                "bin_summary": summarize_bins(df, bins),
                "threshold_summary": summarize_thresholds(df, thresholds),
                "period_threshold_summary": summarize_periods(df, thresholds),
                "probability_edge_summary": summarize_probability_edge_thresholds(
                    df,
                    thresholds,
                    min_probabilities,
                ),
                "probability_edge_period_summary": summarize_probability_edge_periods(
                    df,
                    thresholds,
                    min_probability=0.6,
                ),
            }
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "market_disagreement_audit.json"
    md_path = output_dir / "market_disagreement_audit.md"
    with json_path.open("w") as file:
        json.dump(output, file, indent=2)
    md_path.write_text(markdown_report(output))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
