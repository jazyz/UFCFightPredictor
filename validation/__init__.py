"""
Validation package for proving no data leakage in UFC Fight Predictor backtesting.

Components:
- process_fights_isolated: Stateless feature processor for walk-forward validation
- holdout_validator: Independent validation set management
- walk_forward: Walk-forward validation implementation
- audit_logger: Audit trail for backtesting predictions
"""

from .holdout_validator import HOLDOUT_START_DATE, load_training_data
