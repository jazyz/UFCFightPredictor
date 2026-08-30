"""
Independent validation set management.

This module ensures 2024+ data is never used during development or tuning,
providing a truly unbiased final evaluation.

CRITICAL: The HOLDOUT_START_DATE defines the boundary. Never use data
on or after this date for any development, hyperparameter tuning, or
model selection. The holdout set should only be used for final evaluation.
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd

# CRITICAL: This date defines the holdout boundary
# NEVER use data on or after this date for any development/tuning
HOLDOUT_START_DATE = "2024-01-01"


class HoldoutValidator:
    """
    Manages independent validation set that's never seen during development.

    The holdout set provides an unbiased estimate of model performance on
    truly unseen data. This is critical for proving the model generalizes
    beyond the data it was trained/tuned on.
    """

    def __init__(self, holdout_start: str = HOLDOUT_START_DATE):
        """
        Initialize validator.

        Args:
            holdout_start: Date string (YYYY-MM-DD) marking start of holdout period
        """
        self.holdout_start = pd.to_datetime(holdout_start)
        self.holdout_hash: Optional[str] = None

    def create_development_split(
        self,
        full_data_path: str = None,
        output_dir: str = None
    ) -> Tuple[str, str]:
        """
        Split data into development and holdout sets.

        Creates two files:
        - development_data.csv: Safe to use for all development activities
        - holdout_data.csv: NEVER touch until final evaluation

        Also creates split_metadata.json with hash for integrity verification.

        Args:
            full_data_path: Path to full detailed_fights.csv
            output_dir: Directory for output splits

        Returns:
            Tuple of (development_path, holdout_path)
        """
        if full_data_path is None:
            full_data_path = os.path.join('data', 'detailed_fights.csv')
        if output_dir is None:
            output_dir = os.path.join('data', 'splits')

        os.makedirs(output_dir, exist_ok=True)

        # Load full dataset
        df = pd.read_csv(full_data_path)
        df["Date"] = pd.to_datetime(df["Date"], format="mixed")

        # Split by date
        dev_df = df[df["Date"] < self.holdout_start]
        holdout_df = df[df["Date"] >= self.holdout_start]

        # Save development data (safe to use)
        dev_path = os.path.join(output_dir, "development_data.csv")
        dev_df.to_csv(dev_path, index=False)

        # Save holdout data (NEVER touch until final evaluation)
        holdout_path = os.path.join(output_dir, "holdout_data.csv")
        holdout_df.to_csv(holdout_path, index=False)

        # Create hash of holdout set for integrity verification
        self.holdout_hash = self._compute_hash(holdout_df)

        # Save metadata
        metadata = {
            "created_at": datetime.now().isoformat(),
            "holdout_start_date": self.holdout_start.isoformat(),
            "dev_fights": len(dev_df),
            "holdout_fights": len(holdout_df),
            "holdout_hash": self.holdout_hash,
            "dev_date_range": {
                "start": dev_df["Date"].min().isoformat() if len(dev_df) > 0 else None,
                "end": dev_df["Date"].max().isoformat() if len(dev_df) > 0 else None
            },
            "holdout_date_range": {
                "start": holdout_df["Date"].min().isoformat() if len(holdout_df) > 0 else None,
                "end": holdout_df["Date"].max().isoformat() if len(holdout_df) > 0 else None
            },
            "warning": "NEVER use holdout_data.csv for development, training, or tuning!"
        }

        metadata_path = os.path.join(output_dir, "split_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"Development set: {len(dev_df)} fights (before {self.holdout_start.date()})")
        print(f"Holdout set: {len(holdout_df)} fights (from {self.holdout_start.date()})")
        print(f"Holdout hash: {self.holdout_hash[:16]}...")
        print(f"Files saved to: {output_dir}")

        return dev_path, holdout_path

    def verify_holdout_integrity(
        self,
        holdout_path: str = None,
        metadata_path: str = None
    ) -> bool:
        """
        Verify holdout set hasn't been modified since creation.

        Raises:
            ValueError: If holdout set has been modified

        Returns:
            True if integrity check passes
        """
        if holdout_path is None:
            holdout_path = os.path.join('data', 'splits', 'holdout_data.csv')
        if metadata_path is None:
            metadata_path = os.path.join('data', 'splits', 'split_metadata.json')

        if not os.path.exists(metadata_path):
            raise FileNotFoundError(
                f"Metadata file not found: {metadata_path}\n"
                "Run create_development_split() first."
            )

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        if not os.path.exists(holdout_path):
            raise FileNotFoundError(f"Holdout file not found: {holdout_path}")

        holdout_df = pd.read_csv(holdout_path)
        current_hash = self._compute_hash(holdout_df)

        if current_hash != metadata["holdout_hash"]:
            raise ValueError(
                f"HOLDOUT INTEGRITY VIOLATION!\n"
                f"Expected hash: {metadata['holdout_hash']}\n"
                f"Current hash: {current_hash}\n"
                f"The holdout set has been modified!"
            )

        print(f"Holdout integrity verified: {len(holdout_df)} fights, hash matches")
        return True

    def get_final_evaluation(
        self,
        model_path: str,
        holdout_path: str = None,
        preprocessing_path: str = None
    ) -> Dict:
        """
        Run final unbiased evaluation on holdout set.

        THIS SHOULD ONLY BE CALLED ONCE WHEN DEVELOPMENT IS COMPLETE.
        Results should be reported as the final model performance.

        Args:
            model_path: Path to trained model (.joblib)
            holdout_path: Path to holdout data CSV
            preprocessing_path: Path to preprocessing artifacts

        Returns:
            Dictionary with evaluation metrics
        """
        import joblib
        from sklearn.metrics import accuracy_score, log_loss, classification_report

        if holdout_path is None:
            holdout_path = os.path.join('data', 'splits', 'holdout_data.csv')

        # Verify integrity first
        self.verify_holdout_integrity(holdout_path)

        # Load model
        model = joblib.load(model_path)

        # Load holdout data
        holdout_df = pd.read_csv(holdout_path)
        holdout_df["Date"] = pd.to_datetime(holdout_df["Date"], format="mixed")

        # Prepare features (exclude non-feature columns)
        exclude_cols = ["Result", "Date", "Red Fighter", "Blue Fighter", "Title"]
        feature_cols = [c for c in holdout_df.columns if c not in exclude_cols]

        X_holdout = holdout_df[feature_cols]
        y_holdout = holdout_df["Result"].map({"win": 1, "loss": 0})

        # Handle any missing values
        X_holdout = X_holdout.fillna(0)

        # Predict
        y_pred = model.predict(X_holdout)
        y_prob = model.predict_proba(X_holdout)

        # Calculate metrics
        accuracy = accuracy_score(y_holdout, y_pred)
        logloss = log_loss(y_holdout, y_prob)

        results = {
            "evaluation_date": datetime.now().isoformat(),
            "holdout_period": f"{holdout_df['Date'].min()} to {holdout_df['Date'].max()}",
            "num_fights": len(holdout_df),
            "accuracy": float(accuracy),
            "log_loss": float(logloss),
            "model_path": model_path,
            "classification_report": classification_report(y_holdout, y_pred, output_dict=True)
        }

        # Save results
        results_path = os.path.join('data', 'splits', 'final_evaluation.json')
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n=== FINAL HOLDOUT EVALUATION ===")
        print(f"Period: {results['holdout_period']}")
        print(f"Fights: {results['num_fights']}")
        print(f"Accuracy: {results['accuracy']:.4f}")
        print(f"Log Loss: {results['log_loss']:.4f}")
        print(f"Results saved to: {results_path}")

        return results

    @staticmethod
    def _compute_hash(df: pd.DataFrame) -> str:
        """Compute SHA256 hash of dataframe for integrity verification."""
        return hashlib.sha256(
            df.to_csv(index=False).encode()
        ).hexdigest()


def load_training_data(path: str = None) -> pd.DataFrame:
    """
    Safe data loader that automatically excludes holdout period.

    USE THIS INSTEAD OF pd.read_csv() during development to ensure
    holdout data is never accidentally used.

    Args:
        path: Path to data file

    Returns:
        DataFrame with holdout period excluded
    """
    if path is None:
        path = os.path.join('data', 'detailed_fights.csv')

    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="mixed")

    holdout_start = pd.to_datetime(HOLDOUT_START_DATE)

    holdout_count = (df["Date"] >= holdout_start).sum()
    if holdout_count > 0:
        print(f"WARNING: Excluding {holdout_count} holdout fights (>= {HOLDOUT_START_DATE})")
        df = df[df["Date"] < holdout_start]

    return df


def check_data_for_holdout_leak(df: pd.DataFrame, context: str = "") -> bool:
    """
    Check if a DataFrame contains any holdout period data.

    Use this to verify data doesn't leak holdout information.

    Args:
        df: DataFrame to check
        context: Description of where this data came from (for error message)

    Returns:
        True if data is clean (no holdout data)

    Raises:
        ValueError: If holdout data is present
    """
    if "Date" not in df.columns:
        print(f"Warning: No 'Date' column found in DataFrame. Cannot verify holdout exclusion.")
        return True

    df_dates = pd.to_datetime(df["Date"], format="mixed")
    holdout_start = pd.to_datetime(HOLDOUT_START_DATE)

    holdout_count = (df_dates >= holdout_start).sum()
    if holdout_count > 0:
        raise ValueError(
            f"DATA LEAKAGE DETECTED! {context}\n"
            f"Found {holdout_count} fights from holdout period (>= {HOLDOUT_START_DATE})\n"
            f"This data should never be used during development!"
        )

    return True
