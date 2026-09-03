import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import auto_retrain  # noqa: E402
import bet_ledger  # noqa: E402


def test_step_grade_ledger_logs_the_count(monkeypatch, caplog):
    monkeypatch.setattr(bet_ledger, "grade", lambda: 3)
    with caplog.at_level(logging.INFO, logger="auto_retrain"):
        auto_retrain.step_grade_ledger()
    assert "3" in caplog.text


def test_step_grade_ledger_never_raises(monkeypatch, caplog):
    def boom():
        raise RuntimeError("ledger unreadable")
    monkeypatch.setattr(bet_ledger, "grade", boom)
    with caplog.at_level(logging.WARNING, logger="auto_retrain"):
        auto_retrain.step_grade_ledger()   # must not raise
    assert "ledger unreadable" in caplog.text
