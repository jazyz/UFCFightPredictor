#!/usr/bin/env python3
"""Nested forward audit for simple model-vs-market disagreement policies.

This script reads saved leak-safe prediction ledgers. It does not retrain a
model. Each fold selects a simple flat-stake disagreement rule on the prior
development window, then evaluates the frozen rule on the next holdout window.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_disagreement_audit import load_ledger  # noqa: E402
from testing.statistical_edge_audit import net_odds  # noqa: E402


DEFAULT_THRESHOLDS = [0.0, 0.02, 0.05, 0.08, 0.12, 0.16]
DEFAULT_MIN_PROBABILITIES = [0.5, 0.55, 0.6, 0.65]
DEFAULT_MAX_UNDERDOG_ODDS = [300.0, None]


@dataclass(frozen=True)
class DisagreementPolicy:
    model_label: str
    min_edge: float
    min_probability: float
    max_underdog_odds: Optional[float]


def parse_args():
    parser = argparse.ArgumentParser(description="Nested forward disagreement audit")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="model label and no_leakage_backtest.csv path",
    )
    parser.add_argument("--first-holdout-start", default="2023-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=365)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--min-holdout-days", type=int, default=120)
    parser.add_argument("--step-days", type=int, default=None)
    parser.add_argument("--min-dev-bets", type=int, default=35)
    parser.add_argument(
        "--selection-objective",
        choices=["profit", "roi", "market_edge"],
        default="profit",
        help="metric used to rank policies inside each development window",
    )
    parser.add_argument("--threshold", action="append", type=float)
    parser.add_argument("--min-probability", action="append", type=float)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument(
        "--selection-null-iterations",
        type=int,
        default=2000,
        help=(
            "market-null simulations that rerun fold-level policy selection; "
            "set to 0 to skip"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument(
        "--output-dir",
        default="test_results/disagreement_forward_selection_audit",
    )
    return parser.parse_args()


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


def policy_grid(
    labels: list[str],
    thresholds: list[float],
    min_probabilities: list[float],
):
    for label, min_edge, min_probability, max_underdog_odds in itertools.product(
        labels,
        thresholds,
        min_probabilities,
        DEFAULT_MAX_UNDERDOG_ODDS,
    ):
        yield DisagreementPolicy(
            model_label=label,
            min_edge=min_edge,
            min_probability=min_probability,
            max_underdog_odds=max_underdog_odds,
        )


def policy_mask(df: pd.DataFrame, policy: DisagreementPolicy) -> pd.Series:
    mask = (
        (df["model_label"] == policy.model_label)
        & (df["selected_edge"] >= policy.min_edge)
        & (df["selected_model_probability"] >= policy.min_probability)
    )
    if policy.max_underdog_odds is not None:
        mask &= df["selected_odds"] <= policy.max_underdog_odds
    return mask


def window_for_policy(
    df: pd.DataFrame,
    policy: DisagreementPolicy,
    start_date,
    end_date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_window = df[
        (df["model_label"] == policy.model_label)
        & (df["event_date"] >= pd.Timestamp(start_date))
        & (df["event_date"] <= pd.Timestamp(end_date))
    ].copy()
    bets = model_window[policy_mask(model_window, policy)].copy()
    return model_window, bets


def summarize_bets(model_window: pd.DataFrame, bets: pd.DataFrame) -> dict:
    if bets.empty:
        return {
            "fights": int(len(model_window)),
            "bets": 0,
            "events_with_bets": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_model_probability": None,
            "mean_market_probability": None,
            "mean_edge": None,
            "actual_minus_market": None,
        }

    profit = bets["flat_profit"].astype(float)
    actual_win_rate = float(bets["selected_won"].astype(float).mean())
    mean_market = float(bets["selected_market_probability"].astype(float).mean())
    return {
        "fights": int(len(model_window)),
        "bets": int(len(bets)),
        "events_with_bets": int(bets["event_date"].nunique()),
        "profit": float(profit.sum()),
        "roi": float(profit.mean()),
        "actual_win_rate": actual_win_rate,
        "mean_model_probability": float(bets["selected_model_probability"].astype(float).mean()),
        "mean_market_probability": mean_market,
        "mean_edge": float(bets["selected_edge"].astype(float).mean()),
        "actual_minus_market": actual_win_rate - mean_market,
    }


def evaluate_policy(
    df: pd.DataFrame,
    policy: DisagreementPolicy,
    start_date,
    end_date,
) -> tuple[pd.DataFrame, dict]:
    model_window, bets = window_for_policy(df, policy, start_date, end_date)
    return bets, summarize_bets(model_window, bets)


def objective_score(summary: dict, min_dev_bets: int, objective: str) -> tuple:
    if summary["bets"] < min_dev_bets:
        return (-math.inf,)
    roi = summary["roi"] if summary["roi"] is not None else -math.inf
    market_edge = (
        summary["actual_minus_market"]
        if summary["actual_minus_market"] is not None
        else -math.inf
    )
    if objective == "roi":
        return (roi, summary["profit"], market_edge, summary["bets"])
    if objective == "market_edge":
        return (market_edge, roi, summary["profit"], summary["bets"])
    return (summary["profit"], roi, market_edge, summary["bets"])


def simulated_objective_score(
    profit: float,
    win_count: int,
    bet_count: int,
    mean_market_probability: float,
    min_dev_bets: int,
    objective: str,
) -> tuple:
    if bet_count < min_dev_bets:
        return (-math.inf,)
    roi = profit / bet_count if bet_count else -math.inf
    market_edge = (
        win_count / bet_count - mean_market_probability
        if bet_count and np.isfinite(mean_market_probability)
        else -math.inf
    )
    if objective == "roi":
        return (roi, profit, market_edge, bet_count)
    if objective == "market_edge":
        return (market_edge, roi, profit, bet_count)
    return (profit, roi, market_edge, bet_count)


def select_policy_for_fold(
    df: pd.DataFrame,
    labels: list[str],
    thresholds: list[float],
    min_probabilities: list[float],
    dev_start: pd.Timestamp,
    dev_end: pd.Timestamp,
    args,
) -> tuple[DisagreementPolicy | None, list[dict]]:
    candidates = []
    best_policy = None
    best_score = (-math.inf,)
    for policy in policy_grid(labels, thresholds, min_probabilities):
        _, summary = evaluate_policy(df, policy, iso_date(dev_start), iso_date(dev_end))
        score = objective_score(summary, args.min_dev_bets, args.selection_objective)
        item = {"policy": asdict(policy), "summary": summary, "score": score}
        candidates.append(item)
        if score > best_score:
            best_score = score
            best_policy = policy

    candidates.sort(key=lambda item: item["score"], reverse=True)
    if best_policy is None or not np.isfinite(best_score[0]):
        return None, candidates
    return best_policy, candidates


def add_fold_columns(
    bets: pd.DataFrame,
    fold_index: int,
    dev_start: pd.Timestamp,
    dev_end: pd.Timestamp,
    holdout_start: pd.Timestamp,
    holdout_end: pd.Timestamp,
    policy: DisagreementPolicy,
) -> pd.DataFrame:
    output = bets.copy()
    output["event_date"] = pd.to_datetime(output["event_date"], errors="coerce").dt.date.astype(str)
    output["stake"] = 1.0
    output["fold_index"] = fold_index
    output["fold_dev_start"] = iso_date(dev_start)
    output["fold_dev_end"] = iso_date(dev_end)
    output["fold_holdout_start"] = iso_date(holdout_start)
    output["fold_holdout_end"] = iso_date(holdout_end)
    output["selected_policy"] = json.dumps(asdict(policy), sort_keys=True)
    output["policy_min_edge"] = policy.min_edge
    output["policy_min_probability"] = policy.min_probability
    output["policy_max_underdog_odds"] = (
        "" if policy.max_underdog_odds is None else policy.max_underdog_odds
    )
    return output


def summarize_aggregate(selected_holdouts: pd.DataFrame, folds: list[dict]) -> dict:
    fold_profits = [fold["holdout_summary"]["profit"] for fold in folds]
    fold_bets = [fold["holdout_summary"]["bets"] for fold in folds]
    if selected_holdouts.empty:
        return {
            "folds": len(folds),
            "holdout_fights": int(sum(fold["holdout_summary"]["fights"] for fold in folds)),
            "bets": 0,
            "events_with_bets": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_model_probability": None,
            "mean_market_probability": None,
            "mean_edge": None,
            "actual_minus_market": None,
            "positive_folds": int(sum(value > 0 for value in fold_profits)),
            "folds_with_bets": int(sum(value > 0 for value in fold_bets)),
            "selected_models": {},
            "selected_policies": {},
        }

    actual_win_rate = float(selected_holdouts["selected_won"].astype(float).mean())
    mean_market = float(selected_holdouts["selected_market_probability"].astype(float).mean())
    policy_counts = Counter(fold["selected_policy_json"] for fold in folds)
    model_counts = Counter(fold["selected_policy"]["model_label"] for fold in folds)
    profit = float(selected_holdouts["flat_profit"].astype(float).sum())
    bets = int(len(selected_holdouts))
    return {
        "folds": len(folds),
        "holdout_fights": int(sum(fold["holdout_summary"]["fights"] for fold in folds)),
        "bets": bets,
        "events_with_bets": int(selected_holdouts["event_date"].nunique()),
        "profit": profit,
        "roi": profit / bets if bets else None,
        "actual_win_rate": actual_win_rate,
        "mean_model_probability": float(
            selected_holdouts["selected_model_probability"].astype(float).mean()
        ),
        "mean_market_probability": mean_market,
        "mean_edge": float(selected_holdouts["selected_edge"].astype(float).mean()),
        "actual_minus_market": actual_win_rate - mean_market,
        "positive_folds": int(sum(value > 0 for value in fold_profits)),
        "folds_with_bets": int(sum(value > 0 for value in fold_bets)),
        "selected_models": dict(model_counts),
        "selected_policies": dict(policy_counts),
    }


def market_null_flat(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty:
        return None

    observed_profit = float(bets["flat_profit"].astype(float).sum())
    p_market = bets["selected_market_probability"].astype(float).to_numpy()
    multiples = np.array([net_odds(value) for value in bets["selected_odds"]], dtype=float)
    mask = (
        np.isfinite(p_market)
        & np.isfinite(multiples)
        & (p_market > 0)
        & (p_market < 1)
    )
    p_market = p_market[mask]
    multiples = multiples[mask]
    if len(p_market) == 0:
        return None

    profits = np.empty(iterations, dtype=float)
    cursor = 0
    chunk_size = 5000
    while cursor < iterations:
        chunk = min(chunk_size, iterations - cursor)
        wins = rng.random((chunk, len(p_market))) < p_market
        profit_matrix = np.where(wins, multiples, -1.0)
        profits[cursor : cursor + chunk] = profit_matrix.sum(axis=1)
        cursor += chunk

    return {
        "simulated_bets": int(len(p_market)),
        "observed_profit": observed_profit,
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(x) for x in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed_profit) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0)),
    }


def event_bootstrap(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty:
        return None

    grouped = bets.groupby("event_date", sort=True)["flat_profit"].sum()
    if grouped.empty:
        return None

    profits = grouped.astype(float).to_numpy()
    group_count = len(grouped)
    sampled = rng.integers(0, group_count, size=(iterations, group_count))
    sampled_profit = profits[sampled].sum(axis=1)
    return {
        "events": int(group_count),
        "profit_ci_95": [float(x) for x in np.percentile(sampled_profit, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(sampled_profit <= 0)),
    }


def precompute_policy_windows(
    df: pd.DataFrame,
    policies: list[DisagreementPolicy],
    fold_specs: list[tuple[int, pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]],
) -> list[dict]:
    event_days = df["event_date"].dt.floor("D").to_numpy(dtype="datetime64[D]")
    model_labels = df["model_label"].astype(str).to_numpy()
    selected_edge = df["selected_edge"].astype(float).to_numpy()
    selected_model_probability = df["selected_model_probability"].astype(float).to_numpy()
    selected_market_probability = df["selected_market_probability"].astype(float).to_numpy()
    selected_odds = df["selected_odds"].astype(float).to_numpy()

    policy_base_masks = []
    for policy in policies:
        mask = (
            (model_labels == policy.model_label)
            & (selected_edge >= policy.min_edge)
            & (selected_model_probability >= policy.min_probability)
        )
        if policy.max_underdog_odds is not None:
            mask &= selected_odds <= policy.max_underdog_odds
        policy_base_masks.append(mask)

    fold_windows = []
    for fold_index, dev_start, dev_end, holdout_start, holdout_end in fold_specs:
        dev_start_day = np.datetime64(dev_start.date())
        dev_end_day = np.datetime64(dev_end.date())
        holdout_start_day = np.datetime64(holdout_start.date())
        holdout_end_day = np.datetime64(holdout_end.date())
        dev_date_mask = (event_days >= dev_start_day) & (event_days <= dev_end_day)
        holdout_date_mask = (event_days >= holdout_start_day) & (event_days <= holdout_end_day)

        candidates = []
        for policy, base_mask in zip(policies, policy_base_masks):
            dev_indices = np.flatnonzero(base_mask & dev_date_mask)
            holdout_indices = np.flatnonzero(base_mask & holdout_date_mask)
            candidates.append(
                {
                    "policy": policy,
                    "dev_indices": dev_indices,
                    "holdout_indices": holdout_indices,
                    "dev_bets": int(len(dev_indices)),
                    "holdout_bets": int(len(holdout_indices)),
                    "dev_mean_market_probability": float(np.mean(selected_market_probability[dev_indices]))
                    if len(dev_indices)
                    else math.nan,
                }
            )
        fold_windows.append({"fold_index": fold_index, "candidates": candidates})
    return fold_windows


def fight_level_market_draws(df: pd.DataFrame, rng) -> np.ndarray:
    fight_keys = df["fight_key"].astype(str)
    unique_fights, inverse = np.unique(fight_keys.to_numpy(), return_inverse=True)
    fighter1_market = (
        df.groupby("fight_key", sort=True)["fighter1_market_probability"]
        .first()
        .reindex(unique_fights)
        .astype(float)
        .to_numpy()
    )
    fighter1_market = np.clip(fighter1_market, 1e-12, 1.0 - 1e-12)
    fighter1_wins = rng.random(len(unique_fights)) < fighter1_market
    selected_side = df["selected_side"].astype(int).to_numpy()
    return np.where(selected_side == 1, fighter1_wins[inverse], ~fighter1_wins[inverse])


def selection_adjusted_market_null(
    df: pd.DataFrame,
    policies: list[DisagreementPolicy],
    fold_specs: list[tuple[int, pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]],
    observed_profit: float,
    iterations: int,
    rng,
    min_dev_bets: int,
    objective: str,
) -> dict | None:
    if iterations <= 0:
        return None
    if df.empty or not policies or not fold_specs:
        return None

    fold_windows = precompute_policy_windows(df, policies, fold_specs)
    multiples = np.array([net_odds(value) for value in df["selected_odds"]], dtype=float)
    if not np.isfinite(multiples).all():
        return None

    profits = np.empty(iterations, dtype=float)
    selected_policy_counts = Counter()
    cursor = 0
    while cursor < iterations:
        simulated_won = fight_level_market_draws(df, rng)
        simulated_profit = np.where(simulated_won, multiples, -1.0)
        aggregate_profit = 0.0

        for fold in fold_windows:
            best_candidate = None
            best_score = (-math.inf,)
            for candidate in fold["candidates"]:
                dev_indices = candidate["dev_indices"]
                if candidate["dev_bets"] < min_dev_bets:
                    continue
                dev_profit = float(simulated_profit[dev_indices].sum())
                dev_wins = int(simulated_won[dev_indices].sum())
                score = simulated_objective_score(
                    dev_profit,
                    dev_wins,
                    candidate["dev_bets"],
                    candidate["dev_mean_market_probability"],
                    min_dev_bets,
                    objective,
                )
                if score > best_score:
                    best_score = score
                    best_candidate = candidate

            if best_candidate is None or not np.isfinite(best_score[0]):
                continue
            selected_policy_counts[json.dumps(asdict(best_candidate["policy"]), sort_keys=True)] += 1
            holdout_indices = best_candidate["holdout_indices"]
            if len(holdout_indices):
                aggregate_profit += float(simulated_profit[holdout_indices].sum())

        profits[cursor] = aggregate_profit
        cursor += 1

    return {
        "iterations": int(iterations),
        "observed_profit": float(observed_profit),
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(x) for x in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed_profit) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0)),
        "selected_policy_counts": dict(selected_policy_counts.most_common(20)),
    }


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:.2%}"


def fmt_float(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:.4f}"


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:+.2f}u"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:.3f}"


def policy_label(policy: dict) -> str:
    max_dog = "none" if policy["max_underdog_odds"] is None else f"{policy['max_underdog_odds']:.0f}"
    return (
        f"{policy['model_label']} edge>={policy['min_edge']:.2f} "
        f"p>={policy['min_probability']:.2f} maxdog={max_dog}"
    )


def markdown_report(result: dict) -> str:
    aggregate = result["aggregate"]
    market_null = result.get("market_null_flat") or {}
    selection_null = result.get("selection_adjusted_market_null") or {}
    bootstrap = result.get("event_bootstrap") or {}
    lines = [
        "# Disagreement Forward-Selection Audit",
        "",
        "This audit selects simple model-vs-market disagreement policies only on",
        "past data, then evaluates the frozen policy on the next holdout window.",
        "Each bet is flat 1 unit; no Kelly sizing or bankroll compounding is used.",
        "",
        f"Selection objective: `{result['selection_objective']}`",
        f"Candidate policies: {result['candidate_count']}",
        f"Development window length: {result['dev_days']} days",
        f"Holdout window length: {result['holdout_days']} days",
        f"Minimum development bets: {result['min_dev_bets']}",
        "",
        "## Aggregate Holdout",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| folds | {aggregate['folds']} |",
        f"| holdout fights | {aggregate['holdout_fights']} |",
        f"| bets | {aggregate['bets']} |",
        f"| events with bets | {aggregate['events_with_bets']} |",
        f"| profit | {fmt_units(aggregate['profit'])} |",
        f"| flat ROI | {fmt_pct(aggregate['roi'])} |",
        f"| actual win rate | {fmt_pct(aggregate['actual_win_rate'])} |",
        f"| mean market probability | {fmt_pct(aggregate['mean_market_probability'])} |",
        f"| actual - market | {fmt_pct(aggregate['actual_minus_market'])} |",
        f"| positive folds | {aggregate['positive_folds']} / {aggregate['folds']} |",
        f"| market-null p-value | {fmt_p(market_null.get('p_value_observed_or_better'))} |",
        f"| selection-adjusted market-null p-value | {fmt_p(selection_null.get('p_value_observed_or_better'))} |",
        f"| event-bootstrap P(profit <= 0) | {fmt_p(bootstrap.get('prob_profit_le_zero'))} |",
        "",
    ]
    if selection_null:
        lines.extend(
            [
                "## Selection-Adjusted Market Null",
                "",
                "This null simulates fight outcomes from de-vigged market probabilities",
                "and reruns the same fold-level policy selection in each simulated",
                "world. It asks how often the policy search itself finds holdout",
                "profit at least as high as the observed result.",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| iterations | {selection_null['iterations']} |",
                f"| observed profit | {fmt_units(selection_null['observed_profit'])} |",
                f"| null mean profit | {fmt_units(selection_null['null_mean_profit'])} |",
                f"| null 95% profit interval | {fmt_units(selection_null['null_profit_ci_95'][0])} to {fmt_units(selection_null['null_profit_ci_95'][1])} |",
                f"| p-value observed or better | {fmt_p(selection_null['p_value_observed_or_better'])} |",
                f"| probability null profitable | {fmt_p(selection_null['prob_null_profitable'])} |",
                "",
            ]
        )

    lines.extend(
        [
            "## Selected Policy Counts",
            "",
            "| Policy | Folds |",
            "| --- | ---: |",
        ]
    )

    for policy_json, count in sorted(
        aggregate["selected_policies"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        lines.append(f"| {policy_label(json.loads(policy_json))} | {count} |")

    lines.extend(
        [
            "",
            "## Folds",
            "",
            "| Fold | Dev Window | Holdout Window | Selected Policy | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI | Actual - Market |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for fold in result["folds"]:
        policy = fold["selected_policy"]
        dev = fold["dev_summary"]
        holdout = fold["holdout_summary"]
        lines.append(
            "| {fold} | {dev_start} to {dev_end} | {holdout_start} to {holdout_end} | {policy} | {dev_profit} | {dev_bets} | {holdout_profit} | {holdout_bets} | {holdout_roi} | {holdout_edge} |".format(
                fold=fold["fold_index"],
                dev_start=fold["dev_start"],
                dev_end=fold["dev_end"],
                holdout_start=fold["holdout_start"],
                holdout_end=fold["holdout_end"],
                policy=policy_label(policy),
                dev_profit=fmt_units(dev["profit"]),
                dev_bets=dev["bets"],
                holdout_profit=fmt_units(holdout["profit"]),
                holdout_bets=holdout["bets"],
                holdout_roi=fmt_pct(holdout["roi"]),
                holdout_edge=fmt_pct(holdout["actual_minus_market"]),
            )
        )

    lines.extend(
        [
            "",
            "## Decision Note",
            "",
            "This reduces threshold-picking bias relative to a static all-period slice,",
            "but it still does not remove researcher degrees of freedom from choosing",
            "this policy family after earlier diagnostics. Treat positive results as",
            "support for forward paper tracking unless they remain strong after future",
            "post-freeze outcomes.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    thresholds = args.threshold or DEFAULT_THRESHOLDS
    min_probabilities = args.min_probability or DEFAULT_MIN_PROBABILITIES
    labels = [label for label, _ in args.ledger]
    frames = [load_ledger(Path(csv_path), label) for label, csv_path in args.ledger]
    combined = pd.concat(frames, ignore_index=True)
    combined["event_date"] = pd.to_datetime(combined["event_date"], errors="coerce")
    combined = combined.dropna(subset=["event_date"]).sort_values("event_date").reset_index(drop=True)

    folds = []
    selected_holdout_rows = []
    skipped_folds = []
    fold_specs = [
        (fold_index, dev_start, dev_end, holdout_start, holdout_end)
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
        )
    ]
    for fold_index, dev_start, dev_end, holdout_start, holdout_end in fold_specs:
        selected_policy, candidates = select_policy_for_fold(
            combined,
            labels,
            thresholds,
            min_probabilities,
            dev_start,
            dev_end,
            args,
        )
        if selected_policy is None:
            skipped_folds.append(
                {
                    "fold_index": fold_index,
                    "dev_start": iso_date(dev_start),
                    "dev_end": iso_date(dev_end),
                    "holdout_start": iso_date(holdout_start),
                    "holdout_end": iso_date(holdout_end),
                    "reason": "no policy met selection constraints",
                    "top_candidates": candidates[:10],
                }
            )
            continue

        _, dev_summary = evaluate_policy(combined, selected_policy, iso_date(dev_start), iso_date(dev_end))
        holdout_bets, holdout_summary = evaluate_policy(
            combined,
            selected_policy,
            iso_date(holdout_start),
            iso_date(holdout_end),
        )
        policy_json = json.dumps(asdict(selected_policy), sort_keys=True)
        folds.append(
            {
                "fold_index": fold_index,
                "dev_start": iso_date(dev_start),
                "dev_end": iso_date(dev_end),
                "holdout_start": iso_date(holdout_start),
                "holdout_end": iso_date(holdout_end),
                "selected_policy": asdict(selected_policy),
                "selected_policy_json": policy_json,
                "dev_summary": dev_summary,
                "holdout_summary": holdout_summary,
                "top_dev_candidates": candidates[:10],
            }
        )
        if not holdout_bets.empty:
            selected_holdout_rows.append(
                add_fold_columns(
                    holdout_bets,
                    fold_index,
                    dev_start,
                    dev_end,
                    holdout_start,
                    holdout_end,
                    selected_policy,
                )
            )

    selected_holdouts = (
        pd.concat(selected_holdout_rows, ignore_index=True)
        if selected_holdout_rows
        else pd.DataFrame()
    )
    aggregate = summarize_aggregate(selected_holdouts, folds)
    rng = np.random.default_rng(args.seed)
    market_null = market_null_flat(selected_holdouts, args.iterations, rng)
    bootstrap = event_bootstrap(selected_holdouts, args.iterations, rng)
    policies = list(policy_grid(labels, thresholds, min_probabilities))
    selection_null = selection_adjusted_market_null(
        combined,
        policies,
        fold_specs,
        aggregate["profit"],
        args.selection_null_iterations,
        rng,
        args.min_dev_bets,
        args.selection_objective,
    )
    result = {
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in args.ledger],
        "selection_objective": args.selection_objective,
        "thresholds": thresholds,
        "min_probabilities": min_probabilities,
        "candidate_count": len(list(policy_grid(labels, thresholds, min_probabilities))),
        "first_holdout_start": args.first_holdout_start,
        "last_holdout_end": args.last_holdout_end,
        "dev_days": args.dev_days,
        "holdout_days": args.holdout_days,
        "min_holdout_days": args.min_holdout_days,
        "step_days": args.step_days or args.holdout_days,
        "min_dev_bets": args.min_dev_bets,
        "iterations": args.iterations,
        "selection_null_iterations": args.selection_null_iterations,
        "seed": args.seed,
        "aggregate": aggregate,
        "market_null_flat": market_null,
        "selection_adjusted_market_null": selection_null,
        "event_bootstrap": bootstrap,
        "folds": folds,
        "skipped_folds": skipped_folds,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "selected_holdout_bets.csv"
    json_path = output_dir / "disagreement_forward_selection_audit.json"
    md_path = output_dir / "disagreement_forward_selection_audit.md"
    selected_holdouts.to_csv(csv_path, index=False)
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    print(f"Evaluated {len(folds)} folds; skipped {len(skipped_folds)}")
    print(f"Aggregate holdout profit: {fmt_units(aggregate['profit'])}")
    print(f"Aggregate holdout ROI: {fmt_pct(aggregate['roi'])}")
    print(f"Market-null p-value: {fmt_p((market_null or {}).get('p_value_observed_or_better'))}")
    print(
        "Selection-adjusted market-null p-value: "
        f"{fmt_p((selection_null or {}).get('p_value_observed_or_better'))}"
    )
    print(f"Selected holdout bets: {csv_path}")
    print(f"Summary: {json_path}")
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
