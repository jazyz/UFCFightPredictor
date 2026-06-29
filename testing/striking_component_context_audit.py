#!/usr/bin/env python3
"""Component/context audit for the current striking alpha.

This diagnostic decomposes the current striking-core and pace-adjusted
challengers into fight-interpretable components: efficiency, raw count
differentials, pace-adjusted offense, and pace-adjusted defense. It keeps the
same market-aware rolling protocol and men-only universe as the frozen
striking paper policies.
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

from testing.market_aware_feature_audit import (  # noqa: E402
    VariantSpec,
    aggregate_predictions,
    aligned_market_feature_frame,
    market_null_simulation,
    run_observed_predictions,
)
from testing.market_residual_meta_audit import iter_folds  # noqa: E402
from testing.striking_feature_engineering_audit import (  # noqa: E402
    EDGE_THRESHOLD,
    add_pace_features,
    build_pace_features,
    fmt_float,
    fmt_p,
    fmt_pct,
    fmt_units,
    summarize_bets_for_variant,
)


DEFAULT_OUTPUT_DIR = "test_results/striking_component_context_audit"

COMPONENT_FEATURES = (
    "Sig. str.% differential oppdiff",
    "Sig. str. differential oppdiff",
    "Head differential oppdiff",
    "Sig. str. differential_pm oppdiff",
    "Head differential_pm oppdiff",
    "Sig. str. for_pm oppdiff",
    "Sig. str. against_pm oppdiff",
    "Head for_pm oppdiff",
    "Head against_pm oppdiff",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit striking components after market control")
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
    parser.add_argument("--market-null-iterations", type=int, default=300)
    parser.add_argument("--bet-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def expected_sign(feature: str) -> tuple[int | None, str]:
    if feature == "market_logit":
        return 1, "higher market logit should imply red is likelier to win"
    if "against_pm" in feature:
        return -1, "higher red absorbed pace versus blue should hurt red"
    if any(token in feature for token in ("differential", "for_pm")):
        return 1, "better red striking output/differential should help red"
    return None, "no strong predeclared sign"


def build_component_variants(df: pd.DataFrame) -> list[VariantSpec]:
    specs = [
        VariantSpec("market_recalibrated", ("market_logit",), "market-logit-only recalibration baseline"),
        VariantSpec(
            "current_sigpct_head",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential oppdiff",
            ),
            "current compact sigpct/head challenger",
        ),
        VariantSpec(
            "current_mixed_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential oppdiff",
                "Head differential oppdiff",
            ),
            "current mixed raw-count striking core",
        ),
        VariantSpec(
            "pace_adjusted_mixed_core",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential_pm oppdiff",
                "Head differential_pm oppdiff",
            ),
            "frozen pace-adjusted challenger",
        ),
        VariantSpec(
            "pace_offense_split",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. for_pm oppdiff",
                "Head for_pm oppdiff",
            ),
            "pace-adjusted offensive output split",
        ),
        VariantSpec(
            "pace_defense_split",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. against_pm oppdiff",
                "Head against_pm oppdiff",
            ),
            "pace-adjusted absorbed-strike defense split",
        ),
        VariantSpec(
            "pace_for_against_split",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. for_pm oppdiff",
                "Sig. str. against_pm oppdiff",
                "Head for_pm oppdiff",
                "Head against_pm oppdiff",
            ),
            "pace-adjusted offense and defense split",
        ),
        VariantSpec(
            "pace_sigpm_only",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Sig. str. differential_pm oppdiff",
            ),
            "sigpct plus significant-strike pace differential",
        ),
        VariantSpec(
            "pace_headpm_only",
            (
                "market_logit",
                "Sig. str.% differential oppdiff",
                "Head differential_pm oppdiff",
            ),
            "sigpct plus head-strike pace differential",
        ),
        VariantSpec(
            "sigpct_only",
            ("market_logit", "Sig. str.% differential oppdiff"),
            "significant-strike efficiency only",
        ),
        VariantSpec(
            "raw_head_only",
            ("market_logit", "Head differential oppdiff"),
            "raw head-strike count differential only",
        ),
        VariantSpec(
            "raw_sig_only",
            ("market_logit", "Sig. str. differential oppdiff"),
            "raw significant-strike count differential only",
        ),
    ]
    available = set(df.columns)
    missing = {
        spec.name: [column for column in spec.feature_columns if column not in available]
        for spec in specs
    }
    missing = {name: columns for name, columns in missing.items() if columns}
    if missing:
        raise SystemExit(f"Missing component feature columns: {missing}")
    return specs


def prepare_augmented_frame(args) -> tuple[pd.DataFrame, dict, list]:
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
        raise SystemExit("No rolling folds available for the requested protocol")
    metadata.update(pace_metadata)
    metadata["pace_reconstruction"] = pace_reconstruction
    metadata["source_fights_path"] = args.source_fights
    return aligned, metadata, folds


def component_distribution(aligned: pd.DataFrame) -> dict:
    rows = {}
    for feature in COMPONENT_FEATURES:
        values = pd.to_numeric(aligned[feature], errors="coerce")
        finite = values[np.isfinite(values)]
        sign, sign_note = expected_sign(feature)
        rows[feature] = {
            "rows": int(len(values)),
            "non_missing": int(values.notna().sum()),
            "missing": int(values.isna().sum()),
            "mean": None if finite.empty else float(finite.mean()),
            "std": None if finite.empty else float(finite.std()),
            "p01": None if finite.empty else float(finite.quantile(0.01)),
            "p50": None if finite.empty else float(finite.quantile(0.50)),
            "p99": None if finite.empty else float(finite.quantile(0.99)),
            "expected_sign": sign,
            "expected_sign_note": sign_note,
        }
    return rows


def quantile_shape(aligned: pd.DataFrame, feature: str, bins: int) -> dict:
    values = pd.to_numeric(aligned[feature], errors="coerce")
    residual = aligned["red_won"].astype(float) - aligned["red_market_probability"].astype(float)
    valid = values.notna() & residual.notna()
    sign, _ = expected_sign(feature)
    if valid.sum() < bins * 20 or values[valid].nunique() < bins:
        return {
            "feature": feature,
            "rows": int(valid.sum()),
            "bins": [],
            "spearman_to_actual_minus_market": None,
            "high_minus_low_actual_minus_market": None,
            "aligned_high_minus_low_actual_minus_market": None,
        }
    ranks = values[valid].rank(method="first")
    groups = pd.qcut(ranks, q=bins, labels=False, duplicates="drop")
    work = aligned.loc[valid, ["red_won", "red_market_probability"]].copy()
    work["_value"] = values[valid].to_numpy()
    work["_bin"] = groups.to_numpy()
    work["_residual"] = residual[valid].to_numpy()
    bin_rows = []
    for group, subset in work.groupby("_bin", sort=True):
        bin_rows.append(
            {
                "bin": int(group) + 1,
                "rows": int(len(subset)),
                "feature_min": float(subset["_value"].min()),
                "feature_max": float(subset["_value"].max()),
                "actual_red_win_rate": float(subset["red_won"].astype(float).mean()),
                "mean_market_probability": float(subset["red_market_probability"].astype(float).mean()),
                "actual_minus_market": float(subset["_residual"].mean()),
            }
        )
    low = bin_rows[0]["actual_minus_market"] if bin_rows else None
    high = bin_rows[-1]["actual_minus_market"] if bin_rows else None
    gap = None if low is None or high is None else float(high - low)
    aligned_gap = None if gap is None or sign is None else float(gap * sign)
    return {
        "feature": feature,
        "rows": int(valid.sum()),
        "bins": bin_rows,
        "spearman_to_actual_minus_market": float(values[valid].corr(residual[valid], method="spearman")),
        "high_minus_low_actual_minus_market": gap,
        "aligned_high_minus_low_actual_minus_market": aligned_gap,
    }


def component_signal_shape(aligned: pd.DataFrame, bins: int) -> dict:
    return {feature: quantile_shape(aligned, feature, bins) for feature in COMPONENT_FEATURES}


def component_correlations(aligned: pd.DataFrame) -> dict:
    frame = aligned[list(COMPONENT_FEATURES)].apply(pd.to_numeric, errors="coerce")
    matrix = frame.corr(method="spearman").round(6)
    pairs = []
    for left_index, left in enumerate(COMPONENT_FEATURES):
        for right in COMPONENT_FEATURES[left_index + 1 :]:
            value = matrix.loc[left, right]
            if np.isfinite(value):
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "spearman": float(value),
                        "abs_spearman": float(abs(value)),
                    }
                )
    pairs.sort(key=lambda row: row["abs_spearman"], reverse=True)
    return {"spearman": matrix.to_dict(), "top_abs_pairs": pairs[:12]}


def coefficient_summary(coefficient_rows: list[dict]) -> list[dict]:
    values: dict[tuple[str, str], list[float]] = {}
    for row in coefficient_rows:
        coefficients = row.get("coefficients")
        if coefficients is None:
            continue
        for feature, coefficient in zip(row["feature_columns"], coefficients):
            values.setdefault((row["variant"], feature), []).append(float(coefficient))

    summaries = []
    for (variant, feature), entries in sorted(values.items()):
        array = np.asarray(entries, dtype=float)
        sign, sign_note = expected_sign(feature)
        sign_match_folds = None
        if sign is not None:
            sign_match_folds = int(np.sum(array * sign > 0.0))
        summaries.append(
            {
                "variant": variant,
                "feature": feature,
                "folds": int(len(array)),
                "mean_coefficient": float(np.mean(array)),
                "std_coefficient": float(np.std(array)),
                "min_coefficient": float(np.min(array)),
                "max_coefficient": float(np.max(array)),
                "positive_folds": int(np.sum(array > 0.0)),
                "negative_folds": int(np.sum(array < 0.0)),
                "expected_sign": sign,
                "expected_sign_note": sign_note,
                "expected_sign_match_folds": sign_match_folds,
            }
        )
    return summaries


def summarize_component_bets(predictions: pd.DataFrame, aligned: pd.DataFrame, variants: list[VariantSpec], args, rng):
    summaries = {}
    bet_frames = []
    for variant in variants:
        if variant.name == "market_recalibrated":
            continue
        bets, summary = summarize_bets_for_variant(
            predictions,
            aligned,
            variant.name,
            args.bootstrap_iterations,
            args.bet_null_iterations,
            rng,
        )
        summaries[variant.name] = summary
        if not bets.empty:
            bet_frames.append(bets)
    return summaries, pd.concat(bet_frames, ignore_index=True) if bet_frames else pd.DataFrame()


def probability_table(result: dict) -> list[str]:
    summary = result["summary"]
    null = result.get("market_null") or {}
    baseline_delta = summary["market_recalibrated"]["market_minus_candidate_log_loss"]
    lines = [
        "| Variant | Features | Delta LL | Inc vs Recal | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(
        summary.items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
        reverse=True,
    ):
        boot = row.get("event_bootstrap") or {}
        null_row = null.get(name) or {}
        lines.append(
            "| {name} | {features} | {delta} | {inc} | {brier} | {acc} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                features=len(row["feature_columns"]),
                delta=fmt_float(row["market_minus_candidate_log_loss"]),
                inc=fmt_float(row["market_minus_candidate_log_loss"] - baseline_delta),
                brier=fmt_float(row["market_minus_candidate_brier"]),
                acc=fmt_pct(row["candidate"]["accuracy"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(boot.get("prob_delta_le_zero")),
                null_p=fmt_p(null_row.get("p_value_observed_or_better")),
            )
        )
    return lines


def bet_table(result: dict) -> list[str]:
    lines = [
        "| Variant | Bets | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(
        result["betting"].items(),
        key=lambda item: item[1]["profit"],
        reverse=True,
    ):
        lines.append(
            "| {name} | {bets} | {profit} | {roi} | {actual} | {pos} / {folds} | {boot} | {null_p} |".format(
                name=name,
                bets=row["bets"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row.get("roi")),
                actual=fmt_pct(row.get("actual_minus_market")),
                pos=row["positive_folds"],
                folds=row["folds"],
                boot=fmt_p(row.get("bootstrap_p_profit_le_zero")),
                null_p=fmt_p(row.get("market_null_p")),
            )
        )
    return lines


def coefficient_table(result: dict, variants: set[str]) -> list[str]:
    rows = [
        row
        for row in result["coefficient_summary"]
        if row["variant"] in variants and row["feature"] != "market_logit"
    ]
    lines = [
        "| Variant | Feature | Mean Coef | Positive Folds | Expected Sign Matches |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        match = row["expected_sign_match_folds"]
        lines.append(
            "| {variant} | `{feature}` | {coef} | {pos} / {folds} | {match} |".format(
                variant=row["variant"],
                feature=row["feature"],
                coef=fmt_float(row["mean_coefficient"]),
                pos=row["positive_folds"],
                folds=row["folds"],
                match="" if match is None else f"{match} / {row['folds']}",
            )
        )
    return lines


def shape_table(result: dict) -> list[str]:
    lines = [
        "| Feature | Expected | Spearman vs A-M | Low Bin A-M | High Bin A-M | Aligned High-Low |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for feature, row in result["component_signal_shape"].items():
        sign, sign_note = expected_sign(feature)
        low = row["bins"][0]["actual_minus_market"] if row["bins"] else None
        high = row["bins"][-1]["actual_minus_market"] if row["bins"] else None
        lines.append(
            "| `{feature}` | {expected} | {spearman} | {low} | {high} | {gap} |".format(
                feature=feature,
                expected="+" if sign == 1 else "-" if sign == -1 else "",
                spearman=fmt_float(row.get("spearman_to_actual_minus_market")),
                low=fmt_pct(low),
                high=fmt_pct(high),
                gap=fmt_pct(row.get("aligned_high_minus_low_actual_minus_market")),
            )
        )
    return lines


def correlation_table(result: dict) -> list[str]:
    lines = [
        "| Feature A | Feature B | Spearman |",
        "| --- | --- | ---: |",
    ]
    for row in result["component_correlations"]["top_abs_pairs"][:8]:
        lines.append(
            "| `{left}` | `{right}` | {corr} |".format(
                left=row["left"],
                right=row["right"],
                corr=fmt_float(row["spearman"]),
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    summary = result["summary"]
    best_probability = max(
        summary.items(),
        key=lambda item: item[1]["market_minus_candidate_log_loss"],
    )
    best_bet = max(result["betting"].items(), key=lambda item: item[1]["profit"])
    selected_coef_variants = {
        "current_sigpct_head",
        "pace_adjusted_mixed_core",
        "pace_offense_split",
        "pace_for_against_split",
    }
    lines = [
        "# Striking Component Context Audit",
        "",
        "This diagnostic decomposes the current striking alpha into compact",
        "fight-context components after controlling for the de-vigged market.",
        "It uses the same men-only market-aware rolling protocol as the frozen",
        "striking policies and keeps every fixed `2%` betting ledger uncapped by",
        "event.",
        "",
        "## Protocol",
        "",
        f"- source fights: `{result['metadata']['source_fights_path']}`",
        f"- feature table: `{result['metadata']['features_path']}`",
        f"- odds table: `{result['metadata']['odds_path']}`",
        f"- aligned rows: `{result['metadata']['aligned_rows']}`",
        f"- rolling folds: `{len(result['folds'])}`",
        f"- first holdout start: `{result['parameters']['first_holdout_start']}`",
        f"- last holdout end: `{result['parameters']['last_holdout_end']}`",
        f"- logistic L2 C: `{result['parameters']['c']}`",
        f"- market-null refits: `{result['parameters']['market_null_iterations']}`",
        f"- fixed betting threshold: `{fmt_pct(EDGE_THRESHOLD)}`",
        "",
        "## Probability Results",
        "",
        *probability_table(result),
        "",
        "## Fixed 2% Positive-Edge Uncapped PnL",
        "",
        *bet_table(result),
        "",
        "## Component Coefficient Signs",
        "",
        *coefficient_table(result, selected_coef_variants),
        "",
        "## Raw Component Residual Shape",
        "",
        *shape_table(result),
        "",
        "## Strongest Component Correlations",
        "",
        *correlation_table(result),
        "",
        "## Interpretation",
        "",
        "- Best probability variant: `{}` with Delta LL `{}`, positive folds `{}` / `{}`, and market-null p `{}`.".format(
            best_probability[0],
            fmt_float(best_probability[1]["market_minus_candidate_log_loss"]),
            best_probability[1]["positive_folds"],
            best_probability[1]["folds"],
            fmt_p((result.get("market_null") or {}).get(best_probability[0], {}).get("p_value_observed_or_better")),
        ),
        "- Best fixed `2%` uncapped PnL variant: `{}` with profit `{}`, ROI `{}`, and market-null p `{}`.".format(
            best_bet[0],
            fmt_units(best_bet[1]["profit"]),
            fmt_pct(best_bet[1].get("roi")),
            fmt_p(best_bet[1].get("market_null_p")),
        ),
    ]
    sigpct = summary.get("current_sigpct_head", {})
    pace = summary.get("pace_adjusted_mixed_core", {})
    if sigpct and pace:
        lines.append(
            "- `current_sigpct_head` remains the cleaner probability surface than the frozen pace-adjusted challenger by about `{}` Delta LL, while pace-adjusted variants remain competitive for uncapped PnL.".format(
                fmt_float(sigpct["market_minus_candidate_log_loss"] - pace["market_minus_candidate_log_loss"])
            )
        )
    lines.extend(
        [
            "- The component signs are mixed: significant-strike percentage and head-strike components are stable positive contributors, but generic significant-strike pace/volume turns negative once efficiency and head pace are included.",
            "- Raw pace component residual bins are not uniformly monotone after market control, so the pace-adjusted PnL lead should be treated as a correlated feature clue, not a new live-edge proof.",
            "- No event cap is used here. The result supports continued paper tracking and deeper feature design, not increased live staking.",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit(args) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(args.seed)
    aligned, metadata, folds = prepare_augmented_frame(args)
    variants = build_component_variants(aligned)
    predictions, coefficients, fold_rows = run_observed_predictions(aligned, folds, variants, args.c)
    summary = aggregate_predictions(predictions, variants, args.bootstrap_iterations, rng)
    null = market_null_simulation(
        aligned,
        folds,
        variants,
        summary,
        args.c,
        args.market_null_iterations,
        rng,
    )
    betting, bet_rows = summarize_component_bets(predictions, aligned, variants, args, rng)
    result = {
        "parameters": {
            "first_holdout_start": args.first_holdout_start,
            "last_holdout_end": args.last_holdout_end,
            "dev_days": args.dev_days,
            "holdout_days": args.holdout_days,
            "step_days": args.step_days,
            "min_dev_fights": args.min_dev_fights,
            "min_holdout_fights": args.min_holdout_fights,
            "c": args.c,
            "bins": args.bins,
            "bootstrap_iterations": args.bootstrap_iterations,
            "market_null_iterations": args.market_null_iterations,
            "bet_null_iterations": args.bet_null_iterations,
            "seed": args.seed,
        },
        "metadata": metadata,
        "folds": fold_rows,
        "variants": [
            {
                "name": variant.name,
                "feature_columns": list(variant.feature_columns),
                "note": variant.note,
            }
            for variant in variants
        ],
        "summary": summary,
        "market_null": null,
        "betting": betting,
        "component_distribution": component_distribution(aligned),
        "component_signal_shape": component_signal_shape(aligned, args.bins),
        "component_correlations": component_correlations(aligned),
        "coefficient_summary": coefficient_summary(coefficients),
    }
    return result, predictions, bet_rows


def main():
    args = parse_args()
    result, predictions, bet_rows = run_audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "striking_component_context_audit.json"
    md_path = output_dir / "striking_component_context_audit.md"
    predictions_path = output_dir / "striking_component_context_predictions.csv"
    bets_path = output_dir / "striking_component_context_edge02_bets.csv"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    predictions.to_csv(predictions_path, index=False)
    bet_rows.to_csv(bets_path, index=False)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {predictions_path}")
    print(f"Wrote {bets_path}")


if __name__ == "__main__":
    main()
