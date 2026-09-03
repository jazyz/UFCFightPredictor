import csv
import os
import sys
from datetime import datetime

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bet_ledger  # noqa: E402

PICKS = [
    dict(fighter="A", opponent="B", odds=-150, model_prob=0.66, implied_prob=0.58, edge=0.08, kelly=0.12, stake_pct=0.6),
    dict(fighter="C", opponent="D", odds=180, model_prob=0.45, implied_prob=0.36, edge=0.09, kelly=0.10, stake_pct=0.5),
    dict(fighter="E", opponent="F", odds=-110, model_prob=0.60, implied_prob=0.52, edge=0.08, kelly=0.10, stake_pct=0.5),
    dict(fighter="G", opponent="H", odds=120, model_prob=0.55, implied_prob=0.45, edge=0.10, kelly=0.10, stake_pct=0.5),
]
FIELDS = ["Title", "Winner", "Loser", "Draw", "Method", "Date", "Red Fighter", "Blue Fighter"]


def write_results(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def row(winner, loser, draw, date, red, blue):
    return {"Title": "Bout", "Winner": winner, "Loser": loser, "Draw": draw, "Method": "Decision",
            "Date": date, "Red Fighter": red, "Blue Fighter": blue}


def test_record_appends_pending_entries_and_is_idempotent(tmp_path):
    path = str(tmp_path / "ledger.json")
    assert bet_ledger.record("UFC 999", "2026-09-06", "2026-09-04T02:00:00", PICKS, path=path) == 4
    assert bet_ledger.record("UFC 999", "2026-09-06", "2026-09-04T03:00:00", PICKS, path=path) == 0
    entries = bet_ledger.load(path)
    assert len(entries) == 4
    assert all(e.result == "pending" and e.pnl_per_unit is None and e.graded is None for e in entries)
    first = entries[0]
    assert (first.event, first.event_date, first.generated) == ("UFC 999", "2026-09-06", "2026-09-04T02:00:00")
    assert (first.fighter, first.opponent, first.odds) == ("A", "B", -150)
    assert (first.model_prob, first.market_prob, first.edge, first.kelly, first.stake_pct) == (0.66, 0.58, 0.08, 0.12, 0.6)


def test_record_with_no_bets_creates_nothing(tmp_path):
    path = str(tmp_path / "ledger.json")
    assert bet_ledger.record("UFC 999", "2026-09-06", "2026-09-04T02:00:00", [], path=path) == 0
    assert not os.path.exists(path)


def test_grade_settles_win_loss_push_and_leaves_unmatched_pending(tmp_path):
    path = str(tmp_path / "ledger.json")
    results = str(tmp_path / "results.csv")
    bet_ledger.record("UFC 999", "2026-09-06", "2026-09-04T02:00:00", PICKS, path=path)
    write_results(results, [
        row("A", "B", "False", "September 06, 2026", "B", "A"),        # win, corners swapped
        row("D", "C", "False", "September 06, 2026", "C", "D"),        # loss
        row("", "", "True", "September 07, 2026", "E", "F"),           # draw one day later -> push
        row("G", "H", "False", "January 01, 2026", "G", "H"),          # same pair, wrong card -> stays pending
    ])
    graded = bet_ledger.grade(results_csv=results, path=path, now=datetime(2026, 9, 8, 2, 5))
    assert graded == 3
    by = {e.fighter: e for e in bet_ledger.load(path)}
    assert by["A"].result == "win" and by["A"].pnl_per_unit == pytest.approx(100 / 150, abs=1e-4)
    assert by["C"].result == "loss" and by["C"].pnl_per_unit == -1.0
    assert by["E"].result == "push" and by["E"].pnl_per_unit == 0.0
    assert by["A"].graded == "2026-09-08T02:05:00"
    assert by["G"].result == "pending" and by["G"].graded is None
    assert bet_ledger.grade(results_csv=results, path=path) == 0


def test_grade_positive_odds_pay_odds_over_100(tmp_path):
    path = str(tmp_path / "ledger.json")
    results = str(tmp_path / "results.csv")
    bet_ledger.record("UFC 999", "2026-09-06", "2026-09-04T02:00:00", [PICKS[1]], path=path)
    write_results(results, [row("C", "D", "False", "September 06, 2026", "C", "D")])
    assert bet_ledger.grade(results_csv=results, path=path) == 1
    assert bet_ledger.load(path)[0].pnl_per_unit == pytest.approx(1.8)


def test_grade_without_a_ledger_file_returns_zero(tmp_path):
    assert bet_ledger.grade(results_csv=str(tmp_path / "none.csv"), path=str(tmp_path / "missing.json")) == 0
