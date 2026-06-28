#!/usr/bin/env python3
"""Walk-forward betting strategy search on leak-safe prediction ledgers.

The script optimizes only on a development window, then writes the selected
strategy's holdout ledger for a separate statistical audit.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import implied_prob, net_odds, parse_odds
from utils.name_matching import canonical_name


STARTING_BANKROLL = 1000.0
HELPER_COLUMNS = {
    "red_won",
    "winner_key",
    "fighter1_key",
    "fighter2_key",
    "fighter1_market_probability",
    "fighter2_market_probability",
    "red_market_probability",
    "fighter1_model_probability",
    "fighter2_model_probability",
    "fighter1_parsed_odds",
    "fighter2_parsed_odds",
    "bet_odds",
}


@dataclass(frozen=True)
class Strategy:
    model_label: str
    side_policy: str
    model_weight: float
    min_edge: float
    min_probability: float
    min_kelly: float
    max_underdog_odds: Optional[float]
    kelly_fraction: float
    max_fraction: float


def load_ledger(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["model_label"] = label
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        red = canonical_name(row["red_fighter"])
        winner = canonical_name(row["winner_name"])
        fighter1 = canonical_name(row["odds_fighter1_name"])
        fighter2 = canonical_name(row["odds_fighter2_name"])
        odds1 = parse_odds(row["fighter1_odds"])
        odds2 = parse_odds(row["fighter2_odds"])
        p1_raw = implied_prob(odds1)
        p2_raw = implied_prob(odds2)
        overround = p1_raw + p2_raw if np.isfinite(p1_raw) and np.isfinite(p2_raw) else np.nan
        p1_market = p1_raw / overround if np.isfinite(overround) and overround > 0 else np.nan
        p2_market = p2_raw / overround if np.isfinite(overround) and overround > 0 else np.nan

        p_fighter1 = float(row["fighter1_win_probability"])
        p_fighter2 = float(row["fighter2_win_probability"])
        red_market = np.nan
        if red == fighter1:
            red_market = p1_market
        elif red == fighter2:
            red_market = p2_market

        rows.append(
            {
                "red_won": winner == red,
                "winner_key": winner,
                "fighter1_key": fighter1,
                "fighter2_key": fighter2,
                "fighter1_market_probability": p1_market,
                "fighter2_market_probability": p2_market,
                "red_market_probability": red_market,
                "fighter1_model_probability": p_fighter1,
                "fighter2_model_probability": p_fighter2,
                "fighter1_parsed_odds": odds1,
                "fighter2_parsed_odds": odds2,
            }
        )

    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def kelly_fraction(odds: float, probability: float) -> float:
    multiple = net_odds(odds)
    return (multiple * probability - (1.0 - probability)) / multiple


def score_candidate_side(row, side: int, strategy: Strategy):
    if side == 1:
        fighter = row["odds_fighter1_name"]
        odds = row["fighter1_parsed_odds"]
        model_probability = row["fighter1_model_probability"]
        market_probability = row["fighter1_market_probability"]
    else:
        fighter = row["odds_fighter2_name"]
        odds = row["fighter2_parsed_odds"]
        model_probability = row["fighter2_model_probability"]
        market_probability = row["fighter2_market_probability"]

    if not all(np.isfinite(value) for value in [odds, model_probability, market_probability]):
        return None

    probability = (
        strategy.model_weight * model_probability
        + (1.0 - strategy.model_weight) * market_probability
    )
    edge = probability - market_probability
    kelly = kelly_fraction(odds, probability)
    if probability < strategy.min_probability:
        return None
    if edge < strategy.min_edge:
        return None
    if kelly < strategy.min_kelly:
        return None
    if strategy.max_underdog_odds is not None and odds > strategy.max_underdog_odds:
        return None

    return {
        "bet_candidate": fighter,
        "bet_on": fighter,
        "bet_on_key": canonical_name(fighter),
        "bet_odds": odds,
        "bet_probability": probability,
        "model_probability": model_probability,
        "market_probability": market_probability,
        "bet_edge": edge,
        "kelly": kelly,
    }


def choose_bet(row, strategy: Strategy):
    if strategy.side_policy == "predicted_winner":
        p1 = row["fighter1_model_probability"]
        p2 = row["fighter2_model_probability"]
        sides = [1 if p1 >= p2 else 2]
    elif strategy.side_policy == "best_edge":
        sides = [1, 2]
    else:
        raise ValueError(f"unknown side policy: {strategy.side_policy}")

    scored = [score_candidate_side(row, side, strategy) for side in sides]
    scored = [side for side in scored if side is not None]
    if not scored:
        return None
    return max(scored, key=lambda side: (side["bet_edge"], side["kelly"]))


def score_bet(
    bankroll: float,
    candidate: dict | None,
    winner_key: str,
    strategy: Strategy,
    bankroll_for_sizing: float | None = None,
    max_stake: float | None = None,
):
    if candidate is None:
        return bankroll, 0.0, 0.0, {}

    sizing_bankroll = bankroll if bankroll_for_sizing is None else bankroll_for_sizing
    stake = sizing_bankroll * strategy.kelly_fraction * candidate["kelly"]
    stake = min(stake, sizing_bankroll * strategy.max_fraction)
    if max_stake is not None:
        stake = min(stake, max_stake)
    if stake <= 0:
        return bankroll, 0.0, 0.0, {}

    if winner_key == candidate["bet_on_key"]:
        profit = stake * net_odds(candidate["bet_odds"])
    else:
        profit = -stake
    return bankroll + profit, stake, profit, candidate


def rescore(
    df: pd.DataFrame,
    strategy: Strategy,
    start_date,
    end_date,
    write_rows: bool = True,
    settlement_mode: str = "event",
    max_event_exposure_fraction: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    window = df[
        (df["model_label"] == strategy.model_label)
        & (df["event_date"] >= pd.Timestamp(start_date))
        & (df["event_date"] <= pd.Timestamp(end_date))
    ].copy()
    window = window.sort_values(["event_date", "title", "red_fighter", "blue_fighter"]).reset_index(drop=True)

    bankroll = STARTING_BANKROLL
    rows = []
    bankroll_values = []
    bet_count = 0
    bet_dates = set()
    total_staked = 0.0
    total_profit = 0.0
    for _, event_rows in window.groupby("event_date", sort=True):
        event_start_bankroll = bankroll
        event_profit = 0.0
        event_staked = 0.0
        for _, row in event_rows.iterrows():
            candidate = choose_bet(row, strategy)
            max_stake = None
            if max_event_exposure_fraction is not None:
                event_cap = event_start_bankroll * max_event_exposure_fraction
                max_stake = max(0.0, event_cap - event_staked)

            if settlement_mode == "event":
                bankroll_before = event_start_bankroll
                _, stake, profit, details = score_bet(
                    event_start_bankroll,
                    candidate,
                    row["winner_key"],
                    strategy,
                    bankroll_for_sizing=event_start_bankroll,
                    max_stake=max_stake,
                )
                event_staked += stake
                event_profit += profit
                bankroll_after = event_start_bankroll + event_profit
            else:
                bankroll_before = bankroll
                bankroll, stake, profit, details = score_bet(
                    bankroll,
                    candidate,
                    row["winner_key"],
                    strategy,
                    max_stake=max_stake,
                )
                event_staked += stake
                event_profit += profit
                bankroll_after = bankroll

            bankroll_values.append(bankroll_after)
            total_staked += stake
            total_profit += profit
            if stake > 0:
                bet_count += 1
                bet_dates.add(row["event_date"].date().isoformat())
            if write_rows:
                output = row.to_dict()
                output["event_date"] = row["event_date"].date().isoformat()
                output["bet_candidate"] = details.get("bet_candidate", "")
                output["bet_on"] = details.get("bet_on", "")
                output["bet_odds"] = details.get("bet_odds", np.nan)
                output["bet_probability"] = details.get("bet_probability", np.nan)
                output["market_probability"] = details.get("market_probability", np.nan)
                output["bet_edge"] = details.get("bet_edge", np.nan)
                output["kelly"] = details.get("kelly", 0.0)
                output["bet"] = stake
                output["profit"] = profit
                output["bankroll_before"] = bankroll_before
                output["bankroll_after"] = bankroll_after
                output["event_start_bankroll"] = event_start_bankroll
                output["no_bet_reason"] = "" if stake > 0 else "strategy filter"
                rows.append(output)

        if settlement_mode == "event":
            bankroll = event_start_bankroll + event_profit

    scored = pd.DataFrame(rows)
    profit = float(total_profit)
    max_drawdown = calculate_max_drawdown(np.asarray(bankroll_values, dtype=float))
    summary = {
        "strategy": asdict(strategy),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "starting_bankroll": STARTING_BANKROLL,
        "final_bankroll": float(bankroll),
        "profit": profit,
        "profit_pct": (bankroll - STARTING_BANKROLL) / STARTING_BANKROLL * 100.0,
        "bets": int(bet_count),
        "events_with_bets": int(len(bet_dates)),
        "total_staked": float(total_staked),
        "roi_on_staked": profit / total_staked if total_staked > 0 else None,
        "max_drawdown": max_drawdown,
        "fights": int(len(window)),
        "settlement_mode": settlement_mode,
        "max_event_exposure_fraction": max_event_exposure_fraction,
    }
    return scored, summary


def calculate_max_drawdown(bankroll_values: np.ndarray) -> float:
    if len(bankroll_values) == 0:
        return 0.0
    running_max = np.maximum.accumulate(np.insert(bankroll_values, 0, STARTING_BANKROLL))
    curve = np.insert(bankroll_values, 0, STARTING_BANKROLL)
    drawdowns = (running_max - curve) / running_max
    return float(np.max(drawdowns))


def strategy_grid(model_labels):
    side_policies = ["predicted_winner", "best_edge"]
    model_weights = [0.7, 1.0]
    min_edges = [0.02, 0.08, 0.16]
    min_probabilities = [0.5, 0.6]
    min_kellies = [0.0, 0.10]
    max_underdog_odds_values = [300.0, None]
    staking_pairs = [(0.025, 0.025), (0.025, 0.05), (0.05, 0.05)]

    for parts in itertools.product(
        model_labels,
        side_policies,
        model_weights,
        min_edges,
        min_probabilities,
        min_kellies,
        max_underdog_odds_values,
        staking_pairs,
    ):
        (
            model_label,
            side_policy,
            model_weight,
            min_edge,
            min_probability,
            min_kelly,
            max_underdog_odds,
            staking_pair,
        ) = parts
        kelly_fraction_value, max_fraction = staking_pair
        yield Strategy(
            model_label=model_label,
            side_policy=side_policy,
            model_weight=model_weight,
            min_edge=min_edge,
            min_probability=min_probability,
            min_kelly=min_kelly,
            max_underdog_odds=max_underdog_odds,
            kelly_fraction=kelly_fraction_value,
            max_fraction=max_fraction,
        )


def selection_score(summary: dict, min_dev_bets: int) -> tuple:
    if summary["bets"] < min_dev_bets:
        return (-math.inf,)
    if summary["max_drawdown"] > 0.35:
        return (-math.inf,)
    roi = summary["roi_on_staked"] if summary["roi_on_staked"] is not None else -math.inf
    return (
        summary["profit"],
        roi,
        -summary["max_drawdown"],
        summary["bets"],
    )


def write_rescored_ledger(path: Path, df: pd.DataFrame, summary: dict):
    path.mkdir(parents=True, exist_ok=True)
    csv_path = path / "no_leakage_backtest.csv"
    summary_path = path / "no_leakage_backtest_summary.json"
    output_df = df.drop(columns=[column for column in HELPER_COLUMNS if column in df.columns])
    output_df.to_csv(csv_path, index=False)
    with open(summary_path, "w") as file:
        json.dump(summary, file, indent=2)
    return csv_path, summary_path


def markdown_report(output: dict) -> str:
    selected = output["selected_strategy"]
    dev = output["dev_summary"]
    holdout = output["holdout_summary"]
    top = output["top_dev_candidates"][:20]
    lines = [
        "# Walk-Forward Strategy Search",
        "",
        f"Development window: {output['dev_start']} to {output['dev_end']}",
        f"Holdout window: {output['holdout_start']} to {output['holdout_end']}",
        f"Settlement mode: {output['settlement_mode']}",
        f"Max event exposure fraction: {output['max_event_exposure_fraction']}",
        f"Candidate strategies evaluated on development window: {output['candidate_count']}",
        "",
        "## Selected Strategy",
        "",
        "```json",
        json.dumps(selected, indent=2),
        "```",
        "",
        "## Development Result",
        "",
        f"Profit: ${dev['profit']:.2f} ({dev['profit_pct']:.2f}%)",
        f"Bets: {dev['bets']}",
        f"ROI on staked: {dev['roi_on_staked']:.2%}" if dev["roi_on_staked"] is not None else "ROI on staked: n/a",
        f"Max drawdown: {dev['max_drawdown']:.2%}",
        "",
        "## Holdout Result",
        "",
        f"Profit: ${holdout['profit']:.2f} ({holdout['profit_pct']:.2f}%)",
        f"Bets: {holdout['bets']}",
        f"ROI on staked: {holdout['roi_on_staked']:.2%}" if holdout["roi_on_staked"] is not None else "ROI on staked: n/a",
        f"Max drawdown: {holdout['max_drawdown']:.2%}",
        "",
        "## Top Development Candidates",
        "",
        "| Rank | Model | Side Policy | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, item in enumerate(top, start=1):
        strategy = item["strategy"]
        summary = item["summary"]
        max_dog = "none" if strategy["max_underdog_odds"] is None else f"{strategy['max_underdog_odds']:.0f}"
        roi = "" if summary["roi_on_staked"] is None else f"{summary['roi_on_staked']:.2%}"
        lines.append(
            "| {rank} | {model} | {side} | {weight:.2f} | {edge:.2f} | {minp:.2f} | {mink:.2f} | {maxdog} | {kelly:.3f} | {cap:.3f} | ${profit:.2f} | {bets} | {roi} |".format(
                rank=index,
                model=strategy["model_label"],
                side=strategy["side_policy"],
                weight=strategy["model_weight"],
                edge=strategy["min_edge"],
                minp=strategy["min_probability"],
                mink=strategy["min_kelly"],
                maxdog=max_dog,
                kelly=strategy["kelly_fraction"],
                cap=strategy["max_fraction"],
                profit=summary["profit"],
                bets=summary["bets"],
                roi=roi,
            )
        )
    lines.append("")
    lines.append("The selected strategy is evaluated once on holdout; use the holdout ledger with")
    lines.append("`testing/statistical_edge_audit.py` for market-null and bootstrap inference.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Walk-forward search for betting strategies")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="model label and no_leakage_backtest.csv path",
    )
    parser.add_argument("--dev-start", default="2024-06-27")
    parser.add_argument("--dev-end", default="2025-06-26")
    parser.add_argument("--holdout-start", default="2025-06-27")
    parser.add_argument("--holdout-end", default="2026-06-27")
    parser.add_argument("--min-dev-bets", type=int, default=40)
    parser.add_argument(
        "--settlement-mode",
        choices=["event", "sequential"],
        default="event",
        help=(
            "event sizes all bets on a card from the event-start bankroll; "
            "sequential reproduces the old row-by-row compounding behavior"
        ),
    )
    parser.add_argument(
        "--max-event-exposure-fraction",
        type=float,
        default=None,
        help="optional cap on total stake per event as a fraction of event-start bankroll",
    )
    parser.add_argument("--output-dir", default="test_results/walk_forward_strategy_search")
    args = parser.parse_args()

    ledgers = [
        load_ledger(Path(csv_path), label)
        for label, csv_path in args.ledger
    ]
    combined = add_derived_columns(pd.concat(ledgers, ignore_index=True))
    labels = [label for label, _ in args.ledger]

    candidates = []
    best = None
    best_score = (-math.inf,)
    for strategy in strategy_grid(labels):
        _, dev_summary = rescore(
            combined,
            strategy,
            args.dev_start,
            args.dev_end,
            write_rows=False,
            settlement_mode=args.settlement_mode,
            max_event_exposure_fraction=args.max_event_exposure_fraction,
        )
        score = selection_score(dev_summary, args.min_dev_bets)
        item = {"strategy": asdict(strategy), "summary": dev_summary, "score": score}
        candidates.append(item)
        if score > best_score:
            best = strategy
            best_score = score

    if best is None:
        raise SystemExit("No strategy met selection constraints")

    dev_df, dev_summary = rescore(
        combined,
        best,
        args.dev_start,
        args.dev_end,
        settlement_mode=args.settlement_mode,
        max_event_exposure_fraction=args.max_event_exposure_fraction,
    )
    holdout_df, holdout_summary = rescore(
        combined,
        best,
        args.holdout_start,
        args.holdout_end,
        settlement_mode=args.settlement_mode,
        max_event_exposure_fraction=args.max_event_exposure_fraction,
    )
    output_dir = Path(args.output_dir)
    dev_csv, dev_summary_path = write_rescored_ledger(output_dir / "selected_dev", dev_df, dev_summary)
    holdout_csv, holdout_summary_path = write_rescored_ledger(
        output_dir / "selected_holdout",
        holdout_df,
        holdout_summary,
    )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    result = {
        "dev_start": args.dev_start,
        "dev_end": args.dev_end,
        "holdout_start": args.holdout_start,
        "holdout_end": args.holdout_end,
        "settlement_mode": args.settlement_mode,
        "max_event_exposure_fraction": args.max_event_exposure_fraction,
        "candidate_count": len(candidates),
        "min_dev_bets": args.min_dev_bets,
        "selected_strategy": asdict(best),
        "dev_summary": dev_summary,
        "holdout_summary": holdout_summary,
        "selected_dev_csv": str(dev_csv),
        "selected_dev_summary": str(dev_summary_path),
        "selected_holdout_csv": str(holdout_csv),
        "selected_holdout_summary": str(holdout_summary_path),
        "top_dev_candidates": candidates[:50],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "walk_forward_strategy_search.json", "w") as file:
        json.dump(result, file, indent=2)
    with open(output_dir / "walk_forward_strategy_search.md", "w") as file:
        file.write(markdown_report(result))

    print(f"Evaluated {len(candidates)} candidate strategies")
    print(f"Selected: {asdict(best)}")
    print(f"Development profit: ${dev_summary['profit']:.2f} ({dev_summary['profit_pct']:.2f}%)")
    print(f"Holdout profit: ${holdout_summary['profit']:.2f} ({holdout_summary['profit_pct']:.2f}%)")
    print(f"Holdout ledger: {holdout_csv}")


if __name__ == "__main__":
    main()
