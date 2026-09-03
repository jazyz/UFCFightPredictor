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
    ("ufc-fight-night-february-01-2025", "Feb 01 2025", "G", "H", "Gee Aitch", "-110", "-110"),
    ("ufc-2", "Mar 01 2025", "A", "B", "draw/no contest", "-150", "+130"),
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
    assert payload.coverage == esd.Coverage(fights_in_window=5, scored=3, with_odds=2)
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
    assert len(payload.bets) == 2
    assert [b.result for b in payload.bets] == ["win", "push"]
    bet = payload.bets[0]
    expected = betting_math.decide_bet(0.71, None, -150, 130, blend_w=0.8, min_edge=0.05,
                                       fraction=0.05, cap=0.05, bankroll=1000.0)
    assert (bet.fighter, bet.opponent, bet.odds, bet.result, bet.source) == ("A", "B", -150, "win", "backtest")
    assert bet.stake == pytest.approx(expected["stake"], abs=0.005)
    assert bet.pnl == pytest.approx(expected["stake"] * 100 / 150, abs=0.005)
    assert bet.model_prob == pytest.approx(expected["prob"], abs=1e-4)
    assert bet.market_prob == pytest.approx(expected["market_prob"], abs=1e-4)
    assert payload.betting.final == pytest.approx(1000 + expected["stake"] * 100 / 150, abs=0.005)
    assert payload.betting.bets == 2 and payload.betting.hit == 0.5
    assert payload.betting.favorites == esd.SideRecord(won=1, total=2)
    assert payload.betting.underdogs == esd.SideRecord(won=0, total=0)
    assert payload.betting.max_drawdown_pct == 0.0
    assert payload.betting.low == 1000.0
    # one bankroll point per scored fight with odds, including the no-bet fight
    assert [p.bankroll for p in payload.bankroll] == [payload.betting.final] * 3
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


def test_fight_rows_carry_every_odds_row_with_window_independent_bets(fixture_dir):
    cache, odds = fixture_dir
    site = esd.build_site_payload(esd.load_caches(cache), odds, "2025-01-01", "2025-12-31")
    rows = {(r.f1, r.f2, r.date): r for r in site.fights}
    assert len(site.fights) == 5
    ab = rows[("A", "B", "2025-01-04")]
    assert ab.winner == "f1" and ab.model_p1 == pytest.approx(0.71) and ab.market_p1 is not None
    expected = betting_math.decide_bet(0.71, None, -150, 130, blend_w=0.8, min_edge=0.05,
                                       fraction=0.05, cap=0.05, bankroll=1000.0)
    assert ab.bet.side == 1 and ab.bet.odds == -150
    assert ab.bet.stake_frac * 1000.0 == pytest.approx(expected["stake"], abs=1e-9)
    assert ab.bet.payout_mult == pytest.approx(100 / 150)
    cd = rows[("C", "D", "2025-01-04")]
    assert cd.winner == "f2" and cd.bet is None
    ef = rows[("E", "F", "2025-02-01")]
    assert ef.market_p1 is None and ef.odds1 is None and ef.bet is None
    gh = rows[("G", "H", "2025-02-01")]
    assert gh.model_p1 is None and gh.winner == "unknown" and gh.bet is None
    push = rows[("A", "B", "2025-03-01")]
    assert push.winner == "push" and push.bet is not None


def test_site_payload_summary_config_and_range(fixture_dir):
    cache, odds = fixture_dir
    caches = esd.load_caches(cache)
    site = esd.build_site_payload(caches, odds, "2025-01-01", "2025-12-31")
    v1 = esd.build_payload(caches, odds, "2025-01-01", "2025-12-31")
    assert site.summary.betting == v1.betting and site.summary.metrics == v1.metrics
    assert site.summary.bets == v1.bets and site.summary.bankroll == v1.bankroll
    assert site.range == esd.Range(start="2025-01-01", end="2025-12-31", retrains=["2025-01-01"])
    assert site.default_window == esd.DefaultWindow(start="2025-01-01", end="2025-12-31")
    import inspect
    defaults = {k: p.default for k, p in inspect.signature(betting_math.decide_bet).parameters.items()
                if p.default is not inspect.Parameter.empty}
    assert site.config == esd.Config(blend_w=defaults["blend_w"], min_edge=defaults["min_edge"],
                                     kelly_fraction=defaults["fraction"], kelly_cap=defaults["cap"],
                                     max_dog_odds=defaults["max_dog_odds"], start_bankroll=1000.0,
                                     flat_stake=10.0)


