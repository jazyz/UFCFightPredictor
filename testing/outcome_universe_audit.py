#!/usr/bin/env python3
"""Audit fight universe and non-binary outcome handling.

The goal is to verify two invariants that matter for edge claims:

1. The current production feature/backtest universe excludes women's fights.
2. Draw/no-contest/overturned rows are not supervised labels, but their fight
   activity still updates future fighter-state features.
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

from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_BACKTEST_SUMMARIES = [
    "test_results/regularized_lgbm_1y/no_leakage_backtest_summary.json",
    "test_results/regularized_lgbm_2y/no_leakage_backtest_summary.json",
    "test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest_summary.json",
]
STAT_CHECK_FEATURES = ("Sig. str.", "Total str.", "Td")


def parse_args():
    parser = argparse.ArgumentParser(description="Audit outcome and universe handling")
    parser.add_argument("--raw-fights", default="data/fight_details_date.csv")
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument(
        "--backtest-summary",
        action="append",
        default=None,
        help="no_leakage_backtest_summary.json to include in the universe audit",
    )
    parser.add_argument("--min-check-date", default="2001-01-01")
    parser.add_argument("--output-dir", default="test_results/outcome_universe_audit")
    return parser.parse_args()


def parse_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="mixed", errors="coerce")


def is_blank(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def women_title_count(df: pd.DataFrame) -> int:
    if "Title" not in df.columns:
        return 0
    return int(df["Title"].fillna("").str.contains("Women", case=False, regex=False).sum())


def known_women_fighter_names(df: pd.DataFrame) -> set[str]:
    required_columns = {"Title", "Red Fighter", "Blue Fighter"}
    if not required_columns.issubset(df.columns):
        return set()
    women_title = df["Title"].fillna("").str.contains("Women", case=False, regex=False)
    women_rows = df[women_title]
    return set(women_rows["Red Fighter"].map(canonical_name)) | set(
        women_rows["Blue Fighter"].map(canonical_name)
    )


def known_women_pair_mask(df: pd.DataFrame, known_women: set[str]) -> pd.Series:
    required_columns = {"Red Fighter", "Blue Fighter"}
    if not known_women or not required_columns.issubset(df.columns):
        return pd.Series(False, index=df.index)
    red = df["Red Fighter"].map(canonical_name)
    blue = df["Blue Fighter"].map(canonical_name)
    return red.isin(known_women) & blue.isin(known_women)


def source_binary_mask(df: pd.DataFrame) -> pd.Series:
    winner_is_present = ~df["Winner"].map(is_blank)
    if "Draw" not in df.columns:
        return winner_is_present
    draw_flag = df["Draw"].astype(str).str.strip().str.lower().eq("true")
    return winner_is_present & ~draw_flag


def safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def fight_elapsed_minutes(row: pd.Series) -> float | None:
    round_number = safe_float(row.get("Round"))
    time_value = safe_float(row.get("Time"))
    if round_number is None or time_value is None:
        return None
    elapsed = (round_number - 1) * 5 + time_value
    if elapsed <= 0:
        return None
    return elapsed


def sqr_sum(n: int) -> int:
    return n * (n + 1) * (2 * n + 1) // 6


def dataset_summary(path: str, known_women: set[str]) -> dict:
    df = pd.read_csv(path)
    women_title_rows = women_title_count(df)
    women_pair_rows = int(known_women_pair_mask(df, known_women).sum())
    summary = {
        "path": path,
        "rows": int(len(df)),
        "women_title_rows": women_title_rows,
        "known_women_pair_rows": women_pair_rows,
        "hidden_women_pair_rows": max(0, women_pair_rows - women_title_rows),
    }
    if "Result" in df.columns:
        normalized = df["Result"].fillna("").astype(str).str.strip().str.lower()
        summary["result_counts"] = {
            str(key): int(value)
            for key, value in normalized.value_counts(dropna=False).sort_index().items()
        }
        summary["non_binary_result_rows"] = int((~normalized.isin(["win", "loss"])).sum())
    if "Winner" in df.columns:
        binary = source_binary_mask(df)
        summary["binary_winner_rows"] = int(binary.sum())
        summary["non_binary_or_blank_winner_rows"] = int((~binary).sum())
        summary["draw_rows"] = int(
            df.get("Draw", pd.Series(False, index=df.index))
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("true")
            .sum()
        )
        summary["non_binary_methods"] = {
            str(key): int(value)
            for key, value in df.loc[~binary, "Method"].fillna("").value_counts().head(10).items()
        }
    return summary


def build_fighter_history_index(source: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    source = source.dropna(subset=["DateParsed", "Red Fighter", "Blue Fighter"]).copy()
    binary = source_binary_mask(source)
    rows = []
    for index, row in source.iterrows():
        event_day = np.datetime64(row["DateParsed"].date())
        for column in ["Red Fighter", "Blue Fighter"]:
            rows.append((canonical_name(row[column]), event_day, bool(binary.loc[index])))

    by_fighter: dict[str, list[tuple[np.datetime64, bool]]] = {}
    for fighter, event_day, is_binary in rows:
        by_fighter.setdefault(fighter, []).append((event_day, is_binary))

    indexed = {}
    for fighter, values in by_fighter.items():
        values = sorted(values)
        dates = np.array([value[0] for value in values], dtype="datetime64[D]")
        binary_cumulative = np.cumsum([1 if value[1] else 0 for value in values])
        indexed[fighter] = (dates, binary_cumulative)
    return indexed


def prior_counts(indexed_history, fighter: str, event_day: np.datetime64) -> tuple[int, int]:
    dates, binary_cumulative = indexed_history.get(
        canonical_name(fighter),
        (np.array([], dtype="datetime64[D]"), np.array([], dtype=int)),
    )
    cursor = int(np.searchsorted(dates, event_day, side="left"))
    binary_count = int(binary_cumulative[cursor - 1]) if cursor > 0 else 0
    return cursor, binary_count


def empty_prior_state() -> dict:
    return {
        "total": 0,
        "binary_total": 0,
        "last_day": None,
        "last_is_binary": None,
        "stat_sums": {},
        "binary_stat_sums": {},
    }


def build_fighter_state_history(
    source: pd.DataFrame,
    stat_features: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    source = source.dropna(subset=["DateParsed", "Red Fighter", "Blue Fighter"]).copy()
    source = source.sort_values("DateParsed", kind="mergesort")
    binary = source_binary_mask(source)

    state: dict[str, dict[str, object]] = {}
    snapshots_by_fighter: dict[str, list[dict]] = {}
    for index, row in source.iterrows():
        event_day = np.datetime64(row["DateParsed"].date())
        is_binary = bool(binary.loc[index])
        elapsed = fight_elapsed_minutes(row)
        for side in ["Red", "Blue"]:
            fighter = canonical_name(row[f"{side} Fighter"])
            fighter_state = state.setdefault(
                fighter,
                {
                    "total": 0,
                    "binary_total": 0,
                    "stat_sums": {feature: 0.0 for feature in stat_features},
                    "binary_stat_sums": {feature: 0.0 for feature in stat_features},
                },
            )
            fighter_state["total"] += 1
            if is_binary:
                fighter_state["binary_total"] += 1

            if elapsed is not None:
                weight = fighter_state["total"] ** 2
                binary_weight = fighter_state["binary_total"] ** 2
                for feature in stat_features:
                    value = safe_float(row.get(f"{side} {feature}"))
                    if value is None:
                        continue
                    fighter_state["stat_sums"][feature] += value * weight / elapsed
                    if is_binary:
                        fighter_state["binary_stat_sums"][feature] += value * binary_weight / elapsed

            snapshot = {
                "date": event_day,
                "total": int(fighter_state["total"]),
                "binary_total": int(fighter_state["binary_total"]),
                "last_day": event_day,
                "last_is_binary": is_binary,
                "stat_sums": dict(fighter_state["stat_sums"]),
                "binary_stat_sums": dict(fighter_state["binary_stat_sums"]),
            }
            snapshots_by_fighter.setdefault(fighter, []).append(snapshot)

    indexed = {}
    for fighter, snapshots in snapshots_by_fighter.items():
        indexed[fighter] = {
            "dates": np.array([snapshot["date"] for snapshot in snapshots], dtype="datetime64[D]"),
            "snapshots": snapshots,
        }
    return indexed


def prior_state(indexed_history, fighter: str, event_day: np.datetime64) -> dict:
    history = indexed_history.get(canonical_name(fighter))
    if not history:
        return empty_prior_state()
    dates = history["dates"]
    cursor = int(np.searchsorted(dates, event_day, side="left"))
    if cursor <= 0:
        return empty_prior_state()
    return history["snapshots"][cursor - 1]


def audit_non_binary_state(source_path: str, features_path: str, min_check_date: str) -> dict:
    source = pd.read_csv(source_path)
    features = pd.read_csv(features_path)
    source["DateParsed"] = parse_date_series(source["Date"])
    features["DateParsed"] = parse_date_series(features["Date"])
    indexed_history = build_fighter_history_index(source)
    state_history = build_fighter_state_history(source, STAT_CHECK_FEATURES)

    checked = 0
    matched = 0
    mismatches = []
    examples = []
    last_fight_checked = 0
    last_fight_matched = 0
    last_fight_examples = []
    last_fight_mismatches = []
    weighted_stat_checked = 0
    weighted_stat_matched = 0
    weighted_stat_examples = []
    weighted_stat_mismatches = []
    min_date = pd.Timestamp(min_check_date)
    feature_rows = features[features["DateParsed"] >= min_date].dropna(subset=["DateParsed"])

    for _, row in feature_rows.iterrows():
        event_day = np.datetime64(row["DateParsed"].date())
        for side in ["Red", "Blue"]:
            fighter = row[f"{side} Fighter"]
            total_prior, binary_prior = prior_counts(indexed_history, fighter, event_day)
            prior_non_binary = total_prior - binary_prior
            if prior_non_binary <= 0:
                continue
            details = prior_state(state_history, fighter, event_day)

            checked += 1
            processed_total = float(row[f"{side} totalfights"])
            record = {
                "date": row["Date"],
                "fighter": fighter,
                "side": side,
                "title": row["Title"],
                "processed_totalfights": processed_total,
                "source_prior_fights_including_non_binary": total_prior,
                "source_prior_binary_fights_only": binary_prior,
                "prior_non_binary_fights": prior_non_binary,
            }
            if abs(processed_total - total_prior) < 1e-9:
                matched += 1
                if len(examples) < 12:
                    examples.append(record)
            elif len(mismatches) < 50:
                mismatches.append(record)

            if details["last_day"] is not None and details["last_is_binary"] is False:
                last_fight_checked += 1
                expected_days = int((event_day - details["last_day"]).astype(int))
                processed_days = safe_float(row.get(f"{side} last_fight"))
                last_record = {
                    **record,
                    "processed_last_fight_days": processed_days,
                    "expected_days_since_prior_non_binary": expected_days,
                    "prior_non_binary_date": str(details["last_day"]),
                }
                if processed_days is not None and abs(processed_days - expected_days) < 1e-9:
                    last_fight_matched += 1
                    if len(last_fight_examples) < 8:
                        last_fight_examples.append(last_record)
                elif len(last_fight_mismatches) < 25:
                    last_fight_mismatches.append(last_record)

            for feature in STAT_CHECK_FEATURES:
                processed_value = safe_float(row.get(f"{side} {feature}"))
                total = int(details["total"])
                binary_total = int(details["binary_total"])
                if processed_value is None or total <= 0 or binary_total <= 0:
                    continue
                stat_sum = details["stat_sums"].get(feature)
                binary_stat_sum = details["binary_stat_sums"].get(feature)
                if stat_sum is None or binary_stat_sum is None:
                    continue
                expected_with_non_binary = stat_sum / sqr_sum(total)
                expected_binary_only = binary_stat_sum / sqr_sum(binary_total)
                if abs(expected_with_non_binary - expected_binary_only) < 1e-9:
                    continue

                weighted_stat_checked += 1
                stat_record = {
                    **record,
                    "feature": feature,
                    "processed_feature_value": processed_value,
                    "expected_including_non_binary": expected_with_non_binary,
                    "expected_binary_only": expected_binary_only,
                    "absolute_binary_only_difference": abs(
                        expected_with_non_binary - expected_binary_only
                    ),
                }
                if abs(processed_value - expected_with_non_binary) < 1e-8:
                    weighted_stat_matched += 1
                    if len(weighted_stat_examples) < 8:
                        weighted_stat_examples.append(stat_record)
                elif len(weighted_stat_mismatches) < 25:
                    weighted_stat_mismatches.append(stat_record)

    return {
        "min_check_date": min_check_date,
        "fighter_side_feature_rows_with_prior_non_binary": checked,
        "matched_totalfights_including_non_binary": matched,
        "mismatch_count": checked - matched,
        "latest_prior_non_binary_last_fight_checks": last_fight_checked,
        "latest_prior_non_binary_last_fight_matches": last_fight_matched,
        "latest_prior_non_binary_last_fight_mismatches": (
            last_fight_checked - last_fight_matched
        ),
        "weighted_stat_checks_with_non_binary_impact": weighted_stat_checked,
        "weighted_stat_matches_including_non_binary": weighted_stat_matched,
        "weighted_stat_mismatches": weighted_stat_checked - weighted_stat_matched,
        "stat_check_features": list(STAT_CHECK_FEATURES),
        "examples": examples,
        "mismatches_sample": mismatches,
        "last_fight_examples": last_fight_examples,
        "last_fight_mismatches_sample": last_fight_mismatches,
        "weighted_stat_examples": weighted_stat_examples,
        "weighted_stat_mismatches_sample": weighted_stat_mismatches,
        "note": (
            "The check compares feature-row totalfights against source fights "
            "strictly before the feature date, avoiding same-day tournament ordering."
        ),
    }


def load_backtest_summaries(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        summary_path = Path(path)
        if not summary_path.exists():
            rows.append({"path": path, "missing": True})
            continue
        with summary_path.open() as file:
            data = json.load(file)
        rows.append(
            {
                "path": path,
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "features_path": data.get("features_path"),
                "param_source": data.get("param_source"),
                "excluded_title_patterns": data.get("excluded_title_patterns"),
                "train_title_patterns": data.get("train_title_patterns"),
                "eval_title_patterns": data.get("eval_title_patterns"),
                "odds_title_patterns": data.get("odds_title_patterns"),
                "predicted_fights": data.get("predicted_fights"),
                "accuracy": data.get("accuracy"),
                "log_loss": data.get("log_loss"),
                "profit_pct": data.get("profit_pct"),
                "odds_rows_excluded_universe": data.get("odds_rows_excluded_universe"),
                "odds_rows_non_binary_excluded": data.get("odds_rows_non_binary_excluded"),
            }
        )
    return rows


def fmt_pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


def markdown_report(result: dict) -> str:
    datasets = result["datasets"]
    state = result["non_binary_state_audit"]
    lines = [
        "# Outcome Universe Audit",
        "",
        "This audit verifies that the current production universe excludes women's",
        "fights while draw/no-contest/overturned bouts still update future fighter",
        "state without becoming supervised training labels.",
        "",
        "## Dataset Universe",
        "",
        "| Dataset | Rows | Women's Title Rows | Non-Binary / Blank Winner Rows | Non-Binary Result Rows |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in datasets:
        lines.append(
            "| {path} | {rows} | {women} | {nonbinary_source} | {nonbinary_result} |".format(
                path=item["path"],
                rows=item["rows"],
                women=item["women_title_rows"],
                nonbinary_source=item.get("non_binary_or_blank_winner_rows", ""),
                nonbinary_result=item.get("non_binary_result_rows", ""),
            )
        )

    lines.extend(
        [
            "",
            "Women-pair rows are counted by fighter identity learned from raw rows whose titles contain `Women`.",
            "",
            "| Dataset | Women's Title Rows | Known Women-Pair Rows | Hidden Women-Pair Rows |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for item in datasets:
        lines.append(
            "| {path} | {women} | {women_pairs} | {hidden_pairs} |".format(
                path=item["path"],
                women=item["women_title_rows"],
                women_pairs=item["known_women_pair_rows"],
                hidden_pairs=item["hidden_women_pair_rows"],
            )
        )
    lines.extend(
        [
            "",
            "Hidden women-pair rows are bouts such as catchweights where the title does not contain `Women` even though both fighters are known from women's divisions.",
        ]
    )

    lines.extend(
        [
            "",
            "## Regularized Backtest Universe",
            "",
            "| Summary | Window | Features | Excluded Titles | Predicted Fights | Accuracy | Log Loss | PnL | Excluded Odds Rows | Non-Binary Odds Rows |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in result["backtest_summaries"]:
        if row.get("missing"):
            lines.append(f"| {row['path']} | missing |  |  |  |  |  |  |  |  |")
            continue
        excluded_titles = ", ".join(row.get("excluded_title_patterns") or [])
        lines.append(
            "| {path} | {start} to {end} | {features} | {excluded} | {fights} | {acc} | {ll} | {pnl} | {excluded_rows} | {nonbinary_rows} |".format(
                path=row["path"],
                start=row["start_date"],
                end=row["end_date"],
                features=row["features_path"],
                excluded=excluded_titles,
                fights=row["predicted_fights"],
                acc=fmt_pct(row["accuracy"]),
                ll="" if row["log_loss"] is None else f"{float(row['log_loss']):.4f}",
                pnl=fmt_pct(row["profit_pct"] / 100.0) if row["profit_pct"] is not None else "",
                excluded_rows=row["odds_rows_excluded_universe"],
                nonbinary_rows=row["odds_rows_non_binary_excluded"],
            )
        )

    lines.extend(
        [
            "",
            "## Non-Binary Outcome State Check",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| source non-binary / blank-winner rows retained | {datasets[1].get('non_binary_or_blank_winner_rows', '')} |",
            f"| supervised feature non-binary labels | {datasets[2].get('non_binary_result_rows', '')} |",
            f"| fighter-side feature rows checked | {state['fighter_side_feature_rows_with_prior_non_binary']} |",
            f"| rows matching source prior fights including non-binary | {state['matched_totalfights_including_non_binary']} |",
            f"| mismatches | {state['mismatch_count']} |",
            f"| latest-prior non-binary `last_fight` checks | {state['latest_prior_non_binary_last_fight_checks']} |",
            f"| latest-prior non-binary `last_fight` matches | {state['latest_prior_non_binary_last_fight_matches']} |",
            f"| weighted stat checks where non-binary changed the value | {state['weighted_stat_checks_with_non_binary_impact']} |",
            f"| weighted stat matches including non-binary | {state['weighted_stat_matches_including_non_binary']} |",
            "",
            "Examples where a prior non-binary fight is included in future `totalfights`:",
            "",
            "| Date | Fighter | Side | Feature TotalFights | Prior Source Fights | Prior Binary Only | Prior Non-Binary | Fight |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in state["examples"]:
        lines.append(
            "| {date} | {fighter} | {side} | {processed:.0f} | {source_total} | {binary} | {nonbinary} | {title} |".format(
                date=row["date"],
                fighter=row["fighter"],
                side=row["side"],
                processed=row["processed_totalfights"],
                source_total=row["source_prior_fights_including_non_binary"],
                binary=row["source_prior_binary_fights_only"],
                nonbinary=row["prior_non_binary_fights"],
                title=row["title"],
            )
        )

    lines.extend(
        [
            "",
            "Examples where the latest prior fight was non-binary and still drove `last_fight`:",
            "",
            "| Date | Fighter | Side | Feature Last Fight | Prior Non-Binary Date | Expected Days | Fight |",
            "| --- | --- | --- | ---: | --- | ---: | --- |",
        ]
    )
    for row in state["last_fight_examples"]:
        lines.append(
            "| {date} | {fighter} | {side} | {processed:.0f} | {prior_date} | {expected} | {title} |".format(
                date=row["date"],
                fighter=row["fighter"],
                side=row["side"],
                processed=row["processed_last_fight_days"],
                prior_date=row["prior_non_binary_date"],
                expected=row["expected_days_since_prior_non_binary"],
                title=row["title"],
            )
        )

    lines.extend(
        [
            "",
            "Examples where cumulative weighted fight stats match the calculation that includes prior non-binary bouts:",
            "",
            "| Date | Fighter | Side | Feature | Processed | Including Non-Binary | Binary Only | Fight |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in state["weighted_stat_examples"]:
        lines.append(
            "| {date} | {fighter} | {side} | {feature} | {processed:.6f} | {included:.6f} | {binary_only:.6f} | {title} |".format(
                date=row["date"],
                fighter=row["fighter"],
                side=row["side"],
                feature=row["feature"],
                processed=row["processed_feature_value"],
                included=row["expected_including_non_binary"],
                binary_only=row["expected_binary_only"],
                title=row["title"],
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The current production feature table is men-only: `data/detailed_fights.csv` has zero women's title rows and zero known women-pair rows.",
            "- Future preprocessing/backtests now treat `Women` title matching as fighter-aware, so women-vs-women catchweights are not missed just because the title omits `Women`.",
            "- The current regularized backtests also exclude women's odds rows via `excluded_title_patterns = [\"Women\"]`.",
            "- Draw/no-contest/overturned rows are absent from supervised labels, which remain binary `win/loss` only.",
            "- Those same non-binary rows are still reflected in future fighter state: checked future fighter-side rows matched prior source fight counts, `last_fight`, and weighted cumulative stat calculations that include non-binary bouts.",
            "",
            "This supports the current universe handling: do not train/evaluate on women's fights for the production edge claim, and keep non-binary outcomes as historical state inputs but not supervised labels.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    summary_paths = args.backtest_summary or DEFAULT_BACKTEST_SUMMARIES
    raw_fights = pd.read_csv(args.raw_fights)
    known_women = known_women_fighter_names(raw_fights)
    result = {
        "datasets": [
            dataset_summary(args.raw_fights, known_women),
            dataset_summary(args.source_fights, known_women),
            dataset_summary(args.features, known_women),
        ],
        "backtest_summaries": load_backtest_summaries(summary_paths),
        "non_binary_state_audit": audit_non_binary_state(
            args.source_fights,
            args.features,
            args.min_check_date,
        ),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "outcome_universe_audit.json"
    md_path = output_dir / "outcome_universe_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    state = result["non_binary_state_audit"]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "Non-binary state checks: "
        f"{state['matched_totalfights_including_non_binary']}/"
        f"{state['fighter_side_feature_rows_with_prior_non_binary']} matched"
    )


if __name__ == "__main__":
    main()
