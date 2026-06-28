#!/usr/bin/env python3
"""Dev/holdout audit for blending model probabilities with market prices."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import implied_prob, parse_odds
from utils.name_matching import canonical_name


EPS = 1e-6


def logit(probability):
    clipped = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return np.log(clipped / (1.0 - clipped))


def sigmoid(value):
    return 1.0 / (1.0 + np.exp(-value))


def blend_probabilities(model_probability, market_probability, weight, mode):
    if mode == "linear":
        blended = weight * model_probability + (1.0 - weight) * market_probability
    elif mode == "logit":
        blended = sigmoid(
            weight * logit(model_probability)
            + (1.0 - weight) * logit(market_probability)
        )
    else:
        raise ValueError(f"unknown blend mode: {mode}")
    return np.clip(blended, EPS, 1.0 - EPS)


def load_comparable_rows(path):
    df = pd.read_csv(path)
    rows = []

    for _, row in df.iterrows():
        event_date = pd.to_datetime(row["event_date"], errors="coerce")
        red = canonical_name(row.get("red_fighter", ""))
        winner = canonical_name(row.get("winner_name", ""))
        fighter1 = canonical_name(row.get("odds_fighter1_name", ""))
        fighter2 = canonical_name(row.get("odds_fighter2_name", ""))

        odds1 = parse_odds(row.get("fighter1_odds"))
        odds2 = parse_odds(row.get("fighter2_odds"))
        raw1 = implied_prob(odds1)
        raw2 = implied_prob(odds2)
        if not np.isfinite(raw1) or not np.isfinite(raw2) or raw1 + raw2 <= 0:
            continue

        market1 = raw1 / (raw1 + raw2)
        market2 = raw2 / (raw1 + raw2)
        if red == fighter1:
            market = market1
        elif red == fighter2:
            market = market2
        else:
            continue

        rows.append(
            {
                "event_date": event_date,
                "y_true": winner == red,
                "model_probability": float(row["red_win_probability"]),
                "market_probability": float(market),
            }
        )

    return pd.DataFrame(rows).dropna()


def score_probabilities(y_true, probability):
    y = np.asarray(y_true, dtype=bool)
    p = np.asarray(probability, dtype=float)
    return {
        "fights": int(len(y)),
        "accuracy": float(accuracy_score(y, p >= 0.5)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)),
    }


def window_scores(df, start_date, end_date, mode, weight):
    window = df[
        (df["event_date"] >= pd.Timestamp(start_date))
        & (df["event_date"] <= pd.Timestamp(end_date))
    ].copy()
    if window.empty:
        raise ValueError(f"no comparable rows in window {start_date} to {end_date}")

    blended = blend_probabilities(
        window["model_probability"],
        window["market_probability"],
        weight,
        mode,
    )
    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "model": score_probabilities(window["y_true"], window["model_probability"]),
        "market": score_probabilities(window["y_true"], window["market_probability"]),
        "blend": score_probabilities(window["y_true"], blended),
    }


def candidate_weights(min_weight, max_weight, step):
    count = int(math.floor((max_weight - min_weight) / step)) + 1
    for index in range(count + 1):
        value = min_weight + index * step
        if value <= max_weight + EPS:
            yield round(value, 10)


def select_weight(df, start_date, end_date, mode, weights):
    window = df[
        (df["event_date"] >= pd.Timestamp(start_date))
        & (df["event_date"] <= pd.Timestamp(end_date))
    ].copy()
    if window.empty:
        raise ValueError(f"no comparable rows in dev window {start_date} to {end_date}")

    best = None
    for weight in weights:
        blended = blend_probabilities(
            window["model_probability"],
            window["market_probability"],
            weight,
            mode,
        )
        loss = log_loss(window["y_true"], blended, labels=[0, 1])
        if best is None or loss < best["log_loss"]:
            best = {"weight": weight, "log_loss": float(loss)}
    return best


def markdown_report(result):
    selected = result["selected"]
    dev = result["dev"]
    holdout = result["holdout"]
    return "\n".join(
        [
            "# Market Blend Audit",
            "",
            f"Ledger: `{result['ledger']}`",
            f"Blend mode: `{selected['mode']}`",
            f"Dev-selected model weight: {selected['weight']:.3f}",
            "",
            "## Development",
            "",
            f"Model log loss: {dev['model']['log_loss']:.4f}",
            f"Market log loss: {dev['market']['log_loss']:.4f}",
            f"Blend log loss: {dev['blend']['log_loss']:.4f}",
            "",
            "## Holdout",
            "",
            f"Model log loss: {holdout['model']['log_loss']:.4f}",
            f"Market log loss: {holdout['market']['log_loss']:.4f}",
            f"Blend log loss: {holdout['blend']['log_loss']:.4f}",
            f"Blend accuracy: {holdout['blend']['accuracy']:.4f}",
            "",
        ]
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Audit market/model probability blending")
    parser.add_argument("ledger", help="no_leakage_backtest.csv ledger")
    parser.add_argument("--dev-start", default="2024-06-27")
    parser.add_argument("--dev-end", default="2025-06-26")
    parser.add_argument("--holdout-start", default="2025-06-27")
    parser.add_argument("--holdout-end", default="2026-06-27")
    parser.add_argument("--mode", choices=["linear", "logit"], default="logit")
    parser.add_argument("--min-weight", type=float, default=0.0)
    parser.add_argument("--max-weight", type=float, default=1.0)
    parser.add_argument("--step", type=float, default=0.025)
    parser.add_argument("--output-dir", default="test_results/market_blend_audit")
    return parser.parse_args()


def main():
    args = parse_args()
    df = load_comparable_rows(args.ledger)
    weights = list(candidate_weights(args.min_weight, args.max_weight, args.step))
    selected = select_weight(df, args.dev_start, args.dev_end, args.mode, weights)
    selected["mode"] = args.mode

    result = {
        "ledger": args.ledger,
        "selected": selected,
        "dev": window_scores(df, args.dev_start, args.dev_end, args.mode, selected["weight"]),
        "holdout": window_scores(
            df,
            args.holdout_start,
            args.holdout_end,
            args.mode,
            selected["weight"],
        ),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "market_blend_audit.json"
    md_path = output_dir / "market_blend_audit.md"
    with open(json_path, "w") as file:
        json.dump(result, file, indent=2)
    with open(md_path, "w") as file:
        file.write(markdown_report(result))

    print(f"Selected {args.mode} blend weight: {selected['weight']:.3f}")
    print(f"Dev blend log loss: {result['dev']['blend']['log_loss']:.4f}")
    print(f"Holdout market log loss: {result['holdout']['market']['log_loss']:.4f}")
    print(f"Holdout blend log loss: {result['holdout']['blend']['log_loss']:.4f}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
