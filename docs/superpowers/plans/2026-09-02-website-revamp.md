# Website Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stale internal-tool frontend with a public UFC Alpha results site that shows regenerated backtest numbers, a graded bet ledger, and methodology, and funnels visitors to an external membership link for upcoming picks.

**Architecture:** A Python export script replays the odds file over the deployed walk-forward prediction cache and writes one JSON payload the React app bundles at build time. A small `bet_ledger.py` records live picks from `predict_event.py` and grades them from scraped results inside `auto_retrain.py`. The CRA + Tailwind frontend is rewritten as five static pages that read the bundled JSON; no public page calls the Flask API.

**Tech Stack:** Python 3.9 (stdlib dataclasses, scikit-learn metrics, pytest), React 18 / CRA 5 / react-router 6 / Tailwind 3, recharts 2.15.

**Spec:** `docs/superpowers/specs/2026-09-02-website-revamp-design.md`

## Global Constraints

- Python runtime is 3.9.6 in `.venv`; run Python as `.venv/bin/python` and tests as `.venv/bin/python -m pytest`. No new Python dependencies (pydantic is not installed; use `dataclasses`).
- Production betting config is copied verbatim from `predict_event.py`: `BLEND_W = 0.8`, `MIN_EDGE = 0.05`, `KELLY_FRACTION = 0.05`, `KELLY_MAX = 0.05`, `dog_multiplier = 1.0`, `$1,000` paper bankroll.
- Default export inputs: cache `test_results/.lastyear_tier0_cache`, window `2025-08-30` → `2026-08-30`, odds file `data/fight_results_with_odds.csv`.
- Brand is "UFC Alpha". Membership link is the single constant `MEMBERSHIP_URL` in `frontend/src/constants.js`.
- One new npm dependency only: `recharts@^2.15.4`. Do not remove existing npm dependencies.
- Do not modify `app.py`, model training, feature engineering, or scrapers. Do not delete `FightersPage.js` or `FightersDropdown.js`.
- Frontend build must pass `CI=true npm run build` (warnings are errors). Run npm commands from `frontend/`.
- Claims policy: ROI never appears without its bet count and max drawdown beside it; every bankroll figure is labeled as a $1,000 paper bankroll at closing odds; no forward-looking return claims. All numbers in copy are interpolated from `backtest.json`.
- Design tokens (Tailwind): `ground #0b0b0c`, `surface #151517`, `ink #f4f3ef`, `ink-2 #b8b6ae`, `muted #7c7a72`, `hairline rgba(255,255,255,0.10)`, `accent #e8362b`, `up #3ccb7f`, `down #ef6b62`; fonts `display` = Barlow Condensed, `body` = Barlow.
- Chart rules (from the dataviz skill): bars ≤ 24px thick with 4px rounded tops, 2px lines, solid hairline grid, legend only when ≥ 2 series, every chart has a "View as table" twin, text never wears the series color, stat-tile values in the body sans with proportional figures.
- Commit after every task on branch `website-revamp`. Commit messages end with:

  ```
  Assisted by AI

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

- Do not push. Do not open a PR. Alex owns those steps.

---

## File map

**Python (repo root and `testing/`)**
- Create `testing/export_site_data.py` — replay + metrics + JSON export; owns the payload dataclasses.
- Create `bet_ledger.py` — `LedgerEntry`, `record()`, `grade()`.
- Modify `predict_event.py` — `write_outputs` records picks; `main` resolves the event date.
- Modify `auto_retrain.py` — `step_grade_ledger()` after `step_process()`.
- Create `tests/test_export_site_data.py`, `tests/test_bet_ledger.py`, `tests/test_predict_event_ledger.py`, `tests/test_auto_retrain_ledger.py`.

**Frontend (`frontend/`)**
- Modify `package.json` (recharts), `tailwind.config.js`, `public/index.html`, `public/manifest.json`, `src/index.css`, `src/setupTests.js`, `src/App.js`, `src/App.test.js`, `src/constants.js`.
- Create `src/format.js`, `src/data/backtest.json`, `src/data/ledger.json`, `src/test/fixtures.js`.
- Create `src/components/Navbar.js` (rewrite), `Footer.js`, `StatTile.js`, `ScrollToTop.js`, `Home.js` (rewrite), `Results.js`, `Bets.js` (rewrite), `Methodology.js`, `Join.js`, `charts/chartTheme.js`, `charts/CalibrationChart.js`, `charts/MonthlyAccuracyChart.js`, `charts/BankrollChart.js`.
- Delete `src/components/FightPredictor.js`, `Testing.js`, `About.js`, `src/constants/about.md`, `src/constants/predictions.txt`, `src/constants/README.md`, `src/assets/2021_to_2024.png`, `src/App.css`.

**Docs**
- Modify `CLAUDE.md` — commands, frontend structure, data files, retrain steps.

---

### Task 1: Export script with synthetic-fixture tests

**Files:**
- Create: `testing/export_site_data.py`
- Test: `tests/test_export_site_data.py`

**Interfaces:**
- Consumes: `betting_math.decide_bet`, `betting_math.devig`, `betting_math.american_to_prob`, `betting_math.blend_prob` (repo root, already exist).
- Produces: `load_caches(cache_dir) -> dict[str, dict[tuple[str,str], float]]`, `build_payload(caches, odds_csv, start, end) -> BacktestPayload`, `main(argv=None) -> int`, and the dataclasses `Window, Coverage, Metrics, Band, MonthRow, MarketRow, Agreement, Disagreement, MarketSection, FlatSection, SideRecord, BettingSummary, BankrollPoint, BetRecord, BacktestPayload`. Task 4 runs `main`; Task 7-9 read the JSON these produce.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_site_data.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_export_site_data.py -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'export_site_data'`.

- [ ] **Step 3: Write the export script**

Create `testing/export_site_data.py`:

