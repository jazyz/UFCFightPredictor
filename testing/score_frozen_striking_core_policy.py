#!/usr/bin/env python3
"""Generate pre-outcome paper bets for the frozen striking-core policy."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.market_aware_feature_audit import aligned_market_feature_frame, fit_predict_variant  # noqa: E402
from testing.market_residual_meta_audit import logit  # noqa: E402
from testing.no_leakage_backtest import load_known_women_fighter_keys  # noqa: E402
from testing.statistical_edge_audit import net_odds, parse_odds  # noqa: E402
from testing.striking_feature_engineering_audit import (  # noqa: E402
    add_pace_features,
    build_current_pace_features,
    build_pace_features,
)
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_POLICY = "test_results/frozen_striking_core_paper_policy/frozen_striking_core_paper_policy.json"
DEFAULT_UPCOMING_FEATURES = "data/predict_fights_alpha.csv"
DEFAULT_HISTORICAL_FEATURES = "data/detailed_fights.csv"
DEFAULT_ODDS_HISTORY = "data/fight_results_with_odds.csv"
DEFAULT_FIGHT_DETAILS = "data/fight_details_date.csv"
DEFAULT_SOURCE_FIGHTS = "data/modified_fight_details.csv"
DEFAULT_OUTPUT_CSV = "test_results/forward_paper_tracking/latest_striking_core_paper_bets.csv"
DEFAULT_OUTPUT_JSON = "test_results/forward_paper_tracking/latest_striking_core_paper_bets.json"

LEDGER_COLUMNS = [
    "generated_at_utc",
    "event_key",
    "fight_card_link",
    "policy_path",
    "policy_as_of_date",
    "policy_json",
    "historical_features",
    "historical_odds",
    "upcoming_features",
    "train_through",
    "training_rows",
    "model_variant",
    "fight_index",
    "fighter1",
    "fighter2",
    "fighter1_odds",
    "fighter2_odds",
    "feature_red_fighter",
    "feature_blue_fighter",
    "fighter1_market_probability",
    "fighter2_market_probability",
    "fighter1_policy_probability",
    "fighter2_policy_probability",
    "fighter1_edge",
    "fighter2_edge",
    "selected_fighter",
    "selected_odds",
    "selected_market_probability",
    "selected_policy_probability",
    "selected_edge",
    "stake",
    "potential_profit",
    "potential_return_with_stake",
    "bet_placed",
    "no_bet_reason",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Score frozen striking-core paper bets")
    parser.add_argument(
        "--fights",
        required=True,
        help=(
            "CSV with fighter1, fighter2, fighter1_odds, fighter2_odds. "
            "Optional columns: fight_index, event_key, fight_card_link."
        ),
    )
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--upcoming-features", default=DEFAULT_UPCOMING_FEATURES)
    parser.add_argument("--historical-features", default=DEFAULT_HISTORICAL_FEATURES)
    parser.add_argument("--historical-odds", default=DEFAULT_ODDS_HISTORY)
    parser.add_argument("--fight-details-source", default=DEFAULT_FIGHT_DETAILS)
    parser.add_argument("--source-fights", default=DEFAULT_SOURCE_FIGHTS)
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument(
        "--train-through",
        default="",
        help="Optional YYYY-MM-DD max historical fight date for training.",
    )
    parser.add_argument("--event-key", default="")
    parser.add_argument("--fight-card-link", default="")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: str) -> dict:
    with Path(path).open() as file:
        return json.load(file)


def odds_to_prob(odds: float) -> float:
    if odds >= 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def devig_market_probabilities(odds1: float, odds2: float) -> tuple[float, float] | tuple[None, None]:
    raw1 = odds_to_prob(odds1)
    raw2 = odds_to_prob(odds2)
    total = raw1 + raw2
    if not np.isfinite(total) or total <= 0:
        return None, None
    return raw1 / total, raw2 / total


def optional_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def load_fights(path: str) -> pd.DataFrame:
    fights = pd.read_csv(path)
    required = {"fighter1", "fighter2", "fighter1_odds", "fighter2_odds"}
    missing = required - set(fights.columns)
    if missing:
        raise SystemExit(f"{path} is missing fight columns: {sorted(missing)}")
    return fights


def row_fight_index(row: pd.Series, fallback: int):
    value = row.get("fight_index")
    if value is None or pd.isna(value) or str(value).strip() == "":
        return fallback
    return value


def needs_source_derived_pace(policy: dict) -> bool:
    return str(policy.get("feature_engineering", "")).strip() == "source_derived_pace"


def augment_historical_training(train_df: pd.DataFrame, args, policy: dict) -> pd.DataFrame:
    if not needs_source_derived_pace(policy):
        return train_df
    source = pd.read_csv(args.source_fights)
    features = pd.read_csv(args.historical_features)
    pace_features, _ = build_pace_features(source, features)
    augmented, metadata = add_pace_features(train_df, pace_features)
    if metadata["aligned_rows_missing_pace_features"]:
        raise SystemExit(
            "Historical training data missing source-derived pace features for "
            f"{metadata['aligned_rows_missing_pace_features']} rows"
        )
    return augmented


def load_historical_training(args, policy: dict) -> pd.DataFrame:
    align_args = SimpleNamespace(
        features=args.historical_features,
        odds=args.historical_odds,
        fight_details_source=args.fight_details_source,
        min_training_date=args.min_training_date,
        last_holdout_end=args.train_through or "2099-12-31",
        include_womens_fights=bool(policy.get("include_womens_fights", False)),
    )
    aligned, _ = aligned_market_feature_frame(align_args)
    if args.train_through:
        aligned = aligned[aligned["event_date"] <= pd.Timestamp(args.train_through)].copy()
    if aligned.empty:
        raise SystemExit("No historical aligned rows available for striking-core training")
    aligned = aligned.sort_values(["event_date", "fight_key"]).reset_index(drop=True)
    return augment_historical_training(aligned, args, policy)


def feature_pair_key(fighter1, fighter2) -> frozenset[str]:
    return frozenset({canonical_name(fighter1), canonical_name(fighter2)})


def augment_upcoming_features(df: pd.DataFrame, args, policy: dict, train_df: pd.DataFrame) -> pd.DataFrame:
    if not needs_source_derived_pace(policy):
        return df
    source = pd.read_csv(args.source_fights)
    train_through = pd.Timestamp(train_df["event_date"].max()).normalize()
    pace = build_current_pace_features(source, df, train_through)
    augmented = df.copy()
    for column in pace.columns:
        augmented[column] = pace[column]
    return augmented


def load_upcoming_features(path: str, args, policy: dict, train_df: pd.DataFrame) -> dict[frozenset[str], list[dict]]:
    df = pd.read_csv(path)
    required = {"Red Fighter", "Blue Fighter"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"{path} is missing feature columns: {sorted(missing)}")
    df = augment_upcoming_features(df, args, policy, train_df)
    rows: dict[frozenset[str], list[dict]] = {}
    for _, row in df.iterrows():
        key = feature_pair_key(row["Red Fighter"], row["Blue Fighter"])
        rows.setdefault(key, []).append(row.to_dict())
    return rows


def choose_feature_row(feature_rows: dict[frozenset[str], list[dict]], fighter1: str, fighter2: str) -> dict | None:
    key = feature_pair_key(fighter1, fighter2)
    candidates = feature_rows.get(key, [])
    if not candidates:
        return None
    fighter1_key = canonical_name(fighter1)
    fighter2_key = canonical_name(fighter2)
    for row in candidates:
        if canonical_name(row.get("Red Fighter", "")) == fighter1_key and canonical_name(row.get("Blue Fighter", "")) == fighter2_key:
            return row
    for row in candidates:
        if canonical_name(row.get("Red Fighter", "")) == fighter2_key and canonical_name(row.get("Blue Fighter", "")) == fighter1_key:
            return row
    return candidates[0]


def is_womens_fight(feature_row: dict, fighter1: str, fighter2: str, women_fighter_keys: set[str]) -> bool:
    title = optional_text(feature_row.get("Title")).lower()
    if "women" in title:
        return True
    if not women_fighter_keys:
        return False
    fighter1_key = canonical_name(fighter1)
    fighter2_key = canonical_name(fighter2)
    red_key = canonical_name(feature_row.get("Red Fighter", ""))
    blue_key = canonical_name(feature_row.get("Blue Fighter", ""))
    return (
        fighter1_key in women_fighter_keys
        and fighter2_key in women_fighter_keys
        and red_key in women_fighter_keys
        and blue_key in women_fighter_keys
    )


def score_probability(
    train_df: pd.DataFrame,
    feature_row: dict,
    red_market_probability: float,
    policy: dict,
) -> float:
    eval_df = pd.DataFrame([feature_row]).copy()
    eval_df["market_logit"] = float(logit(red_market_probability))
    _, missing = policy_columns(policy, eval_df)
    if missing:
        raise SystemExit(f"Upcoming feature row missing policy columns: {missing}")
    probabilities, _ = fit_predict_variant(
        train_df,
        eval_df,
        train_df["red_won"].astype(int).to_numpy(),
        tuple(policy["feature_columns"]),
        float(policy["logistic_l2_c"]),
    )
    return float(probabilities[0])


def policy_columns(policy: dict, frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    columns = list(policy["feature_columns"])
    missing = [column for column in columns if column not in frame.columns]
    return columns, missing


def empty_row(fight_index, fighter1, fighter2, odds1, odds2, reason: str) -> dict:
    return {
        "fight_index": fight_index,
        "fighter1": fighter1,
        "fighter2": fighter2,
        "fighter1_odds": odds1 if odds1 is not None else "",
        "fighter2_odds": odds2 if odds2 is not None else "",
        "feature_red_fighter": "",
        "feature_blue_fighter": "",
        "fighter1_market_probability": "",
        "fighter2_market_probability": "",
        "fighter1_policy_probability": "",
        "fighter2_policy_probability": "",
        "fighter1_edge": "",
        "fighter2_edge": "",
        "selected_fighter": "",
        "selected_odds": "",
        "selected_market_probability": "",
        "selected_policy_probability": "",
        "selected_edge": "",
        "stake": 0.0,
        "potential_profit": 0.0,
        "potential_return_with_stake": 0.0,
        "bet_placed": False,
        "no_bet_reason": reason,
    }


def choose_side(fighter1, fighter2, odds1, odds2, p1, market1, market2) -> dict:
    sides = [
        {
            "fighter": fighter1,
            "odds": odds1,
            "policy_probability": p1,
            "market_probability": market1,
            "edge": p1 - market1,
        },
        {
            "fighter": fighter2,
            "odds": odds2,
            "policy_probability": 1.0 - p1,
            "market_probability": market2,
            "edge": (1.0 - p1) - market2,
        },
    ]
    return max(sides, key=lambda side: (side["edge"], side["policy_probability"], canonical_name(side["fighter"])))


def score_fight(
    row: pd.Series,
    fight_index,
    train_df: pd.DataFrame,
    feature_rows: dict[frozenset[str], list[dict]],
    policy: dict,
    women_fighter_keys: set[str],
) -> dict:
    fighter1 = str(row.get("fighter1", "")).strip()
    fighter2 = str(row.get("fighter2", "")).strip()
    odds1 = parse_odds(row.get("fighter1_odds"))
    odds2 = parse_odds(row.get("fighter2_odds"))
    if not fighter1 or not fighter2:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "missing fighter")
    if odds1 is None or odds2 is None:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "missing odds")
    market1, market2 = devig_market_probabilities(odds1, odds2)
    if market1 is None or market2 is None:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "could not score market probabilities")
    feature_row = choose_feature_row(feature_rows, fighter1, fighter2)
    if feature_row is None:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "feature row not found")
    if not bool(policy.get("include_womens_fights", False)) and is_womens_fight(
        feature_row,
        fighter1,
        fighter2,
        women_fighter_keys,
    ):
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "women's fight excluded")

    red_key = canonical_name(feature_row.get("Red Fighter", ""))
    fighter1_key = canonical_name(fighter1)
    fighter2_key = canonical_name(fighter2)
    if red_key == fighter1_key:
        red_market = market1
        p_red = score_probability(train_df, feature_row, red_market, policy)
        p1 = p_red
    elif red_key == fighter2_key:
        red_market = market2
        p_red = score_probability(train_df, feature_row, red_market, policy)
        p1 = 1.0 - p_red
    else:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "feature orientation mismatch")

    selected = choose_side(fighter1, fighter2, odds1, odds2, p1, market1, market2)
    reasons = []
    if selected["edge"] < float(policy["min_edge"]):
        reasons.append("edge below threshold")
    if selected["policy_probability"] < float(policy["min_probability"]):
        reasons.append("probability below threshold")

    stake = float(policy["stake_units"]) if not reasons else 0.0
    potential_profit = stake * net_odds(selected["odds"]) if stake > 0 else 0.0
    return {
        "fight_index": fight_index,
        "fighter1": fighter1,
        "fighter2": fighter2,
        "fighter1_odds": odds1,
        "fighter2_odds": odds2,
        "feature_red_fighter": feature_row.get("Red Fighter", ""),
        "feature_blue_fighter": feature_row.get("Blue Fighter", ""),
        "fighter1_market_probability": market1,
        "fighter2_market_probability": market2,
        "fighter1_policy_probability": p1,
        "fighter2_policy_probability": 1.0 - p1,
        "fighter1_edge": p1 - market1,
        "fighter2_edge": (1.0 - p1) - market2,
        "selected_fighter": selected["fighter"],
        "selected_odds": selected["odds"],
        "selected_market_probability": selected["market_probability"],
        "selected_policy_probability": selected["policy_probability"],
        "selected_edge": selected["edge"],
        "stake": stake,
        "potential_profit": potential_profit,
        "potential_return_with_stake": stake + potential_profit,
        "bet_placed": stake > 0,
        "no_bet_reason": "; ".join(reasons),
    }


def metadata(args, policy_artifact: dict, train_df: pd.DataFrame, generated_at_utc: str) -> dict:
    policy = policy_artifact["policy"]
    train_through = pd.Timestamp(train_df["event_date"].max()).date().isoformat()
    return {
        "generated_at_utc": generated_at_utc,
        "event_key": args.event_key or args.fight_card_link or generated_at_utc,
        "fight_card_link": args.fight_card_link,
        "policy_path": args.policy,
        "policy_as_of_date": policy_artifact.get("as_of_date", ""),
        "policy_json": json.dumps(policy, sort_keys=True),
        "historical_features": args.historical_features,
        "historical_odds": args.historical_odds,
        "upcoming_features": args.upcoming_features,
        "train_through": train_through,
        "training_rows": int(len(train_df)),
        "model_variant": policy["variant"],
    }


def add_metadata(rows: list[dict], meta: dict, fights: pd.DataFrame) -> list[dict]:
    output = []
    for row, (_, source) in zip(rows, fights.iterrows()):
        row_meta = dict(meta)
        row_meta["event_key"] = (
            optional_text(source.get("event_key"))
            or optional_text(source.get("fight_card_link"))
            or meta["event_key"]
        )
        row_meta["fight_card_link"] = optional_text(source.get("fight_card_link")) or meta["fight_card_link"]
        output.append({column: {**row_meta, **row}.get(column, "") for column in LEDGER_COLUMNS})
    return output


def write_outputs(rows: list[dict], meta: dict, args, policy_artifact: dict):
    csv_path = Path(args.output_csv)
    json_path = Path(args.output_json)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "metadata": meta,
        "policy": policy_artifact,
        "rows": rows,
        "warning": (
            "Frozen striking-core paper-tracking recommendations only. "
            "Archive before outcomes are known if this run will be used as evidence."
        ),
    }
    with json_path.open("w") as file:
        json.dump(payload, file, indent=2)
    return csv_path, json_path


def main():
    args = parse_args()
    policy_artifact = load_json(args.policy)
    policy = policy_artifact["policy"]
    fights = load_fights(args.fights)
    train_df = load_historical_training(args, policy)
    _, missing = policy_columns(policy, train_df)
    if missing:
        raise SystemExit(f"Historical training data missing policy columns: {missing}")
    feature_rows = load_upcoming_features(args.upcoming_features, args, policy, train_df)
    women_fighter_keys = set()
    if not bool(policy.get("include_womens_fights", False)):
        women_fighter_keys = load_known_women_fighter_keys(args.fight_details_source)

    scored = []
    for fallback_index, (_, row) in enumerate(fights.iterrows(), start=1):
        scored.append(
            score_fight(
                row,
                row_fight_index(row, fallback_index),
                train_df,
                feature_rows,
                policy,
                women_fighter_keys,
            )
        )
    generated_at_utc = utc_now_iso()
    meta = metadata(args, policy_artifact, train_df, generated_at_utc)
    output_rows = add_metadata(scored, meta, fights)
    csv_path, json_path = write_outputs(output_rows, meta, args, policy_artifact)

    bets = sum(1 for row in output_rows if str(row.get("bet_placed")).lower() == "true")
    print(f"Training rows: {len(train_df)}")
    print(f"Scored fights: {len(output_rows)}")
    print(f"Paper bets: {bets}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
