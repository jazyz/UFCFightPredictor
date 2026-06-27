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
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import LabelEncoder


ID_COLUMNS = {"Red Fighter", "Blue Fighter", "Title", "Date"}
TARGET_COLUMN = "Result"

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

NAME_ALIASES = {
    "king green": "bobby green",
    "asu almabayev": "asu almabaev",
    "carlos leal": "carlos leal miranda",
    "michael aswell jr": "michael aswell",
    "sean o malley": "sean omalley",
    "shara magomedov": "sharabutdin magomedov",
}


def parse_date(value):
    return pd.to_datetime(value, format="mixed", errors="coerce")


def default_dates():
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    return start_date.isoformat(), end_date.isoformat()


def normalize_name(name):
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_name.strip().lower())
    parts = [
        part
        for part in cleaned.split()
        if part not in {"jr", "sr", "ii", "iii", "iv"}
    ]
    normalized = " ".join(parts)
    return NAME_ALIASES.get(normalized, normalized)


def normalize_result(value):
    normalized = str(value).strip().lower()
    if normalized in {"win", "w"}:
        return "win"
    if normalized in {"loss", "lose", "l"}:
        return "loss"
    return None


def load_feature_data(path, min_date):
    df = pd.read_csv(path)
    df["Date"] = parse_date(df["Date"])
    df[TARGET_COLUMN] = df[TARGET_COLUMN].map(normalize_result)
    df = df.dropna(subset=["Date", TARGET_COLUMN, "Red Fighter", "Blue Fighter"])
    df = df[df["Date"] >= pd.Timestamp(min_date)]
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def load_odds_data(path, start_date, end_date):
    df = pd.read_csv(path)
    df["event_date"] = parse_date(df["event_date"])
    df = df.dropna(subset=["event_date", "fighter1_name", "fighter2_name", "winner_name"])
    df = df[(df["event_date"] >= pd.Timestamp(start_date)) & (df["event_date"] <= pd.Timestamp(end_date))]
    df = df.sort_values(["event_date", "event_name"]).reset_index(drop=True)
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
    return feature_columns, to_drop


def swap_column_name(column):
    return column.replace("Red", "__SIDE__").replace("Blue", "Red").replace("__SIDE__", "Blue")


def swap_feature_frame(frame, feature_columns):
    data = {}
    for column in feature_columns:
        if "oppdiff" in column and column in frame.columns:
            data[column] = -pd.to_numeric(frame[column], errors="coerce")
        else:
            source_column = swap_column_name(column)
            if source_column in frame.columns:
                data[column] = frame[source_column]
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


def choose_bet(bankroll, fighter1, fighter2, odds1, odds2, p1, strategy):
    p2 = 1 - p1
    if p1 >= p2:
        fighter, odds, probability = fighter1, odds1, p1
    else:
        fighter, odds, probability = fighter2, odds2, p2

    fraction, max_fraction, flat = strategy
    kelly = kelly_criterion(odds, probability)
    if kelly > 0:
        bet = bankroll * fraction * kelly
        bet = min(bet, max_fraction * bankroll)
        bet = max(bet, bankroll * flat)
    elif flat > 0 and kelly > -0.5:
        bet = bankroll * flat
    else:
        bet = 0.0

    return fighter, odds, probability, kelly, bet


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
    features_df = load_feature_data(args.features, args.min_training_date)
    odds_df = load_odds_data(args.odds, args.start_date, args.end_date)

    coverage_messages = strict_coverage_check(features_df, odds_df, args.end_date)
    if args.strict_end_date and coverage_messages:
        raise SystemExit("Strict end-date check failed: " + "; ".join(coverage_messages))

    _, duplicate_feature_keys, duplicate_feature_count = build_feature_index(
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
    y_true = []
    y_prob = []
    y_pred = []
    models_fit = 0
    fights_with_odds = 0
    bettable_fights = 0

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
                    bet_on, bet_odds, bet_probability, kelly, bet = choose_bet(
                        bankroll, fighter1, fighter2, odds1, odds2, p_fighter1, args.strategy
                    )
                    bankroll, profit = score_bet(bankroll, bet, bet_odds, bet_on, winner_name)
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
                    "bet_on": bet_on if bet > 0 else "",
                    "bet_probability": bet_probability if bet > 0 else "",
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
        "param_source": param_source,
        "strict_coverage_messages": coverage_messages,
        "feature_data_max_date": None if features_df.empty else features_df["Date"].max().date().isoformat(),
        "odds_data_max_date": None if odds_df.empty else odds_df["event_date"].max().date().isoformat(),
        "models_fit": models_fit,
        "predicted_fights": len(predictions),
        "skipped_fights": len(skipped_rows),
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
        "outputs": {
            "predictions_csv": str(predictions_path),
            "summary_json": str(summary_path),
        },
        "skipped": skipped_rows[:100],
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
    parser.add_argument("--params", default=None, help="optional LightGBM params JSON")
    parser.add_argument("--output-dir", default="test_results")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--min-training-fights", type=int, default=200)
    parser.add_argument("--correlation-threshold", type=float, default=0.95)
    parser.add_argument("--starting-bankroll", type=float, default=1000.0)
    parser.add_argument("--strategy", type=parse_strategy, default=[0.05, 0.05, 0.005])
    parser.add_argument(
        "--strict-end-date",
        action="store_true",
        help="fail if feature or odds data does not reach --end-date",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_backtest(parse_args())
