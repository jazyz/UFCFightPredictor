#!/usr/bin/env python3
"""Freeze a market-residual probability transform for forward tracking."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_residual_meta_audit import (  # noqa: E402
    EPS,
    load_aligned_ledgers,
    score_probabilities,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze current market-residual meta transform")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="model label and no_leakage_backtest.csv path",
    )
    parser.add_argument(
        "--as-of-date",
        default=datetime.now().date().isoformat(),
        help="date the transform is frozen; training window ends the previous day",
    )
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--model-label", default="regularized_lgbm")
    parser.add_argument("--c", type=float, default=0.25)
    parser.add_argument("--source-audit", default="test_results/market_residual_meta_audit/MARKET_RESIDUAL_META_AUDIT_SUMMARY.md")
    parser.add_argument("--output-dir", default="test_results/frozen_market_residual_meta")
    return parser.parse_args()


def parse_iso_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"invalid YYYY-MM-DD date: {value}") from exc


def date_window(as_of_date: str, dev_days: int):
    as_of = parse_iso_date(as_of_date)
    dev_end = as_of - timedelta(days=1)
    dev_start = as_of - timedelta(days=dev_days)
    return pd.Timestamp(dev_start), pd.Timestamp(dev_end)


def fit_transform(df: pd.DataFrame, model_label: str, c_value: float) -> dict:
    feature_columns = ["market_logit", f"{model_label}_logit_delta"]
    missing = [column for column in feature_columns if column not in df.columns]
    if missing:
        raise SystemExit(f"missing required feature columns: {missing}")
    if df.empty:
        raise SystemExit("training window has no aligned fights")

    y = df["red_won"].astype(int).to_numpy()
    if len(np.unique(y)) < 2:
        raise SystemExit("training window labels contain fewer than two classes")

    x = df[feature_columns].astype(float).to_numpy()
    model = LogisticRegression(C=c_value, penalty="l2", solver="lbfgs", max_iter=1000)
    model.fit(x, y)
    meta_probability = np.clip(model.predict_proba(x)[:, 1], EPS, 1.0 - EPS)
    market_probability = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)

    return {
        "feature_columns": feature_columns,
        "intercept": float(model.intercept_[0]),
        "coefficients": {
            feature: float(value)
            for feature, value in zip(feature_columns, model.coef_[0])
        },
        "training_diagnostics": {
            "rows": int(len(df)),
            "actual_red_win_rate": float(y.mean()),
            "market": score_probabilities(y, market_probability),
            "frozen_meta": score_probabilities(y, meta_probability),
            "market_minus_meta_log_loss": float(
                score_probabilities(y, market_probability)["log_loss"]
                - score_probabilities(y, meta_probability)["log_loss"]
            ),
        },
    }


def markdown_report(result: dict) -> str:
    transform = result["transform"]
    diagnostics = transform["training_diagnostics"]
    coefficients = transform["coefficients"]
    formula_lines = [
        "market_logit = logit(de-vigged market probability)",
        f"{result['model_label']}_logit_delta = logit({result['model_label']} probability) - market_logit",
        "meta_logit = intercept + sum(coefficient_i * feature_i)",
        "meta_probability = sigmoid(meta_logit)",
    ]
    lines = [
        "# Frozen Market Residual Meta Transform",
        "",
        f"As-of date: `{result['as_of_date']}`",
        f"Training window: `{result['dev_start']}` to `{result['dev_end']}`",
        f"Base model residual: `{result['model_label']}`",
        f"Logistic L2 inverse regularization C: `{result['c']}`",
        f"Source audit: `{result['source_audit']}`",
        "",
        "This is a frozen forward probability-transform contract. It should be",
        "used only for future paper tracking until enough post-freeze outcomes",
        "accrue. Do not refit or alter this artifact after future outcomes are",
        "known.",
        "",
        "## Formula",
        "",
        "```text",
        *formula_lines,
        "```",
        "",
        "## Coefficients",
        "",
        "| Term | Value |",
        "| --- | ---: |",
        f"| intercept | {transform['intercept']:.8f} |",
    ]
    for feature, value in coefficients.items():
        lines.append(f"| `{feature}` | {value:.8f} |")

    lines.extend(
        [
            "",
            "## Training-Window Diagnostics",
            "",
            "These are fit diagnostics on the frozen training window, not fresh",
            "evidence of edge. The out-of-sample evidence is in the source audit.",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| rows | {diagnostics['rows']} |",
            f"| actual red win rate | {diagnostics['actual_red_win_rate']:.2%} |",
            f"| market log loss | {diagnostics['market']['log_loss']:.4f} |",
            f"| frozen meta log loss | {diagnostics['frozen_meta']['log_loss']:.4f} |",
            f"| market - meta log loss | {diagnostics['market_minus_meta_log_loss']:.4f} |",
            "",
            "## Frozen Rules",
            "",
            "- Use the exact feature columns, coefficients, intercept, and de-vigging convention above.",
            f"- Keep the base model label fixed to the saved `{result['model_label']}` probability stream unless a new pre-outcome freeze replaces this artifact.",
            "- Score future outcomes against market log loss, market-null simulations, and any predeclared PnL policy without changing this transform.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    df, labels = load_aligned_ledgers(args.ledger)
    if args.model_label not in labels:
        raise SystemExit(f"model label {args.model_label!r} not found in ledgers: {labels}")
    dev_start, dev_end = date_window(args.as_of_date, args.dev_days)
    train_df = df[(df["event_date"] >= dev_start) & (df["event_date"] <= dev_end)].copy()
    transform = fit_transform(train_df, args.model_label, args.c)
    result = {
        "as_of_date": args.as_of_date,
        "dev_start": dev_start.date().isoformat(),
        "dev_end": dev_end.date().isoformat(),
        "dev_days": args.dev_days,
        "model_label": args.model_label,
        "c": args.c,
        "source_audit": args.source_audit,
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in args.ledger],
        "transform": transform,
        "freeze_warning": (
            "This probability transform is frozen for forward paper tracking. "
            "Do not alter coefficients, feature columns, regularization, or "
            "training window before scoring future outcomes."
        ),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "frozen_market_residual_meta.json"
    md_path = output_dir / "frozen_market_residual_meta.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    diagnostics = transform["training_diagnostics"]
    print(f"Frozen residual meta transform as of {args.as_of_date}")
    print(f"Training window: {result['dev_start']} to {result['dev_end']}")
    print(f"Rows: {diagnostics['rows']}")
    print(f"Intercept: {transform['intercept']:.8f}")
    for feature, value in transform["coefficients"].items():
        print(f"{feature}: {value:.8f}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
