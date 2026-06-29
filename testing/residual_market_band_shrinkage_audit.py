#!/usr/bin/env python3
"""Rolling validation for market-band residual shrinkage transforms.

The feature-drift audit found recent residual damage concentrated in
favorite-ish market bands and positive residual adjustments. This audit tests
whether simple predeclared shrinkage transforms can be selected using only
prior folds and then improve future log loss.
"""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
EPS = 1e-6


def parse_args():
    parser = argparse.ArgumentParser(description="Audit rolling market-band residual shrinkage")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--scales", default="0,0.25,0.5,0.75,1")
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_market_band_shrinkage_audit")
    return parser.parse_args()


def parse_scales(value: str) -> list[float]:
    scales = []
    for token in value.split(","):
        token = token.strip()
        if token:
            scales.append(float(token))
    if not scales:
        raise ValueError("at least one scale is required")
    return sorted(set(scales))


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def logit(probability) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def sigmoid(value) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(value, dtype=float)))


def binary_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def scale_label(value: float) -> str:
    return f"{value:g}"


def make_scaled_probability(
    market_probability: np.ndarray,
    selected_probability: np.ndarray,
    condition: np.ndarray,
    scale: float,
) -> np.ndarray:
    market_logit = logit(market_probability)
    selected_logit = logit(selected_probability)
    residual_delta = selected_logit - market_logit
    scales = np.where(condition, scale, 1.0)
    return sigmoid(market_logit + scales * residual_delta)


def add_candidate(
    candidates: OrderedDict[str, np.ndarray],
    descriptions: dict[str, str],
    label: str,
    probability: np.ndarray,
    description: str,
) -> None:
    if label in candidates:
        return
    candidates[label] = probability
    descriptions[label] = description


def candidate_probabilities(df: pd.DataFrame, scales: list[float]) -> tuple[OrderedDict[str, np.ndarray], dict[str, str]]:
    market = df["market_probability"].astype(float).to_numpy()
    selected = df["selected_probability"].astype(float).to_numpy()
    fixed_half = df["fixed_half_probability"].astype(float).to_numpy()
    residual_delta = logit(selected) - logit(market)
    probability_adjustment = selected - market

    candidates: OrderedDict[str, np.ndarray] = OrderedDict()
    descriptions: dict[str, str] = {}
    add_candidate(candidates, descriptions, "market", market, "de-vigged market probability")
    add_candidate(candidates, descriptions, "selected_shrinkage", selected, "existing nested selected-shrinkage probability")
    add_candidate(candidates, descriptions, "fixed_half_residual", fixed_half, "existing fixed half-residual probability")

    masks = OrderedDict(
        [
            ("global", np.ones(len(df), dtype=bool)),
            ("positive_residual", residual_delta > 0.0),
            ("positive_adj_ge_2pct", probability_adjustment >= 0.02),
            ("positive_adj_ge_5pct", probability_adjustment >= 0.05),
            ("market_ge_60", market >= 0.60),
            ("market_60_80", (market >= 0.60) & (market < 0.80)),
            ("market_60_80_positive", (market >= 0.60) & (market < 0.80) & (residual_delta > 0.0)),
            ("market_ge_60_positive", (market >= 0.60) & (residual_delta > 0.0)),
            ("market_ge_60_adj_ge_2pct", (market >= 0.60) & (probability_adjustment >= 0.02)),
        ]
    )
    for mask_label, mask in masks.items():
        for scale in scales:
            if scale == 1.0:
                continue
            if mask_label == "global" and scale == 0.0:
                continue
            label = f"{mask_label}_scale_{scale_label(scale)}"
            add_candidate(
                candidates,
                descriptions,
                label,
                make_scaled_probability(market, selected, mask, scale),
                f"scale selected residual by {scale_label(scale)} where {mask_label}; otherwise keep selected residual",
            )
    return candidates, descriptions


