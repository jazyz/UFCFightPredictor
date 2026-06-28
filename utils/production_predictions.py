"""Production single-model prediction output helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from utils.feature_engineering import add_engineered_features
from utils.feature_sanitization import sanitize_age_features, validate_feature_ranges


DEFAULT_INPUT_PATH = Path("data/predict_fights_alpha.csv")
DEFAULT_REFERENCE_PATH = Path("data/detailed_fights.csv")
DEFAULT_OUTPUT_DIR = Path("data")
DEFAULT_MODEL_PATH = Path("saved_models/lgbm_single_model.joblib")
DEFAULT_METADATA_PATH = Path("saved_models/lgbm_single_model_metadata.json")
DEFAULT_LABEL_ENCODER_PATH = Path("saved_preprocessing/label_encoder_single.joblib")
DEFAULT_SELECTED_COLUMNS_PATH = Path("saved_preprocessing/selected_columns_single.json")

BETTING_COLUMNS = ["Red Fighter", "Blue Fighter", "Probability Win", "Probability Lose"]


@dataclass(frozen=True)
class PredictionResult:
    predictions: pd.DataFrame
    class_probabilities: dict[str, list[float]]
    metadata: dict


def load_json(path: Path) -> dict | list:
    with path.open() as file:
        return json.load(file)


def load_metadata(path: Path = DEFAULT_METADATA_PATH) -> dict:
    if not path.exists():
        return {}
    metadata = load_json(path)
    if not isinstance(metadata, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return metadata


def resolve_path(value: str | None, fallback: Path) -> Path:
    return Path(value) if value else fallback


def prepare_feature_frame(df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    prepared = sanitize_age_features(df)
    if metadata.get("engineered_features"):
        prepared = add_engineered_features(prepared)
    return prepared


def load_preprocessing_tools(
    label_encoder_path: Path,
    selected_columns_path: Path,
):
    if not label_encoder_path.exists():
        raise FileNotFoundError(f"Missing label encoder artifact: {label_encoder_path}")
    if not selected_columns_path.exists():
        raise FileNotFoundError(f"Missing selected-columns artifact: {selected_columns_path}")

    label_encoder = joblib.load(label_encoder_path)
    selected_columns = load_json(selected_columns_path)
    if not isinstance(selected_columns, list):
        raise ValueError(f"{selected_columns_path} must contain a JSON list")
    return label_encoder, selected_columns


def build_model_frame(feature_frame: pd.DataFrame, selected_columns: list[str]) -> pd.DataFrame:
    missing = [column for column in selected_columns if column not in feature_frame.columns]
    if missing:
        preview = ", ".join(missing[:10])
        suffix = "" if len(missing) <= 10 else f", ... {len(missing) - 10} more"
        raise KeyError(f"Prediction frame is missing selected columns: {preview}{suffix}")

    return feature_frame[selected_columns].drop(["Result", "Date"], axis=1, errors="ignore")


def class_index(label_encoder, label: str) -> int:
    classes = list(label_encoder.classes_)
    if label not in classes:
        raise ValueError(f"Label encoder classes {classes} do not include {label!r}")
    return classes.index(label)


def generate_single_model_predictions(
    input_path: Path | str = DEFAULT_INPUT_PATH,
    reference_path: Path | str = DEFAULT_REFERENCE_PATH,
    model_path: Path | str | None = None,
    metadata_path: Path | str = DEFAULT_METADATA_PATH,
    label_encoder_path: Path | str | None = None,
    selected_columns_path: Path | str | None = None,
) -> PredictionResult:
    metadata = load_metadata(Path(metadata_path))
    model_path = resolve_path(model_path or metadata.get("model_path"), DEFAULT_MODEL_PATH)
    label_encoder_path = resolve_path(
        label_encoder_path or metadata.get("label_encoder_path"),
        DEFAULT_LABEL_ENCODER_PATH,
    )
    selected_columns_path = resolve_path(
        selected_columns_path or metadata.get("selected_columns_path"),
        DEFAULT_SELECTED_COLUMNS_PATH,
    )

    if not model_path.exists():
        raise FileNotFoundError(f"Missing model artifact: {model_path}")

    model = joblib.load(model_path)
    label_encoder, selected_columns = load_preprocessing_tools(
        label_encoder_path,
        selected_columns_path,
    )

    feature_frame = prepare_feature_frame(pd.read_csv(input_path), metadata)
    reference_frame = prepare_feature_frame(pd.read_csv(reference_path), metadata)
    validate_feature_ranges(
        feature_frame,
        reference_frame,
        selected_columns,
        context=str(input_path),
    )

    model_frame = build_model_frame(feature_frame, selected_columns)
    probabilities = model.predict_proba(model_frame)
    predicted_classes = np.argmax(probabilities, axis=1)
    predicted_labels = label_encoder.inverse_transform(predicted_classes)
    win_index = class_index(label_encoder, "win")
    lose_index = class_index(label_encoder, "loss")

    predictions = feature_frame[["Red Fighter", "Blue Fighter"]].copy()
    predictions["Probability Win"] = probabilities[:, win_index]
    predictions["Probability Lose"] = probabilities[:, lose_index]
    predictions["Predicted Result"] = predicted_labels
    predictions["Predicted Winner"] = np.where(
        predicted_labels == "win",
        predictions["Red Fighter"],
        predictions["Blue Fighter"],
    )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output_metadata = {
        "prediction_source": "single_model",
        "generated_at_utc": generated_at,
        "input_path": str(input_path),
        "reference_path": str(reference_path),
        "model_path": str(model_path),
        "label_encoder_path": str(label_encoder_path),
        "selected_columns_path": str(selected_columns_path),
        "model_train_through": metadata.get("train_through"),
        "model_param_source": metadata.get("param_source"),
        "engineered_features": bool(metadata.get("engineered_features")),
        "rows": int(len(predictions)),
    }

    return PredictionResult(
        predictions=predictions,
        class_probabilities={
            "Win": probabilities[:, win_index].tolist(),
            "Lose": probabilities[:, lose_index].tolist(),
        },
        metadata=output_metadata,
    )


def single_model_report_frame(predictions: pd.DataFrame) -> pd.DataFrame:
    report = predictions[["Red Fighter", "Blue Fighter"]].copy()
    report["Red Fighter Win Probability"] = predictions["Probability Win"]
    report["Blue Fighter Win Probability"] = predictions["Probability Lose"]
    report["Predicted Result"] = predictions["Predicted Result"]
    report["Predicted Winner"] = predictions["Predicted Winner"]
    return report


def write_prediction_outputs(
    result: PredictionResult,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    betting_frame = result.predictions[BETTING_COLUMNS]
    paths = {
        "fight_predictions": output_dir / "fight_predictions.csv",
        "betting_predictions": output_dir / "betting_predictions.csv",
        "single_model_predictions": output_dir / "single_model_predictions.csv",
        "predicted_data": output_dir / "predicted_data.json",
        "betting_predictions_metadata": output_dir / "betting_predictions_metadata.json",
    }

    betting_frame.to_csv(paths["fight_predictions"], index=False)
    betting_frame.to_csv(paths["betting_predictions"], index=False)
    single_model_report_frame(result.predictions).to_csv(
        paths["single_model_predictions"],
        index=False,
    )

    predict_data = betting_frame.to_dict(orient="records")
    with paths["predicted_data"].open("w") as file:
        json.dump(
            {
                "predict_data": predict_data,
                "class_probabilities": result.class_probabilities,
                "metadata": result.metadata,
            },
            file,
        )

    with paths["betting_predictions_metadata"].open("w") as file:
        json.dump(result.metadata, file, indent=2)

    return paths
