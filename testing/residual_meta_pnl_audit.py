#!/usr/bin/env python3
"""Nested PnL audit for residual market/meta probabilities.

This test asks whether the residual probability signal can be converted into a
simple flat-stake betting rule. It trains only a small residual meta layer from
saved leak-safe ledgers, selects thresholds on out-of-sample development
probabilities, then freezes those thresholds for the next holdout window.
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

from testing.market_residual_meta_audit import EPS, fit_predict, logit  # noqa: E402
from testing.statistical_edge_audit import implied_prob, net_odds, parse_odds  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_THRESHOLDS = [0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12]
DEFAULT_MIN_PROBABILITIES = [0.50, 0.55, 0.60, 0.65]
DEFAULT_MAX_UNDERDOG_ODDS = [300.0, None]


@dataclass(frozen=True)
class MetaBetPolicy:
    min_edge: float
    min_probability: float
    max_underdog_odds: Optional[float]


@dataclass(frozen=True)
class FoldSpec:
    fold_index: int
    dev_start: pd.Timestamp
    dev_end: pd.Timestamp
    inner_train_end: pd.Timestamp
    policy_dev_start: pd.Timestamp
    holdout_start: pd.Timestamp
    holdout_end: pd.Timestamp
    inner_train_indices: np.ndarray
    policy_dev_indices: np.ndarray
    dev_indices: np.ndarray
    holdout_indices: np.ndarray


def parse_args():
    parser = argparse.ArgumentParser(description="Nested residual-meta PnL audit")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="model label and saved no_leakage_backtest.csv path",
    )
    parser.add_argument("--model-label", default="regularized_lgbm")
    parser.add_argument("--first-holdout-start", default="2024-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--inner-train-days", type=int, default=365)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-inner-train-fights", type=int, default=150)
    parser.add_argument("--min-policy-dev-fights", type=int, default=80)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--min-policy-dev-bets", type=int, default=12)
    parser.add_argument(
        "--selection-objective",
        choices=["profit", "roi", "market_edge"],
        default="profit",
    )
    parser.add_argument("--c", type=float, default=0.25)
    parser.add_argument("--threshold", action="append", type=float)
    parser.add_argument("--min-probability", action="append", type=float)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_meta_pnl_audit")
    return parser.parse_args()


def fight_key(event_date, left_name, right_name) -> str:
    event_text = "" if pd.isna(event_date) else pd.Timestamp(event_date).date().isoformat()
    fighters = sorted([canonical_name(left_name), canonical_name(right_name)])
    return "|".join([event_text, *fighters])


def load_ledger_rows(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    rows = []
    for _, row in df.iterrows():
        event_date = pd.to_datetime(row.get("event_date"), errors="coerce")
        red_key = canonical_name(row.get("red_fighter", ""))
        blue_key = canonical_name(row.get("blue_fighter", ""))
        winner_key = canonical_name(row.get("winner_name", ""))
        fighter1_key = canonical_name(row.get("odds_fighter1_name", ""))
        fighter2_key = canonical_name(row.get("odds_fighter2_name", ""))

        odds1 = parse_odds(row.get("fighter1_odds"))
        odds2 = parse_odds(row.get("fighter2_odds"))
        raw1 = implied_prob(odds1)
        raw2 = implied_prob(odds2)
        vig_sum = raw1 + raw2 if np.isfinite(raw1) and np.isfinite(raw2) else np.nan
        if not np.isfinite(vig_sum) or vig_sum <= 0:
            continue

        market1 = raw1 / vig_sum
        market2 = raw2 / vig_sum
        if red_key == fighter1_key:
            red_market = market1
            blue_market = market2
            red_odds = odds1
            blue_odds = odds2
        elif red_key == fighter2_key:
            red_market = market2
            blue_market = market1
            red_odds = odds2
            blue_odds = odds1
        else:
            continue

        try:
            red_model = float(row.get("red_win_probability"))
        except (TypeError, ValueError):
            continue
        if not np.isfinite(red_model):
            continue

        rows.append(
            {
                "fight_key": fight_key(event_date, red_key, blue_key),
                "event_date": event_date,
                "title": row.get("title", ""),
                "red_fighter": row.get("red_fighter", ""),
                "blue_fighter": row.get("blue_fighter", ""),
                "winner_name": row.get("winner_name", ""),
                "red_key": red_key,
                "blue_key": blue_key,
                "winner_key": winner_key,
                "red_won": bool(winner_key == red_key),
                "red_market_probability": float(red_market),
                "blue_market_probability": float(blue_market),
                "red_odds": float(red_odds),
                "blue_odds": float(blue_odds),
                f"{label}_red_model_probability": float(np.clip(red_model, EPS, 1.0 - EPS)),
            }
        )

    return pd.DataFrame(rows).dropna(subset=["event_date"])


def load_aligned_ledgers(ledger_args: list[list[str]]) -> tuple[pd.DataFrame, list[str]]:
    labels = [label for label, _ in ledger_args]
    frames = [load_ledger_rows(Path(csv_path), label) for label, csv_path in ledger_args]
    for label, frame in zip(labels, frames):
        if frame.empty:
            raise SystemExit(f"No comparable rows loaded for {label}")

    base_columns = [
        "fight_key",
        "event_date",
        "title",
        "red_fighter",
        "blue_fighter",
        "winner_name",
        "red_key",
        "blue_key",
        "winner_key",
        "red_won",
        "red_market_probability",
        "blue_market_probability",
        "red_odds",
        "blue_odds",
    ]
    merged = frames[0][base_columns + [f"{labels[0]}_red_model_probability"]].copy()
    for label, frame in zip(labels[1:], frames[1:]):
        merged = merged.merge(
            frame[["fight_key", f"{label}_red_model_probability"]],
            on="fight_key",
            how="inner",
            validate="one_to_one",
        )

    merged = merged.sort_values(["event_date", "fight_key"]).reset_index(drop=True)
    merged["market_logit"] = logit(merged["red_market_probability"])
    for label in labels:
        model_col = f"{label}_red_model_probability"
        merged[f"{label}_logit_delta"] = logit(merged[model_col]) - merged["market_logit"]
    return merged, labels


def iter_folds(
    df: pd.DataFrame,
    first_holdout_start: str,
    last_holdout_end: str,
    dev_days: int,
    inner_train_days: int,
    holdout_days: int,
    step_days: int,
    min_inner_train_fights: int,
    min_policy_dev_fights: int,
    min_holdout_fights: int,
) -> list[FoldSpec]:
    dates = df["event_date"].to_numpy(dtype="datetime64[ns]")
    current = pd.Timestamp(first_holdout_start)
    last = pd.Timestamp(last_holdout_end)
    folds = []
    fold_index = 1
    while current <= last:
        dev_start = current - pd.Timedelta(days=dev_days)
        dev_end = current - pd.Timedelta(days=1)
        inner_train_end = min(dev_start + pd.Timedelta(days=inner_train_days - 1), dev_end)
        policy_dev_start = inner_train_end + pd.Timedelta(days=1)
        holdout_end = min(current + pd.Timedelta(days=holdout_days - 1), last)

        inner_mask = (dates >= np.datetime64(dev_start)) & (dates <= np.datetime64(inner_train_end))
        policy_dev_mask = (dates >= np.datetime64(policy_dev_start)) & (dates <= np.datetime64(dev_end))
        dev_mask = (dates >= np.datetime64(dev_start)) & (dates <= np.datetime64(dev_end))
        holdout_mask = (dates >= np.datetime64(current)) & (dates <= np.datetime64(holdout_end))
        inner_indices = np.flatnonzero(inner_mask)
        policy_dev_indices = np.flatnonzero(policy_dev_mask)
        dev_indices = np.flatnonzero(dev_mask)
        holdout_indices = np.flatnonzero(holdout_mask)

        if (
            len(inner_indices) >= min_inner_train_fights
            and len(policy_dev_indices) >= min_policy_dev_fights
            and len(holdout_indices) >= min_holdout_fights
        ):
            folds.append(
                FoldSpec(
                    fold_index=fold_index,
                    dev_start=dev_start,
                    dev_end=dev_end,
                    inner_train_end=inner_train_end,
                    policy_dev_start=policy_dev_start,
                    holdout_start=current,
                    holdout_end=holdout_end,
                    inner_train_indices=inner_indices,
                    policy_dev_indices=policy_dev_indices,
                    dev_indices=dev_indices,
                    holdout_indices=holdout_indices,
                )
            )
        fold_index += 1
        current += pd.Timedelta(days=step_days)
    return folds


def policy_grid(thresholds: list[float], min_probabilities: list[float]):
    for min_edge, min_probability, max_underdog_odds in itertools.product(
        thresholds,
        min_probabilities,
        DEFAULT_MAX_UNDERDOG_ODDS,
    ):
        yield MetaBetPolicy(min_edge, min_probability, max_underdog_odds)


def predict_meta_rows(
    df: pd.DataFrame,
    train_indices: np.ndarray,
    eval_indices: np.ndarray,
    feature_columns: list[str],
    c_value: float,
    y_values: np.ndarray,
) -> pd.DataFrame:
    x = df[feature_columns].astype(float).to_numpy()
    probabilities, _ = fit_predict(
        x[train_indices],
        y_values[train_indices],
        x[eval_indices],
        c_value,
    )
    rows = df.iloc[eval_indices].copy()
    rows["meta_red_probability"] = probabilities
    rows["meta_blue_probability"] = 1.0 - rows["meta_red_probability"]
    return rows


def net_odds_array(odds: np.ndarray) -> np.ndarray:
    return np.where(odds >= 0.0, odds / 100.0, 100.0 / -odds)


def policy_arrays(predictions: pd.DataFrame, policy: MetaBetPolicy, y_values: np.ndarray | None = None) -> dict:
    index = predictions.index.to_numpy(dtype=int)
    if y_values is None:
        red_won = predictions["red_won"].astype(bool).to_numpy()
    else:
        red_won = np.asarray(y_values, dtype=bool)[index]

    red_probability = predictions["meta_red_probability"].astype(float).to_numpy()
    blue_probability = 1.0 - red_probability
    red_market = predictions["red_market_probability"].astype(float).to_numpy()
    blue_market = predictions["blue_market_probability"].astype(float).to_numpy()
    red_odds = predictions["red_odds"].astype(float).to_numpy()
    blue_odds = predictions["blue_odds"].astype(float).to_numpy()
    red_edge = red_probability - red_market
    blue_edge = blue_probability - blue_market

    red_valid = (
        np.isfinite(red_odds)
        & np.isfinite(red_probability)
        & np.isfinite(red_market)
        & (red_edge >= policy.min_edge)
        & (red_probability >= policy.min_probability)
    )
    blue_valid = (
        np.isfinite(blue_odds)
        & np.isfinite(blue_probability)
        & np.isfinite(blue_market)
        & (blue_edge >= policy.min_edge)
        & (blue_probability >= policy.min_probability)
    )
    if policy.max_underdog_odds is not None:
        red_valid &= red_odds <= policy.max_underdog_odds
        blue_valid &= blue_odds <= policy.max_underdog_odds

    choose_red = red_valid & (
        ~blue_valid
        | (red_edge > blue_edge)
        | ((red_edge == blue_edge) & (red_probability >= blue_probability))
    )
    choose_blue = blue_valid & ~choose_red
    selected = choose_red | choose_blue

    selected_side = np.where(choose_red, "red", "blue")
    selected_probability = np.where(choose_red, red_probability, blue_probability)
    selected_market = np.where(choose_red, red_market, blue_market)
    selected_edge = np.where(choose_red, red_edge, blue_edge)
    selected_odds = np.where(choose_red, red_odds, blue_odds)
    selected_won = np.where(choose_red, red_won, ~red_won)
    flat_profit = np.where(selected_won, net_odds_array(selected_odds), -1.0)

    return {
        "selected": selected,
        "selected_side": selected_side,
        "selected_probability": selected_probability,
        "selected_market_probability": selected_market,
        "selected_edge": selected_edge,
        "selected_odds": selected_odds,
        "selected_won": selected_won,
        "flat_profit": flat_profit,
    }


def bets_dataframe(predictions: pd.DataFrame, arrays: dict) -> pd.DataFrame:
    mask = arrays["selected"]
    if not np.any(mask):
        return pd.DataFrame()
    selected_rows = predictions.loc[mask].copy()
    side = arrays["selected_side"][mask]
    selected_rows["event_date"] = selected_rows["event_date"].dt.date.astype(str)
    selected_rows["selected_side"] = side
    selected_rows["bet_on"] = np.where(side == "red", selected_rows["red_fighter"], selected_rows["blue_fighter"])
    selected_rows["selected_odds"] = arrays["selected_odds"][mask]
    selected_rows["selected_probability"] = arrays["selected_probability"][mask]
    selected_rows["selected_market_probability"] = arrays["selected_market_probability"][mask]
    selected_rows["selected_edge"] = arrays["selected_edge"][mask]
    selected_rows["selected_won"] = arrays["selected_won"][mask]
    selected_rows["flat_profit"] = arrays["flat_profit"][mask]
    selected_rows["market_red_probability"] = selected_rows["red_market_probability"]
    return selected_rows[
        [
            "event_date",
            "fight_key",
            "title",
            "red_fighter",
            "blue_fighter",
            "winner_name",
            "red_won",
            "meta_red_probability",
            "market_red_probability",
            "selected_side",
            "bet_on",
            "selected_odds",
            "selected_probability",
            "selected_market_probability",
            "selected_edge",
            "selected_won",
            "flat_profit",
        ]
    ].reset_index(drop=True)


def summarize_arrays(fights: int, arrays: dict) -> dict:
    mask = arrays["selected"]
    if not np.any(mask):
        return {
            "fights": int(fights),
            "bets": 0,
            "events_with_bets": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_probability": None,
            "mean_market_probability": None,
            "mean_edge": None,
            "actual_minus_market": None,
        }
    actual = float(arrays["selected_won"][mask].astype(float).mean())
    mean_market = float(arrays["selected_market_probability"][mask].mean())
    return {
        "fights": int(fights),
        "bets": int(mask.sum()),
        "events_with_bets": None,
        "profit": float(arrays["flat_profit"][mask].sum()),
        "roi": float(arrays["flat_profit"][mask].mean()),
        "actual_win_rate": actual,
        "mean_probability": float(arrays["selected_probability"][mask].mean()),
        "mean_market_probability": mean_market,
        "mean_edge": float(arrays["selected_edge"][mask].mean()),
        "actual_minus_market": actual - mean_market,
    }


def objective_score(summary: dict, min_bets: int, objective: str) -> tuple:
    if summary["bets"] < min_bets:
        return (-math.inf,)
    roi = summary["roi"] if summary["roi"] is not None else -math.inf
    market_edge = summary["actual_minus_market"] if summary["actual_minus_market"] is not None else -math.inf
    if objective == "roi":
        return (roi, summary["profit"], market_edge, summary["bets"])
    if objective == "market_edge":
        return (market_edge, roi, summary["profit"], summary["bets"])
    return (summary["profit"], roi, market_edge, summary["bets"])


def evaluate_policy(
    predictions: pd.DataFrame,
    policy: MetaBetPolicy,
    y_values=None,
    write_bets: bool = True,
) -> tuple[pd.DataFrame, dict]:
    arrays = policy_arrays(predictions, policy, y_values=y_values)
    summary = summarize_arrays(len(predictions), arrays)
    if summary["bets"] and write_bets:
        bets = bets_dataframe(predictions, arrays)
        summary["events_with_bets"] = int(bets["event_date"].nunique())
    else:
        bets = pd.DataFrame()
        if summary["bets"]:
            event_dates = predictions.loc[arrays["selected"], "event_date"].dt.date
            summary["events_with_bets"] = int(event_dates.nunique())
        else:
            summary["events_with_bets"] = 0
    return bets, summary


def select_policy(
    predictions: pd.DataFrame,
    policies: list[MetaBetPolicy],
    min_bets: int,
    objective: str,
    y_values=None,
) -> tuple[MetaBetPolicy | None, list[dict]]:
    candidates = []
    best_policy = None
    best_score = (-math.inf,)
    for policy in policies:
        _, summary = evaluate_policy(predictions, policy, y_values=y_values, write_bets=False)
        score = objective_score(summary, min_bets, objective)
        item = {
            "policy": asdict(policy),
            "summary": summary,
            "score": list(score),
        }
        candidates.append(item)
        if score > best_score:
            best_score = score
            best_policy = policy
    candidates.sort(key=lambda item: item["score"], reverse=True)
    if best_score[0] == -math.inf:
        return None, candidates
    return best_policy, candidates


def aggregate_folds(folds: list[dict], selected_holdout_bets: pd.DataFrame) -> dict:
    if selected_holdout_bets.empty:
        profit = 0.0
        bets = 0
        roi = None
        actual = None
        mean_market = None
    else:
        profit = float(selected_holdout_bets["flat_profit"].astype(float).sum())
        bets = int(len(selected_holdout_bets))
        roi = float(selected_holdout_bets["flat_profit"].astype(float).mean())
        actual = float(selected_holdout_bets["selected_won"].astype(float).mean())
        mean_market = float(selected_holdout_bets["selected_market_probability"].astype(float).mean())
    return {
        "folds": int(len(folds)),
        "fights": int(sum(fold["holdout_summary"]["fights"] for fold in folds)),
        "bets": bets,
        "events_with_bets": int(selected_holdout_bets["event_date"].nunique()) if not selected_holdout_bets.empty else 0,
        "profit": profit,
        "roi": roi,
        "actual_win_rate": actual,
        "mean_market_probability": mean_market,
        "actual_minus_market": None if actual is None or mean_market is None else actual - mean_market,
        "positive_folds": int(sum(fold["holdout_summary"]["profit"] > 0 for fold in folds)),
        "selected_policies": dict(Counter(json.dumps(fold["selected_policy"], sort_keys=True) for fold in folds)),
    }


def event_bootstrap(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty or iterations <= 0:
        return None
    grouped = bets.groupby("event_date", sort=True)["flat_profit"].sum().to_numpy(dtype=float)
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    profits = grouped[sampled].sum(axis=1)
    return {
        "events": int(len(grouped)),
        "iterations": int(iterations),
        "profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(profits <= 0.0)),
    }


def market_null_simulation(
    df: pd.DataFrame,
    folds: list[FoldSpec],
    policies: list[MetaBetPolicy],
    feature_columns: list[str],
    observed_profit: float,
    iterations: int,
    c_value: float,
    min_bets: int,
    objective: str,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    profits = np.empty(iterations, dtype=float)
    selected_policy_counts = Counter()
    for iteration in range(iterations):
        simulated_y = rng.random(len(df)) < market
        aggregate_profit = 0.0
        for fold in folds:
            policy_dev_predictions = predict_meta_rows(
                df,
                fold.inner_train_indices,
                fold.policy_dev_indices,
                feature_columns,
                c_value,
                simulated_y,
            )
            selected_policy, _ = select_policy(
                policy_dev_predictions,
                policies,
                min_bets,
                objective,
                y_values=simulated_y,
            )
            if selected_policy is None:
                continue
            selected_policy_counts[json.dumps(asdict(selected_policy), sort_keys=True)] += 1
            holdout_predictions = predict_meta_rows(
                df,
                fold.dev_indices,
                fold.holdout_indices,
                feature_columns,
                c_value,
                simulated_y,
            )
            bets, _ = evaluate_policy(holdout_predictions, selected_policy, y_values=simulated_y)
            if not bets.empty:
                aggregate_profit += float(bets["flat_profit"].astype(float).sum())
        profits[iteration] = aggregate_profit
    return {
        "iterations": int(iterations),
        "observed_profit": float(observed_profit),
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed_profit) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0.0)),
        "selected_policy_counts": dict(selected_policy_counts.most_common(20)),
    }


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


def policy_label(policy: dict) -> str:
    max_dog = "none" if policy["max_underdog_odds"] is None else f"+{policy['max_underdog_odds']:.0f}"
    return (
        f"edge>={policy['min_edge']:.2f}, "
        f"p>={policy['min_probability']:.2f}, "
        f"max dog {max_dog}"
    )


def markdown_report(result: dict) -> str:
    aggregate = result["aggregate"]
    bootstrap = result.get("event_bootstrap") or {}
    market_null = result.get("market_null") or {}
    lines = [
        "# Residual Meta PnL Audit",
        "",
        "This audit tests whether the residual market/meta probability signal can",
        "be converted into a simple flat-stake betting rule without using holdout",
        "outcomes for threshold selection.",
        "",
        "## Protocol",
        "",
        f"- model residual: `{result['model_label']}`",
        f"- meta feature columns: `{', '.join(result['feature_columns'])}`",
        f"- outer development window: `{result['dev_days']}` days",
        f"- inner meta-training window: `{result['inner_train_days']}` days",
        f"- holdout window: `{result['holdout_days']}` days",
        f"- meta logistic C: `{result['c']}`",
        f"- selection objective: `{result['selection_objective']}`",
        "",
        "Within each outer fold, the first part of the development window fits the",
        "meta layer, the second part selects betting thresholds using out-of-sample",
        "meta probabilities, and the selected policy is then frozen onto the outer",
        "holdout.",
        "",
        "## Aggregate Holdout",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| folds | {aggregate['folds']} |",
        f"| holdout fights | {aggregate['fights']} |",
        f"| bets | {aggregate['bets']} |",
        f"| events with bets | {aggregate['events_with_bets']} |",
        f"| flat profit | {fmt_units(aggregate['profit'])} |",
        f"| flat ROI | {fmt_pct(aggregate['roi'])} |",
        f"| actual win rate | {fmt_pct(aggregate['actual_win_rate'])} |",
        f"| mean market probability | {fmt_pct(aggregate['mean_market_probability'])} |",
        f"| actual - market | {fmt_pct(aggregate['actual_minus_market'])} |",
        f"| positive folds | {aggregate['positive_folds']} / {aggregate['folds']} |",
        f"| event-bootstrap P(profit <= 0) | {fmt_p(bootstrap.get('prob_profit_le_zero'))} |",
        f"| selection-adjusted market-null p-value | {fmt_p(market_null.get('p_value_observed_or_better'))} |",
        "",
    ]
    if market_null:
        lines.extend(
            [
                "## Market Null",
                "",
                "This null simulates outcomes from de-vigged market probabilities and",
                "reruns the full inner meta-training, threshold selection, and outer",
                "holdout evaluation loop.",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| iterations | {market_null['iterations']} |",
                f"| observed profit | {fmt_units(market_null['observed_profit'])} |",
                f"| null mean profit | {fmt_units(market_null['null_mean_profit'])} |",
                f"| null 95% interval | {fmt_units(market_null['null_profit_ci_95'][0])} to {fmt_units(market_null['null_profit_ci_95'][1])} |",
                f"| p-value observed or better | {fmt_p(market_null['p_value_observed_or_better'])} |",
                f"| probability null profitable | {fmt_p(market_null['prob_null_profitable'])} |",
                "",
            ]
        )
    lines.extend(
        [
            "## Fold Results",
            "",
            "| Fold | Policy-Dev Window | Holdout Window | Selected Policy | Dev Bets | Dev Profit | Holdout Bets | Holdout Profit | Holdout ROI |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for fold in result["folds"]:
        lines.append(
            "| {fold} | {dev_start} to {dev_end} | {holdout_start} to {holdout_end} | {policy} | {dev_bets} | {dev_profit} | {holdout_bets} | {holdout_profit} | {holdout_roi} |".format(
                fold=fold["fold"],
                dev_start=fold["policy_dev_start"],
                dev_end=fold["dev_end"],
                holdout_start=fold["holdout_start"],
                holdout_end=fold["holdout_end"],
                policy=policy_label(fold["selected_policy"]),
                dev_bets=fold["policy_dev_summary"]["bets"],
                dev_profit=fmt_units(fold["policy_dev_summary"]["profit"]),
                holdout_bets=fold["holdout_summary"]["bets"],
                holdout_profit=fmt_units(fold["holdout_summary"]["profit"]),
                holdout_roi=fmt_pct(fold["holdout_summary"]["roi"]),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A positive result here would support turning the residual probability",
            "signal into a predeclared betting policy. A weak or negative result",
            "means the probability edge is not yet clearly monetizable after vig,",
            "threshold selection, and schedule variance.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    df, labels = load_aligned_ledgers(args.ledger)
    if args.model_label not in labels:
        raise SystemExit(f"model label {args.model_label!r} not found in ledgers: {labels}")

    feature_columns = ["market_logit", f"{args.model_label}_logit_delta"]
    thresholds = args.threshold or DEFAULT_THRESHOLDS
    min_probabilities = args.min_probability or DEFAULT_MIN_PROBABILITIES
    policies = list(policy_grid(thresholds, min_probabilities))
    folds = iter_folds(
        df,
        args.first_holdout_start,
        args.last_holdout_end,
        args.dev_days,
        args.inner_train_days,
        args.holdout_days,
        args.step_days,
        args.min_inner_train_fights,
        args.min_policy_dev_fights,
        args.min_holdout_fights,
    )
    if not folds:
        raise SystemExit("No folds met minimum data constraints")

    observed_y = df["red_won"].astype(bool).to_numpy()
    fold_results = []
    selected_holdouts = []
    for fold in folds:
        policy_dev_predictions = predict_meta_rows(
            df,
            fold.inner_train_indices,
            fold.policy_dev_indices,
            feature_columns,
            args.c,
            observed_y,
        )
        selected_policy, candidates = select_policy(
            policy_dev_predictions,
            policies,
            args.min_policy_dev_bets,
            args.selection_objective,
        )
        if selected_policy is None:
            continue
        holdout_predictions = predict_meta_rows(
            df,
            fold.dev_indices,
            fold.holdout_indices,
            feature_columns,
            args.c,
            observed_y,
        )
        holdout_bets, holdout_summary = evaluate_policy(holdout_predictions, selected_policy)
        policy_dev_bets, policy_dev_summary = evaluate_policy(policy_dev_predictions, selected_policy)
        if not holdout_bets.empty:
            holdout_bets = holdout_bets.copy()
            holdout_bets["fold"] = fold.fold_index
            selected_holdouts.append(holdout_bets)
        fold_results.append(
            {
                "fold": fold.fold_index,
                "dev_start": fold.dev_start.date().isoformat(),
                "inner_train_end": fold.inner_train_end.date().isoformat(),
                "policy_dev_start": fold.policy_dev_start.date().isoformat(),
                "dev_end": fold.dev_end.date().isoformat(),
                "holdout_start": fold.holdout_start.date().isoformat(),
                "holdout_end": fold.holdout_end.date().isoformat(),
                "inner_train_fights": int(len(fold.inner_train_indices)),
                "policy_dev_fights": int(len(fold.policy_dev_indices)),
                "holdout_fights": int(len(fold.holdout_indices)),
                "selected_policy": asdict(selected_policy),
                "policy_dev_summary": policy_dev_summary,
                "holdout_summary": holdout_summary,
                "top_policy_dev_candidates": candidates[:10],
            }
        )

    selected_holdout_bets = (
        pd.concat(selected_holdouts, ignore_index=True)
        if selected_holdouts
        else pd.DataFrame()
    )
    aggregate = aggregate_folds(fold_results, selected_holdout_bets)
    bootstrap = event_bootstrap(selected_holdout_bets, args.iterations, rng)
    market_null = market_null_simulation(
        df,
        folds,
        policies,
        feature_columns,
        aggregate["profit"],
        args.market_null_iterations,
        args.c,
        args.min_policy_dev_bets,
        args.selection_objective,
        rng,
    )
    result = {
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in args.ledger],
        "model_label": args.model_label,
        "feature_columns": feature_columns,
        "aligned_fights": int(len(df)),
        "first_holdout_start": args.first_holdout_start,
        "last_holdout_end": args.last_holdout_end,
        "dev_days": args.dev_days,
        "inner_train_days": args.inner_train_days,
        "holdout_days": args.holdout_days,
        "step_days": args.step_days,
        "min_policy_dev_bets": args.min_policy_dev_bets,
        "selection_objective": args.selection_objective,
        "c": args.c,
        "thresholds": thresholds,
        "min_probabilities": min_probabilities,
        "bootstrap_iterations": args.iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "aggregate": aggregate,
        "event_bootstrap": bootstrap,
        "market_null": market_null,
        "folds": fold_results,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_meta_pnl_audit.json"
    md_path = output_dir / "residual_meta_pnl_audit.md"
    csv_path = output_dir / "selected_holdout_bets.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    selected_holdout_bets.to_csv(csv_path, index=False)

    print(f"Folds: {aggregate['folds']}")
    print(f"Holdout bets: {aggregate['bets']}")
    print(f"Holdout profit: {fmt_units(aggregate['profit'])}")
    print(f"Holdout ROI: {fmt_pct(aggregate['roi'])}")
    print(f"Market-null p-value: {fmt_p((market_null or {}).get('p_value_observed_or_better'))}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
