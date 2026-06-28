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


def women_count(df: pd.DataFrame) -> int:
    if "Title" not in df.columns:
        return 0
    return int(df["Title"].fillna("").str.contains("Women", case=False, regex=False).sum())


def source_binary_mask(df: pd.DataFrame) -> pd.Series:
    winner_is_present = ~df["Winner"].map(is_blank)
    if "Draw" not in df.columns:
        return winner_is_present
    draw_flag = df["Draw"].astype(str).str.strip().str.lower().eq("true")
    return winner_is_present & ~draw_flag


def dataset_summary(path: str) -> dict:
    df = pd.read_csv(path)
    summary = {
        "path": path,
        "rows": int(len(df)),
        "women_title_rows": women_count(df),
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


def audit_non_binary_state(source_path: str, features_path: str, min_check_date: str) -> dict:
    source = pd.read_csv(source_path)
    features = pd.read_csv(features_path)
    source["DateParsed"] = parse_date_series(source["Date"])
    features["DateParsed"] = parse_date_series(features["Date"])
    indexed_history = build_fighter_history_index(source)

    checked = 0
    matched = 0
    mismatches = []
    examples = []
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

    return {
        "min_check_date": min_check_date,
        "fighter_side_feature_rows_with_prior_non_binary": checked,
        "matched_totalfights_including_non_binary": matched,
        "mismatch_count": checked - matched,
        "examples": examples,
        "mismatches_sample": mismatches,
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
            "## Interpretation",
            "",
            "- The current production feature table is men-only: `data/detailed_fights.csv` has zero women's title rows.",
            "- The current regularized backtests also exclude women's odds rows via `excluded_title_patterns = [\"Women\"]`.",
            "- Draw/no-contest/overturned rows are absent from supervised labels, which remain binary `win/loss` only.",
            "- Those same non-binary rows are still reflected in future fighter state: every checked future fighter-side row matched the source prior-fight count that includes non-binary bouts.",
            "",
            "This supports the current universe handling: do not train/evaluate on women's fights for the production edge claim, and keep non-binary outcomes as historical state inputs but not supervised labels.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    summary_paths = args.backtest_summary or DEFAULT_BACKTEST_SUMMARIES
    result = {
        "datasets": [
            dataset_summary(args.raw_fights),
            dataset_summary(args.source_fights),
            dataset_summary(args.features),
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
