"""Shared cleanup for model feature tables."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from utils.name_matching import lookup_keys


SIDES = ("Red", "Blue")
AGE_LIKE_FEATURES = ("age", "dob", "avg age")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCLUDED_DOBS_PATH = PROJECT_ROOT / "data" / "excluded_fighter_dobs.csv"


def load_excluded_dob_names(path: Path = DEFAULT_EXCLUDED_DOBS_PATH) -> set[str]:
    if not path.exists():
        return set()

    df = pd.read_csv(path)
    if "fighter_name" not in df.columns:
        raise ValueError(f"{path} is missing required column: fighter_name")

    excluded = set()
    for name in df["fighter_name"].dropna().astype(str):
        excluded.update(lookup_keys(name))
    return excluded


def sanitize_age_features(
    df: pd.DataFrame,
    excluded_dob_names: set[str] | None = None,
) -> pd.DataFrame:
    """Replace impossible age/DOB-derived values with missing values.

    Missing DOBs are represented upstream as zero, which later creates ages
    around 2025. LightGBM can handle NaN; leaving those outliers in distorts
    probabilities and Kelly sizing.

    Some known DOBs are intentionally excluded from model features when they
    make sparse newer-fighter age features less stable in rolling backtests.
    """
    cleaned = df.copy()
    if excluded_dob_names is None:
        excluded_dob_names = load_excluded_dob_names()

    for side in SIDES:
        fighter_col = f"{side} Fighter"
        age_col = f"{side} age"
        dob_col = f"{side} dob"
        avg_age_col = f"{side} avg age"

        invalid_identity = pd.Series(False, index=cleaned.index)
        if fighter_col in cleaned.columns and excluded_dob_names:
            fighter_keys = cleaned[fighter_col].map(
                lambda name: set(lookup_keys(name)) if pd.notna(name) else set()
            )
            invalid_identity |= fighter_keys.map(
                lambda keys: bool(keys & excluded_dob_names)
            )
        if age_col in cleaned.columns:
            age = pd.to_numeric(cleaned[age_col], errors="coerce")
            invalid_identity |= age.notna() & ((age < 12) | (age > 120))
        if dob_col in cleaned.columns:
            dob = pd.to_numeric(cleaned[dob_col], errors="coerce")
            invalid_identity |= dob.notna() & ((dob < 1900) | (dob > 2100))

        for column in (age_col, dob_col, avg_age_col):
            if column in cleaned.columns:
                cleaned.loc[invalid_identity, column] = np.nan

        if avg_age_col in cleaned.columns:
            avg_age = pd.to_numeric(cleaned[avg_age_col], errors="coerce")
            cleaned.loc[
                avg_age.notna() & ((avg_age < 12) | (avg_age > 120)),
                avg_age_col,
            ] = np.nan

    for feature in AGE_LIKE_FEATURES:
        red_col = f"Red {feature}"
        blue_col = f"Blue {feature}"
        oppdiff_col = f"{feature} oppdiff"
        has_oppdiff_columns = (
            red_col in cleaned.columns
            and blue_col in cleaned.columns
            and oppdiff_col in cleaned.columns
        )
        if has_oppdiff_columns:
            cleaned[oppdiff_col] = (
                pd.to_numeric(cleaned[red_col], errors="coerce")
                - pd.to_numeric(cleaned[blue_col], errors="coerce")
            )

    return cleaned
