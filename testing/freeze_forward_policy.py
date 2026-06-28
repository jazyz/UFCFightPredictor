#!/usr/bin/env python3
"""Freeze the forward paper-tracking policy from historical ledgers.

The goal is to remove future researcher degrees of freedom. Run this before
future outcomes are known, commit the resulting JSON/Markdown, and use the
selected policy unchanged for forward paper tracking.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.nested_walk_forward_edge_audit import objective_score  # noqa: E402
from testing.walk_forward_strategy_search import (  # noqa: E402
    add_derived_columns,
    load_ledger,
    rescore,
    strategy_grid,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze current forward policy")
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
        help="date the policy is frozen; dev window ends the previous day",
    )
    parser.add_argument("--dev-days", type=int, default=365)
    parser.add_argument("--min-dev-bets", type=int, default=35)
    parser.add_argument(
        "--selection-objective",
        choices=["profit", "roi"],
        default="roi",
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
    )
    parser.add_argument("--output-dir", default="test_results/frozen_forward_policy")
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
    return dev_start.isoformat(), dev_end.isoformat()


def select_policy(combined, labels, dev_start, dev_end, args):
    candidates = []
    best = None
    best_score = (float("-inf"),)
    for strategy in strategy_grid(labels):
        _, summary = rescore(
            combined,
            strategy,
            dev_start,
            dev_end,
            write_rows=False,
            settlement_mode=args.settlement_mode,
            max_event_exposure_fraction=args.max_event_exposure_fraction,
        )
        score = objective_score(summary, args.min_dev_bets, args.selection_objective)
        item = {
            "strategy": asdict(strategy),
            "summary": summary,
            "score": list(score),
        }
        candidates.append(item)
        if score > best_score:
            best = strategy
            best_score = score

    candidates.sort(key=lambda item: item["score"], reverse=True)
    if best is None or best_score[0] == float("-inf"):
        raise SystemExit("No strategy met the frozen-policy selection constraints")
    return best, candidates


def markdown_report(result):
    selected = result["selected_strategy"]
    dev = result["development_summary"]
    max_event_exposure = result["max_event_exposure_fraction"]
    max_event_exposure_text = "none" if max_event_exposure is None else str(max_event_exposure)
    lines = [
        "# Frozen Forward Policy",
        "",
        f"As-of date: `{result['as_of_date']}`",
        f"Development window: `{result['dev_start']}` to `{result['dev_end']}`",
        f"Selection objective: `{result['selection_objective']}`",
        f"Minimum development bets: `{result['min_dev_bets']}`",
        f"Settlement mode: `{result['settlement_mode']}`",
        f"Max event exposure fraction: `{max_event_exposure_text}`",
        f"Candidate strategies evaluated: `{result['candidate_count']}`",
        "",
        "This is a frozen forward paper-tracking contract, not evidence that a",
        "live betting edge has been proven. The selection uses only historical",
        "ledgers available as of the as-of date; future scoring should not replace",
        "this artifact after outcomes are known.",
        "",
        "## Selected Strategy",
        "",
        "```json",
        json.dumps(selected, indent=2),
        "```",
        "",
        "## Development Evidence",
        "",
        f"Profit: ${dev['profit']:.2f} ({dev['profit_pct']:.2f}%)",
        f"Fights: {dev['fights']}",
        f"Bets: {dev['bets']}",
        f"Events with bets: {dev['events_with_bets']}",
        "ROI on staked: n/a"
        if dev["roi_on_staked"] is None
        else f"ROI on staked: {dev['roi_on_staked']:.2%}",
        f"Max drawdown: {dev['max_drawdown']:.2%}",
        "",
        "## Frozen Rules",
        "",
        "- Do not change the model candidate set, objective, or strategy grid before future outcomes are known.",
        "- Ties are resolved by the existing `strategy_grid` iteration order.",
        "- Use this policy only for forward paper tracking until enough new outcomes accrue.",
        "- A future edge claim still requires market-null and event-bootstrap evidence on post-freeze bets.",
        "- If this policy is used for live recommendations, record that implementation separately before placing bets.",
        "",
        "## Top Development Candidates",
        "",
        "| Rank | Model | Side | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI | Max DD |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, item in enumerate(result["top_development_candidates"][:15], start=1):
        strategy = item["strategy"]
        summary = item["summary"]
        roi = "" if summary["roi_on_staked"] is None else f"{summary['roi_on_staked']:.2%}"
        max_dog = "none" if strategy["max_underdog_odds"] is None else f"{strategy['max_underdog_odds']:.0f}"
        lines.append(
            "| {rank} | {model} | {side} | {weight:.2f} | {edge:.2f} | {minp:.2f} | {minkelly:.2f} | {maxdog} | {kelly:.3f} | {cap:.3f} | ${profit:.2f} | {bets} | {roi} | {maxdd:.2%} |".format(
                rank=rank,
                model=strategy["model_label"],
                side=strategy["side_policy"],
                weight=strategy["model_weight"],
                edge=strategy["min_edge"],
                minp=strategy["min_probability"],
                minkelly=strategy["min_kelly"],
                maxdog=max_dog,
                kelly=strategy["kelly_fraction"],
                cap=strategy["max_fraction"],
                profit=summary["profit"],
                bets=summary["bets"],
                roi=roi,
                maxdd=summary["max_drawdown"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    dev_start, dev_end = date_window(args.as_of_date, args.dev_days)
    ledgers = [
        load_ledger(Path(csv_path), label)
        for label, csv_path in args.ledger
    ]
    labels = [label for label, _ in args.ledger]
    combined = add_derived_columns(pd.concat(ledgers, ignore_index=True))
    selected, candidates = select_policy(combined, labels, dev_start, dev_end, args)
    _, development_summary = rescore(
        combined,
        selected,
        dev_start,
        dev_end,
        settlement_mode=args.settlement_mode,
        max_event_exposure_fraction=args.max_event_exposure_fraction,
    )

    result = {
        "as_of_date": args.as_of_date,
        "dev_start": dev_start,
        "dev_end": dev_end,
        "dev_days": args.dev_days,
        "min_dev_bets": args.min_dev_bets,
        "selection_objective": args.selection_objective,
        "settlement_mode": args.settlement_mode,
        "max_event_exposure_fraction": args.max_event_exposure_fraction,
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in args.ledger],
        "candidate_count": len(candidates),
        "selected_strategy": asdict(selected),
        "development_summary": development_summary,
        "top_development_candidates": candidates[:25],
        "freeze_warning": (
            "This policy is frozen for forward paper tracking. Do not alter the "
            "candidate set, objective, strategy grid, or thresholds before scoring "
            "future outcomes."
        ),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "frozen_forward_policy.json"
    md_path = output_dir / "frozen_forward_policy.md"
    with open(json_path, "w") as file:
        json.dump(result, file, indent=2)
    with open(md_path, "w") as file:
        file.write(markdown_report(result))

    print(f"Frozen policy as of {args.as_of_date}")
    print(f"Development window: {dev_start} to {dev_end}")
    print(f"Selected strategy: {asdict(selected)}")
    print(f"Development profit: ${development_summary['profit']:.2f}")
    if development_summary["roi_on_staked"] is not None:
        print(f"Development ROI on staked: {development_summary['roi_on_staked']:.2%}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
