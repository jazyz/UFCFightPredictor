#!/usr/bin/env python3
"""
Leak-safe rolling backtest for UFC Fight Predictor.

For every event date in the evaluation window, this script:
1. trains preprocessing and the model only on fights before that event date
2. predicts fights on that event date
3. scores predictions and optionally simulates the existing Kelly-style bankroll

The default date window is the past 365 days ending today.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import LabelEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.feature_sanitization import sanitize_age_features
from utils.name_matching import canonical_name as normalize_name


ID_COLUMNS = {"Red Fighter", "Blue Fighter", "Title", "Date"}
TARGET_COLUMN = "Result"
DEFAULT_FIGHT_DETAILS_SOURCE = os.path.join("data", "fight_details_date.csv")
DEFAULT_EXCLUDED_TITLE_PATTERNS = ("Women",)

DEFAULT_PARAMS = {
    "objective": "binary",
    "n_estimators": 300,
    "learning_rate": 0.04,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.85,
    "subsample_freq": 1,
    "colsample_bytree": 0.85,
    "random_state": 42,
    "verbosity": -1,
    "n_jobs": -1,
}

def parse_date(value):
    return pd.to_datetime(value, format="mixed", errors="coerce")


def default_dates():
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    return start_date.isoformat(), end_date.isoformat()


def normalize_result(value):
    normalized = str(value).strip().lower()
    if normalized in {"win", "w"}:
        return "win"
    if normalized in {"loss", "lose", "l"}:
        return "loss"
    return None


def is_non_binary_outcome(value):
    normalized = str(value).strip().lower()
    return normalized in {
        "draw",
        "draw/no contest",
        "draw / no contest",
        "no contest",
        "nc",
        "overturned",
    }


def load_feature_data(path, min_date, excluded_dob_names=None):
    df = pd.read_csv(path)
    df["Date"] = parse_date(df["Date"])
    df[TARGET_COLUMN] = df[TARGET_COLUMN].map(normalize_result)
    df = df.dropna(subset=["Date", TARGET_COLUMN, "Red Fighter", "Blue Fighter"])
    df = df[df["Date"] >= pd.Timestamp(min_date)]
    df = sanitize_age_features(df, excluded_dob_names=excluded_dob_names)
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def fight_pair_key(left_name, right_name):
    return frozenset({normalize_name(left_name), normalize_name(right_name)})


def build_excluded_fight_index(path, title_patterns):
    if not path or not title_patterns:
        return set(), defaultdict(set), set()

    source_path = Path(path)
    if not source_path.exists():
        return set(), defaultdict(set), set()

    df = pd.read_csv(source_path)
    required_columns = {"Date", "Title", "Red Fighter", "Blue Fighter"}
    if not required_columns.issubset(df.columns):
        return set(), defaultdict(set), set()

    excluded_mask = pd.Series(False, index=df.index)
    titles = df["Title"].fillna("")
    for pattern in title_patterns:
        excluded_mask |= titles.str.contains(pattern, case=False, na=False)

    df = df[excluded_mask].copy()
    df["Date"] = parse_date(df["Date"])
    df = df.dropna(subset=["Date", "Red Fighter", "Blue Fighter"])

    excluded_keys = set()
    dates_by_pair = defaultdict(set)
    fighter_keys = set()
    for _, row in df.iterrows():
        event_date = row["Date"].date()
        pair_key = fight_pair_key(row["Red Fighter"], row["Blue Fighter"])
        excluded_keys.add((event_date, pair_key))
        dates_by_pair[pair_key].add(event_date)
        fighter_keys.add(normalize_name(row["Red Fighter"]))
        fighter_keys.add(normalize_name(row["Blue Fighter"]))

    return excluded_keys, dates_by_pair, fighter_keys


def repair_odds_dates_from_features(odds_df, features_df):
    feature_dates_by_pair = {}
    exact_feature_keys = set()

    for _, row in features_df.dropna(subset=["Date", "Red Fighter", "Blue Fighter"]).iterrows():
        event_date = row["Date"].date()
        pair_key = fight_pair_key(row["Red Fighter"], row["Blue Fighter"])
        exact_feature_keys.add((event_date, pair_key))
        feature_dates_by_pair.setdefault(pair_key, set()).add(event_date)

    repaired = odds_df.copy()
    repairs = []
    for index, row in repaired.iterrows():
        if pd.isna(row["event_date"]):
            continue

        current_date = row["event_date"].date()
        pair_key = fight_pair_key(row["fighter1_name"], row["fighter2_name"])
        if (current_date, pair_key) in exact_feature_keys:
            continue

        candidate_dates = sorted(feature_dates_by_pair.get(pair_key, set()))
        if not candidate_dates:
            continue

        same_month_day = [
            candidate
            for candidate in candidate_dates
            if candidate != current_date
            and (candidate.month, candidate.day) == (current_date.month, current_date.day)
            and 300 <= abs((candidate - current_date).days) <= 400
        ]
        nearby_dates = [
            candidate
            for candidate in candidate_dates
            if candidate != current_date and abs((candidate - current_date).days) <= 1
        ]

        repaired_date = None
        repair_reason = ""
        if len(same_month_day) == 1:
            repaired_date = same_month_day[0]
            repair_reason = "same month/day year correction"
        elif len(nearby_dates) == 1:
            repaired_date = nearby_dates[0]
            repair_reason = "nearby feature date correction"

        if repaired_date is None:
            continue

        repaired.at[index, "event_date"] = pd.Timestamp(repaired_date)
        repairs.append(
            {
                "event_name": row["event_name"],
                "fighter1_name": row["fighter1_name"],
                "fighter2_name": row["fighter2_name"],
                "old_event_date": current_date.isoformat(),
                "new_event_date": repaired_date.isoformat(),
                "reason": repair_reason,
            }
        )

    return repaired, repairs


def is_excluded_universe_row(
    row,
    excluded_fight_keys,
    excluded_dates_by_pair,
    excluded_fighter_keys,
):
    if pd.isna(row["event_date"]):
        return False

    current_date = row["event_date"].date()
    fighter1_key = normalize_name(row["fighter1_name"])
    fighter2_key = normalize_name(row["fighter2_name"])
    if fighter1_key in excluded_fighter_keys and fighter2_key in excluded_fighter_keys:
        return True

    if not excluded_fight_keys:
        return False

    pair_key = frozenset({fighter1_key, fighter2_key})
    if (current_date, pair_key) in excluded_fight_keys:
        return True

    candidate_dates = excluded_dates_by_pair.get(pair_key, set())
    for candidate in candidate_dates:
        days_apart = abs((candidate - current_date).days)
        if days_apart <= 1:
            return True
        if (
            (candidate.month, candidate.day) == (current_date.month, current_date.day)
            and 300 <= days_apart <= 400
        ):
            return True

    return False


def filter_excluded_universe_rows(
    odds_df,
    excluded_fight_keys,
    excluded_dates_by_pair,
    excluded_fighter_keys,
):
    if not excluded_fight_keys and not excluded_fighter_keys:
        return odds_df, 0

    excluded_mask = odds_df.apply(
        lambda row: is_excluded_universe_row(
            row,
            excluded_fight_keys,
            excluded_dates_by_pair,
            excluded_fighter_keys,
        ),
        axis=1,
    )
    excluded_rows = int(excluded_mask.sum())
    return odds_df[~excluded_mask].copy(), excluded_rows


def format_american_odds(value):
    value = int(round(float(value)))
    return f"+{value}" if value > 0 else str(value)


def deduplicate_odds_rows(odds_df):
    groups = {}
    order = []
    for _, row in odds_df.iterrows():
        key = (
            row["event_date"].date(),
            tuple(sorted(fight_pair_key(row["fighter1_name"], row["fighter2_name"]))),
        )
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(row)

    deduped_rows = []
    removed_rows = 0
    for key in order:
        rows = groups[key]
        if len(rows) == 1:
            deduped_rows.append(rows[0].to_dict())
            continue

        removed_rows += len(rows) - 1
        first = rows[0].to_dict()
        odds_by_fighter = defaultdict(list)
        display_by_fighter = {}
        winner_counts = Counter()

        for row in rows:
            fighter1_key = normalize_name(row["fighter1_name"])
            fighter2_key = normalize_name(row["fighter2_name"])
            display_by_fighter.setdefault(fighter1_key, row["fighter1_name"])
            display_by_fighter.setdefault(fighter2_key, row["fighter2_name"])

            fighter1_odds = parse_odds(row["fighter1_odds"])
            fighter2_odds = parse_odds(row["fighter2_odds"])
            if fighter1_odds is not None:
                odds_by_fighter[fighter1_key].append(fighter1_odds)
            if fighter2_odds is not None:
                odds_by_fighter[fighter2_key].append(fighter2_odds)

            winner_key = normalize_name(row["winner_name"])
            if winner_key:
                winner_counts[winner_key] += 1
                display_by_fighter.setdefault(winner_key, row["winner_name"])

        fighter1_key = normalize_name(first["fighter1_name"])
        fighter2_key = normalize_name(first["fighter2_name"])
        if odds_by_fighter[fighter1_key]:
            first["fighter1_odds"] = format_american_odds(np.median(odds_by_fighter[fighter1_key]))
        if odds_by_fighter[fighter2_key]:
            first["fighter2_odds"] = format_american_odds(np.median(odds_by_fighter[fighter2_key]))
        if winner_counts:
            winner_key = winner_counts.most_common(1)[0][0]
            first["winner_name"] = display_by_fighter.get(winner_key, first["winner_name"])

        deduped_rows.append(first)

    return pd.DataFrame(deduped_rows, columns=odds_df.columns), removed_rows


def load_odds_data(
    path,
    start_date,
    end_date,
    features_df=None,
    return_repairs=False,
    excluded_fight_keys=None,
    excluded_dates_by_pair=None,
    excluded_fighter_keys=None,
):
    df = pd.read_csv(path)
    df["event_date"] = parse_date(df["event_date"])
    df = df.dropna(subset=["event_date", "fighter1_name", "fighter2_name", "winner_name"])
    repairs = []
    if features_df is not None:
        df, repairs = repair_odds_dates_from_features(df, features_df)
    df = df[(df["event_date"] >= pd.Timestamp(start_date)) & (df["event_date"] <= pd.Timestamp(end_date))]
    df, excluded_universe_rows = filter_excluded_universe_rows(
        df,
        excluded_fight_keys or set(),
        excluded_dates_by_pair or defaultdict(set),
        excluded_fighter_keys or set(),
    )
    non_binary_rows = int(df["winner_name"].map(is_non_binary_outcome).sum())
    df = df[~df["winner_name"].map(is_non_binary_outcome)].copy()
    df, deduplicated_rows = deduplicate_odds_rows(df)
    df = df.sort_values(["event_date", "event_name"]).reset_index(drop=True)
    df.attrs["deduplicated_rows"] = deduplicated_rows
    df.attrs["non_binary_rows"] = non_binary_rows
    df.attrs["excluded_universe_rows"] = excluded_universe_rows
    if return_repairs:
        repairs_in_window = [
            repair
            for repair in repairs
            if pd.Timestamp(start_date) <= pd.Timestamp(repair["new_event_date"]) <= pd.Timestamp(end_date)
        ]
        return df, repairs_in_window
    return df


def load_model_params(path):
    if not path:
        return DEFAULT_PARAMS.copy(), "built-in-defaults"

    with open(path, "r") as file:
        loaded = json.load(file)

    params = loaded.get("best_params", loaded)
    params = {**params}
    params.setdefault("random_state", 42)
    params.setdefault("verbosity", -1)
    params.setdefault("n_jobs", -1)
    return params, path


def base_feature_columns(df):
    return [
        column
        for column in df.columns
        if column not in ID_COLUMNS and column != TARGET_COLUMN
    ]


def numeric_frame(df, columns):
    return df[columns].apply(pd.to_numeric, errors="coerce")


def swap_column_name(column):
    return column.replace("Red", "__SIDE__").replace("Blue", "Red").replace("__SIDE__", "Blue")


def close_side_feature_pairs(feature_columns, usable_columns):
    usable_set = set(usable_columns)
    selected = list(feature_columns)
    selected_set = set(selected)
    restored_columns = []

    for column in list(selected):
        if "oppdiff" in column:
            continue

        counterpart = swap_column_name(column)
        if counterpart == column:
            continue
        if counterpart not in usable_set or counterpart in selected_set:
            continue

        selected.append(counterpart)
        selected_set.add(counterpart)
        restored_columns.append(counterpart)

    return selected, restored_columns


def select_columns_from_training(train_df, correlation_threshold):
    selected_columns = base_feature_columns(train_df)
    train_x = numeric_frame(train_df, selected_columns)
    usable_columns = [
        column
        for column in selected_columns
        if not train_x[column].isna().all()
    ]

    if not usable_columns:
        return [], []

    train_x = train_x[usable_columns]
    corr_matrix = train_x.corr().abs()
    upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [
        column
        for column in upper_tri.columns
        if any(upper_tri[column] > correlation_threshold)
    ]
    feature_columns = [column for column in usable_columns if column not in to_drop]
    feature_columns, restored_columns = close_side_feature_pairs(feature_columns, usable_columns)
    if restored_columns:
        to_drop = [column for column in to_drop if column not in restored_columns]
    return feature_columns, to_drop


def swap_feature_frame(frame, feature_columns):
    data = {}
    for column in feature_columns:
        if "oppdiff" in column and column in frame.columns:
            data[column] = -pd.to_numeric(frame[column], errors="coerce")
        else:
            source_column = swap_column_name(column)
            if source_column != column:
                if source_column in frame.columns:
                    data[column] = frame[source_column]
                else:
                    data[column] = np.nan
            elif column in frame.columns:
                data[column] = frame[column]
            else:
                data[column] = np.nan

    aligned = pd.DataFrame(data, index=frame.index)
    for column in feature_columns:
        if column not in aligned.columns:
            aligned[column] = np.nan

    return aligned[feature_columns]


def fit_label_encoder():
    label_encoder = LabelEncoder()
    label_encoder.fit(["loss", "win"])
    return label_encoder


def fit_model(train_df, feature_columns, params):
    try:
        import lightgbm as lgb
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "LightGBM could not load. On macOS this usually means libomp is "
            "missing; install it with `brew install libomp`, then rerun."
        ) from exc

    label_encoder = fit_label_encoder()
    x_train = numeric_frame(train_df, feature_columns)
    y_train = pd.Series(label_encoder.transform(train_df[TARGET_COLUMN]), index=train_df.index)

    x_train_swapped = swap_feature_frame(x_train, feature_columns)
    y_train_swapped = 1 - y_train

    x_train_extended = pd.concat([x_train, x_train_swapped], ignore_index=True)
    y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)

    model = lgb.LGBMClassifier(**params)
    model.fit(x_train_extended, y_train_extended)
    return model, label_encoder


def red_win_probability(model, frame):
    class_positions = {klass: index for index, klass in enumerate(model.classes_)}
    win_position = class_positions[1]
    probabilities = model.predict_proba(frame)
    return float(probabilities[0][win_position])


def probability_for_order(model, fight_row, feature_columns, fighter1_name, fighter2_name):
    row_red = normalize_name(fight_row["Red Fighter"])
    row_blue = normalize_name(fight_row["Blue Fighter"])
    fighter1 = normalize_name(fighter1_name)
    fighter2 = normalize_name(fighter2_name)

    base = numeric_frame(pd.DataFrame([fight_row]), feature_columns)

    if row_red == fighter1 and row_blue == fighter2:
        fighter1_frame = base
    elif row_red == fighter2 and row_blue == fighter1:
        fighter1_frame = swap_feature_frame(base, feature_columns)
    else:
        raise ValueError("Fight row does not match requested fighter order")

    fighter2_frame = swap_feature_frame(fighter1_frame, feature_columns)
    p_fighter1_direct = red_win_probability(model, fighter1_frame)
    p_fighter2_direct = red_win_probability(model, fighter2_frame)
    p_fighter1 = (p_fighter1_direct + (1 - p_fighter2_direct)) / 2
    return max(0.0, min(1.0, p_fighter1))


def build_feature_index(features_df, start_date, end_date):
    window = features_df[
        (features_df["Date"] >= pd.Timestamp(start_date))
        & (features_df["Date"] <= pd.Timestamp(end_date))
    ]

    indexed = {}
    duplicate_keys = set()
    duplicates = 0
    for index, row in window.iterrows():
        key = (
            row["Date"].date(),
            frozenset({normalize_name(row["Red Fighter"]), normalize_name(row["Blue Fighter"])}),
        )
        if key in indexed:
            duplicates += 1
            duplicate_keys.add(key)
            continue
        indexed[key] = index

    return indexed, duplicate_keys, duplicates


def build_odds_index(odds_df):
    indexed = {}
    duplicate_keys = set()
    for _, row in odds_df.iterrows():
        key = (
            row["event_date"].date(),
            frozenset({normalize_name(row["fighter1_name"]), normalize_name(row["fighter2_name"])}),
        )
        if key in indexed:
            duplicate_keys.add(key)
            continue
        indexed[key] = row
    return indexed, duplicate_keys


def parse_odds(value):
    cleaned = str(value).strip().replace("−", "-")
    if cleaned in {"", "-", "nan", "None"}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def odds_to_prob(odds):
    if odds >= 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def kelly_criterion(odds, prob_win):
    if odds < 0:
        net_odds = 100 / -odds
    else:
        net_odds = odds / 100
    return (net_odds * prob_win - (1 - prob_win)) / net_odds


def payout(odds, bet):
    if odds < 0:
        return bet * (100 / -odds)
    return bet * (odds / 100)


def choose_bet(
    bankroll,
    fighter1,
    fighter2,
    odds1,
    odds2,
    p1,
    strategy,
    min_edge=None,
    min_kelly=None,
    max_underdog_odds=None,
    positive_floor_fraction=None,
    negative_flat_fraction=None,
):
    p2 = 1 - p1
    if p1 >= p2:
        fighter, odds, probability = fighter1, odds1, p1
    else:
        fighter, odds, probability = fighter2, odds2, p2

    fraction, max_fraction, flat = strategy
    if positive_floor_fraction is None:
        positive_floor_fraction = flat
    if negative_flat_fraction is None:
        negative_flat_fraction = flat
    market_probability = odds_to_prob(odds)
    edge = probability - market_probability
    kelly = kelly_criterion(odds, probability)

    if min_edge is not None and edge < min_edge:
        return (
            fighter,
            odds,
            probability,
            market_probability,
            edge,
            kelly,
            0.0,
            f"edge below {min_edge:.3f}",
        )
    if min_kelly is not None and kelly < min_kelly:
        return (
            fighter,
            odds,
            probability,
            market_probability,
            edge,
            kelly,
            0.0,
            f"kelly below {min_kelly:.3f}",
        )
    if max_underdog_odds is not None and odds > max_underdog_odds:
        return (
            fighter,
            odds,
            probability,
            market_probability,
            edge,
            kelly,
            0.0,
            f"underdog odds above +{int(max_underdog_odds)}",
        )

    if kelly > 0:
        bet = bankroll * fraction * kelly
        bet = min(bet, max_fraction * bankroll)
        bet = max(bet, bankroll * positive_floor_fraction)
    elif negative_flat_fraction > 0 and kelly > -0.5:
        bet = bankroll * negative_flat_fraction
    else:
        bet = 0.0
        return (
            fighter,
            odds,
            probability,
            market_probability,
            edge,
            kelly,
            bet,
            "non-positive kelly",
        )

    return fighter, odds, probability, market_probability, edge, kelly, bet, ""


def score_bet(bankroll, bet, odds, bet_on, winner_name):
    if bet <= 0:
        return bankroll, 0.0
    if normalize_name(winner_name) == normalize_name(bet_on):
        profit = payout(odds, bet)
    else:
        profit = -bet
    return bankroll + profit, profit


def strict_coverage_check(features_df, odds_df, end_date):
    messages = []
    if features_df.empty:
        messages.append("feature data is empty")
    elif features_df["Date"].max() < pd.Timestamp(end_date):
        messages.append(
            f"feature data ends at {features_df['Date'].max().date()}, before requested end {end_date}"
        )

    if odds_df.empty:
        messages.append("odds data has no fights in the requested window")
    elif odds_df["event_date"].max() < pd.Timestamp(end_date):
        messages.append(
            f"odds data ends at {odds_df['event_date'].max().date()}, before requested end {end_date}"
        )

    return messages


def run_backtest(args):
    params, param_source = load_model_params(args.params)
    excluded_dob_names = set() if args.include_excluded_dobs else None
    features_df = load_feature_data(
        args.features,
        args.min_training_date,
        excluded_dob_names=excluded_dob_names,
    )
    excluded_title_patterns = [] if args.include_womens_fights else list(DEFAULT_EXCLUDED_TITLE_PATTERNS)
    excluded_fight_keys, excluded_dates_by_pair, excluded_fighter_keys = build_excluded_fight_index(
        args.fight_details_source,
        excluded_title_patterns,
    )
    odds_df, odds_date_repairs = load_odds_data(
        args.odds,
        args.start_date,
        args.end_date,
        features_df=features_df,
        return_repairs=True,
        excluded_fight_keys=excluded_fight_keys,
        excluded_dates_by_pair=excluded_dates_by_pair,
        excluded_fighter_keys=excluded_fighter_keys,
    )
    odds_rows_deduplicated = odds_df.attrs.get("deduplicated_rows", 0)
    odds_rows_non_binary = odds_df.attrs.get("non_binary_rows", 0)
    odds_rows_excluded_universe = odds_df.attrs.get("excluded_universe_rows", 0)

    coverage_messages = strict_coverage_check(features_df, odds_df, args.end_date)
    if args.strict_end_date and coverage_messages:
        raise SystemExit("Strict end-date check failed: " + "; ".join(coverage_messages))

    feature_index, duplicate_feature_keys, duplicate_feature_count = build_feature_index(
        features_df, args.start_date, args.end_date
    )
    odds_index, duplicate_odds_keys = build_odds_index(odds_df)
    eval_df = features_df[
        (features_df["Date"] >= pd.Timestamp(args.start_date))
        & (features_df["Date"] <= pd.Timestamp(args.end_date))
    ]

    bankroll = args.starting_bankroll
    predictions = []
    skipped = []
    odds_rows_missing_features = []
    odds_rows_duplicate_features = []
    y_true = []
    y_prob = []
    y_pred = []
    models_fit = 0
    fights_with_odds = 0
    bettable_fights = 0

    for _, odds_row in odds_df.iterrows():
        key = (
            odds_row["event_date"].date(),
            frozenset({
                normalize_name(odds_row["fighter1_name"]),
                normalize_name(odds_row["fighter2_name"]),
            }),
        )
        if key in duplicate_feature_keys:
            odds_rows_duplicate_features.append(odds_row)
            skipped.append((odds_row, "ambiguous duplicate feature rows for odds fight"))
        elif key not in feature_index:
            odds_rows_missing_features.append(odds_row)
            skipped.append((odds_row, "missing feature row for odds fight"))
    odds_rows_with_features = (
        len(odds_df) - len(odds_rows_missing_features) - len(odds_rows_duplicate_features)
    )

    for event_date, event_fights in eval_df.groupby(eval_df["Date"].dt.date, sort=True):
        train_df = features_df[features_df["Date"] < pd.Timestamp(event_date)]
        if len(train_df) < args.min_training_fights:
            for _, row in event_fights.iterrows():
                skipped.append((row, f"only {len(train_df)} training fights before event"))
            continue

        if train_df[TARGET_COLUMN].nunique() < 2:
            for _, row in event_fights.iterrows():
                skipped.append((row, "training labels contain fewer than two classes"))
            continue

        feature_columns, dropped_columns = select_columns_from_training(
            train_df, args.correlation_threshold
        )
        if not feature_columns:
            for _, row in event_fights.iterrows():
                skipped.append((row, "no usable numeric feature columns"))
            continue

        model, _ = fit_model(train_df, feature_columns, params)
        models_fit += 1
        max_training_date = train_df["Date"].max().date().isoformat()

        for _, row in event_fights.iterrows():
            red_fighter = row["Red Fighter"]
            blue_fighter = row["Blue Fighter"]
            key = (
                event_date,
                frozenset({normalize_name(red_fighter), normalize_name(blue_fighter)}),
            )
            if key in duplicate_feature_keys:
                skipped.append((row, "ambiguous duplicate feature rows for event date and fighters"))
                continue

            p_red = probability_for_order(model, row, feature_columns, red_fighter, blue_fighter)
            p_blue = 1 - p_red

            predicted_winner = red_fighter if p_red >= p_blue else blue_fighter
            red_won = row[TARGET_COLUMN] == "win"
            winner_name = red_fighter if red_won else blue_fighter
            predicted_red = normalize_name(predicted_winner) == normalize_name(red_fighter)
            correct = red_won == predicted_red

            odds_row = odds_index.get(key)
            no_bet_reason = ""
            odds1 = odds2 = None
            fighter1 = fighter2 = ""
            p_fighter1 = None
            bet_candidate = ""
            bet_market_probability = ""
            bet_edge = ""
            bet_on = ""
            bet_probability = ""
            kelly = 0.0
            bet = 0.0
            profit = 0.0

            if odds_row is None:
                no_bet_reason = "missing odds row"
            elif key in duplicate_odds_keys:
                no_bet_reason = "ambiguous duplicate odds rows"
            else:
                fights_with_odds += 1
                fighter1 = odds_row["fighter1_name"]
                fighter2 = odds_row["fighter2_name"]
                odds1 = parse_odds(odds_row["fighter1_odds"])
                odds2 = parse_odds(odds_row["fighter2_odds"])
                if odds1 is None or odds2 is None:
                    no_bet_reason = "missing odds"
                else:
                    p_fighter1 = probability_for_order(model, row, feature_columns, fighter1, fighter2)
                    (
                        bet_candidate,
                        bet_odds,
                        bet_probability,
                        bet_market_probability,
                        bet_edge,
                        kelly,
                        bet,
                        bet_filter_reason,
                    ) = choose_bet(
                        bankroll,
                        fighter1,
                        fighter2,
                        odds1,
                        odds2,
                        p_fighter1,
                        args.strategy,
                        min_edge=args.min_edge,
                        min_kelly=args.min_kelly,
                        max_underdog_odds=args.max_underdog_odds,
                        positive_floor_fraction=args.positive_floor_fraction,
                        negative_flat_fraction=args.negative_flat_fraction,
                    )
                    bet_on = bet_candidate if bet > 0 else ""
                    if bet_filter_reason and bet <= 0:
                        no_bet_reason = bet_filter_reason
                    bankroll, profit = score_bet(bankroll, bet, bet_odds, bet_candidate, winner_name)
                    bettable_fights += 1

            y_true.append(1 if red_won else 0)
            y_prob.append(p_red)
            y_pred.append(1 if predicted_red else 0)

            predictions.append(
                {
                    "event_date": event_date.isoformat(),
                    "title": row["Title"],
                    "red_fighter": red_fighter,
                    "blue_fighter": blue_fighter,
                    "winner_name": winner_name,
                    "red_win_probability": p_red,
                    "blue_win_probability": p_blue,
                    "predicted_winner": predicted_winner,
                    "correct": correct,
                    "odds_fighter1_name": fighter1,
                    "odds_fighter2_name": fighter2,
                    "fighter1_odds": odds1,
                    "fighter2_odds": odds2,
                    "fighter1_win_probability": p_fighter1 if p_fighter1 is not None else "",
                    "fighter2_win_probability": (1 - p_fighter1) if p_fighter1 is not None else "",
                    "bet_candidate": bet_candidate,
                    "bet_on": bet_on if bet > 0 else "",
                    "bet_probability": bet_probability if bet > 0 else "",
                    "market_probability": bet_market_probability,
                    "bet_edge": bet_edge,
                    "no_bet_reason": no_bet_reason,
                    "kelly": kelly,
                    "bet": bet,
                    "profit": profit,
                    "bankroll_after": bankroll,
                    "training_fights": len(train_df),
                    "max_training_date": max_training_date,
                    "feature_columns": len(feature_columns),
                    "dropped_correlated_columns": len(dropped_columns),
                }
            )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions_path = output_dir / "no_leakage_backtest.csv"
    summary_path = output_dir / "no_leakage_backtest_summary.json"

    predictions_df = pd.DataFrame(predictions)
    predictions_df.to_csv(predictions_path, index=False)

    accuracy = accuracy_score(y_true, y_pred) if y_true else None
    loss = log_loss(y_true, y_prob, labels=[0, 1]) if y_true else None
    final_profit_pct = ((bankroll - args.starting_bankroll) / args.starting_bankroll) * 100

    skipped_rows = [
        {
            "event_date": row["event_date"].date().isoformat(),
            "event_name": row["event_name"],
            "fighter1_name": row["fighter1_name"],
            "fighter2_name": row["fighter2_name"],
            "reason": reason,
        }
        if "event_date" in row.index
        else {
            "event_date": row["Date"].date().isoformat(),
            "event_name": row["Title"],
            "fighter1_name": row["Red Fighter"],
            "fighter2_name": row["Blue Fighter"],
            "reason": reason,
        }
        for row, reason in skipped
    ]

    summary = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "min_training_date": args.min_training_date,
        "features_path": args.features,
        "odds_path": args.odds,
        "fight_details_source": args.fight_details_source,
        "excluded_title_patterns": excluded_title_patterns,
        "included_excluded_dobs": args.include_excluded_dobs,
        "param_source": param_source,
        "strict_coverage_messages": coverage_messages,
        "feature_data_max_date": None if features_df.empty else features_df["Date"].max().date().isoformat(),
        "odds_data_max_date": None if odds_df.empty else odds_df["event_date"].max().date().isoformat(),
        "odds_rows_date_repaired": len(odds_date_repairs),
        "odds_rows_excluded_universe": odds_rows_excluded_universe,
        "odds_rows_deduplicated": odds_rows_deduplicated,
        "odds_rows_non_binary_excluded": odds_rows_non_binary,
        "models_fit": models_fit,
        "predicted_fights": len(predictions),
        "skipped_fights": len(skipped_rows),
        "feature_rows_in_window": len(eval_df),
        "odds_rows_in_window": len(odds_df),
        "odds_rows_with_features": odds_rows_with_features,
        "odds_rows_missing_features": len(odds_rows_missing_features),
        "odds_rows_duplicate_features": len(odds_rows_duplicate_features),
        "odds_feature_coverage": (odds_rows_with_features / len(odds_df)) if len(odds_df) else None,
        "duplicate_feature_keys": duplicate_feature_count,
        "duplicate_odds_keys": len(duplicate_odds_keys),
        "fights_with_odds": fights_with_odds,
        "bettable_fights": bettable_fights,
        "accuracy": accuracy,
        "log_loss": loss,
        "starting_bankroll": args.starting_bankroll,
        "final_bankroll": bankroll,
        "profit_pct": final_profit_pct,
        "strategy": args.strategy,
        "min_edge": args.min_edge,
        "min_kelly": args.min_kelly,
        "max_underdog_odds": args.max_underdog_odds,
        "positive_floor_fraction": args.positive_floor_fraction,
        "negative_flat_fraction": args.negative_flat_fraction,
        "outputs": {
            "predictions_csv": str(predictions_path),
            "summary_json": str(summary_path),
        },
        "skipped": skipped_rows[:100],
        "odds_date_repairs": odds_date_repairs[:100],
    }

    with open(summary_path, "w") as file:
        json.dump(summary, file, indent=2)

    print("No-leakage rolling backtest complete")
    print(f"Window: {args.start_date} to {args.end_date}")
    if coverage_messages:
        print("Coverage warnings:")
        for message in coverage_messages:
            print(f"  - {message}")
    print(f"Models fit: {models_fit}")
    print(f"Predicted fights: {len(predictions)}")
    print(f"Skipped fights: {len(skipped_rows)}")
    print(f"Odds rows in window: {len(odds_df)}")
    print(f"Odds rows date-repaired: {len(odds_date_repairs)}")
    print(f"Odds rows excluded by universe: {odds_rows_excluded_universe}")
    print(f"Odds rows deduplicated: {odds_rows_deduplicated}")
    print(f"Odds rows non-binary excluded: {odds_rows_non_binary}")
    print(f"Odds rows missing feature rows: {len(odds_rows_missing_features)}")
    if accuracy is not None:
        print(f"Accuracy: {accuracy:.4f}")
        print(f"Log loss: {loss:.4f}")
    print(f"Final bankroll: ${bankroll:.2f} ({final_profit_pct:+.2f}%)")
    print(f"Predictions: {predictions_path}")
    print(f"Summary: {summary_path}")

    return summary


def parse_strategy(value):
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("strategy must be fraction,max_fraction,flat")
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("strategy values must be numbers") from exc


def parse_args():
    start_default, end_default = default_dates()

    parser = argparse.ArgumentParser(description="Run a leakage-safe rolling UFC backtest")
    parser.add_argument("--start-date", default=start_default, help="inclusive YYYY-MM-DD start date")
    parser.add_argument("--end-date", default=end_default, help="inclusive YYYY-MM-DD end date")
    parser.add_argument("--features", default=os.path.join("data", "detailed_fights.csv"))
    parser.add_argument("--odds", default=os.path.join("data", "fight_results_with_odds.csv"))
    parser.add_argument("--fight-details-source", default=DEFAULT_FIGHT_DETAILS_SOURCE)
    parser.add_argument(
        "--include-womens-fights",
        action="store_true",
        help="include women's bouts in odds coverage/PnL instead of treating them as out of universe",
    )
    parser.add_argument(
        "--include-excluded-dobs",
        action="store_true",
        help="keep DOB/age features for fighters listed in data/excluded_fighter_dobs.csv",
    )
    parser.add_argument("--params", default=None, help="optional LightGBM params JSON")
    parser.add_argument("--output-dir", default="test_results")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--min-training-fights", type=int, default=200)
    parser.add_argument("--correlation-threshold", type=float, default=0.95)
    parser.add_argument("--starting-bankroll", type=float, default=1000.0)
    parser.add_argument("--strategy", type=parse_strategy, default=[0.05, 0.05, 0.005])
    parser.add_argument(
        "--min-edge",
        type=float,
        default=None,
        help="optional minimum model probability edge over implied market probability",
    )
    parser.add_argument(
        "--min-kelly",
        type=float,
        default=None,
        help="optional minimum Kelly value required before placing a bet",
    )
    parser.add_argument(
        "--max-underdog-odds",
        type=float,
        default=None,
        help="optional maximum positive American odds allowed for underdog bets",
    )
    parser.add_argument(
        "--positive-floor-fraction",
        type=float,
        default=None,
        help="minimum bankroll fraction for positive-Kelly bets; defaults to strategy flat value",
    )
    parser.add_argument(
        "--negative-flat-fraction",
        type=float,
        default=None,
        help="bankroll fraction for negative-Kelly fallback bets; defaults to strategy flat value",
    )
    parser.add_argument(
        "--strict-end-date",
        action="store_true",
        help="fail if feature or odds data does not reach --end-date",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_backtest(parse_args())
