#!/usr/bin/env python3
"""Nested residual-shrinkage audit for market/meta probabilities.

This tests whether the post-hoc "half residual" hint from the negative-control
audit can be selected without looking at future holdout outcomes.
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

from testing.market_residual_meta_audit import (  # noqa: E402
    EPS,
    fit_predict,
    iter_folds,
    load_aligned_ledgers,
    per_row_loss,
    score_probabilities,
)
from testing.statistical_edge_audit import binary_log_loss, brier_score  # noqa: E402


DEFAULT_LEDGERS = [
    [
        "baseline_default",
        "test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv",
    ],
    [
        "regularized_lgbm",
        "test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv",
    ],
]


def parse_shrinkages(value: str) -> list[float]:
    try:
        shrinkages = [float(part) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("shrinkages must be comma-separated floats") from exc
    if not shrinkages:
        raise argparse.ArgumentTypeError("at least one shrinkage is required")
    return sorted(set(shrinkages))


def parse_args():
    parser = argparse.ArgumentParser(description="Nested residual-shrinkage audit")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        default=None,
        help="saved no_leakage_backtest.csv ledger to align by fight",
    )
    parser.add_argument("--model-label", default="regularized_lgbm")
    parser.add_argument("--first-holdout-start", default="2024-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--inner-train-days", type=int, default=365)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=200)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--min-inner-train-fights", type=int, default=100)
    parser.add_argument("--min-selection-fights", type=int, default=60)
    parser.add_argument("--c", type=float, default=1.0, help="L2 inverse regularization for meta logistic models")
    parser.add_argument("--shrinkages", type=parse_shrinkages, default=parse_shrinkages("0,0.25,0.5,0.75,1"))
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_shrinkage_audit")
    return parser.parse_args()


def shrink_probability(market: np.ndarray, meta: np.ndarray, shrinkage: float) -> np.ndarray:
    return np.clip(market + float(shrinkage) * (meta - market), EPS, 1.0 - EPS)


def select_shrinkage(
    y_true: np.ndarray,
    market_probability: np.ndarray,
    meta_probability: np.ndarray,
    shrinkages: list[float],
) -> tuple[float, list[dict]]:
    rows = []
    for shrinkage in shrinkages:
        probability = shrink_probability(market_probability, meta_probability, shrinkage)
        rows.append(
            {
                "shrinkage": float(shrinkage),
                "log_loss": binary_log_loss(y_true, probability),
                "brier": brier_score(y_true, probability),
            }
        )
    best = min(rows, key=lambda row: (row["log_loss"], row["shrinkage"]))
    return float(best["shrinkage"]), rows


def split_inner_indices(df: pd.DataFrame, fold, inner_train_days: int) -> tuple[np.ndarray, np.ndarray]:
    dev_indices = fold.dev_indices
    dev_dates = df.iloc[dev_indices]["event_date"].to_numpy(dtype="datetime64[ns]")
    inner_end = fold.dev_start + pd.Timedelta(days=inner_train_days - 1)
    inner_mask = dev_dates <= np.datetime64(inner_end)
    inner_indices = dev_indices[inner_mask]
    selection_indices = dev_indices[~inner_mask]
    return inner_indices, selection_indices


def run_nested_pipeline(
    df: pd.DataFrame,
    folds,
    y: np.ndarray,
    model_label: str,
    c_value: float,
    shrinkages: list[float],
    inner_train_days: int,
    min_inner_train_fights: int,
    min_selection_fights: int,
    include_prediction_rows: bool = False,
) -> dict:
    feature_columns = ["market_logit", f"{model_label}_logit_delta"]
    missing = [column for column in feature_columns if column not in df.columns]
    if missing:
        raise SystemExit(f"Missing residual feature columns: {missing}")

    x = df[feature_columns].astype(float).to_numpy()
    market = df["red_market_probability"].astype(float).to_numpy()
    all_holdout_indices = []
    market_parts = []
    y_parts = []
    meta_parts = []
    selected_parts = []
    half_parts = []
    fold_rows = []
    selection_rows = []
    prediction_rows = []

    for fold in folds:
        inner_indices, selection_indices = split_inner_indices(df, fold, inner_train_days)
        skip_reason = None
        if len(inner_indices) < min_inner_train_fights:
            skip_reason = f"only {len(inner_indices)} inner-train fights"
        elif len(selection_indices) < min_selection_fights:
            skip_reason = f"only {len(selection_indices)} selection fights"

        if skip_reason:
            fold_rows.append(
                {
                    "fold": fold.fold_index,
                    "skipped": True,
                    "skip_reason": skip_reason,
                    "inner_train_fights": int(len(inner_indices)),
                    "selection_fights": int(len(selection_indices)),
                    "holdout_fights": int(len(fold.holdout_indices)),
                }
            )
            continue

        selection_meta, selection_fit = fit_predict(
            x[inner_indices],
            y[inner_indices],
            x[selection_indices],
            c_value,
        )
        selected_shrinkage, shrinkage_scores = select_shrinkage(
            y[selection_indices],
            market[selection_indices],
            selection_meta,
            shrinkages,
        )
        for row in shrinkage_scores:
            selection_rows.append(
                {
                    "fold": fold.fold_index,
                    "shrinkage": row["shrinkage"],
                    "selection_log_loss": row["log_loss"],
                    "selection_brier": row["brier"],
                }
            )

        holdout_meta, full_fit = fit_predict(
            x[fold.dev_indices],
            y[fold.dev_indices],
            x[fold.holdout_indices],
            c_value,
        )
        holdout_market = market[fold.holdout_indices]
        selected_probability = shrink_probability(holdout_market, holdout_meta, selected_shrinkage)
        half_probability = shrink_probability(holdout_market, holdout_meta, 0.5)
        holdout_y = y[fold.holdout_indices]

        all_holdout_indices.append(fold.holdout_indices)
        market_parts.append(holdout_market)
        y_parts.append(holdout_y)
        meta_parts.append(holdout_meta)
        selected_parts.append(selected_probability)
        half_parts.append(half_probability)

        fold_rows.append(
            {
                "fold": fold.fold_index,
                "skipped": False,
                "dev_start": fold.dev_start.date().isoformat(),
                "dev_end": fold.dev_end.date().isoformat(),
                "holdout_start": fold.holdout_start.date().isoformat(),
                "holdout_end": fold.holdout_end.date().isoformat(),
                "dev_fights": int(len(fold.dev_indices)),
                "inner_train_fights": int(len(inner_indices)),
                "selection_fights": int(len(selection_indices)),
                "holdout_fights": int(len(fold.holdout_indices)),
                "selected_shrinkage": float(selected_shrinkage),
                "selection_best_log_loss": min(row["log_loss"] for row in shrinkage_scores),
                "selection_market_log_loss": next(
                    row["log_loss"] for row in shrinkage_scores if row["shrinkage"] == 0.0
                ),
                "selection_unshrunk_log_loss": next(
                    (row["log_loss"] for row in shrinkage_scores if row["shrinkage"] == 1.0),
                    None,
                ),
                "holdout_market_log_loss": binary_log_loss(holdout_y, holdout_market),
                "holdout_selected_log_loss": binary_log_loss(holdout_y, selected_probability),
                "holdout_half_log_loss": binary_log_loss(holdout_y, half_probability),
                "holdout_unshrunk_log_loss": binary_log_loss(holdout_y, holdout_meta),
                "inner_fit": selection_fit,
                "full_fit": full_fit,
            }
        )

        if include_prediction_rows:
            for row_index, meta_p, selected_p, half_p in zip(
                fold.holdout_indices,
                holdout_meta,
                selected_probability,
                half_probability,
            ):
                source = df.iloc[row_index]
                prediction_rows.append(
                    {
                        "fold": fold.fold_index,
                        "event_date": source["event_date"].date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "winner_name": source["winner_name"],
                        "red_won": bool(y[row_index]),
                        "market_probability": float(market[row_index]),
                        "full_meta_probability": float(meta_p),
                        "selected_shrinkage": float(selected_shrinkage),
                        "selected_probability": float(selected_p),
                        "fixed_half_probability": float(half_p),
                        "unshrunk_probability": float(meta_p),
                    }
                )

    if not all_holdout_indices:
        raise SystemExit("No folds had enough inner-train and selection fights")

    return {
        "holdout_indices": np.concatenate(all_holdout_indices),
        "y": np.concatenate(y_parts),
        "market": np.concatenate(market_parts),
        "unshrunk": np.concatenate(meta_parts),
        "selected": np.concatenate(selected_parts),
        "fixed_half": np.concatenate(half_parts),
        "folds": fold_rows,
        "selection_scores": selection_rows,
        "prediction_rows": prediction_rows,
        "feature_columns": feature_columns,
    }


def event_bootstrap_delta(
    event_dates: np.ndarray,
    y_true: np.ndarray,
    market_probability: np.ndarray,
    candidate_probability: np.ndarray,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0 or len(y_true) == 0:
        return None
    working = pd.DataFrame(
        {
            "event_date": event_dates,
            "market_loss": per_row_loss(y_true, market_probability),
            "candidate_loss": per_row_loss(y_true, candidate_probability),
            "rows": 1,
        }
    )
    grouped = working.groupby("event_date", sort=True)[["market_loss", "candidate_loss", "rows"]].sum()
    if grouped.empty:
        return None
    market_sums = grouped["market_loss"].to_numpy(dtype=float)
    candidate_sums = grouped["candidate_loss"].to_numpy(dtype=float)
    counts = grouped["rows"].to_numpy(dtype=float)
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    deltas = (market_sums[sampled].sum(axis=1) - candidate_sums[sampled].sum(axis=1)) / counts[
        sampled
    ].sum(axis=1)
    return {
        "events": int(len(grouped)),
        "iterations": int(iterations),
        "delta_ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
        "prob_delta_le_zero": float(np.mean(deltas <= 0.0)),
    }


def summarize_pipeline(pipeline: dict, df: pd.DataFrame, bootstrap_iterations: int, rng) -> dict:
    y = pipeline["y"]
    market = pipeline["market"]
    event_dates = df.iloc[pipeline["holdout_indices"]]["event_date"].dt.date.astype(str).to_numpy()
    policies = {
        "market": market,
        "selected_shrinkage": pipeline["selected"],
        "fixed_half_residual": pipeline["fixed_half"],
        "unshrunk_meta": pipeline["unshrunk"],
    }
    market_score = score_probabilities(y, market)
    rows = {}
    for name, probability in policies.items():
        score = score_probabilities(y, probability)
        fold_deltas = []
        for fold in pipeline["folds"]:
            if fold.get("skipped"):
                continue
            fold_predictions = [
                row for row in pipeline["prediction_rows"] if row.get("fold") == fold["fold"]
            ]
            if not fold_predictions:
                continue
            fold_df = pd.DataFrame(fold_predictions)
            fold_y = fold_df["red_won"].astype(float).to_numpy()
            fold_market = fold_df["market_probability"].astype(float).to_numpy()
            column = {
                "selected_shrinkage": "selected_probability",
                "fixed_half_residual": "fixed_half_probability",
                "unshrunk_meta": "unshrunk_probability",
                "market": "market_probability",
            }[name]
            fold_p = fold_df[column].astype(float).to_numpy()
            fold_deltas.append(binary_log_loss(fold_y, fold_market) - binary_log_loss(fold_y, fold_p))

        rows[name] = {
            **score,
            "market_minus_candidate_log_loss": float(market_score["log_loss"] - score["log_loss"]),
            "market_minus_candidate_brier": float(market_score["brier"] - score["brier"]),
            "positive_folds": int(np.sum(np.asarray(fold_deltas) > 0.0)),
            "folds": int(len(fold_deltas)),
            "fold_log_loss_deltas": [float(value) for value in fold_deltas],
            "event_bootstrap": None
            if name == "market"
            else event_bootstrap_delta(event_dates, y, market, probability, bootstrap_iterations, rng),
        }
    return rows


def market_null_simulation(
    df: pd.DataFrame,
    folds,
    observed_summary: dict,
    model_label: str,
    c_value: float,
    shrinkages: list[float],
    inner_train_days: int,
    min_inner_train_fights: int,
    min_selection_fights: int,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    policy_names = ["selected_shrinkage", "fixed_half_residual", "unshrunk_meta"]
    deltas = {name: np.empty(iterations, dtype=float) for name in policy_names}
    selected_shrinkage_counts = {str(shrinkage): 0 for shrinkage in shrinkages}

    for iteration in range(iterations):
        simulated_y = (rng.random(len(df)) < market).astype(int)
        pipeline = run_nested_pipeline(
            df,
            folds,
            simulated_y,
            model_label,
            c_value,
            shrinkages,
            inner_train_days,
            min_inner_train_fights,
            min_selection_fights,
            include_prediction_rows=False,
        )
        y_holdout = pipeline["y"]
        market_holdout = pipeline["market"]
        for name, probability in [
            ("selected_shrinkage", pipeline["selected"]),
            ("fixed_half_residual", pipeline["fixed_half"]),
            ("unshrunk_meta", pipeline["unshrunk"]),
        ]:
            deltas[name][iteration] = binary_log_loss(y_holdout, market_holdout) - binary_log_loss(
                y_holdout,
                probability,
            )
        for fold in pipeline["folds"]:
            if not fold.get("skipped"):
                selected_shrinkage_counts[str(fold["selected_shrinkage"])] += 1

    result = {}
    for name in policy_names:
        observed_delta = observed_summary[name]["market_minus_candidate_log_loss"]
        values = deltas[name]
        result[name] = {
            "iterations": int(iterations),
            "observed_market_minus_candidate_log_loss": float(observed_delta),
            "null_mean_delta": float(np.mean(values)),
            "null_delta_ci_95": [float(value) for value in np.percentile(values, [2.5, 97.5])],
            "p_value_observed_or_better": float((np.sum(values >= observed_delta) + 1) / (iterations + 1)),
            "prob_null_delta_positive": float(np.mean(values > 0.0)),
        }
    total_selections = sum(selected_shrinkage_counts.values())
    result["selected_shrinkage_frequency"] = {
        shrinkage: (count / total_selections if total_selections else 0.0)
        for shrinkage, count in selected_shrinkage_counts.items()
    }
    return result


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.3f}"


def markdown_report(result: dict) -> str:
    null = result.get("market_null") or {}
    lines = [
        "# Residual Shrinkage Audit",
        "",
        "This audit asks whether residual shrinkage can be chosen without looking",
        "at future holdout outcomes. Each outer fold first fits the residual meta",
        "model on the first part of the development window, selects a shrinkage",
        "on the later development slice, refits on the full development window,",
        "then evaluates the frozen shrinkage on the future holdout.",
        "",
        "## Protocol",
        "",
        f"- model residual label: `{result['model_label']}`",
        f"- feature columns: `{', '.join(result['feature_columns'])}`",
        f"- aligned fights: `{result['aligned_fights']}`",
        f"- evaluated holdout fights: `{result['holdout_fights']}`",
        f"- outer folds evaluated: `{result['folds_evaluated']}`",
        f"- development window: `{result['dev_days']}` days",
        f"- inner train window: `{result['inner_train_days']}` days",
        f"- holdout window: `{result['holdout_days']}` days",
        f"- shrinkage grid: `{', '.join(str(value) for value in result['shrinkages'])}`",
        f"- logistic meta C: `{result['c']}`",
        "",
        "## Results",
        "",
        "`Delta LL` is `market log loss - candidate log loss`; positive means the",
        "candidate beat the de-vigged market.",
        "",
        "| Policy | Fights | Log Loss | Brier | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in result["summary"].items():
        bootstrap = summary.get("event_bootstrap") or {}
        null_summary = null.get(name) or {}
        lines.append(
            "| {name} | {fights} | {ll} | {brier} | {delta} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                fights=summary["fights"],
                ll=fmt_float(summary["log_loss"]),
                brier=fmt_float(summary["brier"]),
                delta=fmt_float(summary["market_minus_candidate_log_loss"]),
                pos=summary["positive_folds"],
                folds=summary["folds"],
                boot=fmt_p(bootstrap.get("prob_delta_le_zero")),
                null_p=fmt_p(null_summary.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Fold Selection",
            "",
            "| Fold | Holdout | Inner Train | Selection | Selected Shrinkage | Selection Best LL | Holdout Delta LL |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for fold in result["folds"]:
        if fold.get("skipped"):
            continue
        delta = fold["holdout_market_log_loss"] - fold["holdout_selected_log_loss"]
        lines.append(
            "| {fold} | {start} to {end} | {inner} | {selection} | {shrinkage} | {selection_ll} | {delta} |".format(
                fold=fold["fold"],
                start=fold["holdout_start"],
                end=fold["holdout_end"],
                inner=fold["inner_train_fights"],
                selection=fold["selection_fights"],
                shrinkage=fmt_float(fold["selected_shrinkage"], digits=2),
                selection_ll=fmt_float(fold["selection_best_log_loss"]),
                delta=fmt_float(delta),
            )
        )

    if null.get("selected_shrinkage_frequency"):
        lines.extend(["", "## Market-Null Selection Frequency", "", "| Shrinkage | Frequency |", "| ---: | ---: |"])
        for shrinkage, frequency in null["selected_shrinkage_frequency"].items():
            lines.append(f"| {shrinkage} | {fmt_p(frequency)} |")

    selected = result["summary"]["selected_shrinkage"]
    unshrunk = result["summary"]["unshrunk_meta"]
    half = result["summary"]["fixed_half_residual"]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The nested selected-shrinkage policy is the least post-hoc version of",
            "this test. Fixed half residual is shown as a sensitivity because the",
            "negative-control audit hinted at it, but it was not selected by this",
            "audit protocol.",
            "",
            f"Selected shrinkage Delta LL: `{fmt_float(selected['market_minus_candidate_log_loss'])}`.",
            f"Fixed half-residual Delta LL: `{fmt_float(half['market_minus_candidate_log_loss'])}`.",
            f"Unshrunk residual-meta Delta LL: `{fmt_float(unshrunk['market_minus_candidate_log_loss'])}`.",
            "",
            "Do not treat this as a betting edge by itself; it is a probability",
            "translation audit that should feed the forward paper-policy evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    ledger_args = args.ledger or DEFAULT_LEDGERS
    df, labels = load_aligned_ledgers(ledger_args)
    if args.model_label not in labels:
        raise SystemExit(f"model-label {args.model_label!r} not present in ledgers {labels}")

    folds = iter_folds(
        df,
        args.first_holdout_start,
        args.last_holdout_end,
        args.dev_days,
        args.holdout_days,
        args.step_days,
        args.min_dev_fights,
        args.min_holdout_fights,
    )
    if not folds:
        raise SystemExit("No outer folds generated")

    y = df["red_won"].astype(int).to_numpy()
    pipeline = run_nested_pipeline(
        df,
        folds,
        y,
        args.model_label,
        args.c,
        args.shrinkages,
        args.inner_train_days,
        args.min_inner_train_fights,
        args.min_selection_fights,
        include_prediction_rows=True,
    )
    summary = summarize_pipeline(pipeline, df, args.bootstrap_iterations, rng)
    market_null = market_null_simulation(
        df,
        folds,
        summary,
        args.model_label,
        args.c,
        args.shrinkages,
        args.inner_train_days,
        args.min_inner_train_fights,
        args.min_selection_fights,
        args.market_null_iterations,
        rng,
    )

    result = {
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in ledger_args],
        "model_label": args.model_label,
        "feature_columns": pipeline["feature_columns"],
        "aligned_fights": int(len(df)),
        "holdout_fights": int(len(pipeline["y"])),
        "folds_generated": int(len(folds)),
        "folds_evaluated": int(sum(1 for fold in pipeline["folds"] if not fold.get("skipped"))),
        "dev_days": args.dev_days,
        "inner_train_days": args.inner_train_days,
        "holdout_days": args.holdout_days,
        "step_days": args.step_days,
        "c": args.c,
        "shrinkages": args.shrinkages,
        "seed": args.seed,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "summary": summary,
        "folds": pipeline["folds"],
        "selection_scores": pipeline["selection_scores"],
        "market_null": market_null,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_shrinkage_audit.json"
    md_path = output_dir / "residual_shrinkage_audit.md"
    summary_path = output_dir / "RESIDUAL_SHRINKAGE_AUDIT_SUMMARY.md"
    predictions_path = output_dir / "holdout_shrinkage_predictions.csv"
    selection_path = output_dir / "selection_scores.csv"

    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    report = markdown_report(result)
    md_path.write_text(report)
    summary_path.write_text(report)
    pd.DataFrame(pipeline["prediction_rows"]).to_csv(predictions_path, index=False)
    pd.DataFrame(pipeline["selection_scores"]).to_csv(selection_path, index=False)

    selected = summary["selected_shrinkage"]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {predictions_path}")
    print(
        "Selected shrinkage Delta LL: "
        f"{selected['market_minus_candidate_log_loss']:.6f}; "
        f"LL={selected['log_loss']:.6f}"
    )


if __name__ == "__main__":
    main()
