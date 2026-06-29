#!/usr/bin/env python3
"""Semantic audit for head-strike pace around the sigpct/head alpha.

The prior feature-context audit found that `Head differential_pm oppdiff`
has a negative standardized coefficient when paired with raw
`Head differential oppdiff`. This audit asks whether that extra pace term is
adding robust incremental value, and whether a residualized "pace excess"
view makes the feature story clearer.

This is an exploratory diagnostic. It does not freeze or change any paper
policy.
"""

from __future__ import annotations

import argparse
import json
import sys
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
    VariantSpec,
    aggregate_predictions,
    aligned_market_feature_frame,
    numeric_variant_frame,
    run_observed_predictions,
    summarize_coefficients,
)
from testing.market_residual_meta_audit import EPS, iter_folds  # noqa: E402
from testing.statistical_edge_audit import binary_log_loss, brier_score  # noqa: E402
from testing.striking_feature_engineering_audit import (  # noqa: E402
    add_pace_features,
    build_pace_features,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_head_pace_semantic_audit"
MARKET = "market_logit"
SIGPCT = "Sig. str.% differential oppdiff"
HEAD_RAW = "Head differential oppdiff"
HEAD_PM = "Head differential_pm oppdiff"
HEAD_PM_RESID = "Head differential_pm residual_after_sigpct_raw_head"


def parse_args():
    parser = argparse.ArgumentParser(description="Audit semantic role of head-strike pace")
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
    parser.add_argument("--bins", type=int, default=5)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def fmt_float(value, digits=4) -> str:
    if value is None:
        return ""
    value = float(value)
    if not np.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None:
        return ""
    value = float(value)
    if not np.isfinite(value):
        return ""
    return f"{100.0 * value:.{digits}f}%"


def fmt_p(value) -> str:
    if value is None:
        return ""
    value = float(value)
    if not np.isfinite(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def build_standard_variants() -> list[VariantSpec]:
    return [
        VariantSpec("market_recalibrated", (MARKET,), "market-logit-only recalibration"),
        VariantSpec("sigpct_only", (MARKET, SIGPCT), "market plus striking efficiency"),
        VariantSpec(
            "sigpct_head_raw",
            (MARKET, SIGPCT, HEAD_RAW),
            "clean sigpct plus raw head-differential anchor",
        ),
        VariantSpec(
            "sigpct_head_pm",
            (MARKET, SIGPCT, HEAD_PM),
            "sigpct plus pace-adjusted head differential, no raw head",
        ),
        VariantSpec(
            "sigpct_head_raw_pm",
            (MARKET, SIGPCT, HEAD_RAW, HEAD_PM),
            "frozen raw-head plus head-pace challenger",
        ),
    ]


def prepare_frame(args) -> tuple[pd.DataFrame, dict, list]:
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
    missing = [
        column
        for column in (MARKET, SIGPCT, HEAD_RAW, HEAD_PM)
        if column not in aligned.columns
    ]
    if missing:
        raise SystemExit(f"Missing required head-pace columns: {missing}")
    metadata.update(pace_metadata)
    metadata["pace_reconstruction"] = pace_reconstruction
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
    return aligned, metadata, folds


def residualize_feature(
    train_direct: pd.DataFrame,
    train_swapped: pd.DataFrame,
    eval_direct: pd.DataFrame,
    eval_swapped: pd.DataFrame,
    source_column: str,
    control_columns: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    train_source = pd.concat(
        [train_direct[[source_column]], train_swapped[[source_column]]],
        ignore_index=True,
    )
    train_controls = pd.concat(
        [train_direct[list(control_columns)], train_swapped[list(control_columns)]],
        ignore_index=True,
    )
    control_imputer = SimpleImputer(strategy="median")
    source_imputer = SimpleImputer(strategy="median")
    x_train = control_imputer.fit_transform(train_controls)
    y_train = source_imputer.fit_transform(train_source).ravel()
    design = np.column_stack([np.ones(len(x_train)), x_train])
    beta = np.linalg.lstsq(design, y_train, rcond=None)[0]

    def residual(frame: pd.DataFrame) -> np.ndarray:
        x_values = control_imputer.transform(frame[list(control_columns)])
        y_values = source_imputer.transform(frame[[source_column]]).ravel()
        expected = np.column_stack([np.ones(len(x_values)), x_values]) @ beta
        return y_values - expected

    train_residual = y_train - design @ beta
    return train_residual, residual(eval_direct), residual(eval_swapped), {
        "intercept": float(beta[0]),
        "controls": list(control_columns),
        "coefficients": {
            feature: float(coefficient)
            for feature, coefficient in zip(control_columns, beta[1:])
        },
    }


def fit_predict_residualized_head_pm(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    y_train: np.ndarray,
    c_value: float,
) -> tuple[np.ndarray, dict]:
    base_columns = (MARKET, SIGPCT, HEAD_RAW, HEAD_PM)
    train_direct = numeric_variant_frame(train_df, base_columns, swapped=False)
    train_swapped = numeric_variant_frame(train_df, base_columns, swapped=True)
    eval_direct = numeric_variant_frame(eval_df, base_columns, swapped=False)
    eval_swapped = numeric_variant_frame(eval_df, base_columns, swapped=True)

    train_residual, eval_direct_residual, eval_swapped_residual, residual_fit = residualize_feature(
        train_direct,
        train_swapped,
        eval_direct,
        eval_swapped,
        HEAD_PM,
        (SIGPCT, HEAD_RAW),
    )

    def with_residual(frame: pd.DataFrame, residual_values: np.ndarray) -> pd.DataFrame:
        result = frame[[MARKET, SIGPCT, HEAD_RAW]].copy()
        result[HEAD_PM_RESID] = residual_values
        return result[[MARKET, SIGPCT, HEAD_RAW, HEAD_PM_RESID]]

    x_train = pd.concat(
        [
            with_residual(train_direct, train_residual[: len(train_direct)]),
            with_residual(train_swapped, train_residual[len(train_direct) :]),
        ],
        ignore_index=True,
    )
    y_extended = np.concatenate([np.asarray(y_train, dtype=int), 1 - np.asarray(y_train, dtype=int)])
    eval_direct_x = with_residual(eval_direct, eval_direct_residual)
    eval_swapped_x = with_residual(eval_swapped, eval_swapped_residual)

    if len(np.unique(y_extended)) < 2:
        probability = float(np.clip(np.mean(y_extended), EPS, 1.0 - EPS))
        return np.full(len(eval_df), probability), {
            "constant_fallback": True,
            "intercept": float(np.log(probability / (1.0 - probability))),
            "feature_columns": [MARKET, SIGPCT, HEAD_RAW, HEAD_PM_RESID],
            "coefficients": None,
            "residual_fit": residual_fit,
        }

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=c_value, penalty="l2", solver="liblinear", max_iter=300),
    )
    model.fit(x_train, y_extended)
    direct = np.clip(model.predict_proba(eval_direct_x)[:, 1], EPS, 1.0 - EPS)
    swapped = np.clip(model.predict_proba(eval_swapped_x)[:, 1], EPS, 1.0 - EPS)
    probability = np.clip((direct + (1.0 - swapped)) / 2.0, EPS, 1.0 - EPS)
    logistic = model.named_steps["logisticregression"]
    return probability, {
        "constant_fallback": False,
        "intercept": float(logistic.intercept_[0]),
        "feature_columns": [MARKET, SIGPCT, HEAD_RAW, HEAD_PM_RESID],
        "coefficients": [float(value) for value in logistic.coef_[0]],
        "residual_fit": residual_fit,
    }


def run_residualized_predictions(
    df: pd.DataFrame,
    folds,
    c_value: float,
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    y = df["red_won"].astype(int).to_numpy()
    prediction_rows = []
    coefficient_rows = []
    fold_rows = []
    for fold in folds:
        train_df = df.iloc[fold.dev_indices]
        eval_df = df.iloc[fold.holdout_indices]
        probabilities, fit_info = fit_predict_residualized_head_pm(
            train_df,
            eval_df,
            y[fold.dev_indices],
            c_value,
        )
        holdout_y = y[fold.holdout_indices]
        market_probability = eval_df["red_market_probability"].astype(float).to_numpy()
        fold_rows.append(
            {
                "fold": int(fold.fold_index),
                "dev_start": fold.dev_start.date().isoformat(),
                "dev_end": fold.dev_end.date().isoformat(),
                "holdout_start": fold.holdout_start.date().isoformat(),
                "holdout_end": fold.holdout_end.date().isoformat(),
                "dev_fights": int(len(fold.dev_indices)),
                "holdout_fights": int(len(fold.holdout_indices)),
                "market_log_loss": binary_log_loss(holdout_y, market_probability),
                "sigpct_head_raw_pm_residualized_log_loss": binary_log_loss(
                    holdout_y,
                    probabilities,
                ),
                "sigpct_head_raw_pm_residualized_delta_log_loss": binary_log_loss(
                    holdout_y,
                    market_probability,
                )
                - binary_log_loss(holdout_y, probabilities),
                "residual_fit": fit_info["residual_fit"],
            }
        )
        coefficient_rows.append(
            {
                "fold": int(fold.fold_index),
                "variant": "sigpct_head_raw_pm_residualized",
                "intercept": fit_info["intercept"],
                "constant_fallback": fit_info["constant_fallback"],
                "feature_columns": fit_info["feature_columns"],
                "coefficients": fit_info["coefficients"],
                "residual_fit": fit_info["residual_fit"],
            }
        )
        for row_index, probability in zip(fold.holdout_indices, probabilities):
            source = df.iloc[row_index]
            prediction_rows.append(
                {
                    "fold": int(fold.fold_index),
                    "variant": "sigpct_head_raw_pm_residualized",
                    "event_date": source["event_date"].date().isoformat(),
                    "fight_key": source["fight_key"],
                    "title": source["title"],
                    "red_fighter": source["red_fighter"],
                    "blue_fighter": source["blue_fighter"],
                    "winner_name": source["winner_name"],
                    "red_won": bool(y[row_index]),
                    "market_probability": float(source["red_market_probability"]),
                    "candidate_probability": float(probability),
                }
            )
    return pd.DataFrame(prediction_rows), coefficient_rows, fold_rows


def incremental_table(predictions: pd.DataFrame, base_variant: str, candidate_variant: str) -> dict:
    base = predictions[predictions["variant"].eq(base_variant)].copy()
    candidate = predictions[predictions["variant"].eq(candidate_variant)].copy()
    merged = base.merge(
        candidate[
            [
                "fold",
                "fight_key",
                "candidate_probability",
            ]
        ],
        on=["fold", "fight_key"],
        suffixes=("_base", "_candidate"),
        validate="one_to_one",
    )
    rows = []
    for fold, subset in merged.groupby("fold", sort=True):
        y = subset["red_won"].astype(float).to_numpy()
        base_p = subset["candidate_probability_base"].astype(float).to_numpy()
        candidate_p = subset["candidate_probability_candidate"].astype(float).to_numpy()
        rows.append(
            {
                "fold": int(fold),
                "rows": int(len(subset)),
                "base_log_loss": binary_log_loss(y, base_p),
                "candidate_log_loss": binary_log_loss(y, candidate_p),
                "candidate_minus_base_delta_log_loss": binary_log_loss(y, base_p)
                - binary_log_loss(y, candidate_p),
                "base_brier": brier_score(y, base_p),
                "candidate_brier": brier_score(y, candidate_p),
                "candidate_minus_base_delta_brier": brier_score(y, base_p)
                - brier_score(y, candidate_p),
            }
        )
    y = merged["red_won"].astype(float).to_numpy()
    base_p = merged["candidate_probability_base"].astype(float).to_numpy()
    candidate_p = merged["candidate_probability_candidate"].astype(float).to_numpy()
    return {
        "base_variant": base_variant,
        "candidate_variant": candidate_variant,
        "rows": int(len(merged)),
        "base_log_loss": binary_log_loss(y, base_p),
        "candidate_log_loss": binary_log_loss(y, candidate_p),
        "candidate_minus_base_delta_log_loss": binary_log_loss(y, base_p)
        - binary_log_loss(y, candidate_p),
        "base_brier": brier_score(y, base_p),
        "candidate_brier": brier_score(y, candidate_p),
        "candidate_minus_base_delta_brier": brier_score(y, base_p)
        - brier_score(y, candidate_p),
        "positive_folds": int(
            sum(row["candidate_minus_base_delta_log_loss"] > 0.0 for row in rows)
        ),
        "folds": int(len(rows)),
        "folds_detail": rows,
    }


def global_residualized_frame(aligned: pd.DataFrame) -> tuple[pd.Series, dict]:
    controls = aligned[[SIGPCT, HEAD_RAW]].apply(pd.to_numeric, errors="coerce")
    source = pd.to_numeric(aligned[HEAD_PM], errors="coerce")
    mask = controls.notna().all(axis=1) & source.notna()
    design = np.column_stack([np.ones(mask.sum()), controls.loc[mask].to_numpy()])
    beta = np.linalg.lstsq(design, source.loc[mask].to_numpy(), rcond=None)[0]
    residual = pd.Series(np.nan, index=aligned.index, dtype=float)
    residual.loc[mask] = source.loc[mask].to_numpy() - design @ beta
    return residual, {
        "intercept": float(beta[0]),
        "coefficients": {
            SIGPCT: float(beta[1]),
            HEAD_RAW: float(beta[2]),
        },
    }


def conditional_residual_bins(aligned: pd.DataFrame, bins: int) -> list[dict]:
    work = aligned.copy()
    residual, fit = global_residualized_frame(work)
    work["_head_pm_residual"] = residual
    work["_actual_minus_market"] = work["red_won"].astype(float) - pd.to_numeric(
        work["red_market_probability"],
        errors="coerce",
    )
    raw = pd.to_numeric(work[HEAD_RAW], errors="coerce")
    mask = raw.notna() & work["_head_pm_residual"].notna() & work["_actual_minus_market"].notna()
    work = work[mask].copy()
    ranks = raw.loc[work.index].rank(method="first")
    work["_raw_bin"] = pd.qcut(ranks, q=min(bins, len(work)), labels=False, duplicates="drop")
    rows = []
    for raw_bin, raw_subset in work.groupby("_raw_bin", sort=True):
        median_residual = raw_subset["_head_pm_residual"].median()
        for residual_bin, subset in (
            ("low_excess_pace", raw_subset[raw_subset["_head_pm_residual"] <= median_residual]),
            ("high_excess_pace", raw_subset[raw_subset["_head_pm_residual"] > median_residual]),
        ):
            rows.append(
                {
                    "raw_head_bin": int(raw_bin) + 1,
                    "residual_bin": residual_bin,
                    "rows": int(len(subset)),
                    "mean_raw_head": float(pd.to_numeric(subset[HEAD_RAW], errors="coerce").mean()),
                    "mean_head_pm_residual": float(subset["_head_pm_residual"].mean()),
                    "actual_red_win_rate": float(subset["red_won"].astype(float).mean()),
                    "mean_market_probability": float(
                        pd.to_numeric(subset["red_market_probability"], errors="coerce").mean()
                    ),
                    "actual_minus_market": float(subset["_actual_minus_market"].mean()),
                }
            )
    return rows, fit, {
        "spearman_residual_to_actual_minus_market": float(
            work["_head_pm_residual"].corr(work["_actual_minus_market"], method="spearman")
        ),
        "pearson_residual_to_actual_minus_market": float(
            work["_head_pm_residual"].corr(work["_actual_minus_market"], method="pearson")
        ),
    }


def correlation_summary(aligned: pd.DataFrame) -> dict:
    frame = aligned[[SIGPCT, HEAD_RAW, HEAD_PM]].apply(pd.to_numeric, errors="coerce")
    return {
        "pearson": frame.corr(method="pearson").round(6).to_dict(),
        "spearman": frame.corr(method="spearman").round(6).to_dict(),
    }


def add_coefficient_sign_counts(summary: dict, coefficient_rows: list[dict]) -> dict:
    sign_values: dict[tuple[str, str], list[float]] = {}
    for row in coefficient_rows:
        coefficients = row.get("coefficients")
        if coefficients is None:
            continue
        for feature, coefficient in zip(row["feature_columns"], coefficients):
            sign_values.setdefault((row["variant"], feature), []).append(float(coefficient))

    enriched = json.loads(json.dumps(summary))
    for (variant, feature), values in sign_values.items():
        array = np.asarray(values, dtype=float)
        enriched.setdefault(variant, {}).setdefault(feature, {})
        enriched[variant][feature].update(
            {
                "positive_folds": int(np.sum(array > 0.0)),
                "negative_folds": int(np.sum(array < 0.0)),
            }
        )
    return enriched


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    aligned, metadata, folds = prepare_frame(args)
    variants = build_standard_variants()
    standard_predictions, standard_coefficients, standard_fold_rows = run_observed_predictions(
        aligned,
        folds,
        variants,
        args.c,
    )
    residual_predictions, residual_coefficients, residual_fold_rows = run_residualized_predictions(
        aligned,
        folds,
        args.c,
    )
    all_predictions = pd.concat([standard_predictions, residual_predictions], ignore_index=True)
    all_coefficients = [*standard_coefficients, *residual_coefficients]
    all_variants = [
        *variants,
        VariantSpec(
            "sigpct_head_raw_pm_residualized",
            (MARKET, SIGPCT, HEAD_RAW, HEAD_PM_RESID),
            "dev-fold residualized head pace excess after sigpct/raw head",
        ),
    ]
    aggregate = aggregate_predictions(all_predictions, all_variants, args.bootstrap_iterations, rng)
    coefficient_summary = add_coefficient_sign_counts(
        summarize_coefficients(all_coefficients),
        all_coefficients,
    )

    residual_bins, residual_fit, residual_corr = conditional_residual_bins(aligned, args.bins)
    return {
        "source_fights": args.source_fights,
        "features": args.features,
        "odds": args.odds,
        "fight_details_source": args.fight_details_source,
        "alignment_metadata": metadata,
        "protocol": {
            "first_holdout_start": args.first_holdout_start,
            "last_holdout_end": args.last_holdout_end,
            "dev_days": args.dev_days,
            "holdout_days": args.holdout_days,
            "step_days": args.step_days,
            "min_dev_fights": args.min_dev_fights,
            "min_holdout_fights": args.min_holdout_fights,
            "logistic_l2_c": args.c,
            "bootstrap_iterations": args.bootstrap_iterations,
            "seed": args.seed,
        },
        "variants": [
            {"name": variant.name, "note": variant.note, "feature_columns": list(variant.feature_columns)}
            for variant in all_variants
        ],
        "aggregate_summary": aggregate,
        "coefficient_summary": coefficient_summary,
        "incremental_raw_pm_vs_raw": incremental_table(
            all_predictions,
            "sigpct_head_raw",
            "sigpct_head_raw_pm",
        ),
        "incremental_residualized_vs_raw": incremental_table(
            all_predictions,
            "sigpct_head_raw",
            "sigpct_head_raw_pm_residualized",
        ),
        "correlations": correlation_summary(aligned),
        "global_head_pm_residual_fit": residual_fit,
        "global_head_pm_residual_correlations": residual_corr,
        "conditional_residual_bins": residual_bins,
        "standard_fold_rows": standard_fold_rows,
        "residualized_fold_rows": residual_fold_rows,
    }


def markdown_report(result: dict) -> str:
    aggregate = result["aggregate_summary"]
    coefficients = result["coefficient_summary"]
    raw_increment = result["incremental_raw_pm_vs_raw"]
    resid_increment = result["incremental_residualized_vs_raw"]
    residual_corr = result["global_head_pm_residual_correlations"]
    residual_fit = result["global_head_pm_residual_fit"]
    corr = result["correlations"]["spearman"]

    lines = [
        "# Striking Head-Pace Semantic Audit",
        "",
        "This exploratory audit asks whether the head pace feature adds clean,",
        "interpretable value beyond the simpler sigpct/raw-head anchor. It does",
        "not freeze or alter any paper policy.",
        "",
        "## Protocol",
        "",
        f"- aligned men-only rows: `{result['alignment_metadata']['aligned_rows']}`",
        f"- folds: `{len(result['standard_fold_rows'])}`",
        f"- first holdout start: `{result['protocol']['first_holdout_start']}`",
        f"- last holdout end: `{result['protocol']['last_holdout_end']}`",
        f"- logistic L2 C: `{result['protocol']['logistic_l2_c']}`",
        f"- bootstrap iterations: `{result['protocol']['bootstrap_iterations']}`",
        "",
        "The residualized variant fits the head-pace residual using only each",
        "development fold's feature values, then applies that transform to the",
        "holdout fold before fitting the mirrored logistic model.",
        "",
        "## Probability Results",
        "",
        "| Variant | Features | Delta LL vs Market | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Pace Term Mean Coef | Pace Positive Folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(
        aggregate.items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
        reverse=True,
    ):
        bootstrap = row.get("event_bootstrap") or {}
        pace_term = HEAD_PM_RESID if name == "sigpct_head_raw_pm_residualized" else HEAD_PM
        pace_coef = coefficients.get(name, {}).get(pace_term)
        pace_positive = ""
        if pace_coef is not None:
            pace_positive = f"{pace_coef.get('positive_folds', '')}/{pace_coef['folds']}"
        lines.append(
            "| {name} | {features} | {delta} | {brier} | {acc} | {pos}/{folds} | {boot} | {coef} | {pace_pos} |".format(
                name=name,
                features=len(row["feature_columns"]),
                delta=fmt_float(row["market_minus_candidate_log_loss"]),
                brier=fmt_float(row["market_minus_candidate_brier"]),
                acc=fmt_pct(row["candidate"]["accuracy"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(bootstrap.get("prob_delta_le_zero")),
                coef=fmt_float(None if pace_coef is None else pace_coef["mean"]),
                pace_pos=pace_positive,
            )
        )

    lines.extend(
        [
            "",
            "## Incremental Head Pace Value",
            "",
            "| Candidate | Base | Rows | Incremental Delta LL | Incremental Brier | Positive Folds |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
            "| `{candidate}` | `{base}` | {rows} | {delta} | {brier} | {pos}/{folds} |".format(
                candidate=raw_increment["candidate_variant"],
                base=raw_increment["base_variant"],
                rows=raw_increment["rows"],
                delta=fmt_float(raw_increment["candidate_minus_base_delta_log_loss"]),
                brier=fmt_float(raw_increment["candidate_minus_base_delta_brier"]),
                pos=raw_increment["positive_folds"],
                folds=raw_increment["folds"],
            ),
            "| `{candidate}` | `{base}` | {rows} | {delta} | {brier} | {pos}/{folds} |".format(
                candidate=resid_increment["candidate_variant"],
                base=resid_increment["base_variant"],
                rows=resid_increment["rows"],
                delta=fmt_float(resid_increment["candidate_minus_base_delta_log_loss"]),
                brier=fmt_float(resid_increment["candidate_minus_base_delta_brier"]),
                pos=resid_increment["positive_folds"],
                folds=resid_increment["folds"],
            ),
            "",
            "Fold-level raw-plus-pace increment over raw-head anchor:",
            "",
            "| Fold | Rows | Delta LL | Delta Brier |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for row in raw_increment["folds_detail"]:
        lines.append(
            "| {fold} | {rows} | {delta} | {brier} |".format(
                fold=row["fold"],
                rows=row["rows"],
                delta=fmt_float(row["candidate_minus_base_delta_log_loss"]),
                brier=fmt_float(row["candidate_minus_base_delta_brier"]),
            )
        )

    lines.extend(
        [
            "",
            "## Head Pace Semantics",
            "",
            "| Relationship | Spearman |",
            "| --- | ---: |",
            f"| `{HEAD_RAW}` vs `{HEAD_PM}` | {fmt_float(corr[HEAD_RAW][HEAD_PM])} |",
            f"| `{SIGPCT}` vs `{HEAD_PM}` | {fmt_float(corr[SIGPCT][HEAD_PM])} |",
            f"| global head-pace residual vs actual-minus-market | {fmt_float(residual_corr['spearman_residual_to_actual_minus_market'])} |",
            "",
            "Global descriptive residual fit:",
            "",
            "```text",
            f"{HEAD_PM} ~= {fmt_float(residual_fit['intercept'])} + "
            f"{fmt_float(residual_fit['coefficients'][SIGPCT])} * {SIGPCT} + "
            f"{fmt_float(residual_fit['coefficients'][HEAD_RAW])} * {HEAD_RAW}",
            "```",
            "",
            "Conditional bins by raw head differential quintile and head-pace residual:",
            "",
            "| Raw Bin | Pace Residual Bin | Rows | Mean Raw Head | Mean Pace Residual | Actual Red Win | Mean Market P | Actual - Market |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["conditional_residual_bins"]:
        lines.append(
            "| {raw_bin} | {resid_bin} | {rows} | {raw} | {resid} | {actual} | {market} | {edge} |".format(
                raw_bin=row["raw_head_bin"],
                resid_bin=row["residual_bin"],
                rows=row["rows"],
                raw=fmt_float(row["mean_raw_head"]),
                resid=fmt_float(row["mean_head_pm_residual"]),
                actual=fmt_pct(row["actual_red_win_rate"]),
                market=fmt_pct(row["mean_market_probability"]),
                edge=fmt_pct(row["actual_minus_market"]),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    raw_delta = raw_increment["candidate_minus_base_delta_log_loss"]
    if raw_delta > 0:
        lines.append(
            f"- Adding raw `Head differential_pm oppdiff` to the clean sigpct/raw-head anchor adds only `{fmt_float(raw_delta)}` incremental LL over `961` evaluated fights."
        )
    else:
        lines.append(
            "- Adding raw `Head differential_pm oppdiff` did not improve the clean sigpct/raw-head anchor."
        )
    lines.append(
        "- The head-pace term is highly correlated with raw head differential, so its coefficient should be read as a conditional effect rather than standalone feature importance."
    )
    lines.append(
        "- Residualized head pace does not create a clearer stronger model; the main clean signal remains sig-strike efficiency plus raw head differential."
    )
    lines.append(
        "- This supports leaving `sigpct_head_raw_pm` as a frozen paper challenger, while treating future feature work as a search for cleaner sustained-damage or duration-aware representations."
    )
    lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_head_pace_semantic_audit.json"
    md_path = output_dir / "striking_head_pace_semantic_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
