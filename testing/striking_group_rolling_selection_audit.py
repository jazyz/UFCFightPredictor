#!/usr/bin/env python3
"""Rolling selection validation for grouped striking after-market candidates.

The grouped striking audit found a strong fixed post-hoc candidate. This script
asks a stricter question: if only prior grouped-audit folds were available,
which striking group would have been selected for the next fold, and how would
that selected policy perform?
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

from testing.feature_signal_after_market_audit import (  # noqa: E402
    EPS,
    binary_loss,
    event_bootstrap_delta,
    fmt_float,
    fmt_p,
    load_features,
    load_predictions,
    log_loss,
    merge_predictions_features,
)
from testing.striking_group_after_market_audit import (  # noqa: E402
    DEFAULT_FEATURES,
    DEFAULT_PREDICTIONS,
    build_variants,
    run_predictions,
    summarize_candidate,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_group_rolling_selection_audit"
OBJECTIVES = {
    "incremental_delta": "incremental_delta_log_loss",
    "market_delta": "market_delta_log_loss",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Validate rolling selection over grouped striking candidates")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--c", type=float, default=0.1)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def add_delta_columns(predictions: pd.DataFrame) -> pd.DataFrame:
    work = predictions.copy()
    y = work["red_won"].astype(float).to_numpy()
    market = work["market_probability"].astype(float).to_numpy()
    baseline = work["baseline_probability"].astype(float).to_numpy()
    candidate = work["candidate_probability"].astype(float).to_numpy()
    work["market_delta_log_loss"] = binary_loss(y, market) - binary_loss(y, candidate)
    work["incremental_delta_log_loss"] = binary_loss(y, baseline) - binary_loss(y, candidate)
    return work


def select_by_prior_folds(
    predictions: pd.DataFrame,
    objective_col: str,
) -> tuple[pd.DataFrame, list[dict]]:
    work = add_delta_columns(predictions)
    folds = sorted(int(value) for value in work["fold"].unique())
    variants = list(dict.fromkeys(work["variant"].astype(str).tolist()))
    selected_parts = []
    selection_rows = []

    for fold in folds:
        prior = work[work["fold"] < fold]
        current = work[work["fold"] == fold]
        if prior.empty:
            continue

        scores = {}
        for variant in variants:
            subset = prior[prior["variant"] == variant]
            if subset.empty:
                continue
            scores[variant] = float(subset[objective_col].mean())
        if not scores:
            continue

        selected_variant = max(scores, key=lambda variant: (scores[variant], -variants.index(variant)))
        selected = current[current["variant"] == selected_variant].copy()
        selected_parts.append(selected)
        selection_rows.append(
            {
                "fold": int(fold),
                "objective": objective_col,
                "selected_variant": selected_variant,
                "prior_score": float(scores[selected_variant]),
                "prior_scores": scores,
                "eval_fights": int(len(selected)),
                "eval_market_delta_log_loss": float(selected["market_delta_log_loss"].mean()),
                "eval_incremental_delta_log_loss": float(selected["incremental_delta_log_loss"].mean()),
            }
        )

    if not selected_parts:
        return pd.DataFrame(), selection_rows
    return pd.concat(selected_parts, ignore_index=True), selection_rows


def summarize_rows(
    rows: pd.DataFrame,
    variant_name: str,
    bootstrap_iterations: int,
    rng,
) -> dict:
    return summarize_candidate(rows, "candidate_probability", variant_name, bootstrap_iterations, rng)


def reference_rows(predictions: pd.DataFrame, folds: list[int]) -> pd.DataFrame:
    base = predictions.drop_duplicates("fight_key").copy()
    return base[base["fold"].isin(folds)].copy()


def summarize_reference(
    rows: pd.DataFrame,
    probability_col: str,
    variant_name: str,
    bootstrap_iterations: int,
    rng,
) -> dict:
    base = rows.copy()
    base["candidate_probability"] = base[probability_col].astype(float)
    return summarize_candidate(base, "candidate_probability", variant_name, bootstrap_iterations, rng)


def fixed_variant_summary(
    predictions: pd.DataFrame,
    variant_name: str,
    folds: list[int],
    bootstrap_iterations: int,
    rng,
) -> dict:
    rows = predictions[
        predictions["variant"].eq(variant_name) & predictions["fold"].isin(folds)
    ].copy()
    return summarize_rows(rows, f"fixed_{variant_name}", bootstrap_iterations, rng)


def summarize_observed(
    predictions: pd.DataFrame,
    bootstrap_iterations: int,
    rng,
) -> dict:
    selected = {}
    selections = {}
    for objective_name, objective_col in OBJECTIVES.items():
        selected_rows, selection_rows = select_by_prior_folds(predictions, objective_col)
        selected[objective_name] = summarize_rows(
            selected_rows,
            f"rolling_selected_{objective_name}",
            bootstrap_iterations,
            rng,
        )
        selections[objective_name] = selection_rows

    eval_folds = sorted(int(value) for value in selected_rows["fold"].unique())
    refs = reference_rows(predictions, eval_folds)
    references = {
        "market_recalibrated": summarize_reference(
            refs,
            "baseline_probability",
            "market_recalibrated",
            bootstrap_iterations,
            rng,
        )
    }
    if refs["selected_probability"].notna().all():
        references["selected_shrinkage"] = summarize_reference(
            refs,
            "selected_probability",
            "selected_shrinkage",
            bootstrap_iterations,
            rng,
        )
    if refs["fixed_half_probability"].notna().all():
        references["fixed_half_residual"] = summarize_reference(
            refs,
            "fixed_half_probability",
            "fixed_half_residual",
            bootstrap_iterations,
            rng,
        )
    fixed = {
        "fixed_mixed_sig_head_core": fixed_variant_summary(
            predictions,
            "mixed_sig_head_core",
            eval_folds,
            bootstrap_iterations,
            rng,
        )
    }
    return {
        "eval_folds": eval_folds,
        "selected": selected,
        "selections": selections,
        "references": references,
        "fixed": fixed,
    }


def run_predictions_for_labels(
    df: pd.DataFrame,
    labels: np.ndarray,
    c_value: float,
) -> pd.DataFrame:
    simulated = df.copy()
    simulated["red_won"] = labels.astype(int)
    variants = build_variants(simulated)
    predictions, _ = run_predictions(simulated, variants, c_value)
    return predictions


def summarize_selected_deltas(rows: pd.DataFrame) -> tuple[float, float]:
    if rows.empty:
        return np.nan, np.nan
    y = rows["red_won"].astype(float).to_numpy()
    market = rows["market_probability"].astype(float).to_numpy()
    baseline = rows["baseline_probability"].astype(float).to_numpy()
    candidate = rows["candidate_probability"].astype(float).to_numpy()
    market_delta = float(np.mean(binary_loss(y, market) - binary_loss(y, candidate)))
    incremental_delta = float(np.mean(binary_loss(y, baseline) - binary_loss(y, candidate)))
    return market_delta, incremental_delta


def market_null_simulation(
    df: pd.DataFrame,
    observed: dict,
    c_value: float,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    market = np.clip(df["market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    values = {
        objective: {
            "market_delta": np.empty(iterations, dtype=float),
            "incremental_delta": np.empty(iterations, dtype=float),
        }
        for objective in OBJECTIVES
    }

    for iteration in range(iterations):
        labels = (rng.random(len(df)) < market).astype(int)
        simulated_predictions = run_predictions_for_labels(df, labels, c_value)
        for objective, objective_col in OBJECTIVES.items():
            selected_rows, _ = select_by_prior_folds(simulated_predictions, objective_col)
            market_delta, incremental_delta = summarize_selected_deltas(selected_rows)
            values[objective]["market_delta"][iteration] = market_delta
            values[objective]["incremental_delta"][iteration] = incremental_delta

    result = {}
    for objective in OBJECTIVES:
        observed_row = observed["selected"][objective]
        market_values = values[objective]["market_delta"]
        incremental_values = values[objective]["incremental_delta"]
        result[objective] = {
            "iterations": int(iterations),
            "market_delta_null_mean": float(np.nanmean(market_values)),
            "market_delta_null_ci_95": [
                float(value) for value in np.nanpercentile(market_values, [2.5, 97.5])
            ],
            "market_delta_p_value": float(
                (np.nansum(market_values >= observed_row["market_delta_log_loss"]) + 1)
                / (iterations + 1)
            ),
            "incremental_delta_null_mean": float(np.nanmean(incremental_values)),
            "incremental_delta_null_ci_95": [
                float(value) for value in np.nanpercentile(incremental_values, [2.5, 97.5])
            ],
            "incremental_delta_p_value": float(
                (np.nansum(incremental_values >= observed_row["incremental_delta_log_loss"]) + 1)
                / (iterations + 1)
            ),
        }
    return result


def summary_table(rows: dict, null: dict | None = None) -> list[str]:
    lines = [
        "| Policy | Fights | Market Delta LL | Inc Delta vs Recal | Positive Folds | Boot P(inc<=0) | Null p(market) | Null p(inc) | Latest Inc Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in rows.items():
        boot = summary.get("incremental_bootstrap") or {}
        null_row = (null or {}).get(name) or {}
        lines.append(
            "| {name} | {fights} | {market_delta} | {inc_delta} | {positive} / {folds} | {boot} | {null_market} | {null_inc} | {latest} |".format(
                name=name,
                fights=summary["fights"],
                market_delta=fmt_float(summary["market_delta_log_loss"]),
                inc_delta=fmt_float(summary["incremental_delta_log_loss"]),
                positive=summary["positive_market_folds"],
                folds=summary["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
                null_market=fmt_p(null_row.get("market_delta_p_value")),
                null_inc=fmt_p(null_row.get("incremental_delta_p_value")),
                latest=fmt_float(summary["latest_incremental_delta_log_loss"]),
            )
        )
    return lines


def selection_table(selection_rows: list[dict]) -> list[str]:
    lines = [
        "| Fold | Selected Variant | Prior Score | Eval Market Delta LL | Eval Inc Delta LL | Fights |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in selection_rows:
        lines.append(
            "| {fold} | `{variant}` | {prior} | {market_delta} | {inc_delta} | {fights} |".format(
                fold=row["fold"],
                variant=row["selected_variant"],
                prior=fmt_float(row["prior_score"]),
                market_delta=fmt_float(row["eval_market_delta_log_loss"]),
                inc_delta=fmt_float(row["eval_incremental_delta_log_loss"]),
                fights=row["eval_fights"],
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    null = result.get("market_null") or {}
    selected_with_null = {
        name: summary
        for name, summary in result["selected"].items()
    }
    refs_and_fixed = {
        **result["references"],
        **result["fixed"],
    }
    best_objective, best_summary = max(
        result["selected"].items(),
        key=lambda item: item[1]["incremental_delta_log_loss"],
    )
    best_null = null.get(best_objective) or {}
    fixed = result["fixed"]["fixed_mixed_sig_head_core"]
    gap_to_fixed = best_summary["incremental_delta_log_loss"] - fixed["incremental_delta_log_loss"]
    lines = [
        "# Striking Group Rolling Selection Audit",
        "",
        "This audit validates the post-hoc grouped striking result with a stricter",
        "prior-fold selection protocol. Fold `2` is used only as prior evidence;",
        "evaluation starts at fold `3`. For each later fold, the selector chooses",
        "the grouped striking variant with the best mean prior fold delta.",
        "",
        "## Protocol",
        "",
        f"- predictions: `{result['paths']['predictions']}`",
        f"- features: `{result['paths']['features']}`",
        f"- merged rows: `{result['merged_rows']}`",
        f"- rolling selection eval folds: `{', '.join(str(value) for value in result['eval_folds'])}`",
        f"- rolling selection fights: `{best_summary['fights']}`",
        f"- grouped variants available: `{len(result['variants'])}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- bootstrap iterations: `{result['parameters']['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['parameters']['market_null_iterations']}`",
        "",
        "## Rolling Selected Policies",
        "",
        *summary_table(selected_with_null, null),
        "",
        "## Same-Fold References",
        "",
        *summary_table(refs_and_fixed),
        "",
        "## Incremental-Objective Selection Path",
        "",
        *selection_table(result["selections"]["incremental_delta"]),
        "",
        "## Market-Objective Selection Path",
        "",
        *selection_table(result["selections"]["market_delta"]),
        "",
        "## Interpretation",
        "",
        f"- Best rolling selector: `{best_objective}` with market Delta LL `{fmt_float(best_summary['market_delta_log_loss'])}` and incremental Delta LL `{fmt_float(best_summary['incremental_delta_log_loss'])}`.",
        f"- Selector market-null p-values: `{fmt_p(best_null.get('market_delta_p_value'))}` versus raw market and `{fmt_p(best_null.get('incremental_delta_p_value'))}` versus market recalibration.",
        f"- Fixed `mixed_sig_head_core` on the same folds has incremental Delta LL `{fmt_float(fixed['incremental_delta_log_loss'])}`; rolling selection is `{fmt_float(gap_to_fixed)}` relative to fixed mixed.",
    ]
    if best_summary["incremental_delta_log_loss"] <= 0:
        lines.append("- Rolling selection does not validate the grouped striking clue.")
    elif (best_null.get("incremental_delta_p_value") or 1.0) > 0.05:
        lines.append(
            "- Rolling selection is positive, but it does not clear the market-null screen."
        )
    else:
        lines.append(
            "- Rolling selection clears the unadjusted market-null screen, but the grouped family is still post-hoc and needs a predeclared leak-safe model/backtest."
        )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    predictions = load_predictions(args.predictions)
    features = load_features(args.features)
    df = merge_predictions_features(predictions, features)
    df = df.sort_values(["event_date", "fight_key"]).reset_index(drop=True)
    variants = build_variants(df)
    prediction_rows, _ = run_predictions(df, variants, args.c)
    observed = summarize_observed(prediction_rows, args.bootstrap_iterations, rng)
    null = market_null_simulation(
        df,
        observed,
        args.c,
        args.market_null_iterations,
        rng,
    )
    return {
        "paths": {
            "predictions": args.predictions,
            "features": args.features,
        },
        "parameters": {
            "c": args.c,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "seed": args.seed,
        },
        "merged_rows": int(len(df)),
        "variants": [
            {
                "name": variant.name,
                "feature_columns": list(variant.feature_columns),
                "note": variant.note,
            }
            for variant in variants
        ],
        "eval_folds": observed["eval_folds"],
        "selected": observed["selected"],
        "selections": observed["selections"],
        "references": observed["references"],
        "fixed": observed["fixed"],
        "market_null": null,
    }


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_group_rolling_selection_audit.json"
    md_path = output_dir / "striking_group_rolling_selection_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
