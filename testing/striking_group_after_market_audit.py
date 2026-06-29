#!/usr/bin/env python3
"""Grouped striking-feature audit after market control.

This is a discovery follow-up to the one-feature after-market signal audit. It
tests compact striking-differential groups with rolling prior-fold logistic
models, then compares them with market-only recalibration and the saved
selected-shrinkage residual probability on the same folds.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.feature_signal_after_market_audit import (  # noqa: E402
    EPS,
    binary_loss,
    event_bootstrap_delta,
    fit_predict_variant,
    fmt_float,
    fmt_p,
    fmt_pct,
    load_features,
    load_predictions,
    log_loss,
    merge_predictions_features,
)


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
DEFAULT_FEATURES = "data/detailed_fights.csv"
DEFAULT_OUTPUT_DIR = "test_results/striking_group_after_market_audit"


@dataclass(frozen=True)
class VariantSpec:
    name: str
    feature_columns: tuple[str, ...]
    note: str


def parse_args():
    parser = argparse.ArgumentParser(description="Audit grouped striking signals after market control")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--c", type=float, default=0.1)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def build_variants(df: pd.DataFrame) -> list[VariantSpec]:
    specs = [
        VariantSpec(
            "raw_sig_head_oppdiff",
            (
                "market_logit",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "raw significant-strike and head-strike differential oppdiffs",
        ),
        VariantSpec(
            "raw_sig_head_side_pairs",
            (
                "market_logit",
                "Red Sig. str. differential",
                "Blue Sig. str. differential",
                "Red Head differential",
                "Blue Head differential",
            ),
            "side-pair version of the same raw sig-str/head differential theme",
        ),
        VariantSpec(
            "pct_sig_head_distance",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head% differential oppdiff",
                "Distance% differential oppdiff",
            ),
            "percentage/rate proxy differentials that scored well one at a time",
        ),
        VariantSpec(
            "mixed_sig_head_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "best percentage proxy plus raw sig-str/head differential clues",
        ),
        VariantSpec(
            "raw_striking_diff_core",
            (
                "market_logit",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
                "Distance differential oppdiff",
                "Total str. differential oppdiff",
                "Ground differential oppdiff",
                "Clinch differential oppdiff",
            ),
            "raw striking and position differential core without percentage proxies",
        ),
        VariantSpec(
            "pct_striking_diff_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head% differential oppdiff",
                "Distance% differential oppdiff",
                "Body% differential oppdiff",
                "Clinch% differential oppdiff",
            ),
            "percentage/rate proxy striking differential core",
        ),
        VariantSpec(
            "all_positive_striking_clues",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
                "Head% differential oppdiff",
                "Distance% differential oppdiff",
                "Sig. str. differential oppdiff",
                "Ground differential oppdiff",
                "Total str. differential oppdiff",
                "Clinch% differential oppdiff",
                "Body% differential oppdiff",
                "Clinch differential oppdiff",
                "Distance differential oppdiff",
            ),
            "union of non-defense positive striking clues from the one-feature audit",
        ),
        VariantSpec(
            "defense_proxy_clues",
            (
                "market_logit",
                "Distance% defense oppdiff",
                "Leg% defense oppdiff",
                "Head% defense oppdiff",
                "Total str.% defense oppdiff",
            ),
            "target/position-mix defense proxies, separated from cleaner differentials",
        ),
        VariantSpec(
            "wrong_way_striking_control",
            (
                "market_logit",
                "Leg differential oppdiff",
                "KD differential oppdiff",
                "Head oppdiff",
                "Sig. str. oppdiff",
            ),
            "features that were weak or wrong-way in one-feature probes",
        ),
    ]
    available = set(df.columns)
    missing = {
        spec.name: [column for column in spec.feature_columns if column not in available]
        for spec in specs
    }
    missing = {name: columns for name, columns in missing.items() if columns}
    if missing:
        raise SystemExit(f"Missing planned feature columns: {missing}")
    return specs


def run_predictions(
    df: pd.DataFrame,
    variants: list[VariantSpec],
    c_value: float,
) -> tuple[pd.DataFrame, list[dict]]:
    folds = sorted(int(value) for value in df["fold"].unique())
    first_fold = min(folds)
    prediction_rows = []
    coefficient_rows = []
    baseline_columns = ("market_logit",)

    for fold in folds:
        if fold == first_fold:
            continue
        train_df = df[df["fold"] < fold].copy()
        eval_df = df[df["fold"] == fold].copy()
        baseline_probability, baseline_coefs = fit_predict_variant(
            train_df,
            eval_df,
            baseline_columns,
            c_value,
        )
        baseline_lookup = {
            int(index): float(probability)
            for index, probability in zip(eval_df.index.to_numpy(), baseline_probability)
        }
        coefficient_rows.append(
            {
                "fold": int(fold),
                "variant": "market_recalibrated",
                "coefficients": baseline_coefs,
            }
        )

        for variant in variants:
            probability, coefficients = fit_predict_variant(
                train_df,
                eval_df,
                variant.feature_columns,
                c_value,
            )
            coefficient_rows.append(
                {
                    "fold": int(fold),
                    "variant": variant.name,
                    "coefficients": coefficients,
                }
            )
            for row_index, candidate_probability in zip(eval_df.index.to_numpy(), probability):
                source = df.loc[row_index]
                prediction_rows.append(
                    {
                        "fold": int(fold),
                        "event_date": pd.Timestamp(source["event_date"]).date().isoformat(),
                        "fight_key": source["fight_key"],
                        "title": source["title"],
                        "red_fighter": source["red_fighter"],
                        "blue_fighter": source["blue_fighter"],
                        "red_won": int(source["red_won"]),
                        "market_probability": float(source["market_probability"]),
                        "baseline_probability": baseline_lookup[int(row_index)],
                        "selected_probability": (
                            float(source["selected_probability"])
                            if "selected_probability" in source.index
                            else None
                        ),
                        "fixed_half_probability": (
                            float(source["fixed_half_probability"])
                            if "fixed_half_probability" in source.index
                            else None
                        ),
                        "variant": variant.name,
                        "candidate_probability": float(candidate_probability),
                    }
                )

    return pd.DataFrame(prediction_rows), coefficient_rows


def coefficient_summary(coefficient_rows: list[dict]) -> dict:
    values: dict[str, dict[str, list[float]]] = {}
    for row in coefficient_rows:
        variant = row["variant"]
        for feature, coefficient in row["coefficients"].items():
            values.setdefault(variant, {}).setdefault(feature, []).append(float(coefficient))

    summary = {}
    for variant, feature_values in values.items():
        summary[variant] = {}
        for feature, entries in feature_values.items():
            array = np.asarray(entries, dtype=float)
            summary[variant][feature] = {
                "folds": int(len(array)),
                "mean": float(np.mean(array)),
                "std": float(np.std(array)),
                "min": float(np.min(array)),
                "max": float(np.max(array)),
            }
    return summary


def summarize_candidate(
    rows: pd.DataFrame,
    probability_col: str,
    variant_name: str,
    bootstrap_iterations: int,
    rng,
) -> dict:
    y = rows["red_won"].astype(float).to_numpy()
    market = rows["market_probability"].astype(float).to_numpy()
    baseline = rows["baseline_probability"].astype(float).to_numpy()
    candidate = rows[probability_col].astype(float).to_numpy()
    market_loss = binary_loss(y, market)
    baseline_loss = binary_loss(y, baseline)
    candidate_loss = binary_loss(y, candidate)
    work = rows.copy()
    work["market_delta_log_loss"] = market_loss - candidate_loss
    work["incremental_delta_log_loss"] = baseline_loss - candidate_loss
    fold_deltas = [
        float(group["market_delta_log_loss"].mean())
        for _, group in work.groupby("fold", sort=True)
    ]
    fold_incremental = [
        float(group["incremental_delta_log_loss"].mean())
        for _, group in work.groupby("fold", sort=True)
    ]
    latest_fold = int(work["fold"].max())
    latest = work[work["fold"] == latest_fold]
    return {
        "variant": variant_name,
        "fights": int(len(work)),
        "events": int(work["event_date"].nunique()),
        "market_log_loss": log_loss(y, market),
        "baseline_log_loss": log_loss(y, baseline),
        "candidate_log_loss": log_loss(y, candidate),
        "market_delta_log_loss": float(np.mean(work["market_delta_log_loss"])),
        "incremental_delta_log_loss": float(np.mean(work["incremental_delta_log_loss"])),
        "positive_market_folds": int(sum(delta > 0.0 for delta in fold_deltas)),
        "positive_incremental_folds": int(sum(delta > 0.0 for delta in fold_incremental)),
        "folds": int(len(fold_deltas)),
        "fold_market_deltas": fold_deltas,
        "fold_incremental_deltas": fold_incremental,
        "latest_fold": latest_fold,
        "latest_market_delta_log_loss": float(latest["market_delta_log_loss"].mean()),
        "latest_incremental_delta_log_loss": float(latest["incremental_delta_log_loss"].mean()),
        "market_bootstrap": event_bootstrap_delta(work, "market_delta_log_loss", bootstrap_iterations, rng),
        "incremental_bootstrap": event_bootstrap_delta(
            work,
            "incremental_delta_log_loss",
            bootstrap_iterations,
            rng,
        ),
    }


def summarize_predictions(
    predictions: pd.DataFrame,
    variants: list[VariantSpec],
    bootstrap_iterations: int,
    rng,
) -> dict:
    base_rows = predictions.drop_duplicates("fight_key").copy()
    summaries = {}
    for variant in variants:
        rows = predictions[predictions["variant"] == variant.name].copy()
        summaries[variant.name] = summarize_candidate(
            rows,
            "candidate_probability",
            variant.name,
            bootstrap_iterations,
            rng,
        )
    references = {
        "market_recalibrated": summarize_candidate(
            base_rows,
            "baseline_probability",
            "market_recalibrated",
            bootstrap_iterations,
            rng,
        )
    }
    if "selected_probability" in base_rows.columns and base_rows["selected_probability"].notna().all():
        references["selected_shrinkage"] = summarize_candidate(
            base_rows,
            "selected_probability",
            "selected_shrinkage",
            bootstrap_iterations,
            rng,
        )
    if "fixed_half_probability" in base_rows.columns and base_rows["fixed_half_probability"].notna().all():
        references["fixed_half_residual"] = summarize_candidate(
            base_rows,
            "fixed_half_probability",
            "fixed_half_residual",
            bootstrap_iterations,
            rng,
        )
    return {
        "summaries": summaries,
        "references": references,
    }


def run_predictions_for_labels(
    df: pd.DataFrame,
    variants: list[VariantSpec],
    c_value: float,
    labels: np.ndarray,
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    simulated = df.copy()
    simulated["red_won"] = labels.astype(int)
    predictions, _ = run_predictions(simulated, variants, c_value)
    result = {}
    for variant in variants:
        rows = predictions[predictions["variant"] == variant.name]
        result[variant.name] = (
            rows["red_won"].astype(float).to_numpy(),
            rows["market_probability"].astype(float).to_numpy(),
            rows["baseline_probability"].astype(float).to_numpy(),
            rows["candidate_probability"].astype(float).to_numpy(),
        )
    return result


def market_null_simulation(
    df: pd.DataFrame,
    variants: list[VariantSpec],
    observed: dict,
    c_value: float,
    iterations: int,
    rng,
) -> dict | None:
    if iterations <= 0:
        return None
    market = np.clip(df["market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    values = {
        variant.name: {
            "market_delta": np.empty(iterations, dtype=float),
            "incremental_delta": np.empty(iterations, dtype=float),
        }
        for variant in variants
    }
    for iteration in range(iterations):
        labels = (rng.random(len(df)) < market).astype(int)
        simulated = run_predictions_for_labels(df, variants, c_value, labels)
        for variant in variants:
            y, raw_market, baseline, candidate = simulated[variant.name]
            values[variant.name]["market_delta"][iteration] = float(
                np.mean(binary_loss(y, raw_market) - binary_loss(y, candidate))
            )
            values[variant.name]["incremental_delta"][iteration] = float(
                np.mean(binary_loss(y, baseline) - binary_loss(y, candidate))
            )

    result = {}
    for variant in variants:
        row = observed["summaries"][variant.name]
        market_values = values[variant.name]["market_delta"]
        incremental_values = values[variant.name]["incremental_delta"]
        result[variant.name] = {
            "iterations": int(iterations),
            "market_delta_null_mean": float(np.mean(market_values)),
            "market_delta_null_ci_95": [float(value) for value in np.percentile(market_values, [2.5, 97.5])],
            "market_delta_p_value": float(
                (np.sum(market_values >= row["market_delta_log_loss"]) + 1) / (iterations + 1)
            ),
            "incremental_delta_null_mean": float(np.mean(incremental_values)),
            "incremental_delta_null_ci_95": [
                float(value) for value in np.percentile(incremental_values, [2.5, 97.5])
            ],
            "incremental_delta_p_value": float(
                (np.sum(incremental_values >= row["incremental_delta_log_loss"]) + 1)
                / (iterations + 1)
            ),
        }
    return result


def variant_metadata(variants: list[VariantSpec]) -> list[dict]:
    return [
        {
            "name": variant.name,
            "feature_columns": list(variant.feature_columns),
            "note": variant.note,
        }
        for variant in variants
    ]


def markdown_table_summary(result: dict) -> list[str]:
    null = result.get("market_null") or {}
    lines = [
        "| Variant | Features | Market Delta LL | Inc Delta vs Recal | Positive Market Folds | Boot P(inc<=0) | Null p(market) | Null p(inc) | Latest Inc Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows = sorted(
        result["summaries"].items(),
        key=lambda item: item[1]["incremental_delta_log_loss"],
        reverse=True,
    )
    feature_counts = {
        variant["name"]: len(variant["feature_columns"])
        for variant in result["variants"]
    }
    for name, summary in rows:
        boot = summary.get("incremental_bootstrap") or {}
        null_row = null.get(name) or {}
        lines.append(
            "| {name} | {features} | {market_delta} | {inc_delta} | {pos} / {folds} | {boot} | {null_market} | {null_inc} | {latest} |".format(
                name=name,
                features=feature_counts.get(name, 0),
                market_delta=fmt_float(summary["market_delta_log_loss"]),
                inc_delta=fmt_float(summary["incremental_delta_log_loss"]),
                pos=summary["positive_market_folds"],
                folds=summary["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
                null_market=fmt_p(null_row.get("market_delta_p_value")),
                null_inc=fmt_p(null_row.get("incremental_delta_p_value")),
                latest=fmt_float(summary["latest_incremental_delta_log_loss"]),
            )
        )
    return lines


def markdown_reference_table(result: dict) -> list[str]:
    lines = [
        "| Reference | Fights | Candidate LL | Market Delta LL | Inc Delta vs Recal | Positive Market Folds | Boot P(market<=0) | Latest Market Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in result["references"].items():
        boot = summary.get("market_bootstrap") or {}
        lines.append(
            "| {name} | {fights} | {ll} | {market_delta} | {inc_delta} | {pos} / {folds} | {boot} | {latest} |".format(
                name=name,
                fights=summary["fights"],
                ll=fmt_float(summary["candidate_log_loss"]),
                market_delta=fmt_float(summary["market_delta_log_loss"]),
                inc_delta=fmt_float(summary["incremental_delta_log_loss"]),
                pos=summary["positive_market_folds"],
                folds=summary["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
                latest=fmt_float(summary["latest_market_delta_log_loss"]),
            )
        )
    return lines


def markdown_coefficients(result: dict, best_name: str) -> list[str]:
    coefficients = result.get("coefficient_summary", {}).get(best_name, {})
    lines = [
        "| Feature | Mean Coef | Min | Max |",
        "| --- | ---: | ---: | ---: |",
    ]
    for feature, summary in sorted(
        coefficients.items(),
        key=lambda item: abs(item[1]["mean"]),
        reverse=True,
    ):
        lines.append(
            "| `{feature}` | {mean} | {minv} | {maxv} |".format(
                feature=feature,
                mean=fmt_float(summary["mean"]),
                minv=fmt_float(summary["min"]),
                maxv=fmt_float(summary["max"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    best_name, best_summary = max(
        result["summaries"].items(),
        key=lambda item: item[1]["incremental_delta_log_loss"],
    )
    selected = result["references"].get("selected_shrinkage")
    lines = [
        "# Striking Group After Market Audit",
        "",
        "This discovery audit tests whether the one-feature striking-differential",
        "clues survive as compact grouped models after market control. Each",
        "candidate is a rolling prior-fold logistic model with red/blue mirrored",
        "training and mirrored holdout averaging. It is not a promoted feature",
        "set or betting policy.",
        "",
        "## Protocol",
        "",
        f"- predictions: `{result['paths']['predictions']}`",
        f"- features: `{result['paths']['features']}`",
        f"- merged rows: `{result['merged_rows']}`",
        f"- rolling eval folds: `{', '.join(str(value) for value in result['rolling_eval_folds'])}`",
        f"- rolling eval fights: `{result['reference_rows']}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- bootstrap iterations: `{result['parameters']['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['parameters']['market_null_iterations']}`",
        "",
        "## References On Same Folds",
        "",
        *markdown_reference_table(result),
        "",
        "## Grouped Striking Results",
        "",
        *markdown_table_summary(result),
        "",
        f"## Best Group Coefficients: `{best_name}`",
        "",
        *markdown_coefficients(result, best_name),
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

    best_null = (result.get("market_null") or {}).get(best_name, {})
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Best grouped candidate by incremental log loss: `{best_name}` with market Delta LL `{fmt_float(best_summary['market_delta_log_loss'])}` and incremental Delta LL `{fmt_float(best_summary['incremental_delta_log_loss'])}`.",
            f"- Its event-bootstrap `P(incremental delta <= 0)` is `{fmt_p((best_summary.get('incremental_bootstrap') or {}).get('prob_delta_le_zero'))}`; market-null p-values are `{fmt_p(best_null.get('market_delta_p_value'))}` versus raw market and `{fmt_p(best_null.get('incremental_delta_p_value'))}` versus market recalibration.",
        ]
    )
    if selected:
        gap = best_summary["market_delta_log_loss"] - selected["market_delta_log_loss"]
        lines.append(
            f"- On the same folds, selected-shrinkage residual Delta LL is `{fmt_float(selected['market_delta_log_loss'])}`; the best grouped candidate is `{fmt_float(gap)}` relative to that reference."
        )
    if best_summary["incremental_delta_log_loss"] <= 0:
        lines.append("- The grouped striking variants do not improve on market-only recalibration.")
    elif (best_null.get("incremental_delta_p_value") or 1.0) > 0.05:
        lines.append(
            "- The grouped result is useful feature-forensics evidence, but it does not clear a market-null validation bar."
        )
    else:
        lines.append(
            "- This clears the unadjusted market-null screen, but it is still post-hoc discovery evidence and would need a predeclared leak-safe model/backtest before promotion."
        )
    lines.append(
        "- The practical next step is not broad feature expansion; it is a narrow, predeclared redesign/backtest of striking-differential features if we choose to pursue this clue."
    )
    lines.append("")
    return "\n".join(lines)


def run_audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    predictions = load_predictions(args.predictions)
    features = load_features(args.features)
    df = merge_predictions_features(predictions, features)
    df = df.sort_values(["event_date", "fight_key"]).reset_index(drop=True)
    variants = build_variants(df)
    prediction_rows, coefficient_rows = run_predictions(df, variants, args.c)
    summary = summarize_predictions(prediction_rows, variants, args.bootstrap_iterations, rng)
    market_null = market_null_simulation(
        df,
        variants,
        summary,
        args.c,
        args.market_null_iterations,
        rng,
    )
    base_rows = prediction_rows.drop_duplicates("fight_key")
    result = {
        "paths": {
            "predictions": args.predictions,
            "features": args.features,
        },
        "parameters": {
            "c": args.c,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "seed": args.seed,
        },
        "merged_rows": int(len(df)),
        "folds_available": sorted(int(value) for value in df["fold"].unique()),
        "rolling_eval_folds": sorted(int(value) for value in base_rows["fold"].unique()),
        "reference_rows": int(len(base_rows)),
        "variants": variant_metadata(variants),
        "summaries": summary["summaries"],
        "references": summary["references"],
        "market_null": market_null,
        "coefficient_summary": coefficient_summary(coefficient_rows),
    }
    return result


def main():
    args = parse_args()
    result = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_group_after_market_audit.json"
    md_path = output_dir / "striking_group_after_market_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
