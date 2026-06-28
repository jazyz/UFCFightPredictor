"""Shared feature engineering for fight-level model inputs."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd


WEIGHT_CLASSES = (
    ("strawweight", "Strawweight", 115.0),
    ("flyweight", "Flyweight", 125.0),
    ("bantamweight", "Bantamweight", 135.0),
    ("featherweight", "Featherweight", 145.0),
    ("lightweight", "Lightweight", 155.0),
    ("welterweight", "Welterweight", 170.0),
    ("middleweight", "Middleweight", 185.0),
    ("light_heavyweight", "Light Heavyweight", 205.0),
    ("heavyweight", "Heavyweight", 265.0),
)

PAIR_AGGREGATE_FEATURES = (
    "age",
    "last_fight",
    "totalfights",
    "elo",
    "oppelo",
    "wins",
    "avg age",
    "winstreak",
    "losestreak",
    "titlewins",
)


def _title_series(df: pd.DataFrame) -> pd.Series:
    if "Title" not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return df["Title"].fillna("").astype(str)


def _weight_class_for_title(title: str) -> str:
    normalized = " ".join(str(title).lower().split())
    for slug, label, _ in WEIGHT_CLASSES:
        pattern = rf"\b{re.escape(label.lower())}\b"
        if re.search(pattern, normalized):
            return slug
    if "catch weight" in normalized:
        return "catch_weight"
    return "unknown"


def add_title_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add fixed, pre-fight context features derived from the bout title."""
    enriched = df.copy()
    titles = _title_series(enriched)
    lowered = titles.str.lower()

    enriched["context_is_title_bout"] = lowered.str.contains(
        "title|championship", regex=True, na=False
    ).astype(int)
    enriched["context_is_interim_title"] = lowered.str.contains(
        "interim", regex=False, na=False
    ).astype(int)
    enriched["context_is_catch_weight"] = lowered.str.contains(
        "catch weight", regex=False, na=False
    ).astype(int)

    weight_classes = titles.map(_weight_class_for_title)
    weight_lookup = {slug: pounds for slug, _, pounds in WEIGHT_CLASSES}
    enriched["context_weight_lbs"] = weight_classes.map(weight_lookup).astype(float)

    for slug, _, _ in WEIGHT_CLASSES:
        enriched[f"context_weight_{slug}"] = (weight_classes == slug).astype(int)
    enriched["context_weight_catch_weight"] = (weight_classes == "catch_weight").astype(int)
    enriched["context_weight_unknown"] = (weight_classes == "unknown").astype(int)

    return enriched


def add_matchup_aggregate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add side-symmetric matchup-shape features from existing Red/Blue columns."""
    enriched = df.copy()

    for feature in PAIR_AGGREGATE_FEATURES:
        red_col = f"Red {feature}"
        blue_col = f"Blue {feature}"
        if red_col not in enriched.columns or blue_col not in enriched.columns:
            continue

        red = pd.to_numeric(enriched[red_col], errors="coerce")
        blue = pd.to_numeric(enriched[blue_col], errors="coerce")
        enriched[f"{feature} absdiff"] = (red - blue).abs()
        enriched[f"{feature} mean"] = pd.concat([red, blue], axis=1).mean(axis=1)

        if feature in {"totalfights", "wins", "titlewins"}:
            enriched[f"log {feature} oppdiff"] = np.log1p(red.clip(lower=0)) - np.log1p(
                blue.clip(lower=0)
            )
            enriched[f"{feature} total"] = red + blue

    return enriched


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all shared fight-level feature engineering."""
    return add_matchup_aggregate_features(add_title_context_features(df))
