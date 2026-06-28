#!/usr/bin/env python3
"""Settle frozen-policy forward paper ledgers after outcomes are known.

Use this only after a pre-outcome ledger has already been generated and
archived. The outcomes file supplies winners; this script applies the frozen
ledger's recorded stakes and prices without changing bet decisions.
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

from testing.statistical_edge_audit import net_odds, parse_odds, safe_float  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_LEDGER = "test_results/forward_paper_tracking/latest_forward_paper_bets.csv"
DEFAULT_OUTPUT_DIR = "test_results/forward_paper_tracking/settled"


def parse_args():
    parser = argparse.ArgumentParser(description="Settle forward paper betting ledgers")
    parser.add_argument(
        "ledgers",
        nargs="*",
        default=[DEFAULT_LEDGER],
        help="pre-outcome forward paper ledger CSV(s)",
    )
    parser.add_argument(
        "--outcomes",
        help=(
            "CSV with winner column and either fight_index or fighter1/fighter2. "
            "Use --write-outcome-template to create one from a ledger."
        ),
    )
    parser.add_argument(
        "--write-outcome-template",
        help="write an empty outcome CSV template for the supplied ledger(s) and exit",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument(
        "--require-all-resolved",
        action="store_true",
        help="fail if any ledger fight is missing an outcome",
    )
    return parser.parse_args()


def clean_key(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def numeric(value) -> float:
    return safe_float(value)


def load_ledgers(paths: list[str]) -> pd.DataFrame:
    frames = []
    for path in paths:
        ledger_path = Path(path)
        if not ledger_path.exists():
            raise SystemExit(f"Missing forward ledger: {ledger_path}")
        frame = pd.read_csv(ledger_path)
        frame["ledger_path"] = str(ledger_path)
        if "event_key" not in frame.columns:
            frame["event_key"] = frame.get("fight_card_link", frame.get("generated_at_utc", ""))
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    required = {"fight_index", "fighter1", "fighter2", "selected_fighter", "stake"}
    missing = sorted(required - set(combined.columns))
    if missing:
        raise SystemExit(f"Forward ledger is missing required columns: {', '.join(missing)}")
    return combined


def write_outcome_template(ledger: pd.DataFrame, path: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template = ledger.copy()
    template["winner"] = ""
    template = template[
        [
            column
            for column in [
                "event_key",
                "fight_card_link",
                "fight_index",
                "fighter1",
                "fighter2",
                "winner",
                "selected_fighter",
                "stake",
            ]
            if column in template.columns
        ]
    ]
    template.to_csv(output_path, index=False)
    return output_path


def pair_key(fighter1, fighter2) -> frozenset[str]:
    return frozenset({canonical_name(fighter1), canonical_name(fighter2)})


def add_unique(mapping: dict, key, winner: str, duplicate_keys: set):
    if not key:
        return
    if key in mapping and mapping[key] != winner:
        duplicate_keys.add(key)
        mapping.pop(key, None)
        return
    if key not in duplicate_keys:
        mapping[key] = winner


def load_outcomes(path: str) -> dict:
    outcome_path = Path(path)
    if not outcome_path.exists():
        raise SystemExit(f"Missing outcomes CSV: {outcome_path}")
    outcomes = pd.read_csv(outcome_path)
    if "winner" not in outcomes.columns:
        raise SystemExit(f"{outcome_path} is missing required column: winner")

    by_card_index = {}
    by_index = {}
    by_pair = {}
    duplicate_card_index = set()
    duplicate_index = set()
    duplicate_pair = set()
    rows = []

    for _, row in outcomes.iterrows():
        winner = clean_key(row.get("winner"))
        if not winner:
            continue

        event_key = clean_key(row.get("event_key")) or clean_key(row.get("fight_card_link"))
        fight_index = clean_key(row.get("fight_index"))
        fighter1 = clean_key(row.get("fighter1"))
        fighter2 = clean_key(row.get("fighter2"))

        if event_key and fight_index:
            add_unique(by_card_index, (event_key, fight_index), winner, duplicate_card_index)
        if fight_index:
            add_unique(by_index, fight_index, winner, duplicate_index)
        if fighter1 and fighter2:
            add_unique(by_pair, pair_key(fighter1, fighter2), winner, duplicate_pair)

        rows.append(
            {
                "event_key": event_key,
                "fight_index": fight_index,
                "fighter1": fighter1,
                "fighter2": fighter2,
                "winner": winner,
            }
        )

    return {
        "rows": rows,
        "by_card_index": by_card_index,
        "by_index": by_index,
        "by_pair": by_pair,
        "duplicates": {
            "card_index": len(duplicate_card_index),
            "index": len(duplicate_index),
            "pair": len(duplicate_pair),
        },
    }


def winner_for_row(row: pd.Series, outcomes: dict) -> str:
    event_key = clean_key(row.get("event_key")) or clean_key(row.get("fight_card_link"))
    fight_index = clean_key(row.get("fight_index"))
    fighter1 = clean_key(row.get("fighter1"))
    fighter2 = clean_key(row.get("fighter2"))

    if event_key and fight_index:
        winner = outcomes["by_card_index"].get((event_key, fight_index))
        if winner:
            return winner
    if fight_index:
        winner = outcomes["by_index"].get(fight_index)
        if winner:
            return winner
    if fighter1 and fighter2:
        winner = outcomes["by_pair"].get(pair_key(fighter1, fighter2))
        if winner:
            return winner
    return ""


def settle_row(row: pd.Series, winner: str) -> dict:
    stake = numeric(row.get("stake"))
    selected = clean_key(row.get("selected_fighter"))
    selected_odds = parse_odds(row.get("selected_odds"))
    resolved = bool(winner)
    bet_placed = bool(np.isfinite(stake) and stake > 0 and selected)
    profit = np.nan
    bet_won = ""

    if resolved and bet_placed and selected_odds is not None:
        bet_won_bool = canonical_name(winner) == canonical_name(selected)
        profit = stake * net_odds(selected_odds) if bet_won_bool else -stake
        bet_won = bet_won_bool
    elif resolved:
        profit = 0.0

    output = row.to_dict()
    output.update(
        {
            "winner": winner,
            "resolved": resolved,
            "bet_won": bet_won,
            "profit": profit,
        }
    )
    return output


def settle_ledger(ledger: pd.DataFrame, outcomes: dict, require_all_resolved: bool) -> pd.DataFrame:
    rows = [settle_row(row, winner_for_row(row, outcomes)) for _, row in ledger.iterrows()]
    settled = pd.DataFrame(rows)
    unresolved = settled[~settled["resolved"].astype(bool)]
    if require_all_resolved and not unresolved.empty:
        raise SystemExit(f"{len(unresolved)} ledger rows are missing outcomes")

    bankroll = None
    if "bankroll" in settled.columns:
        bankroll_values = [numeric(value) for value in settled["bankroll"].dropna().tolist()]
        bankroll_values = [value for value in bankroll_values if np.isfinite(value)]
        bankroll = bankroll_values[0] if bankroll_values else None
    if bankroll is None:
        bankroll = 100.0

    running = bankroll
    before = []
    after = []
    for _, row in settled.iterrows():
        before.append(running)
        profit = numeric(row.get("profit"))
        if np.isfinite(profit):
            running += profit
        after.append(running)
    settled["bankroll_before"] = before
    settled["bankroll_after"] = after
    return settled


def event_key_series(df: pd.DataFrame) -> pd.Series:
    if "event_key" in df.columns:
        return df["event_key"].fillna("").replace("", np.nan)
    if "fight_card_link" in df.columns:
        return df["fight_card_link"].fillna("").replace("", np.nan)
    return df.get("generated_at_utc", pd.Series("forward", index=df.index))


def event_bootstrap(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty:
        return None
    grouped = (
        bets.assign(event_key=event_key_series(bets).fillna("unknown"))
        .groupby("event_key", sort=True)[["profit", "stake"]]
        .sum()
    )
    if grouped.empty:
        return None

    profits = grouped["profit"].astype(float).to_numpy()
    stakes = grouped["stake"].astype(float).to_numpy()
    group_count = len(grouped)
    sampled = rng.integers(0, group_count, size=(iterations, group_count))
    sampled_profit = profits[sampled].sum(axis=1)
    sampled_stake = stakes[sampled].sum(axis=1)
    sampled_roi = np.divide(
        sampled_profit,
        sampled_stake,
        out=np.full_like(sampled_profit, np.nan),
        where=sampled_stake > 0,
    )

    return {
        "events": int(group_count),
        "profit_ci_95": [float(x) for x in np.percentile(sampled_profit, [2.5, 97.5])],
        "roi_ci_95": [float(x) for x in np.nanpercentile(sampled_roi, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(sampled_profit <= 0)),
    }


def market_null_fixed_stake(bets: pd.DataFrame, observed_profit: float, iterations: int, rng) -> dict | None:
    if bets.empty:
        return None
    stakes = bets["stake"].astype(float).to_numpy()
    p_market = bets["selected_market_probability"].astype(float).to_numpy()
    multiples = np.array([net_odds(parse_odds(value)) for value in bets["selected_odds"]], dtype=float)
    mask = (
        np.isfinite(stakes)
        & np.isfinite(p_market)
        & np.isfinite(multiples)
        & (stakes > 0)
        & (p_market > 0)
        & (p_market < 1)
    )
    stakes = stakes[mask]
    p_market = p_market[mask]
    multiples = multiples[mask]
    if len(stakes) == 0:
        return None

    profits = np.empty(iterations, dtype=float)
    cursor = 0
    chunk_size = 5000
    while cursor < iterations:
        chunk = min(chunk_size, iterations - cursor)
        wins = rng.random((chunk, len(stakes))) < p_market
        profit_matrix = np.where(wins, stakes * multiples, -stakes)
        profits[cursor : cursor + chunk] = profit_matrix.sum(axis=1)
        cursor += chunk

    return {
        "simulated_bets": int(len(stakes)),
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(x) for x in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed_profit) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0)),
    }


def summarize(settled: pd.DataFrame, iterations: int, rng) -> dict:
    resolved = settled[settled["resolved"].astype(bool)].copy()
    bets = resolved[pd.to_numeric(resolved["stake"], errors="coerce") > 0].copy()
    bets["profit"] = pd.to_numeric(bets["profit"], errors="coerce")
    bets["stake"] = pd.to_numeric(bets["stake"], errors="coerce")
    observed_profit = float(bets["profit"].sum()) if not bets.empty else 0.0
    total_staked = float(bets["stake"].sum()) if not bets.empty else 0.0
    bankroll_start = float(numeric(settled["bankroll_before"].iloc[0])) if not settled.empty else 100.0

    if bets.empty:
        wins = 0
    else:
        wins = int(sum(bool(value) for value in bets["bet_won"].tolist()))

    return {
        "fights": int(len(settled)),
        "resolved_fights": int(len(resolved)),
        "unresolved_fights": int(len(settled) - len(resolved)),
        "bets": int(len(bets)),
        "bet_wins": wins,
        "profit": observed_profit,
        "starting_bankroll": bankroll_start,
        "final_bankroll": bankroll_start + observed_profit,
        "total_staked": total_staked,
        "roi_on_staked": observed_profit / total_staked if total_staked > 0 else None,
        "mean_selected_model_probability": nanmean_or_none(bets.get("selected_model_probability")),
        "mean_selected_market_probability": nanmean_or_none(bets.get("selected_market_probability")),
        "mean_selected_edge": nanmean_or_none(bets.get("selected_edge")),
        "market_null_fixed_stake": market_null_fixed_stake(bets, observed_profit, iterations, rng),
        "event_bootstrap": event_bootstrap(bets, iterations, rng),
    }


def nanmean_or_none(values) -> float | None:
    if values is None:
        return None
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return None
    return float(arr.mean())


def fmt_money(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"${value:,.2f}"


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * value:.2f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:.3f}"


def markdown_report(summary: dict, output: dict) -> str:
    market_null = summary.get("market_null_fixed_stake") or {}
    bootstrap = summary.get("event_bootstrap") or {}
    lines = [
        "# Settled Forward Paper Ledger",
        "",
        f"Ledgers: `{', '.join(output['ledgers'])}`",
        f"Outcomes: `{output['outcomes_path']}`",
        f"Iterations: `{output['iterations']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| fights | {summary['fights']} |",
        f"| resolved fights | {summary['resolved_fights']} |",
        f"| unresolved fights | {summary['unresolved_fights']} |",
        f"| bets | {summary['bets']} |",
        f"| bet wins | {summary['bet_wins']} |",
        f"| profit | {fmt_money(summary['profit'])} |",
        f"| total staked | {fmt_money(summary['total_staked'])} |",
        f"| ROI on staked | {fmt_pct(summary['roi_on_staked'])} |",
        f"| final bankroll | {fmt_money(summary['final_bankroll'])} |",
        "",
        "## Evidence Checks",
        "",
        "| Check | Value |",
        "| --- | ---: |",
        f"| market-null p-value | {fmt_p(market_null.get('p_value_observed_or_better'))} |",
        f"| market-null mean profit | {fmt_money(market_null.get('null_mean_profit'))} |",
        f"| event-bootstrap P(profit <= 0) | {fmt_p(bootstrap.get('prob_profit_le_zero'))} |",
        f"| event-bootstrap events | {bootstrap.get('events', '')} |",
        "",
        "This report settles already-frozen paper bets. It does not prove a live",
        "edge unless the ledger was archived before outcomes were known and enough",
        "post-freeze bets accumulate for the market-null and bootstrap evidence to",
        "be convincing.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(settled: pd.DataFrame, summary: dict, output: dict, output_dir: str):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "settled_forward_paper_bets.csv"
    json_path = directory / "settled_forward_paper_summary.json"
    md_path = directory / "settled_forward_paper_summary.md"
    settled.to_csv(csv_path, index=False)
    payload = {**output, "summary": summary}
    with json_path.open("w") as file:
        json.dump(payload, file, indent=2)
    md_path.write_text(markdown_report(summary, output))
    return csv_path, json_path, md_path


def main():
    args = parse_args()
    ledger = load_ledgers(args.ledgers)
    if args.write_outcome_template:
        path = write_outcome_template(ledger, args.write_outcome_template)
        print(f"Wrote outcome template: {path}")
        return
    if not args.outcomes:
        raise SystemExit("--outcomes is required unless --write-outcome-template is used")

    outcomes = load_outcomes(args.outcomes)
    settled = settle_ledger(ledger, outcomes, args.require_all_resolved)
    rng = np.random.default_rng(args.seed)
    summary = summarize(settled, args.iterations, rng)
    output = {
        "ledgers": args.ledgers,
        "outcomes_path": args.outcomes,
        "iterations": args.iterations,
        "seed": args.seed,
        "outcome_duplicates": outcomes["duplicates"],
    }
    csv_path, json_path, md_path = write_outputs(settled, summary, output, args.output_dir)
    print(f"Settled fights: {summary['resolved_fights']} / {summary['fights']}")
    print(f"Bets: {summary['bets']}")
    print(f"Profit: {fmt_money(summary['profit'])}")
    market_null = summary.get("market_null_fixed_stake") or {}
    if market_null:
        print(f"Market-null p-value: {fmt_p(market_null.get('p_value_observed_or_better'))}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
