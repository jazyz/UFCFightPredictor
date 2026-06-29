#!/usr/bin/env python3
"""Predeclared head-focused striking redesign selection audit.

The component-context audit found a stable compact signal around significant
strike efficiency and head-strike features, while generic significant-strike
pace/volume behaved wrong-way after market control. This audit tests a small
head-focused redesign family with rolling prior-fold selection and a market
selection-null, without changing any frozen paper policy.
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

from testing.market_aware_feature_audit import (  # noqa: E402
    VariantSpec,
    aggregate_predictions,
    aligned_market_feature_frame,
    fit_predict_variant,
    market_null_simulation,
    run_observed_predictions,
)
from testing.market_residual_meta_audit import EPS, iter_folds  # noqa: E402
from testing.striking_core_betting_calibration_audit import (  # noqa: E402
    add_bet_rows,
    attach_odds,
)
from testing.striking_feature_engineering_audit import (  # noqa: E402
    EDGE_THRESHOLD,
    add_pace_features,
    bet_table,
    build_pace_features,
    fmt_float,
    fmt_p,
    fmt_pct,
    fmt_units,
    rolling_prior_probability_selection,
    rolling_prior_profit_selection,
    selection_path_table,
    summarize_bet_frame,
    summarize_bets_for_variant,
    summarize_prediction_frame,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_redesign_selection_audit"


def parse_args():
    parser = argparse.ArgumentParser(description="Audit a head-focused striking redesign family")
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
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
    parser.add_argument("--min-prior-rows", type=int, default=80)
    parser.add_argument("--min-prior-bets", type=int, default=25)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=300)
    parser.add_argument("--selection-null-iterations", type=int, default=200)
    parser.add_argument("--bet-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def build_redesign_variants(df: pd.DataFrame) -> list[VariantSpec]:
    specs = [
        VariantSpec("market_recalibrated", ("market_logit",), "market-logit-only recalibration baseline"),
        VariantSpec(
            "current_sigpct_head",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
            ),
            "current compact sigpct/head challenger anchor",
        ),
        VariantSpec(
            "pace_adjusted_mixed_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential_pm oppdiff",
                "Head differential_pm oppdiff",
            ),
            "frozen pace-adjusted challenger anchor",
        ),
        VariantSpec(
            "sigpct_only",
            ("market_logit", "Sig. str.% differential oppdiff"),
            "efficiency-only reference",
        ),
        VariantSpec(
            "sigpct_head_pm",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential_pm oppdiff",
            ),
            "efficiency plus head-strike pace differential",
        ),
        VariantSpec(
            "sigpct_head_for_against",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head for_pm oppdiff",
                "Head against_pm oppdiff",
            ),
            "efficiency plus head-strike offense and absorbed-pace split",
        ),
        VariantSpec(
            "sigpct_head_raw_pm",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
                "Head differential_pm oppdiff",
            ),
            "efficiency plus raw and pace-adjusted head differential",
        ),
        VariantSpec(
            "sigpct_head_raw_for_against",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
                "Head for_pm oppdiff",
                "Head against_pm oppdiff",
            ),
            "efficiency plus raw head differential and head offense/defense split",
        ),
        VariantSpec(
            "sigpct_head_raw_against",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
                "Head against_pm oppdiff",
            ),
            "efficiency plus raw head differential and absorbed head pace",
        ),
    ]
    available = set(df.columns)
    missing = {
        spec.name: [column for column in spec.feature_columns if column not in available]
        for spec in specs
    }
    missing = {name: columns for name, columns in missing.items() if columns}
    if missing:
        raise SystemExit(f"Missing redesign feature columns: {missing}")
    return specs


def prepare_augmented_frame(args) -> tuple[pd.DataFrame, dict, list[VariantSpec], list]:
    source = pd.read_csv(args.source_fights)
    features = pd.read_csv(args.features)
    pace_features, pace_reconstruction = build_pace_features(source, features)

    align_args = argparse.Namespace(
        features=args.features,
        odds=args.odds,
        fight_details_source=args.fight_details_source,
        min_training_date=args.min_training_date,
        last_holdout_end=args.last_holdout_end,
        include_womens_fights=False,
    )
    aligned, metadata = aligned_market_feature_frame(align_args)
    aligned, pace_metadata = add_pace_features(aligned, pace_features)
    variants = build_redesign_variants(aligned)
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
    if not folds:
        raise SystemExit("No folds met the minimum fight constraints")
    metadata.update(pace_metadata)
    metadata["pace_reconstruction"] = pace_reconstruction
    metadata["source_fights_path"] = args.source_fights
    return aligned, metadata, variants, folds


def run_predictions_for_labels(
    df: pd.DataFrame,
    folds,
    variants: list[VariantSpec],
    labels: np.ndarray,
    c_value: float,
) -> pd.DataFrame:
    prediction_rows = []
    labels = np.asarray(labels, dtype=int)
    for fold in folds:
        train_df = df.iloc[fold.dev_indices]
        eval_df = df.iloc[fold.holdout_indices]
        for variant in variants:
            probabilities, _ = fit_predict_variant(
                train_df,
                eval_df,
                labels[fold.dev_indices],
                variant.feature_columns,
                c_value,
            )
            for row_index, probability in zip(fold.holdout_indices, probabilities):
                source = df.iloc[row_index]
                red_won = bool(labels[row_index])
                prediction_rows.append(
                    {
                        "fold": int(fold.fold_index),
                        "variant": variant.name,
                        "event_date": source["event_date"].date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "winner_name": source["red_fighter"] if red_won else source["blue_fighter"],
                        "red_won": red_won,
                        "market_probability": float(source["red_market_probability"]),
                        "candidate_probability": float(probability),
                    }
                )
    return pd.DataFrame(prediction_rows)


def build_all_bets(predictions: pd.DataFrame, aligned: pd.DataFrame, candidate_names: list[str]) -> pd.DataFrame:
    frames = []
    for name in candidate_names:
        subset = predictions[predictions["variant"].eq(name)].copy()
        if subset.empty:
            continue
        bets = add_bet_rows(attach_odds(subset, aligned), EDGE_THRESHOLD)
        if bets.empty:
            continue
        bets["variant"] = name
        frames.append(bets)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def evaluate_selectors(
    df: pd.DataFrame,
    folds,
    variants: list[VariantSpec],
    labels: np.ndarray,
    c_value: float,
    candidate_names: list[str],
    min_prior_rows: int,
    min_prior_bets: int,
    bootstrap_iterations: int,
    rng,
) -> dict:
    predictions = run_predictions_for_labels(df, folds, variants, labels, c_value)
    probability_selected, probability_path = rolling_prior_probability_selection(
        predictions,
        candidate_names,
        min_prior_rows,
    )
    probability_summary = summarize_prediction_frame(
        probability_selected,
        "rolling_prior_probability_delta",
        bootstrap_iterations,
        rng,
    )

    all_bets = build_all_bets(predictions, df, candidate_names)
    profit_selected, profit_path = rolling_prior_profit_selection(
        all_bets,
        candidate_names,
        min_prior_bets,
    )
    profit_summary = summarize_bet_frame(
        profit_selected,
        "rolling_prior_profit",
        bootstrap_iterations,
        0,
        rng,
    )
    return {
        "all_predictions": predictions,
        "all_bets": all_bets,
        "probability_summary": probability_summary,
        "probability_path": probability_path,
        "probability_predictions": probability_selected,
        "profit_summary": profit_summary,
        "profit_path": profit_path,
        "profit_bets": profit_selected,
    }


def fixed_betting_summary(
    predictions: pd.DataFrame,
    aligned: pd.DataFrame,
    variants: list[VariantSpec],
    args,
    rng,
) -> tuple[dict, pd.DataFrame]:
    summaries = {}
    frames = []
    for variant in variants:
        if variant.name == "market_recalibrated":
            continue
        bets, summary = summarize_bets_for_variant(
            predictions,
            aligned,
            variant.name,
            args.bootstrap_iterations,
            args.bet_null_iterations,
            rng,
        )
        summaries[variant.name] = summary
        if not bets.empty:
            frames.append(bets)
    return summaries, pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def empirical_p_value(null_values: np.ndarray, observed: float | None) -> float | None:
    values = np.asarray(null_values, dtype=float)
    values = values[np.isfinite(values)]
    if observed is None or not np.isfinite(float(observed)) or len(values) == 0:
        return None
    return float((np.sum(values >= float(observed)) + 1) / (len(values) + 1))


def null_summary(values: np.ndarray, observed: float | None) -> dict:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if len(finite) == 0:
        return {
            "iterations": 0,
            "observed": observed,
            "null_mean": None,
            "null_ci_95": [None, None],
            "p_value_observed_or_better": None,
            "prob_null_positive": None,
        }
    return {
        "iterations": int(len(finite)),
        "observed": None if observed is None else float(observed),
        "null_mean": float(np.mean(finite)),
        "null_ci_95": [float(value) for value in np.percentile(finite, [2.5, 97.5])],
        "p_value_observed_or_better": empirical_p_value(finite, observed),
        "prob_null_positive": float(np.mean(finite > 0.0)),
    }


def selection_null(
    aligned: pd.DataFrame,
    folds,
    variants: list[VariantSpec],
    observed: dict,
    args,
    rng,
) -> tuple[dict, pd.DataFrame]:
    candidate_names = [variant.name for variant in variants if variant.name != "market_recalibrated"]
    market = np.clip(
        aligned["red_market_probability"].astype(float).to_numpy(),
        EPS,
        1.0 - EPS,
    )
    probability_null = np.empty(args.selection_null_iterations, dtype=float)
    profit_null = np.empty(args.selection_null_iterations, dtype=float)
    null_rows = []
    for iteration in range(args.selection_null_iterations):
        labels = (rng.random(len(aligned)) < market).astype(int)
        simulated = evaluate_selectors(
            aligned,
            folds,
            variants,
            labels,
            args.c,
            candidate_names,
            args.min_prior_rows,
            args.min_prior_bets,
            0,
            rng,
        )
        probability_delta = simulated["probability_summary"]["delta_log_loss"]
        profit = simulated["profit_summary"]["profit"]
        probability_null[iteration] = np.nan if probability_delta is None else float(probability_delta)
        profit_null[iteration] = np.nan if profit is None else float(profit)
        null_rows.append(
            {
                "iteration": int(iteration + 1),
                "probability_delta_log_loss": probability_null[iteration],
                "probability_positive_folds": simulated["probability_summary"]["positive_folds"],
                "probability_folds": simulated["probability_summary"]["folds"],
                "profit": profit_null[iteration],
                "profit_bets": simulated["profit_summary"]["bets"],
                "profit_positive_folds": simulated["profit_summary"]["positive_folds"],
                "profit_folds": simulated["profit_summary"]["folds"],
            }
        )

    observed_probability = observed["probability_summary"]["delta_log_loss"]
    observed_profit = observed["profit_summary"]["profit"]
    return {
        "probability_delta_log_loss": null_summary(probability_null, observed_probability),
        "profit": null_summary(profit_null, observed_profit),
    }, pd.DataFrame(null_rows)


def fixed_probability_table(result: dict) -> list[str]:
    null = result.get("fixed_market_null") or {}
    lines = [
        "| Variant | Features | Delta LL | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(
        result["fixed_summary"].items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
        reverse=True,
    ):
        null_row = null.get(name) or {}
        boot = row.get("event_bootstrap") or {}
        lines.append(
            "| {name} | {features} | {delta} | {brier} | {acc} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                features=len(row["feature_columns"]),
                delta=fmt_float(row["market_minus_candidate_log_loss"]),
                brier=fmt_float(row["market_minus_candidate_brier"]),
                acc=fmt_pct(row["candidate"]["accuracy"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
                null_p=fmt_p(null_row.get("p_value_observed_or_better")),
            )
        )
    return lines


def fixed_bet_table(result: dict) -> list[str]:
    lines = [
        "| Variant | Bets | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(
        result["fixed_betting"].items(),
        key=lambda item: item[1]["profit"],
        reverse=True,
    ):
        lines.append(
            "| {name} | {bets} | {profit} | {roi} | {actual} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                bets=row["bets"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row.get("roi")),
                actual=fmt_pct(row.get("actual_minus_market")),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(row.get("bootstrap_p_profit_le_zero")),
                null_p=fmt_p(row.get("market_null_p")),
            )
        )
    return lines


def selector_probability_table(summary: dict) -> list[str]:
    return [
        "| Selector | Fights | Delta LL | Delta Brier | Accuracy | Positive Folds | Bootstrap P(delta<=0) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| `{variant}` | {fights} | {delta} | {brier} | {acc} | {pos} / {folds} | {boot} |".format(
            variant=summary["variant"],
            fights=summary["fights"],
            delta=fmt_float(summary["delta_log_loss"]),
            brier=fmt_float(summary["delta_brier"]),
            acc=fmt_pct(summary["accuracy"]),
            pos=summary["positive_folds"],
            folds=summary["folds"],
            boot=fmt_p(summary["bootstrap_p_delta_le_zero"]),
        ),
    ]


def null_table(selection_null_result: dict) -> list[str]:
    probability = selection_null_result["probability_delta_log_loss"]
    profit = selection_null_result["profit"]
    return [
        "| Selector | Observed | Null Mean | Null 95% CI | P(null >= observed) | P(null > 0) |",
        "| --- | ---: | ---: | --- | ---: | ---: |",
        "| probability-delta selector | {observed} | {mean} | {ci} | {p} | {pos} |".format(
            observed=fmt_float(probability["observed"]),
            mean=fmt_float(probability["null_mean"]),
            ci=f"{fmt_float(probability['null_ci_95'][0])} to {fmt_float(probability['null_ci_95'][1])}",
            p=fmt_p(probability["p_value_observed_or_better"]),
            pos=fmt_p(probability["prob_null_positive"]),
        ),
        "| profit selector | {observed} | {mean} | {ci} | {p} | {pos} |".format(
            observed=fmt_units(profit["observed"]),
            mean=fmt_units(profit["null_mean"]),
            ci=f"{fmt_units(profit['null_ci_95'][0])} to {fmt_units(profit['null_ci_95'][1])}",
            p=fmt_p(profit["p_value_observed_or_better"]),
            pos=fmt_p(profit["prob_null_positive"]),
        ),
    ]


def markdown_report(result: dict) -> str:
    observed = result["observed"]
    probability_p = result["selection_null"]["probability_delta_log_loss"]["p_value_observed_or_better"]
    profit_p = result["selection_null"]["profit"]["p_value_observed_or_better"]
    best_fixed_probability = max(
        result["fixed_summary"].items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
    )
    best_fixed_bet = max(result["fixed_betting"].items(), key=lambda item: item[1]["profit"])
    probability_path = observed["probability_selection_path"]
    profit_path = observed["profit_selection_path"]
    selected_probability_variants = sorted({row["variant"] for row in probability_path})
    selected_profit_variants = sorted({row["variant"] for row in profit_path})

    lines = [
        "# Striking Redesign Selection Audit",
        "",
        "This audit tests a small predeclared head-focused striking redesign",
        "family motivated by the component-context result: keep significant",
        "strike efficiency and head-strike concepts, avoid generic",
        "significant-strike pace/volume, and select variants using only prior",
        "folds. It does not change any frozen paper policy.",
        "",
        "## Protocol",
        "",
        f"- aligned men-only rows: `{result['metadata']['aligned_rows']}`",
        f"- candidate variants: `{len(result['candidate_names'])}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- first holdout start: `{result['parameters']['first_holdout_start']}`",
        f"- last holdout end: `{result['parameters']['last_holdout_end']}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- fixed betting threshold: `{fmt_pct(EDGE_THRESHOLD)}`",
        "- event cap: none",
        f"- fixed market-null refits: `{result['parameters']['market_null_iterations']}`",
        f"- selection-null iterations: `{result['parameters']['selection_null_iterations']}`",
        "",
        "## Fixed Variant Probability Results",
        "",
        *fixed_probability_table(result),
        "",
        "## Fixed 2% Positive-Edge Uncapped PnL",
        "",
        *fixed_bet_table(result),
        "",
        "## Rolling Prior-Fold Selectors",
        "",
        *selector_probability_table(observed["probability_summary"]),
        "",
        *bet_table([observed["profit_summary"]]),
        "",
        "Probability selection path:",
        "",
        *selection_path_table(
            observed["probability_selection_path"],
            "prior_delta_log_loss",
            "eval_delta_log_loss",
            "eval_rows",
        ),
        "",
        "Profit selection path:",
        "",
        *selection_path_table(
            observed["profit_selection_path"],
            "prior_profit",
            "eval_profit",
            "eval_bets",
        ),
        "",
        "## Selection-Null Results",
        "",
        *null_table(result["selection_null"]),
        "",
        "## Variant Definitions",
        "",
        "| Variant | Note | Feature Columns |",
        "| --- | --- | --- |",
    ]
    for variant in result["variants"]:
        lines.append(
            "| {name} | {note} | `{features}` |".format(
                name=variant["name"],
                note=variant["note"],
                features="`, `".join(variant["feature_columns"]),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Best fixed probability variant: `{}` with Delta LL `{}` and market-null p `{}`.".format(
                best_fixed_probability[0],
                fmt_float(best_fixed_probability[1]["market_minus_candidate_log_loss"]),
                fmt_p(
                    (result.get("fixed_market_null") or {})
                    .get(best_fixed_probability[0], {})
                    .get("p_value_observed_or_better")
                ),
            ),
            "- Best fixed uncapped `2%` PnL variant: `{}` with profit `{}`, ROI `{}`, and market-null p `{}`.".format(
                best_fixed_bet[0],
                fmt_units(best_fixed_bet[1]["profit"]),
                fmt_pct(best_fixed_bet[1].get("roi")),
                fmt_p(best_fixed_bet[1].get("market_null_p")),
            ),
            "- Probability selector chose: `{}`.".format("`, `".join(selected_probability_variants)),
            "- Profit selector chose: `{}`.".format("`, `".join(selected_profit_variants)),
        ]
    )
    if probability_p is not None and probability_p <= 0.05:
        lines.append("- The rolling probability selector clears the selection-null screen.")
    else:
        lines.append("- The rolling probability selector does not clear the selection-null screen.")
    if profit_p is not None and profit_p <= 0.05:
        lines.append("- The rolling profit selector clears the selection-null screen.")
    else:
        lines.append("- The rolling profit selector does not clear the selection-null screen.")
    lines.append(
        "- Treat this as feature-design evidence only. A new frozen policy would need future pre-outcome paper validation and should not be promoted merely because this historical redesign family is positive."
    )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- `{result['outputs']['fixed_predictions_csv']}`",
            f"- `{result['outputs']['fixed_edge02_bets_csv']}`",
            f"- `{result['outputs']['observed_probability_predictions_csv']}`",
            f"- `{result['outputs']['observed_profit_bets_csv']}`",
            f"- `{result['outputs']['selection_null_csv']}`",
            f"- `{result['outputs']['summary_json']}`",
            f"- `{result['outputs']['report_md']}`",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit(args) -> tuple[dict, dict[str, pd.DataFrame]]:
    rng = np.random.default_rng(args.seed)
    aligned, metadata, variants, folds = prepare_augmented_frame(args)
    candidate_names = [variant.name for variant in variants if variant.name != "market_recalibrated"]

    fixed_predictions, coefficients, fold_rows = run_observed_predictions(aligned, folds, variants, args.c)
    fixed_summary = aggregate_predictions(fixed_predictions, variants, args.bootstrap_iterations, rng)
    fixed_null = market_null_simulation(
        aligned,
        folds,
        variants,
        fixed_summary,
        args.c,
        args.market_null_iterations,
        rng,
    )
    fixed_betting, fixed_bets = fixed_betting_summary(fixed_predictions, aligned, variants, args, rng)

    observed_labels = aligned["red_won"].astype(int).to_numpy()
    observed = evaluate_selectors(
        aligned,
        folds,
        variants,
        observed_labels,
        args.c,
        candidate_names,
        args.min_prior_rows,
        args.min_prior_bets,
        args.bootstrap_iterations,
        rng,
    )
    selection_null_result, null_rows = selection_null(aligned, folds, variants, observed, args, rng)

    result = {
        "parameters": {
            "source_fights": args.source_fights,
            "features": args.features,
            "odds": args.odds,
            "fight_details_source": args.fight_details_source,
            "first_holdout_start": args.first_holdout_start,
            "last_holdout_end": args.last_holdout_end,
            "dev_days": args.dev_days,
            "holdout_days": args.holdout_days,
            "step_days": args.step_days,
            "min_dev_fights": args.min_dev_fights,
            "min_holdout_fights": args.min_holdout_fights,
            "c": args.c,
            "edge_threshold": EDGE_THRESHOLD,
            "min_prior_rows": args.min_prior_rows,
            "min_prior_bets": args.min_prior_bets,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "selection_null_iterations": args.selection_null_iterations,
            "bet_null_iterations": args.bet_null_iterations,
            "seed": args.seed,
        },
        "metadata": metadata,
        "variants": [
            {
                "name": variant.name,
                "feature_columns": list(variant.feature_columns),
                "note": variant.note,
            }
            for variant in variants
        ],
        "candidate_names": candidate_names,
        "folds": [
            {
                "fold": int(fold.fold_index),
                "dev_start": fold.dev_start.date().isoformat(),
                "dev_end": fold.dev_end.date().isoformat(),
                "holdout_start": fold.holdout_start.date().isoformat(),
                "holdout_end": fold.holdout_end.date().isoformat(),
                "dev_fights": int(len(fold.dev_indices)),
                "holdout_fights": int(len(fold.holdout_indices)),
            }
            for fold in folds
        ],
        "fixed_summary": fixed_summary,
        "fixed_market_null": fixed_null,
        "fixed_betting": fixed_betting,
        "coefficients": coefficients,
        "observed": {
            "probability_summary": observed["probability_summary"],
            "probability_selection_path": observed["probability_path"],
            "profit_summary": observed["profit_summary"],
            "profit_selection_path": observed["profit_path"],
        },
        "selection_null": selection_null_result,
    }
    outputs = {
        "fixed_predictions": fixed_predictions,
        "fixed_bets": fixed_bets,
        "probability_predictions": observed["probability_predictions"],
        "profit_bets": observed["profit_bets"],
        "null_rows": null_rows,
    }
    return result, outputs


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result, frames = run_audit(args)

    fixed_predictions_path = output_dir / "fixed_variant_predictions.csv"
    fixed_bets_path = output_dir / "fixed_edge02_bets.csv"
    probability_path = output_dir / "observed_rolling_probability_predictions.csv"
    profit_path = output_dir / "observed_rolling_profit_bets.csv"
    null_path = output_dir / "selection_null_distribution.csv"
    json_path = output_dir / "striking_redesign_selection_audit.json"
    md_path = output_dir / "striking_redesign_selection_audit.md"

    frames["fixed_predictions"].to_csv(fixed_predictions_path, index=False)
    frames["fixed_bets"].to_csv(fixed_bets_path, index=False)
    frames["probability_predictions"].to_csv(probability_path, index=False)
    frames["profit_bets"].to_csv(profit_path, index=False)
    frames["null_rows"].to_csv(null_path, index=False)
    result["outputs"] = {
        "fixed_predictions_csv": str(fixed_predictions_path),
        "fixed_edge02_bets_csv": str(fixed_bets_path),
        "observed_probability_predictions_csv": str(probability_path),
        "observed_profit_bets_csv": str(profit_path),
        "selection_null_csv": str(null_path),
        "summary_json": str(json_path),
        "report_md": str(md_path),
    }
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