def summarize_predictions(df: pd.DataFrame, probability: np.ndarray, mask: np.ndarray) -> dict:
    subset = df[mask].copy()
    if subset.empty:
        return {
            "fights": 0,
            "events": 0,
            "market_log_loss": None,
            "candidate_log_loss": None,
            "delta_log_loss": None,
            "actual_rate": None,
            "mean_market_probability": None,
            "mean_candidate_probability": None,
            "mean_adjustment": None,
        }
    y = subset["red_won"].astype(float).to_numpy()
    market = subset["market_probability"].astype(float).to_numpy()
    candidate = probability[mask]
    market_losses = binary_loss(y, market)
    candidate_losses = binary_loss(y, candidate)
    return {
        "fights": int(len(subset)),
        "events": int(subset["event_date"].nunique()),
        "market_log_loss": float(market_losses.mean()),
        "candidate_log_loss": float(candidate_losses.mean()),
        "delta_log_loss": float(market_losses.mean() - candidate_losses.mean()),
        "actual_rate": float(y.mean()),
        "mean_market_probability": float(market.mean()),
        "mean_candidate_probability": float(candidate.mean()),
        "mean_adjustment": float((candidate - market).mean()),
    }


def event_bootstrap_delta(df: pd.DataFrame, probability: np.ndarray, mask: np.ndarray, iterations: int, rng) -> dict:
    subset = df[mask].copy()
    if subset.empty or iterations <= 0:
        return {"p_delta_le_zero": None, "delta_ci_95": [None, None]}
    y = subset["red_won"].astype(float).to_numpy()
    market = subset["market_probability"].astype(float).to_numpy()
    candidate = probability[mask]
    deltas = binary_loss(y, market) - binary_loss(y, candidate)
    event_delta = (
        pd.DataFrame({"event": subset["event_date"].dt.date.astype(str), "delta": deltas})
        .groupby("event")["delta"]
        .sum()
        .to_numpy(dtype=float)
    )
    sampled = rng.integers(0, len(event_delta), size=(iterations, len(event_delta)))
    sums = event_delta[sampled].sum(axis=1)
    return {
        "p_delta_le_zero": float((np.sum(sums <= 0.0) + 1) / (iterations + 1)),
        "delta_ci_95": [float(value) / len(subset) for value in np.percentile(sums, [2.5, 97.5])],
    }


