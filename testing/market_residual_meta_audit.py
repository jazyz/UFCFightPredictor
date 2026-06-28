#!/usr/bin/env python3
"""Walk-forward audit for model residual information beyond market prices.

The audit uses saved leak-safe backtest ledgers as fixed inputs. It trains only
small logistic meta-models on prior ledger rows, then evaluates whether those
meta probabilities improve future log loss versus de-vigged market prices.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import binary_log_loss, brier_score, implied_prob, parse_odds  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


EPS = 1e-6


@dataclass(frozen=True)
class Variant:
    name: str
    feature_columns: tuple[str, ...]


@dataclass(frozen=True)
class FoldSpec:
    fold_index: int
    dev_start: pd.Timestamp
    dev_end: pd.Timestamp
    holdout_start: pd.Timestamp
    holdout_end: pd.Timestamp
    dev_indices: np.ndarray
    holdout_indices: np.ndarray


def parse_args():
    parser = argparse.ArgumentParser(description="Audit model residual log-loss edge over market")
    parser.add_argument(
        "--ledger",
        action="append",
        nargs=2,
        metavar=("LABEL", "CSV"),
        required=True,
        help="saved no_leakage_backtest.csv ledger to align by fight",
    )
    parser.add_argument("--first-holdout-start", default="2024-02-05")
    parser.add_argument("--last-holdout-end", default="2026-06-27")
    parser.add_argument("--dev-days", type=int, default=730)
    parser.add_argument("--holdout-days", type=int, default=182)
    parser.add_argument("--step-days", type=int, default=182)
    parser.add_argument("--min-dev-fights", type=int, default=200)
    parser.add_argument("--min-holdout-fights", type=int, default=60)
    parser.add_argument("--c", type=float, default=1.0, help="L2 inverse regularization for meta logistic models")
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/market_residual_meta_audit")
    return parser.parse_args()


def logit(probability) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def sigmoid(value) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(value, dtype=float)))


def fight_key(event_date, left_name, right_name) -> str:
    if pd.isna(event_date):
        event_text = ""
    else:
        event_text = pd.Timestamp(event_date).date().isoformat()
    fighters = sorted([canonical_name(left_name), canonical_name(right_name)])
    return "|".join([event_text, *fighters])


def load_ledger_rows(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    rows = []
    for _, row in df.iterrows():
        event_date = pd.to_datetime(row.get("event_date"), errors="coerce")
        red = canonical_name(row.get("red_fighter", ""))
        blue = canonical_name(row.get("blue_fighter", ""))
        winner = canonical_name(row.get("winner_name", ""))
        fighter1 = canonical_name(row.get("odds_fighter1_name", ""))
        fighter2 = canonical_name(row.get("odds_fighter2_name", ""))

        odds1 = parse_odds(row.get("fighter1_odds"))
        odds2 = parse_odds(row.get("fighter2_odds"))
        raw1 = implied_prob(odds1)
        raw2 = implied_prob(odds2)
        vig_sum = raw1 + raw2 if np.isfinite(raw1) and np.isfinite(raw2) else np.nan
        if not np.isfinite(vig_sum) or vig_sum <= 0:
            continue

        market1 = raw1 / vig_sum
        market2 = raw2 / vig_sum
        if red == fighter1:
            market_red = market1
        elif red == fighter2:
            market_red = market2
        else:
            continue

        model_red = row.get("red_win_probability")
        try:
            model_red = float(model_red)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(model_red):
            continue

        rows.append(
            {
                "fight_key": fight_key(event_date, red, blue),
                "event_date": event_date,
                "title": row.get("title", ""),
                "red_fighter": row.get("red_fighter", ""),
                "blue_fighter": row.get("blue_fighter", ""),
                "winner_name": row.get("winner_name", ""),
                "red_won": bool(winner == red),
                "red_market_probability": float(market_red),
                f"{label}_red_model_probability": float(np.clip(model_red, EPS, 1.0 - EPS)),
            }
        )

    return pd.DataFrame(rows).dropna(subset=["event_date"])


def load_aligned_ledgers(ledger_args: list[list[str]]) -> tuple[pd.DataFrame, list[str]]:
    labels = [label for label, _ in ledger_args]
    frames = []
    for label, csv_path in ledger_args:
        frame = load_ledger_rows(Path(csv_path), label)
        if frame.empty:
            raise SystemExit(f"No comparable rows loaded for {label}: {csv_path}")
        frames.append(frame)

    base_columns = [
        "fight_key",
        "event_date",
        "title",
        "red_fighter",
        "blue_fighter",
        "winner_name",
        "red_won",
        "red_market_probability",
    ]
    merged = frames[0][base_columns + [f"{labels[0]}_red_model_probability"]].copy()
    for label, frame in zip(labels[1:], frames[1:]):
        keep = ["fight_key", f"{label}_red_model_probability"]
        merged = merged.merge(frame[keep], on="fight_key", how="inner", validate="one_to_one")

    merged = merged.sort_values(["event_date", "fight_key"]).reset_index(drop=True)
    merged["market_logit"] = logit(merged["red_market_probability"])
    for label in labels:
        model_col = f"{label}_red_model_probability"
        merged[f"{label}_logit_delta"] = logit(merged[model_col]) - merged["market_logit"]
    return merged, labels


def build_variants(labels: list[str]) -> list[Variant]:
    variants = [Variant("market_recalibrated", ("market_logit",))]
    for label in labels:
        variants.append(
            Variant(
                f"market_plus_{label}",
                ("market_logit", f"{label}_logit_delta"),
            )
        )
    if len(labels) > 1:
        variants.append(
            Variant(
                "market_plus_all_models",
                tuple(["market_logit", *[f"{label}_logit_delta" for label in labels]]),
            )
        )
    return variants


def iter_folds(
    df: pd.DataFrame,
    first_holdout_start: str,
    last_holdout_end: str,
    dev_days: int,
    holdout_days: int,
    step_days: int,
    min_dev_fights: int,
    min_holdout_fights: int,
) -> list[FoldSpec]:
    event_dates = df["event_date"].to_numpy(dtype="datetime64[ns]")
    current = pd.Timestamp(first_holdout_start)
    last = pd.Timestamp(last_holdout_end)
    folds = []
    fold_index = 1
    while current <= last:
        dev_start = current - pd.Timedelta(days=dev_days)
        dev_end = current - pd.Timedelta(days=1)
        holdout_end = min(current + pd.Timedelta(days=holdout_days - 1), last)
        dev_mask = (event_dates >= np.datetime64(dev_start)) & (event_dates <= np.datetime64(dev_end))
        holdout_mask = (event_dates >= np.datetime64(current)) & (event_dates <= np.datetime64(holdout_end))
        dev_indices = np.flatnonzero(dev_mask)
        holdout_indices = np.flatnonzero(holdout_mask)
        if len(dev_indices) >= min_dev_fights and len(holdout_indices) >= min_holdout_fights:
            folds.append(
                FoldSpec(
                    fold_index=fold_index,
                    dev_start=dev_start,
                    dev_end=dev_end,
                    holdout_start=current,
                    holdout_end=holdout_end,
                    dev_indices=dev_indices,
                    holdout_indices=holdout_indices,
                )
            )
        fold_index += 1
        current += pd.Timedelta(days=step_days)
    return folds


def fit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_eval: np.ndarray,
    c_value: float,
) -> tuple[np.ndarray, dict]:
    y_train = np.asarray(y_train, dtype=int)
    if len(np.unique(y_train)) < 2:
        probability = float(np.clip(np.mean(y_train), EPS, 1.0 - EPS))
        return np.full(len(x_eval), probability), {
            "intercept": logit(probability).item(),
            "coefficients": None,
            "constant_fallback": True,
        }

    model = LogisticRegression(C=c_value, penalty="l2", solver="lbfgs", max_iter=1000)
    model.fit(x_train, y_train)
    return np.clip(model.predict_proba(x_eval)[:, 1], EPS, 1.0 - EPS), {
        "intercept": float(model.intercept_[0]),
        "coefficients": [float(value) for value in model.coef_[0]],
        "constant_fallback": False,
    }


def score_probabilities(y_true, probability) -> dict:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return {
        "fights": int(len(y)),
        "accuracy": float(np.mean((p >= 0.5) == y)) if len(y) else None,
        "log_loss": binary_log_loss(y, p) if len(y) else None,
        "brier": brier_score(y, p) if len(y) else None,
    }


def run_observed_predictions(
    df: pd.DataFrame,
    variants: list[Variant],
    folds: list[FoldSpec],
    c_value: float,
) -> tuple[pd.DataFrame, list[dict]]:
    y = df["red_won"].astype(int).to_numpy()
    market = df["red_market_probability"].astype(float).to_numpy()
    prediction_rows = []
    coefficient_rows = []

    feature_matrices = {
        variant.name: df[list(variant.feature_columns)].astype(float).to_numpy()
        for variant in variants
    }

    for fold in folds:
        for variant in variants:
            x = feature_matrices[variant.name]
            probabilities, fit_info = fit_predict(
                x[fold.dev_indices],
                y[fold.dev_indices],
                x[fold.holdout_indices],
                c_value,
            )
            coefficient_rows.append(
                {
                    "fold": fold.fold_index,
                    "variant": variant.name,
                    "intercept": fit_info["intercept"],
                    "constant_fallback": fit_info["constant_fallback"],
                    "coefficients": fit_info["coefficients"],
                    "feature_columns": list(variant.feature_columns),
                }
            )

            for row_index, probability in zip(fold.holdout_indices, probabilities):
                source = df.iloc[row_index]
                prediction_rows.append(
                    {
                        "fold": fold.fold_index,
                        "variant": variant.name,
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

    return pd.DataFrame(prediction_rows), coefficient_rows


def per_row_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def event_bootstrap_delta(predictions: pd.DataFrame, iterations: int, rng) -> dict | None:
    if predictions.empty or iterations <= 0:
        return None
    y = predictions["red_won"].astype(float).to_numpy()
    market_loss = per_row_loss(y, predictions["market_probability"].astype(float).to_numpy())
    meta_loss = per_row_loss(y, predictions["meta_probability"].astype(float).to_numpy())
    working = predictions[["event_date"]].copy()
    working["market_loss"] = market_loss
    working["meta_loss"] = meta_loss
    working["rows"] = 1
    grouped = working.groupby("event_date", sort=True)[["market_loss", "meta_loss", "rows"]].sum()
    if grouped.empty:
        return None
    market_sums = grouped["market_loss"].to_numpy(dtype=float)
    meta_sums = grouped["meta_loss"].to_numpy(dtype=float)
    counts = grouped["rows"].to_numpy(dtype=float)
    sampled = rng.integers(0, len(grouped), size=(iterations, len(grouped)))
    sampled_market = market_sums[sampled].sum(axis=1)
    sampled_meta = meta_sums[sampled].sum(axis=1)
    sampled_counts = counts[sampled].sum(axis=1)
    deltas = (sampled_market - sampled_meta) / sampled_counts
    return {
        "events": int(len(grouped)),
        "iterations": int(iterations),
        "delta_ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
        "prob_delta_le_zero": float(np.mean(deltas <= 0.0)),
    }


def summarize_coefficients(coefficient_rows: list[dict]) -> dict:
    values = defaultdict(list)
    for row in coefficient_rows:
        values[(row["variant"], "intercept")].append(row["intercept"])
        coefficients = row.get("coefficients")
        if coefficients is None:
            continue
        for feature, coefficient in zip(row["feature_columns"], coefficients):
            values[(row["variant"], feature)].append(coefficient)

    summary = {}
    for (variant, feature), entries in values.items():
        array = np.asarray(entries, dtype=float)
        summary.setdefault(variant, {})[feature] = {
            "folds": int(len(array)),
            "mean": float(np.mean(array)),
            "std": float(np.std(array)),
            "min": float(np.min(array)),
            "max": float(np.max(array)),
        }
    return summary


def aggregate_observed(
    predictions: pd.DataFrame,
    variants: list[Variant],
    coefficient_rows: list[dict],
    bootstrap_iterations: int,
    rng,
) -> dict:
    aggregate = {}
    for variant in variants:
        subset = predictions[predictions["variant"] == variant.name].copy()
        y = subset["red_won"].astype(float).to_numpy()
        market_p = subset["market_probability"].astype(float).to_numpy()
        meta_p = subset["meta_probability"].astype(float).to_numpy()
        market_score = score_probabilities(y, market_p)
        meta_score = score_probabilities(y, meta_p)
        market_loss = per_row_loss(y, market_p)
        meta_loss = per_row_loss(y, meta_p)
        fold_deltas = []
        for _, fold_subset in subset.groupby("fold", sort=True):
            fold_y = fold_subset["red_won"].astype(float).to_numpy()
            fold_delta = binary_log_loss(
                fold_y,
                fold_subset["market_probability"].astype(float).to_numpy(),
            ) - binary_log_loss(
                fold_y,
                fold_subset["meta_probability"].astype(float).to_numpy(),
            )
            fold_deltas.append(float(fold_delta))
        aggregate[variant.name] = {
            "feature_columns": list(variant.feature_columns),
            "market": market_score,
            "meta": meta_score,
            "market_minus_meta_log_loss": float(market_score["log_loss"] - meta_score["log_loss"]),
            "market_minus_meta_brier": float(market_score["brier"] - meta_score["brier"]),
            "mean_row_loss_delta": float(np.mean(market_loss - meta_loss)),
            "positive_folds": int(np.sum(np.asarray(fold_deltas) > 0.0)),
            "folds": int(len(fold_deltas)),
            "fold_log_loss_deltas": fold_deltas,
            "event_bootstrap": event_bootstrap_delta(subset, bootstrap_iterations, rng),
        }

    return {
        "variants": aggregate,
        "coefficients": summarize_coefficients(coefficient_rows),
    }


def market_null_simulation(
    df: pd.DataFrame,
    variants: list[Variant],
    folds: list[FoldSpec],
    observed: dict,
    iterations: int,
    c_value: float,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None

    y_observed = df["red_won"].astype(int).to_numpy()
    market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    feature_matrices = {
        variant.name: df[list(variant.feature_columns)].astype(float).to_numpy()
        for variant in variants
    }
    null_deltas = {variant.name: np.empty(iterations, dtype=float) for variant in variants}
    holdout_indices = np.concatenate([fold.holdout_indices for fold in folds])
    if len(holdout_indices) == 0:
        return None

    for iteration in range(iterations):
        simulated_y = (rng.random(len(df)) < market).astype(int)
        for variant in variants:
            x = feature_matrices[variant.name]
            predicted_parts = []
            y_parts = []
            market_parts = []
            for fold in folds:
                probabilities, _ = fit_predict(
                    x[fold.dev_indices],
                    simulated_y[fold.dev_indices],
                    x[fold.holdout_indices],
                    c_value,
                )
                predicted_parts.append(probabilities)
                y_parts.append(simulated_y[fold.holdout_indices])
                market_parts.append(market[fold.holdout_indices])
            y_holdout = np.concatenate(y_parts)
            p_market = np.concatenate(market_parts)
            p_meta = np.concatenate(predicted_parts)
            null_deltas[variant.name][iteration] = binary_log_loss(y_holdout, p_market) - binary_log_loss(
                y_holdout,
                p_meta,
            )

    result = {}
    for variant in variants:
        deltas = null_deltas[variant.name]
        observed_delta = observed["variants"][variant.name]["market_minus_meta_log_loss"]
        result[variant.name] = {
            "iterations": int(iterations),
            "observed_market_minus_meta_log_loss": float(observed_delta),
            "null_mean_delta": float(np.mean(deltas)),
            "null_delta_ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
            "p_value_observed_or_better": float((np.sum(deltas >= observed_delta) + 1) / (iterations + 1)),
            "prob_null_delta_positive": float(np.mean(deltas > 0.0)),
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
    lines = [
        "# Market Residual Meta Audit",
        "",
        "This audit trains only small logistic meta-models on saved leak-safe",
        "ledger probabilities. Each fold uses prior fights for meta-training and",
        "evaluates whether the meta probability beats de-vigged market probability",
        "on future log loss.",
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
            "## Protocol",
            "",
            f"- aligned fights: `{result['aligned_fights']}`",
            f"- folds: `{len(result['folds'])}`",
            f"- development window: `{result['dev_days']}` days",
            f"- holdout window: `{result['holdout_days']}` days",
            f"- logistic meta regularization C: `{result['c']}`",
            "",
            "## Results",
            "",
            "`Delta LL` is `market log loss - meta log loss`; positive means the",
            "meta-model beat the de-vigged market.",
            "",
            "| Variant | Features | Fights | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    null = result.get("market_null") or {}
    for name, summary in result["observed"]["variants"].items():
        features = ", ".join(summary["feature_columns"])
        bootstrap = summary.get("event_bootstrap") or {}
        null_summary = null.get(name) or {}
        lines.append(
            "| {name} | `{features}` | {fights} | {market_ll} | {meta_ll} | {delta} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                features=features,
                fights=summary["meta"]["fights"],
                market_ll=fmt_float(summary["market"]["log_loss"]),
                meta_ll=fmt_float(summary["meta"]["log_loss"]),
                delta=fmt_float(summary["market_minus_meta_log_loss"]),
                pos=summary["positive_folds"],
                folds=summary["folds"],
                boot=fmt_p(bootstrap.get("prob_delta_le_zero")),
                null_p=fmt_p(null_summary.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## Coefficients",
            "",
            "Positive delta-feature coefficients mean the meta-model learned to move",
            "with the saved model residual after controlling for market logit.",
            "",
            "| Variant | Feature | Mean Coef | Std | Min | Max |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for variant, features in result["observed"]["coefficients"].items():
        for feature, stats in features.items():
            lines.append(
                "| {variant} | `{feature}` | {mean} | {std} | {minv} | {maxv} |".format(
                    variant=variant,
                    feature=feature,
                    mean=fmt_float(stats["mean"]),
                    std=fmt_float(stats["std"]),
                    minv=fmt_float(stats["min"]),
                    maxv=fmt_float(stats["max"]),
                )
            )

    best_name, best = max(
        result["observed"]["variants"].items(),
        key=lambda item: item[1]["market_minus_meta_log_loss"],
    )
    variant_count = len(result["observed"]["variants"])
    best_null_p = (null.get(best_name) or {}).get("p_value_observed_or_better")
    corrected = min(1.0, best_null_p * variant_count) if best_null_p is not None else None
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"The strongest variant by holdout log-loss delta was `{best_name}` with",
            f"Delta LL `{fmt_float(best['market_minus_meta_log_loss'])}`.",
        ]
    )
    if best_null_p is not None:
        lines.append(
            f"Its market-null p-value was `{fmt_p(best_null_p)}` before and `{fmt_p(corrected)}` after a simple Bonferroni correction across `{variant_count}` variants."
        )
    lines.extend(
        [
            "",
            "This is an incremental-information test, not a betting-policy selector.",
            "It should be read alongside the disagreement and paper-tracking audits.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    df, labels = load_aligned_ledgers(args.ledger)
    variants = build_variants(labels)
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
        raise SystemExit("No folds met min-dev/min-holdout constraints")

    predictions, coefficient_rows = run_observed_predictions(df, variants, folds, args.c)
    observed = aggregate_observed(predictions, variants, coefficient_rows, args.bootstrap_iterations, rng)
    market_null = market_null_simulation(
        df,
        variants,
        folds,
        observed,
        args.market_null_iterations,
        args.c,
        rng,
    )

    result = {
        "ledgers": [{"label": label, "csv_path": csv_path} for label, csv_path in args.ledger],
        "labels": labels,
        "aligned_fights": int(len(df)),
        "first_holdout_start": args.first_holdout_start,
        "last_holdout_end": args.last_holdout_end,
        "dev_days": args.dev_days,
        "holdout_days": args.holdout_days,
        "step_days": args.step_days,
        "min_dev_fights": args.min_dev_fights,
        "min_holdout_fights": args.min_holdout_fights,
        "c": args.c,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "folds": [
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
        ],
        "observed": observed,
        "market_null": market_null,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "market_residual_meta_audit.json"
    md_path = output_dir / "market_residual_meta_audit.md"
    csv_path = output_dir / "holdout_meta_predictions.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    predictions.to_csv(csv_path, index=False)

    print(f"Aligned fights: {len(df)}")
    print(f"Folds: {len(folds)}")
    for name, summary in observed["variants"].items():
        null_summary = (market_null or {}).get(name) or {}
        print(
            f"{name}: delta LL {summary['market_minus_meta_log_loss']:.4f}, "
            f"market-null p {fmt_p(null_summary.get('p_value_observed_or_better'))}"
        )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
