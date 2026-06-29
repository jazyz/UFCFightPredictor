#!/usr/bin/env python3
"""Build and summarize leak-safe recent-form feature variants.

The production feature table is mostly cumulative. This audit creates an
alternate feature table with simple recent form/activity features computed only
from source fights strictly before each modeled fight date.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.name_matching import canonical_name  # noqa: E402


RECENT_WINDOWS = (3, 5)
ACTIVITY_WINDOWS_DAYS = (365, 730)
RECENT_METRICS = (
    "recent_score",
    "recent_binary_win_rate",
    "recent_finish_win_rate",
    "recent_finish_loss_rate",
    "recent_nonbinary_rate",
    "recent_minutes",
    "recent_sig_str_pm",
    "recent_absorbed_sig_str_pm",
    "recent_td_per15",
    "recent_absorbed_td_per15",
    "recent_kd_per_fight",
    "recent_absorbed_kd_per_fight",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Build recent-form feature variant table")
    parser.add_argument("--source-fights", default="data/modified_fight_details.csv")
    parser.add_argument("--base-features", default="data/detailed_fights.csv")
    parser.add_argument("--output-dir", default="test_results/recent_form_feature_audit")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="only regenerate the markdown summary from existing outputs",
    )
    return parser.parse_args()


def parse_date(value):
    return pd.to_datetime(value, format="mixed", errors="coerce")


def safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def elapsed_minutes(row: pd.Series) -> float | None:
    round_number = safe_float(row.get("Round"))
    time_value = safe_float(row.get("Time"))
    if round_number is None or time_value is None:
        return None
    elapsed = (round_number - 1.0) * 5.0 + time_value
    if elapsed <= 0:
        return None
    return elapsed


def is_draw_flag(value) -> bool:
    return str(value).strip().lower() == "true"


def is_decision_method(value) -> bool:
    return "decision" in str(value).strip().lower()


def result_scores(row: pd.Series, red_key: str, blue_key: str) -> tuple[float, float, bool]:
    winner_key = canonical_name(row.get("Winner", ""))
    if not winner_key or is_draw_flag(row.get("Draw")):
        return 0.5, 0.5, False
    if winner_key == red_key:
        return 1.0, 0.0, True
    if winner_key == blue_key:
        return 0.0, 1.0, True
    return 0.5, 0.5, False


def numeric_side(row: pd.Series, side: str, feature: str) -> float:
    value = safe_float(row.get(f"{side} {feature}"))
    return 0.0 if value is None else value


def fight_record(row: pd.Series, side: str, score: float, binary: bool) -> dict:
    opponent = "Blue" if side == "Red" else "Red"
    minutes = elapsed_minutes(row)
    sig_str = numeric_side(row, side, "Sig. str.")
    absorbed_sig_str = numeric_side(row, opponent, "Sig. str.")
    td = numeric_side(row, side, "Td")
    absorbed_td = numeric_side(row, opponent, "Td")
    kd = numeric_side(row, side, "KD")
    absorbed_kd = numeric_side(row, opponent, "KD")
    finish = not is_decision_method(row.get("Method"))

    return {
        "date": row["DateParsed"],
        "score": score,
        "binary_win": score if binary else np.nan,
        "finish_win": 1.0 if binary and score == 1.0 and finish else 0.0,
        "finish_loss": 1.0 if binary and score == 0.0 and finish else 0.0,
        "nonbinary": 0.0 if binary else 1.0,
        "minutes": minutes,
        "sig_str_pm": sig_str / minutes if minutes else np.nan,
        "absorbed_sig_str_pm": absorbed_sig_str / minutes if minutes else np.nan,
        "td_per15": (td / minutes) * 15.0 if minutes else np.nan,
        "absorbed_td_per15": (absorbed_td / minutes) * 15.0 if minutes else np.nan,
        "kd_per_fight": kd,
        "absorbed_kd_per_fight": absorbed_kd,
    }


def load_source_records(path: str) -> pd.DataFrame:
    source = pd.read_csv(path)
    source["DateParsed"] = parse_date(source["Date"])
    source = source.dropna(subset=["DateParsed", "Red Fighter", "Blue Fighter"])
    return source.sort_values("DateParsed", kind="mergesort").reset_index(drop=True)


def build_history_records(source: pd.DataFrame) -> list[tuple[pd.Timestamp, str, dict]]:
    records = []
    for _, row in source.iterrows():
        red_key = canonical_name(row["Red Fighter"])
        blue_key = canonical_name(row["Blue Fighter"])
        red_score, blue_score, binary = result_scores(row, red_key, blue_key)
        event_date = row["DateParsed"]
        records.append((event_date, red_key, fight_record(row, "Red", red_score, binary)))
        records.append((event_date, blue_key, fight_record(row, "Blue", blue_score, binary)))
    return sorted(records, key=lambda item: item[0])


def nanmean(values) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return np.nan
    return float(array.mean())


def summarize_history(history: list[dict], event_date: pd.Timestamp) -> dict:
    output = {}
    for window in RECENT_WINDOWS:
        recent = history[-window:]
        output[f"recent_score_{window}"] = nanmean([row["score"] for row in recent])
        output[f"recent_binary_win_rate_{window}"] = nanmean(
            [row["binary_win"] for row in recent]
        )
        output[f"recent_finish_win_rate_{window}"] = nanmean(
            [row["finish_win"] for row in recent]
        )
        output[f"recent_finish_loss_rate_{window}"] = nanmean(
            [row["finish_loss"] for row in recent]
        )
        output[f"recent_nonbinary_rate_{window}"] = nanmean(
            [row["nonbinary"] for row in recent]
        )
        output[f"recent_minutes_{window}"] = nanmean([row["minutes"] for row in recent])
        output[f"recent_sig_str_pm_{window}"] = nanmean(
            [row["sig_str_pm"] for row in recent]
        )
        output[f"recent_absorbed_sig_str_pm_{window}"] = nanmean(
            [row["absorbed_sig_str_pm"] for row in recent]
        )
        output[f"recent_td_per15_{window}"] = nanmean([row["td_per15"] for row in recent])
        output[f"recent_absorbed_td_per15_{window}"] = nanmean(
            [row["absorbed_td_per15"] for row in recent]
        )
        output[f"recent_kd_per_fight_{window}"] = nanmean(
            [row["kd_per_fight"] for row in recent]
        )
        output[f"recent_absorbed_kd_per_fight_{window}"] = nanmean(
            [row["absorbed_kd_per_fight"] for row in recent]
        )

    for days in ACTIVITY_WINDOWS_DAYS:
        cutoff = event_date - pd.Timedelta(days=days)
        windowed = [row for row in history if row["date"] >= cutoff]
        output[f"recent_fights_{days}d"] = float(len(windowed))
        output[f"recent_wins_{days}d"] = float(
            sum(1 for row in windowed if row["binary_win"] == 1.0)
        )
        output[f"recent_losses_{days}d"] = float(
            sum(1 for row in windowed if row["binary_win"] == 0.0)
        )
        output[f"recent_nonbinary_{days}d"] = float(
            sum(1 for row in windowed if row["nonbinary"] == 1.0)
        )
    return output


def add_pair_features(row: dict, red_summary: dict, blue_summary: dict) -> dict:
    for name, value in red_summary.items():
        row[f"Red {name}"] = value
    for name, value in blue_summary.items():
        row[f"Blue {name}"] = value
    for name in red_summary:
        red = red_summary.get(name)
        blue = blue_summary.get(name)
        row[f"{name} oppdiff"] = red - blue if np.isfinite(red) and np.isfinite(blue) else np.nan
        row[f"{name} absdiff"] = abs(red - blue) if np.isfinite(red) and np.isfinite(blue) else np.nan
    return row


def build_recent_form_features(source_path: str, base_path: str, output_path: Path) -> dict:
    source = load_source_records(source_path)
    records = build_history_records(source)
    base = pd.read_csv(base_path)
    base["DateParsed"] = parse_date(base["Date"])
    base = base.sort_values("DateParsed", kind="mergesort").reset_index(drop=True)

    histories: dict[str, list[dict]] = defaultdict(list)
    cursor = 0
    augmented_rows = []
    for _, feature_row in base.iterrows():
        event_date = feature_row["DateParsed"]
        while cursor < len(records) and records[cursor][0] < event_date:
            _, fighter_key, record = records[cursor]
            histories[fighter_key].append(record)
            cursor += 1

        red_key = canonical_name(feature_row["Red Fighter"])
        blue_key = canonical_name(feature_row["Blue Fighter"])
        red_summary = summarize_history(histories.get(red_key, []), event_date)
        blue_summary = summarize_history(histories.get(blue_key, []), event_date)
        row = feature_row.drop(labels=["DateParsed"]).to_dict()
        augmented_rows.append(add_pair_features(row, red_summary, blue_summary))

    output = pd.DataFrame(augmented_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    added_columns = [column for column in output.columns if column not in pd.read_csv(base_path, nrows=0).columns]
    return {
        "source_fights": source_path,
        "base_features": base_path,
        "output_features": str(output_path),
        "rows": int(len(output)),
        "added_columns": added_columns,
        "added_column_count": int(len(added_columns)),
    }


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open() as file:
        return json.load(file)


def fmt_pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


def fmt_float(value, digits=4) -> str:
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def fmt_money(value) -> str:
    if value is None:
        return ""
    return f"${float(value):,.2f}"


def markdown_report(result: dict) -> str:
    lines = [
        "# Recent Form Feature Audit",
        "",
        "This audit builds an alternate feature table with recent-form and recent-activity",
        "features computed only from source fights strictly before each modeled fight date.",
        "",
        "## Feature Build",
        "",
        f"- source fights: `{result['source_fights']}`",
        f"- base features: `{result['base_features']}`",
        f"- output features: `{result['output_features']}`",
        f"- rows: `{result['rows']}`",
        f"- added columns: `{result['added_column_count']}`",
        "",
        "Feature families include last-3/last-5 result score, binary win rate,",
        "finish win/loss rate, non-binary rate, minutes, recent striking/grappling",
        "rates, knockdown rates, and 365/730-day activity counts.",
    ]

    comparisons = result.get("comparisons") or []
    if comparisons:
        lines.extend(
            [
                "",
                "## Leak-Safe Comparison",
                "",
                "| Window | Feature Set | Fights | Accuracy | Log Loss | Final Bankroll | PnL | Market LL |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in comparisons:
            lines.append(
                "| {window} | {feature_set} | {fights} | {accuracy} | {log_loss} | {bankroll} | {pnl} | {market_ll} |".format(
                    window=row["window"],
                    feature_set=row["feature_set"],
                    fights=row.get("predicted_fights", ""),
                    accuracy=fmt_pct(row.get("accuracy")),
                    log_loss=fmt_float(row.get("log_loss")),
                    bankroll=fmt_money(row.get("final_bankroll")),
                    pnl=fmt_pct((row.get("profit_pct") or 0.0) / 100.0)
                    if row.get("profit_pct") is not None
                    else "",
                    market_ll=fmt_float(row.get("market_log_loss")),
                )
            )
        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                result.get("interpretation", "Backtests have not been summarized yet."),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Next Commands",
                "",
                "Run the regularized leak-safe backtests against the generated feature table,",
                "then rerun this script with `--summary` to refresh this report.",
            ]
        )
    return "\n".join(lines) + "\n"


def collect_comparisons(output_dir: Path) -> list[dict]:
    candidates = [
        (
            "2025-06-27 to 2026-06-27",
            "current regularized",
            Path("test_results/regularized_lgbm_1y/no_leakage_backtest_summary.json"),
        ),
        (
            "2025-06-27 to 2026-06-27",
            "recent-form challenger",
            output_dir / "regularized_recent_form_1y" / "no_leakage_backtest_summary.json",
        ),
        (
            "2024-06-27 to 2026-06-27",
            "current regularized",
            Path("test_results/regularized_lgbm_2y/no_leakage_backtest_summary.json"),
        ),
        (
            "2024-06-27 to 2026-06-27",
            "recent-form challenger",
            output_dir / "regularized_recent_form_2y" / "no_leakage_backtest_summary.json",
        ),
    ]
    rows = []
    for window, feature_set, path in candidates:
        summary = load_json(path)
        if not summary:
            continue
        rows.append(
            {
                "window": window,
                "feature_set": feature_set,
                "summary_path": str(path),
                "predicted_fights": summary.get("predicted_fights"),
                "accuracy": summary.get("accuracy"),
                "log_loss": summary.get("log_loss"),
                "market_log_loss": summary.get("market_log_loss"),
                "final_bankroll": summary.get("final_bankroll"),
                "profit_pct": summary.get("profit_pct"),
            }
        )
    return rows


def interpretation_from_comparisons(rows: list[dict]) -> str:
    recent = [row for row in rows if row["feature_set"] == "recent-form challenger"]
    current_by_window = {
        row["window"]: row for row in rows if row["feature_set"] == "current regularized"
    }
    if len(recent) < 2:
        return "Backtests have not been summarized yet."

    outcomes = []
    for row in recent:
        current = current_by_window.get(row["window"])
        if not current:
            continue
        ll_delta = row["log_loss"] - current["log_loss"]
        pnl_delta = row["profit_pct"] - current["profit_pct"]
        outcomes.append((row["window"], ll_delta, pnl_delta))

    if all(ll_delta < 0 for _, ll_delta, _ in outcomes):
        return (
            "The recent-form challenger improved log loss in all summarized windows. "
            "This makes it a credible feature-family candidate for a longer nested audit "
            "before any production promotion."
        )
    if any(ll_delta < 0 for _, ll_delta, _ in outcomes):
        return (
            "The recent-form challenger is mixed: it improves at least one window but "
            "does not improve all summarized log-loss windows. Treat it as exploratory "
            "and require a longer nested/probability audit before promotion."
        )
    return (
        "The recent-form challenger does not improve summarized log loss versus the "
        "current regularized feature set. Do not promote this feature family."
    )


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_path = output_dir / "detailed_fights_recent_form.csv"
    metadata_path = output_dir / "recent_form_feature_audit.json"
    report_path = output_dir / "RECENT_FORM_FEATURE_AUDIT.md"

    if args.summary and metadata_path.exists():
        result = load_json(metadata_path)
    else:
        result = build_recent_form_features(args.source_fights, args.base_features, feature_path)

    comparisons = collect_comparisons(output_dir)
    result["comparisons"] = comparisons
    result["interpretation"] = interpretation_from_comparisons(comparisons)
    result["outputs"] = {
        "features_csv": str(feature_path),
        "summary_json": str(metadata_path),
        "report_md": str(report_path),
    }

    with metadata_path.open("w") as file:
        json.dump(result, file, indent=2)
    report_path.write_text(markdown_report(result))

    print(f"Rows: {result['rows']}")
    print(f"Added columns: {result['added_column_count']}")
    print(f"Wrote {feature_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