```python
"""Export the public site's data file from a walk-forward prediction cache.

Replays data/fight_results_with_odds.csv over the per-retrain predictions that
testing_time_period.find_fights cached, scores every fight the model covered,
and sizes bets through betting_math.decide_bet at the production config.
Writes frontend/src/data/backtest.json and copies the live ledger to
frontend/src/data/ledger.json.

    python testing/export_site_data.py                       # defaults below
    python testing/export_site_data.py --cache DIR --start YYYY-MM-DD --end YYYY-MM-DD
"""
import argparse
import csv
import glob
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import betting_math  # noqa: E402

# Production betting config, copied from predict_event.py.
BLEND_W = 0.8
MIN_EDGE = 0.05
KELLY_FRACTION = 0.05
KELLY_MAX = 0.05
START_BANKROLL = 1000.0
FLAT_STAKE = 10.0
BANDS = [("50–55%", 0.50, 0.55), ("55–60%", 0.55, 0.60), ("60–65%", 0.60, 0.65),
         ("65–70%", 0.65, 0.70), ("70%+", 0.70, 1.01)]

DEFAULT_CACHE = os.path.join(ROOT, "test_results", ".lastyear_tier0_cache")
DEFAULT_ODDS = os.path.join(ROOT, "data", "fight_results_with_odds.csv")
DEFAULT_OUT = os.path.join(ROOT, "frontend", "src", "data", "backtest.json")
DEFAULT_LEDGER = os.path.join(ROOT, "data", "bet_ledger.json")
DEFAULT_LEDGER_OUT = os.path.join(ROOT, "frontend", "src", "data", "ledger.json")
DEFAULT_START = "2025-08-30"
DEFAULT_END = "2026-08-30"


# ----------------------------------------------------------------- payload types

@dataclass
class Window:
    start: str
    end: str
    retrains: List[str]


@dataclass
class Coverage:
    fights_in_window: int
    scored: int
    with_odds: int


@dataclass
class Metrics:
    accuracy: float
    auc: float
    log_loss: float
    brier: float
    n: int


@dataclass
class Band:
    label: str
    lo: float
    hi: float
    n: int
    stated: Optional[float]
    hit: Optional[float]


@dataclass
class MonthRow:
    month: str
    n: int
    hit: float


@dataclass
class MarketRow:
    name: str
    accuracy: float
    auc: float
    log_loss: float
    brier: float


@dataclass
class Agreement:
    n: int
    hit: Optional[float]


@dataclass
class Disagreement:
    n: int
    model_hit: Optional[float]


@dataclass
class MarketSection:
    rows: List[MarketRow]
    agree: Agreement
    disagree: Disagreement


@dataclass
class FlatSection:
    market_favorite_per_bet: float
    model_pick_per_bet: float
    stake: float


@dataclass
class SideRecord:
    won: int
    total: int


@dataclass
class BettingSummary:
    final: float
    return_pct: float
    bets: int
    hit: Optional[float]
    favorites: SideRecord
    underdogs: SideRecord
    max_drawdown_pct: float
    low: float


@dataclass
class BankrollPoint:
    date: str
    event: str
    bankroll: float


@dataclass
class BetRecord:
    date: str
    event: str
    fighter: str
    opponent: str
    odds: int
    model_prob: float
    market_prob: float
    edge: float
    stake: float
    result: str
    pnl: float
    bankroll_after: float
    source: str = "backtest"


@dataclass
class BacktestPayload:
    generated: str
    window: Window
    coverage: Coverage
    metrics: Metrics
    bands: List[Band]
    monthly: List[MonthRow]
    market: MarketSection
    flat: FlatSection
    betting: BettingSummary
    bankroll: List[BankrollPoint]
    bets: List[BetRecord]


@dataclass
class Scored:
    """One fight the model covered, in the form every section needs."""
    date: str            # YYYY-MM-DD
    month: str           # YYYY-MM
    event: str
    f1: str
    f2: str
    winner: str          # f1, f2, or "draw/no contest"
    model_p1: float      # two-orientation average P(f1 wins)
    odds1: Optional[int]
    odds2: Optional[int]
    market_p1: Optional[float]   # de-vigged P(f1 wins); None without odds


# ------------------------------------------------------------------- inputs

def load_caches(cache_dir: str) -> Dict[str, Dict[Tuple[str, str], float]]:
    """{'YYYY-MM-DD': {(red, blue): P(red wins)}} for every pred_*.csv in the dir."""
    caches = {}
    for path in sorted(glob.glob(os.path.join(cache_dir, "pred_*.csv"))):
        date = os.path.basename(path)[len("pred_"):-len(".csv")]
        table = {}
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                p = float(row["Probability"])
                if row["Predicted Result"] != "win":
                    p = 1 - p
                table[(row["Red Fighter"], row["Blue Fighter"])] = p
        caches[date] = table
    if not caches:
        raise SystemExit(f"no pred_*.csv files in {cache_dir}")
    return caches


def cache_for(caches, date_iso: str):
    """The latest cache trained on or before this fight date (find_fights' retrain rule)."""
    eligible = [d for d in caches if d <= date_iso]
    if not eligible:
        raise ValueError(f"no cache trained on or before {date_iso}")
    return caches[max(eligible)]


def read_window(odds_csv: str, start: datetime, end: datetime) -> List[dict]:
    rows = []
    with open(odds_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            date = datetime.strptime(row["event_date"], "%b %d %Y")
            if start <= date <= end:
                rows.append(row)
    return rows


def parse_odds(text: str) -> Optional[int]:
    text = text.replace("−", "-")
    return None if text == "-" else int(text)


def score_fights(rows: List[dict], caches) -> List[Scored]:
    scored = []
    for row in rows:
        iso = datetime.strptime(row["event_date"], "%b %d %Y").strftime("%Y-%m-%d")
        table = cache_for(caches, iso)
        f1, f2 = row["fighter1_name"], row["fighter2_name"]
        p_ab, p_ba = table.get((f1, f2)), table.get((f2, f1))
        if p_ab is None or p_ba is None:
            continue
        odds1, odds2 = parse_odds(row["fighter1_odds"]), parse_odds(row["fighter2_odds"])
        market_p1 = None
        if odds1 is not None and odds2 is not None:
            market_p1, _ = betting_math.devig(betting_math.american_to_prob(odds1),
                                              betting_math.american_to_prob(odds2))
        scored.append(Scored(date=iso, month=iso[:7], event=row["event_name"], f1=f1, f2=f2,
                             winner=row["winner_name"], model_p1=(p_ab + (1 - p_ba)) / 2,
                             odds1=odds1, odds2=odds2, market_p1=market_p1))
    return scored


# ------------------------------------------------------------------ sections

def decided(fights: List[Scored]) -> List[Scored]:
    return [s for s in fights if s.winner in (s.f1, s.f2)]


def pick_hit(s: Scored) -> Tuple[float, bool]:
    """(stated confidence of the model's pick, whether the pick won)."""
    if s.model_p1 >= 0.5:
        return s.model_p1, s.winner == s.f1
    return 1 - s.model_p1, s.winner == s.f2


def _metrics(ps: List[float], ys: List[int]) -> Tuple[float, float, float, float]:
    """accuracy, AUC, log loss, Brier for P(fighter 1 wins) against 1/0 outcomes."""
    clipped = [min(max(p, 1e-6), 1 - 1e-6) for p in ps]
    acc = sum((p >= 0.5) == (y == 1) for p, y in zip(ps, ys)) / len(ps)
    auc = roc_auc_score(ys, ps) if len(set(ys)) > 1 else float("nan")
    return (acc, float(auc), float(log_loss(ys, clipped, labels=[0, 1])),
            float(brier_score_loss(ys, clipped)))


def prediction_metrics(fights: List[Scored]) -> Metrics:
    ps = [s.model_p1 for s in fights]
    ys = [1 if s.winner == s.f1 else 0 for s in fights]
    acc, auc, ll, br = _metrics(ps, ys)
    return Metrics(accuracy=round(acc, 4), auc=round(auc, 4), log_loss=round(ll, 4),
                   brier=round(br, 4), n=len(fights))


def calibration_bands(fights: List[Scored]) -> List[Band]:
    out = []
    for label, lo, hi in BANDS:
        rows = [pick_hit(s) for s in fights if lo <= pick_hit(s)[0] < hi]
        n = len(rows)
        out.append(Band(label=label, lo=lo, hi=min(hi, 1.0), n=n,
                        stated=round(sum(c for c, _ in rows) / n, 4) if n else None,
                        hit=round(sum(h for _, h in rows) / n, 4) if n else None))
    return out


def monthly_accuracy(fights: List[Scored]) -> List[MonthRow]:
    by_month: Dict[str, List[bool]] = {}
    for s in fights:
        by_month.setdefault(s.month, []).append(pick_hit(s)[1])
    return [MonthRow(month=m, n=len(h), hit=round(sum(h) / len(h), 4))
            for m, h in sorted(by_month.items())]


def market_section(fights: List[Scored]) -> MarketSection:
    """fights: decided AND priced."""
    ys = [1 if s.winner == s.f1 else 0 for s in fights]
    rows = []
    series = [
        ("De-vigged market", [s.market_p1 for s in fights]),
        ("Model (ensemble)", [s.model_p1 for s in fights]),
        (f"Blend · {BLEND_W:g} model + {1 - BLEND_W:g} market",
         [betting_math.blend_prob(s.model_p1, s.market_p1, BLEND_W) for s in fights]),
    ]
    for name, ps in series:
        acc, auc, ll, br = _metrics(ps, ys)
        rows.append(MarketRow(name=name, accuracy=round(acc, 4), auc=round(auc, 4),
                              log_loss=round(ll, 4), brier=round(br, 4)))
    agree = [s for s in fights if (s.model_p1 >= 0.5) == (s.market_p1 >= 0.5)]
    disagree = [s for s in fights if (s.model_p1 >= 0.5) != (s.market_p1 >= 0.5)]

    def hit_rate(group):
        return round(sum(pick_hit(s)[1] for s in group) / len(group), 4) if group else None

    return MarketSection(rows=rows, agree=Agreement(n=len(agree), hit=hit_rate(agree)),
                         disagree=Disagreement(n=len(disagree), model_hit=hit_rate(disagree)))


def payout(odds: int, stake: float) -> float:
    """Profit on a winning stake at an American price."""
    return stake * (100 / -odds) if odds < 0 else stake * (odds / 100)


def settle(winner: str, name: str, odds: int, stake: float) -> Tuple[str, float]:
    if winner == name:
        return "win", payout(odds, stake)
    if winner == "draw/no contest":
        return "push", 0.0
    return "loss", -stake


def flat_section(fights: List[Scored]) -> FlatSection:
    """Return per $1 staked at a flat FLAT_STAKE on every decided, priced fight."""
    def per_bet(choose):
        total = sum(settle(s.winner, *choose(s), FLAT_STAKE)[1] for s in fights)
        return round(total / (FLAT_STAKE * len(fights)), 4) if fights else 0.0

    favorite = per_bet(lambda s: (s.f1, s.odds1) if s.market_p1 >= 0.5 else (s.f2, s.odds2))
    model = per_bet(lambda s: (s.f1, s.odds1) if s.model_p1 >= 0.5 else (s.f2, s.odds2))
    return FlatSection(market_favorite_per_bet=favorite, model_pick_per_bet=model, stake=FLAT_STAKE)


def max_drawdown(series: List[float]) -> float:
    peak, worst = series[0], 0.0
    for x in series:
        peak = max(peak, x)
        worst = max(worst, (peak - x) / peak if peak else 0.0)
    return worst


def replay_bets(fights: List[Scored]) -> Tuple[BettingSummary, List[BankrollPoint], List[BetRecord]]:
    """Compound a $1,000 bankroll over every priced fight in file order (pushes included,
    exactly as testing_time_period.process_fight does). Bankroll math stays unrounded."""
    bankroll = START_BANKROLL
    points: List[BankrollPoint] = []
    bets: List[BetRecord] = []
    won = {"fav": 0, "dog": 0}
    total = {"fav": 0, "dog": 0}
    for s in fights:
        bet = betting_math.decide_bet(s.model_p1, None, s.odds1, s.odds2, blend_w=BLEND_W,
                                      min_edge=MIN_EDGE, fraction=KELLY_FRACTION, cap=KELLY_MAX,
                                      bankroll=bankroll)
        if bet is not None:
            name, opponent, odds = ((s.f1, s.f2, s.odds1) if bet["name_index"] == 0
                                    else (s.f2, s.f1, s.odds2))
            result, pnl = settle(s.winner, name, odds, bet["stake"])
            bankroll += pnl
            side = "fav" if odds < 0 else "dog"
            total[side] += 1
            won[side] += result == "win"
            bets.append(BetRecord(date=s.date, event=s.event, fighter=name, opponent=opponent,
                                  odds=odds, model_prob=round(bet["prob"], 4),
                                  market_prob=round(bet["market_prob"], 4),
                                  edge=round(bet["edge"], 4), stake=round(bet["stake"], 2),
                                  result=result, pnl=round(pnl, 2),
                                  bankroll_after=round(bankroll, 2)))
        points.append(BankrollPoint(date=s.date, event=s.event, bankroll=round(bankroll, 2)))
    series = [START_BANKROLL] + [p.bankroll for p in points]
    n_bets = total["fav"] + total["dog"]
    n_won = won["fav"] + won["dog"]
    summary = BettingSummary(
        final=round(bankroll, 2),
        return_pct=round((bankroll - START_BANKROLL) / START_BANKROLL * 100, 1),
        bets=n_bets, hit=round(n_won / n_bets, 4) if n_bets else None,
        favorites=SideRecord(won=won["fav"], total=total["fav"]),
        underdogs=SideRecord(won=won["dog"], total=total["dog"]),
        max_drawdown_pct=round(max_drawdown(series) * 100, 1), low=round(min(series), 2))
    return summary, points, bets


def build_payload(caches, odds_csv: str, start: str, end: str) -> BacktestPayload:
    rows = read_window(odds_csv, datetime.strptime(start, "%Y-%m-%d"),
                       datetime.strptime(end, "%Y-%m-%d"))
    scored = score_fights(rows, caches)
    dec = decided(scored)
    priced = [s for s in scored if s.market_p1 is not None]
    dec_priced = [s for s in dec if s.market_p1 is not None]
    summary, points, bets = replay_bets(priced)
    return BacktestPayload(
        generated=datetime.now().isoformat(timespec="seconds"),
        window=Window(start=start, end=end, retrains=sorted(d for d in caches if start <= d <= end)),
        coverage=Coverage(fights_in_window=len(rows), scored=len(dec), with_odds=len(dec_priced)),
        metrics=prediction_metrics(dec),
        bands=calibration_bands(dec),
        monthly=monthly_accuracy(dec),
        market=market_section(dec_priced),
        flat=flat_section(dec_priced),
        betting=summary, bankroll=points, bets=bets)


# ---------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=DEFAULT_CACHE, help="dir of pred_YYYY-MM-DD.csv files")
    ap.add_argument("--odds", default=DEFAULT_ODDS)
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--ledger-out", default=DEFAULT_LEDGER_OUT)
    args = ap.parse_args(argv)

    payload = build_payload(load_caches(args.cache), args.odds, args.start, args.end)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(asdict(payload), fh, indent=1)
    os.makedirs(os.path.dirname(args.ledger_out), exist_ok=True)
    if os.path.exists(args.ledger):
        shutil.copy(args.ledger, args.ledger_out)
    else:
        with open(args.ledger_out, "w") as fh:
            fh.write("[]\n")

    m, b = payload.metrics, payload.betting
    print(f"{m.n} fights scored · accuracy {m.accuracy:.1%} · AUC {m.auc:.3f} · "
          f"log loss {m.log_loss:.3f} · Brier {m.brier:.3f}")
    print(f"{b.bets} bets · hit {(b.hit or 0):.1%} · final ${b.final:,.2f} ({b.return_pct:+.1f}%) · "
          f"max drawdown {b.max_drawdown_pct:.1f}%")
    print(f"wrote {os.path.relpath(args.out, ROOT)} and {os.path.relpath(args.ledger_out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_export_site_data.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add testing/export_site_data.py tests/test_export_site_data.py
git commit -m "Add the site data export that replays the walk-forward cache

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Golden test against testing_time_period

**Files:**
- Test: `tests/test_export_site_data.py` (append)

**Interfaces:**
- Consumes: `export_site_data.load_caches`, `export_site_data.build_payload` (Task 1); `testing/testing_time_period.process_dates`, `.train_ml`, `.bankroll`, `.favourites`, `.underdogs` (existing).

- [ ] **Step 1: Append the golden test**

Append to `tests/test_export_site_data.py`:

```python
CACHE = os.path.join(ROOT, "test_results", ".lastyear_tier0_cache")


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
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/test_export_site_data.py::test_export_matches_testing_time_period_to_the_cent -v`
Expected: PASS. If it fails on `final`, the cache-selection rule in `cache_for` differs from `find_fights`; compare the retrain dates `train_from_cache` received against the cache filenames before changing anything else.

- [ ] **Step 3: Confirm the repo is clean**

Run: `git status --short data test_results`
Expected: no modified tracked files (the sandbox absorbed every side effect).

- [ ] **Step 4: Commit**

```bash
git add tests/test_export_site_data.py
git commit -m "Pin the site export to the reference backtest with a golden test

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: bet_ledger.py

**Files:**
- Create: `bet_ledger.py`
- Test: `tests/test_bet_ledger.py`

**Interfaces:**
- Produces: `LedgerEntry` dataclass; `load(path=LEDGER_PATH) -> list[LedgerEntry]`; `save(entries, path=LEDGER_PATH)`; `record(event: str, event_date: str, generated: str, bets: list[dict], path=LEDGER_PATH) -> int`; `grade(results_csv=RESULTS_CSV, path=LEDGER_PATH, now=None) -> int`; `payout_per_unit(odds: int) -> float`. `bets` dicts carry the keys `predict_event.recommend` emits: `fighter, opponent, odds, model_prob, implied_prob, edge, kelly, stake_pct`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bet_ledger.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_bet_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bet_ledger'`.

- [ ] **Step 3: Write the module**

Create `bet_ledger.py` at the repo root:

