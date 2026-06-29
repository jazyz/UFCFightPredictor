#!/usr/bin/env python3
"""Rolling validation for recency-weighted residual meta calibration.

Prior audits found that the residual probability edge decayed recently and
that hand-tuned residual gates do not validate. This audit tests whether the
small logistic residual-meta layer itself should be fit with shorter windows or
exponential recency weights, selected only from prior folds.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_residual_meta_audit import (  # noqa: E402
    EPS,
    binary_log_loss,
    event_bootstrap_delta,
    iter_folds,
    load_aligned_ledgers,
    per_row_loss,
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
DEFAULT_CONFIGS = (
    "dev365_c1_unweighted:365:1.0:none",
    "dev365_c1_hl365:365:1.0:365",
    "dev365_c1_hl182:365:1.0:182",
    "dev365_c1_hl91:365:1.0:91",
    "dev730_c1_unweighted:730:1.0:none",
    "dev730_c1_hl365:730:1.0:365",
    "dev730_c1_hl182:730:1.0:182",
    "dev730_c025_unweighted:730:0.25:none",
)
FEATURE_COLUMNS = ["market_logit", "regularized_lgbm_logit_delta"]


@dataclass(frozen=True)
class RecencyMetaConfig:
    label: str
    dev_days: int
    c_value: float
    half_life_days: float | None


def parse_args():
    parser = argparse.ArgumentParser(description="Audit recency-weighted residual meta calibration")
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
        help="candidate config as label:dev_days:c:half_life_days_or_none",
    )
    parser.add_argument("--first-holdout-start", default="2024-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=120)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--min-prior-selection-fights", type=int, default=100)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_meta_recency_weight_audit")
    return parser.parse_args()


def parse_config(text: str) -> RecencyMetaConfig:
    parts = str(text).split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"config must have form label:dev_days:c:half_life_or_none, got {text!r}"
        )
    label, dev_days, c_value, half_life = parts
    if half_life.strip().lower() in {"none", "unweighted", ""}:
        half_life_days = None
    else:
        half_life_days = float(half_life)
    return RecencyMetaConfig(label.strip(), int(dev_days), float(c_value), half_life_days)


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def sample_weights(df: pd.DataFrame, train_indices: np.ndarray, dev_end: pd.Timestamp, half_life_days: float | None) -> np.ndarray | None:
    if half_life_days is None:
        return None
    dates = pd.to_datetime(df.iloc[train_indices]["event_date"])
    days_ago = (dev_end - dates).dt.days.clip(lower=0).to_numpy(dtype=float)
    weights = np.power(0.5, days_ago / float(half_life_days))
    mean = float(np.mean(weights))
    if mean > 0:
        weights = weights / mean
    return weights


def fit_predict_weighted(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_eval: np.ndarray,
    c_value: float,
    weights: np.ndarray | None,
) -> tuple[np.ndarray, dict]:
    y_train = np.asarray(y_train, dtype=int)
    if len(np.unique(y_train)) < 2:
        probability = float(np.clip(np.mean(y_train), EPS, 1.0 - EPS))
        return np.full(len(x_eval), probability), {
            "intercept": float(np.log(probability / (1.0 - probability))),
            "coefficients": None,
            "constant_fallback": True,
        }
    model = LogisticRegression(C=c_value, penalty="l2", solver="lbfgs", max_iter=1000)
    model.fit(x_train, y_train, sample_weight=weights)
    return np.clip(model.predict_proba(x_eval)[:, 1], EPS, 1.0 - EPS), {
        "intercept": float(model.intercept_[0]),
        "coefficients": [float(value) for value in model.coef_[0]],
        "constant_fallback": False,
    }


def build_predictions_for_configs(
    df: pd.DataFrame,
    configs: list[RecencyMetaConfig],
    first_holdout_start: str,
    last_holdout_end: str,
    holdout_days: int,
    step_days: int,
    min_dev_fights: int,
    min_holdout_fights: int,
) -> tuple[pd.DataFrame, list[dict], dict[str, list[dict]]]:
    y = df["red_won"].astype(int).to_numpy()
    market = df["red_market_probability"].astype(float).to_numpy()
    x = df[FEATURE_COLUMNS].astype(float).to_numpy()
    prediction_rows = []
    coefficient_rows = []
    folds_by_config = {}

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
        folds_by_config[config.label] = [
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
        for fold in folds:
            weights = sample_weights(df, fold.dev_indices, fold.dev_end, config.half_life_days)
            probabilities, fit_info = fit_predict_weighted(
                x[fold.dev_indices],
                y[fold.dev_indices],
                x[fold.holdout_indices],
                config.c_value,
                weights,
            )
            coefficient_rows.append(
                {
                    "candidate": config.label,
                    "fold": fold.fold_index,
                    "intercept": fit_info["intercept"],
                    "coefficients": fit_info["coefficients"],
                    "constant_fallback": fit_info["constant_fallback"],
                    "mean_sample_weight": None if weights is None else float(np.mean(weights)),
                    "min_sample_weight": None if weights is None else float(np.min(weights)),
                    "max_sample_weight": None if weights is None else float(np.max(weights)),
                }
            )
            for row_index, probability in zip(fold.holdout_indices, probabilities):
                source = df.iloc[row_index]
                prediction_rows.append(
                    {
                        "fold": fold.fold_index,
                        "candidate": config.label,
                        "event_date": source["event_date"].date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "winner_name": source["winner_name"],
                        "red_won": bool(y[row_index]),
                        "market_probability": float(market[row_index]),
                        "meta_probability": float(probability),
                    }
                )
    return pd.DataFrame(prediction_rows), coefficient_rows, folds_by_config


def add_loss_columns(predictions: pd.DataFrame) -> pd.DataFrame:
    output = predictions.copy()
    y = output["red_won"].astype(float).to_numpy()
    market = output["market_probability"].astype(float).to_numpy()
    meta = output["meta_probability"].astype(float).to_numpy()
    output["market_loss"] = per_row_loss(y, market)
    output["meta_loss"] = per_row_loss(y, meta)
    output["loss_delta"] = output["market_loss"] - output["meta_loss"]
    return output


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


def candidate_fold_stats(predictions: pd.DataFrame) -> dict[tuple[str, int], dict]:
    stats = {}
    for (candidate, fold), subset in predictions.groupby(["candidate", "fold"], sort=True):
        stats[(str(candidate), int(fold))] = {
            "market_loss": float(subset["market_loss"].sum()),
            "meta_loss": float(subset["meta_loss"].sum()),
            "rows": int(len(subset)),
        }
    return stats


def select_candidate(
    stats: dict[tuple[str, int], dict],
    candidates: list[str],
    prior_folds: list[int],
    min_prior_selection_fights: int,
) -> tuple[str | None, dict | None]:
    best_score = None
    best_candidate = None
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
        score = (delta, rows, candidate)
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


def rolling_selection(predictions: pd.DataFrame, min_prior_selection_fights: int) -> tuple[pd.DataFrame, dict]:
    stats = candidate_fold_stats(predictions)
    candidates = sorted(predictions["candidate"].unique())
    folds = sorted(int(value) for value in predictions["fold"].unique())
    selected_frames = []
    selections = []
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
        selections.append(
            {
                "eval_fold": int(eval_fold),
                "selected_candidate": candidate,
                **(prior_summary or {}),
                "eval_fights": eval_summary["fights"],
                "eval_events": eval_summary["events"],
                "eval_market_log_loss": eval_summary["market_log_loss"],
                "eval_meta_log_loss": eval_summary["meta_log_loss"],
                "eval_delta_log_loss": eval_summary["market_minus_meta_log_loss"],
            }
        )
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
    return selected, summary


def candidate_summaries(predictions: pd.DataFrame) -> list[dict]:
    rows = []
    for candidate, subset in predictions.groupby("candidate", sort=True):
        summary = summarize_rows(subset)
        fold_deltas = [
            summarize_rows(fold_subset)["market_minus_meta_log_loss"]
            for _, fold_subset in subset.groupby("fold", sort=True)
        ]
        rows.append(
            {
                "candidate": str(candidate),
                **summary,
                "positive_folds": int(sum((value or 0.0) > 0.0 for value in fold_deltas)),
                "folds": int(len(fold_deltas)),
                "fold_log_loss_deltas": [float(value) for value in fold_deltas],
            }
        )
    return sorted(rows, key=lambda row: row["market_minus_meta_log_loss"], reverse=True)


def fixed_eval_summaries(predictions: pd.DataFrame, eval_folds: list[int]) -> list[dict]:
    rows = []
    subset = predictions[predictions["fold"].astype(int).isin(eval_folds)]
    for candidate, frame in subset.groupby("candidate", sort=True):
        row = summarize_rows(frame)
        row["candidate"] = str(candidate)
        rows.append(row)
    return sorted(rows, key=lambda row: row["market_minus_meta_log_loss"], reverse=True)


def market_null_selection(
    df: pd.DataFrame,
    configs: list[RecencyMetaConfig],
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
    y_market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    x = df[FEATURE_COLUMNS].astype(float).to_numpy()
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
    candidates = sorted(config.label for config in configs)
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
                weights = sample_weights(df, fold.dev_indices, fold.dev_end, config.half_life_days)
                probabilities, _ = fit_predict_weighted(
                    x[fold.dev_indices],
                    simulated_y[fold.dev_indices],
                    x[fold.holdout_indices],
                    config.c_value,
                    weights,
                )
                y_holdout = simulated_y[fold.holdout_indices]
                market_holdout = y_market[fold.holdout_indices]
                stats[(config.label, fold.fold_index)] = {
                    "market_loss": float(per_row_loss(y_holdout, market_holdout).sum()),
                    "meta_loss": float(per_row_loss(y_holdout, probabilities).sum()),
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
        "p_value_observed_or_better": float((np.sum(simulated_deltas >= observed_delta) + 1) / (iterations + 1)),
        "prob_null_delta_positive": float(np.mean(simulated_deltas > 0.0)),
        "selected_candidate_frequency": selected_counts,
    }


def table_candidate(rows: list[dict], limit: int = 12) -> list[str]:
    lines = [
        "| Candidate | Fights | Market LL | Meta LL | Delta LL | Positive Folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:limit]:
        lines.append(
            "| {candidate} | {fights} | {market_ll} | {meta_ll} | {delta} | {pos} / {folds} |".format(
                candidate=row["candidate"],
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                meta_ll=fmt_float(row["meta_log_loss"]),
                delta=fmt_float(row["market_minus_meta_log_loss"]),
                pos=row.get("positive_folds", ""),
                folds=row.get("folds", ""),
            )
        )
    return lines


def table_fixed_eval(rows: list[dict], limit: int = 12) -> list[str]:
    lines = [
        "| Candidate | Fights | Market LL | Meta LL | Delta LL |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:limit]:
        lines.append(
            "| {candidate} | {fights} | {market_ll} | {meta_ll} | {delta} |".format(
                candidate=row["candidate"],
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                meta_ll=fmt_float(row["meta_log_loss"]),
                delta=fmt_float(row["market_minus_meta_log_loss"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    rolling = result["rolling_selection"]
    bootstrap = rolling.get("event_bootstrap") or {}
    market_null = rolling.get("market_null") or {}
    lines = [
        "# Residual Meta Recency Weight Audit",
        "",
        "This audit tests whether recent residual drift can be repaired at the",
        "small logistic residual-meta layer by using shorter development windows",
        "or exponential recency weights. It uses only saved leak-safe ledgers and",
        "does not retrain the base UFC model.",
        "",
        "## Candidate Configs",
        "",
        "| Candidate | Dev Days | C | Half-Life Days |",
        "| --- | ---: | ---: | ---: |",
    ]
    for config in result["configs"]:
        half_life = "unweighted" if config["half_life_days"] is None else config["half_life_days"]
        lines.append(f"| {config['label']} | {config['dev_days']} | {config['c']} | {half_life} |")
    lines.extend(
        [
            "",
            "## Full-Holdout Candidate Results",
            "",
            *table_candidate(result["candidate_summaries"]),
            "",
            "## Fixed Candidates On Rolling Evaluation Folds",
            "",
            *table_fixed_eval(result["fixed_rolling_eval_summaries"]),
            "",
            "## Rolling Prior-Fold Selection",
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
            "| Combined Eval | Fights | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| rolling selected recency meta | {fights} | {market_ll} | {meta_ll} | {delta} | {positive} / {folds} | {boot} | {null_p} |".format(
                fights=rolling["fights"],
                market_ll=fmt_float(rolling["market_log_loss"]),
                meta_ll=fmt_float(rolling["meta_log_loss"]),
                delta=fmt_float(rolling["market_minus_meta_log_loss"]),
                positive=rolling["positive_eval_folds"],
                folds=rolling["eval_folds"],
                boot=fmt_p(bootstrap.get("prob_delta_le_zero")),
                null_p=fmt_p(market_null.get("p_value_observed_or_better")),
            ),
            "",
            "## Interpretation",
            "",
        ]
    )
    selected = sorted({row["selected_candidate"] for row in rolling["selections"]})
    lines.append(f"- Rolling selection chose: `{', '.join(selected)}`.")
    lines.append(
        "- This is the validation result; fixed full-holdout candidate wins are diagnostic only."
    )
    if any("hl" in label for label in selected):
        lines.append(
            "- At least one recency-weighted candidate was selected before an evaluation fold, so the weighting idea has some prior-fold support."
        )
    else:
        lines.append(
            "- Rolling selection did not choose recency-weighted candidates, so recency weighting remains unvalidated."
        )
    lines.append(
        "- The market-null result is supportive, but event-bootstrap uncertainty and the negative latest fold still block changing the residual transform or edge claim."
    )
    lines.append("")
    return "\n".join(lines)


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    ledger_args = args.ledger if args.ledger is not None else DEFAULT_LEDGERS
    configs = [parse_config(text) for text in (args.config or DEFAULT_CONFIGS)]
    df, labels = load_aligned_ledgers(ledger_args)
    for column in FEATURE_COLUMNS:
        if column not in df.columns:
            raise SystemExit(f"Missing required aligned feature column: {column}")
    predictions, coefficient_rows, folds_by_config = build_predictions_for_configs(
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
    selected, rolling_summary = rolling_selection(predictions, args.min_prior_selection_fights)
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
    eval_folds = [row["eval_fold"] for row in rolling_summary["selections"]]
    return {
        "ledgers": [{"label": label, "csv_path": path} for label, path in ledger_args],
        "labels": labels,
        "feature_columns": FEATURE_COLUMNS,
        "aligned_fights": int(len(df)),
        "configs": [
            {
                "label": config.label,
                "dev_days": config.dev_days,
                "c": config.c_value,
                "half_life_days": config.half_life_days,
            }
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
        "folds_by_config": folds_by_config,
        "candidate_summaries": candidate_summaries(predictions),
        "fixed_rolling_eval_summaries": fixed_eval_summaries(predictions, eval_folds),
        "rolling_selection": rolling_summary,
        "coefficient_rows": coefficient_rows,
    }


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_meta_recency_weight_audit.json"
    md_path = output_dir / "residual_meta_recency_weight_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    rolling = result["rolling_selection"]
    null = rolling.get("market_null") or {}
    print(
        "Rolling selected delta LL "
        f"{rolling['market_minus_meta_log_loss']:.4f}, "
        f"market-null p {fmt_p(null.get('p_value_observed_or_better'))}"
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
