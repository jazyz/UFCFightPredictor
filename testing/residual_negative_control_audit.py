#!/usr/bin/env python3
"""Negative controls for residual market/meta probability improvements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


EPS = 1e-12


def parse_args():
    parser = argparse.ArgumentParser(description="Residual meta negative-control audit")
    parser.add_argument(
        "--predictions",
        default="test_results/market_residual_meta_audit/holdout_meta_predictions.csv",
        help="holdout meta predictions CSV from market_residual_meta_audit.py",
    )
    parser.add_argument("--variant", default="market_plus_regularized_lgbm")
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/residual_negative_control_audit")
    return parser.parse_args()


def binary_losses(y_true: np.ndarray, probability: np.ndarray) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def log_loss(y_true: np.ndarray, probability: np.ndarray) -> float:
    return float(binary_losses(y_true, probability).mean())


def delta_log_loss(y_true: np.ndarray, market: np.ndarray, candidate: np.ndarray) -> float:
    return log_loss(y_true, market) - log_loss(y_true, candidate)


def load_predictions(path: str, variant: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["variant"] == variant].copy()
    if df.empty:
        raise SystemExit(f"No rows for variant {variant!r} in {path}")
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df.dropna(subset=["event_date", "market_probability", "meta_probability"])
    df["year"] = df["event_date"].dt.year.astype(str)
    df["residual_probability"] = df["meta_probability"].astype(float) - df["market_probability"].astype(float)
    return df.reset_index(drop=True)


def permuted_delta(
    y: np.ndarray,
    market: np.ndarray,
    residual: np.ndarray,
    rng,
    groups: np.ndarray | None = None,
) -> float:
    if groups is None:
        shuffled = rng.permutation(residual)
    else:
        shuffled = residual.copy()
        for group in np.unique(groups):
            mask = groups == group
            shuffled[mask] = rng.permutation(shuffled[mask])
    candidate = np.clip(market + shuffled, EPS, 1.0 - EPS)
    return delta_log_loss(y, market, candidate)


def permutation_test(
    y: np.ndarray,
    market: np.ndarray,
    residual: np.ndarray,
    observed_delta: float,
    iterations: int,
    rng,
    groups: np.ndarray | None = None,
) -> dict:
    deltas = np.empty(iterations, dtype=float)
    for index in range(iterations):
        deltas[index] = permuted_delta(y, market, residual, rng, groups=groups)
    return {
        "iterations": int(iterations),
        "null_mean_delta": float(np.mean(deltas)),
        "null_delta_ci_95": [float(value) for value in np.percentile(deltas, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(deltas >= observed_delta) + 1) / (iterations + 1)),
        "prob_null_positive": float(np.mean(deltas > 0.0)),
    }


def fixed_control_scores(y: np.ndarray, market: np.ndarray, meta: np.ndarray) -> dict:
    residual = meta - market
    flipped = np.clip(market - residual, EPS, 1.0 - EPS)
    attenuated_half = np.clip(market + 0.5 * residual, EPS, 1.0 - EPS)
    exaggerated = np.clip(market + 1.5 * residual, EPS, 1.0 - EPS)
    return {
        "observed": {
            "log_loss": log_loss(y, meta),
            "market_minus_candidate_log_loss": delta_log_loss(y, market, meta),
        },
        "market_only": {
            "log_loss": log_loss(y, market),
            "market_minus_candidate_log_loss": 0.0,
        },
        "flipped_residual": {
            "log_loss": log_loss(y, flipped),
            "market_minus_candidate_log_loss": delta_log_loss(y, market, flipped),
        },
        "half_residual": {
            "log_loss": log_loss(y, attenuated_half),
            "market_minus_candidate_log_loss": delta_log_loss(y, market, attenuated_half),
        },
        "one_and_half_residual": {
            "log_loss": log_loss(y, exaggerated),
            "market_minus_candidate_log_loss": delta_log_loss(y, market, exaggerated),
        },
    }


def year_scores(df: pd.DataFrame) -> list[dict]:
    rows = []
    for year, subset in df.groupby("year", sort=True):
        y = subset["red_won"].astype(float).to_numpy()
        market = subset["market_probability"].astype(float).to_numpy()
        meta = subset["meta_probability"].astype(float).to_numpy()
        rows.append(
            {
                "year": str(year),
                "fights": int(len(subset)),
                "market_log_loss": log_loss(y, market),
                "meta_log_loss": log_loss(y, meta),
                "market_minus_meta_log_loss": delta_log_loss(y, market, meta),
            }
        )
    return rows


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.3f}"


def markdown_report(result: dict) -> str:
    fixed = result["fixed_controls"]
    global_perm = result["permutation_controls"]["global"]
    fold_perm = result["permutation_controls"]["within_fold"]
    year_perm = result["permutation_controls"]["within_year"]
    lines = [
        "# Residual Negative-Control Audit",
        "",
        f"Prediction variant: `{result['variant']}`",
        f"Prediction file: `{result['prediction_path']}`",
        "",
        "This audit keeps market probabilities and outcomes fixed, then tests",
        "whether the observed residual adjustment beats deliberately broken",
        "residual adjustments.",
        "",
        "## Fixed Controls",
        "",
        "| Control | Log Loss | Market - Candidate LL |",
        "| --- | ---: | ---: |",
    ]
    for name, row in fixed.items():
        lines.append(
            f"| {name} | {fmt_float(row['log_loss'])} | {fmt_float(row['market_minus_candidate_log_loss'])} |"
        )

    lines.extend(
        [
            "",
            "## Permutation Controls",
            "",
            "`p-value` is the probability that a scrambled residual adjustment beats",
            "or matches the observed residual log-loss improvement.",
            "",
            "| Control | Null Mean Delta LL | Null 95% Interval | P-value | Prob Null Positive |",
            "| --- | ---: | --- | ---: | ---: |",
            "| global residual permutation | {mean} | {lo} to {hi} | {p} | {pos} |".format(
                mean=fmt_float(global_perm["null_mean_delta"]),
                lo=fmt_float(global_perm["null_delta_ci_95"][0]),
                hi=fmt_float(global_perm["null_delta_ci_95"][1]),
                p=fmt_p(global_perm["p_value_observed_or_better"]),
                pos=fmt_p(global_perm["prob_null_positive"]),
            ),
            "| within-fold residual permutation | {mean} | {lo} to {hi} | {p} | {pos} |".format(
                mean=fmt_float(fold_perm["null_mean_delta"]),
                lo=fmt_float(fold_perm["null_delta_ci_95"][0]),
                hi=fmt_float(fold_perm["null_delta_ci_95"][1]),
                p=fmt_p(fold_perm["p_value_observed_or_better"]),
                pos=fmt_p(fold_perm["prob_null_positive"]),
            ),
            "| within-year residual permutation | {mean} | {lo} to {hi} | {p} | {pos} |".format(
                mean=fmt_float(year_perm["null_mean_delta"]),
                lo=fmt_float(year_perm["null_delta_ci_95"][0]),
                hi=fmt_float(year_perm["null_delta_ci_95"][1]),
                p=fmt_p(year_perm["p_value_observed_or_better"]),
                pos=fmt_p(year_perm["prob_null_positive"]),
            ),
            "",
            "## Year Scores",
            "",
            "| Year | Fights | Market LL | Meta LL | Delta LL |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["year_scores"]:
        lines.append(
            "| {year} | {fights} | {market} | {meta} | {delta} |".format(
                year=row["year"],
                fights=row["fights"],
                market=fmt_float(row["market_log_loss"]),
                meta=fmt_float(row["meta_log_loss"]),
                delta=fmt_float(row["market_minus_meta_log_loss"]),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A healthy residual signal should beat sign-flipped and permuted",
            "residual controls. This audit is still conditional on the saved",
            "residual predictions; it does not replace future post-freeze evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    df = load_predictions(args.predictions, args.variant)
    y = df["red_won"].astype(float).to_numpy()
    market = df["market_probability"].astype(float).to_numpy()
    meta = df["meta_probability"].astype(float).to_numpy()
    residual = meta - market
    observed_delta = delta_log_loss(y, market, meta)

    result = {
        "variant": args.variant,
        "prediction_path": args.predictions,
        "fights": int(len(df)),
        "iterations": args.iterations,
        "seed": args.seed,
        "fixed_controls": fixed_control_scores(y, market, meta),
        "permutation_controls": {
            "global": permutation_test(y, market, residual, observed_delta, args.iterations, rng),
            "within_fold": permutation_test(
                y,
                market,
                residual,
                observed_delta,
                args.iterations,
                rng,
                groups=df["fold"].to_numpy(),
            ),
            "within_year": permutation_test(
                y,
                market,
                residual,
                observed_delta,
                args.iterations,
                rng,
                groups=df["year"].to_numpy(),
            ),
        },
        "year_scores": year_scores(df),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_negative_control_audit.json"
    md_path = output_dir / "residual_negative_control_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    print(f"Observed delta LL: {observed_delta:.4f}")
    print(
        "Within-fold permutation p-value: "
        f"{result['permutation_controls']['within_fold']['p_value_observed_or_better']:.3f}"
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
