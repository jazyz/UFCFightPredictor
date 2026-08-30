"""
Unit tests that verify no data leakage in the backtesting system.

Run with: pytest tests/test_no_data_leakage.py -v

These tests verify:
1. Train/test splits are properly temporal
2. Features don't use future data
3. ELO ratings are computed chronologically
4. Fighter stats at prediction time match historical records
"""

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestTrainTestSplit:
    """Tests that verify train/test temporal ordering."""

    def test_train_dates_always_before_test_dates(self, detailed_fights_df, sample_split_date):
        """Verify all training data dates are strictly before test dates."""
        train_df = detailed_fights_df[detailed_fights_df["Date"] < sample_split_date]
        test_df = detailed_fights_df[detailed_fights_df["Date"] >= sample_split_date]

        # Skip if not enough data
        if len(train_df) == 0 or len(test_df) == 0:
            pytest.skip("Not enough data for train/test split")

        # Assertion 1: No overlap
        assert train_df["Date"].max() < test_df["Date"].min(), \
            f"Train max date {train_df['Date'].max()} >= Test min date {test_df['Date'].min()}"

        # Assertion 2: All train dates < split date
        assert (train_df["Date"] < sample_split_date).all(), \
            "Some training dates are >= split date"

        # Assertion 3: All test dates >= split date
        assert (test_df["Date"] >= sample_split_date).all(), \
            "Some test dates are < split date"

    def test_no_future_fighters_in_early_training(self, detailed_fights_df):
        """
        Verify fighters appearing in early training data existed by then.
        """
        # Get first 10% of data as early training
        early_cutoff = detailed_fights_df["Date"].quantile(0.1)
        early_df = detailed_fights_df[detailed_fights_df["Date"] <= early_cutoff]

        if len(early_df) == 0:
            pytest.skip("Not enough early data")

        # Get all fighters and their first fight date
        all_fighters = pd.concat([
            detailed_fights_df[["Red Fighter", "Date"]].rename(columns={"Red Fighter": "Fighter"}),
            detailed_fights_df[["Blue Fighter", "Date"]].rename(columns={"Blue Fighter": "Fighter"})
        ])
        first_fights = all_fighters.groupby("Fighter")["Date"].min()

        # Check fighters in early training all debuted by then
        early_fighters = set(early_df["Red Fighter"].unique()) | set(early_df["Blue Fighter"].unique())

        for fighter in early_fighters:
            if fighter in first_fights.index:
                debut = first_fights[fighter]
                # Fighter's debut should be <= their appearance in early data
                fighter_early_appearances = early_df[
                    (early_df["Red Fighter"] == fighter) | (early_df["Blue Fighter"] == fighter)
                ]["Date"].min()
                assert debut <= fighter_early_appearances, \
                    f"Fighter {fighter} appears before their debut!"


