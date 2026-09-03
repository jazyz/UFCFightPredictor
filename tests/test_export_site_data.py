"""Unit tests for testing/export_site_data.py on a tiny synthetic cache."""
import csv
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "testing"))

import betting_math  # noqa: E402
import export_site_data as esd  # noqa: E402

# (red, blue, predicted result, probability) -> P(red wins) is prob if "win" else 1-prob
CACHE_ROWS = [
    ("A", "B", "win", "0.72"),   # P(A beats B) = 0.72
    ("B", "A", "loss", "0.70"),  # P(B beats A) = 0.30  -> model_a = (0.72 + 0.70)/2 = 0.71
    ("C", "D", "loss", "0.60"),  # P(C beats D) = 0.40
    ("D", "C", "win", "0.62"),   # P(D beats C) = 0.62  -> model_c = (0.40 + 0.38)/2 = 0.39
    ("E", "F", "win", "0.56"),   # P(E beats F) = 0.56
    ("F", "E", "loss", "0.56"),  # P(F beats E) = 0.44  -> model_e = 0.56
]
ODDS_ROWS = [
    ("ufc-1", "Jan 04 2025", "A", "B", "A", "-150", "+130"),
    ("ufc-1", "Jan 04 2025", "C", "D", "D", "+200", "-240"),
    ("ufc-fight-night-february-01-2025", "Feb 01 2025", "E", "F", "F", "-", "-"),
]


@pytest.fixture
def fixture_dir(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    with open(cache / "pred_2025-01-01.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Red Fighter", "Blue Fighter", "Predicted Result", "Probability"])
        w.writerows(CACHE_ROWS)
    odds = tmp_path / "odds.csv"
    with open(odds, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["event_name", "event_date", "fighter1_name", "fighter2_name",
                    "winner_name", "fighter1_odds", "fighter2_odds"])
        w.writerows(ODDS_ROWS)
    return str(cache), str(odds)


@pytest.fixture
def payload(fixture_dir):
    cache, odds = fixture_dir
    return esd.build_payload(esd.load_caches(cache), odds, "2025-01-01", "2025-12-31")


def test_coverage_and_accuracy_average_both_orientations(payload):
    assert payload.coverage == esd.Coverage(fights_in_window=3, scored=3, with_odds=2)
    assert payload.metrics.n == 3
    # A (0.71) correct, D (0.61) correct, E (0.56) wrong
    assert payload.metrics.accuracy == pytest.approx(2 / 3, abs=1e-4)
    assert payload.window == esd.Window(start="2025-01-01", end="2025-12-31",
                                        retrains=["2025-01-01"])


def test_bands_and_monthly(payload):
    by_label = {b.label: b for b in payload.bands}
    assert [b.label for b in payload.bands] == ["50–55%", "55–60%", "60–65%", "65–70%", "70%+"]
    assert by_label["70%+"].n == 1 and by_label["70%+"].hit == 1.0
    assert by_label["70%+"].stated == pytest.approx(0.71, abs=1e-4)
    assert by_label["60–65%"].n == 1 and by_label["60–65%"].hit == 1.0
    assert by_label["55–60%"].n == 1 and by_label["55–60%"].hit == 0.0
    assert by_label["50–55%"].n == 0 and by_label["50–55%"].hit is None
    assert payload.monthly == [esd.MonthRow(month="2025-01", n=2, hit=1.0),
                               esd.MonthRow(month="2025-02", n=1, hit=0.0)]


def test_bet_replay_matches_betting_math(payload):
    assert len(payload.bets) == 1
    bet = payload.bets[0]
    expected = betting_math.decide_bet(0.71, None, -150, 130, blend_w=0.8, min_edge=0.05,
                                       fraction=0.05, cap=0.05, bankroll=1000.0)
    assert (bet.fighter, bet.opponent, bet.odds, bet.result, bet.source) == ("A", "B", -150, "win", "backtest")
    assert bet.stake == pytest.approx(expected["stake"], abs=0.005)
    assert bet.pnl == pytest.approx(expected["stake"] * 100 / 150, abs=0.005)
    assert bet.model_prob == pytest.approx(expected["prob"], abs=1e-4)
    assert bet.market_prob == pytest.approx(expected["market_prob"], abs=1e-4)
    assert payload.betting.final == pytest.approx(1000 + expected["stake"] * 100 / 150, abs=0.005)
    assert payload.betting.bets == 1 and payload.betting.hit == 1.0
    assert payload.betting.favorites == esd.SideRecord(won=1, total=1)
    assert payload.betting.underdogs == esd.SideRecord(won=0, total=0)
    assert payload.betting.max_drawdown_pct == 0.0
    assert payload.betting.low == 1000.0
    # one bankroll point per scored fight with odds, including the no-bet fight
    assert [p.bankroll for p in payload.bankroll] == [payload.betting.final, payload.betting.final]
    assert payload.bankroll[1].event == "ufc-1"


def test_market_and_flat_sections(payload):
    names = [r.name for r in payload.market.rows]
    assert names == ["De-vigged market", "Model (ensemble)", "Blend · 0.8 model + 0.2 market"]
    assert all(r.accuracy == 1.0 for r in payload.market.rows)
    assert payload.market.agree == esd.Agreement(n=2, hit=1.0)
    assert payload.market.disagree == esd.Disagreement(n=0, model_hit=None)
    # $10 on the favorite: A at -150 (+6.667), D at -240 (+4.167) -> 10.833 / 20 staked
    assert payload.flat.market_favorite_per_bet == pytest.approx(10.8333 / 20, abs=1e-3)
    assert payload.flat.model_pick_per_bet == pytest.approx(10.8333 / 20, abs=1e-3)
    assert payload.flat.stake == 10.0


def test_main_writes_json_and_empty_ledger(fixture_dir, tmp_path):
    cache, odds = fixture_dir
    out = tmp_path / "site" / "backtest.json"
    ledger_out = tmp_path / "site" / "ledger.json"
    rc = esd.main(["--cache", cache, "--odds", odds, "--start", "2025-01-01", "--end", "2025-12-31",
                   "--out", str(out), "--ledger", str(tmp_path / "missing.json"),
                   "--ledger-out", str(ledger_out)])
    assert rc == 0
    import json
    data = json.load(open(out))
    assert data["metrics"]["n"] == 3
    assert data["bets"][0]["fighter"] == "A"
    assert json.load(open(ledger_out)) == []
