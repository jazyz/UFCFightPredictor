import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import calibration  # noqa: E402


def test_calibrated_corners_stay_complementary():
    p = np.array([0.05, 0.3, 0.5, 0.7, 0.95])
    assert np.allclose(calibration.calibrate(p) + calibration.calibrate(1 - p), 1.0, atol=1e-9)


def test_artifact_path_is_anchored_on_the_repo_not_the_cwd():
    assert calibration.CALIBRATOR_PATH == os.path.join(ROOT, "saved_preprocessing", "calibrator.joblib")


def test_missing_artifact_warns_and_passes_through(tmp_path):
    p = np.array([0.2, 0.8])
    with pytest.warns(UserWarning):
        out = calibration.calibrate(p, path=str(tmp_path / "missing.joblib"))
    assert np.allclose(out, p)