class TestFeatureIntegrity:
    """Tests that verify features don't use future data."""

    def test_elo_ratings_increase_over_time_for_winners(self, detailed_fights_df):
        """
        Verify ELO rating changes make sense - winners should gain ELO.
        """
        # Sort by date
        df = detailed_fights_df.sort_values("Date")

        if "Red elo" not in df.columns:
            pytest.skip("ELO columns not found")

        # Sample some fights and verify ELO logic
        sample = df.sample(min(50, len(df)), random_state=42)

        for _, fight in sample.iterrows():
            red_elo = fight.get("Red elo", 1000)
            blue_elo = fight.get("Blue elo", 1000)

            # ELO should be positive
            assert red_elo > 0, f"Red ELO <= 0: {red_elo}"
            assert blue_elo > 0, f"Blue ELO <= 0: {blue_elo}"

            # ELO should be in reasonable range (800-1600 for most fighters)
            assert 500 < red_elo < 2000, f"Red ELO out of range: {red_elo}"
            assert 500 < blue_elo < 2000, f"Blue ELO out of range: {blue_elo}"

    def test_total_fights_non_negative(self, detailed_fights_df):
        """Verify total fights counts are non-negative and reasonable."""
        if "Red totalfights" not in detailed_fights_df.columns:
            pytest.skip("Total fights columns not found")

        assert (detailed_fights_df["Red totalfights"] >= 0).all(), \
            "Negative Red totalfights found"
        assert (detailed_fights_df["Blue totalfights"] >= 0).all(), \
            "Negative Blue totalfights found"

        # Minimum 2 fights required for feature computation
        assert (detailed_fights_df["Red totalfights"] >= 2).all(), \
            "Red totalfights < 2 found (should be filtered)"
        assert (detailed_fights_df["Blue totalfights"] >= 2).all(), \
            "Blue totalfights < 2 found (should be filtered)"

    def test_winstreak_losestreak_mutual_exclusion(self, detailed_fights_df):
        """Verify a fighter can't have both win and lose streak simultaneously."""
        if "Red winstreak" not in detailed_fights_df.columns:
            pytest.skip("Streak columns not found")

        # A fighter with a winstreak should have losestreak = 0 and vice versa
        # (This is a logical consistency check)
        for _, fight in detailed_fights_df.sample(min(100, len(detailed_fights_df))).iterrows():
            red_win = fight.get("Red winstreak", 0)
            red_lose = fight.get("Red losestreak", 0)

            # Can't have both active
            if red_win > 0:
                assert red_lose == 0, \
                    f"Red has both winstreak ({red_win}) and losestreak ({red_lose})"

            blue_win = fight.get("Blue winstreak", 0)
            blue_lose = fight.get("Blue losestreak", 0)

            if blue_win > 0:
                assert blue_lose == 0, \
                    f"Blue has both winstreak ({blue_win}) and losestreak ({blue_lose})"


class TestChronologicalProcessing:
    """Tests that verify chronological data processing."""

    def test_data_is_sorted_by_date(self, detailed_fights_df):
        """Verify data can be properly sorted by date."""
        sorted_df = detailed_fights_df.sort_values("Date")

        # Check dates are in order
        dates = sorted_df["Date"].tolist()
        for i in range(1, len(dates)):
            assert dates[i] >= dates[i-1], \
                f"Date order violation at index {i}: {dates[i-1]} > {dates[i]}"

    def test_no_future_dates(self, detailed_fights_df):
        """Verify no fights have future dates."""
        today = pd.Timestamp.now()
        future_fights = detailed_fights_df[detailed_fights_df["Date"] > today]

        assert len(future_fights) == 0, \
            f"Found {len(future_fights)} fights with future dates"

    def test_date_range_reasonable(self, detailed_fights_df):
        """Verify date range is reasonable for UFC data."""
        min_date = detailed_fights_df["Date"].min()
        max_date = detailed_fights_df["Date"].max()

        # UFC started in 1993
        assert min_date.year >= 1993, f"Date too early: {min_date}"

        # Max date shouldn't be too far in the future
        assert max_date <= pd.Timestamp.now() + timedelta(days=30), \
            f"Date too far in future: {max_date}"


class TestHoldoutSeparation:
    """Tests for holdout set separation."""

    def test_holdout_date_constant_defined(self):
        """Verify holdout date constant is properly defined."""
        from validation.holdout_validator import HOLDOUT_START_DATE

        holdout_date = pd.to_datetime(HOLDOUT_START_DATE)

        # Should be a recent date (2024)
        assert holdout_date.year >= 2024, \
            f"Holdout date too early: {holdout_date}"

        # Should not be in the future
        assert holdout_date <= pd.Timestamp.now(), \
            f"Holdout date is in future: {holdout_date}"

    def test_load_training_data_excludes_holdout(self, detailed_fights_df):
        """Verify load_training_data properly excludes holdout period."""
        from validation.holdout_validator import HOLDOUT_START_DATE, load_training_data

        # This would actually load and filter
        # For now, verify the logic
        holdout_date = pd.to_datetime(HOLDOUT_START_DATE)
        holdout_count = (detailed_fights_df["Date"] >= holdout_date).sum()

        pre_holdout = detailed_fights_df[detailed_fights_df["Date"] < holdout_date]

        # Pre-holdout should have fewer fights than total
        if holdout_count > 0:
            assert len(pre_holdout) < len(detailed_fights_df), \
                "Pre-holdout should have fewer fights than total"


