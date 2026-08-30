"""
Audit trail logging for backtesting predictions.

This module provides comprehensive logging of what data was available at each
prediction point, enabling manual verification of no data leakage.

Key features:
- Log model training events with data ranges and hashes
- Log each prediction with fighter stats at that time
- Generate human-readable audit reports
- Provide verification checklists for manual review
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


class BacktestAuditLogger:
    """
    Logs detailed audit trail during backtesting for verification.

    All logged data can be used to manually verify that each prediction
    was made using only historically available information.
    """

    def __init__(self, output_dir: str = None):
        """
        Initialize audit logger.

        Args:
            output_dir: Directory for audit logs
        """
        self.output_dir = output_dir or os.path.join("logs", "audit")
        os.makedirs(self.output_dir, exist_ok=True)

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.predictions: List[Dict] = []
        self.model_trainings: List[Dict] = []
        self.feature_derivations: List[Dict] = []

    def log_model_training(
        self,
        training_date: datetime,
        training_data_start: datetime,
        training_data_end: datetime,
        num_training_fights: int,
        model_params: Dict,
        feature_columns: List[str],
        cv_score: float,
        training_data_hash: str
    ):
        """
        Log details when model is trained.

        Args:
            training_date: Date when model training was triggered
            training_data_start: Earliest fight in training data
            training_data_end: Latest fight in training data
            num_training_fights: Number of fights in training set
            model_params: Model hyperparameters used
            feature_columns: List of feature column names
            cv_score: Cross-validation score achieved
            training_data_hash: Hash of training data for integrity
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "training_triggered_at": training_date.isoformat(),
            "data_range": {
                "start": training_data_start.isoformat() if training_data_start else None,
                "end": training_data_end.isoformat() if training_data_end else None
            },
            "num_training_fights": num_training_fights,
            "model_params": model_params,
            "num_features": len(feature_columns),
            "feature_columns_sample": feature_columns[:20],  # First 20 for brevity
            "cv_score": cv_score,
            "training_data_hash": training_data_hash
        }

        self.model_trainings.append(entry)
        self._append_to_jsonl("model_trainings.jsonl", entry)

    def log_prediction(
        self,
        prediction_date: datetime,
        fighter1: str,
        fighter2: str,
        fighter1_stats: Dict,
        fighter2_stats: Dict,
        feature_values: Dict,
        predicted_prob: float,
        model_training_date: datetime,
        actual_result: Optional[str] = None,
        odds1: Optional[float] = None,
        odds2: Optional[float] = None,
        bet_placed: bool = False,
        bet_amount: float = 0
    ):
        """
        Log details for each prediction.

        Args:
            prediction_date: Date of the fight being predicted
            fighter1: First fighter name
            fighter2: Second fighter name
            fighter1_stats: Fighter 1's stats at prediction time
            fighter2_stats: Fighter 2's stats at prediction time
            feature_values: Key feature values used
            predicted_prob: Predicted probability for fighter1
            model_training_date: When the model making this prediction was trained
            actual_result: Actual fight outcome (if known)
            odds1: Betting odds for fighter1
            odds2: Betting odds for fighter2
            bet_placed: Whether a bet was placed
            bet_amount: Amount bet (if any)
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prediction_date": prediction_date.isoformat(),
            "fight": {
                "fighter1": fighter1,
                "fighter2": fighter2
            },
            "fighter1_stats_at_prediction": {
                "elo": fighter1_stats.get("elo"),
                "total_fights": fighter1_stats.get("totalfights"),
                "win_streak": fighter1_stats.get("winstreak"),
                "lose_streak": fighter1_stats.get("losestreak"),
                "wins": fighter1_stats.get("wins"),
                "last_fight": str(fighter1_stats.get("last_fight")) if fighter1_stats.get("last_fight") else None
            },
            "fighter2_stats_at_prediction": {
                "elo": fighter2_stats.get("elo"),
                "total_fights": fighter2_stats.get("totalfights"),
                "win_streak": fighter2_stats.get("winstreak"),
                "lose_streak": fighter2_stats.get("losestreak"),
                "wins": fighter2_stats.get("wins"),
                "last_fight": str(fighter2_stats.get("last_fight")) if fighter2_stats.get("last_fight") else None
            },
            "key_features": feature_values,
            "prediction": {
                "fighter1_win_prob": predicted_prob,
                "fighter2_win_prob": 1 - predicted_prob
            },
            "model_trained_on": model_training_date.isoformat(),
            "actual_result": actual_result,
            "betting": {
                "odds1": odds1,
                "odds2": odds2,
                "bet_placed": bet_placed,
                "bet_amount": bet_amount
            }
        }

        self.predictions.append(entry)
        self._append_to_jsonl("predictions.jsonl", entry)

    def log_feature_derivation(
        self,
        fight_date: datetime,
        fighter: str,
        feature_name: str,
        raw_value: Any,
        computed_value: Any,
        derivation_steps: List[str]
    ):
        """
        Log how a specific feature value was derived.

        Useful for detailed verification of feature computation.

        Args:
            fight_date: Date of the fight
            fighter: Fighter name
            feature_name: Name of the feature
            raw_value: Raw value before processing
            computed_value: Final computed value
            derivation_steps: Steps taken to derive the value
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "fight_date": fight_date.isoformat(),
            "fighter": fighter,
            "feature": feature_name,
            "raw_value": raw_value,
            "computed_value": computed_value,
            "derivation": derivation_steps
        }

        self.feature_derivations.append(entry)
        self._append_to_jsonl("feature_derivations.jsonl", entry)

    def generate_audit_report(self) -> str:
        """
        Generate human-readable audit report.

        Returns:
            Path to generated report
        """
        report_path = os.path.join(
            self.output_dir,
            f"audit_report_{self.session_id}.md"
        )

        with open(report_path, "w") as f:
            f.write("# Backtesting Audit Report\n\n")
            f.write(f"**Session ID:** {self.session_id}\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")

            # Summary
            f.write("## Summary\n\n")
            f.write(f"- Total model trainings: {len(self.model_trainings)}\n")
            f.write(f"- Total predictions: {len(self.predictions)}\n")

            if self.predictions:
                correct = sum(1 for p in self.predictions if p.get("actual_result") == "correct")
                f.write(f"- Correct predictions: {correct}\n")
                f.write(f"- Accuracy: {correct/len(self.predictions):.2%}\n")
            f.write("\n")

            # Model Training Events
            f.write("## Model Training Events\n\n")
            for i, training in enumerate(self.model_trainings, 1):
                f.write(f"### Training #{i} at {training['training_triggered_at']}\n")
                f.write(f"- Data range: {training['data_range']['start']} to {training['data_range']['end']}\n")
                f.write(f"- Num fights: {training['num_training_fights']}\n")
                f.write(f"- Num features: {training['num_features']}\n")
                f.write(f"- CV Score: {training['cv_score']:.4f}\n")
                f.write(f"- Data hash: `{training['training_data_hash'][:16]}...`\n\n")

            # Sample Predictions for Verification
            f.write("## Sample Predictions (for manual verification)\n\n")
            sample_size = min(10, len(self.predictions))
            for pred in self.predictions[:sample_size]:
                f.write(f"### {pred['fight']['fighter1']} vs {pred['fight']['fighter2']}\n")
                f.write(f"- **Date:** {pred['prediction_date']}\n")
                f.write(f"- **Model trained on:** {pred['model_trained_on']}\n\n")

                f.write("| Stat | Fighter 1 | Fighter 2 |\n")
                f.write("|------|-----------|----------|\n")
                stats1 = pred['fighter1_stats_at_prediction']
                stats2 = pred['fighter2_stats_at_prediction']
                f.write(f"| ELO | {stats1.get('elo', 'N/A')} | {stats2.get('elo', 'N/A')} |\n")
                f.write(f"| Total Fights | {stats1.get('total_fights', 'N/A')} | {stats2.get('total_fights', 'N/A')} |\n")
                f.write(f"| Win Streak | {stats1.get('win_streak', 'N/A')} | {stats2.get('win_streak', 'N/A')} |\n")
                f.write("\n")

                f.write(f"- **Predicted prob (F1 wins):** {pred['prediction']['fighter1_win_prob']:.3f}\n")
                f.write(f"- **Actual result:** {pred.get('actual_result', 'N/A')}\n\n")

            # Verification Checklist
            f.write("## Verification Checklist\n\n")
            f.write("Use this checklist to manually verify data integrity:\n\n")
            f.write("- [ ] Each model was trained on data BEFORE the prediction date\n")
            f.write("- [ ] Fighter stats at prediction time match historical records\n")
            f.write("- [ ] ELO ratings reflect only fights before the prediction date\n")
            f.write("- [ ] Win/lose streaks match actual fight history\n")
            f.write("- [ ] No future information present in any prediction\n\n")

            # Data Sources
            f.write("## Data Sources to Cross-Reference\n\n")
            f.write("- `data/detailed_fights.csv` - Feature-engineered dataset\n")
            f.write("- `data/modified_fight_details.csv` - Raw processed fights\n")
            f.write(f"- `{self.output_dir}/{self.session_id}_predictions.jsonl` - Full prediction logs\n")
            f.write(f"- `{self.output_dir}/{self.session_id}_model_trainings.jsonl` - Training logs\n")

        print(f"Audit report generated: {report_path}")
        return report_path

    def verify_prediction_manually(self, prediction_index: int) -> Dict:
        """
        Get all data needed to manually verify a specific prediction.

        Args:
            prediction_index: Index of prediction to verify

        Returns:
            Dictionary with prediction details and verification checklist
        """
        if prediction_index >= len(self.predictions):
            return {"error": f"Prediction index {prediction_index} out of range"}

        pred = self.predictions[prediction_index]

        return {
            "prediction": pred,
            "verification_checklist": [
                f"[ ] Verify {pred['fight']['fighter1']} had {pred['fighter1_stats_at_prediction']['total_fights']} UFC fights before {pred['prediction_date']}",
                f"[ ] Verify {pred['fight']['fighter2']} had {pred['fighter2_stats_at_prediction']['total_fights']} UFC fights before {pred['prediction_date']}",
                f"[ ] Verify model was trained on data before {pred['model_trained_on']}",
                f"[ ] Verify {pred['fight']['fighter1']} ELO ({pred['fighter1_stats_at_prediction']['elo']}) is correct for pre-{pred['prediction_date']}",
                f"[ ] Verify {pred['fight']['fighter2']} ELO ({pred['fighter2_stats_at_prediction']['elo']}) is correct for pre-{pred['prediction_date']}"
            ],
            "data_sources": [
                "data/detailed_fights.csv",
                "data/modified_fight_details.csv",
                f"{self.output_dir}/{self.session_id}_predictions.jsonl"
            ],
            "how_to_verify": [
                f"1. Filter detailed_fights.csv for fights before {pred['prediction_date']}",
                f"2. Count fights involving {pred['fight']['fighter1']} and {pred['fight']['fighter2']}",
                f"3. Manually calculate ELO from fight history",
                f"4. Compare with logged stats above"
            ]
        }

    def get_summary_stats(self) -> Dict:
        """Get summary statistics from audit log."""
        if not self.predictions:
            return {"error": "No predictions logged"}

        correct = sum(
            1 for p in self.predictions
            if p.get("actual_result") == "correct"
        )

        return {
            "session_id": self.session_id,
            "total_predictions": len(self.predictions),
            "correct_predictions": correct,
            "accuracy": correct / len(self.predictions) if self.predictions else 0,
            "model_trainings": len(self.model_trainings),
            "date_range": {
                "first_prediction": self.predictions[0]["prediction_date"] if self.predictions else None,
                "last_prediction": self.predictions[-1]["prediction_date"] if self.predictions else None
            }
        }

    def export_for_analysis(self, output_path: str = None) -> str:
        """
        Export full audit log for external analysis.

        Args:
            output_path: Path for export file

        Returns:
            Path to exported file
        """
        if output_path is None:
            output_path = os.path.join(
                self.output_dir,
                f"audit_export_{self.session_id}.json"
            )

        export_data = {
            "session_id": self.session_id,
            "export_timestamp": datetime.now().isoformat(),
            "summary": self.get_summary_stats(),
            "model_trainings": self.model_trainings,
            "predictions": self.predictions,
            "feature_derivations": self.feature_derivations
        }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        return output_path

    def _append_to_jsonl(self, filename: str, entry: Dict):
        """Append entry to JSONL file for crash recovery."""
        filepath = os.path.join(self.output_dir, f"{self.session_id}_{filename}")
        with open(filepath, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")


# Convenience function for quick integration
def create_audit_logger(output_dir: str = None) -> BacktestAuditLogger:
    """
    Create and return a new audit logger instance.

    Args:
        output_dir: Directory for audit logs

    Returns:
        Configured BacktestAuditLogger instance
    """
    return BacktestAuditLogger(output_dir)
