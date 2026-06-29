#!/usr/bin/env python3
"""Rolling selection audit for residual-meta configuration choices.

The residual-meta audit showed that shorter development windows can improve the
market-vs-meta log-loss delta. This script asks whether that kind of
configuration could be selected using only earlier holdout folds, instead of
after inspecting the full historical holdout.
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

from testing.market_residual_meta_audit import (  # noqa: E402
    EPS,
    binary_log_loss,
    build_variants,
    event_bootstrap_delta,
    fit_predict,
    iter_folds,
    load_aligned_ledgers,
    per_row_loss,
    run_observed_predictions,
)


DEFAULT_LEDGERS = [
    (
        "baseline_default",
        "test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv",
    ),
    (
        "regularized_lgbm",
        "test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv",
    ),
]
DEFAULT_CONFIGS = ("dev365_c1.0:365:1.0", "dev730_c1.0:730:1.0", "dev730_c0.25:730:0.25")


@dataclass(frozen=True)
class MetaConfig:
    label: str
    dev_days: int
    c_value: float


def parse_args():
    parser = argparse.ArgumentParser(description="Rolling residual-meta config selection audit")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        default=None,
        help="saved no_leakage_backtest.csv ledger to align by fight",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=None,
        help="candidate config as label:dev_days:c, e.g. dev365_c1.0:365:1.0",
    )
    parser.add_argument("--first-holdout-start", default="2024-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=200)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument(
        "--min-prior-selection-fights",
        type=int,
        default=100,
        help="minimum prior holdout predictions required before a candidate can be selected",
    )
    parser.add_argument("--market-null-iterations", type=int, default=1000)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_meta_config_selection_audit")
    return parser.parse_args()


def parse_config(text: str) -> MetaConfig:
    parts = str(text).split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"config must have form label:dev_days:c, got {text!r}"
        )
    label, dev_days, c_value = parts
    if not label.strip():
        raise argparse.ArgumentTypeError(f"config label cannot be blank: {text!r}")
    return MetaConfig(label.strip(), int(dev_days), float(c_value))


def candidate_name(config_label: str, variant: str) -> str:
    return f"{config_label}|{variant}"


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def build_predictions_for_configs(
    df: pd.DataFrame,
    configs: list[MetaConfig],
    first_holdout_start: str,
    last_holdout_end: str,
    holdout_days: int,
    step_days: int,
    min_dev_fights: int,
    min_holdout_fights: int,
) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    labels = [
        column.removesuffix("_logit_delta")
        for column in df.columns
        if column.endswith("_logit_delta")
    ]
    variants = build_variants(labels)
    frames = []
    fold_specs = {}
    for config in configs:
        folds = iter_folds(
            df,
            first_holdout_start,
            last_holdout_end,
            config.dev_days,
            holdout_days,
            step_days,
            min_dev_fights,
            min_holdout_fights,
        )
        if not folds:
            raise SystemExit(f"No folds met constraints for config {config.label}")
        predictions, _ = run_observed_predictions(df, variants, folds, config.c_value)
        predictions = predictions.copy()
        predictions["config"] = config.label
        predictions["config_dev_days"] = config.dev_days
        predictions["config_c"] = config.c_value
        predictions["candidate"] = [
            candidate_name(config.label, variant) for variant in predictions["variant"]
        ]
        frames.append(predictions)
        fold_specs[config.label] = [
            {
                "fold": fold.fold_index,
                "dev_start": fold.dev_start.date().isoformat(),
                "dev_end": fold.dev_end.date().isoformat(),
                "holdout_start": fold.holdout_start.date().isoformat(),
                "holdout_end": fold.holdout_end.date().isoformat(),
                "dev_fights": int(len(fold.dev_indices)),
                "holdout_fights": int(len(fold.holdout_indices)),
            }
            for fold in folds
        ]
    return pd.concat(frames, ignore_index=True), fold_specs


def add_loss_columns(predictions: pd.DataFrame) -> pd.DataFrame:
    output = predictions.copy()
    y = output["red_won"].astype(float).to_numpy()
    market = output["market_probability"].astype(float).to_numpy()
    meta = output["meta_probability"].astype(float).to_numpy()
    output["market_loss"] = per_row_loss(y, market)
    output["meta_loss"] = per_row_loss(y, meta)
    output["loss_delta"] = output["market_loss"] - output["meta_loss"]
    return output


def candidate_fold_stats(predictions: pd.DataFrame) -> dict[tuple[str, int], dict]:
    stats = {}
    for (candidate, fold), subset in predictions.groupby(["candidate", "fold"], sort=True):
        market_loss = float(subset["market_loss"].sum())
        meta_loss = float(subset["meta_loss"].sum())
        rows = int(len(subset))
        stats[(str(candidate), int(fold))] = {
            "market_loss": market_loss,
            "meta_loss": meta_loss,
            "loss_delta": market_loss - meta_loss,
            "rows": rows,
        }
    return stats


def select_candidate(
    stats: dict[tuple[str, int], dict],
    candidates: list[str],
    prior_folds: list[int],
    min_prior_selection_fights: int,
) -> tuple[str | None, dict | None]:
    best_candidate = None
    best_score = None
    best_summary = None
    for candidate in candidates:
        market_loss = 0.0
        meta_loss = 0.0
        rows = 0
        for fold in prior_folds:
            row = stats.get((candidate, fold))
            if row is None:
                continue
            market_loss += row["market_loss"]
            meta_loss += row["meta_loss"]
            rows += row["rows"]
        if rows < min_prior_selection_fights:
            continue
        delta = (market_loss - meta_loss) / rows
        score = (delta, market_loss - meta_loss, rows, candidate)
        if best_score is None or score > best_score:
            best_score = score
            best_candidate = candidate
            best_summary = {
                "prior_rows": int(rows),
                "prior_market_log_loss": float(market_loss / rows),
                "prior_meta_log_loss": float(meta_loss / rows),
                "prior_delta_log_loss": float(delta),
            }
    return best_candidate, best_summary


def summarize_rows(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {
            "fights": 0,
            "events": 0,
            "market_log_loss": None,
            "meta_log_loss": None,
            "market_minus_meta_log_loss": None,
        }
    y = rows["red_won"].astype(float).to_numpy()
    market = rows["market_probability"].astype(float).to_numpy()
    meta = rows["meta_probability"].astype(float).to_numpy()
    market_ll = binary_log_loss(y, market)
    meta_ll = binary_log_loss(y, meta)
    return {
        "fights": int(len(rows)),
        "events": int(rows["event_date"].nunique()),
        "market_log_loss": float(market_ll),
        "meta_log_loss": float(meta_ll),
        "market_minus_meta_log_loss": float(market_ll - meta_ll),
    }


def rolling_selection(
    predictions: pd.DataFrame,
    min_prior_selection_fights: int,
) -> tuple[list[dict], pd.DataFrame, dict]:
    stats = candidate_fold_stats(predictions)
    candidates = sorted(predictions["candidate"].unique())
    folds = sorted(int(value) for value in predictions["fold"].unique())
    selections = []
    selected_frames = []
    for eval_fold in folds[1:]:
        candidate, prior_summary = select_candidate(
            stats,
            candidates,
            [fold for fold in folds if fold < eval_fold],
            min_prior_selection_fights,
        )
        if candidate is None:
            continue
        eval_subset = predictions[
            predictions["candidate"].eq(candidate)
            & predictions["fold"].astype(int).eq(eval_fold)
        ].copy()
        eval_summary = summarize_rows(eval_subset)
        config_label, variant = candidate.split("|", 1)
        selections.append(
            {
                "eval_fold": int(eval_fold),
                "selected_candidate": candidate,
                "selected_config": config_label,
                "selected_variant": variant,
                **(prior_summary or {}),
                "eval_fights": eval_summary["fights"],
                "eval_events": eval_summary["events"],
                "eval_market_log_loss": eval_summary["market_log_loss"],
                "eval_meta_log_loss": eval_summary["meta_log_loss"],
                "eval_delta_log_loss": eval_summary["market_minus_meta_log_loss"],
            }
        )
        if not eval_subset.empty:
            eval_subset["rolling_eval_fold"] = int(eval_fold)
            selected_frames.append(eval_subset)

    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    summary = summarize_rows(selected)
    summary.update(
        {
            "eval_folds": int(len(selections)),
            "positive_eval_folds": int(
                sum((row.get("eval_delta_log_loss") or 0.0) > 0.0 for row in selections)
            ),
            "selections": selections,
        }
    )
    return selections, selected, summary


def candidate_summaries(predictions: pd.DataFrame) -> list[dict]:
    rows = []
    for candidate, subset in predictions.groupby("candidate", sort=True):
        config_label, variant = candidate.split("|", 1)
        summary = summarize_rows(subset)
        fold_deltas = []
        for _, fold_subset in subset.groupby("fold", sort=True):
            fold_deltas.append(summarize_rows(fold_subset)["market_minus_meta_log_loss"])
        rows.append(
            {
                "candidate": candidate,
                "config": config_label,
                "variant": variant,
                **summary,
                "positive_folds": int(sum((value or 0.0) > 0.0 for value in fold_deltas)),
                "folds": int(len(fold_deltas)),
                "fold_log_loss_deltas": [float(value) for value in fold_deltas],
            }
        )
    return rows


def market_null_selection(
    df: pd.DataFrame,
    configs: list[MetaConfig],
    min_prior_selection_fights: int,
    first_holdout_start: str,
    last_holdout_end: str,
    holdout_days: int,
    step_days: int,
    min_dev_fights: int,
    min_holdout_fights: int,
    observed_delta: float,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    labels = [
        column.removesuffix("_logit_delta")
        for column in df.columns
        if column.endswith("_logit_delta")
    ]
    variants = build_variants(labels)
    y_market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    feature_matrices = {
        variant.name: df[list(variant.feature_columns)].astype(float).to_numpy()
        for variant in variants
    }
    folds_by_config = {
        config.label: iter_folds(
            df,
            first_holdout_start,
            last_holdout_end,
            config.dev_days,
            holdout_days,
            step_days,
            min_dev_fights,
            min_holdout_fights,
        )
        for config in configs
    }
    candidates = sorted(
        candidate_name(config.label, variant.name)
        for config in configs
        for variant in variants
    )
    fold_ids = sorted(
        {
            fold.fold_index
            for folds in folds_by_config.values()
            for fold in folds
        }
    )
    simulated_deltas = np.empty(iterations, dtype=float)
    selected_counts: dict[str, int] = {}

    for iteration in range(iterations):
        simulated_y = (rng.random(len(df)) < y_market).astype(int)
        stats = {}
        for config in configs:
            for fold in folds_by_config[config.label]:
                for variant in variants:
                    x = feature_matrices[variant.name]
                    probabilities, _ = fit_predict(
                        x[fold.dev_indices],
                        simulated_y[fold.dev_indices],
                        x[fold.holdout_indices],
                        config.c_value,
                    )
                    y_holdout = simulated_y[fold.holdout_indices]
                    market_holdout = y_market[fold.holdout_indices]
                    market_loss = float(per_row_loss(y_holdout, market_holdout).sum())
                    meta_loss = float(per_row_loss(y_holdout, probabilities).sum())
                    stats[(candidate_name(config.label, variant.name), fold.fold_index)] = {
                        "market_loss": market_loss,
                        "meta_loss": meta_loss,
                        "loss_delta": market_loss - meta_loss,
                        "rows": int(len(fold.holdout_indices)),
                    }

        total_market_loss = 0.0
        total_meta_loss = 0.0
        total_rows = 0
        for eval_fold in fold_ids[1:]:
            candidate, _ = select_candidate(
                stats,
                candidates,
                [fold for fold in fold_ids if fold < eval_fold],
                min_prior_selection_fights,
            )
            if candidate is None:
                continue
            row = stats.get((candidate, eval_fold))
            if row is None:
                continue
            selected_counts[candidate] = selected_counts.get(candidate, 0) + 1
            total_market_loss += row["market_loss"]
            total_meta_loss += row["meta_loss"]
            total_rows += row["rows"]

        simulated_deltas[iteration] = (
            (total_market_loss - total_meta_loss) / total_rows if total_rows else 0.0
        )

    return {
        "iterations": int(iterations),
        "observed_market_minus_meta_log_loss": float(observed_delta),
        "null_mean_delta": float(np.mean(simulated_deltas)),
        "null_delta_ci_95": [float(value) for value in np.percentile(simulated_deltas, [2.5, 97.5])],
        "p_value_observed_or_better": float(
            (np.sum(simulated_deltas >= observed_delta) + 1) / (iterations + 1)
        ),
        "prob_null_delta_positive": float(np.mean(simulated_deltas > 0.0)),
        "selected_candidate_frequency": selected_counts,
    }


def markdown_report(result: dict) -> str:
    rolling = result["rolling_selection"]
    bootstrap = rolling.get("event_bootstrap") or {}
    market_null = rolling.get("market_null") or {}
    lines = [
        "# Residual Meta Config Selection Audit",
        "",
        "This audit tests whether the residual-meta development window and",
        "regularization choices can be selected without looking at future folds.",
        "Each evaluation fold after fold 1 chooses the candidate with the best",
        "prior holdout log-loss delta, then scores that candidate on the next fold.",
        "",
        "## Inputs",
        "",
        "| Label | Ledger |",
        "| --- | --- |",
    ]
    for item in result["ledgers"]:
        lines.append(f"| {item['label']} | `{item['csv_path']}` |")
    lines.extend(
        [
            "",
            "## Candidate Configs",
            "",
            "| Config | Development Days | Logistic C |",
            "| --- | ---: | ---: |",
        ]
    )
    for config in result["configs"]:
        lines.append(f"| {config['label']} | {config['dev_days']} | {config['c']} |")

    lines.extend(
        [
            "",
            "## Full-Holdout Candidate Results",
            "",
            "| Candidate | Fights | Market LL | Meta LL | Delta LL | Positive Folds |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["candidate_summaries"]:
        lines.append(
            "| {candidate} | {fights} | {market_ll} | {meta_ll} | {delta} | {pos} / {folds} |".format(
                candidate=row["candidate"],
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                meta_ll=fmt_float(row["meta_log_loss"]),
                delta=fmt_float(row["market_minus_meta_log_loss"]),
                pos=row["positive_folds"],
                folds=row["folds"],
            )
        )

    lines.extend(
        [
            "",
            "## Rolling Selection Result",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| eval folds | {rolling['eval_folds']} |",
            f"| fights | {rolling['fights']} |",
            f"| events | {rolling['events']} |",
            f"| market log loss | {fmt_float(rolling['market_log_loss'])} |",
            f"| selected meta log loss | {fmt_float(rolling['meta_log_loss'])} |",
            f"| market - selected meta log loss | {fmt_float(rolling['market_minus_meta_log_loss'])} |",
            f"| positive eval folds | {rolling['positive_eval_folds']} / {rolling['eval_folds']} |",
            f"| event-bootstrap P(delta <= 0) | {fmt_p(bootstrap.get('prob_delta_le_zero'))} |",
            f"| rolling market-null p | {fmt_p(market_null.get('p_value_observed_or_better'))} |",
            "",
            "## Fold Selections",
            "",
            "| Eval Fold | Selected Candidate | Prior Delta LL | Eval Fights | Eval Delta LL |",
            "| ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for row in rolling["selections"]:
        lines.append(
            "| {fold} | {candidate} | {prior_delta} | {fights} | {eval_delta} |".format(
                fold=row["eval_fold"],
                candidate=row["selected_candidate"],
                prior_delta=fmt_float(row["prior_delta_log_loss"]),
                fights=row["eval_fights"],
                eval_delta=fmt_float(row["eval_delta_log_loss"]),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a configuration-selection audit, not a new betting-policy search.",
            "A positive result means the residual-meta setup choice had a plausible",
            "prior-fold selection path. It still remains historical evidence and",
            "should not replace post-freeze paper tracking.",
        ]
    )
    if rolling.get("market_minus_meta_log_loss") is not None:
        lines.extend(
            [
                "",
                "The rolling-selected result is positive but weak: the selected meta",
                f"probability improved log loss by only `{fmt_float(rolling['market_minus_meta_log_loss'])}`,",
                f"with event-bootstrap `P(delta <= 0) = {fmt_p(bootstrap.get('prob_delta_le_zero'))}`",
                f"and rolling market-null p `{fmt_p(market_null.get('p_value_observed_or_better'))}`.",
                "The latest evaluation fold was negative, so this audit does not justify",
                "promoting an adaptively selected residual-meta configuration.",
            ]
        )
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    ledger_args = args.ledger if args.ledger is not None else DEFAULT_LEDGERS
    configs = [parse_config(text) for text in (args.config or DEFAULT_CONFIGS)]

    df, labels = load_aligned_ledgers(ledger_args)
    predictions, fold_specs = build_predictions_for_configs(
        df,
        configs,
        args.first_holdout_start,
        args.last_holdout_end,
        args.holdout_days,
        args.step_days,
        args.min_dev_fights,
        args.min_holdout_fights,
    )
    predictions = add_loss_columns(predictions)
    _, selected, rolling_summary = rolling_selection(predictions, args.min_prior_selection_fights)
    rolling_summary["event_bootstrap"] = event_bootstrap_delta(
        selected,
        args.bootstrap_iterations,
        rng,
    )
    rolling_summary["market_null"] = market_null_selection(
        df,
        configs,
        args.min_prior_selection_fights,
        args.first_holdout_start,
        args.last_holdout_end,
        args.holdout_days,
        args.step_days,
        args.min_dev_fights,
        args.min_holdout_fights,
        rolling_summary["market_minus_meta_log_loss"],
        args.market_null_iterations,
        rng,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "ledgers": [{"label": label, "csv_path": path} for label, path in ledger_args],
        "labels": labels,
        "aligned_fights": int(len(df)),
        "configs": [
            {"label": config.label, "dev_days": config.dev_days, "c": config.c_value}
            for config in configs
        ],
        "first_holdout_start": args.first_holdout_start,
        "last_holdout_end": args.last_holdout_end,
        "holdout_days": args.holdout_days,
        "step_days": args.step_days,
        "min_dev_fights": args.min_dev_fights,
        "min_holdout_fights": args.min_holdout_fights,
        "min_prior_selection_fights": args.min_prior_selection_fights,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "folds_by_config": fold_specs,
        "candidate_summaries": candidate_summaries(predictions),
        "rolling_selection": rolling_summary,
        "outputs": {
            "summary_json": str(output_dir / "residual_meta_config_selection_audit.json"),
            "report_md": str(output_dir / "residual_meta_config_selection_audit.md"),
            "selected_predictions_csv": str(output_dir / "rolling_selected_predictions.csv"),
        },
    }

    json_path = output_dir / "residual_meta_config_selection_audit.json"
    md_path = output_dir / "residual_meta_config_selection_audit.md"
    selected_path = output_dir / "rolling_selected_predictions.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    selected.to_csv(selected_path, index=False)

    null = rolling_summary.get("market_null") or {}
    print(
        "Rolling selected delta LL "
        f"{rolling_summary['market_minus_meta_log_loss']:.4f}, "
        f"market-null p {fmt_p(null.get('p_value_observed_or_better'))}"
    )
    print(f"Report: {md_path}")


if __name__ == "__main__":
    main()
