#!/usr/bin/env python3
"""Recency stress tests for the residual probability and capped-PnL edge.

The strongest current evidence is the model-after-market residual signal and
the frozen cap-3 residual paper policy. This audit checks whether that evidence
survives recent-only slices, rather than being carried by early 2024.
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

PROBABILITY_POLICIES = (
    ("selected_shrinkage", "selected_probability"),
    ("fixed_half_residual", "fixed_half_probability"),
    ("unshrunk_meta", "unshrunk_probability"),
)


def parse_args():
    parser = argparse.ArgumentParser(description="Stress residual edge by recent time slices")
    parser.add_argument("--probabilities", default=DEFAULT_PROBABILITIES)
    parser.add_argument("--ranked-bets", default=DEFAULT_RANKED_BETS)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_recent_stress_audit")
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


def binary_loss(y_true: np.ndarray, probability: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1.0 - 1e-6)
    y = np.asarray(y_true, dtype=float)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def event_bootstrap(values: np.ndarray, event_keys: np.ndarray, iterations: int, rng) -> dict:
    if len(values) == 0:
        return {"p_le_zero": None, "ci_95": [None, None]}

    by_event = pd.DataFrame({"event": event_keys, "value": values}).groupby("event")["value"].sum()
    event_values = by_event.to_numpy(dtype=float)
    if len(event_values) == 0:
        return {"p_le_zero": None, "ci_95": [None, None]}

    samples = np.zeros(iterations, dtype=float)
    for index in range(iterations):
        sampled = rng.integers(0, len(event_values), size=len(event_values))
        samples[index] = float(event_values[sampled].sum())

    return {
        "p_le_zero": float((np.sum(samples <= 0.0) + 1) / (iterations + 1)),
        "ci_95": [float(value) for value in np.percentile(samples, [2.5, 97.5])],
    }


def event_bootstrap_mean(values: np.ndarray, event_keys: np.ndarray, iterations: int, rng) -> dict:
    result = event_bootstrap(values, event_keys, iterations, rng)
    if result["ci_95"][0] is not None:
        n = len(values)
        result["ci_95_mean"] = [float(value) / n for value in result["ci_95"]]
    else:
        result["ci_95_mean"] = [None, None]
    return result


def american_win_profit(odds: np.ndarray) -> np.ndarray:
    odds = np.asarray(odds, dtype=float)
    return np.where(odds > 0.0, odds / 100.0, 100.0 / np.abs(odds))


def period_specs(max_fold: int) -> list[dict]:
    return [
        {"name": "aggregate", "label": "aggregate", "start": None, "end": None, "fold": None},
        {"name": "2024", "label": "calendar 2024", "start": "2024-01-01", "end": "2024-12-31", "fold": None},
        {"name": "2025", "label": "calendar 2025", "start": "2025-01-01", "end": "2025-12-31", "fold": None},
        {"name": "2026", "label": "calendar 2026", "start": "2026-01-01", "end": "2026-12-31", "fold": None},
        {"name": "post_2024", "label": "2025-2026 only", "start": "2025-01-01", "end": None, "fold": None},
        {"name": "last_365d", "label": "last 365 days", "start": "2025-06-28", "end": None, "fold": None},
        {"name": "latest_fold", "label": f"latest fold {max_fold}", "start": None, "end": None, "fold": max_fold},
    ]


def apply_period(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if spec["start"] is not None:
        mask &= df["event_date"] >= pd.Timestamp(spec["start"])
    if spec["end"] is not None:
        mask &= df["event_date"] <= pd.Timestamp(spec["end"])
    if spec["fold"] is not None:
        mask &= df["fold"].astype(int) == int(spec["fold"])
    return df[mask].copy()


def market_null_probability_pvalue(
    y_market_prob: np.ndarray,
    market_loss_win: np.ndarray,
    market_loss_loss: np.ndarray,
    candidate_loss_win: np.ndarray,
    candidate_loss_loss: np.ndarray,
    observed_delta: float,
    iterations: int,
    rng,
) -> float | None:
    if len(y_market_prob) == 0:
        return None
    samples = np.zeros(iterations, dtype=float)
    for index in range(iterations):
        wins = rng.random(len(y_market_prob)) < y_market_prob
        market_loss = np.where(wins, market_loss_win, market_loss_loss).mean()
        candidate_loss = np.where(wins, candidate_loss_win, candidate_loss_loss).mean()
        samples[index] = market_loss - candidate_loss
    return float((np.sum(samples >= observed_delta) + 1) / (iterations + 1))


def summarize_probability_period(
    df: pd.DataFrame,
    policy_name: str,
    probability_column: str,
    bootstrap_iterations: int,
    market_null_iterations: int,
    rng,
) -> dict:
    if df.empty:
        return {
            "policy": policy_name,
            "fights": 0,
            "events": 0,
            "market_log_loss": None,
            "candidate_log_loss": None,
            "delta_log_loss": None,
            "event_bootstrap_p_delta_le_zero": None,
            "market_null_p_observed_or_better": None,
        }

    y = df["red_won"].astype(float).to_numpy()
    market = df["market_probability"].astype(float).to_numpy()
    candidate = df[probability_column].astype(float).to_numpy()
    market_losses = binary_loss(y, market)
    candidate_losses = binary_loss(y, candidate)
    deltas = market_losses - candidate_losses
    delta = float(np.mean(deltas))

    market_loss_win = binary_loss(np.ones(len(df)), market)
    market_loss_loss = binary_loss(np.zeros(len(df)), market)
    candidate_loss_win = binary_loss(np.ones(len(df)), candidate)
    candidate_loss_loss = binary_loss(np.zeros(len(df)), candidate)

    bootstrap = event_bootstrap_mean(
        deltas,
        df["event_date"].dt.date.astype(str).to_numpy(),
        bootstrap_iterations,
        rng,
    )
    return {
        "policy": policy_name,
        "fights": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "market_log_loss": float(np.mean(market_losses)),
        "candidate_log_loss": float(np.mean(candidate_losses)),
        "delta_log_loss": delta,
        "event_bootstrap_p_delta_le_zero": bootstrap["p_le_zero"],
        "event_bootstrap_delta_ci_95": bootstrap["ci_95_mean"],
        "market_null_p_observed_or_better": market_null_probability_pvalue(
            market,
            market_loss_win,
            market_loss_loss,
            candidate_loss_win,
            candidate_loss_loss,
            delta,
            market_null_iterations,
            rng,
        ),
    }


def market_null_profit_pvalue(
    market_prob: np.ndarray,
    selected_odds: np.ndarray,
    observed_profit: float,
    iterations: int,
    rng,
) -> float | None:
    if len(market_prob) == 0:
        return None
    win_profit = american_win_profit(selected_odds)
    samples = np.zeros(iterations, dtype=float)
    for index in range(iterations):
        wins = rng.random(len(market_prob)) < market_prob
        samples[index] = float(np.where(wins, win_profit, -1.0).sum())
    return float((np.sum(samples >= observed_profit) + 1) / (iterations + 1))


def summarize_bet_period(
    df: pd.DataFrame,
    bootstrap_iterations: int,
    market_null_iterations: int,
    rng,
) -> dict:
    if df.empty:
        return {
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_minus_market": None,
            "event_bootstrap_p_profit_le_zero": None,
            "market_null_p_observed_or_better": None,
            "positive_folds": 0,
            "folds": 0,
        }

    profit_values = df["flat_profit"].astype(float).to_numpy()
    profit = float(profit_values.sum())
    bootstrap = event_bootstrap(
        profit_values,
        df["event_date"].dt.date.astype(str).to_numpy(),
        bootstrap_iterations,
        rng,
    )
    fold_profits = df.groupby("fold")["flat_profit"].sum()
    return {
        "bets": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "profit": profit,
        "roi": profit / len(df),
        "actual_minus_market": float(
            df["selected_won"].astype(float).mean()
            - df["selected_market_probability"].astype(float).mean()
        ),
        "event_bootstrap_p_profit_le_zero": bootstrap["p_le_zero"],
        "event_bootstrap_profit_ci_95": bootstrap["ci_95"],
        "market_null_p_observed_or_better": market_null_profit_pvalue(
            df["selected_market_probability"].astype(float).to_numpy(),
            df["selected_odds"].astype(float).to_numpy(),
            profit,
            market_null_iterations,
            rng,
        ),
        "positive_folds": int((fold_profits > 0.0).sum()),
        "folds": int(len(fold_profits)),
    }


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    probabilities = pd.read_csv(args.probabilities, parse_dates=["event_date"])
    ranked_bets = pd.read_csv(args.ranked_bets, parse_dates=["event_date"])

    capped_bets = ranked_bets[
        (ranked_bets["probability_policy"] == "frozen_residual_meta")
        & (ranked_bets["ranking_mode"] == "top_edge")
    ].copy()
    max_fold = int(max(probabilities["fold"].max(), capped_bets["fold"].max()))
    specs = period_specs(max_fold)

    probability_periods = []
    bet_periods = []
    for spec in specs:
        prob_slice = apply_period(probabilities, spec)
        bet_slice = apply_period(capped_bets, spec)
        probability_periods.append(
            {
                "name": spec["name"],
                "label": spec["label"],
                "start": spec["start"],
                "end": spec["end"],
                "fold": spec["fold"],
                "policies": [
                    summarize_probability_period(
                        prob_slice,
                        policy_name,
                        column,
                        args.bootstrap_iterations,
                        args.market_null_iterations,
                        rng,
                    )
                    for policy_name, column in PROBABILITY_POLICIES
                ],
            }
        )
        bet_periods.append(
            {
                "name": spec["name"],
                "label": spec["label"],
                "start": spec["start"],
                "end": spec["end"],
                "fold": spec["fold"],
                "frozen_residual_meta_cap3": summarize_bet_period(
                    bet_slice,
                    args.bootstrap_iterations,
                    args.market_null_iterations,
                    rng,
                ),
            }
        )

    return {
        "probabilities_path": args.probabilities,
        "ranked_bets_path": args.ranked_bets,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "probability_periods": probability_periods,
        "bet_periods": bet_periods,
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Recent Stress Audit",
        "",
        "This audit asks whether the residual probability edge and frozen cap-3",
        "residual paper bets survive recent-only slices, or whether early 2024 is",
        "doing most of the historical work.",
        "",
        "## Inputs",
        "",
        f"- probability predictions: `{result['probabilities_path']}`",
        f"- capped-bet source: `{result['ranked_bets_path']}`",
        f"- event-bootstrap iterations: `{result['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        "",
        "## Probability Stress",
        "",
        "| Period | Policy | Fights | Events | Market LL | Candidate LL | Delta LL | Bootstrap P(delta <= 0) | Market-Null p |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for period in result["probability_periods"]:
        for policy in period["policies"]:
            lines.append(
                "| {period} | {policy} | {fights} | {events} | {market_ll} | {candidate_ll} | {delta} | {boot} | {null} |".format(
                    period=period["label"],
                    policy=policy["policy"],
                    fights=policy["fights"],
                    events=policy["events"],
                    market_ll=fmt_float(policy["market_log_loss"]),
                    candidate_ll=fmt_float(policy["candidate_log_loss"]),
                    delta=fmt_float(policy["delta_log_loss"]),
                    boot=fmt_p(policy["event_bootstrap_p_delta_le_zero"]),
                    null=fmt_p(policy["market_null_p_observed_or_better"]),
                )
            )

    lines.extend(
        [
            "",
            "## Frozen Cap-3 PnL Stress",
            "",
            "This uses the frozen residual-meta top-edge cap-3 historical ledger.",
            "",
            "| Period | Bets | Events | Profit | ROI | Actual - Market | Bootstrap P(profit <= 0) | Market-Null p | Positive Folds |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for period in result["bet_periods"]:
        summary = period["frozen_residual_meta_cap3"]
        lines.append(
            "| {period} | {bets} | {events} | {profit} | {roi} | {actual_market} | {boot} | {null} | {pos} / {folds} |".format(
                period=period["label"],
                bets=summary["bets"],
                events=summary["events"],
                profit=fmt_units(summary["profit"]),
                roi=fmt_pct(summary["roi"]),
                actual_market=fmt_pct(summary["actual_minus_market"]),
                boot=fmt_p(summary["event_bootstrap_p_profit_le_zero"]),
                null=fmt_p(summary["market_null_p_observed_or_better"]),
                pos=summary["positive_folds"],
                folds=summary["folds"],
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The aggregate residual probability signal remains positive, but the recent-only slices are materially weaker.",
            "- The frozen cap-3 PnL edge is heavily front-loaded: 2024 is positive, while 2025-2026 and the latest fold are not convincing.",
            "- This does not refute the existence of a weak residual signal, but it argues against a strong live edge claim until post-freeze paper results reverse the recent decay.",
            "- Feature work should focus on explaining or fixing recency drift; simply adding more historical-feature capacity is unlikely to be enough.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_recent_stress_audit.json"
    md_path = output_dir / "residual_recent_stress_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    aggregate = next(period for period in result["bet_periods"] if period["name"] == "aggregate")
    recent = next(period for period in result["bet_periods"] if period["name"] == "post_2024")
    print(
        "Frozen cap-3 profit: aggregate {aggregate_profit:+.2f}u, post-2024 {recent_profit:+.2f}u".format(
            aggregate_profit=aggregate["frozen_residual_meta_cap3"]["profit"],
            recent_profit=recent["frozen_residual_meta_cap3"]["profit"],
        )
    )


if __name__ == "__main__":
    main()
