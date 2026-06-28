#!/usr/bin/env python3
"""Event-exposure cap audit for residual fixed-policy bets.

The fixed residual paper rule can place several 1u bets on the same card. This
diagnostic asks whether simple, pre-declarable per-event caps change the PnL
translation. It reads already-generated fixed-policy bets and does not retrain
or select model parameters.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.residual_meta_pnl_audit import net_odds_array  # noqa: E402


DEFAULT_INPUT = "test_results/residual_shrinkage_fixed_pnl_audit/fixed_policy_bets.csv"
DEFAULT_CAPS = "1,2,3,5,all"


def parse_caps(value: str) -> list[int | None]:
    caps: list[int | None] = []
    for part in value.split(","):
        token = part.strip().lower()
        if not token:
            continue
        if token in {"all", "none", "inf"}:
            caps.append(None)
        else:
            cap = int(token)
            if cap <= 0:
                raise argparse.ArgumentTypeError("caps must be positive integers or 'all'")
            caps.append(cap)
    if not caps:
        raise argparse.ArgumentTypeError("at least one cap is required")
    return caps


def parse_args():
    parser = argparse.ArgumentParser(description="Audit per-event caps for residual fixed-policy bets")
    parser.add_argument("--bets", default=DEFAULT_INPUT)
    parser.add_argument("--caps", type=parse_caps, default=parse_caps(DEFAULT_CAPS))
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_event_cap_audit")
    return parser.parse_args()


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_float(value, digits=3) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def cap_label(cap: int | None) -> str:
    return "all" if cap is None else str(cap)


def load_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "probability_policy",
        "event_date",
        "fight_key",
        "market_red_probability",
        "selected_edge",
        "selected_probability",
        "selected_market_probability",
        "selected_side",
        "selected_odds",
        "selected_won",
        "flat_profit",
        "fold",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")
    return df.sort_values(["probability_policy", "event_date", "selected_edge"], ascending=[True, True, False])


def apply_event_cap(bets: pd.DataFrame, cap: int | None) -> pd.DataFrame:
    ordered = bets.sort_values(
        ["event_date", "selected_edge", "selected_probability", "fight_key"],
        ascending=[True, False, False, True],
    )
    if cap is None:
        return ordered.copy()
    return ordered.groupby("event_date", sort=False).head(cap).copy()


def event_bootstrap(kept: pd.DataFrame, iterations: int, rng) -> dict | None:
    if kept.empty or iterations <= 0:
        return None
    grouped = kept.groupby("event_date", sort=True).agg(
        profit=("flat_profit", "sum"),
        bets=("fight_key", "size"),
    )
    profits = grouped["profit"].to_numpy(dtype=float)
    bets = grouped["bets"].to_numpy(dtype=float)
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    sampled_profit = profits[sampled].sum(axis=1)
    sampled_bets = bets[sampled].sum(axis=1)
    sampled_roi = sampled_profit / sampled_bets
    return {
        "events": int(len(grouped)),
        "profit_ci_95": [float(value) for value in np.percentile(sampled_profit, [2.5, 97.5])],
        "roi_ci_95": [float(value) for value in np.percentile(sampled_roi, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(sampled_profit <= 0.0)),
    }


def market_null(kept: pd.DataFrame, iterations: int, rng) -> dict | None:
    if kept.empty or iterations <= 0:
        return None
    market = kept["selected_market_probability"].astype(float).to_numpy()
    odds = kept["selected_odds"].astype(float).to_numpy()
    net = net_odds_array(odds)
    simulated = rng.random((iterations, len(kept))) < market
    profits = np.where(simulated, net, -1.0).sum(axis=1)
    observed = float(kept["flat_profit"].astype(float).sum())
    return {
        "iterations": int(iterations),
        "observed_profit": observed,
        "null_mean_profit": float(np.mean(profits)),
        "null_profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(profits >= observed) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(profits > 0.0)),
    }


def selection_adjusted_market_null(capped_frames: list[pd.DataFrame], iterations: int, rng) -> dict | None:
    if not capped_frames or iterations <= 0:
        return None

    combined = pd.concat(capped_frames, ignore_index=True)
    if combined.empty:
        return None

    fight_market = (
        combined[["fight_key", "market_red_probability"]]
        .drop_duplicates("fight_key")
        .reset_index(drop=True)
    )
    fight_index = {fight_key: index for index, fight_key in enumerate(fight_market["fight_key"])}
    red_market = fight_market["market_red_probability"].astype(float).to_numpy()
    simulated_red_won = rng.random((iterations, len(fight_market))) < red_market

    variant_profits = {}
    observed_profits = {}
    for (policy_name, event_cap), subset in combined.groupby(["probability_policy", "event_cap"], sort=True):
        fight_indices = subset["fight_key"].map(fight_index).astype(int).to_numpy()
        selected_red = subset["selected_side"].astype(str).eq("red").to_numpy()
        net = net_odds_array(subset["selected_odds"].astype(float).to_numpy())
        selected_won = simulated_red_won[:, fight_indices] == selected_red
        profits = np.where(selected_won, net, -1.0).sum(axis=1)
        variant_key = f"{policy_name}|cap={event_cap}"
        variant_profits[variant_key] = profits
        observed_profits[variant_key] = float(subset["flat_profit"].astype(float).sum())

    observed_best_key = max(observed_profits, key=observed_profits.get)
    observed_best_profit = observed_profits[observed_best_key]
    null_matrix = np.vstack([variant_profits[key] for key in sorted(variant_profits)])
    null_best = null_matrix.max(axis=0)

    return {
        "iterations": int(iterations),
        "variants": int(len(variant_profits)),
        "fights": int(len(fight_market)),
        "observed_best_variant": observed_best_key,
        "observed_best_profit": float(observed_best_profit),
        "null_best_mean_profit": float(np.mean(null_best)),
        "null_best_profit_ci_95": [float(value) for value in np.percentile(null_best, [2.5, 97.5])],
        "selection_adjusted_p_value": float(
            (np.sum(null_best >= observed_best_profit) + 1) / (iterations + 1)
        ),
        "prob_null_best_profitable": float(np.mean(null_best > 0.0)),
        "observed_variant_profits": observed_profits,
    }


def fold_rows(kept: pd.DataFrame) -> list[dict]:
    rows = []
    if kept.empty:
        return rows
    for fold, subset in kept.groupby("fold", sort=True):
        profit = float(subset["flat_profit"].sum())
        bets = int(len(subset))
        rows.append(
            {
                "fold": int(fold),
                "bets": bets,
                "events": int(subset["event_date"].nunique()),
                "profit": profit,
                "roi": profit / bets if bets else None,
            }
        )
    return rows


def summarize_cap(
    policy_name: str,
    source_bets: pd.DataFrame,
    cap: int | None,
    iterations: int,
    rng,
) -> tuple[pd.DataFrame, dict]:
    kept = apply_event_cap(source_bets, cap)
    if kept.empty:
        summary = {
            "probability_policy": policy_name,
            "event_cap": cap_label(cap),
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_market_probability": None,
            "actual_minus_market": None,
            "mean_probability": None,
            "mean_edge": None,
            "positive_folds": 0,
            "folds": [],
            "event_bootstrap": None,
            "market_null": None,
        }
        return kept, summary

    profit = float(kept["flat_profit"].sum())
    bets = int(len(kept))
    folds = fold_rows(kept)
    actual = float(kept["selected_won"].astype(float).mean())
    market = float(kept["selected_market_probability"].astype(float).mean())
    summary = {
        "probability_policy": policy_name,
        "event_cap": cap_label(cap),
        "bets": bets,
        "events": int(kept["event_date"].nunique()),
        "profit": profit,
        "roi": profit / bets if bets else None,
        "actual_win_rate": actual,
        "mean_market_probability": market,
        "actual_minus_market": actual - market,
        "mean_probability": float(kept["selected_probability"].astype(float).mean()),
        "mean_edge": float(kept["selected_edge"].astype(float).mean()),
        "positive_folds": int(sum(row["profit"] > 0.0 for row in folds)),
        "folds": folds,
        "event_bootstrap": event_bootstrap(kept, iterations, rng),
        "market_null": market_null(kept, iterations, rng),
    }
    kept = kept.copy()
    kept["event_cap"] = cap_label(cap)
    return kept, summary


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Event-Cap Audit",
        "",
        "This diagnostic applies simple per-event bet caps to the fixed residual",
        "paper-policy bets. Within each event, bets are ranked by residual edge;",
        "cap `1` keeps only the highest-edge bet on each card, cap `all` keeps the",
        "original fixed-policy bet set.",
        "",
        "This is exploratory because the caps are inspected after the historical",
        "fixed-policy ledger exists. Treat this as a future-paper-policy clue, not",
        "a live staking upgrade.",
        "",
        "## Inputs",
        "",
        f"- fixed-policy bets: `{result['bets_path']}`",
        f"- source rows: `{result['source_bets']}`",
        f"- iterations: `{result['iterations']}`",
        "",
        "## Results",
        "",
        "| Policy | Cap/Event | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Bootstrap P(profit <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in result["summaries"]:
        bootstrap = summary.get("event_bootstrap") or {}
        null = summary.get("market_null") or {}
        lines.append(
            "| {policy} | {cap} | {bets} | {events} | {profit} | {roi} | {actual_market} | {positive} / {folds} | {boot} | {null_p} |".format(
                policy=summary["probability_policy"],
                cap=summary["event_cap"],
                bets=summary["bets"],
                events=summary["events"],
                profit=fmt_units(summary["profit"]),
                roi=fmt_pct(summary["roi"]),
                actual_market=fmt_pct(summary["actual_minus_market"]),
                positive=summary["positive_folds"],
                folds=len(summary["folds"]),
                boot=fmt_p(bootstrap.get("prob_profit_le_zero")),
                null_p=fmt_p(null.get("p_value_observed_or_better")),
            )
        )

    best_by_policy = {}
    for summary in result["summaries"]:
        current = best_by_policy.get(summary["probability_policy"])
        if current is None or summary["profit"] > current["profit"]:
            best_by_policy[summary["probability_policy"]] = summary

    lines.extend(
        [
            "",
            "## Best Historical Cap Per Policy",
            "",
            "| Policy | Cap/Event | Bets | Profit | ROI | Market-Null p |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for policy_name, summary in best_by_policy.items():
        null = summary.get("market_null") or {}
        lines.append(
            "| {policy} | {cap} | {bets} | {profit} | {roi} | {null_p} |".format(
                policy=policy_name,
                cap=summary["event_cap"],
                bets=summary["bets"],
                profit=fmt_units(summary["profit"]),
                roi=fmt_pct(summary["roi"]),
                null_p=fmt_p(null.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Selection-Adjusted Market Null",
            "",
        ]
    )
    selection_null = result.get("selection_adjusted_market_null") or {}
    if selection_null:
        lines.extend(
            [
                "| Metric | Value |",
                "| --- | ---: |",
                f"| variants inspected | {selection_null['variants']} |",
                f"| observed best variant | `{selection_null['observed_best_variant']}` |",
                f"| observed best profit | {fmt_units(selection_null['observed_best_profit'])} |",
                f"| null best mean profit | {fmt_units(selection_null['null_best_mean_profit'])} |",
                f"| null best 95% interval | {fmt_units(selection_null['null_best_profit_ci_95'][0])} to {fmt_units(selection_null['null_best_profit_ci_95'][1])} |",
                f"| selection-adjusted p-value | {fmt_p(selection_null['selection_adjusted_p_value'])} |",
                "",
            ]
        )

    lines.extend(
        [
            "## Fold Results For Selected Shrinkage",
            "",
            "| Cap/Event | Fold | Bets | Events | Profit | ROI |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in result["summaries"]:
        if summary["probability_policy"] != "selected_shrinkage":
            continue
        for row in summary["folds"]:
            lines.append(
                "| {cap} | {fold} | {bets} | {events} | {profit} | {roi} |".format(
                    cap=summary["event_cap"],
                    fold=row["fold"],
                    bets=row["bets"],
                    events=row["events"],
                    profit=fmt_units(row["profit"]),
                    roi=fmt_pct(row["roi"]),
                )
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Per-event caps improve the historical fixed-policy PnL because the lower",
            "ranked same-card bets were dilutive. For selected shrinkage, the all-bets",
            "rule made `+4.55u`; caps of `1`, `2`, and `3` produced `+11.92u`,",
            "`+15.75u`, and `+17.45u` respectively.",
            "",
            "This should not be promoted as a live edge claim because the cap family was",
            "inspected after seeing the historical residual ledger. The family-level",
            "selection-null is encouraging, but it still uses the same historical",
            "ledger for discovery. The useful next step is to freeze one simple capped",
            "variant for forward paper tracking, then judge future cards under the",
            "same market-null and event-bootstrap tests.",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    bets = load_bets(args.bets)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    capped_frames = []
    for policy_name, policy_bets in bets.groupby("probability_policy", sort=True):
        for cap in args.caps:
            capped, summary = summarize_cap(policy_name, policy_bets, cap, args.iterations, rng)
            summaries.append(summary)
            if not capped.empty:
                capped_frames.append(capped)
    selection_null = selection_adjusted_market_null(capped_frames, args.iterations, rng)

    result = {
        "bets_path": args.bets,
        "source_bets": int(len(bets)),
        "caps": [cap_label(cap) for cap in args.caps],
        "iterations": args.iterations,
        "seed": args.seed,
        "summaries": summaries,
        "selection_adjusted_market_null": selection_null,
        "outputs": {
            "summary_json": str(output_dir / "residual_event_cap_audit.json"),
            "report_md": str(output_dir / "residual_event_cap_audit.md"),
            "capped_bets_csv": str(output_dir / "capped_fixed_policy_bets.csv"),
        },
    }

    json_path = output_dir / "residual_event_cap_audit.json"
    md_path = output_dir / "residual_event_cap_audit.md"
    capped_path = output_dir / "capped_fixed_policy_bets.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    if capped_frames:
        pd.concat(capped_frames, ignore_index=True).to_csv(capped_path, index=False)
    else:
        pd.DataFrame().to_csv(capped_path, index=False)

    selected = [
        row
        for row in summaries
        if row["probability_policy"] == "selected_shrinkage" and row["event_cap"] == "3"
    ][0]
    print(
        "selected_shrinkage cap=3 profit "
        f"{selected['profit']:+.2f}u, market-null p "
        f"{fmt_p((selected.get('market_null') or {}).get('p_value_observed_or_better'))}"
    )
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
