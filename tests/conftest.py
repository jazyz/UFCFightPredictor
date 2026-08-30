"""
Pytest configuration and fixtures for data leakage tests.

This module provides shared fixtures for all tests in the package.
"""

import os
import sys

import pytest
import pandas as pd

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture(scope="session")
def project_root_path():
    """Return project root path."""
    return project_root


@pytest.fixture(scope="session")
def data_dir():
    """Return path to data directory."""
    return os.path.join(project_root, "data")


@pytest.fixture(scope="session")
def raw_fights_df(data_dir):
    """Load raw fights data once per test session."""
    path = os.path.join(data_dir, "modified_fight_details.csv")
    if not os.path.exists(path):
        pytest.skip(f"Data file not found: {path}")
    return pd.read_csv(path)


@pytest.fixture(scope="session")
def detailed_fights_df(data_dir):
    """Load feature-engineered fights data once per test session."""
    path = os.path.join(data_dir, "detailed_fights.csv")
    if not os.path.exists(path):
        pytest.skip(f"Data file not found: {path}")
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="mixed")
    return df


@pytest.fixture(scope="session")
def fight_results_df(data_dir):
    """Load fight results with odds."""
    path = os.path.join(data_dir, "fight_results_with_odds.csv")
    if not os.path.exists(path):
        pytest.skip(f"Data file not found: {path}")
    return pd.read_csv(path)


@pytest.fixture
def sample_split_date():
    """Return a sample split date for testing."""
    return pd.to_datetime("2021-01-01")


@pytest.fixture
def holdout_start_date():
    """Return holdout start date."""
    return pd.to_datetime("2024-01-01")


@pytest.fixture
def processor():
    """Return fresh ProcessFightsIsolated instance."""
    from validation.process_fights_isolated import ProcessFightsIsolated
    return ProcessFightsIsolated()
