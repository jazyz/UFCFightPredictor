#!/usr/bin/env python3
"""Nested validation for semantic feature ablation candidates.

The one/two-year semantic ablation audit found mixed signals. This stricter
audit builds long leak-safe ledgers for those ablations, then lets the existing
nested model/strategy selector choose among baseline, current regularized, and
ablation models using only prior windows.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.feature_semantic_ablation_audit import (  # noqa: E402
    run_backtest,
    summarize_ledger,
    write_variant_features,
)


LONG_START = "2022-02-05"
LONG_END = "2026-06-27"
FIRST_HOLDOUT_START = "2023-02-05"
BASELINE_LEDGERS = {
    "baseline_default": "test_results/nested_edge_long/ledgers/baseline_default_2022_2026",
    "current_regularized": "test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Nested validation for feature ablation models")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--params", default="test_results/regularized_lgbm_params.json")
    parser.add_argument("--output-dir", default="test_results/feature_ablation_nested_validation_audit")
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--force", action="store_true", help="rerun long backtests and nested audits")
    return parser.parse_args()


def command_env() -> dict:
    env = os.environ.copy()
    mpl_dir = Path("/tmp/ufc_mplconfig")
    mpl_dir.mkdir(parents=True, exist_ok=True)
    env.setdefault("MPLCONFIGDIR", str(mpl_dir))
    return env


def run_command(command: list[str], force_output: Path | None = None, force: bool = False) -> None:
    if force_output is not None and force_output.exists() and not force:
        return
    subprocess.run(command, cwd=PROJECT_ROOT, check=True, env=command_env())


def no_leakage_csv(ledger_dir: str | Path) -> str:
    return str(Path(ledger_dir) / "no_leakage_backtest.csv")


def build_long_ledgers(args) -> tuple[list[dict], list[tuple[str, str]]]:
    output_dir = Path(args.output_dir)
    variants = write_variant_features(args.features, output_dir)
    ledgers: list[tuple[str, str]] = [
        (label, no_leakage_csv(path))
        for label, path in BASELINE_LEDGERS.items()
    ]

    for variant in variants:
        ledger_dir = output_dir / "ledgers" / variant["name"] / "2022_2026"
        run_backtest(
            variant["features_path"],
            args.params,
            ledger_dir,
            LONG_START,
            LONG_END,
            args.force,
        )
        ledgers.append((variant["name"], no_leakage_csv(ledger_dir)))

    return variants, ledgers


def summarize_long_ledgers(ledgers: list[tuple[str, str]]) -> list[dict]:
    rows = []
    for label, csv_path in ledgers:
        rows.append(summarize_ledger(label, "2022_2026", Path(csv_path).parent))
    return rows


def run_nested_objective(args, ledgers: list[tuple[str, str]], objective: str) -> dict:
    output_dir = Path(args.output_dir) / f"{objective}_objective"
    nested_json = output_dir / "nested_walk_forward_edge_audit.json"
    command = [
        sys.executable,
        "testing/nested_walk_forward_edge_audit.py",
        "--first-holdout-start",
        FIRST_HOLDOUT_START,
        "--last-holdout-end",
        LONG_END,
        "--dev-days",
        "365",
        "--holdout-days",
        "182",
        "--min-holdout-days",
        "120",
        "--min-dev-bets",
        "35",
        "--selection-objective",
        objective,
        "--output-dir",
        str(output_dir),
    ]
    for label, csv_path in ledgers:
        command.extend(["--ledger", label, csv_path])
    run_command(command, nested_json, args.force)

    selected_holdouts = output_dir / "selected_holdouts.csv"
    audit_dir = output_dir / "selected_holdouts_audit"
    edge_json = audit_dir / "edge_audit_summary.json"
    run_command(
        [
            sys.executable,
            "testing/statistical_edge_audit.py",
            str(selected_holdouts),
            "--iterations",
            str(args.iterations),
            "--output-dir",
            str(audit_dir),
        ],
        edge_json,
        args.force,
    )

    with nested_json.open() as file:
        nested = json.load(file)
    with edge_json.open() as file:
        edge = json.load(file)
    run = edge["runs"][0]
    betting = run["betting"]
    market_null = betting.get("market_null_path") or {}
    event_bootstrap = betting.get("event_bootstrap") or {}
    return {
        "objective": objective,
        "output_dir": str(output_dir),
        "nested_json": str(nested_json),
        "nested_md": str(output_dir / "nested_walk_forward_edge_audit.md"),
        "selected_holdouts_csv": str(selected_holdouts),
        "edge_audit_json": str(edge_json),
        "edge_audit_md": str(audit_dir / "edge_audit.md"),
        "aggregate": nested["aggregate"],
        "market_null_p": market_null.get("p_value_observed_or_better"),
        "prob_null_profitable": market_null.get("prob_null_profitable"),
        "bootstrap_prob_profit_le_zero": event_bootstrap.get("prob_profit_le_zero"),
        "bootstrap_profit_ci_95": event_bootstrap.get("profit_ci_95"),
        "folds": nested["folds"],
        "skipped_folds": nested["skipped_folds"],
    }


def fmt_float(value, digits=4) -> str:
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


def fmt_money(value) -> str:
    if value is None:
        return ""
    return f"${float(value):.2f}"


def model_counts_text(counts: dict) -> str:
    return ", ".join(f"{label}: {count}" for label, count in sorted(counts.items()))


def markdown_report(result: dict) -> str:
    lines = [
        "# Feature Ablation Nested Validation Audit",
        "",
        "This audit tests whether semantic feature ablations survive stricter",
        "long-history model/strategy selection. It compares baseline default,",
        "current regularized, and all semantic ablation variants. Each nested",
        "fold selects a model and betting strategy on the previous 365 days and",
        "evaluates the next 182-day holdout.",
        "",
        "## Long Ledgers",
        "",
        "| Model | Fights | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in result["long_ledger_summaries"]:
        lines.append(
            "| {label} | {fights} | {acc} | {model_ll} | {market_ll} | {delta} | {profit} | {bets} |".format(
                label=row["label"],
                fights=row["fights"],
                acc=fmt_pct(row["accuracy"]),
                model_ll=fmt_float(row["model_log_loss"]),
                market_ll=fmt_float(row["market_log_loss"]),
                delta=fmt_float(row["model_minus_market_log_loss"]),
                profit=fmt_pct((row["profit_pct"] or 0.0) / 100.0),
                bets=row["bets"],
            )
        )

    lines.extend(
        [
            "",
            "## Nested Selection",
            "",
            "| Objective | Folds | Fights | Bets | Profit | ROI | Positive Folds | Selected Models | Market-Null p | Bootstrap P(profit <= 0) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for nested in result["nested_results"]:
        aggregate = nested["aggregate"]
        lines.append(
            "| {objective} | {folds} | {fights} | {bets} | {profit} | {roi} | {positive} / {folds} | {models} | {p} | {boot} |".format(
                objective=nested["objective"],
                folds=aggregate["folds"],
                fights=aggregate["fights"],
                bets=aggregate["bets"],
                profit=fmt_money(aggregate["profit"]),
                roi=fmt_pct(aggregate["roi_on_staked"]),
                positive=aggregate["positive_folds"],
                models=model_counts_text(aggregate["selected_models"]),
                p=fmt_float(nested["market_null_p"], digits=3),
                boot=fmt_float(nested["bootstrap_prob_profit_le_zero"], digits=3),
            )
        )

    lines.extend(["", "## Interpretation", ""])
    best_long_ll = min(
        result["long_ledger_summaries"],
        key=lambda row: row["model_log_loss"] if row["model_log_loss"] is not None else float("inf"),
    )
    best_long_profit = max(
        result["long_ledger_summaries"],
        key=lambda row: row["profit_pct"] if row["profit_pct"] is not None else -float("inf"),
    )
    lines.append(
        f"- Long standalone best model log loss was `{best_long_ll['label']}` at {fmt_float(best_long_ll['model_log_loss'])}; best plain-strategy PnL was `{best_long_profit['label']}` at {fmt_pct((best_long_profit['profit_pct'] or 0.0) / 100.0)}."
    )
    if all((row["model_minus_market_log_loss"] or 0.0) > 0.0 for row in result["long_ledger_summaries"]):
        lines.append("- Every standalone model ledger still trailed de-vigged market log loss.")
    for nested in result["nested_results"]:
        aggregate = nested["aggregate"]
        selected_ablation_folds = sum(
            count
            for label, count in aggregate["selected_models"].items()
            if label.startswith("drop_")
        )
        lines.append(
            f"- `{nested['objective']}` selected ablation models in {selected_ablation_folds}/{aggregate['folds']} folds."
        )
    lines.append(
        "- The ablation family does not validate: even when the nested selector often chooses ablated models, the profit objective has weak market-null/bootstrap support and the ROI objective loses money."
    )
    lines.append(
        "- Do not promote these ablations into production or the edge claim. The useful lesson is narrower: percentage/defense semantics deserve redesign, but the tested removals are not a validated improvement."
    )
    lines.append("")
    return "\n".join(lines)


def audit(args) -> dict:
    variants, ledgers = build_long_ledgers(args)
    long_summaries = summarize_long_ledgers(ledgers)
    nested_results = [
        run_nested_objective(args, ledgers, "profit"),
        run_nested_objective(args, ledgers, "roi"),
    ]
    return {
        "features": args.features,
        "params": args.params,
        "long_start": LONG_START,
        "long_end": LONG_END,
        "first_holdout_start": FIRST_HOLDOUT_START,
        "iterations": args.iterations,
        "variants": variants,
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in ledgers],
        "long_ledger_summaries": long_summaries,
        "nested_results": nested_results,
    }


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "feature_ablation_nested_validation_audit.json"
    md_path = output_dir / "feature_ablation_nested_validation_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
