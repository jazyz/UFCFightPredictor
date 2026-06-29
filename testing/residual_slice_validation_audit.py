#!/usr/bin/env python3
"""Validate residual-edge slices with prior-period selection.

Full-sample slice tables are tempting but dangerous. This audit asks whether
simple residual/probability/bout-category slices selected from earlier
outcomes survive later periods, and reruns that selection under market-null
simulations.
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


DEFAULT_PROBABILITIES = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
DEFAULT_RANKED_BETS = "test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv"
EPS = 1e-6


def parse_args():
    parser = argparse.ArgumentParser(description="Validate residual slices selected on prior periods")
    parser.add_argument("--probabilities", default=DEFAULT_PROBABILITIES)
    parser.add_argument("--ranked-bets", default=DEFAULT_RANKED_BETS)
    parser.add_argument("--min-dev-fights", type=int, default=30)
    parser.add_argument("--min-dev-bets", type=int, default=15)
    parser.add_argument("--market-null-iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_slice_validation_audit")
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def title_group(title: str) -> str:
    text = str(title)
    if "Women" in text:
        return "women"
    if "Heavyweight" in text or "Light Heavyweight" in text:
        return "heavy_or_lhw"
    if "Middleweight" in text or "Welterweight" in text:
        return "middle_or_welter"
    if "Lightweight" in text or "Featherweight" in text:
        return "light_or_feather"
    if "Bantamweight" in text or "Flyweight" in text:
        return "bantam_or_fly"
    if "Catch" in text or "Open" in text:
        return "catch_or_open"
    return "other"


def bin_series(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(series.astype(float), bins=bins, labels=labels, include_lowest=True, right=False)


def binary_loss(y_true: np.ndarray, probability: np.ndarray) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def american_win_profit(odds: np.ndarray) -> np.ndarray:
    odds = np.asarray(odds, dtype=float)
    return np.where(odds > 0.0, odds / 100.0, 100.0 / np.abs(odds))


def prepare_probabilities(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    df["year"] = df["event_date"].dt.year.astype(int)
    df["title_group"] = df["title"].map(title_group)
    df["market_bin"] = bin_series(
        df["market_probability"],
        [0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.000001],
        ["market_<0.40", "market_0.40_0.50", "market_0.50_0.60", "market_0.60_0.70", "market_0.70_0.80", "market_>=0.80"],
    )
    df["residual_edge"] = df["selected_probability"].astype(float) - df["market_probability"].astype(float)
    df["abs_edge"] = df["residual_edge"].abs()
    df["abs_edge_bin"] = bin_series(
        df["abs_edge"],
        [0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 1.000001],
        ["abs_edge_<0.01", "abs_edge_0.01_0.02", "abs_edge_0.02_0.03", "abs_edge_0.03_0.05", "abs_edge_0.05_0.08", "abs_edge_>=0.08"],
    )
    df["edge_direction"] = np.where(df["residual_edge"] >= 0.0, "meta_up_on_red", "meta_down_on_red")

    y = df["red_won"].astype(float).to_numpy()
    market = df["market_probability"].astype(float).to_numpy()
    candidate = df["selected_probability"].astype(float).to_numpy()
    df["market_loss"] = binary_loss(y, market)
    df["candidate_loss"] = binary_loss(y, candidate)
    df["delta_loss"] = df["market_loss"] - df["candidate_loss"]
    return df


def prepare_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    df = df[
        (df["probability_policy"] == "frozen_residual_meta")
        & (df["ranking_mode"] == "top_edge")
    ].copy()
    if df.empty:
        raise SystemExit("No frozen_residual_meta/top_edge bets found")
    df["year"] = df["event_date"].dt.year.astype(int)
    df["title_group"] = df["title"].map(title_group)
    df["market_bin"] = bin_series(
        df["selected_market_probability"],
        [0.0, 0.5, 0.6, 0.7, 0.8, 1.000001],
        ["market_<0.50", "market_0.50_0.60", "market_0.60_0.70", "market_0.70_0.80", "market_>=0.80"],
    )
    df["edge_bin"] = bin_series(
        df["selected_edge"],
        [0.0, 0.02, 0.03, 0.05, 0.08, 1.000001],
        ["edge_<0.02", "edge_0.02_0.03", "edge_0.03_0.05", "edge_0.05_0.08", "edge_>=0.08"],
    )
    df["probability_bin"] = bin_series(
        df["selected_probability"],
        [0.0, 0.6, 0.65, 0.7, 0.8, 1.000001],
        ["prob_<0.60", "prob_0.60_0.65", "prob_0.65_0.70", "prob_0.70_0.80", "prob_>=0.80"],
    )
    df["win_profit"] = american_win_profit(df["selected_odds"].astype(float).to_numpy())
    return df


def candidate_masks(df: pd.DataFrame, families: list[str]) -> list[dict]:
    candidates = [{"name": "all", "family": "all", "mask": np.ones(len(df), dtype=bool)}]
    for family in families:
        for value in sorted(df[family].dropna().astype(str).unique()):
            mask = df[family].astype(str).to_numpy() == value
            if mask.any():
                candidates.append({"name": value, "family": family, "mask": mask})
    return candidates


def summarize_probability(df: pd.DataFrame, mask: np.ndarray) -> dict:
    subset = df[mask]
    if subset.empty:
        return {
            "fights": 0,
            "events": 0,
            "market_log_loss": None,
            "candidate_log_loss": None,
            "delta_log_loss": None,
            "sum_delta": 0.0,
        }
    return {
        "fights": int(len(subset)),
        "events": int(subset["event_date"].nunique()),
        "market_log_loss": float(subset["market_loss"].mean()),
        "candidate_log_loss": float(subset["candidate_loss"].mean()),
        "delta_log_loss": float(subset["delta_loss"].mean()),
        "sum_delta": float(subset["delta_loss"].sum()),
    }


def summarize_bets(df: pd.DataFrame, mask: np.ndarray) -> dict:
    subset = df[mask]
    if subset.empty:
        return {
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_minus_market": None,
        }
    profit = subset["flat_profit"].astype(float)
    return {
        "bets": int(len(subset)),
        "events": int(subset["event_date"].nunique()),
        "profit": float(profit.sum()),
        "roi": float(profit.mean()),
        "actual_minus_market": float(
            subset["selected_won"].astype(float).mean()
            - subset["selected_market_probability"].astype(float).mean()
        ),
    }


def select_candidate(
    candidates: list[dict],
    metric_values: np.ndarray,
    train_mask: np.ndarray,
    min_count: int,
    objective: str,
) -> dict | None:
    scored = []
    for candidate in candidates:
        mask = train_mask & candidate["mask"]
        count = int(mask.sum())
        if count < min_count:
            continue
        if objective == "mean":
            score = float(np.mean(metric_values[mask]))
        elif objective == "sum":
            score = float(np.sum(metric_values[mask]))
        else:
            raise ValueError(f"unknown objective: {objective}")
        scored.append((score, count, candidate["family"], candidate["name"], candidate))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
    return scored[0][4]


def top_candidates(
    candidates: list[dict],
    metric_values: np.ndarray,
    train_mask: np.ndarray,
    min_count: int,
    objective: str,
    limit: int = 8,
) -> list[dict]:
    rows = []
    for candidate in candidates:
        mask = train_mask & candidate["mask"]
        count = int(mask.sum())
        if count < min_count:
            continue
        score = float(np.mean(metric_values[mask]) if objective == "mean" else np.sum(metric_values[mask]))
        rows.append(
            {
                "family": candidate["family"],
                "name": candidate["name"],
                "count": count,
                "score": score,
            }
        )
    return sorted(rows, key=lambda row: (row["score"], row["count"]), reverse=True)[:limit]


def probability_2024_selection(df: pd.DataFrame, candidates: list[dict], min_dev_fights: int) -> dict:
    dev_mask = df["year"].to_numpy() == 2024
    post_mask = df["year"].to_numpy() >= 2025
    latest_mask = df["event_date"].to_numpy(dtype="datetime64[ns]") >= np.datetime64("2025-06-28")
    metric = df["delta_loss"].to_numpy(dtype=float)
    selected = select_candidate(candidates, metric, dev_mask, min_dev_fights, "mean")
    if selected is None:
        raise SystemExit("No probability candidate passed min dev fights")
    return {
        "selected": {"family": selected["family"], "name": selected["name"]},
        "top_dev_candidates": top_candidates(candidates, metric, dev_mask, min_dev_fights, "mean"),
        "dev_2024": summarize_probability(df, dev_mask & selected["mask"]),
        "eval_2025_2026": summarize_probability(df, post_mask & selected["mask"]),
        "eval_last_365d": summarize_probability(df, latest_mask & selected["mask"]),
        "aggregate_same_slice": summarize_probability(df, selected["mask"]),
    }


def bets_2024_selection(df: pd.DataFrame, candidates: list[dict], min_dev_bets: int) -> dict:
    dev_mask = df["year"].to_numpy() == 2024
    post_mask = df["year"].to_numpy() >= 2025
    latest_mask = df["event_date"].to_numpy(dtype="datetime64[ns]") >= np.datetime64("2025-06-28")
    metric = df["flat_profit"].astype(float).to_numpy()
    selected = select_candidate(candidates, metric, dev_mask, min_dev_bets, "sum")
    if selected is None:
        raise SystemExit("No bet candidate passed min dev bets")
    return {
        "selected": {"family": selected["family"], "name": selected["name"]},
        "top_dev_candidates": top_candidates(candidates, metric, dev_mask, min_dev_bets, "sum"),
        "dev_2024": summarize_bets(df, dev_mask & selected["mask"]),
        "eval_2025_2026": summarize_bets(df, post_mask & selected["mask"]),
        "eval_last_365d": summarize_bets(df, latest_mask & selected["mask"]),
        "aggregate_same_slice": summarize_bets(df, selected["mask"]),
    }


def rolling_selection(
    df: pd.DataFrame,
    candidates: list[dict],
    metric_values: np.ndarray,
    min_dev_count: int,
    objective: str,
    summarize_fn,
) -> dict:
    selected_rows = []
    eval_masks = []
    for fold in sorted(df["fold"].astype(int).unique()):
        if fold <= 1:
            continue
        train_mask = df["fold"].astype(int).to_numpy() < fold
        eval_mask = df["fold"].astype(int).to_numpy() == fold
        selected = select_candidate(candidates, metric_values, train_mask, min_dev_count, objective)
        if selected is None:
            continue
        selected_eval = eval_mask & selected["mask"]
        eval_masks.append(selected_eval)
        selected_rows.append(
            {
                "eval_fold": int(fold),
                "selected_family": selected["family"],
                "selected_name": selected["name"],
                "dev_count": int((train_mask & selected["mask"]).sum()),
                "eval_count": int(selected_eval.sum()),
                "dev_score": float(
                    np.mean(metric_values[train_mask & selected["mask"]])
                    if objective == "mean"
                    else np.sum(metric_values[train_mask & selected["mask"]])
                ),
                "eval_summary": summarize_fn(df, selected_eval),
            }
        )
    if eval_masks:
        combined = np.logical_or.reduce(eval_masks)
    else:
        combined = np.zeros(len(df), dtype=bool)
    return {
        "folds": selected_rows,
        "combined_eval": summarize_fn(df, combined),
    }


def probability_market_null(df, candidates, protocol: str, min_dev_fights: int, iterations: int, rng) -> float:
    market = df["market_probability"].astype(float).to_numpy()
    candidate_prob = df["selected_probability"].astype(float).to_numpy()
    actual = df["red_won"].astype(float).to_numpy()
    actual_delta = df["delta_loss"].to_numpy(dtype=float)

    if protocol == "2024_to_later":
        observed_selected = select_candidate(
            candidates,
            actual_delta,
            df["year"].to_numpy() == 2024,
            min_dev_fights,
            "mean",
        )
        observed_mask = (df["year"].to_numpy() >= 2025) & observed_selected["mask"]
        observed = float(actual_delta[observed_mask].mean()) if observed_mask.any() else np.nan
    elif protocol == "rolling":
        observed = rolling_selection(df, candidates, actual_delta, min_dev_fights, "mean", summarize_probability)[
            "combined_eval"
        ]["delta_log_loss"]
    else:
        raise ValueError(protocol)

    null_values = []
    market_loss_win = binary_loss(np.ones(len(df)), market)
    market_loss_loss = binary_loss(np.zeros(len(df)), market)
    candidate_loss_win = binary_loss(np.ones(len(df)), candidate_prob)
    candidate_loss_loss = binary_loss(np.zeros(len(df)), candidate_prob)
    folds = df["fold"].astype(int).to_numpy()
    years = df["year"].to_numpy()

    for _ in range(iterations):
        wins = rng.random(len(df)) < market
        delta = np.where(wins, market_loss_win - candidate_loss_win, market_loss_loss - candidate_loss_loss)
        if protocol == "2024_to_later":
            selected = select_candidate(candidates, delta, years == 2024, min_dev_fights, "mean")
            if selected is None:
                continue
            mask = (years >= 2025) & selected["mask"]
            if mask.any():
                null_values.append(float(delta[mask].mean()))
        else:
            eval_masks = []
            for fold in sorted(np.unique(folds)):
                if fold <= 1:
                    continue
                selected = select_candidate(candidates, delta, folds < fold, min_dev_fights, "mean")
                if selected is not None:
                    eval_masks.append((folds == fold) & selected["mask"])
            if eval_masks:
                mask = np.logical_or.reduce(eval_masks)
                if mask.any():
                    null_values.append(float(delta[mask].mean()))

    if not null_values or not np.isfinite(observed):
        return None
    null = np.asarray(null_values, dtype=float)
    return float((np.sum(null >= observed) + 1) / (len(null) + 1))


def bet_market_null(df, candidates, protocol: str, min_dev_bets: int, iterations: int, rng) -> float:
    market = df["selected_market_probability"].astype(float).to_numpy()
    win_profit = df["win_profit"].astype(float).to_numpy()
    actual_profit = df["flat_profit"].astype(float).to_numpy()
    years = df["year"].to_numpy()
    folds = df["fold"].astype(int).to_numpy()

    if protocol == "2024_to_later":
        observed_selected = select_candidate(candidates, actual_profit, years == 2024, min_dev_bets, "sum")
        observed_mask = (years >= 2025) & observed_selected["mask"]
        observed = float(actual_profit[observed_mask].sum()) if observed_mask.any() else np.nan
    elif protocol == "rolling":
        observed = rolling_selection(df, candidates, actual_profit, min_dev_bets, "sum", summarize_bets)[
            "combined_eval"
        ]["profit"]
    else:
        raise ValueError(protocol)

    null_values = []
    for _ in range(iterations):
        wins = rng.random(len(df)) < market
        profit = np.where(wins, win_profit, -1.0)
        if protocol == "2024_to_later":
            selected = select_candidate(candidates, profit, years == 2024, min_dev_bets, "sum")
            if selected is None:
                continue
            mask = (years >= 2025) & selected["mask"]
            if mask.any():
                null_values.append(float(profit[mask].sum()))
        else:
            eval_masks = []
            for fold in sorted(np.unique(folds)):
                if fold <= 1:
                    continue
                selected = select_candidate(candidates, profit, folds < fold, min_dev_bets, "sum")
                if selected is not None:
                    eval_masks.append((folds == fold) & selected["mask"])
            if eval_masks:
                mask = np.logical_or.reduce(eval_masks)
                if mask.any():
                    null_values.append(float(profit[mask].sum()))

    if not null_values or not np.isfinite(observed):
        return None
    null = np.asarray(null_values, dtype=float)
    return float((np.sum(null >= observed) + 1) / (len(null) + 1))


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    probabilities = prepare_probabilities(args.probabilities)
    bets = prepare_bets(args.ranked_bets)

    probability_candidates = candidate_masks(
        probabilities,
        ["market_bin", "abs_edge_bin", "edge_direction", "title_group"],
    )
    bet_candidates = candidate_masks(
        bets,
        ["market_bin", "edge_bin", "probability_bin", "title_group"],
    )

    probability_2024 = probability_2024_selection(
        probabilities,
        probability_candidates,
        args.min_dev_fights,
    )
    probability_rolling = rolling_selection(
        probabilities,
        probability_candidates,
        probabilities["delta_loss"].to_numpy(dtype=float),
        args.min_dev_fights,
        "mean",
        summarize_probability,
    )
    bet_2024 = bets_2024_selection(bets, bet_candidates, args.min_dev_bets)
    bet_rolling = rolling_selection(
        bets,
        bet_candidates,
        bets["flat_profit"].astype(float).to_numpy(),
        args.min_dev_bets,
        "sum",
        summarize_bets,
    )

    probability_2024["market_null_p"] = probability_market_null(
        probabilities,
        probability_candidates,
        "2024_to_later",
        args.min_dev_fights,
        args.market_null_iterations,
        rng,
    )
    probability_rolling["market_null_p"] = probability_market_null(
        probabilities,
        probability_candidates,
        "rolling",
        args.min_dev_fights,
        args.market_null_iterations,
        rng,
    )
    bet_2024["market_null_p"] = bet_market_null(
        bets,
        bet_candidates,
        "2024_to_later",
        args.min_dev_bets,
        args.market_null_iterations,
        rng,
    )
    bet_rolling["market_null_p"] = bet_market_null(
        bets,
        bet_candidates,
        "rolling",
        args.min_dev_bets,
        args.market_null_iterations,
        rng,
    )

    return {
        "probabilities_path": args.probabilities,
        "ranked_bets_path": args.ranked_bets,
        "probability_policy": "selected_shrinkage",
        "bet_policy": "frozen_residual_meta_top_edge_cap3",
        "min_dev_fights": args.min_dev_fights,
        "min_dev_bets": args.min_dev_bets,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "candidate_counts": {
            "probability": len(probability_candidates),
            "betting": len(bet_candidates),
        },
        "probability": {
            "selection_2024_to_2025_2026": probability_2024,
            "rolling_prior_fold_selection": probability_rolling,
        },
        "betting": {
            "selection_2024_to_2025_2026": bet_2024,
            "rolling_prior_fold_selection": bet_rolling,
        },
    }


def probability_eval_line(label: str, summary: dict) -> str:
    return "| {label} | {fights} | {market_ll} | {candidate_ll} | {delta} |".format(
        label=label,
        fights=summary["fights"],
        market_ll=fmt_float(summary["market_log_loss"]),
        candidate_ll=fmt_float(summary["candidate_log_loss"]),
        delta=fmt_float(summary["delta_log_loss"]),
    )


def bet_eval_line(label: str, summary: dict) -> str:
    return "| {label} | {bets} | {profit} | {roi} | {actual_market} |".format(
        label=label,
        bets=summary["bets"],
        profit=fmt_units(summary["profit"]),
        roi=fmt_pct(summary["roi"]),
        actual_market=fmt_pct(summary["actual_minus_market"]),
    )


def markdown_report(result: dict) -> str:
    prob_2024 = result["probability"]["selection_2024_to_2025_2026"]
    prob_roll = result["probability"]["rolling_prior_fold_selection"]
    bet_2024 = result["betting"]["selection_2024_to_2025_2026"]
    bet_roll = result["betting"]["rolling_prior_fold_selection"]
    latest_prob_fold = prob_roll["folds"][-1] if prob_roll["folds"] else None
    latest_bet_fold = bet_roll["folds"][-1] if bet_roll["folds"] else None
    bet_roll_selected = sorted(
        {
            f"{row['selected_family']}={row['selected_name']}"
            for row in bet_roll["folds"]
        }
    )

    lines = [
        "# Residual Slice Validation Audit",
        "",
        "This audit checks whether residual edge slices selected from earlier",
        "outcomes survive later periods. It is meant to guard against using",
        "full-sample slice tables as after-the-fact strategy tuning.",
        "",
        "## Inputs",
        "",
        f"- probability predictions: `{result['probabilities_path']}`",
        f"- capped-bet ledger: `{result['ranked_bets_path']}`",
        f"- probability policy: `{result['probability_policy']}`",
        f"- bet policy: `{result['bet_policy']}`",
        f"- probability candidate slices: `{result['candidate_counts']['probability']}`",
        f"- betting candidate slices: `{result['candidate_counts']['betting']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        "",
        "## Key Diagnostics",
        "",
        "- The 2024-selected probability slice did not validate: `{family}={name}` had 2024 delta LL `{dev_delta}` but 2025-2026 delta LL `{eval_delta}` and market-null p `{p_value}`.".format(
            family=prob_2024["selected"]["family"],
            name=prob_2024["selected"]["name"],
            dev_delta=fmt_float(prob_2024["dev_2024"]["delta_log_loss"]),
            eval_delta=fmt_float(prob_2024["eval_2025_2026"]["delta_log_loss"]),
            p_value=fmt_p(prob_2024["market_null_p"]),
        ),
        "- Rolling prior-fold probability selection was positive but thin: combined delta LL `{delta}` on `{fights}` fights, market-null p `{p_value}`, latest-fold delta `{latest_delta}`.".format(
            delta=fmt_float(prob_roll["combined_eval"]["delta_log_loss"]),
            fights=prob_roll["combined_eval"]["fights"],
            p_value=fmt_p(prob_roll["market_null_p"]),
            latest_delta=fmt_float(
                latest_prob_fold["eval_summary"]["delta_log_loss"] if latest_prob_fold else None
            ),
        ),
        "- The 2024-selected capped-bet slice was simply `all=all`, with 2025-2026 profit `{profit}` but last-365-day profit `{recent_profit}`.".format(
            profit=fmt_units(bet_2024["eval_2025_2026"]["profit"]),
            recent_profit=fmt_units(bet_2024["eval_last_365d"]["profit"]),
        ),
        "- Rolling prior-fold capped-bet selection chose {selected} and made `{profit}` with market-null p `{p_value}`, but the latest fold was `{latest_profit}`.".format(
            selected=", ".join(f"`{value}`" for value in bet_roll_selected),
            profit=fmt_units(bet_roll["combined_eval"]["profit"]),
            p_value=fmt_p(bet_roll["market_null_p"]),
            latest_profit=fmt_units(latest_bet_fold["eval_summary"]["profit"] if latest_bet_fold else None),
        ),
        "",
        "## 2024-Selected Probability Slice",
        "",
        "The selector chooses the candidate slice with the best 2024 mean",
        "market-minus-candidate log-loss delta, then evaluates it later.",
        "",
        f"Selected slice: `{prob_2024['selected']['family']}={prob_2024['selected']['name']}`",
        f"Market-null p-value on 2025-2026 evaluation: `{fmt_p(prob_2024['market_null_p'])}`",
        "",
        "| Period | Fights | Market LL | Candidate LL | Delta LL |",
        "| --- | ---: | ---: | ---: | ---: |",
        probability_eval_line("2024 development", prob_2024["dev_2024"]),
        probability_eval_line("2025-2026 evaluation", prob_2024["eval_2025_2026"]),
        probability_eval_line("last 365d evaluation", prob_2024["eval_last_365d"]),
        probability_eval_line("full same slice", prob_2024["aggregate_same_slice"]),
        "",
        "Top 2024 probability candidates:",
        "",
        "| Rank | Candidate | Dev Fights | Dev Delta LL |",
        "| ---: | --- | ---: | ---: |",
    ]
    for rank, row in enumerate(prob_2024["top_dev_candidates"], start=1):
        lines.append(
            f"| {rank} | `{row['family']}={row['name']}` | {row['count']} | {fmt_float(row['score'])} |"
        )

    lines.extend(
        [
            "",
            "## Rolling Prior-Fold Probability Selection",
            "",
            f"Market-null p-value: `{fmt_p(prob_roll['market_null_p'])}`",
            "",
            "| Eval Fold | Selected Slice | Dev Fights | Eval Fights | Dev Delta LL | Eval Delta LL |",
            "| ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in prob_roll["folds"]:
        lines.append(
            "| {fold} | `{family}={name}` | {dev_count} | {eval_count} | {dev_score} | {eval_score} |".format(
                fold=row["eval_fold"],
                family=row["selected_family"],
                name=row["selected_name"],
                dev_count=row["dev_count"],
                eval_count=row["eval_count"],
                dev_score=fmt_float(row["dev_score"]),
                eval_score=fmt_float(row["eval_summary"]["delta_log_loss"]),
            )
        )
    lines.extend(
        [
            "",
            "| Combined Rolling Eval | Fights | Market LL | Candidate LL | Delta LL |",
            "| --- | ---: | ---: | ---: | ---: |",
            probability_eval_line("selected slices", prob_roll["combined_eval"]),
            "",
            "## 2024-Selected Capped-Bet Slice",
            "",
            "The selector chooses the candidate slice with the best 2024 flat profit,",
            "then evaluates it later.",
            "",
            f"Selected slice: `{bet_2024['selected']['family']}={bet_2024['selected']['name']}`",
            f"Market-null p-value on 2025-2026 evaluation: `{fmt_p(bet_2024['market_null_p'])}`",
            "",
            "| Period | Bets | Profit | ROI | Actual - Market |",
            "| --- | ---: | ---: | ---: | ---: |",
            bet_eval_line("2024 development", bet_2024["dev_2024"]),
            bet_eval_line("2025-2026 evaluation", bet_2024["eval_2025_2026"]),
            bet_eval_line("last 365d evaluation", bet_2024["eval_last_365d"]),
            bet_eval_line("full same slice", bet_2024["aggregate_same_slice"]),
            "",
            "Top 2024 betting candidates:",
            "",
            "| Rank | Candidate | Dev Bets | Dev Profit |",
            "| ---: | --- | ---: | ---: |",
        ]
    )
    for rank, row in enumerate(bet_2024["top_dev_candidates"], start=1):
        lines.append(
            f"| {rank} | `{row['family']}={row['name']}` | {row['count']} | {fmt_units(row['score'])} |"
        )

    lines.extend(
        [
            "",
            "## Rolling Prior-Fold Capped-Bet Selection",
            "",
            f"Market-null p-value: `{fmt_p(bet_roll['market_null_p'])}`",
            "",
            "| Eval Fold | Selected Slice | Dev Bets | Eval Bets | Dev Profit | Eval Profit |",
            "| ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in bet_roll["folds"]:
        lines.append(
            "| {fold} | `{family}={name}` | {dev_count} | {eval_count} | {dev_score} | {eval_score} |".format(
                fold=row["eval_fold"],
                family=row["selected_family"],
                name=row["selected_name"],
                dev_count=row["dev_count"],
                eval_count=row["eval_count"],
                dev_score=fmt_units(row["dev_score"]),
                eval_score=fmt_units(row["eval_summary"]["profit"]),
            )
        )
    lines.extend(
        [
            "",
            "| Combined Rolling Eval | Bets | Profit | ROI | Actual - Market |",
            "| --- | ---: | ---: | ---: | ---: |",
            bet_eval_line("selected slices", bet_roll["combined_eval"]),
            "",
            "## Interpretation",
            "",
            "- Prior-period slice selection does not create a strong live-edge claim.",
            "- Any positive selected-slice result here is still historical and has only a few evaluation folds.",
            "- Treat this as a guardrail against full-sample slice tuning: useful for deciding what to paper-track, not evidence for staking up.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_slice_validation_audit.json"
    md_path = output_dir / "residual_slice_validation_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    prob = result["probability"]["rolling_prior_fold_selection"]["combined_eval"]
    bet = result["betting"]["rolling_prior_fold_selection"]["combined_eval"]
    print(f"Rolling selected probability delta LL: {prob['delta_log_loss']:.4f}")
    print(f"Rolling selected capped-bet profit: {bet['profit']:+.2f}u")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