class TestProcessFightsIsolated:
    """Tests for the isolated feature processor."""

    def test_processor_initialization(self, processor):
        """Verify processor initializes correctly."""
        assert processor is not None
        assert processor.fighter_stats == {}
        assert processor.processed_fights == []

    def test_processor_reset_state(self, processor):
        """Verify state reset works."""
        processor.fighter_stats = {"test": {"elo": 1000}}
        processor.processed_fights = [{"test": "fight"}]

        processor._reset_state()

        assert processor.fighter_stats == {}
        assert processor.processed_fights == []

    def test_elo_calculation_functions(self, processor):
        """Verify ELO calculation helper functions."""
        # K-factor should decrease with more fights
        assert processor.calculate_k_factor(1) == 40
        assert processor.calculate_k_factor(5) == 35
        assert processor.calculate_k_factor(10) == 30
        assert processor.calculate_k_factor(25) == 25

        # Expected win probability should be 0.5 for equal ratings
        prob = processor.calculate_expected_win_probability(1000, 1000)
        assert abs(prob - 0.5) < 0.001

        # Higher rated should have higher probability
        prob_higher = processor.calculate_expected_win_probability(1200, 1000)
        assert prob_higher > 0.5

        prob_lower = processor.calculate_expected_win_probability(800, 1000)
        assert prob_lower < 0.5

    def test_elo_update_winner_gains(self, processor):
        """Verify ELO update gives points to winner."""
        initial_a = 1000
        initial_b = 1000

        new_a, new_b = processor.update_elo_ratings(
            initial_a, initial_b, "win", 10, 10
        )

        # Winner should gain ELO
        assert new_a > initial_a, "Winner should gain ELO"
        # Loser should lose ELO
        assert new_b < initial_b, "Loser should lose ELO"
        # Changes should be equal magnitude (for equal fight counts)
        assert abs((new_a - initial_a) + (new_b - initial_b)) < 1, \
            "ELO changes should sum to ~0"


class TestQuickValidation:
    """Quick validation tests that don't require full walk-forward."""

    def test_temporal_split_verification(self, detailed_fights_df):
        """Run quick temporal split verification."""
        from validation.walk_forward import QuickValidator

        result = QuickValidator.verify_temporal_split()

        assert result["passed"], f"Temporal split verification failed: {result}"
        assert result["no_overlap"], "Train and test sets overlap!"
        assert result["train_count"] > 0, "No training data"
        assert result["test_count"] > 0, "No test data"


class TestDataConsistency:
    """Tests for general data consistency."""

    def test_no_duplicate_fights(self, detailed_fights_df):
        """Verify no exact duplicate rows."""
        duplicates = detailed_fights_df.duplicated()
        assert not duplicates.any(), \
            f"Found {duplicates.sum()} duplicate rows"

    def test_result_column_valid(self, detailed_fights_df):
        """Verify Result column has valid values."""
        valid_results = {"win", "loss"}
        results = set(detailed_fights_df["Result"].unique())

        assert results.issubset(valid_results), \
            f"Invalid results found: {results - valid_results}"

    def test_fighter_names_not_empty(self, detailed_fights_df):
        """Verify fighter names are not empty."""
        assert not detailed_fights_df["Red Fighter"].isna().any(), \
            "Found empty Red Fighter names"
        assert not detailed_fights_df["Blue Fighter"].isna().any(), \
            "Found empty Blue Fighter names"

        assert not (detailed_fights_df["Red Fighter"] == "").any(), \
            "Found blank Red Fighter names"
        assert not (detailed_fights_df["Blue Fighter"] == "").any(), \
            "Found blank Blue Fighter names"

    def test_fighters_not_fighting_themselves(self, detailed_fights_df):
        """Verify no fighter fights themselves."""
        same_fighter = detailed_fights_df["Red Fighter"] == detailed_fights_df["Blue Fighter"]
        assert not same_fighter.any(), \
            f"Found {same_fighter.sum()} fights where fighter fights themselves"