def candidate_score(df: pd.DataFrame, probability: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return -np.inf
    y = df.loc[mask, "red_won"].astype(float).to_numpy()
    market = df.loc[mask, "market_probability"].astype(float).to_numpy()
    candidate = probability[mask]
    return float((binary_loss(y, market) - binary_loss(y, candidate)).mean())


def select_best(scored: list[tuple[float, str]], order: dict[str, int]) -> tuple[float, str]:
    return sorted(scored, key=lambda item: (item[0], -order[item[1]]), reverse=True)[0]


def rolling_select(df: pd.DataFrame, candidates: OrderedDict[str, np.ndarray], candidate_labels: list[str]) -> dict:
    folds = sorted(df["fold"].astype(int).unique())
    order = {label: index for index, label in enumerate(candidate_labels)}
    selected_probability = np.full(len(df), np.nan, dtype=float)
    eval_mask = np.zeros(len(df), dtype=bool)
    fold_rows = []

    for fold in folds:
        if fold <= min(folds):
            continue
        train_mask = df["fold"].astype(int).to_numpy() < fold
        fold_mask = df["fold"].astype(int).to_numpy() == fold
        scored = [
            (candidate_score(df, candidates[label], train_mask), label)
            for label in candidate_labels
        ]
        best_score, selected_label = select_best(scored, order)
        selected_probability[fold_mask] = candidates[selected_label][fold_mask]
        eval_mask |= fold_mask
        fold_rows.append(
            {
                "eval_fold": int(fold),
                "selected_candidate": selected_label,
                "dev_delta_log_loss": float(best_score),
                "eval_summary": summarize_predictions(df, candidates[selected_label], fold_mask),
            }
        )

    return {
        "folds": fold_rows,
        "selected_probability": selected_probability,
        "eval_mask": eval_mask,
        "combined_eval": summarize_predictions(df, selected_probability, eval_mask),
    }


def market_null_rolling_pvalue(
    df: pd.DataFrame,
    candidates: OrderedDict[str, np.ndarray],
    candidate_labels: list[str],
    observed_delta: float,
    iterations: int,
    rng,
) -> float | None:
    if iterations <= 0 or not np.isfinite(observed_delta):
        return None

    market = df["market_probability"].astype(float).to_numpy()
    folds = df["fold"].astype(int).to_numpy()
    unique_folds = sorted(np.unique(folds))
    order = {label: index for index, label in enumerate(candidate_labels)}
    market_loss_win = binary_loss(np.ones(len(df)), market)
    market_loss_loss = binary_loss(np.zeros(len(df)), market)
    candidate_loss_win = {
        label: binary_loss(np.ones(len(df)), candidates[label])
        for label in candidate_labels
    }
    candidate_loss_loss = {
        label: binary_loss(np.zeros(len(df)), candidates[label])
        for label in candidate_labels
    }

    null_values = []
    for _ in range(iterations):
        wins = rng.random(len(df)) < market
        market_loss = np.where(wins, market_loss_win, market_loss_loss)
        candidate_delta = {}
        for label in candidate_labels:
            candidate_loss = np.where(wins, candidate_loss_win[label], candidate_loss_loss[label])
            candidate_delta[label] = market_loss - candidate_loss

        eval_deltas = []
        for fold in unique_folds:
            if fold <= min(unique_folds):
                continue
            train_mask = folds < fold
            fold_mask = folds == fold
            scored = [
                (float(candidate_delta[label][train_mask].mean()), label)
                for label in candidate_labels
            ]
            _, selected_label = select_best(scored, order)
            eval_deltas.extend(candidate_delta[selected_label][fold_mask].tolist())
        if eval_deltas:
            null_values.append(float(np.mean(eval_deltas)))

    if not null_values:
        return None
    null = np.asarray(null_values, dtype=float)
    return float((np.sum(null >= observed_delta) + 1) / (len(null) + 1))


def fixed_summaries(
    df: pd.DataFrame,
    candidates: OrderedDict[str, np.ndarray],
    labels: list[str],
    mask: np.ndarray,
    rng,
    bootstrap_iterations: int,
) -> list[dict]:
    rows = []
    for label in labels:
        summary = summarize_predictions(df, candidates[label], mask)
        bootstrap = event_bootstrap_delta(df, candidates[label], mask, bootstrap_iterations, rng)
        summary["candidate"] = label
        summary["bootstrap_p_delta_le_zero"] = bootstrap["p_delta_le_zero"]
        summary["bootstrap_delta_ci_95"] = bootstrap["delta_ci_95"]
        rows.append(summary)
    return rows


def top_fixed_candidates(rows: list[dict], required_labels: list[str], limit: int = 12) -> list[dict]:
    by_label = {row["candidate"]: row for row in rows}
    required = [by_label[label] for label in required_labels if label in by_label]
    sorted_rows = sorted(rows, key=lambda row: row["delta_log_loss"], reverse=True)
    result = []
    seen = set()
    for row in [*required, *sorted_rows]:
        if row["candidate"] in seen:
            continue
        result.append(row)
        seen.add(row["candidate"])
        if len(result) >= limit:
            break
    return result


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    scales = parse_scales(args.scales)
    df = pd.read_csv(args.predictions, parse_dates=["event_date"])
    candidates, descriptions = candidate_probabilities(df, scales)
    candidate_labels = list(candidates.keys())
    latest_fold = int(df["fold"].max())
    all_mask = np.ones(len(df), dtype=bool)

    rolling = rolling_select(df, candidates, candidate_labels)
    rolling_bootstrap = event_bootstrap_delta(
        df,
        rolling["selected_probability"],
        rolling["eval_mask"],
        args.bootstrap_iterations,
        rng,
    )
    rolling["combined_eval"]["bootstrap_p_delta_le_zero"] = rolling_bootstrap["p_delta_le_zero"]
    rolling["combined_eval"]["bootstrap_delta_ci_95"] = rolling_bootstrap["delta_ci_95"]
    rolling["combined_eval"]["market_null_p"] = market_null_rolling_pvalue(
        df,
        candidates,
        candidate_labels,
        rolling["combined_eval"]["delta_log_loss"],
        args.market_null_iterations,
        rng,
    )

    required_labels = [
        "market",
        "selected_shrinkage",
        "fixed_half_residual",
        "global_scale_0.5",
        "positive_residual_scale_0.5",
        "market_60_80_positive_scale_0",
        "market_60_80_positive_scale_0.5",
        "market_ge_60_adj_ge_2pct_scale_0",
        "market_ge_60_adj_ge_2pct_scale_0.5",
    ]
    all_fixed = fixed_summaries(
        df,
        candidates,
        candidate_labels,
        all_mask,
        rng,
        args.bootstrap_iterations,
    )
    rolling_fixed = fixed_summaries(
        df,
        candidates,
        candidate_labels,
        rolling["eval_mask"],
        rng,
        args.bootstrap_iterations,
    )
    latest_fixed = fixed_summaries(
        df,
        candidates,
        candidate_labels,
        df["fold"].astype(int).to_numpy() == latest_fold,
        rng,
        0,
    )

    return {
        "predictions_path": args.predictions,
        "scales": scales,
        "candidate_count": len(candidate_labels),
        "candidate_descriptions": descriptions,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "fixed_all_summary": top_fixed_candidates(all_fixed, required_labels),
        "fixed_rolling_eval_summary": top_fixed_candidates(rolling_fixed, required_labels),
        "fixed_latest_fold_summary": top_fixed_candidates(latest_fixed, required_labels),
        "rolling_market_band_selection": {
            "folds": rolling["folds"],
            "combined_eval": rolling["combined_eval"],
        },
    }


def fixed_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {candidate} | {fights} | {market_ll} | {candidate_ll} | {delta} | {adj} | {boot} |".format(
                candidate=f"`{row['candidate']}`",
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                candidate_ll=fmt_float(row["candidate_log_loss"]),
                delta=fmt_float(row["delta_log_loss"]),
                adj=fmt_pct(row["mean_adjustment"]),
                boot=fmt_p(row.get("bootstrap_p_delta_le_zero")),
            )
        )
    return lines


