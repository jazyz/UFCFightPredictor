#!/usr/bin/env python3
"""Ablate semantically muddy feature families from the UFC feature table.

The semantic-integrity audit found no hard arithmetic bug, but it flagged
percentage/defense proxy families whose fight meaning is muddy. This audit
tests whether removing those families improves leak-safe regularized-LGBM
performance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import add_market_columns, binary_log_loss, brier_score  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


ID_COLUMNS = {"Result", "Red Fighter", "Blue Fighter", "Title", "Date"}
WINDOWS = {
    "1y": ("2025-06-27", "2026-06-27"),
    "2y": ("2024-06-27", "2026-06-27"),
}
BASELINE_LEDGER_DIRS = {
    "1y": "test_results/regularized_lgbm_1y",
    "2y": "test_results/regularized_lgbm_2y",
}
TARGET_MIX_BASES = {"Head%", "Body%", "Leg%", "Distance%", "Clinch%", "Ground%"}


def parse_args():
    parser = argparse.ArgumentParser(description="Audit semantic feature ablations")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--params", default="test_results/regularized_lgbm_params.json")
    parser.add_argument("--output-dir", default="test_results/feature_semantic_ablation_audit")
    parser.add_argument("--force", action="store_true", help="rerun backtests even when outputs already exist")
    return parser.parse_args()


def base_feature_name(column: str) -> str:
    base = column
    for prefix in ("Red ", "Blue "):
        if base.startswith(prefix):
            base = base[len(prefix) :]
            break
    if base.endswith(" oppdiff"):
        base = base[: -len(" oppdiff")]
    return base


def is_target_mix_defense(column: str) -> bool:
    base = base_feature_name(column)
    if not base.endswith("% defense"):
        return False
    stem = base[: -len(" defense")]
    return stem in TARGET_MIX_BASES


def is_pct_scaled_side_proxy(column: str) -> bool:
    base = base_feature_name(column)
    return "%" in base and "defense" not in base and "differential" not in base


def is_raw_dob_proxy(column: str) -> bool:
    return base_feature_name(column) == "dob"


def is_all_percentage(column: str) -> bool:
    return "%" in base_feature_name(column)


def variant_specs() -> list[dict]:
    return [
        {
            "name": "drop_target_mix_defense",
            "description": "drop target/position-mix defense proxies such as Head% defense and Leg% defense",
            "predicate": is_target_mix_defense,
        },
        {
            "name": "drop_muddy_pct_and_dob",
            "description": "drop target-mix defense proxies, side percentage proxies scaled by elapsed fight time, and raw DOB proxies",
            "predicate": lambda column: is_target_mix_defense(column)
            or is_pct_scaled_side_proxy(column)
            or is_raw_dob_proxy(column),
        },
        {
            "name": "drop_all_percentage",
            "description": "drop all percentage-derived columns",
            "predicate": is_all_percentage,
        },
    ]


def write_variant_features(source_path: str, output_dir: Path) -> list[dict]:
    source = pd.read_csv(source_path)
    rows = []
    features_dir = output_dir / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    for spec in variant_specs():
        drop_columns = [
            column
            for column in source.columns
            if column not in ID_COLUMNS and spec["predicate"](column)
        ]
        variant = source.drop(columns=drop_columns)
        path = features_dir / f"{spec['name']}.csv"
        variant.to_csv(path, index=False)
        rows.append(
            {
                "name": spec["name"],
                "description": spec["description"],
                "features_path": str(path),
                "dropped_columns": drop_columns,
                "dropped_column_count": len(drop_columns),
                "remaining_columns": int(len(variant.columns)),
            }
        )
    return rows


def run_backtest(features_path: str, params_path: str, output_dir: Path, start_date: str, end_date: str, force: bool) -> None:
    summary_path = output_dir / "no_leakage_backtest_summary.json"
    csv_path = output_dir / "no_leakage_backtest.csv"
    if summary_path.exists() and csv_path.exists() and not force:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "testing/no_leakage_backtest.py",
        "--features",
        features_path,
        "--params",
        params_path,
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--output-dir",
        str(output_dir),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def red_won_from_ledger(row: pd.Series) -> bool:
    return canonical_name(row["winner_name"]) == canonical_name(row["red_fighter"])


def summarize_ledger(label: str, window: str, ledger_dir: str | Path) -> dict:
    ledger_dir = Path(ledger_dir)
    csv_path = ledger_dir / "no_leakage_backtest.csv"
    summary_path = ledger_dir / "no_leakage_backtest_summary.json"
    with summary_path.open() as file:
        summary = json.load(file)
    df = pd.read_csv(csv_path)
    df_market = add_market_columns(df)
    y = df_market.apply(red_won_from_ledger, axis=1).astype(float).to_numpy()
    model_prob = pd.to_numeric(df_market["red_win_probability"], errors="coerce").to_numpy(dtype=float)
    market_prob = pd.to_numeric(df_market["red_market_probability"], errors="coerce").to_numpy(dtype=float)
    market_mask = np.isfinite(y) & np.isfinite(model_prob) & np.isfinite(market_prob)
    model_market_ll = binary_log_loss(y[market_mask], model_prob[market_mask]) if market_mask.any() else None
    market_ll = binary_log_loss(y[market_mask], market_prob[market_mask]) if market_mask.any() else None
    return {
        "label": label,
        "window": window,
        "ledger_dir": str(ledger_dir),
        "fights": int(summary.get("predicted_fights") or len(df)),
        "bets": int((pd.to_numeric(df.get("bet", 0), errors="coerce").fillna(0) > 0).sum()),
        "accuracy": summary.get("accuracy"),
        "model_log_loss": summary.get("log_loss"),
        "market_aligned_fights": int(market_mask.sum()),
        "market_aligned_model_log_loss": model_market_ll,
        "market_log_loss": market_ll,
        "model_minus_market_log_loss": (
            None if model_market_ll is None or market_ll is None else model_market_ll - market_ll
        ),
        "brier": brier_score(y[np.isfinite(model_prob)], model_prob[np.isfinite(model_prob)]),
        "profit_pct": summary.get("profit_pct"),
        "final_bankroll": summary.get("final_bankroll"),
        "feature_columns_median": float(pd.to_numeric(df["feature_columns"], errors="coerce").median())
        if "feature_columns" in df.columns
        else None,
    }


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):.2%}"


def markdown_report(result: dict) -> str:
    rows = result["summaries"]
    lines = [
        "# Feature Semantic Ablation Audit",
        "",
        "This audit removes semantically muddy feature families identified by the",
        "feature semantic-integrity audit, then reruns the same regularized",
        "leak-safe LightGBM backtests. It tests whether those feature families",
        "look helpful, harmful, or merely noisy.",
        "",
        "## Variants",
        "",
        "| Variant | Dropped Columns | Remaining Columns | Description |",
        "| --- | ---: | ---: | --- |",
    ]
    for variant in result["variants"]:
        lines.append(
            "| {name} | {dropped} | {remaining} | {description} |".format(
                name=variant["name"],
                dropped=variant["dropped_column_count"],
                remaining=variant["remaining_columns"],
                description=variant["description"],
            )
        )

    for window in WINDOWS:
        lines.extend(
            [
                "",
                f"## {window} Leak-Safe Results",
                "",
                "| Variant | Fights | Feature Columns | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in [item for item in rows if item["window"] == window]:
            lines.append(
                "| {label} | {fights} | {features} | {acc} | {model_ll} | {market_ll} | {delta} | {profit} | {bets} |".format(
                    label=row["label"],
                    fights=row["fights"],
                    features=fmt_float(row["feature_columns_median"], digits=0),
                    acc=fmt_pct(row["accuracy"]),
                    model_ll=fmt_float(row["model_log_loss"]),
                    market_ll=fmt_float(row["market_log_loss"]),
                    delta=fmt_float(row["model_minus_market_log_loss"]),
                    profit=fmt_pct((row["profit_pct"] or 0.0) / 100.0),
                    bets=row["bets"],
                )
            )

    lines.extend(["", "## Interpretation", ""])
    for window in WINDOWS:
        window_rows = [row for row in rows if row["window"] == window]
        baseline = next(row for row in window_rows if row["label"] == "current_regularized")
        best_ll = min(window_rows, key=lambda row: row["model_log_loss"] if row["model_log_loss"] is not None else float("inf"))
        best_pnl = max(window_rows, key=lambda row: row["profit_pct"] if row["profit_pct"] is not None else -float("inf"))
        beat_market = [
            row
            for row in window_rows
            if row["model_minus_market_log_loss"] is not None
            and row["model_minus_market_log_loss"] < 0.0
        ]
        lines.append(
            "- {window}: best model log loss was `{best_ll}` ({best_ll_value}), while current regularized was {base_ll}; best PnL was `{best_pnl}` ({best_pnl_value}), while current regularized was {base_pnl}.".format(
                window=window,
                best_ll=best_ll["label"],
                best_ll_value=fmt_float(best_ll["model_log_loss"]),
                base_ll=fmt_float(baseline["model_log_loss"]),
                best_pnl=best_pnl["label"],
                best_pnl_value=fmt_pct((best_pnl["profit_pct"] or 0.0) / 100.0),
                base_pnl=fmt_pct((baseline["profit_pct"] or 0.0) / 100.0),
            )
        )
        if not beat_market:
            lines.append(
                f"- {window}: every ablation still trailed the de-vigged market on aligned log loss."
            )
    lines.append(
        "- These are ablations, not new feature promotions. The narrow target-mix-defense drop is a probability-cleanup candidate; the broader drop's 2y PnL gain needs nested validation because its log loss worsened."
    )
    lines.append("")
    return "\n".join(lines)


def audit(args) -> dict:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    variants = write_variant_features(args.features, output_dir)

    summaries = []
    for window, ledger_dir in BASELINE_LEDGER_DIRS.items():
        summaries.append(summarize_ledger("current_regularized", window, ledger_dir))

    for variant in variants:
        for window, (start_date, end_date) in WINDOWS.items():
            ledger_dir = output_dir / variant["name"] / window
            run_backtest(
                variant["features_path"],
                args.params,
                ledger_dir,
                start_date,
                end_date,
                args.force,
            )
            summaries.append(summarize_ledger(variant["name"], window, ledger_dir))

    return {
        "features": args.features,
        "params": args.params,
        "windows": {key: {"start_date": value[0], "end_date": value[1]} for key, value in WINDOWS.items()},
        "variants": variants,
        "summaries": summaries,
    }


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    json_path = output_dir / "feature_semantic_ablation_audit.json"
    md_path = output_dir / "feature_semantic_ablation_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
