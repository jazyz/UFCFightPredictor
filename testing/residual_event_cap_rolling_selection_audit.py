#!/usr/bin/env python3
"""Rolling selection audit for residual event-cap policies.

The event-cap audit showed that capped variants look much better historically,
but those caps were inspected after the full ledger existed. This audit uses a
prequential protocol: for each future fold, select a cap/policy only from prior
folds, then score the selected variant on the next fold.
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

from testing.residual_event_cap_audit import apply_event_cap, cap_label, parse_caps  # noqa: E402
from testing.residual_meta_pnl_audit import net_odds_array  # noqa: E402


DEFAULT_CAPPED_BETS = "test_results/residual_event_cap_audit/capped_fixed_policy_bets.csv"
DEFAULT_FIXED_BETS = "test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv"
DEFAULT_CAPS = "1,2,3,5,all"
VARIANT_COLUMNS = ("probability_policy", "event_cap")


def parse_args():
    parser = argparse.ArgumentParser(description="Rolling selection audit for event-cap policies")
    parser.add_argument("--capped-bets", default=DEFAULT_CAPPED_BETS)
    parser.add_argument("--fixed-bets", default=DEFAULT_FIXED_BETS)
    parser.add_argument("--caps", type=parse_caps, default=parse_caps(DEFAULT_CAPS))
    parser.add_argument("--min-dev-bets", type=int, default=35)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_event_cap_rolling_selection_audit")
    return parser.parse_args()


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.2f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def cap_sort_value(value: str) -> tuple[int, int]:
    return (1, 999999) if value == "all" else (0, int(value))


def variant_sort_key(variant: tuple[str, str]) -> tuple[str, tuple[int, int]]:
    return (variant[0], cap_sort_value(variant[1]))


def load_capped_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "probability_policy",
        "event_cap",
        "event_date",
        "fight_key",
        "market_red_probability",
        "selected_side",
        "selected_odds",
        "selected_won",
        "flat_profit",
        "fold",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing capped-bet columns: {missing}")
    df["event_cap"] = df["event_cap"].astype(str)
    return df


def load_fixed_cap_family(path: str, caps: list[int | None], policy_name: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "event_date",
        "fight_key",
        "market_red_probability",
        "selected_edge",
        "selected_probability",
        "selected_side",
        "selected_odds",
        "selected_won",
        "flat_profit",
        "fold",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing fixed-policy bet columns: {missing}")
    frames = []
    for cap in caps:
        capped = apply_event_cap(df, cap)
        capped = capped.copy()
        capped["probability_policy"] = policy_name
        capped["event_cap"] = cap_label(cap)
        frames.append(capped)
    return pd.concat(frames, ignore_index=True)


def variant_stats(df: pd.DataFrame) -> dict[tuple[str, str, int], dict]:
    stats = {}
    for (policy, cap, fold), subset in df.groupby(["probability_policy", "event_cap", "fold"], sort=True):
        profit = float(subset["flat_profit"].astype(float).sum())
        bets = int(len(subset))
        stats[(str(policy), str(cap), int(fold))] = {
            "profit": profit,
            "bets": bets,
            "events": int(subset["event_date"].nunique()),
            "roi": profit / bets if bets else None,
        }
    return stats


def candidate_score(profit: float, bets: int, objective: str) -> tuple:
    roi = profit / bets if bets else float("-inf")
    if objective == "roi":
        return (roi, profit, bets)
    return (profit, roi, bets)


def select_variant(
    stats: dict[tuple[str, str, int], dict],
    variants: list[tuple[str, str]],
    prior_folds: list[int],
    objective: str,
    min_dev_bets: int,
    profit_override: dict[tuple[str, str, int], float] | None = None,
):
    best_variant = None
    best_score = None
    best_summary = None
    for variant in variants:
        dev_profit = 0.0
        dev_bets = 0
        dev_events = 0
        for fold in prior_folds:
            row = stats.get((variant[0], variant[1], fold))
            if row is None:
                continue
            dev_profit += (
                profit_override.get((variant[0], variant[1], fold), row["profit"])
                if profit_override is not None
                else row["profit"]
            )
            dev_bets += row["bets"]
            dev_events += row["events"]
        if dev_bets < min_dev_bets:
            continue
        score = candidate_score(dev_profit, dev_bets, objective)
        sort_key = (*score, tuple(reversed(variant_sort_key(variant))))
        if best_score is None or sort_key > best_score:
            best_score = sort_key
            best_variant = variant
            best_summary = {
                "profit": float(dev_profit),
                "bets": int(dev_bets),
                "events": int(dev_events),
                "roi": float(dev_profit / dev_bets) if dev_bets else None,
            }
    return best_variant, best_summary


def observed_rolling_selection(
    df: pd.DataFrame,
    objective: str,
    min_dev_bets: int,
) -> tuple[list[dict], pd.DataFrame, dict]:
    stats = variant_stats(df)
    folds = sorted(int(value) for value in df["fold"].unique())
    variants = sorted(
        {(str(row.probability_policy), str(row.event_cap)) for row in df.itertuples()},
        key=variant_sort_key,
    )
    selections = []
    selected_frames = []
    for eval_fold in folds[1:]:
        variant, dev_summary = select_variant(
            stats,
            variants,
            [fold for fold in folds if fold < eval_fold],
            objective,
            min_dev_bets,
        )
        if variant is None:
            continue
        eval_subset = df[
            (df["probability_policy"].astype(str) == variant[0])
            & (df["event_cap"].astype(str) == variant[1])
            & (df["fold"].astype(int) == eval_fold)
        ].copy()
        profit = float(eval_subset["flat_profit"].astype(float).sum())
        bets = int(len(eval_subset))
        selections.append(
            {
                "eval_fold": int(eval_fold),
                "selected_policy": variant[0],
                "selected_cap": variant[1],
                "dev_profit": dev_summary["profit"],
                "dev_bets": dev_summary["bets"],
                "dev_roi": dev_summary["roi"],
                "eval_bets": bets,
                "eval_events": int(eval_subset["event_date"].nunique()),
                "eval_profit": profit,
                "eval_roi": profit / bets if bets else None,
            }
        )
        if not eval_subset.empty:
            eval_subset["rolling_objective"] = objective
            eval_subset["rolling_eval_fold"] = int(eval_fold)
            selected_frames.append(eval_subset)
    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    total_profit = float(selected["flat_profit"].astype(float).sum()) if not selected.empty else 0.0
    total_bets = int(len(selected))
    summary = {
        "objective": objective,
        "eval_folds": int(len(selections)),
        "bets": total_bets,
        "events": int(selected["event_date"].nunique()) if not selected.empty else 0,
        "profit": total_profit,
        "roi": total_profit / total_bets if total_bets else None,
        "positive_eval_folds": int(sum(row["eval_profit"] > 0.0 for row in selections)),
        "selections": selections,
    }
    return selections, selected, summary


def event_bootstrap(selected: pd.DataFrame, iterations: int, rng) -> dict | None:
    if selected.empty or iterations <= 0:
        return None
    grouped = selected.groupby("event_date", sort=True).agg(
        profit=("flat_profit", "sum"),
        bets=("fight_key", "size"),
    )
    profits = grouped["profit"].astype(float).to_numpy()
    bets = grouped["bets"].astype(float).to_numpy()
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    sample_profit = profits[sampled].sum(axis=1)
    sample_bets = bets[sampled].sum(axis=1)
    return {
        "iterations": int(iterations),
        "events": int(len(grouped)),
        "profit_ci_95": [float(value) for value in np.percentile(sample_profit, [2.5, 97.5])],
        "roi_ci_95": [float(value) for value in np.percentile(sample_profit / sample_bets, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(sample_profit <= 0.0)),
    }


def rolling_market_null(
    df: pd.DataFrame,
    objective: str,
    min_dev_bets: int,
    observed_profit: float,
    iterations: int,
    rng,
) -> dict | None:
    if df.empty or iterations <= 0:
        return None
    stats = variant_stats(df)
    folds = sorted(int(value) for value in df["fold"].unique())
    variants = sorted(
        {(str(row.probability_policy), str(row.event_cap)) for row in df.itertuples()},
        key=variant_sort_key,
    )

    fight_market = (
        df[["fight_key", "market_red_probability"]]
        .drop_duplicates("fight_key")
        .reset_index(drop=True)
    )
    fight_index = {fight_key: index for index, fight_key in enumerate(fight_market["fight_key"])}
    red_market = fight_market["market_red_probability"].astype(float).to_numpy()
    simulated_red_won = rng.random((iterations, len(fight_market))) < red_market

    profit_by_variant_fold: dict[tuple[str, str, int], np.ndarray] = {}
    for (policy, cap, fold), subset in df.groupby(["probability_policy", "event_cap", "fold"], sort=True):
        fight_indices = subset["fight_key"].map(fight_index).astype(int).to_numpy()
        selected_red = subset["selected_side"].astype(str).eq("red").to_numpy()
        net = net_odds_array(subset["selected_odds"].astype(float).to_numpy())
        selected_won = simulated_red_won[:, fight_indices] == selected_red
        profit_by_variant_fold[(str(policy), str(cap), int(fold))] = np.where(selected_won, net, -1.0).sum(axis=1)

    simulated_totals = np.zeros(iterations, dtype=float)
    selected_counts: dict[str, int] = {}
    for iteration in range(iterations):
        overrides = {
            key: float(values[iteration])
            for key, values in profit_by_variant_fold.items()
        }
        total = 0.0
        for eval_fold in folds[1:]:
            variant, _ = select_variant(
                stats,
                variants,
                [fold for fold in folds if fold < eval_fold],
                objective,
                min_dev_bets,
                profit_override=overrides,
            )
            if variant is None:
                continue
            selected_counts[f"{variant[0]}|cap={variant[1]}"] = selected_counts.get(
                f"{variant[0]}|cap={variant[1]}",
                0,
            ) + 1
            total += float(overrides.get((variant[0], variant[1], eval_fold), 0.0))
        simulated_totals[iteration] = total

    return {
        "iterations": int(iterations),
        "observed_profit": float(observed_profit),
        "null_mean_profit": float(np.mean(simulated_totals)),
        "null_profit_ci_95": [float(value) for value in np.percentile(simulated_totals, [2.5, 97.5])],
        "p_value_observed_or_better": float(
            (np.sum(simulated_totals >= observed_profit) + 1) / (iterations + 1)
        ),
        "prob_null_profitable": float(np.mean(simulated_totals > 0.0)),
        "selected_variant_frequency": selected_counts,
    }


def run_family(
    name: str,
    df: pd.DataFrame,
    objectives: list[str],
    min_dev_bets: int,
    iterations: int,
    rng,
) -> tuple[list[dict], list[pd.DataFrame]]:
    results = []
    selected_frames = []
    for objective in objectives:
        _, selected, summary = observed_rolling_selection(df, objective, min_dev_bets)
        summary["family"] = name
        summary["variants"] = int(df[list(VARIANT_COLUMNS)].drop_duplicates().shape[0])
        summary["event_bootstrap"] = event_bootstrap(selected, iterations, rng)
        summary["rolling_market_null"] = rolling_market_null(
            df,
            objective,
            min_dev_bets,
            summary["profit"],
            iterations,
            rng,
        )
        results.append(summary)
        if not selected.empty:
            selected = selected.copy()
            selected["rolling_family"] = name
            selected_frames.append(selected)
    return results, selected_frames


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Event-Cap Rolling Selection Audit",
        "",
        "This audit tests whether capped residual policies would have been selected",
        "using only earlier folds. For each evaluation fold after fold 1, the",
        "selector chooses a cap/policy from prior folds only, then scores the",
        "chosen variant on the next fold.",
        "",
        "## Inputs",
        "",
        f"- capped shrinkage bets: `{result['capped_bets_path']}`",
        f"- fixed residual-meta bets: `{result['fixed_bets_path']}`",
        f"- minimum development bets: `{result['min_dev_bets']}`",
        f"- market-null iterations: `{result['iterations']}`",
        "",
        "## Rolling Results",
        "",
        "| Family | Objective | Variants | Eval Folds | Bets | Profit | ROI | Positive Folds | Bootstrap P(profit <= 0) | Rolling Market-Null p |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in result["summaries"]:
        bootstrap = summary.get("event_bootstrap") or {}
        null = summary.get("rolling_market_null") or {}
        lines.append(
            "| {family} | {objective} | {variants} | {folds} | {bets} | {profit} | {roi} | {pos} / {folds} | {boot} | {null_p} |".format(
                family=summary["family"],
                objective=summary["objective"],
                variants=summary["variants"],
                folds=summary["eval_folds"],
                bets=summary["bets"],
                profit=fmt_units(summary["profit"]),
                roi=fmt_pct(summary["roi"]),
                pos=summary["positive_eval_folds"],
                boot=fmt_p(bootstrap.get("prob_profit_le_zero")),
                null_p=fmt_p(null.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Fold Selections",
            "",
            "| Family | Objective | Eval Fold | Selected Variant | Dev Profit | Dev Bets | Eval Bets | Eval Profit | Eval ROI |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in result["summaries"]:
        for row in summary["selections"]:
            lines.append(
                "| {family} | {objective} | {fold} | {variant} | {dev_profit} | {dev_bets} | {eval_bets} | {eval_profit} | {eval_roi} |".format(
                    family=summary["family"],
                    objective=summary["objective"],
                    fold=row["eval_fold"],
                    variant=f"{row['selected_policy']}|cap={row['selected_cap']}",
                    dev_profit=fmt_units(row["dev_profit"]),
                    dev_bets=row["dev_bets"],
                    eval_bets=row["eval_bets"],
                    eval_profit=fmt_units(row["eval_profit"]),
                    eval_roi=fmt_pct(row["eval_roi"]),
                )
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a stricter check than the static event-cap audit. It does not ask",
            "whether cap `3` looked best after all outcomes were known; it asks whether",
            "a simple rolling selector using only earlier folds would keep choosing",
            "capped residual variants that work on later folds.",
            "",
            "The result should be read alongside the frozen capped paper policy: a",
            "positive rolling result strengthens the case for forward paper tracking,",
            "but it still does not replace genuinely post-freeze evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    capped = load_capped_bets(args.capped_bets)
    fixed_caps = load_fixed_cap_family(args.fixed_bets, args.caps, "frozen_residual_meta")

    families = {
        "frozen_residual_meta_caps": fixed_caps,
        "selected_shrinkage_caps": capped[capped["probability_policy"].eq("selected_shrinkage")].copy(),
        "all_shrinkage_policy_caps": capped.copy(),
    }

    all_summaries = []
    selected_frames = []
    for family_name, family_df in families.items():
        summaries, frames = run_family(
            family_name,
            family_df,
            ["profit", "roi"],
            args.min_dev_bets,
            args.iterations,
            rng,
        )
        all_summaries.extend(summaries)
        selected_frames.extend(frames)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "capped_bets_path": args.capped_bets,
        "fixed_bets_path": args.fixed_bets,
        "caps": [cap_label(cap) for cap in args.caps],
        "min_dev_bets": args.min_dev_bets,
        "iterations": args.iterations,
        "seed": args.seed,
        "summaries": all_summaries,
        "outputs": {
            "summary_json": str(output_dir / "residual_event_cap_rolling_selection_audit.json"),
            "report_md": str(output_dir / "residual_event_cap_rolling_selection_audit.md"),
            "selected_bets_csv": str(output_dir / "rolling_selected_bets.csv"),
        },
    }

    json_path = output_dir / "residual_event_cap_rolling_selection_audit.json"
    md_path = output_dir / "residual_event_cap_rolling_selection_audit.md"
    selected_path = output_dir / "rolling_selected_bets.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    if selected_frames:
        pd.concat(selected_frames, ignore_index=True).to_csv(selected_path, index=False)
    else:
        pd.DataFrame().to_csv(selected_path, index=False)

    best = max(all_summaries, key=lambda row: row["profit"])
    print(
        f"Best rolling result: {best['family']} {best['objective']} "
        f"{fmt_units(best['profit'])}, p="
        f"{fmt_p((best.get('rolling_market_null') or {}).get('p_value_observed_or_better'))}"
    )
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
