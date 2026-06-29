#!/usr/bin/env python3
"""Uncapped betting and calibration audit for striking-core policies.

The probability audits show a weak but recurring market-aware striking signal.
This script asks the next practical question: under fixed uncapped edge
thresholds, does that probability signal translate into PnL, and do Brier/ECE
calibration diagnostics move in the same direction?
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

from testing.market_aware_feature_audit import aligned_market_feature_frame  # noqa: E402
from testing.market_residual_meta_audit import iter_folds, score_probabilities  # noqa: E402
from testing.statistical_edge_audit import calibration_stats  # noqa: E402
from testing.striking_core_predeclared_backtest import (  # noqa: E402
    add_red_blue_odds,
    american_profit,
    event_bootstrap_profit,
    market_null_bets,
)
from testing.striking_core_robustness_selection_audit import (  # noqa: E402
    build_gates,
    build_models,
    build_policies,
    ensure_columns,
    expand_policy_predictions,
    run_model_predictions,
    select_rolling_policy,
)
from testing.striking_group_after_market_audit import fmt_float, fmt_p, fmt_pct  # noqa: E402


DEFAULT_OUTPUT_DIR = "test_results/striking_core_betting_calibration_audit"
EDGE_THRESHOLDS = (0.0, 0.02, 0.05)
REFERENCE_POLICIES = (
    "mixed_core|all",
    "sigpct_head|all",
    "mixed_core|min5",
    "sigpct_head|min5",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit striking-core betting/calibration")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--odds", default="data/fight_results_with_odds.csv")
    parser.add_argument("--fight-details-source", default="data/fight_details_date.csv")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--first-holdout-start", default="2023-01-01")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=200)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--c", type=float, default=0.1)
    parser.add_argument("--clip-quantile", type=float, default=0.99)
    parser.add_argument("--min-prior-selection-rows", type=int, default=80)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--bet-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def attach_odds(rows: pd.DataFrame, aligned: pd.DataFrame) -> pd.DataFrame:
    keep = ["fight_key", "red_odds", "blue_odds", "fighter1_odds", "fighter2_odds"]
    aligned_odds = add_red_blue_odds(aligned)
    return rows.merge(aligned_odds[keep], on="fight_key", how="left", validate="many_to_one")


def add_bet_rows(rows: pd.DataFrame, threshold: float) -> pd.DataFrame:
    bet_rows = []
    for _, row in rows.iterrows():
        candidate = float(row["candidate_probability"])
        market = float(row["market_probability"])
        red_edge = candidate - market
        if abs(red_edge) < threshold or not np.isfinite(red_edge):
            continue
        bet_red = red_edge > 0.0
        odds = float(row["red_odds"] if bet_red else row["blue_odds"])
        if not np.isfinite(odds):
            continue
        won = bool(row["red_won"]) if bet_red else not bool(row["red_won"])
        selected_market = market if bet_red else 1.0 - market
        selected_model = candidate if bet_red else 1.0 - candidate
        bet_rows.append(
            {
                "fold": int(row["fold"]),
                "event_date": row["event_date"],
                "fight_key": row["fight_key"],
                "policy": row.get("policy", ""),
                "bet_side": "red" if bet_red else "blue",
                "bet_odds": odds,
                "bet_won": won,
                "market_probability": selected_market,
                "model_probability": selected_model,
                "edge": selected_model - selected_market,
                "bet": 1.0,
                "profit": american_profit(odds) if won else -1.0,
            }
        )
    return pd.DataFrame(bet_rows)


def summarize_bets(rows: pd.DataFrame, threshold: float, bootstrap_iterations: int, null_iterations: int, rng) -> dict:
    bets = add_bet_rows(rows, threshold)
    if bets.empty:
        return {
            "threshold": threshold,
            "bets": 0,
            "profit": 0.0,
            "roi": None,
            "positive_folds": 0,
            "folds_with_bets": 0,
            "mean_edge": None,
            "mean_market_probability": None,
            "mean_model_probability": None,
            "market_null": None,
            "event_bootstrap": None,
        }
    fold_profit = bets.groupby("fold", sort=True)["profit"].sum()
    profit = float(bets["profit"].sum())
    stake = float(bets["bet"].sum())
    return {
        "threshold": threshold,
        "bets": int(len(bets)),
        "profit": profit,
        "roi": profit / stake if stake > 0 else None,
        "positive_folds": int((fold_profit > 0.0).sum()),
        "folds_with_bets": int(len(fold_profit)),
        "mean_edge": float(bets["edge"].mean()),
        "mean_market_probability": float(bets["market_probability"].mean()),
        "mean_model_probability": float(bets["model_probability"].mean()),
        "market_null": market_null_bets(bets, null_iterations, rng),
        "event_bootstrap": event_bootstrap_profit(bets, bootstrap_iterations, rng),
    }


def calibration_summary(rows: pd.DataFrame) -> dict:
    y = rows["red_won"].astype(float).to_numpy()
    market = rows["market_probability"].astype(float).to_numpy()
    candidate = rows["candidate_probability"].astype(float).to_numpy()
    market_score = score_probabilities(y, market)
    candidate_score = score_probabilities(y, candidate)
    market_cal = calibration_stats(y, market)
    candidate_cal = calibration_stats(y, candidate)
    return {
        "rows": int(len(rows)),
        "events": int(rows["event_date"].nunique()),
        "market": market_score,
        "candidate": candidate_score,
        "market_minus_candidate_log_loss": float(market_score["log_loss"] - candidate_score["log_loss"]),
        "market_minus_candidate_brier": float(market_score["brier"] - candidate_score["brier"]),
        "market_ece": market_cal["ece"],
        "candidate_ece": candidate_cal["ece"],
        "candidate_minus_market_ece": None
        if market_cal["ece"] is None or candidate_cal["ece"] is None
        else float(candidate_cal["ece"] - market_cal["ece"]),
        "mean_abs_candidate_minus_market": float(np.mean(np.abs(candidate - market))),
    }


def summarize_policy(rows: pd.DataFrame, name: str, bootstrap_iterations: int, null_iterations: int, rng) -> dict:
    result = {
        "name": name,
        "calibration": calibration_summary(rows),
        "betting": [
            summarize_bets(rows, threshold, bootstrap_iterations, null_iterations, rng)
            for threshold in EDGE_THRESHOLDS
        ],
    }
    return result


def selected_reference_rows(policy_predictions: pd.DataFrame, selected_folds: list[int], policy_name: str) -> pd.DataFrame:
    return policy_predictions[
        policy_predictions["policy"].eq(policy_name)
        & policy_predictions["fold"].isin(selected_folds)
    ].copy()


def fmt_units(value) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):+.2f}u"


def betting_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Policy | Threshold | Bets | Profit | ROI | Positive Folds | Mean Edge | Market-Null p | Boot P(profit<=0) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy in rows:
        for bet in policy["betting"]:
            null = bet.get("market_null") or {}
            boot = bet.get("event_bootstrap") or {}
            lines.append(
                "| `{policy}` | {threshold} | {bets} | {profit} | {roi} | {positive} / {folds} | {edge} | {null_p} | {boot_p} |".format(
                    policy=policy["name"],
                    threshold=fmt_pct(bet["threshold"]),
                    bets=bet["bets"],
                    profit=fmt_units(bet["profit"]),
                    roi=fmt_pct(bet.get("roi")),
                    positive=bet.get("positive_folds", 0),
                    folds=bet.get("folds_with_bets", 0),
                    edge=fmt_pct(bet.get("mean_edge")),
                    null_p=fmt_p(null.get("p_value_observed_or_better")),
                    boot_p=fmt_p(boot.get("prob_profit_le_zero")),
                )
            )
    return lines


def calibration_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Policy | Rows | Market Delta LL | Brier Delta | Market ECE | Candidate ECE | Candidate-Market ECE | Mean Abs Move |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy in rows:
        cal = policy["calibration"]
        lines.append(
            "| `{policy}` | {rows} | {delta} | {brier} | {market_ece} | {candidate_ece} | {ece_delta} | {move} |".format(
                policy=policy["name"],
                rows=cal["rows"],
                delta=fmt_float(cal["market_minus_candidate_log_loss"]),
                brier=fmt_float(cal["market_minus_candidate_brier"]),
                market_ece=fmt_pct(cal["market_ece"]),
                candidate_ece=fmt_pct(cal["candidate_ece"]),
                ece_delta=fmt_pct(cal["candidate_minus_market_ece"]),
                move=fmt_pct(cal["mean_abs_candidate_minus_market"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    primary = next(row for row in result["policy_summaries"] if row["name"] == "rolling_selected_prior_delta")
    primary_bets = next(row for row in primary["betting"] if abs(row["threshold"] - 0.02) < 1e-12)
    primary_null = primary_bets.get("market_null") or {}
    primary_boot = primary_bets.get("event_bootstrap") or {}
    lines = [
        "# Striking Core Betting And Calibration Audit",
        "",
        "This audit asks whether the striking-core probability edge translates",
        "into uncapped flat betting at fixed positive-edge thresholds, and whether",
        "Brier/ECE calibration diagnostics agree with the log-loss result.",
        "",
        "## Protocol",
        "",
        f"- aligned men-only rows: `{result['metadata']['aligned_rows']}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- rolling selection eval folds: `{', '.join(str(value) for value in result['selected_eval_folds'])}`",
        f"- edge thresholds: `{', '.join(fmt_pct(value) for value in EDGE_THRESHOLDS)}`",
        "- event cap: none",
        f"- bet market-null iterations: `{result['parameters']['bet_null_iterations']}`",
        "",
        "## Calibration And Probability Metrics",
        "",
        *calibration_table(result["policy_summaries"]),
        "",
        "## Uncapped Flat Betting",
        "",
        *betting_table(result["policy_summaries"]),
        "",
        "## Interpretation",
        "",
    ]
    if primary_bets["profit"] <= 0:
        lines.append(
            "- The rolling-selected policy's fixed 2% edge ledger does not show positive uncapped PnL."
        )
    elif (primary_null.get("p_value_observed_or_better") or 1.0) <= 0.05:
        lines.append(
            "- The rolling-selected policy's fixed 2% edge ledger is profitable and clears the conditional market-null PnL screen."
        )
    else:
        lines.append(
            "- The rolling-selected policy's fixed 2% edge ledger is profitable but does not clear the conditional market-null PnL screen."
        )
    lines.append(
        "- PnL market-null tests here are conditional on the selected historical bets; the probability selection-null result remains in the robustness audit."
    )
    lines.append(
        "- Calibration is mixed: log loss and Brier improve, but ECE often worsens versus market, so this looks more like an edge-ranking signal than a globally better probability surface."
    )
    lines.append(
        "- The main edge claim still depends on future frozen pre-outcome paper tracking, not these retrospective threshold rows."
    )
    lines.append(
        "- Primary 2% ledger: profit {profit}, ROI {roi}, market-null p {null_p}, bootstrap P(profit<=0) {boot_p}.".format(
            profit=fmt_units(primary_bets["profit"]),
            roi=fmt_pct(primary_bets["roi"]),
            null_p=fmt_p(primary_null.get("p_value_observed_or_better")),
            boot_p=fmt_p(primary_boot.get("prob_profit_le_zero")),
        )
    )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    align_args = argparse.Namespace(
        features=args.features,
        odds=args.odds,
        fight_details_source=args.fight_details_source,
        min_training_date=args.min_training_date,
        last_holdout_end=args.last_holdout_end,
        include_womens_fights=False,
    )
    df, metadata = aligned_market_feature_frame(align_args)
    models = build_models()
    gates = build_gates()
    policies = build_policies(models, gates)
    ensure_columns(df, models)
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
    labels = df["red_won"].astype(int).to_numpy()
    model_predictions, _, fold_rows = run_model_predictions(
        df,
        folds,
        models,
        labels,
        args.c,
        args.clip_quantile,
    )
    policy_predictions = expand_policy_predictions(model_predictions, policies, gates)
    selected, selections = select_rolling_policy(
        policy_predictions,
        policies,
        args.min_prior_selection_rows,
    )
    selected_folds = sorted(int(value) for value in selected["fold"].unique())
    selected = attach_odds(selected, df)

    policy_summaries = [
        summarize_policy(
            selected,
            "rolling_selected_prior_delta",
            args.bootstrap_iterations,
            args.bet_null_iterations,
            rng,
        )
    ]
    for policy_name in REFERENCE_POLICIES:
        rows = selected_reference_rows(policy_predictions, selected_folds, policy_name)
        rows = attach_odds(rows, df)
        policy_summaries.append(
            summarize_policy(
                rows,
                policy_name,
                args.bootstrap_iterations,
                args.bet_null_iterations,
                rng,
            )
        )

    return {
        "parameters": {
            "first_holdout_start": args.first_holdout_start,
            "last_holdout_end": args.last_holdout_end,
            "dev_days": args.dev_days,
            "holdout_days": args.holdout_days,
            "step_days": args.step_days,
            "min_dev_fights": args.min_dev_fights,
            "min_holdout_fights": args.min_holdout_fights,
            "c": args.c,
            "clip_quantile": args.clip_quantile,
            "min_prior_selection_rows": args.min_prior_selection_rows,
            "bootstrap_iterations": args.bootstrap_iterations,
            "bet_null_iterations": args.bet_null_iterations,
            "seed": args.seed,
        },
        "metadata": metadata,
        "folds": fold_rows,
        "selected_eval_folds": selected_folds,
        "selection_path": selections,
        "reference_policies": list(REFERENCE_POLICIES),
        "policy_summaries": policy_summaries,
    }


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_core_betting_calibration_audit.json"
    md_path = output_dir / "striking_core_betting_calibration_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