def test_scored_row_with_unknown_winner_is_rejected(fixture_dir, tmp_path):
    cache, _ = fixture_dir
    bad = tmp_path / "bad.csv"
    with open(bad, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["event_name", "event_date", "fighter1_name", "fighter2_name",
                    "winner_name", "fighter1_odds", "fighter2_odds"])
        w.writerow(("ufc-1", "Jan 04 2025", "A", "B", "Ay Bee", "-150", "+130"))
    with pytest.raises(SystemExit):
        esd.build_site_payload(esd.load_caches(cache), str(bad), "2025-01-01", "2025-12-31")


def test_main_writes_v2_json(fixture_dir, tmp_path):
    cache, odds = fixture_dir
    out = tmp_path / "site" / "backtest.json"
    rc = esd.main(["--cache", cache, "--odds", odds, "--start", "2025-01-01", "--end", "2025-12-31",
                   "--out", str(out), "--ledger", str(tmp_path / "missing.json"),
                   "--ledger-out", str(tmp_path / "site" / "ledger.json")])
    assert rc == 0
    import json
    data = json.load(open(out))
    assert set(data) == {"generated", "range", "config", "default_window", "summary", "fights"}
    assert data["summary"]["metrics"]["n"] == 3 and len(data["fights"]) == 5
    assert data["config"]["max_dog_odds"] == 200
    assert json.load(open(tmp_path / "site" / "ledger.json")) == []


CACHE = os.path.join(ROOT, "test_results", ".tier2_full_cache")


@pytest.mark.skipif(not os.path.isdir(CACHE), reason="walk-forward cache not present (gitignored)")
def test_export_matches_testing_time_period_to_the_cent(tmp_path, monkeypatch):
    """The export must stake exactly what the reference backtest stakes.

    process_dates writes relative to the cwd (test_results/*.txt, data/*.png,
    data/predicted_results.csv), so run it inside a sandbox that holds a copy of
    the odds file, with train_ml replaced by a copy from the cache."""
    import shutil
    (tmp_path / "data").mkdir()
    (tmp_path / "test_results").mkdir()
    odds = os.path.join(ROOT, "data", "fight_results_with_odds.csv")
    shutil.copy(odds, tmp_path / "data" / "fight_results_with_odds.csv")
    monkeypatch.chdir(tmp_path)
    import testing_time_period as ttp

    def train_from_cache(date):
        shutil.copy(os.path.join(CACHE, f"pred_{date}.csv"), "data/predicted_results.csv")

    monkeypatch.setattr(ttp, "train_ml", train_from_cache)
    ttp.process_dates(esd.DEFAULT_START, esd.DEFAULT_END, [0.05, 0.05, 0, 0.05, 0.8])

    payload = esd.build_payload(esd.load_caches(CACHE), "data/fight_results_with_odds.csv",
                                esd.DEFAULT_START, esd.DEFAULT_END)
    assert payload.betting.final == pytest.approx(ttp.bankroll, abs=0.005)
    assert payload.betting.bets == ttp.favourites + ttp.underdogs
    assert payload.betting.favorites.total == ttp.favourites
    assert payload.betting.underdogs.total == ttp.underdogs
    assert payload.betting.favorites.won == ttp.favouritesHit
    assert payload.betting.underdogs.won == ttp.underdogsHit
    assert len(payload.bankroll) == len(ttp.bankrolls)
