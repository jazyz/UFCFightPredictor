"""Temperature calibrator for the ensemble's win probabilities.

ml_ensemble.py fits logit(q) = a * logit(p) on pooled out-of-fold predictions
and saves {'a': ...} to saved_preprocessing/calibrator.joblib; every serving
path applies it through calibrate() below. The form has no intercept, so
calibrated corner probabilities stay complementary under the Red/Blue swap,
and a = 1 is the identity. When no calibrator artifact exists (older model
dirs, rolled-back deploys), calibrate() is a no-op.
"""
import os

import joblib
import numpy as np

CALIBRATOR_PATH = os.path.join("saved_preprocessing", "calibrator.joblib")


def load_temperature(path=CALIBRATOR_PATH):
    """The fitted exponent a, or None when no calibrator has been trained."""
    if not os.path.exists(path):
        return None
    return joblib.load(path)["a"]


def apply_temperature(p, a):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return 1.0 / (1.0 + np.exp(-a * np.log(p / (1.0 - p))))


def calibrate(p, path=CALIBRATOR_PATH):
    """Calibrated copy of win probability array p (no-op without an artifact)."""
    a = load_temperature(path)
    return np.asarray(p, dtype=float) if a is None else apply_temperature(p, a)
