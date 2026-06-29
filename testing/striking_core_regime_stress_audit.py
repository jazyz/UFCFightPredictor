#!/usr/bin/env python3
"""Regime and concentration stress tests for striking-core paper ledgers.

The striking-core probability and betting audits are positive but not yet a
live-edge proof. This audit checks whether the fixed uncapped 2% edge ledger is
broad across time/price regimes or carried by a handful of historical events.
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
from testing.market_residual_meta_audit import iter_folds  # noqa: E402
from testing.striking_core_betting_calibration_audit import (  # noqa: E402
    add_bet_rows,
    attach_odds,
)
from testing.striking_core_predeclared_backtest import event_bootstrap_profit, market_null_bets  # noqa: E402
from testing.striking_core_robustness_selection_audit import (  # noqa: E402
    build_gates,
    build_models,
    build_policies,
    ensure_columns,
    expand_policy_predictions,
    run_model_predictions,
    select_rolling_policy,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_core_regime_stress_audit"
EDGE_THRESHOLD = 0.02
REFERENCE_POLICIES = (
    "mixed_core|all",
    "sigpct_head|all",
    "mixed_core|min5",
    "sigpct_head|min5",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Stress striking-core regimes and concentration")
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
    parser.add_argument("--market-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def fmt_units(value) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def odds_band(odds: float) -> str:
    odds = float(odds)
    if odds <= -300:
        return "<= -300"
    if odds <= -200:
        return "-300 to -200"
    if odds <= -150:
        return "-200 to -150"
    if odds < 0:
        return "-150 to -100"
    if odds <= 150:
        return "+100 to +150"
    return "> +150"


def market_bin(probability: float) -> str:
    value = float(probability)
    if value < 0.50:
        return "<0.50"
    if value < 0.60:
        return "0.50-0.60"
    if value < 0.70:
        return "0.60-0.70"
    return ">=0.70"


def edge_bin(edge: float) -> str:
    value = float(edge)
    if value < 0.035:
        return "0.02-0.035"
    if value < 0.05:
        return "0.035-0.05"
    if value < 0.075:
        return "0.05-0.075"
    return ">=0.075"


def title_group(title: str) -> str:
    text = str(title)
    if "Heavyweight" in text or "Light Heavyweight" in text:
        return "heavy_or_lhw"
    if "Middleweight" in text or "Welterweight" in text:
        return "middle_or_welter"
    if "Lightweight" in text or "Featherweight" in text:
        return "light_or_feather"
    if "Bantamweight" in text or "Flyweight" in text:
        return "bantam_or_fly"
    return "other"


def enrich_bets(bets: pd.DataFrame) -> pd.DataFrame:
    enriched = bets.copy()
    enriched["event_date"] = pd.to_datetime(enriched["event_date"], errors="coerce")
    enriched["year"] = enriched["event_date"].dt.year.astype("Int64").astype(str)
    enriched["fold_label"] = "fold " + enriched["fold"].astype(int).astype(str)
    enriched["period"] = np.where(enriched["event_date"] >= pd.Timestamp("2025-01-01"), "2025-2026", "2023-2024")
    enriched["last_365d"] = np.where(enriched["event_date"] >= pd.Timestamp("2025-06-28"), "last_365d", "older")
    enriched["market_bin"] = enriched["market_probability"].map(market_bin)
    enriched["edge_bin"] = enriched["edge"].map(edge_bin)
    enriched["odds_band"] = enriched["bet_odds"].map(odds_band)
    enriched["bet_type"] = np.where(enriched["bet_odds"].astype(float) < 0.0, "favorite", "underdog")
    enriched["title_group"] = enriched.get("title", "").map(title_group) if "title" in enriched.columns else "unknown"
    return enriched


def policy_rows(policy_predictions: pd.DataFrame, selected_folds: list[int], policy_name: str) -> pd.DataFrame:
    return policy_predictions[
        policy_predictions["policy"].eq(policy_name)
        & policy_predictions["fold"].isin(selected_folds)
    ].copy()


def selected_policy_rows(policy_predictions: pd.DataFrame, policies, min_prior_rows: int) -> tuple[pd.DataFrame, list[dict]]:
    selected, selections = select_rolling_policy(policy_predictions, policies, min_prior_rows)
    selected = selected.copy()
    selected["policy"] = "rolling_selected_prior_delta"
    return selected, selections


def build_bets(rows: pd.DataFrame, aligned: pd.DataFrame, policy_name: str) -> pd.DataFrame:
    with_odds = attach_odds(rows, aligned)
    bets = add_bet_rows(with_odds, EDGE_THRESHOLD)
    if bets.empty:
        return bets
    metadata_cols = ["fight_key", "title", "red_fighter", "blue_fighter", "winner_name"]
    metadata = rows.drop_duplicates("fight_key")[metadata_cols]
    bets = bets.merge(metadata, on="fight_key", how="left", validate="many_to_one")
    bets["policy"] = policy_name
    return enrich_bets(bets)


def summarize_slice(df: pd.DataFrame, label: str, bootstrap_iterations: int, null_iterations: int, rng) -> dict:
    if df.empty:
        return {
            "slice": str(label),
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_market_probability": None,
            "actual_minus_market": None,
            "mean_model_probability": None,
            "mean_edge": None,
            "positive_folds": 0,
            "folds": 0,
            "bootstrap_p_profit_le_zero": None,
            "bootstrap_profit_ci_95": [None, None],
            "market_null_p": None,
        }
    profit = df["profit"].astype(float)
    actual = df["bet_won"].astype(float)
    market = df["market_probability"].astype(float)
    bootstrap = event_bootstrap_profit(df, bootstrap_iterations, rng)
    fold_profit = df.groupby("fold", sort=True)["profit"].sum()
    return {
        "slice": str(label),
        "bets": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "profit": float(profit.sum()),
        "roi": float(profit.mean()),
        "actual_win_rate": float(actual.mean()),
        "mean_market_probability": float(market.mean()),
        "actual_minus_market": float(actual.mean() - market.mean()),
        "mean_model_probability": float(df["model_probability"].astype(float).mean()),
        "mean_edge": float(df["edge"].astype(float).mean()),
        "positive_folds": int((fold_profit > 0.0).sum()),
        "folds": int(len(fold_profit)),
        "bootstrap_p_profit_le_zero": None if bootstrap is None else bootstrap["prob_profit_le_zero"],
        "bootstrap_profit_ci_95": [None, None] if bootstrap is None else bootstrap["profit_ci_95"],
        "market_null_p": None
        if df.empty
        else market_null_bets(df, null_iterations, rng)["p_value_observed_or_better"],
    }


def summarize_group(df: pd.DataFrame, column: str, bootstrap_iterations: int, null_iterations: int, rng) -> list[dict]:
    rows = []
    for value, subset in df.groupby(column, sort=True, observed=False, dropna=False):
        if subset.empty:
            continue
        rows.append(summarize_slice(subset.copy(), str(value), bootstrap_iterations, null_iterations, rng))
    return rows


def event_concentration(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "events": 0,
            "total_profit": 0.0,
            "events_to_erase_profit": None,
            "removal_sensitivity": [],
            "top_events": [],
        }
    event_profit = (
        df.groupby("event_date", sort=True)
        .agg(
            bets=("fight_key", "size"),
            profit=("profit", "sum"),
            mean_edge=("edge", "mean"),
        )
        .reset_index()
    )
    total_profit = float(event_profit["profit"].sum())
    ordered = event_profit.sort_values("profit", ascending=False).reset_index(drop=True)
    removals = []
    for remove_count in (1, 3, 5, 10):
        remaining = ordered.iloc[remove_count:]
        removals.append(
            {
                "remove_top_events": int(remove_count),
                "remaining_events": int(len(remaining)),
                "remaining_profit": float(remaining["profit"].sum()),
            }
        )

    cumulative = 0.0
    events_to_erase = None
    for index, profit in enumerate(ordered["profit"].to_numpy(dtype=float), start=1):
        cumulative += float(profit)
        if total_profit - cumulative <= 0.0:
            events_to_erase = index
            break

    return {
        "events": int(len(event_profit)),
        "total_profit": total_profit,
        "events_to_erase_profit": events_to_erase,
        "removal_sensitivity": removals,
        "top_events": [
            {
                "event_date": pd.Timestamp(row["event_date"]).date().isoformat(),
                "bets": int(row["bets"]),
                "profit": float(row["profit"]),
                "mean_edge": float(row["mean_edge"]),
            }
            for row in ordered.head(10).to_dict("records")
        ],
    }


def summarize_policy_bets(df: pd.DataFrame, bootstrap_iterations: int, null_iterations: int, rng) -> dict:
    return {
        "overall": summarize_slice(df, "overall", bootstrap_iterations, null_iterations, rng),
        "by_fold": summarize_group(df, "fold_label", bootstrap_iterations, null_iterations, rng),
        "by_year": summarize_group(df, "year", bootstrap_iterations, null_iterations, rng),
        "by_period": summarize_group(df, "period", bootstrap_iterations, null_iterations, rng),
        "by_last_365d": summarize_group(df, "last_365d", bootstrap_iterations, null_iterations, rng),
        "by_market_bin": summarize_group(df, "market_bin", bootstrap_iterations, null_iterations, rng),
        "by_edge_bin": summarize_group(df, "edge_bin", bootstrap_iterations, null_iterations, rng),
        "by_odds_band": summarize_group(df, "odds_band", bootstrap_iterations, null_iterations, rng),
        "by_bet_type": summarize_group(df, "bet_type", bootstrap_iterations, null_iterations, rng),
        "by_title_group": summarize_group(df, "title_group", bootstrap_iterations, null_iterations, rng),
        "event_concentration": event_concentration(df),
    }


def table(rows: list[dict]) -> list[str]:
    lines = [
        "| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {slice} | {bets} | {events} | {profit} | {roi} | {actual} | {market} | {actual_market} | {edge} | {pos} / {folds} | {boot} | {null} |".format(
                slice=row["slice"],
                bets=row["bets"],
                events=row["events"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual=fmt_pct(row["actual_win_rate"]),
                market=fmt_pct(row["mean_market_probability"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                edge=fmt_pct(row["mean_edge"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(row["bootstrap_p_profit_le_zero"]),
                null=fmt_p(row["market_null_p"]),
            )
        )
    return lines


def concentration_table(rows: list[dict]) -> list[str]:
    lines = ["| Remove Top Events | Remaining Events | Remaining Profit |", "| ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['remove_top_events']} | {row['remaining_events']} | {fmt_units(row['remaining_profit'])} |")
    return lines


def top_events_table(rows: list[dict]) -> list[str]:
    lines = ["| Event Date | Bets | Profit | Mean Edge |", "| --- | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['event_date']} | {row['bets']} | {fmt_units(row['profit'])} | {fmt_pct(row['mean_edge'])} |")
    return lines


def policy_section(name: str, result: dict) -> list[str]:
    concentration = result["event_concentration"]
    lines = [
        f"## `{name}`",
        "",
        "Overall:",
        "",
        *table([result["overall"]]),
        "",
        "By fold:",
        "",
        *table(result["by_fold"]),
        "",
        "By period:",
        "",
        *table(result["by_period"]),
        "",
        "By market probability bin:",
        "",
        *table(result["by_market_bin"]),
        "",
        "By edge bin:",
        "",
        *table(result["by_edge_bin"]),
        "",
        "Event concentration:",
        "",
        f"- events to erase aggregate profit: `{concentration['events_to_erase_profit']}`",
        "",
        *concentration_table(concentration["removal_sensitivity"]),
        "",
        "Top profit events:",
        "",
        *top_events_table(concentration["top_events"][:5]),
        "",
    ]
    return lines


def markdown_report(result: dict) -> str:
    lines = [
        "# Striking Core Regime Stress Audit",
        "",
        "This audit stress-tests fixed uncapped `2%` striking-core paper ledgers",
        "by fold, time period, price band, edge band, and event concentration.",
        "It does not select a new policy or threshold.",
        "",
        "## Protocol",
        "",
        f"- aligned men-only rows: `{result['metadata']['aligned_rows']}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- evaluated folds for betting: `{', '.join(str(value) for value in result['selected_eval_folds'])}`",
        f"- edge threshold: `{fmt_pct(EDGE_THRESHOLD)}`",
        "- event cap: none",
        f"- market-null iterations per slice: `{result['parameters']['market_null_iterations']}`",
        "",
        "## Summary",
        "",
        "| Policy | Bets | Events | Profit | ROI | Actual - Market | Pos Folds | Boot P(profit<=0) | Market-Null p | Events To Erase Profit | Profit After Removing Top 5 Events |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, policy in result["policies"].items():
        overall = policy["overall"]
        concentration = policy["event_concentration"]
        remove5 = next(
            (row["remaining_profit"] for row in concentration["removal_sensitivity"] if row["remove_top_events"] == 5),
            None,
        )
        lines.append(
            "| `{name}` | {bets} | {events} | {profit} | {roi} | {actual_market} | {pos} / {folds} | {boot} | {null} | {erase} | {remove5} |".format(
                name=name,
                bets=overall["bets"],
                events=overall["events"],
                profit=fmt_units(overall["profit"]),
                roi=fmt_pct(overall["roi"]),
                actual_market=fmt_pct(overall["actual_minus_market"]),
                pos=overall["positive_folds"],
                folds=overall["folds"],
                boot=fmt_p(overall["bootstrap_p_profit_le_zero"]),
                null=fmt_p(overall["market_null_p"]),
                erase=concentration["events_to_erase_profit"],
                remove5=fmt_units(remove5),
            )
        )

    lines.extend(["", "## Detailed Slices", ""])
    for name, policy in result["policies"].items():
        lines.extend(policy_section(name, policy))

    lines.extend(["## Interpretation", ""])
    challenger = result["policies"].get("sigpct_head|all")
    if challenger:
        overall = challenger["overall"]
        concentration = challenger["event_concentration"]
        remove5 = next(
            (row["remaining_profit"] for row in concentration["removal_sensitivity"] if row["remove_top_events"] == 5),
            None,
        )
        if remove5 is not None and remove5 > 0.0:
            lines.append(
                "- The sigpct/head challenger remains profitable after removing its top five profit events, which is a useful concentration check."
            )
        else:
            lines.append(
                "- The sigpct/head challenger is sensitive to top-event removal, so historical PnL may be concentrated."
            )
        if overall["bootstrap_p_profit_le_zero"] is not None and overall["bootstrap_p_profit_le_zero"] <= 0.05:
            lines.append("- Its event-bootstrap PnL screen is positive at the aggregate level.")
        else:
            lines.append("- Its event-bootstrap PnL screen remains marginal at the aggregate level.")
    lines.append(
        "- These are retrospective stress diagnostics. The frozen challenger and mixed-core policies still need future pre-outcome paper settlement before a live edge claim."
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
    aligned, metadata = aligned_market_feature_frame(align_args)
    models = build_models()
    gates = build_gates()
    policies = build_policies(models, gates)
    ensure_columns(aligned, models)
    folds = iter_folds(
        aligned,
        args.first_holdout_start,
        args.last_holdout_end,
        args.dev_days,
        args.holdout_days,
        args.step_days,
        args.min_dev_fights,
        args.min_holdout_fights,
    )
    labels = aligned["red_won"].astype(int).to_numpy()
    model_predictions, _, fold_rows = run_model_predictions(
        aligned,
        folds,
        models,
        labels,
        args.c,
        args.clip_quantile,
    )
    policy_predictions = expand_policy_predictions(model_predictions, policies, gates)
    rolling_rows, selections = selected_policy_rows(
        policy_predictions,
        policies,
        args.min_prior_selection_rows,
    )
    selected_folds = sorted(int(value) for value in rolling_rows["fold"].unique())

    policy_bets = {
        "rolling_selected_prior_delta": build_bets(
            rolling_rows,
            aligned,
            "rolling_selected_prior_delta",
        )
    }
    for policy_name in REFERENCE_POLICIES:
        rows = policy_rows(policy_predictions, selected_folds, policy_name)
        policy_bets[policy_name] = build_bets(rows, aligned, policy_name)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for policy_name, bets in policy_bets.items():
        safe_name = policy_name.replace("|", "_").replace("/", "_")
        bets.to_csv(output_dir / f"{safe_name}_edge02_bets.csv", index=False)

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
            "edge_threshold": EDGE_THRESHOLD,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "seed": args.seed,
        },
        "metadata": metadata,
        "folds": fold_rows,
        "selected_eval_folds": selected_folds,
        "selection_path": selections,
        "bet_files": {
            policy_name: f"{policy_name.replace('|', '_').replace('/', '_')}_edge02_bets.csv"
            for policy_name in policy_bets
        },
        "policies": {
            policy_name: summarize_policy_bets(
                bets,
                args.bootstrap_iterations,
                args.market_null_iterations,
                rng,
            )
            for policy_name, bets in policy_bets.items()
        },
    }


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_core_regime_stress_audit.json"
    md_path = output_dir / "striking_core_regime_stress_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
