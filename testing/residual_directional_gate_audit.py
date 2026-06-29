#!/usr/bin/env python3
"""Rolling directional gate audit for residual probability adjustments.

The calibration-drift audit showed recent upward red-side residual adjustments
were harmful. This audit tests a stricter question: can a simple directional
gate, selected only from prior folds, repair that drift out of sample?
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
EPS = 1e-6


def parse_args():
    parser = argparse.ArgumentParser(description="Audit directional residual gates")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--scales", default="0,0.5,1.0")
    parser.add_argument("--market-null-iterations", type=int, default=10000)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_directional_gate_audit")
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
    value = np.asarray(value, dtype=float)
    return 1.0 / (1.0 + np.exp(-value))


def binary_loss(y_true, probability) -> np.ndarray:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), EPS, 1.0 - EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def make_probability(df: pd.DataFrame, up_scale: float, down_scale: float) -> np.ndarray:
    market_logit = logit(df["market_probability"].astype(float).to_numpy())
    selected_logit = logit(df["selected_probability"].astype(float).to_numpy())
    residual_delta = selected_logit - market_logit
    scale = np.where(residual_delta >= 0.0, up_scale, down_scale)
    return sigmoid(market_logit + scale * residual_delta)


def add_candidate_probabilities(df: pd.DataFrame, scales: list[float]) -> dict[str, np.ndarray]:
    candidates = {
        "market": df["market_probability"].astype(float).to_numpy(),
        "selected_shrinkage": df["selected_probability"].astype(float).to_numpy(),
    }
    for up_scale in scales:
        for down_scale in scales:
            label = f"up{up_scale:g}_down{down_scale:g}"
            candidates[label] = make_probability(df, up_scale, down_scale)
    return candidates


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
    return {
        "fights": int(len(subset)),
        "events": int(subset["event_date"].nunique()),
        "market_log_loss": float(binary_loss(y, market).mean()),
        "candidate_log_loss": float(binary_loss(y, candidate).mean()),
        "delta_log_loss": float(binary_loss(y, market).mean() - binary_loss(y, candidate).mean()),
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
        pd.DataFrame({"event_date": subset["event_date"].dt.date.astype(str), "delta": deltas})
        .groupby("event_date")["delta"]
        .sum()
        .to_numpy(dtype=float)
    )
    sampled = rng.integers(0, len(event_delta), size=(iterations, len(event_delta)))
    sums = event_delta[sampled].sum(axis=1)
    mean_sums = sums / len(subset)
    return {
        "p_delta_le_zero": float((np.sum(sums <= 0.0) + 1) / (iterations + 1)),
        "delta_ci_95": [float(value) for value in np.percentile(mean_sums, [2.5, 97.5])],
    }


def candidate_score(df: pd.DataFrame, probability: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return -np.inf
    y = df.loc[mask, "red_won"].astype(float).to_numpy()
    market = df.loc[mask, "market_probability"].astype(float).to_numpy()
    candidate = probability[mask]
    return float((binary_loss(y, market) - binary_loss(y, candidate)).mean())


def rolling_select(
    df: pd.DataFrame,
    candidates: dict[str, np.ndarray],
    candidate_labels: list[str],
) -> dict:
    folds = sorted(df["fold"].astype(int).unique())
    fold_rows = []
    selected_probability = np.full(len(df), np.nan, dtype=float)
    eval_mask = np.zeros(len(df), dtype=bool)

    for fold in folds:
        if fold <= min(folds):
            continue
        train_mask = df["fold"].astype(int).to_numpy() < fold
        fold_mask = df["fold"].astype(int).to_numpy() == fold
        scored = []
        for label in candidate_labels:
            score = candidate_score(df, candidates[label], train_mask)
            scored.append((score, label))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected_label = scored[0][1]
        selected_probability[fold_mask] = candidates[selected_label][fold_mask]
        eval_mask |= fold_mask
        eval_summary = summarize_predictions(df, candidates[selected_label], fold_mask)
        fold_rows.append(
            {
                "eval_fold": int(fold),
                "selected_candidate": selected_label,
                "dev_delta_log_loss": float(scored[0][0]),
                "eval_summary": eval_summary,
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
    candidates: dict[str, np.ndarray],
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
    market_loss_win = binary_loss(np.ones(len(df)), market)
    market_loss_loss = binary_loss(np.zeros(len(df)), market)
    candidate_loss_win = {
        label: binary_loss(np.ones(len(df)), probability)
        for label, probability in candidates.items()
    }
    candidate_loss_loss = {
        label: binary_loss(np.zeros(len(df)), probability)
        for label, probability in candidates.items()
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
            scores = [
                (float(candidate_delta[label][train_mask].mean()), label)
                for label in candidate_labels
                if train_mask.any()
            ]
            if not scores:
                continue
            scores.sort(key=lambda item: (item[0], item[1]), reverse=True)
            selected = scores[0][1]
            eval_deltas.extend(candidate_delta[selected][fold_mask].tolist())
        if eval_deltas:
            null_values.append(float(np.mean(eval_deltas)))

    if not null_values:
        return None
    null = np.asarray(null_values, dtype=float)
    return float((np.sum(null >= observed_delta) + 1) / (len(null) + 1))


def fixed_policy_summaries(df: pd.DataFrame, candidates: dict[str, np.ndarray], labels: list[str], rng, args) -> list[dict]:
    rows = []
    mask = np.ones(len(df), dtype=bool)
    for label in labels:
        summary = summarize_predictions(df, candidates[label], mask)
        bootstrap = event_bootstrap_delta(df, candidates[label], mask, args.bootstrap_iterations, rng)
        summary["candidate"] = label
        summary["bootstrap_p_delta_le_zero"] = bootstrap["p_delta_le_zero"]
        summary["bootstrap_delta_ci_95"] = bootstrap["delta_ci_95"]
        rows.append(summary)
    return rows


def masked_policy_summaries(
    df: pd.DataFrame,
    candidates: dict[str, np.ndarray],
    labels: list[str],
    mask: np.ndarray,
    rng,
    args,
) -> list[dict]:
    rows = []
    for label in labels:
        summary = summarize_predictions(df, candidates[label], mask)
        bootstrap = event_bootstrap_delta(df, candidates[label], mask, args.bootstrap_iterations, rng)
        summary["candidate"] = label
        summary["bootstrap_p_delta_le_zero"] = bootstrap["p_delta_le_zero"]
        summary["bootstrap_delta_ci_95"] = bootstrap["delta_ci_95"]
        rows.append(summary)
    return rows


def latest_fold_summaries(df: pd.DataFrame, candidates: dict[str, np.ndarray], labels: list[str]) -> list[dict]:
    latest = int(df["fold"].max())
    mask = df["fold"].astype(int).to_numpy() == latest
    rows = []
    for label in labels:
        summary = summarize_predictions(df, candidates[label], mask)
        summary["candidate"] = label
        rows.append(summary)
    return rows


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    scales = parse_scales(args.scales)
    df = pd.read_csv(args.predictions, parse_dates=["event_date"])
    candidates = add_candidate_probabilities(df, scales)
    gate_labels = [label for label in candidates if label.startswith("up")]
    fixed_labels = ["market", "selected_shrinkage", "up0_down1", "up1_down0", "up0_down0.5", "up0.5_down1"]
    fixed_labels = [label for label in fixed_labels if label in candidates]

    rolling = rolling_select(df, candidates, gate_labels)
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
        gate_labels,
        rolling["combined_eval"]["delta_log_loss"],
        args.market_null_iterations,
        rng,
    )

    return {
        "predictions_path": args.predictions,
        "scales": scales,
        "candidate_count": len(gate_labels),
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "fixed_policy_summaries": fixed_policy_summaries(df, candidates, fixed_labels, rng, args),
        "rolling_eval_fixed_policy_summaries": masked_policy_summaries(
            df,
            candidates,
            fixed_labels,
            rolling["eval_mask"],
            rng,
            args,
        ),
        "latest_fold_summaries": latest_fold_summaries(df, candidates, fixed_labels),
        "rolling_directional_gate": {
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
            "| {label} | {fights} | {market_ll} | {candidate_ll} | {delta} | {adj} | {boot} |".format(
                label=row["candidate"],
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
        "| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {label} | {fights} | {market_ll} | {candidate_ll} | {delta} | {adj} |".format(
                label=row["candidate"],
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                candidate_ll=fmt_float(row["candidate_log_loss"]),
                delta=fmt_float(row["delta_log_loss"]),
                adj=fmt_pct(row["mean_adjustment"]),
            )
        )
    return lines


def rolling_fold_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Eval Fold | Selected Gate | Dev Delta LL | Eval Fights | Eval Delta LL | Eval Mean Adj |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        summary = row["eval_summary"]
        lines.append(
            "| {fold} | `{gate}` | {dev} | {fights} | {delta} | {adj} |".format(
                fold=row["eval_fold"],
                gate=row["selected_candidate"],
                dev=fmt_float(row["dev_delta_log_loss"]),
                fights=summary["fights"],
                delta=fmt_float(summary["delta_log_loss"]),
                adj=fmt_pct(summary["mean_adjustment"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    rolling = result["rolling_directional_gate"]
    combined = rolling["combined_eval"]
    selected_gates = sorted({row["selected_candidate"] for row in rolling["folds"]})
    latest_selected = rolling["folds"][-1]
    latest_best = max(
        result["latest_fold_summaries"],
        key=lambda row: row["delta_log_loss"] if row["delta_log_loss"] is not None else -np.inf,
    )
    eval_baselines = {
        row["candidate"]: row
        for row in result["rolling_eval_fixed_policy_summaries"]
    }
    selected_eval = eval_baselines.get("selected_shrinkage")
    lines = [
        "# Residual Directional Gate Audit",
        "",
        "This audit tests whether a simple drift-aware residual transform can be",
        "selected without looking at the evaluation fold. For each future fold,",
        "it chooses separate scales for upward and downward residual logit",
        "adjustments using only prior folds, then evaluates the chosen gate.",
        "",
        "## Inputs",
        "",
        f"- predictions: `{result['predictions_path']}`",
        f"- scale grid: `{result['scales']}`",
        f"- directional candidates: `{result['candidate_count']}`",
        f"- event-bootstrap iterations: `{result['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        "",
        "## Key Diagnostics",
        "",
        "- Rolling directional selection chose {gates} across folds 2-5.".format(
            gates=", ".join(f"`{gate}`" for gate in selected_gates)
        ),
        "- Combined rolling evaluation: delta LL `{delta}`, bootstrap P(delta <= 0) `{boot}`, market-null p `{null}`.".format(
            delta=fmt_float(combined["delta_log_loss"]),
            boot=fmt_p(combined["bootstrap_p_delta_le_zero"]),
            null=fmt_p(combined["market_null_p"]),
        ),
        "- Latest fold selected `{gate}` and scored delta LL `{delta}`.".format(
            gate=latest_selected["selected_candidate"],
            delta=fmt_float(latest_selected["eval_summary"]["delta_log_loss"]),
        ),
        "- On the same folds 2-5 evaluation set, selected_shrinkage scored delta LL `{selected_delta}`; the rolling gate scored `{gate_delta}`.".format(
            selected_delta=fmt_float(selected_eval["delta_log_loss"] if selected_eval else None),
            gate_delta=fmt_float(combined["delta_log_loss"]),
        ),
        "- The best fixed latest-fold gate was `{gate}` with delta LL `{delta}`, but that is visible only after seeing fold 5.".format(
            gate=latest_best["candidate"],
            delta=fmt_float(latest_best["delta_log_loss"]),
        ),
        "",
        "## Fixed Candidate Summary",
        "",
        *fixed_table(result["fixed_policy_summaries"]),
        "",
        "## Folds 2-5 Fixed Candidate Baselines",
        "",
        *fixed_table(result["rolling_eval_fixed_policy_summaries"]),
        "",
        "## Latest Fold Fixed Candidates",
        "",
        *latest_table(result["latest_fold_summaries"]),
        "",
        "## Rolling Directional Gate",
        "",
        *rolling_fold_table(rolling["folds"]),
        "",
        "| Combined Eval | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| selected gates | {fights} | {market_ll} | {candidate_ll} | {delta} | {adj} | {boot} | {null} |".format(
            fights=combined["fights"],
            market_ll=fmt_float(combined["market_log_loss"]),
            candidate_ll=fmt_float(combined["candidate_log_loss"]),
            delta=fmt_float(combined["delta_log_loss"]),
            adj=fmt_pct(combined["mean_adjustment"]),
            boot=fmt_p(combined["bootstrap_p_delta_le_zero"]),
            null=fmt_p(combined["market_null_p"]),
        ),
        "",
        "## Interpretation",
        "",
        "- This is an exploratory validation audit, not a frozen policy change.",
        "- A useful drift-aware transform should improve the latest fold while preserving positive rolling selection evidence.",
        "- If rolling selection keeps choosing the original full adjustment, the calibration drift cannot be fixed by this simple gate.",
        "- If it mutes upward adjustments only after the damage is already visible, the result is still historical and needs future paper validation.",
        "",
    ]
    return "\n".join(lines)


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_directional_gate_audit.json"
    md_path = output_dir / "residual_directional_gate_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    combined = result["rolling_directional_gate"]["combined_eval"]
    print(
        "Rolling directional gate delta LL {delta:.4f}, market-null p {p}".format(
            delta=combined["delta_log_loss"],
            p=fmt_p(combined["market_null_p"]),
        )
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