```python
"""Public bet ledger: record live picks, grade them once results land.

predict_event.py appends the picks it recommends; auto_retrain.py grades the
pending ones after each scrape. data/bet_ledger.json is a JSON list of
LedgerEntry dicts, and testing/export_site_data.py copies it into the site.
"""
import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER_PATH = os.path.join(ROOT, "data", "bet_ledger.json")
RESULTS_CSV = os.path.join(ROOT, "data", "fight_details_date.csv")
MATCH_WINDOW = timedelta(days=3)   # scraped Date may differ from the card date by a day or two


@dataclass
class LedgerEntry:
    event: str
    event_date: str            # YYYY-MM-DD
    generated: str             # ISO timestamp of the prediction run
    fighter: str
    opponent: str
    odds: int                  # American price at recommendation time
    model_prob: float          # blended betting probability
    market_prob: float         # de-vigged market probability
    edge: float
    kelly: float
    stake_pct: float           # percent of bankroll
    result: str = "pending"    # pending | win | loss | push
    pnl_per_unit: Optional[float] = None   # profit per $1 staked
    graded: Optional[str] = None           # ISO timestamp when settled


def load(path: str = LEDGER_PATH) -> List[LedgerEntry]:
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [LedgerEntry(**row) for row in json.load(fh)]


def save(entries: List[LedgerEntry], path: str = LEDGER_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump([asdict(e) for e in entries], fh, indent=1)
    os.replace(tmp, path)


def record(event: str, event_date: str, generated: str, bets: List[dict],
           path: str = LEDGER_PATH) -> int:
    """Append one pending entry per pick; (event, fighter) pairs already present are skipped."""
    entries = load(path)
    seen = {(e.event, e.fighter) for e in entries}
    added = 0
    for b in bets:
        if (event, b["fighter"]) in seen:
            continue
        entries.append(LedgerEntry(event=event, event_date=event_date, generated=generated,
                                   fighter=b["fighter"], opponent=b["opponent"], odds=int(b["odds"]),
                                   model_prob=b["model_prob"], market_prob=b["implied_prob"],
                                   edge=b["edge"], kelly=b["kelly"], stake_pct=b["stake_pct"]))
        seen.add((event, b["fighter"]))
        added += 1
    if added:
        save(entries, path)
    return added


def payout_per_unit(odds: int) -> float:
    """Profit on a $1 winning stake at an American price."""
    return 100 / -odds if odds < 0 else odds / 100


def _outcome(row: dict, entry: LedgerEntry):
    if row["Draw"] == "True" or not row["Winner"]:
        return "push", 0.0
    if row["Winner"] == entry.fighter:
        return "win", round(payout_per_unit(entry.odds), 4)
    return "loss", -1.0


def grade(results_csv: str = RESULTS_CSV, path: str = LEDGER_PATH, now=None) -> int:
    """Settle pending entries from scraped results. Returns how many were graded."""
    entries = load(path)
    pending = [e for e in entries if e.result == "pending"]
    if not pending:
        return 0
    with open(results_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    graded = 0
    for entry in pending:
        when = datetime.strptime(entry.event_date, "%Y-%m-%d")
        for row in rows:
            if {row["Red Fighter"], row["Blue Fighter"]} != {entry.fighter, entry.opponent}:
                continue
            if abs(datetime.strptime(row["Date"], "%B %d, %Y") - when) > MATCH_WINDOW:
                continue
            entry.result, entry.pnl_per_unit = _outcome(row, entry)
            entry.graded = stamp
            graded += 1
            break
    if graded:
        save(entries, path)
    return graded
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bet_ledger.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add bet_ledger.py tests/test_bet_ledger.py
git commit -m "Add bet_ledger: record live picks and grade them from scraped results

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Hook the ledger into predict_event.py and auto_retrain.py

**Files:**
- Modify: `predict_event.py:47-49` (imports), `predict_event.py:301-315` (`write_outputs`), `predict_event.py:340-369` (`main`)
- Modify: `auto_retrain.py:88-92` (after `step_process`), `auto_retrain.py:224-225` (call site in `main`)
- Test: `tests/test_predict_event_ledger.py`, `tests/test_auto_retrain_ledger.py`

**Interfaces:**
- Consumes: `bet_ledger.record`, `bet_ledger.grade` (Task 3).
- Produces: `predict_event.write_outputs(rows, event, bets, event_date)` (new 4th positional arg); `auto_retrain.step_grade_ledger() -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_predict_event_ledger.py`:

```python
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
```

Create `tests/test_auto_retrain_ledger.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_predict_event_ledger.py tests/test_auto_retrain_ledger.py -v`
Expected: FAIL. The predict_event tests fail with `TypeError: write_outputs() takes 3 positional arguments but 4 were given`; the auto_retrain tests fail with `AttributeError: module 'auto_retrain' has no attribute 'step_grade_ledger'`.

- [ ] **Step 3: Modify predict_event.py**

After `import betting_math` (line 47) add:

```python
import bet_ledger
```

Replace `write_outputs` (lines 301-315) with:

```python
def write_outputs(rows, event, bets, event_date):
    predict_data = [{"Red Fighter": r, "Blue Fighter": b,
                     "Probability Win": p, "Probability Lose": 1 - p}
                    for r, b, p in rows]
    payload = {
        "predict_data": predict_data,
        "class_probabilities": {"Win": [p for _, _, p in rows],
                                "Lose": [1 - p for _, _, p in rows]},
        "event": event,
        "event_date": event_date,
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    if bets:
        payload["bets"] = bets
        bet_ledger.record(event, event_date, payload["generated"], bets)
    with open(PRED_JSON, "w") as fh:
        json.dump(payload, fh)
```

Keep the `BET_CSV` block that follows unchanged.

In `main`, replace the block

```python
    when = None
    if args.event:
        url = args.event
    else:
        events = upcoming_events(session)
        when, url, name = events[0]
        print(f"Next event: {name} — {when.date()}")
```

with

```python
    when = None
    if args.event:
        url = args.event
        try:
            when = next((w for w, u, _ in upcoming_events(session) if u == url), None)
        except ScrapeError:
            when = None
    else:
        events = upcoming_events(session)
        when, url, name = events[0]
        print(f"Next event: {name} — {when.date()}")
    event_date = (when or datetime.datetime.now()).strftime("%Y-%m-%d")
```

and change the call `write_outputs(rows, event_name, bets)` to `write_outputs(rows, event_name, bets, event_date)`.

- [ ] **Step 4: Modify auto_retrain.py**

After `step_process()` (ends line 92) add:

```python
def step_grade_ledger():
    """Settle public-ledger picks whose results just landed. Never fails the run."""
    banner("STEP 2b: GRADING THE BET LEDGER")
    try:
        import bet_ledger
        n = bet_ledger.grade()
        log.info(f"✓ Ledger graded: {n} entries settled")
    except Exception as exc:
        log.warning(f"Ledger grading skipped: {type(exc).__name__}: {exc}")
```

In `main`, change

```python
        step_process()
        step_features()
```

to

```python
        step_process()
        step_grade_ledger()
        step_features()
```

- [ ] **Step 5: Run the tests and the whole Python suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all pass (the leakage tests may skip if their data files are absent; that is fine).

- [ ] **Step 6: Commit**

```bash
git add predict_event.py auto_retrain.py tests/test_predict_event_ledger.py tests/test_auto_retrain_ledger.py
git commit -m "Record live picks in the bet ledger and grade them during retrains

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Generate the site data

**Files:**
- Create: `frontend/src/data/backtest.json`, `frontend/src/data/ledger.json` (generated)

**Interfaces:**
- Consumes: `testing/export_site_data.py` `main` (Task 1).
- Produces: the two JSON files every frontend task imports.

- [ ] **Step 1: Run the export with defaults**

Run from the repo root: `.venv/bin/python testing/export_site_data.py`
Expected: three summary lines and `wrote frontend/src/data/backtest.json and frontend/src/data/ledger.json`. Record the printed accuracy, AUC, bets, return and drawdown in the commit message body.

- [ ] **Step 2: Sanity-check the payload**

Run:

```bash
.venv/bin/python - <<'EOF'
import json
d = json.load(open("frontend/src/data/backtest.json"))
print(d["window"], d["coverage"])
print(d["metrics"])
for b in d["bands"]: print(b)
print(d["market"]["agree"], d["market"]["disagree"])
print(d["betting"])
print(len(d["bankroll"]), "bankroll points;", len(d["bets"]), "bets")
EOF
```

Expected: `retrains` lists exactly `2025-08-30`, `2026-02-28`, `2026-08-29`; `scored` is in the 270-290 range; bands have non-zero `n` for at least the 50-55 through 65-70 bands; `bets` is non-empty. If `scored` is far below 270, the cache dir is wrong.

- [ ] **Step 3: Commit the data**

```bash
git add frontend/src/data/backtest.json frontend/src/data/ledger.json
git commit -m "Generate the public site data from the tier-0 last-year cache

<paste the three summary lines the export printed>

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Frontend shell — theme, meta, constants, helpers, Navbar, Footer, App

**Files:**
- Modify: `frontend/package.json`, `frontend/tailwind.config.js`, `frontend/public/index.html`, `frontend/public/manifest.json`, `frontend/src/index.css`, `frontend/src/setupTests.js`, `frontend/src/constants.js`, `frontend/src/App.js`, `frontend/src/App.test.js`
- Create: `frontend/src/format.js`, `frontend/src/format.test.js`, `frontend/src/components/StatTile.js`, `frontend/src/components/ScrollToTop.js`, `frontend/src/components/Navbar.js` (rewrite), `frontend/src/components/Footer.js`, `frontend/src/test/fixtures.js`
- Delete: `frontend/src/components/FightPredictor.js`, `frontend/src/components/Testing.js`, `frontend/src/components/About.js`, `frontend/src/constants/about.md`, `frontend/src/constants/predictions.txt`, `frontend/src/constants/README.md`, `frontend/src/assets/2021_to_2024.png`, `frontend/src/App.css`

**Interfaces:**
- Produces: `format.js` exports `pct(x, digits=1)`, `money(x)`, `signedMoney(x)`, `signedPct(x, digits=1)` (x already in percent units), `odds(o)`, `eventName(slug)`, `shortDate(iso)`, `monthLabel(yyyymm)`, `stdErrPts(p, n)`; `StatTile({label, value, sub, tone})`; `Navbar()`, `Footer()`, `ScrollToTop()`; `constants.js` exports `baseURL, SITE_NAME, MEMBERSHIP_URL, GITHUB_URL, RESPONSIBLE_GAMBLING_URL`; `test/fixtures.js` exports `backtestFixture`, `ledgerFixture`. `App.js` renders placeholder routes that Tasks 8-11 replace.

- [ ] **Step 1: Install recharts**

Run from `frontend/`: `npm install recharts@^2.15.4`
Expected: `package.json` gains `"recharts": "^2.15.4"` under dependencies and `package-lock.json` updates.

- [ ] **Step 2: Write the failing format tests**

Create `frontend/src/format.test.js`:

```js
import { pct, money, signedMoney, signedPct, odds, eventName, shortDate, monthLabel, stdErrPts } from "./format";

test("pct formats fractions and dashes nulls", () => {
  expect(pct(0.6702)).toBe("67.0%");
  expect(pct(0.6702, 0)).toBe("67%");
  expect(pct(null)).toBe("—");
});

test("money and signed helpers", () => {
  expect(money(1132.93)).toBe("$1,132.93");
  expect(signedMoney(-8.5)).toBe("−$8.50");
  expect(signedMoney(12)).toBe("+$12.00");
  expect(signedPct(13.3)).toBe("+13.3%");
  expect(signedPct(-0.4)).toBe("−0.4%");
});

test("odds keeps the plus sign on dogs", () => {
  expect(odds(150)).toBe("+150");
  expect(odds(-210)).toBe("-210");
});

test("eventName turns ufcstats slugs into names", () => {
  expect(eventName("ufc-fight-night-september-06-2025")).toBe("UFC Fight Night");
  expect(eventName("ufc-320")).toBe("UFC 320");
  expect(eventName("ufc-on-espn-70")).toBe("UFC on ESPN 70");
  expect(eventName("start")).toBe("Start");
});

test("dates", () => {
  expect(shortDate("2025-09-06")).toBe("Sep 6, 2025");
  expect(monthLabel("2025-09")).toBe("Sep ’25");
});

test("stdErrPts is the binomial standard error in percentage points", () => {
  expect(stdErrPts(0.67, 282)).toBeCloseTo(2.8, 1);
});
```

- [ ] **Step 3: Run it to verify it fails**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/format.test.js`
Expected: FAIL, `Cannot find module './format'`.

- [ ] **Step 4: Write format.js**

Create `frontend/src/format.js`:

```js
const MONTHS = ["january", "february", "march", "april", "may", "june", "july",
  "august", "september", "october", "november", "december"];
const UPPER = { ufc: "UFC", espn: "ESPN", abc: "ABC", fox: "FOX" };

export const pct = (x, digits = 1) => (x == null ? "—" : `${(x * 100).toFixed(digits)}%`);

export const money = (x) =>
  x == null ? "—" : x.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const signedMoney = (x) => `${x < 0 ? "−" : "+"}${money(Math.abs(x))}`;

export const signedPct = (x, digits = 1) => `${x < 0 ? "−" : "+"}${Math.abs(x).toFixed(digits)}%`;

export const odds = (o) => (o > 0 ? `+${o}` : `${o}`);

export function eventName(slug) {
  const words = slug.split("-");
  const cut = words.findIndex((w) => MONTHS.includes(w));
  const kept = cut === -1 ? words : words.slice(0, cut);
  return kept
    .map((w) => UPPER[w] || (w === "on" ? "on" : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

export const shortDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export function monthLabel(yyyymm) {
  const [y, m] = yyyymm.split("-").map(Number);
  const name = new Date(y, m - 1, 1).toLocaleString("en-US", { month: "short" });
  return `${name} ’${String(y).slice(2)}`;
}

/** Binomial standard error of a hit rate, in percentage points. */
export const stdErrPts = (p, n) => Math.sqrt((p * (1 - p)) / n) * 100;
```

- [ ] **Step 5: Run the format tests**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/format.test.js`
Expected: 6 passed.

- [ ] **Step 6: Theme, fonts, meta**

Replace `frontend/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: "#0b0b0c",
        surface: "#151517",
        ink: "#f4f3ef",
        "ink-2": "#b8b6ae",
        muted: "#7c7a72",
        hairline: "rgba(255,255,255,0.10)",
        accent: "#e8362b",
        up: "#3ccb7f",
        down: "#ef6b62",
      },
      fontFamily: {
        display: ['"Barlow Condensed"', '"Arial Narrow"', "system-ui", "sans-serif"],
        body: ["Barlow", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
      },
      maxWidth: { content: "1040px" },
    },
  },
  plugins: [],
};
```

Replace `frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  background: #0b0b0c;
  color: #f4f3ef;
  font-family: Barlow, system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.tnum {
  font-variant-numeric: tabular-nums;
}
```

Replace `frontend/public/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/betUFC.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#0b0b0c" />
    <meta
      name="description"
      content="UFC Alpha: a machine-learning UFC fight model, tested out of sample against closing odds. Backtests, calibration, and a public bet log."
    />
    <meta property="og:title" content="UFC Alpha" />
    <meta
      property="og:description"
      content="A UFC fight model that knows when it's right. Out-of-sample results, calibration, and every bet, graded."
    />
    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://ufcalpha.com/" />
    <meta property="og:image" content="https://ufcalpha.com/betUFC.png" />
    <meta name="twitter:card" content="summary" />
    <link rel="apple-touch-icon" href="%PUBLIC_URL%/betUFC.png" />
    <link rel="manifest" href="%PUBLIC_URL%/manifest.json" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap"
      rel="stylesheet"
    />
    <title>UFC Alpha</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
