#!/usr/bin/env python3
"""Nested walk-forward model/strategy selection audit.

This script is stricter than a single development/holdout strategy search:
for each fold it selects the model and betting strategy using only the fold's
development window, then evaluates that frozen selection on the next holdout
window. The output is meant to answer whether model/strategy choices generalize
across time rather than just looking good on one chosen split.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.walk_forward_strategy_search import (  # noqa: E402
    HELPER_COLUMNS,
    STARTING_BANKROLL,
    add_derived_columns,
    load_ledger,
    rescore,
    selection_score,
    strategy_grid,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Nested walk-forward edge audit")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="model label and no_leakage_backtest.csv path",
    )
    parser.add_argument("--first-holdout-start", default="2023-01-01")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=365)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument(
        "--min-holdout-days",
        type=int,
        default=120,
        help="skip the final fold if the remaining holdout window is shorter than this",
    )
    parser.add_argument("--step-days", type=int, default=None)
    parser.add_argument("--min-dev-bets", type=int, default=35)
    parser.add_argument(
        "--selection-objective",
        choices=["profit", "roi"],
        default="profit",
        help="metric used to rank candidates inside each development window",
    )
    parser.add_argument(
        "--settlement-mode",
        choices=["event", "sequential"],
        default="event",
    )
    parser.add_argument(
        "--max-event-exposure-fraction",
        type=float,
        default=None,
        help="optional cap on total stake per event as a fraction of event-start bankroll",
    )
    parser.add_argument("--output-dir", default="test_results/nested_walk_forward_edge_audit")
    return parser.parse_args()


def objective_score(summary: dict, min_dev_bets: int, objective: str) -> tuple:
    if objective == "profit":
        return selection_score(summary, min_dev_bets)

    if summary["bets"] < min_dev_bets:
        return (-math.inf,)
    if summary["max_drawdown"] > 0.35:
        return (-math.inf,)
    roi = summary["roi_on_staked"] if summary["roi_on_staked"] is not None else -math.inf
    return (
        roi,
        summary["profit"],
        -summary["max_drawdown"],
        summary["bets"],
    )


def iter_folds(
    first_holdout_start,
    last_holdout_end,
    dev_days,
    holdout_days,
    min_holdout_days,
    step_days,
):
    holdout_start = pd.Timestamp(first_holdout_start)
    last_end = pd.Timestamp(last_holdout_end)
    step = pd.Timedelta(days=step_days or holdout_days)
    dev_delta = pd.Timedelta(days=dev_days)
    holdout_delta = pd.Timedelta(days=holdout_days - 1)

    while holdout_start <= last_end:
        holdout_end = min(holdout_start + holdout_delta, last_end)
        if (holdout_end - holdout_start).days + 1 < min_holdout_days:
            break
        dev_end = holdout_start - pd.Timedelta(days=1)
        dev_start = holdout_start - dev_delta
        yield dev_start, dev_end, holdout_start, holdout_end
        holdout_start = holdout_start + step


def iso_date(value: pd.Timestamp) -> str:
    return value.date().isoformat()


def select_strategy_for_fold(
    combined: pd.DataFrame,
    labels: list[str],
    dev_start: pd.Timestamp,
    dev_end: pd.Timestamp,
    args,
):
    candidates = []
    best_strategy = None
    best_score = (-math.inf,)
    for strategy in strategy_grid(labels):
        _, dev_summary = rescore(
            combined,
            strategy,
            iso_date(dev_start),
            iso_date(dev_end),
            write_rows=False,
            settlement_mode=args.settlement_mode,
            max_event_exposure_fraction=args.max_event_exposure_fraction,
        )
        score = objective_score(dev_summary, args.min_dev_bets, args.selection_objective)
        item = {"strategy": asdict(strategy), "summary": dev_summary, "score": score}
        candidates.append(item)
        if score > best_score:
            best_score = score
            best_strategy = strategy

    candidates.sort(key=lambda item: item["score"], reverse=True)
    if best_strategy is None or not np.isfinite(best_score[0]):
        return None, candidates
    return best_strategy, candidates


def summarize_selected_holdouts(holdout_df: pd.DataFrame, fold_summaries: list[dict]) -> dict:
    if holdout_df.empty:
        return {
            "folds": len(fold_summaries),
            "fights": 0,
            "bets": 0,
            "events_with_bets": 0,
            "profit": 0.0,
            "total_staked": 0.0,
            "roi_on_staked": None,
            "positive_folds": 0,
            "mean_fold_profit": None,
            "median_fold_profit": None,
            "selected_models": {},
        }

    bets = holdout_df[holdout_df["bet"].fillna(0) > 0].copy()
    total_staked = float(bets["bet"].sum())
    profit = float(bets["profit"].sum())
    fold_profits = [summary["holdout_summary"]["profit"] for summary in fold_summaries]
    selected_models = Counter(
        summary["selected_strategy"]["model_label"] for summary in fold_summaries
    )
    return {
        "folds": len(fold_summaries),
        "fights": int(len(holdout_df)),
        "bets": int(len(bets)),
        "events_with_bets": int(bets["event_date"].nunique()) if not bets.empty else 0,
        "profit": profit,
        "total_staked": total_staked,
        "roi_on_staked": profit / total_staked if total_staked > 0 else None,
        "positive_folds": int(sum(value > 0 for value in fold_profits)),
        "mean_fold_profit": float(np.mean(fold_profits)) if fold_profits else None,
        "median_fold_profit": float(np.median(fold_profits)) if fold_profits else None,
        "selected_models": dict(selected_models),
    }


def markdown_report(result: dict) -> str:
    aggregate = result["aggregate"]
    lines = [
        "# Nested Walk-Forward Edge Audit",
        "",
        f"Selection objective: `{result['selection_objective']}`",
        f"Development window length: {result['dev_days']} days",
        f"Holdout window length: {result['holdout_days']} days",
        f"Minimum holdout length: {result['min_holdout_days']} days",
        f"Minimum development bets: {result['min_dev_bets']}",
        "",
        "## Aggregate Holdout",
        "",
        f"Folds: {aggregate['folds']}",
        f"Fights: {aggregate['fights']}",
        f"Bets: {aggregate['bets']}",
        f"Profit: ${aggregate['profit']:.2f}",
        "ROI on staked: n/a"
        if aggregate["roi_on_staked"] is None
        else f"ROI on staked: {aggregate['roi_on_staked']:.2%}",
        f"Positive folds: {aggregate['positive_folds']} / {aggregate['folds']}",
        f"Selected models: `{json.dumps(aggregate['selected_models'], sort_keys=True)}`",
        "",
        "## Folds",
        "",
        "| Fold | Dev Window | Holdout Window | Selected Model | Edge | Min P | Kelly | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for fold in result["folds"]:
        strategy = fold["selected_strategy"]
        dev = fold["dev_summary"]
        holdout = fold["holdout_summary"]
        holdout_roi = (
            ""
            if holdout["roi_on_staked"] is None
            else f"{holdout['roi_on_staked']:.2%}"
        )
        lines.append(
            "| {fold} | {dev_start} to {dev_end} | {holdout_start} to {holdout_end} | {model} | {edge:.2f} | {minp:.2f} | {kelly:.3f} | ${dev_profit:.2f} | {dev_bets} | ${holdout_profit:.2f} | {holdout_bets} | {holdout_roi} |".format(
                fold=fold["fold_index"],
                dev_start=fold["dev_start"],
                dev_end=fold["dev_end"],
                holdout_start=fold["holdout_start"],
                holdout_end=fold["holdout_end"],
                model=strategy["model_label"],
                edge=strategy["min_edge"],
                minp=strategy["min_probability"],
                kelly=strategy["kelly_fraction"],
                dev_profit=dev["profit"],
                dev_bets=dev["bets"],
                holdout_profit=holdout["profit"],
                holdout_bets=holdout["bets"],
                holdout_roi=holdout_roi,
            )
        )

    lines.extend(
        [
            "",
            "Each fold resets bankroll to $1000. Aggregate profit is the sum of",
            "fold-level holdout profits, so treat it as repeated independent",
            "paper-tracking experiments rather than one continuously compounded",
            "live bankroll.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    ledgers = [
        load_ledger(Path(csv_path), label)
        for label, csv_path in args.ledger
    ]
    labels = [label for label, _ in args.ledger]
    combined = add_derived_columns(pd.concat(ledgers, ignore_index=True))

    fold_summaries = []
    selected_holdout_rows = []
    skipped_folds = []
    for fold_index, (dev_start, dev_end, holdout_start, holdout_end) in enumerate(
        iter_folds(
            args.first_holdout_start,
            args.last_holdout_end,
            args.dev_days,
            args.holdout_days,
            args.min_holdout_days,
            args.step_days,
        ),
        start=1,
    ):
        selected_strategy, candidates = select_strategy_for_fold(
            combined,
            labels,
            dev_start,
            dev_end,
            args,
        )
        if selected_strategy is None:
            skipped_folds.append(
                {
                    "fold_index": fold_index,
                    "dev_start": iso_date(dev_start),
                    "dev_end": iso_date(dev_end),
                    "holdout_start": iso_date(holdout_start),
                    "holdout_end": iso_date(holdout_end),
                    "reason": "no candidate met selection constraints",
                    "top_candidates": candidates[:5],
                }
            )
            continue

        dev_df, dev_summary = rescore(
            combined,
            selected_strategy,
            iso_date(dev_start),
            iso_date(dev_end),
            settlement_mode=args.settlement_mode,
            max_event_exposure_fraction=args.max_event_exposure_fraction,
        )
        holdout_df, holdout_summary = rescore(
            combined,
            selected_strategy,
            iso_date(holdout_start),
            iso_date(holdout_end),
            settlement_mode=args.settlement_mode,
            max_event_exposure_fraction=args.max_event_exposure_fraction,
        )
        fold_summary = {
            "fold_index": fold_index,
            "dev_start": iso_date(dev_start),
            "dev_end": iso_date(dev_end),
            "holdout_start": iso_date(holdout_start),
            "holdout_end": iso_date(holdout_end),
            "selected_strategy": asdict(selected_strategy),
            "dev_summary": dev_summary,
            "holdout_summary": holdout_summary,
            "top_dev_candidates": candidates[:10],
        }
        fold_summaries.append(fold_summary)

        holdout_output = holdout_df.copy()
        holdout_output["fold_index"] = fold_index
        holdout_output["fold_dev_start"] = iso_date(dev_start)
        holdout_output["fold_dev_end"] = iso_date(dev_end)
        holdout_output["fold_holdout_start"] = iso_date(holdout_start)
        holdout_output["fold_holdout_end"] = iso_date(holdout_end)
        holdout_output["selected_strategy"] = json.dumps(asdict(selected_strategy), sort_keys=True)
        selected_holdout_rows.append(holdout_output)

    selected_holdouts = (
        pd.concat(selected_holdout_rows, ignore_index=True)
        if selected_holdout_rows
        else pd.DataFrame()
    )
    if not selected_holdouts.empty:
        selected_holdouts = selected_holdouts.drop(
            columns=[column for column in HELPER_COLUMNS if column in selected_holdouts.columns]
        )

    aggregate = summarize_selected_holdouts(selected_holdouts, fold_summaries)
    result = {
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in args.ledger],
        "selection_objective": args.selection_objective,
        "dev_days": args.dev_days,
        "holdout_days": args.holdout_days,
        "min_holdout_days": args.min_holdout_days,
        "step_days": args.step_days or args.holdout_days,
        "min_dev_bets": args.min_dev_bets,
        "settlement_mode": args.settlement_mode,
        "max_event_exposure_fraction": args.max_event_exposure_fraction,
        "starting_bankroll_per_fold": STARTING_BANKROLL,
        "aggregate": aggregate,
        "folds": fold_summaries,
        "skipped_folds": skipped_folds,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "selected_holdouts.csv"
    json_path = output_dir / "nested_walk_forward_edge_audit.json"
    md_path = output_dir / "nested_walk_forward_edge_audit.md"

    selected_holdouts.to_csv(csv_path, index=False)
    with open(json_path, "w") as file:
        json.dump(result, file, indent=2)
    with open(md_path, "w") as file:
        file.write(markdown_report(result))

    print(f"Evaluated {len(fold_summaries)} folds; skipped {len(skipped_folds)}")
    print(f"Aggregate holdout profit: ${aggregate['profit']:.2f}")
    if aggregate["roi_on_staked"] is not None:
        print(f"Aggregate holdout ROI on staked: {aggregate['roi_on_staked']:.2%}")
    print(f"Selected models: {aggregate['selected_models']}")
    print(f"Selected holdouts: {csv_path}")
    print(f"Summary: {json_path}")
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
