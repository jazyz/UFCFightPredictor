#!/usr/bin/env python3
"""Rolling robustness selection for the striking-core market-aware clue.

This audit makes the current best feature clue work harder. It predefines a
small family of striking-core model variants and pre-fight experience gates,
selects one policy using only prior fold log-loss deltas, and evaluates that
selected policy on later folds.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_aware_feature_audit import (  # noqa: E402
    aligned_market_feature_frame,
    fit_predict_variant,
    numeric_variant_frame,
)
from testing.market_residual_meta_audit import (  # noqa: E402
    EPS,
    event_bootstrap_delta,
    iter_folds,
    per_row_loss,
    score_probabilities,
)
from testing.statistical_edge_audit import binary_log_loss  # noqa: E402
from testing.striking_group_after_market_audit import fmt_float, fmt_p, fmt_pct  # noqa: E402


DEFAULT_OUTPUT_DIR = "test_results/striking_core_robustness_selection_audit"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    feature_columns: tuple[str, ...]
    transform: str
    note: str


@dataclass(frozen=True)
class GateSpec:
    name: str
    min_prior_fights: int | None
    note: str


@dataclass(frozen=True)
class PolicySpec:
    name: str
    model_name: str
    gate_name: str
    note: str


def parse_args():
    parser = argparse.ArgumentParser(description="Rolling robustness selection for striking core")
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
    parser.add_argument("--clip-quantile", type=float, default=0.99)
    parser.add_argument("--min-prior-selection-rows", type=int, default=80)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def build_models() -> list[ModelSpec]:
    return [
        ModelSpec(
            "mixed_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "none",
            "frozen mixed significant-strike/head core",
        ),
        ModelSpec(
            "mixed_core_clip99",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "clip_abs_train_quantile",
            "same core with train-only symmetric absolute clipping",
        ),
        ModelSpec(
            "sigpct_head",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
            ),
            "none",
            "drops raw significant-strike differential to reduce collinearity",
        ),
        ModelSpec(
            "sigpct_only",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
            ),
            "none",
            "market plus strongest single forensics residual-shape feature",
        ),
        ModelSpec(
            "raw_sig_head",
            (
                "market_logit",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "none",
            "raw significant-strike/head differential reference",
        ),
    ]


def build_gates() -> list[GateSpec]:
    return [
        GateSpec("all", None, "all aligned men-only fights"),
        GateSpec("min5", 5, "both fighters have at least five prior fights"),
        GateSpec("min10", 10, "both fighters have at least ten prior fights"),
    ]


def build_policies(models: list[ModelSpec], gates: list[GateSpec]) -> list[PolicySpec]:
    policies = []
    for model in models:
        for gate in gates:
            policies.append(
                PolicySpec(
                    name=f"{model.name}|{gate.name}",
                    model_name=model.name,
                    gate_name=gate.name,
                    note=f"{model.note}; gate: {gate.note}",
                )
            )
    return policies


def ensure_columns(df: pd.DataFrame, models: list[ModelSpec]) -> None:
    available = set(df.columns)
    missing = {}
    for model in models:
        columns = [column for column in model.feature_columns if column not in available]
        if columns:
            missing[model.name] = columns
    if missing:
        raise SystemExit(f"Missing robustness feature columns: {missing}")


def clip_abs_train_quantile(
    train_direct: pd.DataFrame,
    train_swapped: pd.DataFrame,
    eval_direct: pd.DataFrame,
    eval_swapped: pd.DataFrame,
    columns: tuple[str, ...],
    quantile: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    bounds = {}
    for column in columns:
        if column == "market_logit":
            continue
        train_values = pd.concat([train_direct[column], train_swapped[column]], ignore_index=True)
        finite_abs = np.abs(pd.to_numeric(train_values, errors="coerce").dropna().to_numpy(dtype=float))
        if finite_abs.size == 0:
            continue
        bound = float(np.quantile(finite_abs, quantile))
        if not np.isfinite(bound) or bound <= 0.0:
            continue
        bounds[column] = bound
        for frame in (train_direct, train_swapped, eval_direct, eval_swapped):
            frame[column] = pd.to_numeric(frame[column], errors="coerce").clip(-bound, bound)
    return train_direct, train_swapped, eval_direct, eval_swapped, bounds


def fit_predict_model(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    y_train: np.ndarray,
    model: ModelSpec,
    c_value: float,
    clip_quantile: float,
) -> tuple[np.ndarray, dict]:
    if model.transform == "none":
        return fit_predict_variant(train_df, eval_df, y_train, model.feature_columns, c_value)
    if model.transform != "clip_abs_train_quantile":
        raise ValueError(f"Unknown model transform: {model.transform}")

    y_train = np.asarray(y_train, dtype=int)
    train_direct = numeric_variant_frame(train_df, model.feature_columns, swapped=False)
    train_swapped = numeric_variant_frame(train_df, model.feature_columns, swapped=True)
    eval_direct = numeric_variant_frame(eval_df, model.feature_columns, swapped=False)
    eval_swapped = numeric_variant_frame(eval_df, model.feature_columns, swapped=True)
    train_direct, train_swapped, eval_direct, eval_swapped, bounds = clip_abs_train_quantile(
        train_direct.copy(),
        train_swapped.copy(),
        eval_direct.copy(),
        eval_swapped.copy(),
        model.feature_columns,
        clip_quantile,
    )
    x_train = pd.concat([train_direct, train_swapped], ignore_index=True)
    y_extended = np.concatenate([y_train, 1 - y_train])

    if len(np.unique(y_extended)) < 2:
        probability = float(np.clip(np.mean(y_extended), EPS, 1.0 - EPS))
        return np.full(len(eval_df), probability), {
            "constant_fallback": True,
            "intercept": float(np.log(probability / (1.0 - probability))),
            "coefficients": None,
            "clip_bounds": bounds,
        }

    pipeline = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=c_value, penalty="l2", solver="liblinear", max_iter=300),
    )
    pipeline.fit(x_train, y_extended)
    direct = np.clip(pipeline.predict_proba(eval_direct)[:, 1], EPS, 1.0 - EPS)
    swapped = np.clip(pipeline.predict_proba(eval_swapped)[:, 1], EPS, 1.0 - EPS)
    probability = np.clip((direct + (1.0 - swapped)) / 2.0, EPS, 1.0 - EPS)
    logistic = pipeline.named_steps["logisticregression"]
    return probability, {
        "constant_fallback": False,
        "intercept": float(logistic.intercept_[0]),
        "coefficients": [float(value) for value in logistic.coef_[0]],
        "clip_bounds": bounds,
    }


def min_prior_fights(frame: pd.DataFrame) -> pd.Series:
    red = pd.to_numeric(frame["Red totalfights"], errors="coerce")
    blue = pd.to_numeric(frame["Blue totalfights"], errors="coerce")
    return pd.concat([red, blue], axis=1).min(axis=1)


def gate_mask(frame: pd.DataFrame, gate: GateSpec) -> pd.Series:
    if gate.min_prior_fights is None:
        return pd.Series(True, index=frame.index)
    return min_prior_fights(frame) >= gate.min_prior_fights


def run_model_predictions(
    df: pd.DataFrame,
    folds,
    models: list[ModelSpec],
    labels: np.ndarray,
    c_value: float,
    clip_quantile: float,
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    rows = []
    coefficients = []
    fold_rows = []
    for fold in folds:
        train_df = df.iloc[fold.dev_indices]
        holdout_df = df.iloc[fold.holdout_indices]
        holdout_y = labels[fold.holdout_indices]
        fold_row = {
            "fold": int(fold.fold_index),
            "dev_start": fold.dev_start.date().isoformat(),
            "dev_end": fold.dev_end.date().isoformat(),
            "holdout_start": fold.holdout_start.date().isoformat(),
            "holdout_end": fold.holdout_end.date().isoformat(),
            "dev_fights": int(len(fold.dev_indices)),
            "holdout_fights": int(len(fold.holdout_indices)),
            "market_log_loss": binary_log_loss(
                holdout_y,
                holdout_df["red_market_probability"].astype(float).to_numpy(),
            ),
        }
        for model in models:
            probabilities, fit_info = fit_predict_model(
                train_df,
                holdout_df,
                labels[fold.dev_indices],
                model,
                c_value,
                clip_quantile,
            )
            model_loss = binary_log_loss(holdout_y, probabilities)
            fold_row[f"{model.name}_delta_log_loss"] = fold_row["market_log_loss"] - model_loss
            coefficients.append(
                {
                    "fold": int(fold.fold_index),
                    "model": model.name,
                    "feature_columns": list(model.feature_columns),
                    "transform": model.transform,
                    "intercept": fit_info["intercept"],
                    "constant_fallback": fit_info["constant_fallback"],
                    "coefficients": fit_info["coefficients"],
                    "clip_bounds": fit_info.get("clip_bounds"),
                }
            )
            for row_index, probability in zip(fold.holdout_indices, probabilities):
                source = df.iloc[row_index]
                rows.append(
                    {
                        "fold": int(fold.fold_index),
                        "model": model.name,
                        "event_date": source["event_date"].date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "winner_name": source["winner_name"],
                        "red_won": bool(labels[row_index]),
                        "market_probability": float(source["red_market_probability"]),
                        "candidate_probability": float(probability),
                        "min_prior_fights": float(
                            min(float(source["Red totalfights"]), float(source["Blue totalfights"]))
                        ),
                    }
                )
        fold_rows.append(fold_row)
    return pd.DataFrame(rows), coefficients, fold_rows


def expand_policy_predictions(
    model_predictions: pd.DataFrame,
    policies: list[PolicySpec],
    gates: list[GateSpec],
) -> pd.DataFrame:
    gate_by_name = {gate.name: gate for gate in gates}
    parts = []
    for policy in policies:
        rows = model_predictions[model_predictions["model"] == policy.model_name].copy()
        gate = gate_by_name[policy.gate_name]
        if gate.min_prior_fights is not None:
            rows = rows[rows["min_prior_fights"] >= gate.min_prior_fights].copy()
        rows["policy"] = policy.name
        rows["gate"] = policy.gate_name
        parts.append(rows)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def add_loss_deltas(rows: pd.DataFrame) -> pd.DataFrame:
    work = rows.copy()
    y = work["red_won"].astype(float).to_numpy()
    market = work["market_probability"].astype(float).to_numpy()
    candidate = work["candidate_probability"].astype(float).to_numpy()
    work["loss_delta"] = per_row_loss(y, market) - per_row_loss(y, candidate)
    return work


def summarize_policy(rows: pd.DataFrame, name: str, note: str, bootstrap_iterations: int, rng) -> dict:
    if rows.empty:
        return {
            "name": name,
            "note": note,
            "rows": 0,
            "events": 0,
            "market": score_probabilities([], []),
            "candidate": score_probabilities([], []),
            "market_minus_candidate_log_loss": None,
            "market_minus_candidate_brier": None,
            "mean_row_loss_delta": None,
            "positive_folds": 0,
            "folds": 0,
            "fold_log_loss_deltas": [],
            "event_bootstrap": None,
        }
    y = rows["red_won"].astype(float).to_numpy()
    market = rows["market_probability"].astype(float).to_numpy()
    candidate = rows["candidate_probability"].astype(float).to_numpy()
    market_score = score_probabilities(y, market)
    candidate_score = score_probabilities(y, candidate)
    fold_deltas = []
    for _, fold_subset in rows.groupby("fold", sort=True):
        fold_y = fold_subset["red_won"].astype(float).to_numpy()
        fold_deltas.append(
            float(
                binary_log_loss(fold_y, fold_subset["market_probability"].astype(float).to_numpy())
                - binary_log_loss(fold_y, fold_subset["candidate_probability"].astype(float).to_numpy())
            )
        )
    bootstrap_input = rows.rename(columns={"candidate_probability": "meta_probability"})
    return {
        "name": name,
        "note": note,
        "rows": int(len(rows)),
        "events": int(rows["event_date"].nunique()),
        "market": market_score,
        "candidate": candidate_score,
        "market_minus_candidate_log_loss": float(market_score["log_loss"] - candidate_score["log_loss"]),
        "market_minus_candidate_brier": float(market_score["brier"] - candidate_score["brier"]),
        "mean_row_loss_delta": float(np.mean(per_row_loss(y, market) - per_row_loss(y, candidate))),
        "positive_folds": int(np.sum(np.asarray(fold_deltas) > 0.0)),
        "folds": int(len(fold_deltas)),
        "fold_log_loss_deltas": fold_deltas,
        "event_bootstrap": event_bootstrap_delta(bootstrap_input, bootstrap_iterations, rng),
    }


def select_rolling_policy(
    policy_predictions: pd.DataFrame,
    policies: list[PolicySpec],
    min_prior_rows: int,
) -> tuple[pd.DataFrame, list[dict]]:
    work = add_loss_deltas(policy_predictions)
    folds = sorted(int(value) for value in work["fold"].unique())
    policy_order = {policy.name: index for index, policy in enumerate(policies)}
    selected_parts = []
    selections = []
    for fold in folds:
        prior = work[work["fold"] < fold]
        current = work[work["fold"] == fold]
        if prior.empty:
            continue
        scores = {}
        prior_rows = {}
        prior_positive_folds = {}
        for policy in policies:
            subset = prior[prior["policy"] == policy.name]
            if len(subset) < min_prior_rows:
                continue
            by_fold = subset.groupby("fold", sort=True)["loss_delta"].mean()
            scores[policy.name] = float(subset["loss_delta"].mean())
            prior_rows[policy.name] = int(len(subset))
            prior_positive_folds[policy.name] = int((by_fold > 0.0).sum())
        if not scores:
            continue
        selected_policy = max(scores, key=lambda name: (scores[name], -policy_order[name]))
        selected_current = current[current["policy"] == selected_policy].copy()
        selected_parts.append(selected_current)
        eval_delta = None
        if not selected_current.empty:
            eval_delta = float(selected_current["loss_delta"].mean())
        selections.append(
            {
                "fold": int(fold),
                "selected_policy": selected_policy,
                "prior_score": float(scores[selected_policy]),
                "prior_rows": int(prior_rows[selected_policy]),
                "prior_positive_folds": int(prior_positive_folds[selected_policy]),
                "eval_rows": int(len(selected_current)),
                "eval_delta_log_loss": eval_delta,
                "candidate_scores": scores,
            }
        )
    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    return selected, selections


def summarize_fixed_policies(
    policy_predictions: pd.DataFrame,
    policies: list[PolicySpec],
    bootstrap_iterations: int,
    rng,
) -> dict:
    summaries = {}
    for policy in policies:
        rows = policy_predictions[policy_predictions["policy"] == policy.name].copy()
        summaries[policy.name] = summarize_policy(rows, policy.name, policy.note, bootstrap_iterations, rng)
    return summaries


def market_null_selection(
    df: pd.DataFrame,
    folds,
    models: list[ModelSpec],
    gates: list[GateSpec],
    policies: list[PolicySpec],
    observed_delta: float,
    c_value: float,
    clip_quantile: float,
    min_prior_rows: int,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    market = np.clip(df["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    deltas = np.empty(iterations, dtype=float)
    row_counts = np.empty(iterations, dtype=int)
    for iteration in range(iterations):
        labels = (rng.random(len(df)) < market).astype(int)
        model_predictions, _, _ = run_model_predictions(
            df,
            folds,
            models,
            labels,
            c_value,
            clip_quantile,
        )
        policy_predictions = expand_policy_predictions(model_predictions, policies, gates)
        selected, _ = select_rolling_policy(policy_predictions, policies, min_prior_rows)
        if selected.empty:
            deltas[iteration] = np.nan
            row_counts[iteration] = 0
        else:
            selected = add_loss_deltas(selected)
            deltas[iteration] = float(selected["loss_delta"].mean())
            row_counts[iteration] = int(len(selected))
    valid = np.isfinite(deltas)
    valid_deltas = deltas[valid]
    if valid_deltas.size == 0:
        return None
    return {
        "iterations": int(iterations),
        "valid_iterations": int(valid_deltas.size),
        "observed_delta": float(observed_delta),
        "null_mean_delta": float(np.mean(valid_deltas)),
        "null_delta_ci_95": [float(value) for value in np.percentile(valid_deltas, [2.5, 97.5])],
        "p_value_observed_or_better": float(
            (np.sum(valid_deltas >= observed_delta) + 1) / (valid_deltas.size + 1)
        ),
        "prob_null_delta_positive": float(np.mean(valid_deltas > 0.0)),
        "null_row_count_mean": float(np.mean(row_counts[valid])),
        "null_row_count_ci_95": [float(value) for value in np.percentile(row_counts[valid], [2.5, 97.5])],
    }


def summarize_selection(
    policy_predictions: pd.DataFrame,
    policies: list[PolicySpec],
    min_prior_rows: int,
    bootstrap_iterations: int,
    rng,
) -> dict:
    selected, selections = select_rolling_policy(policy_predictions, policies, min_prior_rows)
    selected_summary = summarize_policy(
        selected,
        "rolling_selected_prior_delta",
        "select highest mean prior-fold row delta across predefined striking policies",
        bootstrap_iterations,
        rng,
    )
    eval_folds = sorted(int(value) for value in selected["fold"].unique()) if not selected.empty else []
    return {
        "eval_folds": eval_folds,
        "selected_summary": selected_summary,
        "selected_rows": int(len(selected)),
        "selections": selections,
    }


def top_fixed_table_rows(fixed: dict, limit: int = 12) -> list[dict]:
    return sorted(
        fixed.values(),
        key=lambda row: (
            -999.0 if row["market_minus_candidate_log_loss"] is None else row["market_minus_candidate_log_loss"],
            row["rows"],
        ),
        reverse=True,
    )[:limit]


def markdown_report(result: dict) -> str:
    selected = result["rolling_selection"]["selected_summary"]
    null = result.get("selection_market_null") or {}
    boot = selected.get("event_bootstrap") or {}
    lines = [
        "# Striking Core Robustness Selection Audit",
        "",
        "This audit tests whether the striking-core clue survives a stricter",
        "rolling policy-selection protocol. A small family of feature variants",
        "and pre-fight experience gates is predefined, then one policy is selected",
        "for each evaluation fold using only prior fold log-loss deltas.",
        "",
        "## Protocol",
        "",
        f"- feature table: `{result['metadata']['features_path']}`",
        f"- odds table: `{result['metadata']['odds_path']}`",
        f"- aligned men-only rows: `{result['metadata']['aligned_rows']}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- candidate policies: `{len(result['policies'])}`",
        f"- first holdout start: `{result['parameters']['first_holdout_start']}`",
        f"- last holdout end: `{result['parameters']['last_holdout_end']}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- selection minimum prior rows: `{result['parameters']['min_prior_selection_rows']}`",
        f"- market-null iterations: `{result['parameters']['market_null_iterations']}`",
        "",
        "## Rolling Selection Result",
        "",
        "| Policy | Rows | Candidate LL | Market Delta LL | Brier Delta | Positive Folds | Bootstrap P(delta<=0) | Selection-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| `{name}` | {rows} | {ll} | {delta} | {brier} | {positive} / {folds} | {boot} | {null_p} |".format(
            name=selected["name"],
            rows=selected["rows"],
            ll=fmt_float(selected["candidate"]["log_loss"]),
            delta=fmt_float(selected["market_minus_candidate_log_loss"]),
            brier=fmt_float(selected["market_minus_candidate_brier"]),
            positive=selected["positive_folds"],
            folds=selected["folds"],
            boot=fmt_p(boot.get("prob_delta_le_zero")),
            null_p=fmt_p(null.get("p_value_observed_or_better")),
        ),
        "",
        "Selection path:",
        "",
        "| Fold | Selected Policy | Prior Rows | Prior Score | Eval Rows | Eval Delta LL |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in result["rolling_selection"]["selections"]:
        lines.append(
            "| {fold} | `{policy}` | {prior_rows} | {prior_score} | {eval_rows} | {eval_delta} |".format(
                fold=row["fold"],
                policy=row["selected_policy"],
                prior_rows=row["prior_rows"],
                prior_score=fmt_float(row["prior_score"]),
                eval_rows=row["eval_rows"],
                eval_delta=fmt_float(row.get("eval_delta_log_loss")),
            )
        )

    lines.extend(
        [
            "",
            "## Best Fixed Policies In Hindsight",
            "",
            "| Policy | Rows | Market Delta LL | Brier Delta | Positive Folds | Bootstrap P(delta<=0) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top_fixed_table_rows(result["fixed_policy_summaries"]):
        boot = row.get("event_bootstrap") or {}
        lines.append(
            "| `{name}` | {rows} | {delta} | {brier} | {positive} / {folds} | {boot} |".format(
                name=row["name"],
                rows=row["rows"],
                delta=fmt_float(row["market_minus_candidate_log_loss"]),
                brier=fmt_float(row["market_minus_candidate_brier"]),
                positive=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
            )
        )

    lines.extend(
        [
            "",
            "## Candidate Family",
            "",
            "| Policy | Note |",
            "| --- | --- |",
        ]
    )
    for policy in result["policies"]:
        lines.append(f"| `{policy['name']}` | {policy['note']} |")

    lines.extend(["", "## Interpretation", ""])
    delta = selected["market_minus_candidate_log_loss"]
    null_p = null.get("p_value_observed_or_better")
    if delta is None or delta <= 0.0:
        lines.append("- Rolling prior-fold selection did not preserve a positive probability edge.")
    elif null_p is not None and null_p <= 0.05:
        lines.append(
            "- Rolling prior-fold selection preserved a positive edge and cleared the unadjusted selection-null screen."
        )
    else:
        lines.append(
            "- Rolling prior-fold selection preserved a positive edge, but did not clear a strong selection-adjusted market-null screen."
        )
    lines.append(
        "- The fixed-policy table is hindsight context only; the rolling-selected row is the main robustness result."
    )
    lines.append(
        "- This is still not proof of a live edge: the event-bootstrap interval crosses zero, and the candidate family was designed after earlier striking-feature discovery."
    )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    align_args = argparse.Namespace(
        features=args.features,
        odds=args.odds,
        fight_details_source=args.fight_details_source,
        min_training_date=args.min_training_date,
        last_holdout_end=args.last_holdout_end,
        include_womens_fights=False,
    )
    df, metadata = aligned_market_feature_frame(align_args)
    models = build_models()
    gates = build_gates()
    policies = build_policies(models, gates)
    ensure_columns(df, models)
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
        raise SystemExit("No rolling folds available for requested robustness audit")

    labels = df["red_won"].astype(int).to_numpy()
    model_predictions, coefficients, fold_rows = run_model_predictions(
        df,
        folds,
        models,
        labels,
        args.c,
        args.clip_quantile,
    )
    policy_predictions = expand_policy_predictions(model_predictions, policies, gates)
    fixed = summarize_fixed_policies(policy_predictions, policies, args.bootstrap_iterations, rng)
    rolling = summarize_selection(
        policy_predictions,
        policies,
        args.min_prior_selection_rows,
        args.bootstrap_iterations,
        rng,
    )
    observed_delta = rolling["selected_summary"]["market_minus_candidate_log_loss"]
    null = None
    if observed_delta is not None:
        null = market_null_selection(
            df,
            folds,
            models,
            gates,
            policies,
            observed_delta,
            args.c,
            args.clip_quantile,
            args.min_prior_selection_rows,
            args.market_null_iterations,
            rng,
        )

    return {
        "parameters": {
            "first_holdout_start": args.first_holdout_start,
            "last_holdout_end": args.last_holdout_end,
            "dev_days": args.dev_days,
            "holdout_days": args.holdout_days,
            "step_days": args.step_days,
            "min_dev_fights": args.min_dev_fights,
            "min_holdout_fights": args.min_holdout_fights,
            "c": args.c,
            "clip_quantile": args.clip_quantile,
            "min_prior_selection_rows": args.min_prior_selection_rows,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "seed": args.seed,
        },
        "metadata": metadata,
        "folds": fold_rows,
        "models": [
            {
                "name": model.name,
                "feature_columns": list(model.feature_columns),
                "transform": model.transform,
                "note": model.note,
            }
            for model in models
        ],
        "gates": [
            {
                "name": gate.name,
                "min_prior_fights": gate.min_prior_fights,
                "note": gate.note,
            }
            for gate in gates
        ],
        "policies": [
            {
                "name": policy.name,
                "model_name": policy.model_name,
                "gate_name": policy.gate_name,
                "note": policy.note,
            }
            for policy in policies
        ],
        "coefficients": coefficients,
        "fixed_policy_summaries": fixed,
        "rolling_selection": rolling,
        "selection_market_null": null,
    }


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_core_robustness_selection_audit.json"
    md_path = output_dir / "striking_core_robustness_selection_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
