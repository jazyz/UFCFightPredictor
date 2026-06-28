#!/usr/bin/env python3
"""
Train the production single LightGBM model on all completed fights available
through an as-of date.

This is for the deployable model. For honest evaluation, use
testing/no_leakage_backtest.py, which retrains only on fights before each
evaluated event.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd

from testing.no_leakage_backtest import (
    TARGET_COLUMN,
    fit_model,
    load_feature_data,
    load_model_params,
    parse_date,
    select_columns_from_training,
)


def default_as_of_date():
    return datetime.now().date().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Train the final UFC prediction model")
    parser.add_argument("--features", default=os.path.join("data", "detailed_fights.csv"))
    parser.add_argument("--params", default=None, help="optional LightGBM params JSON")
    parser.add_argument("--min-training-date", default="2009-01-01")
    parser.add_argument("--train-through", default=default_as_of_date(), help="inclusive YYYY-MM-DD as-of date")
    parser.add_argument("--correlation-threshold", type=float, default=0.95)
    parser.add_argument(
        "--engineered-features",
        action="store_true",
        help="add experimental title-context and matchup aggregate features",
    )
    parser.add_argument("--model-dir", default="saved_models")
    parser.add_argument("--preprocessing-dir", default="saved_preprocessing")
    return parser.parse_args()


def main():
    args = parse_args()
    params, param_source = load_model_params(args.params)
    features_df = load_feature_data(
        args.features,
        args.min_training_date,
        engineered_features=args.engineered_features,
    )
    train_through = parse_date(args.train_through)
    if pd.isna(train_through):
        raise SystemExit(f"Could not parse --train-through date: {args.train_through}")
    train_df = features_df[features_df["Date"] <= train_through]

    if train_df.empty:
        raise SystemExit(f"No training rows found through {args.train_through}")

    if train_df[TARGET_COLUMN].nunique() < 2:
        raise SystemExit("Training labels contain fewer than two classes")

    feature_columns, dropped_columns = select_columns_from_training(
        train_df, args.correlation_threshold
    )
    if not feature_columns:
        raise SystemExit("No usable feature columns found")

    model, label_encoder = fit_model(train_df, feature_columns, params)

    model_dir = Path(args.model_dir)
    preprocessing_dir = Path(args.preprocessing_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    preprocessing_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "lgbm_single_model.joblib"
    label_encoder_path = preprocessing_dir / "label_encoder_single.joblib"
    selected_columns_path = preprocessing_dir / "selected_columns_single.json"
    model_feature_columns_path = preprocessing_dir / "model_feature_columns_single.json"
    metadata_path = model_dir / "lgbm_single_model_metadata.json"

    joblib.dump(model, model_path)
    joblib.dump(label_encoder, label_encoder_path)

    selected_columns_for_prediction = [TARGET_COLUMN, *feature_columns, "Date"]
    with open(selected_columns_path, "w") as file:
        json.dump(selected_columns_for_prediction, file, indent=2)

    with open(model_feature_columns_path, "w") as file:
        json.dump(feature_columns, file, indent=2)

    metadata = {
        "features_path": args.features,
        "param_source": param_source,
        "min_training_date": args.min_training_date,
        "train_through": args.train_through,
        "engineered_features": args.engineered_features,
        "max_feature_date_used": train_df["Date"].max().date().isoformat(),
        "training_rows": len(train_df),
        "feature_columns": len(feature_columns),
        "dropped_correlated_columns": len(dropped_columns),
        "model_path": str(model_path),
        "label_encoder_path": str(label_encoder_path),
        "selected_columns_path": str(selected_columns_path),
    }
    with open(metadata_path, "w") as file:
        json.dump(metadata, file, indent=2)

    print("Final model training complete")
    print(f"Training rows: {len(train_df)}")
    print(f"Max feature date used: {metadata['max_feature_date_used']}")
    print(f"Feature columns: {len(feature_columns)}")
    print(f"Model: {model_path}")
    print(f"Preprocessing: {preprocessing_dir}")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
