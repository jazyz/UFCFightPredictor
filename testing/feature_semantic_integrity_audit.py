#!/usr/bin/env python3
"""Audit UFC feature semantics and pre-fight state integrity.

This is a feature-forensics pass, not a model search. It checks whether the
current feature table obeys mechanical invariants and highlights feature
families whose names can be misleading in fight context.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.name_matching import lookup_keys, normalize_name  # noqa: E402


CORE_STATE_FEATURES = (
    "totalfights",
    "wins",
    "winstreak",
    "losestreak",
    "titlewins",
    "elo",
    "oppelo",
    "last_fight",
)
INTUITIVE_DEFENSE_FEATURES = {
    "Sig. str.% defense",
    "Total str.% defense",
    "Td% defense",
}
TARGET_MIX_DEFENSE_BASES = {
    "Head%",
    "Body%",
    "Leg%",
    "Distance%",
    "Clinch%",
    "Ground%",
}
TOLERANCE = 1e-6


@dataclass
class FighterState:
    totalfights: int = 0
    wins: int = 0
    winstreak: int = 0
    losestreak: int = 0
    titlewins: int = 0
    elo: float = 1000.0
    oppelo_sum: float = 0.0
    last_fight: pd.Timestamp | None = None


@dataclass
class StateAudit:
    expected_feature_rows: int = 0
    matched_feature_rows: int = 0
    missing_feature_rows: int = 0
    core_checks: int = 0
    core_matches: int = 0
    same_day_prior_feature_rows: int = 0
    same_day_prior_examples: list[dict] = field(default_factory=list)
    mismatch_counts: Counter = field(default_factory=Counter)
    mismatch_examples: list[dict] = field(default_factory=list)


def parse_args():
    parser = argparse.ArgumentParser(description="Audit feature semantics and integrity")
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--model-features", default="saved_preprocessing/model_feature_columns_single.json")
    parser.add_argument("--feature-importance", default="test_results/regularized_lgbm_feature_importance.csv")
    parser.add_argument("--output-dir", default="test_results/feature_semantic_integrity_audit")
    return parser.parse_args()


def parse_date(value) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, format="mixed", errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).normalize()


def canonical_fighter_key(name) -> str:
    keys = lookup_keys(name)
    return keys[-1] if keys else normalize_name(name)


def pair_key(red, blue) -> tuple[str, str]:
    return tuple(sorted([canonical_fighter_key(red), canonical_fighter_key(blue)]))


def feature_lookup_key(row: pd.Series) -> tuple[str, tuple[str, str], str]:
    date = parse_date(row["Date"])
    date_text = "" if date is None else date.date().isoformat()
    return date_text, pair_key(row["Red Fighter"], row["Blue Fighter"]), str(row.get("Title", ""))


def source_lookup_key(row: pd.Series) -> tuple[str, tuple[str, str], str]:
    date = parse_date(row["Date"])
    date_text = "" if date is None else date.date().isoformat()
    return date_text, pair_key(row["Red Fighter"], row["Blue Fighter"]), str(row.get("Title", ""))


def is_blank(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def source_result(row: pd.Series) -> str:
    winner = row.get("Winner")
    if is_blank(winner):
        return "draw"
    winner_key = canonical_fighter_key(winner)
    red_key = canonical_fighter_key(row["Red Fighter"])
    blue_key = canonical_fighter_key(row["Blue Fighter"])
    if winner_key == red_key:
        return "win"
    if winner_key == blue_key:
        return "loss"
    return "draw"


def safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def calculate_k_factor(number_of_fights: int) -> int:
    if number_of_fights < 5:
        return 40
    if number_of_fights < 10:
        return 35
    if number_of_fights < 20:
        return 30
    return 25


def expected_win_probability(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + pow(10.0, (rating_b - rating_a) / 400.0))


def update_elo(rating_a: float, rating_b: float, result: str, fights_a: int, fights_b: int) -> tuple[float, float]:
    expected = expected_win_probability(rating_a, rating_b)
    if result == "win":
        actual = 1.0
    elif result == "loss":
        actual = 0.0
    else:
        actual = 0.5
    k_a = calculate_k_factor(fights_a)
    k_b = calculate_k_factor(fights_b)
    return (
        rating_a + k_a * (actual - expected),
        rating_b + k_b * ((1.0 - actual) - (1.0 - expected)),
    )


def chronological_source_rows(source: pd.DataFrame) -> list[pd.Series]:
    unique_rows = []
    seen = set()
    for _, row in source.iterrows():
        date = parse_date(row.get("Date"))
        normalized_date = "" if date is None else date.date().isoformat()
        key = (
            normalized_date,
            str(row.get("Title", "")),
            frozenset(pair_key(row.get("Red Fighter", ""), row.get("Blue Fighter", ""))),
            canonical_fighter_key(row.get("Winner", "")),
            str(row.get("Method", "")),
            str(row.get("Round", "")),
            str(row.get("Time", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return sorted(unique_rows, key=lambda row: parse_date(row.get("Date")) or pd.Timestamp.max)


def build_feature_queues(features: pd.DataFrame) -> dict[tuple[str, tuple[str, str], str], deque[int]]:
    queues: dict[tuple[str, tuple[str, str], str], deque[int]] = defaultdict(deque)
    for index, row in features.iterrows():
        queues[feature_lookup_key(row)].append(index)
    return queues


def feature_value_for_state(feature: str, state: FighterState, event_date: pd.Timestamp) -> float | None:
    if feature == "totalfights":
        return float(state.totalfights)
    if feature == "wins":
        return None if state.totalfights <= 0 else float(state.wins / state.totalfights)
    if feature == "winstreak":
        return float(state.winstreak)
    if feature == "losestreak":
        return float(state.losestreak)
    if feature == "titlewins":
        return float(state.titlewins)
    if feature == "elo":
        return float(state.elo)
    if feature == "oppelo":
        return None if state.totalfights <= 0 else float(state.oppelo_sum / state.totalfights)
    if feature == "last_fight":
        if state.last_fight is None:
            return None
        return float((event_date - state.last_fight).days)
    return None


def compare_core_state(
    audit: StateAudit,
    row: pd.Series,
    side: str,
    state: FighterState,
    event_date: pd.Timestamp,
) -> None:
    for feature in CORE_STATE_FEATURES:
        column = f"{side} {feature}"
        if column not in row.index:
            continue
        actual = safe_float(row[column])
        expected = feature_value_for_state(feature, state, event_date)
        if actual is None or expected is None:
            continue
        audit.core_checks += 1
        if abs(actual - expected) <= TOLERANCE:
            audit.core_matches += 1
            continue
        audit.mismatch_counts[feature] += 1
        if len(audit.mismatch_examples) < 50:
            audit.mismatch_examples.append(
                {
                    "date": event_date.date().isoformat(),
                    "title": str(row.get("Title", "")),
                    "fighter": str(row.get(f"{side} Fighter", "")),
                    "side": side,
                    "feature": feature,
                    "actual": actual,
                    "expected": expected,
                    "absolute_error": abs(actual - expected),
                }
            )


def update_state_from_source(
    states: defaultdict[str, FighterState],
    row: pd.Series,
) -> None:
    event_date = parse_date(row.get("Date"))
    red_key = canonical_fighter_key(row["Red Fighter"])
    blue_key = canonical_fighter_key(row["Blue Fighter"])
    red_state = states[red_key]
    blue_state = states[blue_key]
    result = source_result(row)

    red_state.totalfights += 1
    blue_state.totalfights += 1
    red_fights = red_state.totalfights
    blue_fights = blue_state.totalfights

    red_rating = red_state.elo
    blue_rating = blue_state.elo
    red_state.oppelo_sum += blue_rating
    blue_state.oppelo_sum += red_rating

    if event_date is not None:
        red_state.last_fight = event_date
        blue_state.last_fight = event_date

    is_title = "Title" in str(row.get("Title", ""))
    if result == "win":
        blue_state.losestreak += 1
        red_state.losestreak = 0
        red_state.winstreak += 1
        blue_state.winstreak = 0
        red_state.wins += 1
        if is_title:
            red_state.titlewins += 1
    elif result == "loss":
        red_state.losestreak += 1
        blue_state.losestreak = 0
        blue_state.winstreak += 1
        red_state.winstreak = 0
        blue_state.wins += 1
        if is_title:
            blue_state.titlewins += 1

    red_state.elo, blue_state.elo = update_elo(
        red_rating,
        blue_rating,
        result,
        red_fights,
        blue_fights,
    )


def audit_pre_fight_state(source: pd.DataFrame, features: pd.DataFrame) -> dict:
    queues = build_feature_queues(features)
    used_feature_indices = set()
    states: defaultdict[str, FighterState] = defaultdict(FighterState)
    audit = StateAudit()

    for source_row in chronological_source_rows(source):
        event_date = parse_date(source_row.get("Date"))
        red_key = canonical_fighter_key(source_row["Red Fighter"])
        blue_key = canonical_fighter_key(source_row["Blue Fighter"])
        result = source_result(source_row)

        if (
            result in {"win", "loss"}
            and states[red_key].totalfights >= 2
            and states[blue_key].totalfights >= 2
            and event_date is not None
        ):
            audit.expected_feature_rows += 1
            key = source_lookup_key(source_row)
            feature_index = queues.get(key, deque()).popleft() if queues.get(key) else None
            if feature_index is None:
                audit.missing_feature_rows += 1
            else:
                used_feature_indices.add(feature_index)
                audit.matched_feature_rows += 1
                feature_row = features.loc[feature_index]
                for side in ("Red", "Blue"):
                    fighter_key = canonical_fighter_key(feature_row[f"{side} Fighter"])
                    fighter_state = states[fighter_key]
                    if fighter_state.last_fight is not None and fighter_state.last_fight == event_date:
                        audit.same_day_prior_feature_rows += 1
                        if len(audit.same_day_prior_examples) < 20:
                            audit.same_day_prior_examples.append(
                                {
                                    "date": event_date.date().isoformat(),
                                    "fighter": str(feature_row[f"{side} Fighter"]),
                                    "side": side,
                                    "title": str(feature_row.get("Title", "")),
                                    "feature_totalfights": safe_float(feature_row.get(f"{side} totalfights")),
                                }
                            )
                    compare_core_state(audit, feature_row, side, fighter_state, event_date)

        update_state_from_source(states, source_row)

    extra_feature_rows = int(len(features) - len(used_feature_indices))
    return {
        "expected_feature_rows_from_source": audit.expected_feature_rows,
        "matched_feature_rows": audit.matched_feature_rows,
        "missing_feature_rows": audit.missing_feature_rows,
        "extra_feature_rows": extra_feature_rows,
        "core_state_checks": audit.core_checks,
        "core_state_matches": audit.core_matches,
        "core_state_mismatches": audit.core_checks - audit.core_matches,
        "mismatch_counts": dict(audit.mismatch_counts.most_common()),
        "mismatch_examples": audit.mismatch_examples,
        "same_day_prior_feature_rows": audit.same_day_prior_feature_rows,
        "same_day_prior_examples": audit.same_day_prior_examples,
    }


def audit_oppdiff_consistency(features: pd.DataFrame) -> dict:
    rows = []
    checked_pairs = 0
    total_checks = 0
    total_mismatches = 0
    for column in features.columns:
        if not column.endswith(" oppdiff"):
            continue
        base = column[: -len(" oppdiff")]
        red_col = f"Red {base}"
        blue_col = f"Blue {base}"
        if red_col not in features.columns or blue_col not in features.columns:
            continue
        checked_pairs += 1
        red = pd.to_numeric(features[red_col], errors="coerce")
        blue = pd.to_numeric(features[blue_col], errors="coerce")
        diff = pd.to_numeric(features[column], errors="coerce")
        mask = red.notna() & blue.notna() & diff.notna()
        expected = red[mask] - blue[mask]
        error = (diff[mask] - expected).abs()
        mismatches = int((error > TOLERANCE).sum())
        checks = int(mask.sum())
        total_checks += checks
        total_mismatches += mismatches
        rows.append(
            {
                "oppdiff_column": column,
                "red_column": red_col,
                "blue_column": blue_col,
                "checks": checks,
                "mismatches": mismatches,
                "max_abs_error": float(error.max()) if len(error) else 0.0,
            }
        )
    return {
        "oppdiff_pairs_checked": checked_pairs,
        "row_level_checks": total_checks,
        "row_level_mismatches": total_mismatches,
        "worst_columns": sorted(rows, key=lambda row: row["max_abs_error"], reverse=True)[:20],
    }


def load_model_features(path: str) -> list[str]:
    with open(path) as file:
        return list(json.load(file))


def swap_column_name(column: str) -> str:
    return column.replace("Red", "__SIDE__").replace("Blue", "Red").replace("__SIDE__", "Blue")


def audit_swap_coverage(feature_columns: list[str], available_columns: set[str]) -> dict:
    missing_available_counterparts = []
    missing_model_counterparts = []
    side_specific = []
    for column in feature_columns:
        if "oppdiff" in column:
            continue
        counterpart = swap_column_name(column)
        if counterpart == column:
            continue
        side_specific.append(column)
        if counterpart not in available_columns:
            missing_available_counterparts.append({"feature": column, "counterpart": counterpart})
        elif counterpart not in feature_columns:
            missing_model_counterparts.append({"feature": column, "counterpart": counterpart})
    return {
        "model_features": len(feature_columns),
        "side_specific_model_features": len(side_specific),
        "missing_available_counterparts": missing_available_counterparts,
        "missing_model_counterparts": missing_model_counterparts,
    }


def load_importance(path: str) -> dict[str, float]:
    importance_path = Path(path)
    if not importance_path.exists():
        return {}
    df = pd.read_csv(importance_path)
    if "feature" not in df.columns or "importance" not in df.columns:
        return {}
    return {
        str(row["feature"]): float(row["importance"])
        for _, row in df.iterrows()
    }


def base_feature_name(column: str) -> str:
    base = re.sub(r"^(Red|Blue) ", "", column)
    base = base.replace(" oppdiff", "")
    return base


def audit_feature_semantics(feature_columns: list[str], importance: dict[str, float]) -> dict:
    target_mix_defense = []
    percentage_rate_like = []
    raw_dob_features = []
    top_flagged = []

    for column in feature_columns:
        base = base_feature_name(column)
        imp = float(importance.get(column, 0.0))
        warning = None
        if base == "dob":
            raw_dob_features.append({"feature": column, "importance": imp})
            warning = "raw birth-year proxy; should be interpreted through age context"
        elif base.endswith("% defense") and base not in INTUITIVE_DEFENSE_FEATURES:
            stem = base[: -len(" defense")]
            if stem in TARGET_MIX_DEFENSE_BASES:
                target_mix_defense.append({"feature": column, "importance": imp})
                warning = "target/position mix defense proxy, not conventional defensive success"
        elif "%" in base and "defense" not in base and "differential" not in base:
            percentage_rate_like.append({"feature": column, "importance": imp})
            warning = "weighted percentage-side feature; generator scales side values by elapsed fight time"
        if warning is not None:
            top_flagged.append({"feature": column, "importance": imp, "warning": warning})

    top_flagged = sorted(top_flagged, key=lambda row: row["importance"], reverse=True)
    return {
        "raw_dob_features": sorted(raw_dob_features, key=lambda row: row["importance"], reverse=True),
        "target_mix_defense_features": sorted(target_mix_defense, key=lambda row: row["importance"], reverse=True),
        "percentage_rate_like_side_features": sorted(percentage_rate_like, key=lambda row: row["importance"], reverse=True),
        "target_mix_defense_importance_sum": float(sum(row["importance"] for row in target_mix_defense)),
        "top_flagged_features": top_flagged[:25],
    }


def fmt_float(value, digits=6) -> str:
    if value is None or not np.isfinite(float(value)):
        return ""
    return f"{float(value):.{digits}f}"


def markdown_report(result: dict) -> str:
    oppdiff = result["oppdiff_consistency"]
    state = result["pre_fight_state"]
    swap = result["swap_coverage"]
    semantics = result["feature_semantics"]
    hard_failures = (
        oppdiff["row_level_mismatches"]
        + state["missing_feature_rows"]
        + state["core_state_mismatches"]
        + len(swap["missing_available_counterparts"])
        + len(swap["missing_model_counterparts"])
    )

    lines = [
        "# Feature Semantic Integrity Audit",
        "",
        "This audit checks whether the current feature table obeys mechanical",
        "feature invariants and whether high-importance feature names mean what",
        "they appear to mean in fight context. It does not train or select a new",
        "model.",
        "",
        "## Mechanical Checks",
        "",
        "| Check | Value |",
        "| --- | ---: |",
        f"| feature rows | {result['feature_rows']} |",
        f"| feature columns | {result['feature_columns']} |",
        f"| active model features | {swap['model_features']} |",
        f"| oppdiff pairs checked | {oppdiff['oppdiff_pairs_checked']} |",
        f"| oppdiff row-level checks | {oppdiff['row_level_checks']} |",
        f"| oppdiff mismatches | {oppdiff['row_level_mismatches']} |",
        f"| expected supervised rows from source | {state['expected_feature_rows_from_source']} |",
        f"| matched source rows | {state['matched_feature_rows']} |",
        f"| missing feature rows | {state['missing_feature_rows']} |",
        f"| extra feature rows | {state['extra_feature_rows']} |",
        f"| core pre-fight state checks | {state['core_state_checks']} |",
        f"| core pre-fight state mismatches | {state['core_state_mismatches']} |",
        f"| side-specific active features | {swap['side_specific_model_features']} |",
        f"| active features missing table counterpart | {len(swap['missing_available_counterparts'])} |",
        f"| active features missing model counterpart | {len(swap['missing_model_counterparts'])} |",
        f"| feature rows with same-day prior fighter state | {state['same_day_prior_feature_rows']} |",
        "",
    ]

    if oppdiff["row_level_mismatches"]:
        lines.extend(
            [
                "Worst oppdiff consistency columns:",
                "",
                "| Column | Checks | Mismatches | Max Abs Error |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for row in oppdiff["worst_columns"][:10]:
            if row["mismatches"] <= 0:
                continue
            lines.append(
                f"| `{row['oppdiff_column']}` | {row['checks']} | {row['mismatches']} | {fmt_float(row['max_abs_error'])} |"
            )
        lines.append("")

    if state["mismatch_examples"]:
        lines.extend(
            [
                "Sample pre-fight state mismatches:",
                "",
                "| Date | Fighter | Side | Feature | Actual | Expected | Abs Error |",
                "| --- | --- | --- | --- | ---: | ---: | ---: |",
            ]
        )
        for row in state["mismatch_examples"][:10]:
            lines.append(
                "| {date} | {fighter} | {side} | `{feature}` | {actual} | {expected} | {error} |".format(
                    date=row["date"],
                    fighter=row["fighter"],
                    side=row["side"],
                    feature=row["feature"],
                    actual=fmt_float(row["actual"]),
                    expected=fmt_float(row["expected"]),
                    error=fmt_float(row["absolute_error"]),
                )
            )
        lines.append("")

    if state["same_day_prior_examples"]:
        lines.extend(
            [
                "Same-day prior fighter-state examples:",
                "",
                "| Date | Fighter | Side | Feature TotalFights | Fight |",
                "| --- | --- | --- | ---: | --- |",
            ]
        )
        for row in state["same_day_prior_examples"][:10]:
            lines.append(
                "| {date} | {fighter} | {side} | {total} | {title} |".format(
                    date=row["date"],
                    fighter=row["fighter"],
                    side=row["side"],
                    total=fmt_float(row["feature_totalfights"], digits=0),
                    title=row["title"],
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Semantic Warnings",
            "",
            "| Warning Family | Active Features | Importance Sum |",
            "| --- | ---: | ---: |",
            f"| raw DOB / birth-year proxies | {len(semantics['raw_dob_features'])} | {sum(row['importance'] for row in semantics['raw_dob_features']):.0f} |",
            f"| target/position-mix defense proxies | {len(semantics['target_mix_defense_features'])} | {semantics['target_mix_defense_importance_sum']:.0f} |",
            f"| side percentage values scaled by elapsed fight time | {len(semantics['percentage_rate_like_side_features'])} | {sum(row['importance'] for row in semantics['percentage_rate_like_side_features']):.0f} |",
            "",
            "Top flagged active features by current regularized-LGBM importance:",
            "",
            "| Feature | Importance | Why Flagged |",
            "| --- | ---: | --- |",
        ]
    )
    for row in semantics["top_flagged_features"][:15]:
        lines.append(f"| `{row['feature']}` | {row['importance']:.0f} | {row['warning']} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    if hard_failures == 0:
        lines.append(
            "- No hard arithmetic, source-row matching, core pre-fight state, or active side-swap coverage failure was found."
        )
    else:
        lines.append(
            f"- Found {hard_failures} mechanical failures across arithmetic, source matching, pre-fight state, or swap coverage; inspect the samples above before trusting feature experiments."
        )
    if state["same_day_prior_feature_rows"]:
        lines.append(
            "- Some feature rows include same-day prior fighter state. This only matters when the same fighter appears more than once on a date; review these rows before treating them as clean pre-event predictions."
        )
    else:
        lines.append(
            "- No supervised feature rows used same-day prior state for the same fighter, so card-level chronological leakage was not detected in this table."
        )
    lines.extend(
        [
            "- The bigger issue is semantic, not arithmetic: several active percentage/defense columns are proxies created by the historical generator, not literal fight-skill concepts.",
            "- Treat these columns as empirical model inputs unless a follow-up feature redesign gives them clearer fight meaning and validates after market control.",
            "",
        ]
    )
    return "\n".join(lines)


def audit(args) -> dict:
    source = pd.read_csv(args.source_fights)
    features = pd.read_csv(args.features)
    model_features = load_model_features(args.model_features)
    importance = load_importance(args.feature_importance)
    return {
        "source_fights": args.source_fights,
        "features": args.features,
        "model_features_path": args.model_features,
        "feature_importance_path": args.feature_importance,
        "source_rows": int(len(source)),
        "feature_rows": int(len(features)),
        "feature_columns": int(len(features.columns)),
        "oppdiff_consistency": audit_oppdiff_consistency(features),
        "pre_fight_state": audit_pre_fight_state(source, features),
        "swap_coverage": audit_swap_coverage(model_features, set(features.columns)),
        "feature_semantics": audit_feature_semantics(model_features, importance),
    }


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "feature_semantic_integrity_audit.json"
    md_path = output_dir / "feature_semantic_integrity_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))
    state = result["pre_fight_state"]
    oppdiff = result["oppdiff_consistency"]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "Mechanical checks: "
        f"{oppdiff['row_level_mismatches']} oppdiff mismatches, "
        f"{state['core_state_mismatches']} core-state mismatches"
    )


if __name__ == "__main__":
    main()
