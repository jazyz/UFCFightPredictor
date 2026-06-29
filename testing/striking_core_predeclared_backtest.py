#!/usr/bin/env python3
"""Predeclared market-aware backtest for the narrow striking-core clue.

This audit moves the grouped striking clue out of the residual-fold artifact
and into the existing market-aware feature/odds alignment stack. It keeps the
candidate family narrow and fixed: the primary candidate is
`mixed_sig_head_core`, with two nearby reference variants.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_aware_feature_audit import (  # noqa: E402
    VariantSpec,
    aggregate_predictions,
    aligned_market_feature_frame,
    market_null_simulation,
    run_observed_predictions,
)
from testing.market_residual_meta_audit import iter_folds  # noqa: E402
from testing.statistical_edge_audit import calibration_stats  # noqa: E402
from testing.striking_group_after_market_audit import fmt_float, fmt_p, fmt_pct  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_OUTPUT_DIR = "test_results/striking_core_predeclared_backtest"
EDGE_THRESHOLDS = (0.0, 0.02, 0.05)
PRIMARY_VARIANT = "mixed_sig_head_core"


@dataclass(frozen=True)
class BettingSummary:
    threshold: float
    bets: int
    profit: float
    roi: float | None
    positive_folds: int
    mean_edge: float | None
    market_null_p: float | None
    bootstrap_prob_profit_le_zero: float | None


def parse_args():
    parser = argparse.ArgumentParser(description="Predeclared striking-core market-aware backtest")
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
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=100)
    parser.add_argument("--bet-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--include-womens-fights", action="store_true")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def build_variants(df: pd.DataFrame) -> list[VariantSpec]:
    specs = [
        VariantSpec(
            "market_recalibrated",
            ("market_logit",),
            "market-logit-only recalibration baseline",
        ),
        VariantSpec(
            PRIMARY_VARIANT,
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "primary predeclared striking core from grouped audit",
        ),
        VariantSpec(
            "raw_sig_head_oppdiff",
            (
                "market_logit",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "raw significant-strike/head differential reference",
        ),
        VariantSpec(
            "pct_sig_head_distance",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head% differential oppdiff",
                "Distance% differential oppdiff",
            ),
            "percentage differential reference",
        ),
    ]
    available = set(df.columns)
    missing = {
        spec.name: [column for column in spec.feature_columns if column not in available]
        for spec in specs
    }
    missing = {name: columns for name, columns in missing.items() if columns}
    if missing:
        raise SystemExit(f"Missing predeclared feature columns: {missing}")
    return specs


def american_profit(odds: float) -> float:
    odds = float(odds)
    if odds > 0:
        return odds / 100.0
    return 100.0 / abs(odds)


def add_red_blue_odds(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        red_key = canonical_name(row["red_fighter"])
        fighter1_key = canonical_name(row["odds_fighter1_name"])
        fighter2_key = canonical_name(row["odds_fighter2_name"])
        if red_key == fighter1_key:
            red_odds = float(row["fighter1_odds"])
            blue_odds = float(row["fighter2_odds"])
        elif red_key == fighter2_key:
            red_odds = float(row["fighter2_odds"])
            blue_odds = float(row["fighter1_odds"])
        else:
            red_odds = np.nan
            blue_odds = np.nan
        rows.append({"fight_key": row["fight_key"], "red_odds": red_odds, "blue_odds": blue_odds})
    odds = pd.DataFrame(rows)
    return df.merge(odds, on="fight_key", how="left", validate="one_to_one")


def prediction_with_odds(predictions: pd.DataFrame, aligned: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "fight_key",
        "red_odds",
        "blue_odds",
        "fighter1_odds",
        "fighter2_odds",
        "odds_fighter1_name",
        "odds_fighter2_name",
    ]
    aligned_odds = add_red_blue_odds(aligned)
    return predictions.merge(aligned_odds[keep], on="fight_key", how="left", validate="many_to_one")


def add_bet_rows(predictions: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    for _, row in predictions.iterrows():
        candidate = float(row["candidate_probability"])
        market = float(row["market_probability"])
        red_edge = candidate - market
        abs_edge = abs(red_edge)
        if abs_edge < threshold or not np.isfinite(abs_edge):
            continue
        bet_red = red_edge > 0.0
        odds = float(row["red_odds"] if bet_red else row["blue_odds"])
        if not np.isfinite(odds):
            continue
        won = bool(row["red_won"]) if bet_red else not bool(row["red_won"])
        market_probability = market if bet_red else 1.0 - market
        model_probability = candidate if bet_red else 1.0 - candidate
        profit = american_profit(odds) if won else -1.0
        rows.append(
            {
                "fold": int(row["fold"]),
                "event_date": row["event_date"],
                "fight_key": row["fight_key"],
                "variant": row["variant"],
                "bet_side": "red" if bet_red else "blue",
                "bet_odds": odds,
                "bet_won": won,
                "market_probability": market_probability,
                "model_probability": model_probability,
                "edge": model_probability - market_probability,
                "bet": 1.0,
                "profit": profit,
            }
        )
    return pd.DataFrame(rows)


def event_bootstrap_profit(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty or iterations <= 0:
        return None
    grouped = bets.groupby("event_date", sort=True)[["profit", "bet"]].sum()
    profits = grouped["profit"].astype(float).to_numpy()
    stakes = grouped["bet"].astype(float).to_numpy()
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    sampled_profit = profits[sampled].sum(axis=1)
    sampled_stake = stakes[sampled].sum(axis=1)
    sampled_roi = np.divide(
        sampled_profit,
        sampled_stake,
        out=np.full(iterations, np.nan, dtype=float),
        where=sampled_stake > 0,
    )
    return {
        "events": int(len(grouped)),
        "iterations": int(iterations),
        "profit_ci_95": [float(value) for value in np.percentile(sampled_profit, [2.5, 97.5])],
        "roi_ci_95": [float(value) for value in np.nanpercentile(sampled_roi, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(sampled_profit <= 0.0)),
    }


def market_null_bets(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty or iterations <= 0:
        return None
    market = bets["market_probability"].astype(float).to_numpy()
    win_profit = np.array([american_profit(value) for value in bets["bet_odds"].astype(float)], dtype=float)
    observed = float(bets["profit"].astype(float).sum())
    profits = np.empty(iterations, dtype=float)
    chunk_size = 1000
    for start in range(0, iterations, chunk_size):
        end = min(start + chunk_size, iterations)
        wins = rng.random((end - start, len(bets))) < market
        profits[start:end] = np.where(wins, win_profit, -1.0).sum(axis=1)
    return {
        "iterations": int(iterations),
        "observed_profit": observed,
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0.0)),
    }


def summarize_bets(
    predictions: pd.DataFrame,
    threshold: float,
    bootstrap_iterations: int,
    null_iterations: int,
    rng,
) -> dict:
    bets = add_bet_rows(predictions, threshold)
    if bets.empty:
        return {
            "threshold": threshold,
            "bets": 0,
            "profit": 0.0,
            "roi": None,
            "positive_folds": 0,
            "mean_edge": None,
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
        "market_null": market_null_bets(bets, null_iterations, rng),
        "event_bootstrap": event_bootstrap_profit(bets, bootstrap_iterations, rng),
    }


def add_calibration(summary: dict, predictions: pd.DataFrame) -> dict:
    enriched = dict(summary)
    for variant_name, row in enriched.items():
        subset = predictions[predictions["variant"] == variant_name]
        y = subset["red_won"].astype(float).to_numpy()
        row["market_calibration"] = calibration_stats(
            y,
            subset["market_probability"].astype(float).to_numpy(),
        )
        row["candidate_calibration"] = calibration_stats(
            y,
            subset["candidate_probability"].astype(float).to_numpy(),
        )
    return enriched


def summarize_betting_by_variant(
    predictions: pd.DataFrame,
    bootstrap_iterations: int,
    null_iterations: int,
    rng,
) -> dict:
    result = {}
    for variant_name, subset in predictions.groupby("variant", sort=True):
        result[variant_name] = [
            summarize_bets(subset, threshold, bootstrap_iterations, null_iterations, rng)
            for threshold in EDGE_THRESHOLDS
        ]
    return result


def best_threshold(rows: list[dict]) -> dict:
    return max(rows, key=lambda row: row["profit"])


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def probability_table(summary: dict, market_null: dict | None) -> list[str]:
    lines = [
        "| Variant | Fights | Candidate LL | Market Delta LL | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Market-Null p | Candidate ECE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(
        summary.items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
        reverse=True,
    ):
        boot = row.get("event_bootstrap") or {}
        null = (market_null or {}).get(name) or {}
        calibration = row.get("candidate_calibration") or {}
        lines.append(
            "| {name} | {fights} | {ll} | {delta} | {brier} | {acc} | {positive} / {folds} | {boot} | {null_p} | {ece} |".format(
                name=name,
                fights=row["candidate"]["fights"],
                ll=fmt_float(row["candidate"]["log_loss"]),
                delta=fmt_float(row["market_minus_candidate_log_loss"]),
                brier=fmt_float(row["market_minus_candidate_brier"]),
                acc=fmt_pct(row["candidate"]["accuracy"]),
                positive=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
                null_p=fmt_p(null.get("p_value_observed_or_better")),
                ece=fmt_pct(calibration.get("ece")),
            )
        )
    return lines


def betting_table(betting: dict, variant_name: str) -> list[str]:
    lines = [
        "| Edge Threshold | Bets | Profit | ROI | Positive Folds | Mean Edge | Market-Null p | Bootstrap P(profit<=0) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in betting.get(variant_name, []):
        null = row.get("market_null") or {}
        boot = row.get("event_bootstrap") or {}
        lines.append(
            "| {threshold} | {bets} | {profit} | {roi} | {positive} / {folds} | {edge} | {null_p} | {boot_p} |".format(
                threshold=fmt_pct(row["threshold"]),
                bets=row["bets"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row.get("roi")),
                positive=row.get("positive_folds", 0),
                folds=row.get("folds_with_bets", 0),
                edge=fmt_pct(row.get("mean_edge")),
                null_p=fmt_p(null.get("p_value_observed_or_better")),
                boot_p=fmt_p(boot.get("prob_profit_le_zero")),
            )
        )
    return lines


def fold_table(fold_rows: list[dict], variants: list[VariantSpec]) -> list[str]:
    variant_names = [
        variant.name if hasattr(variant, "name") else variant["name"]
        for variant in variants
    ]
    lines = [
        "| Fold | Holdout | Fights | Market LL | " + " | ".join(variant_names) + " |",
        "| ---: | --- | ---: | ---: | " + " | ".join("---:" for _ in variant_names) + " |",
    ]
    for row in fold_rows:
        cells = [
            str(row["fold"]),
            f"{row['holdout_start']} to {row['holdout_end']}",
            str(row["holdout_fights"]),
            fmt_float(row["market_log_loss"]),
        ]
        for variant_name in variant_names:
            cells.append(fmt_float(row.get(f"{variant_name}_delta_log_loss")))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def markdown_report(result: dict) -> str:
    summary = result["summary"]
    primary = summary[PRIMARY_VARIANT]
    primary_bets = result["betting"].get(PRIMARY_VARIANT, [])
    best_primary_bet = best_threshold(primary_bets)
    best_bet_null = best_primary_bet.get("market_null") or {}
    lines = [
        "# Striking Core Predeclared Backtest",
        "",
        "This audit tests the narrow `mixed_sig_head_core` clue with a fixed",
        "market-aware logistic protocol over rolling date folds. It reuses the",
        "existing odds/feature alignment and men-only universe exclusions. The",
        "primary candidate and comparison variants are fixed before this run;",
        "no threshold is selected for promotion.",
        "",
        "## Protocol",
        "",
        f"- feature table: `{result['metadata']['features_path']}`",
        f"- odds table: `{result['metadata']['odds_path']}`",
        f"- aligned rows: `{result['metadata']['aligned_rows']}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- first holdout start: `{result['parameters']['first_holdout_start']}`",
        f"- last holdout end: `{result['parameters']['last_holdout_end']}`",
        f"- development window: `{result['parameters']['dev_days']}` days",
        f"- holdout window: `{result['parameters']['holdout_days']}` days",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- market-null refits: `{result['parameters']['market_null_iterations']}`",
        "",
        "## Probability Results",
        "",
        *probability_table(summary, result.get("market_null")),
        "",
        "## Fold Delta LL",
        "",
        *fold_table(result["folds"], result["variants"]),
        "",
        f"## Flat Positive-Edge PnL: `{PRIMARY_VARIANT}`",
        "",
        *betting_table(result["betting"], PRIMARY_VARIANT),
        "",
        "## Variant Definitions",
        "",
        "| Variant | Note | Feature Columns |",
        "| --- | --- | --- |",
    ]
    for variant in result["variants"]:
        lines.append(
            "| {name} | {note} | `{features}` |".format(
                name=variant["name"],
                note=variant["note"],
                features="`, `".join(variant["feature_columns"]),
            )
        )

    primary_null = (result.get("market_null") or {}).get(PRIMARY_VARIANT) or {}
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Primary probability result: `{PRIMARY_VARIANT}` has market Delta LL `{fmt_float(primary['market_minus_candidate_log_loss'])}`, Brier Delta `{fmt_float(primary['market_minus_candidate_brier'])}`, positive folds `{primary['positive_folds']} / {primary['folds']}`, event-bootstrap `P(delta <= 0)` `{fmt_p((primary.get('event_bootstrap') or {}).get('prob_delta_le_zero'))}`, and market-null p `{fmt_p(primary_null.get('p_value_observed_or_better'))}`.",
            f"- Best descriptive flat positive-edge threshold for `{PRIMARY_VARIANT}` in this report is `{fmt_pct(best_primary_bet['threshold'])}` with profit `{fmt_units(best_primary_bet['profit'])}`, ROI `{fmt_pct(best_primary_bet.get('roi'))}`, and market-null p `{fmt_p(best_bet_null.get('p_value_observed_or_better'))}`.",
        ]
    )
    if primary["market_minus_candidate_log_loss"] <= 0:
        lines.append("- The predeclared striking core does not beat raw market log loss in this rolling date-fold test.")
    elif (primary_null.get("p_value_observed_or_better") or 1.0) > 0.05:
        lines.append(
            "- The probability result is positive, but it does not clear the market-null screen."
        )
    else:
        lines.append(
            "- The probability result clears the unadjusted market-null screen, but still needs correction for adjacent variants and future pre-outcome paper tracking before it can support staking."
        )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    df, metadata = aligned_market_feature_frame(args)
    variants = build_variants(df)
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
    if not folds:
        raise SystemExit("No rolling folds available for the requested protocol")
    predictions, coefficients, fold_rows = run_observed_predictions(df, folds, variants, args.c)
    summary = aggregate_predictions(predictions, variants, args.bootstrap_iterations, rng)
    summary = add_calibration(summary, predictions)
    null = market_null_simulation(
        df,
        folds,
        variants,
        summary,
        args.c,
        args.market_null_iterations,
        rng,
    )
    predictions_odds = prediction_with_odds(predictions, df)
    betting = summarize_betting_by_variant(
        predictions_odds,
        args.bootstrap_iterations,
        args.bet_null_iterations,
        rng,
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
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "bet_null_iterations": args.bet_null_iterations,
            "seed": args.seed,
        },
        "metadata": metadata,
        "folds": fold_rows,
        "variants": [
            {
                "name": variant.name,
                "feature_columns": list(variant.feature_columns),
                "note": variant.note,
            }
            for variant in variants
        ],
        "summary": summary,
        "market_null": null,
        "betting": betting,
        "coefficients": coefficients,
    }


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_core_predeclared_backtest.json"
    md_path = output_dir / "striking_core_predeclared_backtest.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
