#!/usr/bin/env python3
"""Summarize the uncapped residual-after-market alpha evidence.

This report deliberately treats per-event caps as a risk/exposure overlay,
not as the fundamental alpha. It reads saved leak-safe audit artifacts and
summarizes the probability signal, calibration diagnostics, uncapped PnL
translation, recent stress, and universe handling.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PREDICTIONS = "test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv"
DEFAULT_MARKET_META = "test_results/market_residual_meta_audit/market_residual_meta_audit.json"
DEFAULT_SHRINKAGE = "test_results/residual_shrinkage_audit/residual_shrinkage_audit.json"
DEFAULT_RECENT_STRESS = "test_results/residual_recent_stress_audit/residual_recent_stress_audit.json"
DEFAULT_SHRINKAGE_PNL = "test_results/residual_shrinkage_fixed_pnl_audit/residual_shrinkage_fixed_pnl_audit.json"
DEFAULT_OUTCOME_UNIVERSE = "test_results/outcome_universe_audit/outcome_universe_audit.json"
DEFAULT_OUTPUT_DIR = "test_results/residual_uncapped_alpha_audit"

META_PNL_OBJECTIVES = {
    "profit": "test_results/residual_meta_pnl_audit/profit_objective/residual_meta_pnl_audit.json",
    "ROI": "test_results/residual_meta_pnl_audit/roi_objective/residual_meta_pnl_audit.json",
    "actual - market": "test_results/residual_meta_pnl_audit/market_edge_objective/residual_meta_pnl_audit.json",
    "fixed edge>=0.02, p>=0.60": (
        "test_results/residual_meta_pnl_audit/fixed_edge02_prob60/residual_meta_pnl_audit.json"
    ),
}

PROBABILITY_COLUMNS = {
    "market": "market_probability",
    "selected_shrinkage": "selected_probability",
    "fixed_half_residual": "fixed_half_probability",
    "unshrunk_meta": "unshrunk_probability",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize uncapped residual alpha evidence")
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--market-meta", default=DEFAULT_MARKET_META)
    parser.add_argument("--shrinkage", default=DEFAULT_SHRINKAGE)
    parser.add_argument("--recent-stress", default=DEFAULT_RECENT_STRESS)
    parser.add_argument("--shrinkage-pnl", default=DEFAULT_SHRINKAGE_PNL)
    parser.add_argument("--outcome-universe", default=DEFAULT_OUTCOME_UNIVERSE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: str | Path) -> dict:
    with Path(path).open() as file:
        return json.load(file)


def fmt_float(value, digits=4) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


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


def bonferroni(value, tests: int) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return min(1.0, float(value) * tests)


def probability_clip(values: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 1e-6, 1.0 - 1e-6)


def logit(values: np.ndarray) -> np.ndarray:
    p = probability_clip(values)
    return np.log(p / (1.0 - p))


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))


def binary_log_loss(y_true: np.ndarray, probability: np.ndarray) -> float:
    p = probability_clip(probability)
    y = np.asarray(y_true, dtype=float)
    return float(np.mean(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))))


def brier_score(y_true: np.ndarray, probability: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probability, dtype=float)
    return float(np.mean((p - y) ** 2))


def calibration_intercept_slope(y_true: np.ndarray, probability: np.ndarray) -> tuple[float | None, float | None]:
    y = np.asarray(y_true, dtype=float)
    if len(np.unique(y)) < 2:
        return None, None
    x = np.column_stack([np.ones(len(y)), logit(probability)])
    beta = np.array([0.0, 1.0], dtype=float)
    ridge = np.eye(2) * 1e-6
    for _ in range(50):
        mu = sigmoid(x @ beta)
        weights = np.clip(mu * (1.0 - mu), 1e-8, None)
        hessian = x.T @ (weights[:, None] * x) + ridge
        gradient = x.T @ (y - mu)
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        beta = beta + step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return float(beta[0]), float(beta[1])


def calibration_bins(y_true: np.ndarray, probability: np.ndarray, bins: int = 10) -> tuple[list[dict], float, float]:
    y = np.asarray(y_true, dtype=float)
    p = probability_clip(probability)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows = []
    weighted_abs_gap = 0.0
    max_gap = 0.0
    for index in range(bins):
        left = edges[index]
        right = edges[index + 1]
        if index == bins - 1:
            mask = (p >= left) & (p <= right)
        else:
            mask = (p >= left) & (p < right)
        count = int(mask.sum())
        if count == 0:
            continue
        mean_prediction = float(p[mask].mean())
        actual_rate = float(y[mask].mean())
        gap = actual_rate - mean_prediction
        weighted_abs_gap += count * abs(gap)
        max_gap = max(max_gap, abs(gap))
        rows.append(
            {
                "bin": f"{left:.1f}-{right:.1f}",
                "count": count,
                "mean_prediction": mean_prediction,
                "actual_rate": actual_rate,
                "actual_minus_prediction": gap,
            }
        )
    ece = weighted_abs_gap / len(y) if len(y) else math.nan
    return rows, float(ece), float(max_gap)


def summarize_probability(df: pd.DataFrame, name: str, column: str) -> dict:
    y = df["red_won"].astype(float).to_numpy()
    p = df[column].astype(float).to_numpy()
    intercept, slope = calibration_intercept_slope(y, p)
    bins, ece, max_gap = calibration_bins(y, p)
    return {
        "policy": name,
        "fights": int(len(df)),
        "mean_prediction": float(np.mean(p)),
        "actual_rate": float(np.mean(y)),
        "actual_minus_prediction": float(np.mean(y) - np.mean(p)),
        "accuracy": float(np.mean((p >= 0.5) == (y >= 0.5))),
        "log_loss": binary_log_loss(y, p),
        "brier": brier_score(y, p),
        "calibration_intercept": intercept,
        "calibration_slope": slope,
        "ece_10bin": ece,
        "max_10bin_gap": max_gap,
        "bins": bins,
    }


def residual_sign_buckets(df: pd.DataFrame, column: str) -> list[dict]:
    work = df.copy()
    work["candidate_minus_market"] = work[column].astype(float) - work["market_probability"].astype(float)
    bins = [-np.inf, -0.05, -0.02, 0.02, 0.05, np.inf]
    labels = ["<= -5%", "-5% to -2%", "-2% to +2%", "+2% to +5%", ">= +5%"]
    work["bucket"] = pd.cut(work["candidate_minus_market"], bins=bins, labels=labels)
    rows = []
    for label, subset in work.groupby("bucket", observed=True):
        y = subset["red_won"].astype(float).to_numpy()
        market = subset["market_probability"].astype(float).to_numpy()
        candidate = subset[column].astype(float).to_numpy()
        rows.append(
            {
                "bucket": str(label),
                "fights": int(len(subset)),
                "mean_candidate_minus_market": float(np.mean(candidate - market)),
                "actual_minus_market": float(np.mean(y - market)),
                "actual_minus_candidate": float(np.mean(y - candidate)),
                "delta_log_loss": binary_log_loss(y, market) - binary_log_loss(y, candidate),
            }
        )
    return rows


def probability_evidence(market_meta: dict, shrinkage: dict) -> list[dict]:
    rows = []
    regularized = market_meta["observed"]["variants"]["market_plus_regularized_lgbm"]
    market_null = market_meta.get("market_null", {}).get("market_plus_regularized_lgbm", {})
    rows.append(
        {
            "test": "market + regularized residual meta",
            "fights": regularized["market"]["fights"],
            "market_log_loss": regularized["market"]["log_loss"],
            "candidate_log_loss": regularized["meta"]["log_loss"],
            "delta_log_loss": regularized["market_minus_meta_log_loss"],
            "delta_brier": regularized["market_minus_meta_brier"],
            "positive_folds": regularized["positive_folds"],
            "folds": regularized["folds"],
            "bootstrap_p_delta_le_zero": regularized["event_bootstrap"]["prob_delta_le_zero"],
            "market_null_p": market_null.get("p_value_observed_or_better"),
            "correction_family": 4,
        }
    )

    shrinkage_null = shrinkage.get("market_null", {})
    for policy in ["selected_shrinkage", "fixed_half_residual", "unshrunk_meta"]:
        summary = shrinkage["summary"][policy]
        rows.append(
            {
                "test": policy,
                "fights": summary["fights"],
                "market_log_loss": shrinkage["summary"]["market"]["log_loss"],
                "candidate_log_loss": summary["log_loss"],
                "delta_log_loss": summary["market_minus_candidate_log_loss"],
                "delta_brier": summary["market_minus_candidate_brier"],
                "positive_folds": summary["positive_folds"],
                "folds": summary["folds"],
                "bootstrap_p_delta_le_zero": summary["event_bootstrap"]["prob_delta_le_zero"],
                "market_null_p": shrinkage_null.get(policy, {}).get("p_value_observed_or_better"),
                "correction_family": 3,
            }
        )
    for row in rows:
        row["bonferroni_p"] = bonferroni(row.get("market_null_p"), row["correction_family"])
    return rows


def recent_probability_stress(recent_stress: dict) -> list[dict]:
    wanted = {"aggregate", "post_2024", "last_365d", "latest_fold"}
    rows = []
    for period in recent_stress["probability_periods"]:
        if period["name"] not in wanted:
            continue
        for policy in period["policies"]:
            rows.append(
                {
                    "period": period["label"],
                    "policy": policy["policy"],
                    "fights": policy["fights"],
                    "delta_log_loss": policy["delta_log_loss"],
                    "bootstrap_p_delta_le_zero": policy["event_bootstrap_p_delta_le_zero"],
                    "market_null_p": policy["market_null_p_observed_or_better"],
                }
            )
    return rows


def meta_pnl_rows() -> list[dict]:
    rows = []
    for objective, path in META_PNL_OBJECTIVES.items():
        data = load_json(path)
        aggregate = data["aggregate"]
        market_null = data.get("market_null") or {}
        bootstrap = data.get("event_bootstrap") or {}
        inspected = 3 if objective != "fixed edge>=0.02, p>=0.60" else 1
        rows.append(
            {
                "family": "residual meta threshold selection",
                "objective": objective,
                "bets": aggregate["bets"],
                "profit": aggregate["profit"],
                "roi": aggregate["roi"],
                "actual_minus_market": aggregate["actual_minus_market"],
                "positive_folds": aggregate["positive_folds"],
                "folds": aggregate["folds"],
                "market_null_p": market_null.get("p_value_observed_or_better"),
                "bootstrap_p_profit_le_zero": bootstrap.get("prob_profit_le_zero"),
                "correction_family": inspected,
                "bonferroni_p": bonferroni(market_null.get("p_value_observed_or_better"), inspected),
            }
        )
    return rows


def shrinkage_pnl_rows(shrinkage_pnl: dict) -> list[dict]:
    rows = []
    for policy, summary in shrinkage_pnl["policies"].items():
        market_null = summary.get("market_null") or {}
        bootstrap = summary.get("event_bootstrap") or {}
        rows.append(
            {
                "family": "fixed uncapped shrinkage thresholds",
                "objective": policy,
                "bets": summary["bets"],
                "profit": summary["profit"],
                "roi": summary["roi"],
                "actual_minus_market": summary["actual_minus_market"],
                "positive_folds": summary["positive_folds"],
                "folds": summary["folds_with_bets"],
                "market_null_p": market_null.get("p_value_observed_or_better"),
                "bootstrap_p_profit_le_zero": bootstrap.get("prob_profit_le_zero"),
                "correction_family": 3,
                "bonferroni_p": bonferroni(market_null.get("p_value_observed_or_better"), 3),
            }
        )
    return rows


def outcome_universe_summary(outcome_universe: dict) -> dict:
    datasets = {item["path"]: item for item in outcome_universe["datasets"]}
    state = outcome_universe["non_binary_state_audit"]
    features = datasets.get("data/detailed_fights.csv", {})
    source = datasets.get("data/modified_fight_details.csv", {})
    return {
        "feature_rows": features.get("rows"),
        "feature_women_title_rows": features.get("women_title_rows"),
        "feature_known_women_pair_rows": features.get("known_women_pair_rows"),
        "feature_non_binary_result_rows": features.get("non_binary_result_rows"),
        "source_non_binary_or_blank_winner_rows": source.get("non_binary_or_blank_winner_rows"),
        "fighter_side_rows_checked": state["fighter_side_feature_rows_with_prior_non_binary"],
        "totalfights_matches": state["matched_totalfights_including_non_binary"],
        "last_fight_checks": state["latest_prior_non_binary_last_fight_checks"],
        "last_fight_matches": state["latest_prior_non_binary_last_fight_matches"],
        "weighted_stat_checks": state["weighted_stat_checks_with_non_binary_impact"],
        "weighted_stat_matches": state["weighted_stat_matches_including_non_binary"],
    }


def table_probability_metrics(rows: list[dict]) -> list[str]:
    lines = [
        "| Policy | LL | Brier | Accuracy | Calibration Intercept | Calibration Slope | ECE 10-bin | Max Bin Gap | Actual - Pred |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {policy} | {ll} | {brier} | {acc} | {intercept} | {slope} | {ece} | {max_gap} | {actual_gap} |".format(
                policy=row["policy"],
                ll=fmt_float(row["log_loss"]),
                brier=fmt_float(row["brier"]),
                acc=fmt_pct(row["accuracy"]),
                intercept=fmt_float(row["calibration_intercept"]),
                slope=fmt_float(row["calibration_slope"]),
                ece=fmt_pct(row["ece_10bin"]),
                max_gap=fmt_pct(row["max_10bin_gap"]),
                actual_gap=fmt_pct(row["actual_minus_prediction"]),
            )
        )
    return lines


def table_probability_evidence(rows: list[dict]) -> list[str]:
    lines = [
        "| Test | Fights | Market LL | Candidate LL | Delta LL | Delta Brier | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p | Corrected p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {test} | {fights} | {market_ll} | {candidate_ll} | {delta_ll} | {delta_brier} | {positive} / {folds} | {boot} | {null_p} | {corrected} |".format(
                test=row["test"],
                fights=row["fights"],
                market_ll=fmt_float(row["market_log_loss"]),
                candidate_ll=fmt_float(row["candidate_log_loss"]),
                delta_ll=fmt_float(row["delta_log_loss"]),
                delta_brier=fmt_float(row["delta_brier"]),
                positive=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(row["bootstrap_p_delta_le_zero"]),
                null_p=fmt_p(row["market_null_p"]),
                corrected=fmt_p(row["bonferroni_p"]),
            )
        )
    return lines


def table_recent_stress(rows: list[dict]) -> list[str]:
    lines = [
        "| Period | Policy | Fights | Delta LL | Bootstrap P(delta <= 0) | Market-Null p |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {period} | {policy} | {fights} | {delta} | {boot} | {null_p} |".format(
                period=row["period"],
                policy=row["policy"],
                fights=row["fights"],
                delta=fmt_float(row["delta_log_loss"]),
                boot=fmt_p(row["bootstrap_p_delta_le_zero"]),
                null_p=fmt_p(row["market_null_p"]),
            )
        )
    return lines


def table_pnl(rows: list[dict]) -> list[str]:
    lines = [
        "| Family | Policy / Objective | Bets | Profit | ROI | Actual - Market | Positive Folds | Market-Null p | Corrected p | Bootstrap P(profit <= 0) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {family} | {objective} | {bets} | {profit} | {roi} | {actual_market} | {positive} / {folds} | {null_p} | {corrected} | {boot} |".format(
                family=row["family"],
                objective=row["objective"],
                bets=row["bets"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                positive=row["positive_folds"],
                folds=row["folds"],
                null_p=fmt_p(row["market_null_p"]),
                corrected=fmt_p(row["bonferroni_p"]),
                boot=fmt_p(row["bootstrap_p_profit_le_zero"]),
            )
        )
    return lines


def table_residual_buckets(rows: list[dict]) -> list[str]:
    lines = [
        "| Selected Residual Bucket | Fights | Mean Candidate - Market | Actual - Market | Actual - Candidate | Delta LL |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {bucket} | {fights} | {edge} | {actual_market} | {actual_candidate} | {delta} |".format(
                bucket=row["bucket"],
                fights=row["fights"],
                edge=fmt_pct(row["mean_candidate_minus_market"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                actual_candidate=fmt_pct(row["actual_minus_candidate"]),
                delta=fmt_float(row["delta_log_loss"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    universe = result["outcome_universe"]
    lines = [
        "# Residual Uncapped Alpha Audit",
        "",
        "This report reframes the current evidence around uncapped residual alpha.",
        "A per-event cap is treated as an exposure/risk overlay, not as the",
        "fundamental alpha claim.",
        "",
        "## Bottom Line",
        "",
        "- The best current alpha is a weak historical model-after-market probability residual, not an event-cap betting rule.",
        "- The probability evidence is directionally positive on aggregate, especially selected shrinkage, but recent 2026/last-365-day slices are negative.",
        "- Uncapped flat-bet PnL is positive but statistically fragile: corrected market-null p-values and event-bootstrap intervals do not support a live staking claim.",
        "- The production universe/no-contest handling is already aligned with the requested policy: no women's fights in production training/evaluation, while non-binary bouts update future fighter state but are not supervised labels.",
        "",
        "## Inputs",
        "",
        f"- predictions: `{result['paths']['predictions']}`",
        f"- market residual meta: `{result['paths']['market_meta']}`",
        f"- residual shrinkage: `{result['paths']['shrinkage']}`",
        f"- recent stress: `{result['paths']['recent_stress']}`",
        f"- shrinkage fixed PnL: `{result['paths']['shrinkage_pnl']}`",
        f"- outcome universe: `{result['paths']['outcome_universe']}`",
        "",
        "## Probability Metrics",
        "",
        "Lower log loss is useful because it is a proper scoring rule, but it is",
        "not sufficient by itself. The table also tracks Brier score, directional",
        "accuracy, calibration slope/intercept, and reliability-style bin gaps.",
        "",
        *table_probability_metrics(result["probability_metrics"]),
        "",
        "## Probability Evidence After Market Control",
        "",
        "`Delta LL` is market log loss minus candidate log loss; positive means the",
        "candidate improved over de-vigged market probability on future holdouts.",
        "",
        *table_probability_evidence(result["probability_evidence"]),
        "",
        "## Selected-Shrinkage Residual Buckets",
        "",
        "These buckets check whether the model's signed disagreement with market",
        "corresponds to realized market error. If the residual is real, positive",
        "candidate-minus-market buckets should usually have positive actual-minus-market,",
        "and negative buckets should usually have negative actual-minus-market.",
        "",
        *table_residual_buckets(result["selected_shrinkage_residual_buckets"]),
        "",
        "## Recent Probability Stress",
        "",
        *table_recent_stress(result["recent_probability_stress"]),
        "",
        "## Uncapped PnL Translation",
        "",
        "These rows do not use a per-event cap. Positive historical PnL is useful",
        "as a translation check, but this is weaker than the probability evidence.",
        "",
        *table_pnl(result["uncapped_pnl"]),
        "",
        "## Universe And Non-Binary Outcome Handling",
        "",
        "| Check | Value |",
        "| --- | ---: |",
        f"| production feature rows | {universe['feature_rows']} |",
        f"| production women's title rows | {universe['feature_women_title_rows']} |",
        f"| production known women-pair rows | {universe['feature_known_women_pair_rows']} |",
        f"| supervised non-binary result rows | {universe['feature_non_binary_result_rows']} |",
        f"| retained source non-binary / blank-winner rows | {universe['source_non_binary_or_blank_winner_rows']} |",
        f"| future fighter-side rows with prior non-binary history checked | {universe['fighter_side_rows_checked']} |",
        f"| `totalfights` matches including non-binary bouts | {universe['totalfights_matches']} |",
        f"| `last_fight` checks after latest prior non-binary bout | {universe['last_fight_checks']} |",
        f"| `last_fight` matches | {universe['last_fight_matches']} |",
        f"| weighted stat checks affected by non-binary bouts | {universe['weighted_stat_checks']} |",
        f"| weighted stat matches including non-binary bouts | {universe['weighted_stat_matches']} |",
        "",
        "## Interpretation",
        "",
        "The current edge claim should be stated narrowly: the regularized model",
        "has historically provided a small residual probability signal after",
        "controlling for the market. The selected-shrinkage transform is the",
        "cleanest version of that claim because shrinkage was selected inside",
        "walk-forward development windows.",
        "",
        "That does not yet prove a live betting edge. The uncapped PnL checks are",
        "positive but fragile after objective/policy correction, recent probability",
        "stress is negative, and event-bootstrap uncertainty still crosses zero.",
        "Future work should focus on explaining the recent residual drift and on",
        "predeclared forward paper tracking. Per-event caps may still be useful",
        "for risk control, but they should not be presented as the alpha itself.",
        "",
    ]
    return "\n".join(lines)


def build_result(args) -> dict:
    predictions = pd.read_csv(args.predictions)
    market_meta = load_json(args.market_meta)
    shrinkage = load_json(args.shrinkage)
    recent_stress = load_json(args.recent_stress)
    shrinkage_pnl = load_json(args.shrinkage_pnl)
    outcome_universe = load_json(args.outcome_universe)

    probability_metrics = [
        summarize_probability(predictions, name, column)
        for name, column in PROBABILITY_COLUMNS.items()
    ]
    result = {
        "paths": {
            "predictions": args.predictions,
            "market_meta": args.market_meta,
            "shrinkage": args.shrinkage,
            "recent_stress": args.recent_stress,
            "shrinkage_pnl": args.shrinkage_pnl,
            "outcome_universe": args.outcome_universe,
        },
        "probability_metrics": probability_metrics,
        "probability_evidence": probability_evidence(market_meta, shrinkage),
        "selected_shrinkage_residual_buckets": residual_sign_buckets(
            predictions,
            PROBABILITY_COLUMNS["selected_shrinkage"],
        ),
        "recent_probability_stress": recent_probability_stress(recent_stress),
        "uncapped_pnl": [*meta_pnl_rows(), *shrinkage_pnl_rows(shrinkage_pnl)],
        "outcome_universe": outcome_universe_summary(outcome_universe),
    }
    return result


def main():
    args = parse_args()
    result = build_result(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_uncapped_alpha_audit.json"
    md_path = output_dir / "residual_uncapped_alpha_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
