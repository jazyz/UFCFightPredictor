#!/usr/bin/env python3
"""Freeze a capped residual-meta paper policy for future tracking."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.residual_meta_pnl_audit import net_odds_array  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze capped residual-meta paper policy")
    parser.add_argument("--as-of-date", default=datetime.now().date().isoformat())
    parser.add_argument(
        "--transform",
        default="test_results/frozen_market_residual_meta/frozen_market_residual_meta.json",
        help="frozen residual probability transform JSON",
    )
    parser.add_argument(
        "--source-cap-audit",
        default="test_results/residual_event_cap_audit/residual_event_cap_audit.json",
        help="event-cap exploratory audit JSON",
    )
    parser.add_argument(
        "--fixed-policy-bets",
        default="test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv",
        help="historical fixed residual-meta bet ledger for cap diagnostics",
    )
    parser.add_argument("--min-edge", type=float, default=0.02)
    parser.add_argument("--min-probability", type=float, default=0.60)
    parser.add_argument("--max-underdog-odds", type=float, default=300.0)
    parser.add_argument("--max-bets-per-event", type=int, default=3)
    parser.add_argument("--stake-units", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/frozen_residual_event_cap_paper_policy")
    return parser.parse_args()


def load_json(path: str) -> dict | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    with file_path.open() as file:
        return json.load(file)


def fmt_units(value) -> str:
    if value is None:
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


def fmt_p(value) -> str:
    if value is None:
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def load_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "event_date",
        "fight_key",
        "selected_edge",
        "selected_probability",
        "selected_market_probability",
        "selected_odds",
        "selected_won",
        "flat_profit",
        "fold",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing fixed-policy bet columns: {missing}")
    return df.sort_values(["event_date", "selected_edge", "fight_key"], ascending=[True, False, True])


def apply_event_cap(bets: pd.DataFrame, cap: int) -> pd.DataFrame:
    return (
        bets.sort_values(
            ["event_date", "selected_edge", "selected_probability", "fight_key"],
            ascending=[True, False, False, True],
        )
        .groupby("event_date", sort=False)
        .head(cap)
        .copy()
    )


def fold_summaries(bets: pd.DataFrame) -> list[dict]:
    rows = []
    for fold, subset in bets.groupby("fold", sort=True):
        profit = float(subset["flat_profit"].astype(float).sum())
        bet_count = int(len(subset))
        rows.append(
            {
                "fold": int(fold),
                "bets": bet_count,
                "events": int(subset["event_date"].nunique()),
                "profit": profit,
                "roi": profit / bet_count if bet_count else None,
            }
        )
    return rows


def event_bootstrap(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty or iterations <= 0:
        return None
    grouped = bets.groupby("event_date", sort=True).agg(
        profit=("flat_profit", "sum"),
        bets=("fight_key", "size"),
    )
    profits = grouped["profit"].astype(float).to_numpy()
    bet_counts = grouped["bets"].astype(float).to_numpy()
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    sampled_profit = profits[sampled].sum(axis=1)
    sampled_bets = bet_counts[sampled].sum(axis=1)
    sampled_roi = sampled_profit / sampled_bets
    return {
        "iterations": int(iterations),
        "events": int(len(grouped)),
        "profit_ci_95": [float(value) for value in np.percentile(sampled_profit, [2.5, 97.5])],
        "roi_ci_95": [float(value) for value in np.percentile(sampled_roi, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(sampled_profit <= 0.0)),
    }


def market_null(bets: pd.DataFrame, iterations: int, rng) -> dict | None:
    if bets.empty or iterations <= 0:
        return None
    market = bets["selected_market_probability"].astype(float).to_numpy()
    odds = bets["selected_odds"].astype(float).to_numpy()
    net = net_odds_array(odds)
    simulated = rng.random((iterations, len(bets))) < market
    profits = np.where(simulated, net, -1.0).sum(axis=1)
    observed = float(bets["flat_profit"].astype(float).sum())
    return {
        "iterations": int(iterations),
        "observed_profit": observed,
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0.0)),
    }


def historical_cap_diagnostic(path: str, cap: int, iterations: int, rng) -> dict:
    all_bets = load_bets(path)
    capped = apply_event_cap(all_bets, cap)
    profit = float(capped["flat_profit"].astype(float).sum())
    bet_count = int(len(capped))
    folds = fold_summaries(capped)
    actual = float(capped["selected_won"].astype(float).mean()) if bet_count else None
    market = (
        float(capped["selected_market_probability"].astype(float).mean())
        if bet_count
        else None
    )
    return {
        "source_bets_path": path,
        "source_bets": int(len(all_bets)),
        "source_events": int(all_bets["event_date"].nunique()),
        "event_cap": int(cap),
        "bets": bet_count,
        "events": int(capped["event_date"].nunique()),
        "profit": profit,
        "roi": profit / bet_count if bet_count else None,
        "actual_win_rate": actual,
        "mean_market_probability": market,
        "actual_minus_market": actual - market if actual is not None and market is not None else None,
        "mean_probability": float(capped["selected_probability"].astype(float).mean()) if bet_count else None,
        "mean_edge": float(capped["selected_edge"].astype(float).mean()) if bet_count else None,
        "positive_folds": int(sum(row["profit"] > 0 for row in folds)),
        "folds": folds,
        "event_bootstrap": event_bootstrap(capped, iterations, rng),
        "market_null": market_null(capped, iterations, rng),
    }


def find_cap_summary(cap_audit: dict | None, policy_name: str, event_cap: str) -> dict | None:
    if not cap_audit:
        return None
    for row in cap_audit.get("summaries", []):
        if row.get("probability_policy") == policy_name and str(row.get("event_cap")) == str(event_cap):
            return row
    return None


def markdown_report(result: dict) -> str:
    policy = result["policy"]
    transform = result["transform_summary"]
    diagnostic = result["historical_cap_diagnostic"]
    bootstrap = diagnostic.get("event_bootstrap") or {}
    null = diagnostic.get("market_null") or {}
    cap_audit = result.get("source_cap_audit_summary") or {}
    selection_null = result.get("source_selection_adjusted_market_null") or {}

    lines = [
        "# Frozen Residual Event-Cap Paper Policy",
        "",
        f"As-of date: `{result['as_of_date']}`",
        f"Frozen transform: `{result['transform_path']}`",
        f"Exploratory cap audit: `{result['source_cap_audit']}`",
        f"Historical fixed-policy bet ledger: `{diagnostic['source_bets_path']}`",
        "",
        "This is a paper-tracking contract only. It is not a live staking",
        "recommendation. The event cap was chosen after historical diagnostics,",
        "so future outcomes must be tracked unchanged before making an edge claim.",
        "",
        "## Probability Transform",
        "",
        f"- base residual model: `{transform['model_label']}`",
        f"- transform training window: `{transform['dev_start']}` to `{transform['dev_end']}`",
        f"- logistic C: `{transform['c']}`",
        "",
        "| Term | Value |",
        "| --- | ---: |",
        f"| intercept | {transform['intercept']:.8f} |",
    ]
    for feature, coefficient in transform["coefficients"].items():
        lines.append(f"| `{feature}` | {coefficient:.8f} |")

    lines.extend(
        [
            "",
            "## Paper Betting Rule",
            "",
            "For each future event:",
            "",
            "1. Compute de-vigged market probabilities for every fight with available odds.",
            "2. Apply the frozen residual transform to produce red and blue meta probabilities.",
            "3. For each fight, compute each side's residual edge: `meta probability - market probability`.",
            "4. Keep candidate paper bets only when the best side passes the thresholds below.",
            "5. Rank candidates within the event by residual edge, then meta probability, then fight key.",
            "6. Paper bet at most the first `max_bets_per_event` candidates at flat stake.",
            "",
            "| Rule | Value |",
            "| --- | ---: |",
            f"| minimum residual edge | {policy['min_edge']:.2%} |",
            f"| minimum meta probability | {policy['min_probability']:.2%} |",
            f"| maximum underdog odds | +{policy['max_underdog_odds']:.0f} |",
            f"| max bets per event | {policy['max_bets_per_event']} |",
            f"| event ranking | `{policy['event_ranking']}` |",
            f"| stake | {policy['stake_units']:.2f}u flat paper stake |",
            "",
            "## Historical Cap Diagnostic",
            "",
            "This applies the cap to the historical fixed residual-meta paper-policy",
            "bet ledger. It is discovery evidence only, not post-freeze proof.",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| source bets before cap | {diagnostic['source_bets']} |",
            f"| source events before cap | {diagnostic['source_events']} |",
            f"| capped bets | {diagnostic['bets']} |",
            f"| capped events | {diagnostic['events']} |",
            f"| flat profit | {fmt_units(diagnostic['profit'])} |",
            f"| flat ROI | {fmt_pct(diagnostic['roi'])} |",
            f"| actual - market | {fmt_pct(diagnostic['actual_minus_market'])} |",
            f"| positive folds | {diagnostic['positive_folds']} / {len(diagnostic['folds'])} |",
            f"| event-bootstrap P(profit <= 0) | {fmt_p(bootstrap.get('prob_profit_le_zero'))} |",
            f"| market-null p-value | {fmt_p(null.get('p_value_observed_or_better'))} |",
        ]
    )

    if cap_audit:
        cap_boot = cap_audit.get("event_bootstrap") or {}
        cap_null = cap_audit.get("market_null") or {}
        lines.extend(
            [
                "",
                "## Related Exploratory Cap-Family Evidence",
                "",
                "The residual event-cap audit inspected 15 policy/cap variants on the",
                "historical shrinkage fixed-policy ledger.",
                "",
                "| Diagnostic | Value |",
                "| --- | ---: |",
                f"| selected-shrinkage cap-3 profit | {fmt_units(cap_audit.get('profit'))} |",
                f"| selected-shrinkage cap-3 ROI | {fmt_pct(cap_audit.get('roi'))} |",
                f"| selected-shrinkage cap-3 market-null p | {fmt_p(cap_null.get('p_value_observed_or_better'))} |",
                f"| selected-shrinkage cap-3 bootstrap P(profit <= 0) | {fmt_p(cap_boot.get('prob_profit_le_zero'))} |",
                f"| variants inspected in selection-null | {selection_null.get('variants', '')} |",
                f"| best inspected variant | `{selection_null.get('observed_best_variant', '')}` |",
                f"| selection-adjusted market-null p | {fmt_p(selection_null.get('selection_adjusted_p_value'))} |",
            ]
        )

    lines.extend(
        [
            "",
            "## Frozen Rules",
            "",
            "- Do not alter transform coefficients, thresholds, event cap, ranking rule, or stake size after future outcomes are known.",
            "- Generate and archive paper-bet ledgers before outcomes are known.",
            "- Score future paper bets against market-null and event-bootstrap tests before making any real edge claim.",
            "- Keep this capped policy separate from live staking until enough post-freeze evidence accrues.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    transform = load_json(args.transform)
    if transform is None:
        raise SystemExit(f"Missing frozen transform: {args.transform}")
    cap_audit = load_json(args.source_cap_audit)

    transform_summary = {
        "model_label": transform["model_label"],
        "dev_start": transform["dev_start"],
        "dev_end": transform["dev_end"],
        "c": transform["c"],
        "intercept": transform["transform"]["intercept"],
        "coefficients": transform["transform"]["coefficients"],
    }
    cap_diagnostic = historical_cap_diagnostic(
        args.fixed_policy_bets,
        args.max_bets_per_event,
        args.iterations,
        rng,
    )
    result = {
        "as_of_date": args.as_of_date,
        "transform_path": args.transform,
        "source_cap_audit": args.source_cap_audit,
        "transform_summary": transform_summary,
        "policy": {
            "side_policy": "best_residual_edge",
            "min_edge": args.min_edge,
            "min_probability": args.min_probability,
            "max_underdog_odds": args.max_underdog_odds,
            "max_bets_per_event": args.max_bets_per_event,
            "event_ranking": "selected_edge desc, selected_probability desc, fight_key asc",
            "stake_units": args.stake_units,
            "settlement": "flat_units",
        },
        "historical_cap_diagnostic": cap_diagnostic,
        "source_cap_audit_summary": find_cap_summary(
            cap_audit,
            "selected_shrinkage",
            str(args.max_bets_per_event),
        ),
        "source_selection_adjusted_market_null": (
            (cap_audit or {}).get("selection_adjusted_market_null")
        ),
        "freeze_warning": (
            "This capped residual-meta paper policy is frozen for future paper "
            "tracking. Do not alter transform coefficients, thresholds, event cap, "
            "ranking rule, or stake size after future outcomes are known."
        ),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "frozen_residual_event_cap_paper_policy.json"
    md_path = output_dir / "frozen_residual_event_cap_paper_policy.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    print(f"Frozen capped residual paper policy as of {args.as_of_date}")
    print(f"Max bets per event: {args.max_bets_per_event}")
    print(f"Historical capped profit: {fmt_units(cap_diagnostic['profit'])}")
    print(f"Historical capped market-null p: {fmt_p((cap_diagnostic.get('market_null') or {}).get('p_value_observed_or_better'))}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
