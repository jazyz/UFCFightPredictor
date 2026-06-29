#!/usr/bin/env python3
"""Selection-null audit for pace-adjusted striking feature variants.

The pace-adjusted striking audit found an attractive fixed PnL diagnostic, but
the variants were designed after seeing earlier striking-core evidence. This
script reruns the rolling prior-fold feature-variant selectors under
market-implied outcomes, including refitting the candidate models on each
simulated label path.
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
    aligned_market_feature_frame,
    fit_predict_variant,
)
from testing.market_residual_meta_audit import EPS, iter_folds  # noqa: E402
from testing.statistical_edge_audit import binary_log_loss  # noqa: E402
from testing.striking_core_betting_calibration_audit import (  # noqa: E402
    add_bet_rows,
    attach_odds,
)
from testing.striking_feature_engineering_audit import (  # noqa: E402
    EDGE_THRESHOLD,
    add_pace_features,
    bet_table,
    build_pace_features,
    build_variants,
    fmt_float,
    fmt_p,
    fmt_pct,
    fmt_units,
    rolling_prior_probability_selection,
    rolling_prior_profit_selection,
    selection_path_table,
    summarize_bet_frame,
    summarize_prediction_frame,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_feature_engineering_selection_null_audit"


def parse_args():
    parser = argparse.ArgumentParser(description="Selection-null audit for striking feature variants")
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
    parser.add_argument("--null-iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


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
    variants = build_variants()
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
    return aligned, {**metadata, **pace_metadata, "pace_reconstruction": pace_reconstruction}, variants, folds


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
        "probability_summary": probability_summary,
        "probability_path": probability_path,
        "probability_predictions": probability_selected,
        "profit_summary": profit_summary,
        "profit_path": profit_path,
        "profit_bets": profit_selected,
    }


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


def run_selection_null(args) -> dict:
    rng = np.random.default_rng(args.seed)
    aligned, metadata, variants, folds = prepare_augmented_frame(args)
    candidate_names = [variant.name for variant in variants if variant.name != "market_recalibrated"]
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

    market = np.clip(
        aligned["red_market_probability"].astype(float).to_numpy(),
        EPS,
        1.0 - EPS,
    )
    null_rows = []
    probability_null = np.empty(args.null_iterations, dtype=float)
    profit_null = np.empty(args.null_iterations, dtype=float)
    for iteration in range(args.null_iterations):
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
            "null_iterations": args.null_iterations,
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
        "observed": {
            "probability_summary": observed["probability_summary"],
            "probability_selection_path": observed["probability_path"],
            "profit_summary": observed["profit_summary"],
            "profit_selection_path": observed["profit_path"],
        },
        "selection_null": {
            "probability_delta_log_loss": null_summary(probability_null, observed_probability),
            "profit": null_summary(profit_null, observed_profit),
        },
        "_observed_probability_predictions": observed["probability_predictions"],
        "_observed_profit_bets": observed["profit_bets"],
        "_null_rows": pd.DataFrame(null_rows),
    }


def null_table(selection_null: dict) -> list[str]:
    lines = [
        "| Selector | Observed | Null Mean | Null 95% CI | P(null >= observed) | P(null > 0) |",
        "| --- | ---: | ---: | --- | ---: | ---: |",
    ]
    probability = selection_null["probability_delta_log_loss"]
    profit = selection_null["profit"]
    lines.append(
        "| probability-delta selector | {observed} | {mean} | {ci} | {p} | {pos} |".format(
            observed=fmt_float(probability["observed"]),
            mean=fmt_float(probability["null_mean"]),
            ci=f"{fmt_float(probability['null_ci_95'][0])} to {fmt_float(probability['null_ci_95'][1])}",
            p=fmt_p(probability["p_value_observed_or_better"]),
            pos=fmt_p(probability["prob_null_positive"]),
        )
    )
    lines.append(
        "| profit selector | {observed} | {mean} | {ci} | {p} | {pos} |".format(
            observed=fmt_units(profit["observed"]),
            mean=fmt_units(profit["null_mean"]),
            ci=f"{fmt_units(profit['null_ci_95'][0])} to {fmt_units(profit['null_ci_95'][1])}",
            p=fmt_p(profit["p_value_observed_or_better"]),
            pos=fmt_p(profit["prob_null_positive"]),
        )
    )
    return lines


def probability_observed_table(summary: dict) -> list[str]:
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


def markdown_report(result: dict) -> str:
    observed = result["observed"]
    selection_null = result["selection_null"]
    probability_p = selection_null["probability_delta_log_loss"]["p_value_observed_or_better"]
    profit_p = selection_null["profit"]["p_value_observed_or_better"]
    lines = [
        "# Striking Feature Engineering Selection-Null Audit",
        "",
        "This audit reruns the rolling feature-variant selectors under",
        "market-implied outcomes. Each null iteration simulates fight outcomes",
        "from de-vigged market probabilities, refits every feature variant on the",
        "simulated labels, reruns prior-fold selection, and scores the selected",
        "next-fold result.",
        "",
        "## Protocol",
        "",
        f"- aligned men-only rows: `{result['metadata']['aligned_rows']}`",
        f"- candidate feature variants: `{len(result['candidate_names'])}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- first holdout start: `{result['parameters']['first_holdout_start']}`",
        f"- last holdout end: `{result['parameters']['last_holdout_end']}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- fixed betting threshold: `{fmt_pct(EDGE_THRESHOLD)}`",
        "- event cap: none",
        f"- selection-null iterations: `{result['parameters']['null_iterations']}`",
        "",
        "## Observed Rolling Selectors",
        "",
        *probability_observed_table(observed["probability_summary"]),
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
        *null_table(selection_null),
        "",
        "## Interpretation",
        "",
    ]
    if probability_p is not None and probability_p <= 0.05:
        lines.append("- The rolling probability selector clears the 200-path selection-null screen.")
    else:
        lines.append("- The rolling probability selector does not clear the 200-path selection-null screen.")
    if profit_p is not None and profit_p <= 0.05:
        lines.append("- The rolling profit selector clears the 200-path selection-null screen.")
    else:
        lines.append("- The rolling profit selector does not clear the 200-path selection-null screen.")
    lines.append(
        "- This is still historical evidence over a feature family designed after prior striking-core discovery; it is not a live-edge proof or a reason to alter the frozen paper policies without future validation."
    )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- `{result['outputs']['observed_probability_predictions_csv']}`",
            f"- `{result['outputs']['observed_profit_bets_csv']}`",
            f"- `{result['outputs']['selection_null_csv']}`",
            f"- `{result['outputs']['summary_json']}`",
            f"- `{result['outputs']['report_md']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run_selection_null(args)

    observed_probability_predictions = result.pop("_observed_probability_predictions")
    observed_profit_bets = result.pop("_observed_profit_bets")
    null_rows = result.pop("_null_rows")

    probability_path = output_dir / "observed_rolling_probability_predictions.csv"
    profit_path = output_dir / "observed_rolling_profit_bets.csv"
    null_path = output_dir / "selection_null_distribution.csv"
    json_path = output_dir / "striking_feature_engineering_selection_null_audit.json"
    md_path = output_dir / "striking_feature_engineering_selection_null_audit.md"

    observed_probability_predictions.to_csv(probability_path, index=False)
    observed_profit_bets.to_csv(profit_path, index=False)
    null_rows.to_csv(null_path, index=False)
    result["outputs"] = {
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
