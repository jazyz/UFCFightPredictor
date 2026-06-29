#!/usr/bin/env python3
"""Ranking audit for capped residual paper bets.

The frozen capped residual policy keeps the top residual-edge candidates within
each event. This diagnostic checks whether that ranking rule adds value versus
bottom-edge or random same-event caps with the same bet count.
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


DEFAULT_FIXED_META_BETS = "test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv"
DEFAULT_SHRINKAGE_BETS = "test_results/residual_shrinkage_fixed_pnl_audit/fixed_policy_bets.csv"


def parse_args():
    parser = argparse.ArgumentParser(description="Audit capped residual ranking rule")
    parser.add_argument("--fixed-meta-bets", default=DEFAULT_FIXED_META_BETS)
    parser.add_argument("--shrinkage-bets", default=DEFAULT_SHRINKAGE_BETS)
    parser.add_argument("--cap", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_event_cap_ranking_audit")
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
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def load_fixed_meta(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    df["probability_policy"] = "frozen_residual_meta"
    return validate_bets(df, path)


def load_shrinkage(path: str) -> dict[str, pd.DataFrame]:
    df = pd.read_csv(path, parse_dates=["event_date"])
    validate_bets(df, path)
    return {
        str(policy): subset.copy()
        for policy, subset in df.groupby("probability_policy", sort=True)
    }


def validate_bets(df: pd.DataFrame, path: str) -> pd.DataFrame:
    required = {
        "probability_policy",
        "event_date",
        "fight_key",
        "selected_edge",
        "selected_probability",
        "selected_market_probability",
        "flat_profit",
        "fold",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"{path} missing required columns: {missing}")
    return df.copy()


def rank_subset(df: pd.DataFrame, cap: int, mode: str) -> pd.DataFrame:
    if mode == "top_edge":
        ordered = df.sort_values(
            ["event_date", "selected_edge", "selected_probability", "fight_key"],
            ascending=[True, False, False, True],
        )
    elif mode == "bottom_edge":
        ordered = df.sort_values(
            ["event_date", "selected_edge", "selected_probability", "fight_key"],
            ascending=[True, True, True, True],
        )
    elif mode == "top_probability":
        ordered = df.sort_values(
            ["event_date", "selected_probability", "selected_edge", "fight_key"],
            ascending=[True, False, False, True],
        )
    elif mode == "top_market_probability":
        ordered = df.sort_values(
            ["event_date", "selected_market_probability", "selected_edge", "fight_key"],
            ascending=[True, False, False, True],
        )
    else:
        raise ValueError(f"Unknown rank mode: {mode}")
    return ordered.groupby("event_date", sort=False).head(cap).copy()


def summarize_bets(bets: pd.DataFrame) -> dict:
    if bets.empty:
        return {
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_minus_market": None,
            "positive_folds": 0,
            "folds": [],
        }
    profit = float(bets["flat_profit"].astype(float).sum())
    bet_count = int(len(bets))
    fold_rows = []
    for fold, subset in bets.groupby("fold", sort=True):
        fold_profit = float(subset["flat_profit"].astype(float).sum())
        fold_bets = int(len(subset))
        fold_rows.append(
            {
                "fold": int(fold),
                "bets": fold_bets,
                "profit": fold_profit,
                "roi": fold_profit / fold_bets if fold_bets else None,
            }
        )
    return {
        "bets": bet_count,
        "events": int(bets["event_date"].nunique()),
        "profit": profit,
        "roi": profit / bet_count if bet_count else None,
        "actual_minus_market": (
            float(bets["selected_won"].astype(float).mean())
            - float(bets["selected_market_probability"].astype(float).mean())
            if "selected_won" in bets.columns
            else None
        ),
        "positive_folds": int(sum(row["profit"] > 0 for row in fold_rows)),
        "folds": fold_rows,
    }


def random_cap_distribution(df: pd.DataFrame, cap: int, iterations: int, rng) -> dict:
    event_groups = []
    for event_date, subset in df.groupby("event_date", sort=True):
        profits = subset["flat_profit"].astype(float).to_numpy()
        folds = subset["fold"].astype(int).to_numpy()
        keep = min(cap, len(profits))
        event_groups.append((event_date, profits, folds, keep))

    totals = np.zeros(iterations, dtype=float)
    fold_positive = np.zeros(iterations, dtype=float)
    for iteration in range(iterations):
        fold_profit = {}
        total = 0.0
        for _, profits, folds, keep in event_groups:
            if keep == len(profits):
                chosen = np.arange(len(profits))
            else:
                chosen = rng.choice(len(profits), size=keep, replace=False)
            selected_profit = profits[chosen]
            total += float(selected_profit.sum())
            for fold, value in zip(folds[chosen], selected_profit):
                fold_profit[int(fold)] = fold_profit.get(int(fold), 0.0) + float(value)
        totals[iteration] = total
        fold_positive[iteration] = sum(value > 0.0 for value in fold_profit.values())

    return {
        "iterations": int(iterations),
        "random_mean_profit": float(np.mean(totals)),
        "random_profit_ci_95": [float(value) for value in np.percentile(totals, [2.5, 97.5])],
        "prob_random_profit_positive": float(np.mean(totals > 0.0)),
        "random_positive_folds_mean": float(np.mean(fold_positive)),
        "profit_samples": totals,
    }


def audit_policy(policy_name: str, df: pd.DataFrame, cap: int, iterations: int, rng) -> tuple[dict, pd.DataFrame]:
    modes = ["top_edge", "bottom_edge", "top_probability", "top_market_probability"]
    rankings = {}
    kept_frames = []
    for mode in modes:
        kept = rank_subset(df, cap, mode)
        kept = kept.copy()
        kept["ranking_mode"] = mode
        kept_frames.append(kept)
        rankings[mode] = summarize_bets(kept)

    random_result = random_cap_distribution(df, cap, iterations, rng)
    top_profit = rankings["top_edge"]["profit"]
    random_samples = random_result.pop("profit_samples")
    random_result["p_value_random_profit_at_least_top_edge"] = float(
        (np.sum(random_samples >= top_profit) + 1) / (len(random_samples) + 1)
    )
    random_result["top_edge_minus_random_mean_profit"] = float(
        top_profit - random_result["random_mean_profit"]
    )

    return {
        "probability_policy": policy_name,
        "source_bets": int(len(df)),
        "source_events": int(df["event_date"].nunique()),
        "cap": int(cap),
        "rankings": rankings,
        "random_cap": random_result,
    }, pd.concat(kept_frames, ignore_index=True)


def markdown_report(result: dict) -> str:
    frozen = next(
        (policy for policy in result["policies"] if policy["probability_policy"] == "frozen_residual_meta"),
        None,
    )
    lines = [
        "# Residual Event-Cap Ranking Audit",
        "",
        "This diagnostic checks whether the event-cap ranking rule itself matters.",
        "For each policy, it compares the frozen top-residual-edge cap against",
        "bottom-edge, probability-ranked, market-probability-ranked, and random",
        "same-event selections with the same cap.",
        "",
        "## Inputs",
        "",
        f"- frozen residual-meta fixed bets: `{result['fixed_meta_bets']}`",
        f"- shrinkage fixed-policy bets: `{result['shrinkage_bets']}`",
        f"- cap per event: `{result['cap']}`",
        f"- random iterations: `{result['iterations']}`",
        "",
        "## Ranking Results",
        "",
        "| Policy | Ranking | Bets | Events | Profit | ROI | Actual - Market | Positive Folds |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy in result["policies"]:
        for ranking, summary in policy["rankings"].items():
            lines.append(
                "| {policy} | {ranking} | {bets} | {events} | {profit} | {roi} | {actual_market} | {pos} / {folds} |".format(
                    policy=policy["probability_policy"],
                    ranking=ranking,
                    bets=summary["bets"],
                    events=summary["events"],
                    profit=fmt_units(summary["profit"]),
                    roi=fmt_pct(summary["roi"]),
                    actual_market=fmt_pct(summary["actual_minus_market"]),
                    pos=summary["positive_folds"],
                    folds=len(summary["folds"]),
                )
            )

    lines.extend(
        [
            "",
            "## Random Cap Comparison",
            "",
            "| Policy | Top Edge Profit | Random Mean | Random 95% Interval | P(random >= top edge) | Top - Random Mean |",
            "| --- | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for policy in result["policies"]:
        random_cap = policy["random_cap"]
        top_profit = policy["rankings"]["top_edge"]["profit"]
        ci = random_cap["random_profit_ci_95"]
        lines.append(
            "| {policy} | {top} | {mean} | {lo} to {hi} | {p} | {diff} |".format(
                policy=policy["probability_policy"],
                top=fmt_units(top_profit),
                mean=fmt_units(random_cap["random_mean_profit"]),
                lo=fmt_units(ci[0]),
                hi=fmt_units(ci[1]),
                p=fmt_p(random_cap["p_value_random_profit_at_least_top_edge"]),
                diff=fmt_units(random_cap["top_edge_minus_random_mean_profit"]),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The frozen cap rule is stronger if top residual-edge ranking beats random",
            "same-event caps and bottom-edge caps. If random caps perform similarly,",
            "then the main value is exposure reduction rather than residual ordering.",
            "",
        ]
    )
    if frozen:
        random_cap = frozen["random_cap"]
        lines.extend(
            [
                "For the frozen residual-meta ledger, top residual-edge ranking produced",
                f"`{fmt_units(frozen['rankings']['top_edge']['profit'])}` versus",
                f"`{fmt_units(frozen['rankings']['bottom_edge']['profit'])}` for bottom-edge ranking",
                f"and a random-cap mean of `{fmt_units(random_cap['random_mean_profit'])}`.",
                f"Only `{fmt_p(random_cap['p_value_random_profit_at_least_top_edge'])}` of random caps matched or beat the top-edge result.",
                "That supports the ranking rule as more than generic exposure reduction,",
                "though it remains historical evidence rather than post-freeze proof.",
                "",
            ]
        )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    policies = {"frozen_residual_meta": load_fixed_meta(args.fixed_meta_bets)}
    policies.update(load_shrinkage(args.shrinkage_bets))

    summaries = []
    kept_frames = []
    for policy_name, df in policies.items():
        summary, kept = audit_policy(policy_name, df, args.cap, args.iterations, rng)
        summaries.append(summary)
        kept["probability_policy"] = policy_name
        kept_frames.append(kept)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "fixed_meta_bets": args.fixed_meta_bets,
        "shrinkage_bets": args.shrinkage_bets,
        "cap": int(args.cap),
        "iterations": int(args.iterations),
        "seed": int(args.seed),
        "policies": summaries,
        "outputs": {
            "summary_json": str(output_dir / "residual_event_cap_ranking_audit.json"),
            "report_md": str(output_dir / "residual_event_cap_ranking_audit.md"),
            "ranked_bets_csv": str(output_dir / "ranked_cap_bets.csv"),
        },
    }

    json_path = output_dir / "residual_event_cap_ranking_audit.json"
    md_path = output_dir / "residual_event_cap_ranking_audit.md"
    bets_path = output_dir / "ranked_cap_bets.csv"
    serializable = json.loads(json.dumps(result))
    with json_path.open("w") as file:
        json.dump(serializable, file, indent=2)
    md_path.write_text(markdown_report(serializable))
    pd.concat(kept_frames, ignore_index=True).to_csv(bets_path, index=False)

    frozen = next(row for row in summaries if row["probability_policy"] == "frozen_residual_meta")
    print(
        "Frozen residual-meta top-edge profit "
        f"{fmt_units(frozen['rankings']['top_edge']['profit'])}; "
        "P(random >= top) "
        f"{fmt_p(frozen['random_cap']['p_value_random_profit_at_least_top_edge'])}"
    )
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