```

Replace `frontend/public/manifest.json`:

```json
{
  "short_name": "UFC Alpha",
  "name": "UFC Alpha",
  "icons": [
    { "src": "favicon.ico", "sizes": "64x64 32x32 24x24 16x16", "type": "image/x-icon" },
    { "src": "betUFC.png", "type": "image/png", "sizes": "192x192" }
  ],
  "start_url": ".",
  "display": "standalone",
  "theme_color": "#0b0b0c",
  "background_color": "#0b0b0c"
}
```

Replace `frontend/src/setupTests.js`:

```js
// jest-dom adds custom jest matchers for asserting on DOM nodes.
import "@testing-library/jest-dom";

// recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = window.ResizeObserver || ResizeObserverStub;
```

- [ ] **Step 7: Constants and fixtures**

Replace `frontend/src/constants.js`:

```js
export const baseURL = process.env.REACT_APP_API_URL || "http://127.0.0.1:5000";

export const SITE_NAME = "UFC Alpha";
// Swap for the live Patreon or Discord invite before launch.
export const MEMBERSHIP_URL = "https://www.patreon.com/ufcalpha";
export const GITHUB_URL = "https://github.com/UFCAlpha/UFCFightPredictor";
export const RESPONSIBLE_GAMBLING_URL = "https://www.responsiblegambling.org/";
```

Create `frontend/src/test/fixtures.js`:

```js
export const backtestFixture = {
  generated: "2026-09-02T14:05:00",
  window: { start: "2025-08-30", end: "2026-08-30", retrains: ["2025-08-30", "2026-02-28", "2026-08-29"] },
  coverage: { fights_in_window: 547, scored: 282, with_odds: 281 },
  metrics: { accuracy: 0.6702, auc: 0.704, log_loss: 0.638, brier: 0.223, n: 282 },
  bands: [
    { label: "50–55%", lo: 0.5, hi: 0.55, n: 60, stated: 0.525, hit: 0.6 },
    { label: "55–60%", lo: 0.55, hi: 0.6, n: 70, stated: 0.575, hit: 0.63 },
    { label: "60–65%", lo: 0.6, hi: 0.65, n: 62, stated: 0.625, hit: 0.629 },
    { label: "65–70%", lo: 0.65, hi: 0.7, n: 68, stated: 0.675, hit: 0.72 },
    { label: "70%+", lo: 0.7, hi: 1.0, n: 22, stated: 0.74, hit: 0.818 },
  ],
  monthly: [
    { month: "2025-09", n: 33, hit: 0.667 },
    { month: "2025-10", n: 30, hit: 0.7 },
  ],
  market: {
    rows: [
      { name: "De-vigged market", accuracy: 0.69, auc: 0.736, log_loss: 0.603, brier: 0.207 },
      { name: "Model (ensemble)", accuracy: 0.673, auc: 0.704, log_loss: 0.638, brier: 0.223 },
      { name: "Blend · 0.8 model + 0.2 market", accuracy: 0.68, auc: 0.73, log_loss: 0.624, brier: 0.217 },
    ],
    agree: { n: 212, hit: 0.741 },
    disagree: { n: 69, model_hit: 0.464 },
  },
  flat: { market_favorite_per_bet: 0.008, model_pick_per_bet: 0.081, stake: 10 },
  betting: {
    final: 1132.93, return_pct: 13.3, bets: 199, hit: 0.618,
    favorites: { won: 102, total: 152 }, underdogs: { won: 21, total: 47 },
    max_drawdown_pct: 7.5, low: 991.5,
  },
  bankroll: [
    { date: "2025-09-06", event: "ufc-fight-night-september-06-2025", bankroll: 1008.27 },
    { date: "2025-09-13", event: "ufc-320", bankroll: 1001.1 },
  ],
  bets: [
    {
      date: "2025-09-06", event: "ufc-fight-night-september-06-2025", fighter: "Alpha Fighter",
      opponent: "Beta Fighter", odds: -150, model_prob: 0.66, market_prob: 0.58, edge: 0.08,
      stake: 12.4, result: "win", pnl: 8.27, bankroll_after: 1008.27, source: "backtest",
    },
    {
      date: "2025-09-13", event: "ufc-320", fighter: "Gamma Fighter", opponent: "Delta Fighter",
      odds: 140, model_prob: 0.48, market_prob: 0.41, edge: 0.07, stake: 7.17, result: "loss",
      pnl: -7.17, bankroll_after: 1001.1, source: "backtest",
    },
  ],
};

export const ledgerFixture = [
  {
    event: "UFC Fight Night: Live vs Test", event_date: "2026-09-06", generated: "2026-09-04T02:10:00",
    fighter: "Live Winner", opponent: "Live Loser", odds: -130, model_prob: 0.64, market_prob: 0.56,
    edge: 0.08, kelly: 0.11, stake_pct: 0.55, result: "win", pnl_per_unit: 0.7692, graded: "2026-09-08T02:05:00",
  },
  {
    event: "UFC Fight Night: Live vs Test", event_date: "2026-09-06", generated: "2026-09-04T02:10:00",
    fighter: "Pending Pick", opponent: "Pending Foe", odds: 150, model_prob: 0.47, market_prob: 0.4,
    edge: 0.07, kelly: 0.09, stake_pct: 0.45, result: "pending", pnl_per_unit: null, graded: null,
  },
];
```

- [ ] **Step 8: StatTile, ScrollToTop, Navbar, Footer**

Create `frontend/src/components/StatTile.js`:

```jsx
import React from "react";

/** label / value / sub. tone colors the value: "up" | "down" | undefined. */
export default function StatTile({ label, value, sub, tone }) {
  const toneClass = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";
  return (
    <div className="rounded-lg border border-hairline bg-surface px-5 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className={`mt-1 font-body text-4xl font-semibold leading-none ${toneClass}`}>{value}</div>
      {sub && <div className="mt-2 text-sm text-ink-2">{sub}</div>}
    </div>
  );
}
```

Create `frontend/src/components/ScrollToTop.js`:

```jsx
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export default function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
```

Replace `frontend/src/components/Navbar.js`:

```jsx
import React from "react";
import { Link, NavLink } from "react-router-dom";
import { MEMBERSHIP_URL, SITE_NAME } from "../constants";

const LINKS = [
  ["/results", "Results"],
  ["/bets", "Bet log"],
  ["/methodology", "Methodology"],
];

const linkClass = ({ isActive }) =>
  `text-sm font-medium ${isActive ? "text-ink" : "text-ink-2 hover:text-ink"}`;