def latest_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Candidate | Fights | Delta LL | Mean Adj |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {candidate} | {fights} | {delta} | {adj} |".format(
                candidate=f"`{row['candidate']}`",
                fights=row["fights"],
                delta=fmt_float(row["delta_log_loss"]),
                adj=fmt_pct(row["mean_adjustment"]),
            )
        )
    return lines


def rolling_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Eval Fold | Selected Candidate | Dev Delta LL | Eval Fights | Eval Delta LL | Eval Mean Adj |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        summary = row["eval_summary"]
        lines.append(
            "| {fold} | `{candidate}` | {dev} | {fights} | {delta} | {adj} |".format(
                fold=row["eval_fold"],
                candidate=row["selected_candidate"],
                dev=fmt_float(row["dev_delta_log_loss"]),
                fights=summary["fights"],
                delta=fmt_float(summary["delta_log_loss"]),
                adj=fmt_pct(summary["mean_adjustment"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    combined = result["rolling_market_band_selection"]["combined_eval"]
    selected_folds = result["rolling_market_band_selection"]["folds"]
    selected_labels = sorted({row["selected_candidate"] for row in selected_folds})
    baseline_labels = {"market", "selected_shrinkage", "fixed_half_residual"}
    selected_new_transform = any(label not in baseline_labels for label in selected_labels)
    lines = [
        "# Residual Market-Band Shrinkage Audit",
        "",
        "This audit tests whether the feature-drift clue can become validation",
        "evidence. Candidate transforms shrink the selected residual adjustment",
        "globally, for positive residuals, and for positive residuals inside",
        "favorite-ish market bands. Each evaluation fold selects from the full",
        "candidate family using only prior folds.",
        "",
        "## Inputs",
        "",
        f"- predictions: `{result['predictions_path']}`",
        f"- scale grid: `{result['scales']}`",
        f"- candidates, including market and baselines: `{result['candidate_count']}`",
        f"- event-bootstrap iterations: `{result['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        "",
        "## Candidate Notes",
        "",
        "- `global_scale_s`: scale every selected residual logit adjustment by `s`.",
        "- `positive_residual_scale_s`: scale only positive logit residual adjustments by `s`.",
        "- `market_60_80_positive_scale_s`: scale positive residuals only when market P is `0.60` to `0.80`.",
        "- `market_ge_60_adj_ge_2pct_scale_s`: scale adjustments of at least `+2pp` when market P is at least `0.60`.",
        "- All conditional candidates keep the original selected residual outside the named condition.",
        "",
        "## Fixed Candidate Diagnostics",
        "",
        "These rows are diagnostics only; the validation test is the rolling",
        "prior-fold selection below.",
        "",
        *fixed_table(result["fixed_all_summary"]),
        "",
        "## Fixed Candidates On Rolling Evaluation Folds",
        "",
        *fixed_table(result["fixed_rolling_eval_summary"]),
        "",
        "## Latest-Fold Fixed Candidates",
        "",
        *latest_table(result["fixed_latest_fold_summary"]),
        "",
        "## Rolling Prior-Fold Selection",
        "",
        *rolling_table(selected_folds),
        "",
        "| Combined Eval | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| selected market-band shrinkage | {fights} | {market_ll} | {candidate_ll} | {delta} | {adj} | {boot} | {null_p} |".format(
            fights=combined["fights"],
            market_ll=fmt_float(combined["market_log_loss"]),
            candidate_ll=fmt_float(combined["candidate_log_loss"]),
            delta=fmt_float(combined["delta_log_loss"]),
            adj=fmt_pct(combined["mean_adjustment"]),
            boot=fmt_p(combined["bootstrap_p_delta_le_zero"]),
            null_p=fmt_p(combined["market_null_p"]),
        ),
        "",
        "## Interpretation",
        "",
        f"- Rolling selection chose: `{', '.join(selected_labels)}`.",
        "- This is the relevant validation result because each fold selects using only prior folds.",
        "- A fixed candidate that looks good on the latest fold is still only diagnostic unless rolling selection chose it before that fold.",
    ]
    if not selected_new_transform:
        lines.append(
            "- Rolling selection did not choose a new market-band transform; it reverted to existing baselines. The market-band shrinkage clue remains diagnostic, not validated."
        )
    elif combined["delta_log_loss"] is not None and combined["delta_log_loss"] > 0:
        lines.append(
            "- The rolling transform is directionally positive, but it still needs market-null, bootstrap, and recent-fold scrutiny before becoming a live edge claim."
        )
    else:
        lines.append(
            "- The rolling transform does not improve the edge claim; the drift clue remains diagnostic rather than validated."
        )
    lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_market_band_shrinkage_audit.json"
    md_path = output_dir / "residual_market_band_shrinkage_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    combined = result["rolling_market_band_selection"]["combined_eval"]
    print(f"Rolling Delta LL: {combined['delta_log_loss']:.4f}")
    print(f"Market-null p: {combined['market_null_p']:.3f}")


if __name__ == "__main__":
    main()
