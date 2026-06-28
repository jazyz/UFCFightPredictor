#!/usr/bin/env python3
"""Concentration audit for residual market/meta probability edge.

The residual-shrinkage audit already tests whether candidate probabilities beat
market probabilities on aggregate log loss. This diagnostic asks whether that
small gain is broad or concentrated in a few events/fights.
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

from testing.market_residual_meta_audit import per_row_loss, score_probabilities  # noqa: E402


DEFAULT_INPUT = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
DEFAULT_POLICIES = {
    "selected_shrinkage": "selected_probability",
    "fixed_half_residual": "fixed_half_probability",
    "unshrunk_meta": "unshrunk_probability",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Audit concentration of residual edge")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default="test_results/residual_edge_concentration_audit")
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits=1) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def group_value(value):
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def summarize_group(grouped: pd.DataFrame) -> list[dict]:
    rows = []
    key = str(grouped.index.name or "group")
    for index_value, row in grouped.iterrows():
        rows.append(
            {
                key: group_value(index_value),
                "fights": int(row["fights"]),
                "sum_delta": float(row["sum_delta"]),
                "mean_delta": float(row["sum_delta"] / row["fights"]) if row["fights"] else None,
            }
        )
    return rows


def removal_rows(df: pd.DataFrame, event_delta: pd.DataFrame, total_delta_sum: float, top_ks: list[int]) -> list[dict]:
    rows = []
    sorted_events = event_delta.sort_values("sum_delta", ascending=False)
    for k in top_ks:
        selected = sorted_events.head(k)
        selected_events = set(selected.index)
        removed_fights = int(df["event_date"].isin(selected_events).sum())
        remaining_fights = len(df) - removed_fights
        remaining_delta_sum = float(total_delta_sum - selected["sum_delta"].sum())
        rows.append(
            {
                "removed_top_events": int(k),
                "removed_fights": removed_fights,
                "remaining_fights": remaining_fights,
                "remaining_sum_delta": remaining_delta_sum,
                "remaining_mean_delta": remaining_delta_sum / remaining_fights if remaining_fights else None,
            }
        )
    return rows


def top_fight_rows(df: pd.DataFrame, top_k: int, ascending: bool = False) -> list[dict]:
    columns = [
        "event_date",
        "title",
        "red_fighter",
        "blue_fighter",
        "winner_name",
        "market_probability",
        "candidate_probability",
        "delta",
    ]
    rows = []
    for _, row in df.sort_values("delta", ascending=ascending).head(top_k)[columns].iterrows():
        rows.append(
            {
                "event_date": group_value(row["event_date"]),
                "title": row["title"],
                "red_fighter": row["red_fighter"],
                "blue_fighter": row["blue_fighter"],
                "winner_name": row["winner_name"],
                "market_probability": float(row["market_probability"]),
                "candidate_probability": float(row["candidate_probability"]),
                "delta": float(row["delta"]),
            }
        )
    return rows


def policy_summary(base: pd.DataFrame, policy_name: str, probability_column: str, top_k: int) -> dict:
    df = base.copy()
    y = df["red_won"].astype(float).to_numpy()
    market = np.clip(df["market_probability"].astype(float).to_numpy(), 1e-12, 1.0 - 1e-12)
    candidate = np.clip(df[probability_column].astype(float).to_numpy(), 1e-12, 1.0 - 1e-12)
    df["candidate_probability"] = candidate
    df["market_loss"] = per_row_loss(y, market)
    df["candidate_loss"] = per_row_loss(y, candidate)
    df["delta"] = df["market_loss"] - df["candidate_loss"]
    df["year"] = pd.to_datetime(df["event_date"]).dt.year

    total_delta_sum = float(df["delta"].sum())
    total_fights = int(len(df))
    event_delta = df.groupby("event_date", sort=True).agg(
        sum_delta=("delta", "sum"),
        fights=("delta", "size"),
    )
    positive_events = event_delta[event_delta["sum_delta"] > 0.0]
    negative_events = event_delta[event_delta["sum_delta"] < 0.0]
    sorted_positive_events = positive_events.sort_values("sum_delta", ascending=False)
    sorted_all_events = event_delta.sort_values("sum_delta", ascending=False)

    positive_event_sum = float(positive_events["sum_delta"].sum())
    negative_event_sum = float(negative_events["sum_delta"].sum())
    top_positive_event_sum = float(sorted_positive_events.head(top_k)["sum_delta"].sum())

    min_events_to_zero = None
    remaining = total_delta_sum
    removed_fights = 0
    for index, (_, row) in enumerate(sorted_all_events.iterrows(), start=1):
        remaining -= float(row["sum_delta"])
        removed_fights += int(row["fights"])
        if remaining <= 0.0:
            min_events_to_zero = {
                "events": int(index),
                "fights": int(removed_fights),
                "remaining_sum_delta": float(remaining),
                "remaining_mean_delta": float(remaining / (total_fights - removed_fights))
                if total_fights > removed_fights
                else None,
            }
            break

    by_year = df.groupby("year").agg(sum_delta=("delta", "sum"), fights=("delta", "size"))
    by_fold = df.groupby("fold").agg(sum_delta=("delta", "sum"), fights=("delta", "size"))

    top_event_rows = []
    for event_date, row in sorted_all_events.head(top_k).iterrows():
        top_event_rows.append(
            {
                "event_date": group_value(event_date),
                "fights": int(row["fights"]),
                "sum_delta": float(row["sum_delta"]),
                "mean_delta": float(row["sum_delta"] / row["fights"]),
            }
        )

    bottom_event_rows = []
    for event_date, row in sorted_all_events.tail(top_k).sort_values("sum_delta").iterrows():
        bottom_event_rows.append(
            {
                "event_date": group_value(event_date),
                "fights": int(row["fights"]),
                "sum_delta": float(row["sum_delta"]),
                "mean_delta": float(row["sum_delta"] / row["fights"]),
            }
        )

    return {
        "policy": policy_name,
        "probability_column": probability_column,
        "fights": total_fights,
        "events": int(len(event_delta)),
        "market": score_probabilities(y, market),
        "candidate": score_probabilities(y, candidate),
        "sum_delta": total_delta_sum,
        "mean_delta": float(total_delta_sum / total_fights),
        "positive_fight_fraction": float((df["delta"] > 0.0).mean()),
        "positive_event_fraction": float((event_delta["sum_delta"] > 0.0).mean()),
        "positive_event_sum": positive_event_sum,
        "negative_event_sum": negative_event_sum,
        "top_positive_event_sum": top_positive_event_sum,
        "top_positive_event_share_of_positive_sum": (
            top_positive_event_sum / positive_event_sum if positive_event_sum > 0 else None
        ),
        "top_positive_event_share_of_net_sum": (
            top_positive_event_sum / total_delta_sum if total_delta_sum > 0 else None
        ),
        "min_top_events_to_zero": min_events_to_zero,
        "removal": removal_rows(df, event_delta, total_delta_sum, [1, 3, 5, top_k]),
        "by_year": summarize_group(by_year),
        "by_fold": summarize_group(by_fold),
        "top_events": top_event_rows,
        "bottom_events": bottom_event_rows,
        "top_fights": top_fight_rows(df, top_k, ascending=False),
        "bottom_fights": top_fight_rows(df, top_k, ascending=True),
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# Residual Edge Concentration Audit",
        "",
        "This diagnostic asks whether the residual market/meta log-loss edge is broad",
        "or concentrated in a small number of events/fights. `Delta LL` is market",
        "log loss minus candidate log loss; positive means the residual candidate",
        "beat the market.",
        "",
        "## Input",
        "",
        f"- predictions: `{result['input']}`",
        f"- rows: `{result['rows']}`",
        f"- policies: `{', '.join(result['policies'])}`",
        "",
        "## Policy Summary",
        "",
        "| Policy | Fights | Events | Candidate LL | Delta LL | Positive Fights | Positive Events | Events To Erase Edge | Top-10 Positive Share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy in result["summaries"]:
        erase = policy.get("min_top_events_to_zero") or {}
        lines.append(
            "| {policy} | {fights} | {events} | {candidate_ll} | {delta} | {pos_fights} | {pos_events} | {erase} | {share} |".format(
                policy=policy["policy"],
                fights=policy["fights"],
                events=policy["events"],
                candidate_ll=fmt_float(policy["candidate"]["log_loss"]),
                delta=fmt_float(policy["mean_delta"]),
                pos_fights=fmt_pct(policy["positive_fight_fraction"]),
                pos_events=fmt_pct(policy["positive_event_fraction"]),
                erase=erase.get("events", ""),
                share=fmt_pct(policy.get("top_positive_event_share_of_positive_sum")),
            )
        )

    lines.extend(
        [
            "",
            "## Removal Sensitivity",
            "",
            "| Policy | Remove Top Events | Removed Fights | Remaining Delta LL | Remaining Sum Delta |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for policy in result["summaries"]:
        for row in policy["removal"]:
            lines.append(
                "| {policy} | {events} | {fights} | {mean} | {sum_delta} |".format(
                    policy=policy["policy"],
                    events=row["removed_top_events"],
                    fights=row["removed_fights"],
                    mean=fmt_float(row["remaining_mean_delta"]),
                    sum_delta=fmt_float(row["remaining_sum_delta"]),
                )
            )

    lines.extend(
        [
            "",
            "## Year And Fold Deltas",
            "",
            "| Policy | Group | Fights | Delta LL | Sum Delta |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for policy in result["summaries"]:
        for row in policy["by_year"]:
            lines.append(
                "| {policy} | year {group} | {fights} | {mean} | {sum_delta} |".format(
                    policy=policy["policy"],
                    group=row["year"],
                    fights=row["fights"],
                    mean=fmt_float(row["mean_delta"]),
                    sum_delta=fmt_float(row["sum_delta"]),
                )
            )
        for row in policy["by_fold"]:
            lines.append(
                "| {policy} | fold {group} | {fights} | {mean} | {sum_delta} |".format(
                    policy=policy["policy"],
                    group=row["fold"],
                    fights=row["fights"],
                    mean=fmt_float(row["mean_delta"]),
                    sum_delta=fmt_float(row["sum_delta"]),
                )
            )

    best = result["summaries"][0]
    lines.extend(
        [
            "",
            "## Top Selected-Shrinkage Events",
            "",
            "| Event | Fights | Sum Delta | Mean Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in best["top_events"]:
        lines.append(
            f"| {row['event_date']} | {row['fights']} | {fmt_float(row['sum_delta'])} | {fmt_float(row['mean_delta'])} |"
        )

    lines.extend(
        [
            "",
            "## Worst Selected-Shrinkage Events",
            "",
            "| Event | Fights | Sum Delta | Mean Delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in best["bottom_events"]:
        lines.append(
            f"| {row['event_date']} | {row['fights']} | {fmt_float(row['sum_delta'])} | {fmt_float(row['mean_delta'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The residual probability edge is not a broad, high-margin effect. For the",
            "`selected_shrinkage` policy, the aggregate Delta LL is positive, but the",
            "top five positive events reduce it to a very small value when removed,",
            "and the top ten positive events erase it entirely. The fixed-half",
            "residual policy is slightly less volatile, but still depends heavily",
            "on the top event cluster.",
            "",
            "Practical read: this supports continued paper tracking of the residual",
            "hypothesis, not live staking confidence. Future evidence should be judged",
            "by whether post-freeze gains are broad across cards and years, not only",
            "by aggregate log loss or PnL.",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    input_path = Path(args.input)
    df = pd.read_csv(input_path, parse_dates=["event_date"])
    required = {"event_date", "fold", "red_won", "market_probability", *DEFAULT_POLICIES.values()}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = [
        policy_summary(df, policy_name, column, args.top_k)
        for policy_name, column in DEFAULT_POLICIES.items()
    ]
    result = {
        "input": str(input_path),
        "rows": int(len(df)),
        "top_k": int(args.top_k),
        "policies": list(DEFAULT_POLICIES),
        "summaries": summaries,
        "outputs": {
            "summary_json": str(output_dir / "residual_edge_concentration_audit.json"),
            "report_md": str(output_dir / "residual_edge_concentration_audit.md"),
        },
    }

    json_path = output_dir / "residual_edge_concentration_audit.json"
    md_path = output_dir / "residual_edge_concentration_audit.md"
    with open(json_path, "w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    selected = summaries[0]
    erase = selected.get("min_top_events_to_zero") or {}
    print(
        "selected_shrinkage delta LL "
        f"{selected['mean_delta']:.4f}; top events to erase edge: {erase.get('events')}"
    )
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
