#!/usr/bin/env python3
"""Fixed betting-policy audit for residual-shrinkage probabilities.

This translates the out-of-sample residual-shrinkage probabilities into the
already frozen residual-meta paper thresholds. It deliberately avoids selecting
new betting thresholds from these holdout outcomes.
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

from testing.residual_meta_pnl_audit import (  # noqa: E402
    MetaBetPolicy,
    evaluate_policy,
    event_bootstrap,
    load_ledger_rows,
    net_odds_array,
)


PROBABILITY_POLICIES = {
    "selected_shrinkage": "selected_probability",
    "fixed_half_residual": "fixed_half_probability",
    "unshrunk_meta": "unshrunk_probability",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Fixed PnL audit for residual-shrinkage probabilities")
    parser.add_argument(
        "--predictions",
        default="test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv",
        help="holdout_shrinkage_predictions.csv from residual_shrinkage_audit.py",
    )
    parser.add_argument(
        "--ledger",
        default="test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv",
        help="source ledger with odds and settlement fields",
    )
    parser.add_argument("--ledger-label", default="regularized_lgbm")
    parser.add_argument("--min-edge", type=float, default=0.02)
    parser.add_argument("--min-probability", type=float, default=0.60)
    parser.add_argument("--max-underdog-odds", type=float, default=300.0)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_shrinkage_fixed_pnl_audit")
    return parser.parse_args()


def load_predictions(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"fight_key", "event_date", "red_won", *PROBABILITY_POLICIES.values()}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing prediction columns: {sorted(missing)}")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    return df.dropna(subset=["event_date"]).copy()


def merge_predictions_with_ledger(predictions: pd.DataFrame, ledger_path: str, ledger_label: str) -> pd.DataFrame:
    ledger = load_ledger_rows(Path(ledger_path), ledger_label)
    odds_columns = [
        "fight_key",
        "red_market_probability",
        "blue_market_probability",
        "red_odds",
        "blue_odds",
    ]
    merged = predictions.merge(ledger[odds_columns], on="fight_key", how="inner", validate="one_to_one")
    if len(merged) != len(predictions):
        missing = len(predictions) - len(merged)
        raise SystemExit(f"Could not match {missing} shrinkage prediction rows to ledger odds")
    return merged.sort_values(["event_date", "fight_key"]).reset_index(drop=True)


def market_null_fixed_bets(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty or iterations <= 0:
        return None
    market = bets["selected_market_probability"].astype(float).to_numpy()
    odds = bets["selected_odds"].astype(float).to_numpy()
    net = net_odds_array(odds)
    simulated = rng.random((iterations, len(bets))) < market
    profits = np.where(simulated, net, -1.0).sum(axis=1)
    observed_profit = float(bets["flat_profit"].astype(float).sum())
    return {
        "iterations": int(iterations),
        "observed_profit": observed_profit,
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed_profit) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0.0)),
    }


def fold_summaries(bets: pd.DataFrame) -> list[dict]:
    if bets.empty:
        return []
    rows = []
    for fold, subset in bets.groupby("fold", sort=True):
        rows.append(
            {
                "fold": int(fold),
                "bets": int(len(subset)),
                "profit": float(subset["flat_profit"].astype(float).sum()),
                "roi": float(subset["flat_profit"].astype(float).mean()),
                "events": int(subset["event_date"].nunique()),
            }
        )
    return rows


def aggregate_summary(predictions: pd.DataFrame, bets: pd.DataFrame, bootstrap: dict | None, market_null: dict | None) -> dict:
    if bets.empty:
        return {
            "fights": int(len(predictions)),
            "bets": 0,
            "events_with_bets": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_probability": None,
            "mean_market_probability": None,
            "mean_edge": None,
            "actual_minus_market": None,
            "positive_folds": 0,
            "folds_with_bets": 0,
            "folds": fold_summaries(bets),
            "event_bootstrap": bootstrap,
            "market_null": market_null,
        }
    actual = float(bets["selected_won"].astype(float).mean())
    mean_market = float(bets["selected_market_probability"].astype(float).mean())
    folds = fold_summaries(bets)
    return {
        "fights": int(len(predictions)),
        "bets": int(len(bets)),
        "events_with_bets": int(bets["event_date"].nunique()),
        "profit": float(bets["flat_profit"].astype(float).sum()),
        "roi": float(bets["flat_profit"].astype(float).mean()),
        "actual_win_rate": actual,
        "mean_probability": float(bets["selected_probability"].astype(float).mean()),
        "mean_market_probability": mean_market,
        "mean_edge": float(bets["selected_edge"].astype(float).mean()),
        "actual_minus_market": actual - mean_market,
        "positive_folds": int(sum(row["profit"] > 0 for row in folds)),
        "folds_with_bets": int(len(folds)),
        "folds": folds,
        "event_bootstrap": bootstrap,
        "market_null": market_null,
    }


def run_policy(
    merged: pd.DataFrame,
    policy_name: str,
    probability_column: str,
    fixed_policy: MetaBetPolicy,
    iterations: int,
    market_null_iterations: int,
    rng,
) -> tuple[pd.DataFrame, dict]:
    predictions = merged.copy()
    predictions["meta_red_probability"] = predictions[probability_column].astype(float)
    bets, _ = evaluate_policy(predictions, fixed_policy)
    if not bets.empty:
        bets.insert(0, "probability_policy", policy_name)
        if "fold" in predictions.columns:
            bets = bets.merge(
                predictions[["fight_key", "fold"]],
                on="fight_key",
                how="left",
                validate="one_to_one",
            )
        else:
            bets["fold"] = np.nan
    bootstrap = event_bootstrap(bets, iterations, rng)
    market_null = market_null_fixed_bets(bets, market_null_iterations, rng)
    return bets, aggregate_summary(predictions, bets, bootstrap, market_null)


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.2%}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.3f}"


def markdown_report(result: dict) -> str:
    policy = result["fixed_policy"]
    lines = [
        "# Residual Shrinkage Fixed PnL Audit",
        "",
        "This audit applies the already frozen residual-meta paper thresholds to",
        "the out-of-sample residual-shrinkage probabilities. It does not select",
        "new thresholds from these holdout outcomes.",
        "",
        "## Inputs",
        "",
        f"- shrinkage predictions: `{result['predictions_path']}`",
        f"- odds ledger: `{result['ledger_path']}`",
        f"- fights matched: `{result['fights']}`",
        "",
        "## Fixed Betting Rule",
        "",
        "| Rule | Value |",
        "| --- | ---: |",
        f"| minimum residual edge | {policy['min_edge']:.2%} |",
        f"| minimum probability | {policy['min_probability']:.2%} |",
        f"| max underdog odds | +{policy['max_underdog_odds']:.0f} |",
        f"| stake | 1u flat |",
        "",
        "## Results",
        "",
        "| Probability Policy | Bets | Profit | ROI | Actual - Market | Positive Folds | Bootstrap P(profit <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in result["policies"].items():
        bootstrap = summary.get("event_bootstrap") or {}
        market_null = summary.get("market_null") or {}
        lines.append(
            "| {name} | {bets} | {profit} | {roi} | {actual_market} | {positive} / {folds} | {boot} | {null_p} |".format(
                name=name,
                bets=summary["bets"],
                profit=fmt_units(summary["profit"]),
                roi=fmt_pct(summary["roi"]),
                actual_market=fmt_pct(summary["actual_minus_market"]),
                positive=summary["positive_folds"],
                folds=summary["folds_with_bets"],
                boot=fmt_p(bootstrap.get("prob_profit_le_zero")),
                null_p=fmt_p(market_null.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Fold Results",
            "",
            "| Policy | Fold | Bets | Profit | ROI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, summary in result["policies"].items():
        for row in summary["folds"]:
            lines.append(
                "| {name} | {fold} | {bets} | {profit} | {roi} |".format(
                    name=name,
                    fold=row["fold"],
                    bets=row["bets"],
                    profit=fmt_units(row["profit"]),
                    roi=fmt_pct(row["roi"]),
                )
            )

    selected = result["policies"].get("selected_shrinkage", {})
    unshrunk = result["policies"].get("unshrunk_meta", {})
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a fixed-threshold translation test. It can show whether the",
            "probability improvement survives the existing paper-bet rule, but it",
            "does not replace future paper tracking.",
            "",
            f"Selected-shrinkage profit: `{fmt_units(selected.get('profit'))}`.",
            f"Unshrunk residual-meta profit: `{fmt_units(unshrunk.get('profit'))}`.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    predictions = load_predictions(args.predictions)
    merged = merge_predictions_with_ledger(predictions, args.ledger, args.ledger_label)
    fixed_policy = MetaBetPolicy(
        min_edge=args.min_edge,
        min_probability=args.min_probability,
        max_underdog_odds=args.max_underdog_odds,
    )

    policies = {}
    all_bets = []
    for policy_name, probability_column in PROBABILITY_POLICIES.items():
        bets, summary = run_policy(
            merged,
            policy_name,
            probability_column,
            fixed_policy,
            args.iterations,
            args.market_null_iterations,
            rng,
        )
        policies[policy_name] = summary
        if not bets.empty:
            all_bets.append(bets)

    result = {
        "predictions_path": args.predictions,
        "ledger_path": args.ledger,
        "fights": int(len(merged)),
        "seed": args.seed,
        "iterations": args.iterations,
        "market_null_iterations": args.market_null_iterations,
        "fixed_policy": {
            "min_edge": args.min_edge,
            "min_probability": args.min_probability,
            "max_underdog_odds": args.max_underdog_odds,
            "stake_units": 1.0,
        },
        "policies": policies,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_shrinkage_fixed_pnl_audit.json"
    md_path = output_dir / "residual_shrinkage_fixed_pnl_audit.md"
    summary_path = output_dir / "RESIDUAL_SHRINKAGE_FIXED_PNL_AUDIT_SUMMARY.md"
    bets_path = output_dir / "fixed_policy_bets.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    report = markdown_report(result)
    md_path.write_text(report)
    summary_path.write_text(report)
    if all_bets:
        pd.concat(all_bets, ignore_index=True).to_csv(bets_path, index=False)
    else:
        pd.DataFrame().to_csv(bets_path, index=False)

    selected = policies["selected_shrinkage"]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {bets_path}")
    print(f"Selected-shrinkage fixed-policy profit: {fmt_units(selected['profit'])}")


if __name__ == "__main__":
    main()
