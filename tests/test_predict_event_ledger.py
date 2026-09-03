import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bet_ledger  # noqa: E402
import predict_event  # noqa: E402

ROWS = [("A", "B", 0.7), ("B", "A", 0.3)]
BETS = [dict(fighter="A", opponent="B", odds=-150, model_prob=0.66, implied_prob=0.58,
             edge=0.08, kelly=0.12, stake_pct=0.6)]


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(predict_event, "PRED_JSON", str(tmp_path / "predicted_data.json"))
    monkeypatch.setattr(predict_event, "BET_CSV", str(tmp_path / "betting_predictions.csv"))
    return tmp_path


def test_write_outputs_records_bets_in_the_ledger(outputs, monkeypatch):
    calls = []
    monkeypatch.setattr(bet_ledger, "record", lambda *args, **kw: calls.append(args) or 1)
    predict_event.write_outputs(ROWS, "UFC 999", BETS, "2026-09-06")
    assert len(calls) == 1
    event, event_date, generated, bets = calls[0]
    assert (event, event_date, bets) == ("UFC 999", "2026-09-06", BETS)
    payload = json.load(open(outputs / "predicted_data.json"))
    assert payload["event_date"] == "2026-09-06"
    assert payload["generated"] == generated
    assert payload["bets"] == BETS


def test_write_outputs_without_bets_leaves_the_ledger_alone(outputs, monkeypatch):
    def boom(*args, **kw):
        raise AssertionError("record must not be called without bets")
    monkeypatch.setattr(bet_ledger, "record", boom)
    predict_event.write_outputs(ROWS, "UFC 999", [], "2026-09-06")
    payload = json.load(open(outputs / "predicted_data.json"))
    assert "bets" not in payload and payload["event_date"] == "2026-09-06"