export default function Navbar() {
  return (
    <header className="sticky top-0 z-10 border-b border-hairline bg-ground/90 backdrop-blur">
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-4">
        <Link to="/" className="font-display text-2xl font-bold uppercase tracking-wide text-ink">
          {SITE_NAME}
        </Link>
        <nav className="flex items-center gap-6">
          <div className="hidden items-center gap-6 sm:flex">
            {LINKS.map(([to, label]) => (
              <NavLink key={to} to={to} className={linkClass}>
                {label}
              </NavLink>
            ))}
          </div>
          <a
            href={MEMBERSHIP_URL}
            target="_blank"
            rel="noreferrer"
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-[#f04e43]"
          >
            Get the picks
          </a>
        </nav>
      </div>
      <nav className="flex gap-5 px-6 pb-3 sm:hidden">
        {LINKS.map(([to, label]) => (
          <NavLink key={to} to={to} className={linkClass}>
            {label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
```

Create `frontend/src/components/Footer.js`:

```jsx
import React from "react";
import { Link } from "react-router-dom";
import { GITHUB_URL, RESPONSIBLE_GAMBLING_URL, SITE_NAME } from "../constants";

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-hairline">
      <div className="mx-auto max-w-content px-6 py-10 text-sm text-ink-2">
        <p className="max-w-3xl">
          {SITE_NAME} publishes model output for informational purposes. Nothing here is betting
          advice. Past performance does not guarantee future results. Every bankroll figure on this
          site is a $1,000 paper bankroll replayed against closing odds. You must be of legal
          gambling age in your jurisdiction.
        </p>
        <div className="mt-6 flex flex-wrap gap-6 text-muted">
          <a href={RESPONSIBLE_GAMBLING_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
            Gambling problem? Get help
          </a>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
            Source on GitHub
          </a>
          <Link to="/methodology" className="hover:text-ink">
            Methodology
          </Link>
        </div>
      </div>
    </footer>
  );
}
```

- [ ] **Step 9: App.js with placeholder pages, App.test.js, deletions**

Replace `frontend/src/App.js`:

```jsx
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import Home from "./components/Home";
import backtest from "./data/backtest.json";
import ledger from "./data/ledger.json";

const App = () => (
  <Router>
    <ScrollToTop />
    <div className="min-h-screen bg-ground font-body text-ink">
      <Navbar />
      <Routes>
        <Route path="/" element={<Home data={backtest} ledger={ledger} />} />
      </Routes>
      <Footer />
    </div>
  </Router>
);

export default App;
```

Replace `frontend/src/components/Home.js` with a temporary stub that Task 8 replaces:

```jsx
import React from "react";

export default function Home({ data }) {
  return <main className="mx-auto max-w-content px-6 py-16">{data.metrics.n} fights scored.</main>;
}
```

Replace `frontend/src/App.test.js`:

```js
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the brand and the membership button", () => {
  render(<App />);
  expect(screen.getByText("UFC Alpha")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Get the picks" })).toHaveAttribute("target", "_blank");
});
```

Delete the old files:

```bash
git rm frontend/src/components/FightPredictor.js frontend/src/components/Testing.js \
  frontend/src/components/About.js frontend/src/constants/about.md \
  frontend/src/constants/predictions.txt frontend/src/constants/README.md \
  frontend/src/assets/2021_to_2024.png frontend/src/App.css
```

- [ ] **Step 10: Run the frontend tests and the production build**

Run from `frontend/`:

```bash
CI=true npx react-scripts test --watchAll=false
CI=true npm run build
```

Expected: tests pass (format + App), build prints `Compiled successfully.` with no warnings. If the build fails on an unused import, remove that import.

- [ ] **Step 11: Commit**

```bash
git add -A frontend/package.json frontend/package-lock.json frontend/tailwind.config.js \
  frontend/public/index.html frontend/public/manifest.json frontend/src
git commit -m "Rebuild the frontend shell as UFC Alpha: theme, meta, nav, footer, helpers

Removes the predictor, live backtest and about pages; adds recharts.

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Chart components

**Files:**
- Create: `frontend/src/components/charts/chartTheme.js`, `CalibrationChart.js`, `MonthlyAccuracyChart.js`, `BankrollChart.js`
- Test: `frontend/src/components/charts/charts.test.js`

**Interfaces:**
- Consumes: `format.js` helpers (Task 6).
- Produces: `CalibrationChart({ bands })`, `MonthlyAccuracyChart({ monthly, overall })`, `BankrollChart({ points, start = 1000 })`. Each renders a fixed-height plot plus a "View as table" `<details>` twin.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/charts/charts.test.js`:

```js
import { render, screen } from "@testing-library/react";
import CalibrationChart from "./CalibrationChart";
import MonthlyAccuracyChart from "./MonthlyAccuracyChart";
import BankrollChart from "./BankrollChart";
import { backtestFixture as fx } from "../../test/fixtures";

test("calibration chart ships a table twin with every band", () => {
  render(<CalibrationChart bands={fx.bands} />);
  expect(screen.getAllByText("View as table")).toHaveLength(1);
  expect(screen.getByRole("table", { name: "Calibration by confidence band" })).toBeInTheDocument();
  // axis ticks may or may not render in jsdom, so allow more than one match
  expect(screen.getAllByText("70%+").length).toBeGreaterThan(0);
  expect(screen.getAllByText("81.8%").length).toBeGreaterThan(0);
});

test("monthly chart table lists every month", () => {
  render(<MonthlyAccuracyChart monthly={fx.monthly} overall={fx.metrics.accuracy} />);
  expect(screen.getByRole("table", { name: "Accuracy by month" })).toBeInTheDocument();
  expect(screen.getAllByText("Sep ’25").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Oct ’25").length).toBeGreaterThan(0);
});

test("bankroll chart table shows month-end checkpoints", () => {
  render(<BankrollChart points={fx.bankroll} />);
  expect(screen.getByRole("table", { name: "Bankroll at month end" })).toBeInTheDocument();
  expect(screen.getByText("$1,001.10")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/charts`
Expected: FAIL, `Cannot find module './CalibrationChart'`.

- [ ] **Step 3: Write the shared theme**

Create `frontend/src/components/charts/chartTheme.js`:

```jsx
import React from "react";

// Series colors validated on the #151517 surface: accent carries the model,
// the neutral gray is de-emphasis context (the "emphasis" form, not a second hue).
export const C = {
  accent: "#e8362b",
  gray: "#b8b6ae",
  grid: "rgba(255,255,255,0.10)",
  axis: "#7c7a72",
  surface: "#151517",
  ink: "#f4f3ef",
  ink2: "#b8b6ae",
};

export const tick = { fill: C.axis, fontSize: 12, fontFamily: "Barlow, system-ui, sans-serif" };

/** Tooltip body: value first (strong), label second, keyed by a short line of the series color. */
export function TooltipBox({ title, rows }) {
  return (
    <div className="rounded-md border border-hairline bg-ground px-3 py-2 text-sm shadow-lg">
      <div className="mb-1 text-xs text-muted">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2">
          {r.color && <span className="inline-block h-0.5 w-3" style={{ background: r.color }} />}
          <span className="tnum font-semibold text-ink">{r.value}</span>
          <span className="text-ink-2">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Every chart's table twin, collapsed behind a disclosure. */
export function ChartTable({ caption, columns, rows }) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-muted hover:text-ink-2">View as table</summary>
      <table className="tnum mt-2 w-full text-left" aria-label={caption}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} className="border-b border-hairline py-1 pr-4 text-xs font-semibold uppercase tracking-wider text-muted">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((cell, j) => (
                <td key={j} className="border-b border-hairline py-1 pr-4 text-ink-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export const legendText = (value) => <span style={{ color: C.ink2, fontSize: 12 }}>{value}</span>;
```

- [ ] **Step 4: CalibrationChart**

Create `frontend/src/components/charts/CalibrationChart.js`:

```jsx
import React from "react";
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { pct } from "../../format";
import { C, ChartTable, TooltipBox, legendText, tick } from "./chartTheme";

function CalibrationTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const b = payload[0].payload;
  return (
    <TooltipBox
      title={`${b.label} · ${b.n} fights`}
      rows={[
        { label: "actual hit rate", value: pct(b.hit), color: C.accent },
        { label: "avg stated confidence", value: pct(b.stated), color: C.gray },
      ]}
    />
  );
}

export default function CalibrationChart({ bands }) {
  const data = bands.filter((b) => b.n > 0);
  return (
    <div>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={2} barCategoryGap="32%" margin={{ top: 20, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="label" tick={tick} axisLine={{ stroke: C.grid }} tickLine={false} />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={tick}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<CalibrationTooltip />} />
            <Legend iconType="rect" iconSize={10} formatter={legendText} />
            <Bar dataKey="stated" name="Stated confidence" fill={C.gray} barSize={20} radius={[4, 4, 0, 0]} />
            <Bar dataKey="hit" name="Actual hit rate" fill={C.accent} barSize={20} radius={[4, 4, 0, 0]}>
              <LabelList dataKey="hit" position="top" formatter={(v) => pct(v, 0)} style={{ fill: C.ink, fontSize: 12 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption="Calibration by confidence band"
        columns={["Band", "Fights", "Avg stated", "Actual hit rate"]}
        rows={bands.map((b) => [b.label, b.n, pct(b.stated), pct(b.hit)])}
      />
    </div>
  );
}
```

- [ ] **Step 5: MonthlyAccuracyChart**

Create `frontend/src/components/charts/MonthlyAccuracyChart.js`:

```jsx
import React from "react";
import {
  Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { monthLabel, pct } from "../../format";
import { C, ChartTable, TooltipBox, tick } from "./chartTheme";

function MonthTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <TooltipBox
      title={`${m.label} · ${m.n} fights`}
      rows={[{ label: "hit rate", value: pct(m.hit), color: C.accent }]}
    />
  );
}

export default function MonthlyAccuracyChart({ monthly, overall }) {
  const data = monthly.map((m) => ({ ...m, label: monthLabel(m.month) }));
  return (
    <div>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="35%" margin={{ top: 16, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="label" tick={tick} axisLine={{ stroke: C.grid }} tickLine={false} interval={0} />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={tick}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<MonthTooltip />} />
            <ReferenceLine
              y={overall}
              stroke={C.gray}
              strokeWidth={1}
              label={{ value: `year ${pct(overall, 0)}`, position: "insideTopRight", fill: C.ink2, fontSize: 12 }}
            />
            <Bar dataKey="hit" fill={C.accent} barSize={20} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartTable
        caption="Accuracy by month"
        columns={["Month", "Fights", "Hit rate"]}
        rows={data.map((m) => [m.label, m.n, pct(m.hit)])}
      />
    </div>
  );
}
```

- [ ] **Step 6: BankrollChart**

Create `frontend/src/components/charts/BankrollChart.js`:

```jsx
import React from "react";
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { eventName, money, monthLabel, shortDate } from "../../format";
import { C, ChartTable, TooltipBox, tick } from "./chartTheme";

function BankrollTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const title = d.event === "start" ? "Start" : `${shortDate(d.date)} · ${eventName(d.event)}`;
  return <TooltipBox title={title} rows={[{ label: "bankroll", value: money(d.bankroll), color: C.accent }]} />;
}

/** Month-end checkpoints for the table twin. */
function monthEnds(points) {
  const last = new Map();
  points.forEach((p) => last.set(p.date.slice(0, 7), p.bankroll));
  return [...last.entries()].map(([m, b]) => [monthLabel(m), money(b)]);
}

export default function BankrollChart({ points, start = 1000 }) {
  const data = [
    { i: 0, date: points[0]?.date ?? "", event: "start", bankroll: start },
    ...points.map((p, k) => ({ i: k + 1, ...p })),
  ];
  const ticks = [];
  let seen = null;
  data.slice(1).forEach((d) => {
    const m = d.date.slice(0, 7);
    if (m !== seen) {
      ticks.push(d.i);
      seen = m;
    }
  });
  const values = data.map((d) => d.bankroll);
  const lo = Math.floor(Math.min(...values) / 50) * 50;
  const hi = Math.ceil(Math.max(...values) / 50) * 50;
  return (
    <div>
      <div style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 16, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="bankrollWash" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.accent} stopOpacity={0.18} />
                <stop offset="100%" stopColor={C.accent} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis
              dataKey="i"
              type="number"
              domain={[0, data.length - 1]}
              ticks={ticks}
              tickFormatter={(i) => monthLabel(data[i].date.slice(0, 7))}
              tick={tick}
              axisLine={{ stroke: C.grid }}
              tickLine={false}
            />
            <YAxis
              domain={[lo, hi]}
              tickFormatter={(v) => `$${v.toLocaleString("en-US")}`}
              tick={tick}
              axisLine={false}
              tickLine={false}
              width={72}
            />
            <ReferenceLine
              y={start}
              stroke={C.gray}
              strokeWidth={1}
              label={{ value: "break-even", position: "insideBottomRight", fill: C.ink2, fontSize: 12 }}
            />
            <Tooltip cursor={{ stroke: C.gray, strokeWidth: 1 }} content={<BankrollTooltip />} />
            <Area
              type="linear"
              dataKey="bankroll"
              stroke={C.accent}
              strokeWidth={2}
              fill="url(#bankrollWash)"
              dot={false}
              activeDot={{ r: 4, fill: C.accent, stroke: C.surface, strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <ChartTable caption="Bankroll at month end" columns={["Month", "Bankroll"]} rows={monthEnds(points)} />
    </div>
  );
}
```

- [ ] **Step 7: Run the chart tests**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/charts`
Expected: 3 passed. recharts may warn about a zero-width container in jsdom; that is noise, not a failure.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/charts
git commit -m "Add calibration, monthly accuracy and bankroll charts with table twins

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Home page

**Files:**
- Modify: `frontend/src/components/Home.js` (replace the Task 6 stub)
- Test: `frontend/src/components/Home.test.js`

**Interfaces:**
- Consumes: `StatTile`, `CalibrationChart`, `format.js`, `constants.js`.
- Produces: `Home({ data })` where `data` is the backtest payload.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/Home.test.js`:

```js
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Home from "./Home";
import { MEMBERSHIP_URL } from "../constants";
import { backtestFixture as fx } from "../test/fixtures";

test("home leads with the out-of-sample record and the membership CTA", () => {
  render(<MemoryRouter><Home data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("A UFC model that knows when it's right.");
  expect(screen.getAllByText("67.0%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("81.8%").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/199 bets/).length).toBeGreaterThan(0);
  const ctas = screen.getAllByRole("link", { name: "Get this week's picks" });
  expect(ctas[0]).toHaveAttribute("href", MEMBERSHIP_URL);
  expect(screen.getByRole("link", { name: "See the full results" })).toHaveAttribute("href", "/results");
  expect(screen.getByText(/\$1,000 paper bankroll/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/Home.test.js`
Expected: FAIL on the heading assertion (the stub renders no h1).

- [ ] **Step 3: Write Home.js**

Replace `frontend/src/components/Home.js`:

```jsx
import React from "react";
import { Link } from "react-router-dom";
import StatTile from "./StatTile";
import CalibrationChart from "./charts/CalibrationChart";
import { MEMBERSHIP_URL } from "../constants";
import { pct, shortDate, signedPct, stdErrPts } from "../format";

const Eyebrow = ({ children }) => (
  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{children}</p>
);

const H2 = ({ children }) => (
  <h2 className="mt-2 font-display text-4xl font-bold leading-none tracking-wide text-ink">{children}</h2>
);

const CtaButton = ({ children }) => (
  <a
    href={MEMBERSHIP_URL}
    target="_blank"
    rel="noreferrer"
    className="inline-block rounded-md bg-accent px-6 py-3 text-base font-semibold text-white hover:bg-[#f04e43]"
  >
    {children}
  </a>
);

const STEPS = [
  ["Data", "Every UFC fight since 1994, scraped from ufcstats.com: strikes, takedowns, control time, finishes. Each fight is described only by what was known before it happened."],
  ["Model", "180+ engineered features per fighter feed a five-model LightGBM ensemble retrained twice a week. It outputs a win probability, not a hot take."],
  ["Bets", "Probability meets closing odds. A fractional Kelly stake goes down only when the model's edge over the de-vigged market clears 5%."],
];

export default function Home({ data }) {
  // `window` is renamed so it never shadows the browser global
  const { metrics, bands, market, flat, betting, coverage, window: span } = data;
  const top = bands[bands.length - 1];
  const populated = bands.filter((b) => b.n > 0);
  const climbs = populated.every((b, i) => i === 0 || b.hit >= populated[i - 1].hit);
  const modelBeatsFavorites = flat.model_pick_per_bet > flat.market_favorite_per_bet;
  const se = stdErrPts(metrics.accuracy, metrics.n);

  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-16 pt-20">
        <Eyebrow>Out-of-sample · walk-forward · closing odds</Eyebrow>
        <h1 className="mt-4 max-w-4xl font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink sm:text-7xl">
          A UFC model that knows when it's right.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          Over the last twelve months it scored <b className="text-ink">{metrics.n}</b> fights it had never
          seen and called <b className="text-ink">{pct(metrics.accuracy)}</b> of them. When it said 70% or
          better, it hit <b className="text-ink">{pct(top.hit)}</b>.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <CtaButton>Get this week's picks</CtaButton>
          <Link
            to="/results"
            className="inline-block rounded-md border border-hairline px-6 py-3 text-base font-semibold text-ink hover:bg-surface"
          >
            See the full results
          </Link>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Out-of-sample accuracy"
          value={pct(metrics.accuracy)}
          sub={`${metrics.n} fights · ${shortDate(span.start)} to ${shortDate(span.end)}`}
        />
        <StatTile
          label="70%+ confidence picks"
          value={pct(top.hit)}
          sub={`${top.n} picks · stated ${pct(top.stated)} on average`}
        />
        <StatTile
          label="Flat $10 on the model's pick"
          value={`${signedPct(flat.model_pick_per_bet * 100)} / bet`}
          tone={flat.model_pick_per_bet >= 0 ? "up" : "down"}
          sub={`Blindly backing the favorite: ${signedPct(flat.market_favorite_per_bet * 100)} / bet`}
        />
        <StatTile
          label="Kelly paper bankroll"
          value={signedPct(betting.return_pct)}
          tone={betting.return_pct >= 0 ? "up" : "down"}
          sub={`${betting.bets} bets · ${betting.max_drawdown_pct}% max drawdown · $1,000 start`}
        />
      </section>

      <section className="mt-24">
        <Eyebrow>How it works</Eyebrow>
        <H2>Three steps, no vibes</H2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {STEPS.map(([title, body]) => (
            <div key={title} className="rounded-lg border border-hairline bg-surface p-6">
              <h3 className="font-display text-2xl font-bold tracking-wide text-ink">{title}</h3>
              <p className="mt-2 text-ink-2">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-24">
        <Eyebrow>Calibration</Eyebrow>
        <H2>Confidence you can size a bet on</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          Kelly sizing only works if "70%" means 70%. This chart puts the model's stated confidence beside
          what actually happened, band by band.{" "}
          {climbs
            ? "The bars climb together: the more confident the model, the more often it is right."
            : "The higher bands mostly hit more often; the small bands wobble, and that is what small samples do."}{" "}
          That is the property a stale model loses first, and the reason the ensemble is retrained twice a week.
        </p>
        <div className="mt-8 rounded-lg border border-hairline bg-surface p-5">
          <CalibrationChart bands={bands} />
        </div>
      </section>

      <section className="mt-24">
        <Eyebrow>Versus the market</Eyebrow>
        <H2>{modelBeatsFavorites ? "The market predicts well. The model still finds prices." : "The market is sharp. So is the model."}</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          On <b className="text-ink">{market.agree.n}</b> of {coverage.with_odds} priced fights, the model and the
          closing line pick the same fighter, and those picks hit <b className="text-ink">{pct(market.agree.hit)}</b>.
          Where they disagree ({market.disagree.n} fights) the model wins {pct(market.disagree.model_hit)}. Sharp
          lines price injuries, camp changes and late news that a career-stats model never sees.{" "}
          {modelBeatsFavorites
            ? `The edge is not out-predicting the market. It is knowing which prices are soft: a flat $10 on every model pick returned ${signedPct(flat.model_pick_per_bet * 100)} per bet against ${signedPct(flat.market_favorite_per_bet * 100)} for the favorite.`
            : `At flat stakes this year the model's picks returned ${signedPct(flat.model_pick_per_bet * 100)} per bet against ${signedPct(flat.market_favorite_per_bet * 100)} for blindly backing the favorite.`}
        </p>
        <div className="mt-8 overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="tnum w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Forecaster</th>
                <th className="px-5 py-3 font-semibold">Accuracy</th>
                <th className="px-5 py-3 font-semibold">AUC</th>
                <th className="px-5 py-3 font-semibold">Log loss</th>
                <th className="px-5 py-3 font-semibold">Brier</th>
              </tr>
            </thead>
            <tbody>
              {market.rows.map((r) => (
                <tr key={r.name} className="border-t border-hairline">
                  <td className="px-5 py-3 text-ink">{r.name}</td>
                  <td className="px-5 py-3 text-ink-2">{pct(r.accuracy)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.auc.toFixed(3)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.log_loss.toFixed(3)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.brier.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-24 rounded-lg border border-hairline bg-surface p-8 sm:p-12">
        <Eyebrow>Membership</Eyebrow>
        <H2>Every pick for the next card, before it starts</H2>
        <ul className="mt-6 max-w-2xl list-disc space-y-2 pl-5 text-ink-2">
          <li>Model probability, de-vigged market probability, edge and Kelly stake for every bout the model covers.</li>
          <li>Posted before the card. Graded publicly on the bet log afterwards.</li>
          <li>The same numbers the backtest was scored on. Nothing hand-picked.</li>
        </ul>
        <div className="mt-8">
          <CtaButton>Get this week's picks</CtaButton>
        </div>
      </section>

      <section className="mt-24">
        <Eyebrow>Read the fine print</Eyebrow>
        <H2>What this record does not prove</H2>
        <ul className="mt-6 max-w-2xl list-disc space-y-3 pl-5 text-ink-2">
          <li>
            <b className="text-ink">Sample size.</b> {pct(metrics.accuracy)} on {metrics.n} fights carries a
            ±{se.toFixed(1)}-point standard error. Treat the direction as meaningful, not the second digit.
          </li>
          <li>
            <b className="text-ink">Coverage.</b> The model scored {coverage.scored} of {coverage.fights_in_window}{" "}
            fights in the window. It skips women's bouts, debutants, and anyone with fewer than two UFC fights.
          </li>
          <li>
            <b className="text-ink">Paper money.</b> Every return here is a $1,000 paper bankroll replayed against
            closing odds, with {betting.bets} bets and a {betting.max_drawdown_pct}% max drawdown. Real limits,
            line movement and fees will differ.
          </li>
        </ul>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Run the test**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/Home.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Home.js frontend/src/components/Home.test.js
git commit -m "Write the UFC Alpha landing page from the exported record

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Results page

**Files:**
- Create: `frontend/src/components/Results.js`
- Modify: `frontend/src/App.js` (add route)
- Test: `frontend/src/components/Results.test.js`

**Interfaces:**
- Consumes: `StatTile`, all three charts, `format.js`.
- Produces: `Results({ data })`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/Results.test.js`:

```js
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Results from "./Results";
import { backtestFixture as fx } from "../test/fixtures";

test("results page reports method, coverage, calibration, market and betting", () => {
  render(<MemoryRouter><Results data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("One year out of sample");
  expect(screen.getByText(/547 fights/)).toBeInTheDocument();
  expect(screen.getByText(/2026-02-28/)).toBeInTheDocument();
  expect(screen.getByText("$1,132.93")).toBeInTheDocument();
  expect(screen.getAllByText(/199 bets/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/7.5% max drawdown/).length).toBeGreaterThan(0);
  expect(screen.getByRole("table", { name: "Calibration by confidence band" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Accuracy by month" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Bankroll at month end" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/Results.test.js`
Expected: FAIL, `Cannot find module './Results'`.

- [ ] **Step 3: Write Results.js**

Create `frontend/src/components/Results.js`:

```jsx
import React from "react";
import StatTile from "./StatTile";
import CalibrationChart from "./charts/CalibrationChart";
import MonthlyAccuracyChart from "./charts/MonthlyAccuracyChart";
import BankrollChart from "./charts/BankrollChart";
import { money, monthLabel, pct, shortDate, signedPct, stdErrPts } from "../format";

const Eyebrow = ({ children }) => (
  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{children}</p>
);
const H2 = ({ children }) => (
  <h2 className="mt-2 font-display text-4xl font-bold leading-none tracking-wide text-ink">{children}</h2>
);
const Card = ({ children }) => (
  <div className="mt-8 rounded-lg border border-hairline bg-surface p-5">{children}</div>
);

export default function Results({ data }) {
  // `window` is renamed so it never shadows the browser global
  const { window: span, coverage, metrics, bands, monthly, market, flat, betting, bankroll } = data;
  const top = bands[bands.length - 1];
  const retrains = span.retrains.slice(1);
  const se = stdErrPts(metrics.accuracy, metrics.n);
  const months = monthly.map((m) => m.hit);
  const worst = monthly[months.indexOf(Math.min(...months))];
  const best = monthly[months.indexOf(Math.max(...months))];

  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-12 pt-20">
        <Eyebrow>
          Annual model review · {shortDate(span.start)} → {shortDate(span.end)} · generated {data.generated.slice(0, 10)}
        </Eyebrow>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">
          One year out of sample
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          How the deployed model performed on twelve months it never trained on: {metrics.n} fights scored
          walk-forward, graded on accuracy, calibration, and what a $1,000 paper bankroll did against real
          closing odds.
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Accuracy" value={pct(metrics.accuracy)} sub={`${metrics.n} out-of-sample fights`} />
        <StatTile
          label="Kelly return"
          value={signedPct(betting.return_pct)}
          tone={betting.return_pct >= 0 ? "up" : "down"}
          sub={`${betting.bets} bets · ${betting.max_drawdown_pct}% max drawdown`}
        />
        <StatTile label="AUC" value={metrics.auc.toFixed(3)} sub={`log loss ${metrics.log_loss.toFixed(3)} · Brier ${metrics.brier.toFixed(3)}`} />
        <StatTile label="70%+ confidence" value={pct(top.hit)} sub={`hit rate on ${top.n} high-conviction picks`} />
      </section>

      <section className="mt-20">
        <Eyebrow>Method</Eyebrow>
        <H2>No peeking</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          Every prediction comes from a model that had never seen the fight, or anything after it. The ensemble
          trained on fights before {span.start}, then retrained on {retrains.join(" and ")} as the year
          advanced, matching the production cadence. Hyperparameters were frozen before the window opened.
        </p>
        <p className="mt-4 max-w-2xl text-ink-2">
          Coverage: the window had {coverage.fights_in_window} fights with recorded results. The model scored{" "}
          {coverage.scored} of them and skipped the rest by design: women's bouts are excluded from the training
          data, both fighters need at least two prior UFC fights, and draws and no contests are not graded.
          Betting uses the {coverage.with_odds} scored fights with usable closing odds, de-vigged to remove the
          bookmaker's margin.
        </p>
      </section>

      <section className="mt-20">
        <Eyebrow>Calibration</Eyebrow>
        <H2>When it says 70%, does it win 70%?</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          For Kelly sizing the question is not "how often is it right" but whether stated confidence tracks
          reality. Stated confidence against actual hit rate, by the model's pre-fight win probability.
        </p>
        <Card><CalibrationChart bands={bands} /></Card>
      </section>

      <section className="mt-20">
        <Eyebrow>By month</Eyebrow>
        <H2>Accuracy by month</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          Month-to-month swings ({pct(worst.hit, 0)} in {monthLabel(worst.month)} to {pct(best.hit, 0)} in {monthLabel(best.month)}) are
          what {Math.min(...monthly.map((m) => m.n))} to {Math.max(...monthly.map((m) => m.n))} fight samples do.
          The reference line is the year's hit rate.
        </p>
        <Card><MonthlyAccuracyChart monthly={monthly} overall={metrics.accuracy} /></Card>
      </section>

      <section className="mt-20">
        <Eyebrow>Versus the market</Eyebrow>
        <H2>Model, market, and the blend that bets</H2>
        <div className="mt-8 overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="tnum w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Forecaster</th>
                <th className="px-5 py-3 font-semibold">Accuracy</th>
                <th className="px-5 py-3 font-semibold">AUC</th>
                <th className="px-5 py-3 font-semibold">Log loss</th>
                <th className="px-5 py-3 font-semibold">Brier</th>
              </tr>
            </thead>
            <tbody>
              {market.rows.map((r) => (
                <tr key={r.name} className="border-t border-hairline">
                  <td className="px-5 py-3 text-ink">{r.name}</td>
                  <td className="px-5 py-3 text-ink-2">{pct(r.accuracy)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.auc.toFixed(3)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.log_loss.toFixed(3)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.brier.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-6 max-w-2xl text-ink-2">
          On the {coverage.with_odds} priced fights, the model and the market favor the same fighter{" "}
          {market.agree.n} times, and those picks hit {pct(market.agree.hit)}. On the {market.disagree.n} fights
          where they disagree, the model wins {pct(market.disagree.model_hit)}. A bettor does not need to
          out-predict the market, only to find prices that pay more than a calibrated probability says they should.
        </p>
      </section>

      <section className="mt-20">
        <Eyebrow>Betting</Eyebrow>
        <H2>{signedPct(betting.return_pct)} on a $1,000 paper bankroll</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          The production config bets the model's pick with fractional Kelly (5% fraction, 5% cap, no floor)
          whenever the blended probability beats the de-vigged price by at least 5 points. {betting.bets} bets,{" "}
          {betting.max_drawdown_pct}% max drawdown, low point {money(betting.low)}.
        </p>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Final bankroll" value={money(betting.final)} sub={`from $1,000 · ${betting.bets} bets`} />
          <StatTile label="Hit rate" value={pct(betting.hit)} sub={`${betting.favorites.won}/${betting.favorites.total} favorites · ${betting.underdogs.won}/${betting.underdogs.total} underdogs`} />
          <StatTile label="Max drawdown" value={`${betting.max_drawdown_pct}%`} sub={`low point ${money(betting.low)}`} />
          <StatTile
            label="Flat $10 per fight"
            value={`${signedPct(flat.model_pick_per_bet * 100)} / bet`}
            tone={flat.model_pick_per_bet >= 0 ? "up" : "down"}
            sub={`model pick · favorite ${signedPct(flat.market_favorite_per_bet * 100)} / bet`}
          />
        </div>
        <Card><BankrollChart points={bankroll} /></Card>
      </section>

      <section className="mt-20">
        <Eyebrow>Analysis</Eyebrow>
        <H2>Why this works, and where it doesn't</H2>
        <ul className="mt-6 max-w-2xl list-disc space-y-3 pl-5 text-ink-2">
          <li>
            <b className="text-ink">The edge is price selection, not prophecy.</b> The market forecasts at least as
            well as the model. The return comes from which agreements the model sizes up: fights where its
            calibrated probability says the price is soft.
          </li>
          <li>
            <b className="text-ink">Disagreement is a warning sign.</b> When model and market split, the model wins{" "}
            {pct(market.disagree.model_hit)}. Large gaps usually mean the market knows something a career-stats
            model structurally cannot: injuries, short-notice replacements, weight-cut news.
          </li>
          <li>
            <b className="text-ink">Calibration is the asset to protect.</b> Accuracy barely separates a good year
            from a bad one. What makes betting work is that stated confidence tracked reality band by band.
          </li>
          <li>
            <b className="text-ink">Honest error bars.</b> {pct(metrics.accuracy)} on {metrics.n} fights carries a
            ±{se.toFixed(1)}-point standard error; the return rides on {betting.bets} bets and their sequencing.
          </li>
          <li>
            <b className="text-ink">Coverage is the ceiling.</b> The model acts on{" "}
            {pct(coverage.scored / coverage.fights_in_window, 0)} of fights. The largest untapped improvement is
            not a better model but a wider one.
          </li>
        </ul>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Add the route**

In `frontend/src/App.js` add `import Results from "./components/Results";` and, inside `<Routes>`, after the home route:

```jsx
        <Route path="/results" element={<Results data={backtest} />} />
```

- [ ] **Step 5: Run the tests and build**

Run from `frontend/`:

```bash
CI=true npx react-scripts test --watchAll=false src/components/Results.test.js
CI=true npm run build
```

Expected: PASS; `Compiled successfully.`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Results.js frontend/src/components/Results.test.js frontend/src/App.js
git commit -m "Add the out-of-sample results page

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: Bet log page

**Files:**
- Modify: `frontend/src/components/Bets.js` (rewrite), `frontend/src/App.js` (add route)
- Test: `frontend/src/components/Bets.test.js`

**Interfaces:**
- Consumes: `StatTile`, `BankrollChart`, `format.js`.
- Produces: `Bets({ data, ledger })` where `ledger` is the list of ledger entries.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/Bets.test.js`:

```js
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Bets from "./Bets";
import { backtestFixture as fx, ledgerFixture } from "../test/fixtures";

test("backtest segment lists every bet newest first with P&L", () => {
  render(<MemoryRouter><Bets data={fx} ledger={ledgerFixture} /></MemoryRouter>);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0]).toHaveTextContent("Gamma Fighter");
  expect(rows[0]).toHaveTextContent("−$7.17");
  expect(rows[1]).toHaveTextContent("Alpha Fighter");
  expect(rows[1]).toHaveTextContent("+$8.27");
  expect(screen.getByText("$1,132.93")).toBeInTheDocument();
});

test("live segment shows graded and pending picks in bankroll percent", () => {
  render(<MemoryRouter><Bets data={fx} ledger={ledgerFixture} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: /Live/ }));
  expect(screen.getByText("Live Winner")).toBeInTheDocument();
  expect(screen.getByText("+0.42%")).toBeInTheDocument();
  expect(screen.getByText("pending")).toBeInTheDocument();
  expect(screen.getByText(/1 graded/)).toBeInTheDocument();
});

test("live segment has an empty state", () => {
  render(<MemoryRouter><Bets data={fx} ledger={[]} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: /Live/ }));
  expect(screen.getByText(/No live picks graded yet/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/Bets.test.js`
Expected: FAIL (the old Bets component fetches from the API and renders none of this).

- [ ] **Step 3: Write Bets.js**

Replace `frontend/src/components/Bets.js`:

```jsx
import React, { useState } from "react";
import StatTile from "./StatTile";
import BankrollChart from "./charts/BankrollChart";
import { eventName, money, odds, pct, shortDate, signedMoney, signedPct } from "../format";

const Eyebrow = ({ children }) => (
  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{children}</p>
);

const RESULT_STYLE = {
  win: "text-up",
  loss: "text-down",
  push: "text-ink-2",
  pending: "text-muted",
};

function Segmented({ value, onChange, counts }) {
  return (
    <div role="group" aria-label="Record" className="inline-flex rounded-md border border-hairline bg-surface p-1">
      {[["backtest", "Backtest"], ["live", "Live"]].map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`rounded px-4 py-1.5 text-sm font-medium ${
            value === key ? "bg-ground text-ink" : "text-ink-2 hover:text-ink"
          }`}
        >
          {label} <span className="tnum text-muted">{counts[key]}</span>
        </button>
      ))}
    </div>
  );
}

const Th = ({ children, right }) => (
  <th className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted ${right ? "text-right" : "text-left"}`}>
    {children}
  </th>
);
const Td = ({ children, right, className = "" }) => (
  <td className={`px-4 py-3 ${right ? "text-right" : "text-left"} ${className}`}>{children}</td>
);

function BetTable({ rows, live }) {
  return (
    <div className="mt-6 overflow-x-auto rounded-lg border border-hairline bg-surface">
      <table className="tnum w-full text-sm">
        <thead>
          <tr>
            <Th>Date</Th>
            <Th>Event</Th>
            <Th>Pick</Th>
            <Th>Opponent</Th>
            <Th right>Odds</Th>
            <Th right>Model</Th>
            <Th right>Market</Th>
            <Th right>Edge</Th>
            <Th right>Stake</Th>
            <Th>Result</Th>
            <Th right>P&amp;L</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.event}-${r.fighter}`} className="border-t border-hairline">
              <Td className="whitespace-nowrap text-ink-2">{shortDate(r.date)}</Td>
              <Td className="whitespace-nowrap text-ink-2">{live ? r.event : eventName(r.event)}</Td>
              <Td className="whitespace-nowrap font-medium text-ink">{r.fighter}</Td>
              <Td className="whitespace-nowrap text-ink-2">{r.opponent}</Td>
              <Td right className="text-ink-2">{odds(r.odds)}</Td>
              <Td right className="text-ink-2">{pct(r.model_prob)}</Td>
              <Td right className="text-ink-2">{pct(r.market_prob)}</Td>
              <Td right className="text-ink-2">{signedPct(r.edge * 100)}</Td>
              <Td right className="text-ink-2">{r.stake}</Td>
              <Td className={`font-medium ${RESULT_STYLE[r.result]}`}>{r.result}</Td>
              <Td right className={`font-medium ${r.pnl == null ? "text-muted" : r.pnl >= 0 ? "text-up" : "text-down"}`}>
                {r.pnlText}
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Bets({ data, ledger }) {
  const [segment, setSegment] = useState("backtest");
  // `window` is renamed so it never shadows the browser global
  const { betting, bankroll, bets, window: span } = data;

  const backtestRows = [...bets].reverse().map((b) => ({
    ...b, stake: money(b.stake), pnlText: signedMoney(b.pnl),
  }));

  const graded = ledger.filter((e) => e.result !== "pending");
  const liveWins = graded.filter((e) => e.result === "win").length;
  const netPct = graded.reduce((sum, e) => sum + e.pnl_per_unit * e.stake_pct, 0);
  const liveRows = [...ledger]
    .sort((a, b) => (a.event_date < b.event_date ? 1 : -1))
    .map((e) => ({
      ...e,
      date: e.event_date,
      stake: `${e.stake_pct.toFixed(2)}%`,
      pnl: e.pnl_per_unit == null ? null : e.pnl_per_unit * e.stake_pct,
      pnlText: e.pnl_per_unit == null ? "pending" : signedPct(e.pnl_per_unit * e.stake_pct, 2),
    }));

  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-10 pt-20">
        <Eyebrow>Every bet, graded</Eyebrow>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">Bet log</h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          The backtest record replays the deployed model over {shortDate(span.start)} to {shortDate(span.end)}{" "}
          at closing odds from a $1,000 paper bankroll. The live record is every pick posted to members, settled
          once results land.
        </p>
        <div className="mt-8">
          <Segmented value={segment} onChange={setSegment} counts={{ backtest: bets.length, live: ledger.length }} />
        </div>
      </section>

      {segment === "backtest" ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Bets" value={betting.bets} sub={`${betting.favorites.total} favorites · ${betting.underdogs.total} underdogs`} />
            <StatTile label="Hit rate" value={pct(betting.hit)} sub={`${betting.favorites.won + betting.underdogs.won} winners`} />
            <StatTile label="Final paper bankroll" value={money(betting.final)} sub="from $1,000 at closing odds" />
            <StatTile
              label="Return"
              value={signedPct(betting.return_pct)}
              tone={betting.return_pct >= 0 ? "up" : "down"}
              sub={`${betting.max_drawdown_pct}% max drawdown`}
            />
          </section>
          <div className="mt-8 rounded-lg border border-hairline bg-surface p-5">
            <BankrollChart points={bankroll} />
          </div>
          <BetTable rows={backtestRows} live={false} />
        </>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Picks posted" value={ledger.length} sub={`${graded.length} graded · ${ledger.length - graded.length} pending`} />
            <StatTile label="Hit rate" value={graded.length ? pct(liveWins / graded.length) : "—"} sub={`${liveWins} winners of ${graded.length} graded`} />
            <StatTile
              label="Net, % of bankroll"
              value={graded.length ? signedPct(netPct, 2) : "—"}
              tone={netPct >= 0 ? "up" : "down"}
              sub="sum of stake % × payout on graded picks"
            />
            <StatTile label="Sizing" value="5% Kelly" sub="5% cap · no floor · 5% min edge" />
          </section>
          {ledger.length === 0 ? (
            <p className="mt-10 max-w-2xl text-ink-2">
              No live picks graded yet. Picks post to members before each card and land here once the results are in.
            </p>
          ) : (
            <BetTable rows={liveRows} live />
          )}
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Add the route**

In `frontend/src/App.js` add `import Bets from "./components/Bets";` and inside `<Routes>`:

```jsx
        <Route path="/bets" element={<Bets data={backtest} ledger={ledger} />} />
```

- [ ] **Step 5: Run the tests and build**

Run from `frontend/`:

```bash
CI=true npx react-scripts test --watchAll=false src/components/Bets.test.js
CI=true npm run build
```

Expected: 3 passed; `Compiled successfully.`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Bets.js frontend/src/components/Bets.test.js frontend/src/App.js
git commit -m "Rebuild the bet log from the backtest ledger and the live graded ledger

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: Methodology and Join pages

**Files:**
- Create: `frontend/src/components/Methodology.js`, `frontend/src/components/Join.js`
- Modify: `frontend/src/App.js` (add routes; drop the `ledger` prop from Home)
- Test: `frontend/src/components/Pages.test.js`

**Interfaces:**
- Consumes: `constants.js`, `format.js`.
- Produces: `Methodology({ data })`, `Join({ data })`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/Pages.test.js`:

```js
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Methodology from "./Methodology";
import Join from "./Join";
import { GITHUB_URL, MEMBERSHIP_URL } from "../constants";
import { backtestFixture as fx } from "../test/fixtures";

test("methodology explains the pipeline and links the source", () => {
  render(<MemoryRouter><Methodology data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("How the model works");
  expect(screen.getByText(/five-model LightGBM/i)).toBeInTheDocument();
  expect(screen.getByText(/women's bouts/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /GitHub/ })).toHaveAttribute("href", GITHUB_URL);
});

test("join page sends members to the paywall", () => {
  render(<MemoryRouter><Join data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Get the picks");
  expect(screen.getByRole("link", { name: "Join UFC Alpha" })).toHaveAttribute("href", MEMBERSHIP_URL);
  expect(screen.getByText(/legal gambling age/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/Pages.test.js`
Expected: FAIL, `Cannot find module './Methodology'`.

- [ ] **Step 3: Write Methodology.js**

Create `frontend/src/components/Methodology.js`:

```jsx
import React from "react";
import { GITHUB_URL } from "../constants";
import { pct } from "../format";

const Section = ({ eyebrow, title, children }) => (
  <section className="mt-16">
    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{eyebrow}</p>
    <h2 className="mt-2 font-display text-4xl font-bold leading-none tracking-wide text-ink">{title}</h2>
    <div className="mt-4 max-w-2xl space-y-4 text-ink-2">{children}</div>
  </section>
);

export default function Methodology({ data }) {
  // `window` is renamed so it never shadows the browser global
  const { coverage, metrics, window: span } = data;
  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-4 pt-20">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Methodology</p>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">How the model works</h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          A career-statistics model for UFC fights, built to be tested the hard way: on fights it has never seen,
          against the closing line. The code is public.
        </p>
      </section>

      <Section eyebrow="Data" title="Every fight since 1994">
        <p>
          Fight-level statistics are scraped from ufcstats.com: significant strikes by target and position,
          takedowns, submission attempts, reversals, control time, knockdowns, method and round of finish.
          Debut fighters have no history, so they are skipped rather than guessed.
        </p>
        <p>
          The cleaning step drops women's bouts, so the model never trains on or predicts them. Widening
          coverage is the largest open improvement.
        </p>
      </Section>

      <Section eyebrow="Features" title="180+ signals per fighter, frozen at fight time">
        <p>
          For each base statistic the pipeline derives per-minute rates, accuracy, differentials against the
          opponent, and career totals, then rolls them into weighted averages that favor recent fights. An ELO
          rating tracks quality of opposition. Height, reach, age and stance round it out.
        </p>
        <p>
          Every feature for a fight is computed from bouts that preceded it. Nothing from the fight itself or
          from later fights leaks in. Skipping this step is how a predictor reports 80% accuracy and then loses
          money.
        </p>
      </Section>

      <Section eyebrow="Model" title="A five-model LightGBM ensemble">
        <p>
          Five gradient-boosted tree models, each with its own Optuna-tuned hyperparameters, are averaged at
          inference. Training data is mirrored so that swapping the red and blue corners flips the answer
          exactly, and correlated features are pruned in pairs so the mirror stays intact.
        </p>
        <p>
          The output is a win probability. Judged on {metrics.n} out-of-sample fights it scores{" "}
          {pct(metrics.accuracy)} accuracy, {metrics.auc.toFixed(3)} AUC and a {metrics.brier.toFixed(3)} Brier
          score. Calibration, not accuracy, is what the retraining schedule protects.
        </p>
      </Section>

      <Section eyebrow="Evaluation" title="Walk-forward, never in-sample">
        <p>
          The published record trains on fights before {span.start}, then retrains on the production cadence
          as the window advances, so every prediction comes from a model that stopped learning before the fight.
          Of {coverage.fights_in_window} fights in the window, {coverage.scored} were scorable.
        </p>
        <p>
          Betting is replayed with the exact production sizing code: fractional Kelly at 5% of the criterion,
          capped at 5% of bankroll, no floor, and a 5-point minimum edge measured against the de-vigged closing
          price. The bet log shows every stake.
        </p>
      </Section>

      <Section eyebrow="Operations" title="Retrained twice a week">
        <p>
          A scheduled job scrapes new results, rebuilds every feature from scratch for ELO consistency, retrains
          the ensemble, and validates it on a chronological holdout before it can replace the previous models.
          The same job grades the public bet ledger.
        </p>
        <p>
          Everything described here is in the repository:{" "}
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="text-ink underline hover:text-accent">
            UFC Alpha on GitHub
          </a>
          .
        </p>
      </Section>
    </main>
  );
}
```

- [ ] **Step 4: Write Join.js**

Create `frontend/src/components/Join.js`:

```jsx
import React from "react";
import { Link } from "react-router-dom";
import { MEMBERSHIP_URL } from "../constants";
import { pct } from "../format";

export default function Join({ data }) {
  const { metrics, bands } = data;
  const top = bands[bands.length - 1];
  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-12 pt-20">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Membership</p>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">Get the picks</h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          The model that scored {pct(metrics.accuracy)} on {metrics.n} out-of-sample fights, and hit {pct(top.hit)}{" "}
          on its most confident calls, runs on every upcoming card. Members see its output before the fights.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          ["Every covered bout", "Win probability for each fight the model can score, with the de-vigged market probability beside it."],
          ["Edge and stake", "Which side clears the 5-point edge gate, and the fractional Kelly stake as a percent of bankroll."],
          ["Graded in public", "Every pick lands on the bet log once results are in. Wins and losses alike."],
        ].map(([title, body]) => (
          <div key={title} className="rounded-lg border border-hairline bg-surface p-6">
            <h2 className="font-display text-2xl font-bold tracking-wide text-ink">{title}</h2>
            <p className="mt-2 text-ink-2">{body}</p>
          </div>
        ))}
      </section>

      <section className="mt-16 rounded-lg border border-hairline bg-surface p-8 sm:p-12">
        <a
          href={MEMBERSHIP_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-block rounded-md bg-accent px-8 py-4 text-lg font-semibold text-white hover:bg-[#f04e43]"
        >
          Join UFC Alpha
        </a>
        <p className="mt-6 max-w-2xl text-sm text-ink-2">
          Picks are model output for informational purposes, not betting advice. Past performance does not
          guarantee future results. You must be of legal gambling age in your jurisdiction. Not sure yet? Read the{" "}
          <Link to="/results" className="text-ink underline hover:text-accent">full results</Link> first.
        </p>
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Final App.js**

Replace `frontend/src/App.js` in full:

```jsx
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import Home from "./components/Home";
import Results from "./components/Results";
import Bets from "./components/Bets";
import Methodology from "./components/Methodology";
import Join from "./components/Join";
import backtest from "./data/backtest.json";
import ledger from "./data/ledger.json";

const App = () => (
  <Router>
    <ScrollToTop />
    <div className="min-h-screen bg-ground font-body text-ink">
      <Navbar />
      <Routes>
        <Route path="/" element={<Home data={backtest} />} />
        <Route path="/results" element={<Results data={backtest} />} />
        <Route path="/bets" element={<Bets data={backtest} ledger={ledger} />} />
        <Route path="/methodology" element={<Methodology data={backtest} />} />
        <Route path="/join" element={<Join data={backtest} />} />
      </Routes>
      <Footer />
    </div>
  </Router>
);

export default App;
```

- [ ] **Step 6: Run every frontend test and the build**

Run from `frontend/`:

```bash
CI=true npx react-scripts test --watchAll=false
CI=true npm run build
```

Expected: all suites pass; `Compiled successfully.`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Methodology.js frontend/src/components/Join.js \
  frontend/src/components/Pages.test.js frontend/src/App.js
git commit -m "Add the methodology and membership pages and wire every route

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 12: Docs, browser check, final verification

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** none new.

- [ ] **Step 1: Update CLAUDE.md**

In `## Project Overview`, change `Website: http://betufc.ca/` to `Website: https://ufcalpha.com/ (frontend on Cloudflare Pages, API on Render)`.

Under `### Flask API & Frontend`, replace the block with:

```bash
python app.py                               # Start Flask server (localhost:5000)
cd frontend && npm start                    # Start React dev server (localhost:3000)
cd frontend && npm run build                # Production build
cd frontend && CI=true npx react-scripts test --watchAll=false   # Frontend tests

# Public site data: replay the walk-forward cache into the JSON the frontend bundles,
# then commit and push so Cloudflare Pages rebuilds.
python testing/export_site_data.py
git add frontend/src/data && git commit -m "Refresh site data" && git push
```

Under `### Data Files`, add:

```
- `data/bet_ledger.json` — live picks written by `predict_event.py --odds`, graded by
  `auto_retrain.py`; copied into the site by `testing/export_site_data.py`
```

Under `### Auto-Retraining System`, change step 2 to read:

```
2. New rows prepended to `fight_details_date.csv` (backup written first); pending entries in
   `data/bet_ledger.json` are graded against the new results (a grading error is logged, never fatal)
```

Replace the `## React Frontend Structure` section with:

```
## React Frontend Structure

The public site is static: every page reads `frontend/src/data/backtest.json` and
`ledger.json`, which `testing/export_site_data.py` writes. No public page calls the Flask
API. Brand and paywall constants live in `frontend/src/constants.js` (`SITE_NAME`,
`MEMBERSHIP_URL`).

Components in `frontend/src/components/`:
- `Home.js` — landing page: headline stats, how it works, calibration proof, market table, membership CTA
- `Results.js` — the full walk-forward report
- `Bets.js` — bet log with Backtest / Live segments
- `Methodology.js` — pipeline explainer
- `Join.js` — membership page
- `Navbar.js`, `Footer.js`, `StatTile.js`, `ScrollToTop.js` — chrome
- `charts/` — recharts wrappers: `CalibrationChart`, `MonthlyAccuracyChart`, `BankrollChart`, shared `chartTheme`
- `FightersPage.js` / `FightersDropdown.js` — unrouted legacy components
```

- [ ] **Step 2: Run the full Python suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: every new test passes; leakage tests pass or skip.

- [ ] **Step 3: Look at the site in a browser**

Run from `frontend/`: `npm start`, then open `http://localhost:3000/`, `/results`, `/bets` (both segments), `/methodology`, `/join`. Check: no console errors, fonts load, charts render with visible axis labels, "View as table" expands, the nav button opens `MEMBERSHIP_URL`, nothing scrolls horizontally on a 390px-wide viewport (use devtools device toolbar). Stop the dev server.

- [ ] **Step 4: Final build and status**

Run from `frontend/`: `CI=true npm run build`
Expected: `Compiled successfully.`

Run from the repo root: `git status --short`
Expected: only `CLAUDE.md` modified (plus the pre-existing untracked files `CODE_REVIEW.md`, `test_results/.lastyear_tier0_cache/`, `test_results/improvement_review_2026-08-31.md`, `test_results/one_year_oos_report.html`, which are not part of this work).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "Document the static site data flow and the bet ledger

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Plan self-review

**Spec coverage.** Part A (export, dataclasses, golden test): Tasks 1-2, 5. Part B (ledger, hooks, tests): Tasks 3-4. Part C (stack, files, design system, five pages, footer, claims policy, frontend tests): Tasks 6-11. Part D (refresh workflow in CLAUDE.md): Task 12. Deletions listed in the spec: Task 6 Step 9. Out-of-scope items are untouched.

**Placeholders.** None. The only "placeholder" is `MEMBERSHIP_URL`'s value, which the spec requires to be a placeholder Alex replaces.

**Type consistency.** `write_outputs(rows, event, bets, event_date)` in Task 4 matches its tests. `bet_ledger.record(event, event_date, generated, bets, path=)` and `grade(results_csv=, path=, now=)` match Tasks 3-4. Frontend components take `data` (backtest payload) and `Bets` additionally takes `ledger`; `App.js` in Task 11 matches. Chart props `bands`, `monthly`/`overall`, `points` match Tasks 7-10. Table captions `"Calibration by confidence band"`, `"Accuracy by month"`, `"Bankroll at month end"` match between Task 7 and Task 9's test.
