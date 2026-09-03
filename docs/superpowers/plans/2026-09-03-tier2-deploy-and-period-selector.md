# Tier-2 Deploy and Period Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the tier-2 model with a +200 longshot cap, rebuild the walk-forward record over 2024-01 → 2026-08 from the merged pipeline, and let the public site aggregate any time window in the browser, defaulting to the full range.

**Architecture:** The tier-2 branch merges into the working branch and the retrain pipeline regenerates features, models and calibrator under the merged code. A cache-builder script produces one full-range walk-forward prediction cache. The export emits every odds-file fight as a window-independent row plus a Python-computed summary for the default window. A JS aggregator recomputes every section for a URL-selected window, and a parity test pins it to the Python summary.

**Tech Stack:** Python 3.9 (stdlib dataclasses, scikit-learn, pytest), React 18 / CRA 5 / react-router 6 / Tailwind 3 / recharts 2.15.

**Spec:** `docs/superpowers/specs/2026-09-03-tier2-deploy-and-period-selector-design.md`

## Global Constraints

- Work on branch `tier2-site-periods` (already created from `main`). Repo root `/Users/alex.xu/Desktop/UFCFightPredictor`. Python via `.venv/bin/python`; pytest via `.venv/bin/python -m pytest`. npm from `frontend/`; `CI=true` makes warnings fail the build.
- The tier-2 worktree is `/Users/alex.xu/Desktop/UFCFightPredictor/.claude/worktrees/tier2-model-upgrades` on branch `worktree-tier2-model-upgrades`.
- Production betting doctrine after this plan: blend `w=0.8`, edge gate `0.05` de-vigged, Kelly fraction `0.05`, cap `0.05`, no floor, `dog_multiplier=1.0`, **`max_dog_odds=200`** (skip a pick priced strictly greater than +200). `betting_math.decide_bet` defaults are the single source; the export reads them by introspection.
- Full-range window: `2024-01-01` → `2026-08-30`; cache `test_results/.tier2_full_cache/`; expected retrain dates `2024-01-01, 2024-07-13, 2025-01-11, 2025-07-12, 2026-01-24, 2026-07-25`.
- Per-fight `winner` vocabulary: `"f1" | "f2" | "push" | "unknown"`; `"unknown"` may appear only on unscored rows, and the export raises if a scored row has it.
- Claims policy from the prior spec still binds: every statistic in copy is interpolated from data (now including the doctrine numbers, from `config`); any return shows its bet count and drawdown; "$1,000 paper bankroll at closing odds" labeling; no forward-looking claims.
- Long-running commands (the retrain, the cache build) exceed the 10-minute tool limit: run them with the Bash tool's `run_in_background: true`, redirecting output to a log file, then poll the log with short foreground commands (`tail`), each well under 10 minutes. Never `sleep` longer than 240 seconds in one call.
- Commit after every task with the trailer:

  ```
  Assisted by AI

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

- Do not push. Do not open a PR.

---

## File map

**Python**
- Modify: `betting_math.py` (cap knob). Create: `tests/test_betting_math.py`.
- Create: `testing/build_walk_forward_cache.py`.
- Modify: `testing/export_site_data.py` (v2 payload), `tests/test_export_site_data.py`.
- Generated/committed: `data/*`, `saved_models/*`, `saved_preprocessing/*` (retrain), `test_results/.tier2_full_cache/pred_*.csv` (6 files), `frontend/src/data/backtest.json`. Deleted from git: `test_results/.lastyear_tier0_cache/`.

**Frontend**
- Create: `frontend/src/aggregate.js`, `frontend/src/aggregate.test.js`, `frontend/src/components/PeriodFilter.js`, `frontend/src/components/PeriodFilter.test.js`.
- Modify: `frontend/src/App.js`, `frontend/src/test/fixtures.js`, `Home.js`, `Results.js`, `Results.test.js`, `Bets.js`, `Methodology.js`, `Join.js`.

**Docs**: `CLAUDE.md`.

---

### Task 1: Commit the tier-2 backtest twin and merge the branch

**Files:**
- Worktree: commit `testing/ml_alpha_testing.py` (modified) and `testing/devig_cap_experiment.py` (untracked) on `worktree-tier2-model-upgrades`; restore its stray `data/*` and `test_results/*.txt` modifications.
- Main checkout: merge `worktree-tier2-model-upgrades` into `tier2-site-periods`.

**Interfaces:**
- Produces: `calibration.py` with `calibrate(p)`, calibrator-aware `load_ensemble.py`/`predict_event.py`/`ml_web.py`, seed-diverse `ml_ensemble.py`, tier-2 `saved_models/*.joblib`, `saved_preprocessing/calibrator.joblib`, and a backtest twin `testing/ml_alpha_testing.main(split_date)` that trains seed-diverse members and fits a per-split calibrator. Later tasks call `ml_alpha_testing.main`.

- [ ] **Step 1: Inspect the worktree**

Run:
```bash
git -C /Users/alex.xu/Desktop/UFCFightPredictor/.claude/worktrees/tier2-model-upgrades status --short
git -C /Users/alex.xu/Desktop/UFCFightPredictor/.claude/worktrees/tier2-model-upgrades diff --stat -- testing/ml_alpha_testing.py
```
Expected: ` M testing/ml_alpha_testing.py` (about 39 insertions), `?? testing/devig_cap_experiment.py`, plus modified `data/*` files and `test_results/testing_time_period*.txt`.

- [ ] **Step 2: Commit the twin, discard the stray outputs**

```bash
WT=/Users/alex.xu/Desktop/UFCFightPredictor/.claude/worktrees/tier2-model-upgrades
git -C $WT checkout -- data test_results/testing_time_period.txt test_results/testing_time_period_results.txt
git -C $WT add testing/ml_alpha_testing.py testing/devig_cap_experiment.py
git -C $WT commit -m "Commit the tier-2 backtest twin and the de-vig/cap experiment

The twin trains seed-diverse members and fits a per-split out-of-fold
temperature calibrator, matching the deployed ensemble.

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
git -C $WT status --short
```
Expected: the last command prints nothing tracked (untracked caches under `test_results/` may remain).

- [ ] **Step 3: Merge into the working branch**

From the repo root, on `tier2-site-periods`:
```bash
git merge --no-edit worktree-tier2-model-upgrades
git log --oneline -3
ls saved_preprocessing/ && .venv/bin/python -c "import calibration; print('calibrate ok', calibration.calibrate(0.7))"
```
Expected: a merge commit with no conflicts; `calibrator.joblib` listed; the import prints a calibrated probability.

- [ ] **Step 4: Run the Python suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass (36 tests; the golden test still targets the old tier-0 cache, which still exists at this point).

No separate commit: the merge commit is the task's commit.

---

### Task 2: Regenerate features, models and calibrator under the merged code

**Files:**
- Generated: `data/detailed_fights.csv`, `data/detailed_fighter_stats.csv`, `data/predicted_data.json` and siblings, `saved_models/lgbm_model_*.joblib`, `saved_preprocessing/*`.

**Interfaces:**
- Consumes: `auto_retrain.py --skip-scrape` (existing).
- Produces: a consistent tier-2 deployment on this branch; later tasks train walk-forward models from the regenerated `data/detailed_fights.csv`.

- [ ] **Step 1: Start the retrain in the background**

Run with `run_in_background: true`:
```bash
cd /Users/alex.xu/Desktop/UFCFightPredictor && .venv/bin/python auto_retrain.py --skip-scrape > /tmp/tier2-retrain.log 2>&1
```

- [ ] **Step 2: Poll until it finishes**

Every few minutes: `tail -5 /tmp/tier2-retrain.log`. Finish when the log shows `STEP 6: NOTIFICATION` followed by `✓ Auto-retraining success` and a `holdout accuracy` figure, or `✗ Auto-retraining FAILED`. Record the holdout accuracy line. If it failed, report BLOCKED with the last 30 log lines; do not retry.

- [ ] **Step 3: Confirm what changed and that the gate passed**

```bash
grep -E "holdout accuracy|temperature calibrator|rejected|restored" /tmp/tier2-retrain.log
git status --short | grep -v '^??'
```
Expected: holdout accuracy ≥ 0.60 and a `temperature calibrator: a=...` line; modified tracked files under `data/`, `saved_models/`, `saved_preprocessing/`. Backups under `saved_models/backup_*/` are gitignored.

- [ ] **Step 4: Run the suite and commit**

```bash
.venv/bin/python -m pytest tests/ -q
git add -u data saved_models saved_preprocessing
git commit -m "Retrain the tier-2 ensemble and calibrator on the merged pipeline

<paste the holdout accuracy line and the temperature calibrator line>

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: The +200 cap in betting_math

**Files:**
- Modify: `betting_math.py:49-79`
- Test: `tests/test_betting_math.py`

**Interfaces:**
- Produces: `decide_bet(..., dog_multiplier=1.0, max_dog_odds=200, bankroll)`; returns `None` when the pick's price is greater than `max_dog_odds`; `max_dog_odds=None` disables the cap.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_betting_math.py`:
```python
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import betting_math  # noqa: E402


def bet(odds1, odds2, model_p1, **kw):
    return betting_math.decide_bet(model_p1, None, odds1, odds2, bankroll=1000.0, **kw)


def test_a_plus_200_pick_is_still_bet():
    # model 0.60 on a +200 dog: blend ~0.54 beats the de-vigged 0.32, Kelly positive
    result = bet(200, -250, 0.60)
    assert result is not None and result["side"] == 1


def test_a_pick_longer_than_plus_200_is_skipped():
    assert bet(201, -250, 0.60) is None


def test_the_cap_can_be_disabled():
    assert bet(201, -250, 0.60, max_dog_odds=None) is not None


def test_favorites_are_unaffected_by_the_cap():
    result = bet(-150, 130, 0.70)
    assert result is not None and result["side"] == 1


def test_default_cap_is_200():
    import inspect
    assert inspect.signature(betting_math.decide_bet).parameters["max_dog_odds"].default == 200
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_betting_math.py -v`
Expected: the +201 test fails (a bet is returned) and the disable/default tests fail with `TypeError`/`KeyError`.

- [ ] **Step 3: Add the knob**

In `betting_math.py`, change the signature to
```python
def decide_bet(model_p1, model_p2, odds1, odds2, *, blend_w=0.8, min_edge=0.05,
               fraction=0.05, cap=0.05, dog_multiplier=1.0, max_dog_odds=200, bankroll):
```
append to the docstring, before the closing quotes:
```
    max_dog_odds skips a pick priced strictly longer than +N (default +200, None
    disables it). The 2024-26 walk-forward study found picks beyond +200 lost at
    flat stakes (13 bets, 2-11); the cap removes the segment where the model is
    most often blind.
```
and insert, right after the line `prob, market_prob, odds = (p1, market1, odds1) if side == 1 else (p2, market2, odds2)`:
```python
    if max_dog_odds is not None and odds > max_dog_odds:
        return None
```
Update the module docstring's doctrine sentence to end `... and a betting probability that blends model and market at w=0.8. Picks priced longer than +200 are skipped.`

- [ ] **Step 4: Run the tests and the suite**

Run: `.venv/bin/python -m pytest tests/test_betting_math.py tests/ -q`
Expected: all pass. The tier-0 golden test still passes because none of its 58 bets was priced above +200 (the export's synthetic tests are unaffected too).

- [ ] **Step 5: Commit**

```bash
git add betting_math.py tests/test_betting_math.py
git commit -m "Skip picks priced longer than +200 in decide_bet

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Cache builder and the full-range cache

**Files:**
- Create: `testing/build_walk_forward_cache.py`
- Generated: `test_results/.tier2_full_cache/pred_{2024-01-01,2024-07-13,2025-01-11,2025-07-12,2026-01-24,2026-07-25}.csv`
- Delete from git: `test_results/.lastyear_tier0_cache/`

**Interfaces:**
- Consumes: `testing.testing_time_period.process_dates`, `testing.ml_alpha_testing.main` (tier-2 twin from Task 1).
- Produces: the cache directory Task 5's export reads.

- [ ] **Step 1: Write the builder**

Create `testing/build_walk_forward_cache.py`:
```python
"""Build or extend a walk-forward prediction cache for the site export.

Replays testing_time_period.process_dates over a window, training the backtest
twin (testing/ml_alpha_testing.py) once per retrain date and saving each
retrain's data/predicted_results.csv as <cache>/pred_<date>.csv. Existing files
are reused, so extending a window only trains the missing dates.

    python testing/build_walk_forward_cache.py --start 2024-01-01 --end 2026-08-30 \
        --cache test_results/.tier2_full_cache
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "testing"))
os.chdir(ROOT)  # process_dates and ml_alpha_testing use repo-relative paths

import testing_time_period as ttp  # noqa: E402
import ml_alpha_testing  # noqa: E402

# fraction, cap, (inert legacy slot), min edge, blend weight: the production config
PRODUCTION_STRATEGY = [0.05, 0.05, 0, 0.05, 0.8]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD, first training cutoff")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD, last fight date")
    ap.add_argument("--cache", required=True, help="directory of pred_<date>.csv files")
    args = ap.parse_args(argv)
    os.makedirs(args.cache, exist_ok=True)
    retrains = []

    def cached_train(date):
        target = os.path.join(args.cache, f"pred_{date}.csv")
        if os.path.exists(target):
            print(f"reusing {target}", flush=True)
        else:
            print(f"training walk-forward model for {date} ...", flush=True)
            ml_alpha_testing.main(date)
            shutil.copy(os.path.join("data", "predicted_results.csv"), target)
        shutil.copy(target, os.path.join("data", "predicted_results.csv"))
        retrains.append(date)

    ttp.train_ml = cached_train
    ttp.process_dates(args.start, args.end, PRODUCTION_STRATEGY)
    print("retrain dates:", ", ".join(retrains))
    print(f"final bankroll ${ttp.bankroll:,.2f} over {ttp.favourites + ttp.underdogs} bets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Build the cache in the background**

Run with `run_in_background: true`:
```bash
cd /Users/alex.xu/Desktop/UFCFightPredictor && .venv/bin/python testing/build_walk_forward_cache.py --start 2024-01-01 --end 2026-08-30 --cache test_results/.tier2_full_cache > /tmp/tier2-cache.log 2>&1
```
Poll with `tail -3 /tmp/tier2-cache.log` every few minutes. Six trainings take roughly 30-60 minutes. Finish when the log shows `retrain dates: 2024-01-01, 2024-07-13, 2025-01-11, 2025-07-12, 2026-01-24, 2026-07-25` and a final bankroll line. If the dates differ, stop and report BLOCKED with the log.

- [ ] **Step 3: Discard the replay's side effects, keep the cache**

`process_dates` overwrites tracked files. Run:
```bash
git checkout -- test_results/testing_time_period.txt test_results/testing_time_period_results.txt data/bankroll_plot.png data/predicted_results.csv
ls -la test_results/.tier2_full_cache/
git status --short | grep -v '^??' || echo "only the new cache is pending"
```
Expected: six `pred_*.csv` files; no modified tracked files.

- [ ] **Step 4: Swap the caches in git and commit**

```bash
git rm -r -q test_results/.lastyear_tier0_cache
git add -f test_results/.tier2_full_cache/pred_2024-01-01.csv test_results/.tier2_full_cache/pred_2024-07-13.csv test_results/.tier2_full_cache/pred_2025-01-11.csv test_results/.tier2_full_cache/pred_2025-07-12.csv test_results/.tier2_full_cache/pred_2026-01-24.csv test_results/.tier2_full_cache/pred_2026-07-25.csv
git add testing/build_walk_forward_cache.py
git commit -m "Add the walk-forward cache builder and the 2024-26 tier-2 cache

Replaces the one-year tier-0 cache as the site's source of numbers.

<paste the final bankroll line>

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```
The old golden test now skips (its cache is gone); Task 5 repoints it.

---

### Task 5: Export v2

**Files:**
- Modify: `testing/export_site_data.py`, `tests/test_export_site_data.py`
- Generated: `frontend/src/data/backtest.json`

**Interfaces:**
- Consumes: `betting_math.decide_bet` defaults (Task 3), `.tier2_full_cache` (Task 4).
- Produces: `build_site_payload(caches, odds_csv, start, end) -> SitePayload`; `fight_rows(rows, caches) -> list[FightRow]`; `config_from_betting_math() -> Config`; dataclasses `Range, Config, DefaultWindow, Bet, FightRow, Summary, SitePayload`; JSON shape per spec C1. `build_payload` and every v1 section function stay unchanged.

- [ ] **Step 1: Write the failing tests**

In `tests/test_export_site_data.py`, extend `ODDS_ROWS` with a fourth fight the cache does not know and a fifth that is a draw the cache does know:
```python
ODDS_ROWS = [
    ("ufc-1", "Jan 04 2025", "A", "B", "A", "-150", "+130"),
    ("ufc-1", "Jan 04 2025", "C", "D", "D", "+200", "-240"),
    ("ufc-fight-night-february-01-2025", "Feb 01 2025", "E", "F", "F", "-", "-"),
    ("ufc-fight-night-february-01-2025", "Feb 01 2025", "G", "H", "Gee Aitch", "-110", "-110"),
    ("ufc-2", "Mar 01 2025", "A", "B", "draw/no contest", "-150", "+130"),
]
```
The existing tests stay valid: G/H is unscored (not in the cache), and the A/B draw is a scored, priced push, which is excluded from `decided` metrics and bands, gives no bet in `betting` ... except it does: `decide_bet` still fires on the push (blend 0.684 vs de-vigged 0.58), so the bet is recorded with result `push`, pnl 0. Update these existing assertions:
- in `test_bet_replay_matches_betting_math`: `assert len(payload.bets) == 2` and `assert [b.result for b in payload.bets] == ["win", "push"]`; `payload.betting.bets == 2`; `payload.betting.hit == 0.5`; `payload.betting.favorites == esd.SideRecord(won=1, total=2)`; bankroll points become `[final, final, final]`.
- in `test_coverage_and_accuracy_average_both_orientations`: `esd.Coverage(fights_in_window=5, scored=3, with_odds=2)`.

Then append:
```python
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
```
Replace the old `test_main_writes_json_and_empty_ledger` with `test_main_writes_v2_json` above (the ledger-copy assertion moves in: add `assert json.load(open(tmp_path / "site" / "ledger.json")) == []`).

Repoint the golden test: `CACHE = os.path.join(ROOT, "test_results", ".tier2_full_cache")` and keep everything else (it uses `esd.DEFAULT_START/END`).

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_export_site_data.py -v`
Expected: the new tests fail with `AttributeError: module 'export_site_data' has no attribute 'build_site_payload'`; the updated v1 assertions fail on the new fixture rows until Step 3.

- [ ] **Step 3: Implement v2 in `testing/export_site_data.py`**

a) Defaults and config. Replace the constants block
```python
BLEND_W = 0.8
MIN_EDGE = 0.05
KELLY_FRACTION = 0.05
KELLY_MAX = 0.05
```
with
```python
import inspect  # (add to the imports at the top)

_DECIDE_BET_DEFAULTS = {k: p.default for k, p in inspect.signature(betting_math.decide_bet).parameters.items()
                        if p.default is not inspect.Parameter.empty}
BLEND_W = _DECIDE_BET_DEFAULTS["blend_w"]
MIN_EDGE = _DECIDE_BET_DEFAULTS["min_edge"]
KELLY_FRACTION = _DECIDE_BET_DEFAULTS["fraction"]
KELLY_MAX = _DECIDE_BET_DEFAULTS["cap"]
MAX_DOG_ODDS = _DECIDE_BET_DEFAULTS["max_dog_odds"]
```
and change the defaults:
```python
DEFAULT_CACHE = os.path.join(ROOT, "test_results", ".tier2_full_cache")
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2026-08-30"
```

b) New dataclasses, after `BacktestPayload`:
```python
@dataclass
class Range:
    start: str
    end: str
    retrains: List[str]


@dataclass
class Config:
    blend_w: float
    min_edge: float
    kelly_fraction: float
    kelly_cap: float
    max_dog_odds: Optional[int]
    start_bankroll: float
    flat_stake: float


@dataclass
class DefaultWindow:
    start: str
    end: str


@dataclass
class Bet:
    """The production decision for one fight, independent of bankroll: stake_frac is
    stake / bankroll and payout_mult is profit per $1 staked."""
    side: int
    odds: int
    prob: float
    market_prob: float
    edge: float
    kc: float
    stake_frac: float
    payout_mult: float


@dataclass
class FightRow:
    date: str
    event: str
    f1: str
    f2: str
    winner: str            # "f1" | "f2" | "push" | "unknown" (unknown only when unscored)
    model_p1: Optional[float]
    market_p1: Optional[float]
    odds1: Optional[int]
    odds2: Optional[int]
    bet: Optional[Bet]


@dataclass
class Summary:
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
class SitePayload:
    generated: str
    range: Range
    config: Config
    default_window: DefaultWindow
    summary: Summary
    fights: List[FightRow]
```

c) New functions, after `build_payload`:
```python
def config_from_betting_math() -> Config:
    return Config(blend_w=BLEND_W, min_edge=MIN_EDGE, kelly_fraction=KELLY_FRACTION,
                  kelly_cap=KELLY_MAX, max_dog_odds=MAX_DOG_ODDS,
                  start_bankroll=START_BANKROLL, flat_stake=FLAT_STAKE)


def fight_rows(rows: List[dict], caches) -> List[FightRow]:
    """One row per odds-file fight; unscored and unpriced fights carry nulls."""
    out = []
    for row in rows:
        iso = datetime.strptime(row["event_date"], "%b %d %Y").strftime("%Y-%m-%d")
        table = cache_for(caches, iso)
        f1, f2 = row["fighter1_name"], row["fighter2_name"]
        p_ab, p_ba = table.get((f1, f2)), table.get((f2, f1))
        model_p1 = None if p_ab is None or p_ba is None else (p_ab + (1 - p_ba)) / 2
        odds1, odds2 = parse_odds(row["fighter1_odds"]), parse_odds(row["fighter2_odds"])
        market_p1 = None
        if odds1 is not None and odds2 is not None:
            market_p1, _ = betting_math.devig(betting_math.american_to_prob(odds1),
                                              betting_math.american_to_prob(odds2))
        name = row["winner_name"]
        winner = "f1" if name == f1 else "f2" if name == f2 else "push" if name == "draw/no contest" else "unknown"
        if winner == "unknown" and model_p1 is not None:
            raise SystemExit(f"scored fight {f1} vs {f2} on {iso} has an unrecognized winner {name!r}")
        bet = None
        if model_p1 is not None and market_p1 is not None:
            decision = betting_math.decide_bet(model_p1, None, odds1, odds2, blend_w=BLEND_W,
                                               min_edge=MIN_EDGE, fraction=KELLY_FRACTION,
                                               cap=KELLY_MAX, bankroll=1.0)
            if decision is not None:
                odds = odds1 if decision["side"] == 1 else odds2
                bet = Bet(side=decision["side"], odds=odds, prob=round(decision["prob"], 4),
                          market_prob=round(decision["market_prob"], 4), edge=round(decision["edge"], 4),
                          kc=round(decision["kc"], 4), stake_frac=decision["stake"],
                          payout_mult=payout(odds, 1.0))
        out.append(FightRow(date=iso, event=row["event_name"], f1=f1, f2=f2, winner=winner,
                            model_p1=model_p1, market_p1=market_p1, odds1=odds1, odds2=odds2, bet=bet))
    return out


def build_site_payload(caches, odds_csv: str, start: str, end: str) -> SitePayload:
    v1 = build_payload(caches, odds_csv, start, end)
    rows = read_window(odds_csv, datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d"))
    summary = Summary(coverage=v1.coverage, metrics=v1.metrics, bands=v1.bands, monthly=v1.monthly,
                      market=v1.market, flat=v1.flat, betting=v1.betting, bankroll=v1.bankroll, bets=v1.bets)
    return SitePayload(generated=v1.generated,
                       range=Range(start=start, end=end, retrains=v1.window.retrains),
                       config=config_from_betting_math(),
                       default_window=DefaultWindow(start=start, end=end),
                       summary=summary, fights=fight_rows(rows, caches))
```
`decide_bet(..., bankroll=1.0)` returns `stake = min(fraction × kc, cap)`, which is the stake fraction. Because `decide_bet` now applies the cap by default, `replay_bets` (used by `build_payload`) inherits it too, so the summary and the rows agree.

d) In `main`, replace `payload = build_payload(...)` with `payload = build_site_payload(...)`, dump `asdict(payload)`, and adjust the summary prints to read `payload.summary.metrics` / `payload.summary.betting`; add a line `print(f"{len(payload.fights)} fight rows · {payload.range.start} → {payload.range.end} · retrains {', '.join(payload.range.retrains)}")`.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_export_site_data.py -v`
Expected: all pass, including the golden test against `.tier2_full_cache` (about 1,450 fights; a few seconds).

- [ ] **Step 5: Run the export and inspect**

```bash
.venv/bin/python testing/export_site_data.py
.venv/bin/python - <<'EOF'
import json
d = json.load(open("frontend/src/data/backtest.json"))
s = d["summary"]
print(d["range"], d["config"])
print(s["coverage"], s["metrics"])
print({k: v for k, v in s["betting"].items() if k not in ("favorites", "underdogs")})
print("fights:", len(d["fights"]), "| scored:", sum(f["model_p1"] is not None for f in d["fights"]),
      "| with bets:", sum(f["bet"] is not None for f in d["fights"]),
      "| unknown winners:", sum(f["winner"] == "unknown" for f in d["fights"]))
print("size KB:", round(__import__("os").path.getsize("frontend/src/data/backtest.json") / 1024))
EOF
```
Record the printed lines. Expected: six retrains, roughly 750 scored fights, `max_dog_odds: 200`, a positive return, and no bare `NaN` in the file (`grep -c NaN frontend/src/data/backtest.json` prints 0).

- [ ] **Step 6: Commit**

```bash
git add testing/export_site_data.py tests/test_export_site_data.py frontend/src/data/backtest.json frontend/src/data/ledger.json
git commit -m "Export per-fight rows, config and a default-window summary over 2024-26

<paste the export's printed summary lines>

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Browser-side aggregation

**Files:**
- Create: `frontend/src/aggregate.js`, `frontend/src/aggregate.test.js`

**Interfaces:**
- Consumes: `frontend/src/data/backtest.json` v2 (Task 5).
- Produces: `aggregate(fights, start, end, config)` returning `{coverage, metrics, bands, monthly, market, flat, betting, bankroll, bets}` in the v1 summary shape; `windowRetrains(range, start, end)`; `presets(range)`; `clampWindow(range, from, to, fallback)`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/aggregate.test.js`:
```js
import backtest from "./data/backtest.json";
import { aggregate, clampWindow, presets, windowRetrains } from "./aggregate";

const CONFIG = { blend_w: 0.8, min_edge: 0.05, kelly_fraction: 0.05, kelly_cap: 0.05, max_dog_odds: 200, start_bankroll: 1000, flat_stake: 10 };

const close = (a, b, tol) => Math.abs(a - b) <= tol;

test("aggregate reproduces the Python summary for the default window", () => {
  const { start, end } = backtest.default_window;
  const js = aggregate(backtest.fights, start, end, backtest.config);
  const py = backtest.summary;
  expect(js.coverage).toEqual(py.coverage);
  ["accuracy", "auc", "log_loss", "brier"].forEach((k) => expect(close(js.metrics[k], py.metrics[k], 1e-4)).toBe(true));
  expect(js.metrics.n).toBe(py.metrics.n);
  py.bands.forEach((b, i) => {
    expect(js.bands[i].label).toBe(b.label);
    expect(js.bands[i].n).toBe(b.n);
    if (b.n) { expect(close(js.bands[i].stated, b.stated, 1e-4)).toBe(true); expect(close(js.bands[i].hit, b.hit, 1e-4)).toBe(true); }
  });
  expect(js.monthly.map((m) => [m.month, m.n])).toEqual(py.monthly.map((m) => [m.month, m.n]));
  py.monthly.forEach((m, i) => expect(close(js.monthly[i].hit, m.hit, 1e-4)).toBe(true));
  py.market.rows.forEach((r, i) => {
    expect(js.market.rows[i].name).toBe(r.name);
    ["accuracy", "auc", "log_loss", "brier"].forEach((k) => expect(close(js.market.rows[i][k], r[k], 1e-4)).toBe(true));
  });
  expect(js.market.agree.n).toBe(py.market.agree.n);
  expect(close(js.market.agree.hit, py.market.agree.hit, 1e-4)).toBe(true);
  expect(js.market.disagree.n).toBe(py.market.disagree.n);
  expect(close(js.flat.market_favorite_per_bet, py.flat.market_favorite_per_bet, 1e-4)).toBe(true);
  expect(close(js.flat.model_pick_per_bet, py.flat.model_pick_per_bet, 1e-4)).toBe(true);
  expect(js.betting.bets).toBe(py.betting.bets);
  expect(js.betting.favorites).toEqual(py.betting.favorites);
  expect(js.betting.underdogs).toEqual(py.betting.underdogs);
  expect(close(js.betting.final, py.betting.final, 0.005)).toBe(true);
  expect(close(js.betting.hit, py.betting.hit, 1e-4)).toBe(true);
  expect(close(js.betting.max_drawdown_pct, py.betting.max_drawdown_pct, 0.05)).toBe(true);
  expect(close(js.betting.low, py.betting.low, 0.005)).toBe(true);
  expect(js.bankroll.length).toBe(py.bankroll.length);
  py.bankroll.forEach((p, i) => expect(close(js.bankroll[i].bankroll, p.bankroll, 0.005)).toBe(true));
  expect(js.bets.length).toBe(py.bets.length);
  py.bets.forEach((b, i) => {
    expect(js.bets[i].fighter).toBe(b.fighter);
    expect(js.bets[i].result).toBe(b.result);
    expect(close(js.bets[i].stake, b.stake, 0.005)).toBe(true);
    expect(close(js.bets[i].pnl, b.pnl, 0.005)).toBe(true);
    expect(close(js.bets[i].bankroll_after, b.bankroll_after, 0.005)).toBe(true);
  });
});

const FIGHTS = [
  { date: "2025-01-04", event: "ufc-1", f1: "A", f2: "B", winner: "f1", model_p1: 0.71, market_p1: 0.58, odds1: -150, odds2: 130,
    bet: { side: 1, odds: -150, prob: 0.684, market_prob: 0.58, edge: 0.104, kc: 0.21, stake_frac: 0.0105, payout_mult: 100 / 150 } },
  { date: "2025-01-04", event: "ufc-1", f1: "C", f2: "D", winner: "f2", model_p1: 0.39, market_p1: 0.32, odds1: 200, odds2: -240, bet: null },
  { date: "2025-02-01", event: "ufc-fn", f1: "E", f2: "F", winner: "f2", model_p1: 0.56, market_p1: null, odds1: null, odds2: null, bet: null },
  { date: "2025-02-01", event: "ufc-fn", f1: "G", f2: "H", winner: "unknown", model_p1: null, market_p1: 0.5, odds1: -110, odds2: -110, bet: null },
  { date: "2025-03-01", event: "ufc-2", f1: "A", f2: "B", winner: "push", model_p1: 0.71, market_p1: 0.58, odds1: -150, odds2: 130,
    bet: { side: 1, odds: -150, prob: 0.684, market_prob: 0.58, edge: 0.104, kc: 0.21, stake_frac: 0.0105, payout_mult: 100 / 150 } },
];

test("aggregate on a small fixture: coverage, push handling, compounding", () => {
  const r = aggregate(FIGHTS, "2025-01-01", "2025-12-31", CONFIG);
  expect(r.coverage).toEqual({ fights_in_window: 5, scored: 3, with_odds: 2 });
  expect(r.metrics.n).toBe(3);
  expect(r.metrics.accuracy).toBeCloseTo(2 / 3, 4);
  expect(r.betting.bets).toBe(2);
  expect(r.bets.map((b) => b.result)).toEqual(["win", "push"]);
  expect(r.bets[0].stake).toBeCloseTo(10.5, 2);
  expect(r.bets[0].pnl).toBeCloseTo(7.0, 2);
  expect(r.betting.final).toBeCloseTo(1007.0, 2);
  expect(r.bankroll.map((p) => p.bankroll)).toEqual([1007.0, 1007.0, 1007.0]);
  expect(r.monthly).toEqual([{ month: "2025-01", n: 2, hit: 1 }, { month: "2025-02", n: 1, hit: 0 }]);
});

test("aggregate slices by window and survives an empty window", () => {
  const jan = aggregate(FIGHTS, "2025-01-01", "2025-01-31", CONFIG);
  expect(jan.coverage.fights_in_window).toBe(2);
  expect(jan.betting.bets).toBe(1);
  const empty = aggregate(FIGHTS, "2026-01-01", "2026-01-31", CONFIG);
  expect(empty.coverage).toEqual({ fights_in_window: 0, scored: 0, with_odds: 0 });
  expect(empty.metrics).toEqual({ accuracy: null, auc: null, log_loss: null, brier: null, n: 0 });
  expect(empty.betting.final).toBe(1000);
  expect(empty.betting.hit).toBeNull();
  expect(empty.bets).toEqual([]);
});

test("windowRetrains and presets and clampWindow", () => {
  const range = { start: "2024-01-01", end: "2026-08-30", retrains: ["2024-01-01", "2024-07-13", "2025-01-11", "2025-07-12", "2026-01-24", "2026-07-25"] };
  expect(windowRetrains(range, "2025-01-01", "2025-12-31")).toEqual(["2024-07-13", "2025-01-11", "2025-07-12"]);
  expect(windowRetrains(range, "2024-01-01", "2026-08-30")).toEqual(range.retrains);
  expect(presets(range).map((p) => p[0])).toEqual(["All time", "Last 12 months", "2026 YTD", "2025", "2024"]);
  expect(presets(range)[1]).toEqual(["Last 12 months", "2025-08-30", "2026-08-30"]);
  const fallback = { start: range.start, end: range.end };
  expect(clampWindow(range, "2025-01-01", "2025-12-31", fallback)).toEqual({ start: "2025-01-01", end: "2025-12-31" });
  expect(clampWindow(range, "nope", "2025-12-31", fallback)).toEqual(fallback);
  expect(clampWindow(range, "2025-12-31", "2025-01-01", fallback)).toEqual(fallback);
  expect(clampWindow(range, "2020-01-01", "2030-01-01", fallback)).toEqual(fallback);
  expect(clampWindow(range, null, null, fallback)).toEqual(fallback);
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/aggregate.test.js`
Expected: FAIL, `Cannot find module './aggregate'`.

- [ ] **Step 3: Write `frontend/src/aggregate.js`**

```js
// Browser-side twin of testing/export_site_data.py's summary sections. Every function
// here mirrors a Python function by name; aggregate.test.js pins the two together
// against the real payload. Rounding matches the Python export (4 dp rates, cents).

const BANDS = [["50–55%", 0.5, 0.55], ["55–60%", 0.55, 0.6], ["60–65%", 0.6, 0.65], ["65–70%", 0.65, 0.7], ["70%+", 0.7, 1.01]];
const r4 = (x) => Math.round(x * 1e4) / 1e4;
const r2 = (x) => Math.round(x * 100) / 100;
const r1 = (x) => Math.round(x * 10) / 10;
const clip = (p) => Math.min(Math.max(p, 1e-6), 1 - 1e-6);
const ISO = /^\d{4}-\d{2}-\d{2}$/;

function auc(ps, ys) {
  // average-rank Mann–Whitney, identical to sklearn's roc_auc_score
  const order = ps.map((_, i) => i).sort((a, b) => ps[a] - ps[b]);
  const ranks = new Array(ps.length);
  for (let i = 0; i < order.length; ) {
    let j = i;
    while (j + 1 < order.length && ps[order[j + 1]] === ps[order[i]]) j += 1;
    const rank = (i + j) / 2 + 1;
    for (let k = i; k <= j; k += 1) ranks[order[k]] = rank;
    i = j + 1;
  }
  const pos = ys.filter((y) => y === 1).length;
  const neg = ys.length - pos;
  if (!pos || !neg) return null;
  let sumPos = 0;
  ys.forEach((y, i) => { if (y === 1) sumPos += ranks[i]; });
  return (sumPos - (pos * (pos + 1)) / 2) / (pos * neg);
}

function metricsFor(ps, ys) {
  const n = ps.length;
  if (!n) return { accuracy: null, auc: null, log_loss: null, brier: null, n: 0 };
  let acc = 0, ll = 0, br = 0;
  ps.forEach((p, i) => {
    const y = ys[i];
    if ((p >= 0.5) === (y === 1)) acc += 1;
    const q = clip(p);
    ll -= y ? Math.log(q) : Math.log(1 - q);
    br += (q - y) ** 2;
  });
  const a = auc(ps, ys);
  return { accuracy: r4(acc / n), auc: a == null ? null : r4(a), log_loss: r4(ll / n), brier: r4(br / n), n };
}

const pickHit = (f) => (f.model_p1 >= 0.5 ? [f.model_p1, f.winner === "f1"] : [1 - f.model_p1, f.winner === "f2"]);
const y1 = (f) => (f.winner === "f1" ? 1 : 0);
const rate = (hits, n) => (n ? r4(hits / n) : null);

function bands(decided) {
  return BANDS.map(([label, lo, hi]) => {
    const rows = decided.map(pickHit).filter(([c]) => c >= lo && c < hi);
    const n = rows.length;
    return { label, lo, hi: Math.min(hi, 1), n,
      stated: n ? r4(rows.reduce((s, [c]) => s + c, 0) / n) : null,
      hit: n ? r4(rows.filter(([, h]) => h).length / n) : null };
  });
}

function monthly(decided) {
  const by = new Map();
  decided.forEach((f) => { const m = f.date.slice(0, 7); if (!by.has(m)) by.set(m, []); by.get(m).push(pickHit(f)[1]); });
  return [...by.keys()].sort().map((m) => { const h = by.get(m); return { month: m, n: h.length, hit: r4(h.filter(Boolean).length / h.length) }; });
}

function market(priced, blendW) {
  const ys = priced.map(y1);
  const series = [
    ["De-vigged market", priced.map((f) => f.market_p1)],
    ["Model (ensemble)", priced.map((f) => f.model_p1)],
    [`Blend · ${blendW} model + ${r4(1 - blendW)} market`, priced.map((f) => blendW * f.model_p1 + (1 - blendW) * f.market_p1)],
  ];
  const rows = series.map(([name, ps]) => { const m = metricsFor(ps, ys); return { name, accuracy: m.accuracy, auc: m.auc, log_loss: m.log_loss, brier: m.brier }; });
  const agree = priced.filter((f) => (f.model_p1 >= 0.5) === (f.market_p1 >= 0.5));
  const disagree = priced.filter((f) => (f.model_p1 >= 0.5) !== (f.market_p1 >= 0.5));
  const hits = (g) => g.filter((f) => pickHit(f)[1]).length;
  return { rows, agree: { n: agree.length, hit: rate(hits(agree), agree.length) },
    disagree: { n: disagree.length, model_hit: rate(hits(disagree), disagree.length) } };
}

const payout = (odds, stake) => (odds < 0 ? stake * (100 / -odds) : stake * (odds / 100));
function settle(winner, side, odds, stake) {
  if (winner === "push") return ["push", 0];
  if ((winner === "f1") === (side === 1)) return ["win", payout(odds, stake)];
  return ["loss", -stake];
}

function flat(priced, stake) {
  const perBet = (choose) => {
    if (!priced.length) return 0;
    const total = priced.reduce((s, f) => s + settle(f.winner, ...choose(f), stake)[1], 0);
    return r4(total / (stake * priced.length));
  };
  return { market_favorite_per_bet: perBet((f) => (f.market_p1 >= 0.5 ? [1, f.odds1] : [2, f.odds2])),
    model_pick_per_bet: perBet((f) => (f.model_p1 >= 0.5 ? [1, f.odds1] : [2, f.odds2])), stake };
}

function maxDrawdown(series) {
  let peak = series[0], worst = 0;
  series.forEach((x) => { peak = Math.max(peak, x); worst = Math.max(worst, peak ? (peak - x) / peak : 0); });
  return worst;
}

function replay(walk, start) {
  let bankroll = start;
  const points = [], bets = [];
  const won = { fav: 0, dog: 0 }, total = { fav: 0, dog: 0 };
  walk.forEach((f) => {
    if (f.bet) {
      const stake = bankroll * f.bet.stake_frac;
      const [result, pnl] = settle(f.winner, f.bet.side, f.bet.odds, stake);
      bankroll += pnl;
      const side = f.bet.odds < 0 ? "fav" : "dog";
      total[side] += 1;
      if (result === "win") won[side] += 1;
      bets.push({ date: f.date, event: f.event, fighter: f.bet.side === 1 ? f.f1 : f.f2, opponent: f.bet.side === 1 ? f.f2 : f.f1,
        odds: f.bet.odds, model_prob: f.bet.prob, market_prob: f.bet.market_prob, edge: f.bet.edge,
        stake: r2(stake), result, pnl: r2(pnl), bankroll_after: r2(bankroll), source: "backtest" });
    }
    points.push({ date: f.date, event: f.event, bankroll: r2(bankroll) });
  });
  const series = [start, ...points.map((p) => p.bankroll)];
  const n = total.fav + total.dog;
  return { betting: { final: r2(bankroll), return_pct: r1(((bankroll - start) / start) * 100), bets: n,
      hit: rate(won.fav + won.dog, n), favorites: { won: won.fav, total: total.fav }, underdogs: { won: won.dog, total: total.dog },
      max_drawdown_pct: r1(maxDrawdown(series) * 100), low: r2(Math.min(...series)) }, bankroll: points, bets };
}

/** Every summary section for rows with start <= date <= end. Shape matches backtest.summary. */
export function aggregate(fights, start, end, config) {
  const rows = fights.filter((f) => f.date >= start && f.date <= end);
  const scored = rows.filter((f) => f.model_p1 != null);
  const decided = scored.filter((f) => f.winner !== "push");
  const walk = scored.filter((f) => f.market_p1 != null);
  const priced = decided.filter((f) => f.market_p1 != null);
  const { betting, bankroll, bets } = replay(walk, config.start_bankroll);
  return {
    coverage: { fights_in_window: rows.length, scored: decided.length, with_odds: priced.length },
    metrics: metricsFor(decided.map((f) => f.model_p1), decided.map(y1)),
    bands: bands(decided), monthly: monthly(decided), market: market(priced, config.blend_w),
    flat: flat(priced, config.flat_stake), betting, bankroll, bets,
  };
}

/** The retrain in force at the window start, then every retrain inside (start, end]. */
export function windowRetrains(range, start, end) {
  const before = range.retrains.filter((d) => d <= start);
  return [before.length ? before[before.length - 1] : range.retrains[0], ...range.retrains.filter((d) => d > start && d <= end)];
}

/** [label, start, end] presets derived from the data range. */
export function presets(range) {
  const endYear = Number(range.end.slice(0, 4));
  const startYear = Number(range.start.slice(0, 4));
  const list = [["All time", range.start, range.end]];
  const yearAgo = `${endYear - 1}${range.end.slice(4)}`;
  if (yearAgo > range.start) list.push(["Last 12 months", yearAgo, range.end]);
  if (`${endYear}-01-01` > range.start) list.push([`${endYear} YTD`, `${endYear}-01-01`, range.end]);
  for (let y = endYear - 1; y >= startYear; y -= 1) {
    const s = `${y}-01-01`, e = `${y}-12-31`;
    if (e >= range.start) list.push([String(y), s < range.start ? range.start : s, e]);
  }
  return list;
}

/** Validated {start, end} from URL params, else the fallback window. */
export function clampWindow(range, from, to, fallback) {
  if (!from || !to || !ISO.test(from) || !ISO.test(to)) return fallback;
  if (from < range.start || to > range.end || from > to) return fallback;
  return { start: from, end: to };
}
```

Note: `market` labels the blend row `Blend · 0.8 model + 0.2 market`, the same text Python produces (`f"Blend · {BLEND_W:g} model + {1 - BLEND_W:g} market"`); `r4(1 - blendW)` yields `0.2`.

- [ ] **Step 4: Run the tests**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/aggregate.test.js`
Expected: 4 passed. If the parity test fails on a specific field, compare the JS function against the Python function of the same name in `testing/export_site_data.py` before changing tolerances; report BLOCKED with the failing field and both values if the discrepancy is not a transcription error.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/aggregate.js frontend/src/aggregate.test.js
git commit -m "Aggregate any window in the browser, pinned to the Python summary

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Period filter, window wiring, data-driven doctrine copy

**Files:**
- Create: `frontend/src/components/PeriodFilter.js`, `frontend/src/components/PeriodFilter.test.js`
- Modify: `frontend/src/App.js`, `frontend/src/test/fixtures.js`, `frontend/src/components/Home.js`, `Results.js`, `Results.test.js`, `Bets.js`, `Methodology.js`, `Join.js`

**Interfaces:**
- Consumes: `aggregate`, `windowRetrains`, `presets`, `clampWindow` (Task 6); `backtest.json` v2.
- Produces: pages receive `data = { generated, range, config, window: {start, end, retrains}, ...aggregate(...) }`; `PeriodFilter({ range, window })`.

- [ ] **Step 1: Write the failing filter test**

Create `frontend/src/components/PeriodFilter.test.js`:
```js
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, useSearchParams } from "react-router-dom";
import PeriodFilter from "./PeriodFilter";

const range = { start: "2024-01-01", end: "2026-08-30", retrains: ["2024-01-01", "2024-07-13", "2025-01-11", "2025-07-12", "2026-01-24", "2026-07-25"] };

function Probe() {
  const [params] = useSearchParams();
  return <span data-testid="query">{params.toString()}</span>;
}

test("presets write the window to the URL and mark the active one", () => {
  render(
    <MemoryRouter>
      <PeriodFilter range={range} window={{ start: range.start, end: range.end }} />
      <Probe />
    </MemoryRouter>
  );
  expect(screen.getByRole("button", { name: "All time" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "2025" }));
  expect(screen.getByTestId("query")).toHaveTextContent("from=2025-01-01&to=2025-12-31");
});

test("choosing All time clears the query", () => {
  render(
    <MemoryRouter initialEntries={["/results?from=2025-01-01&to=2025-12-31"]}>
      <PeriodFilter range={range} window={{ start: "2025-01-01", end: "2025-12-31" }} />
      <Probe />
    </MemoryRouter>
  );
  expect(screen.getByRole("button", { name: "2025" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "All time" }));
  expect(screen.getByTestId("query")).toHaveTextContent("");
});
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `CI=true npx react-scripts test --watchAll=false src/components/PeriodFilter.test.js`
Expected: FAIL, `Cannot find module './PeriodFilter'`.

- [ ] **Step 3: Write `PeriodFilter.js`**

```jsx
import React from "react";
import { useSearchParams } from "react-router-dom";
import { presets } from "../aggregate";

/** One filter row above the results: presets plus a custom range, mirrored in the URL. */
export default function PeriodFilter({ range, window: win }) {
  const [, setParams] = useSearchParams();
  const set = (from, to) => setParams(from === range.start && to === range.end ? {} : { from, to });
  const input = "rounded-md border border-hairline bg-surface px-2 py-1 text-sm text-ink";
  return (
    <div className="mx-auto max-w-content px-6 pt-6" role="group" aria-label="Time period">
      <div className="flex flex-wrap items-center gap-2">
        {presets(range).map(([label, s, e]) => {
          const active = s === win.start && e === win.end;
          return (
            <button
              key={label}
              type="button"
              aria-pressed={active}
              onClick={() => set(s, e)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                active ? "border-ink bg-surface text-ink" : "border-hairline text-ink-2 hover:text-ink"
              }`}
            >
              {label}
            </button>
          );
        })}
        <label className="ml-2 flex items-center gap-2 text-sm text-ink-2">
          From
          <input type="date" aria-label="From date" className={input} min={range.start} max={win.end} value={win.start}
            onChange={(e) => e.target.value && set(e.target.value, win.end)} />
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          to
          <input type="date" aria-label="To date" className={input} min={win.start} max={range.end} value={win.end}
            onChange={(e) => e.target.value && set(win.start, e.target.value)} />
        </label>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire the window in `App.js`**

Replace `frontend/src/App.js` in full:
```jsx
import React, { useMemo } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import PeriodFilter from "./components/PeriodFilter";
import Home from "./components/Home";
import Results from "./components/Results";
import Bets from "./components/Bets";
import Methodology from "./components/Methodology";
import Join from "./components/Join";
import backtest from "./data/backtest.json";
import ledger from "./data/ledger.json";
import { aggregate, clampWindow, windowRetrains } from "./aggregate";

/** The page data for one window: the summary sections plus window, range and config. */
function viewFor(start, end) {
  return {
    generated: backtest.generated,
    range: backtest.range,
    config: backtest.config,
    window: { start, end, retrains: windowRetrains(backtest.range, start, end) },
    ...aggregate(backtest.fights, start, end, backtest.config),
  };
}

const DEFAULT_VIEW = viewFor(backtest.default_window.start, backtest.default_window.end);

function Site() {
  const [params] = useSearchParams();
  const { start, end } = clampWindow(backtest.range, params.get("from"), params.get("to"), backtest.default_window);
  const view = useMemo(() => viewFor(start, end), [start, end]);
  const filter = <PeriodFilter range={backtest.range} window={view.window} />;
  return (
    <div className="min-h-screen bg-ground font-body text-ink">
      <Navbar />
      <Routes>
        <Route path="/" element={<>{filter}<Home data={view} /></>} />
        <Route path="/results" element={<>{filter}<Results data={view} /></>} />
        <Route path="/bets" element={<>{filter}<Bets data={view} ledger={ledger} /></>} />
        <Route path="/methodology" element={<Methodology data={DEFAULT_VIEW} />} />
        <Route path="/join" element={<Join data={DEFAULT_VIEW} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Footer />
    </div>
  );
}

const App = () => (
  <Router>
    <ScrollToTop />
    <Site />
  </Router>
);

export default App;
```

- [ ] **Step 5: Extend the fixture**

In `frontend/src/test/fixtures.js`, add to `backtestFixture` (after `generated`):
```js
  range: { start: "2024-01-01", end: "2026-08-30", retrains: ["2024-01-01", "2024-07-13", "2025-01-11", "2025-07-12", "2026-01-24", "2026-07-25"] },
  config: { blend_w: 0.8, min_edge: 0.05, kelly_fraction: 0.05, kelly_cap: 0.05, max_dog_odds: 200, start_bankroll: 1000, flat_stake: 10 },
```
Leave `window` and every section as they are: pages receive exactly this shape.

- [ ] **Step 6: Page copy from `config`, window-generic titles**

`Home.js`:
- Move `STEPS` inside the component as `const steps = [...]` (delete the module-level `STEPS`), with the third entry:
```js
    ["Bets", `Probability meets closing odds. A fractional Kelly stake goes down only when the blended probability's edge over the de-vigged market clears ${Math.round(config.min_edge * 100)}%, and never on a price longer than +${config.max_dog_odds}.`],
```
  and destructure `config` from `data` alongside the other fields; change `{STEPS.map(` to `{steps.map(`.

`Results.js`:
- `<Eyebrow>`: replace `Annual model review ·` with `Walk-forward record ·`.
- `<h1>`: replace `One year out of sample` with `Out of sample`.
- Betting paragraph: replace
```
          The production config bets the model's pick with fractional Kelly (5% fraction, 5% cap, no floor)
          whenever the blended probability beats the de-vigged price by at least 5 points. {betting.bets} bets,{" "}
```
  with
```
          The production config bets the model's pick with fractional Kelly ({pct(config.kelly_fraction, 0)} fraction,{" "}
          {pct(config.kelly_cap, 0)} cap, no floor) whenever the blended probability beats the de-vigged price by at
          least {Math.round(config.min_edge * 100)} points, and skips any pick priced longer than +{config.max_dog_odds}.{" "}
          {betting.bets} bets,{" "}
```
  and destructure `config` from `data`.
- `Results.test.js`: change the h1 assertion to `toHaveTextContent("Out of sample")`.

`Methodology.js`:
- Evaluation paragraph two: replace
```
          Betting is replayed with the exact production sizing code: fractional Kelly at 5% of the
          criterion, capped at 5% of bankroll, no floor, and a 5-point minimum edge measured against the de-vigged closing
          price. The bet log shows every stake.
```
  with
```
          Betting is replayed with the exact production sizing code: fractional Kelly at{" "}
          {pct(config.kelly_fraction, 0)} of the criterion, capped at {pct(config.kelly_cap, 0)} of bankroll, no floor, a{" "}
          {Math.round(config.min_edge * 100)}-point minimum edge measured against the de-vigged closing price, and no
          picks priced longer than +{config.max_dog_odds}. The bet log shows every stake.
        </p>
        <p>
          This model version and the longshot cap were adopted after the window they are scored on. Treat the
          improvement they show as a hypothesis the live bet log tests going forward.
```
  (the second `<p>` is new; the existing closing `</p>` of the first paragraph is reused by the new one), and destructure `config` from `data`. If the sentence wraps differently in the file, match by meaning.

`Join.js`:
- Change the "Edge and stake" card text to `` `Which side clears the ${Math.round(config.min_edge * 100)}-point edge gate, and the fractional Kelly stake as a percent of bankroll.` `` (turn the static array into one built inside the component) and destructure `config` from `data`.

`Bets.js`: no copy change needed (the intro already uses `span`).

- [ ] **Step 7: Tests, build**

Run from `frontend/`:
```bash
CI=true npx react-scripts test --watchAll=false
CI=true npm run build
```
Expected: every suite passes (existing page tests still receive the summary shape; `App.test.js` renders the real v2 payload through `aggregate`); `Compiled successfully.`

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PeriodFilter.js frontend/src/components/PeriodFilter.test.js frontend/src/App.js frontend/src/test/fixtures.js frontend/src/components/Home.js frontend/src/components/Results.js frontend/src/components/Results.test.js frontend/src/components/Methodology.js frontend/src/components/Join.js
git commit -m "Add the period filter and drive every page from a URL-selected window

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Docs and final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Read the file first; make these edits with exact matches:
- Project Overview: replace the "Measured out-of-sample accuracy is **~63%** ..." paragraph with one sentence quoting the new export's headline for 2024-01 → 2026-08 (accuracy, scored fights, Kelly return with bet count and drawdown) and a pointer: "The public site (`frontend/`) recomputes every window from `frontend/src/data/backtest.json`."
- Key Commands, the "Public site data" comment block: replace the sentence about `test_results/.lastyear_tier0_cache/` with:
```
# The export reads test_results/.tier2_full_cache/ (one pred_YYYY-MM-DD.csv per walk-forward
# retrain, 2024-01-01 → 2026-08-30, committed). To extend or rebuild it:
python testing/build_walk_forward_cache.py --start 2024-01-01 --end 2026-08-30 --cache test_results/.tier2_full_cache
```
- Model Files: add "Members are trained with distinct seeds; `saved_preprocessing/calibrator.joblib` holds the temperature calibrator `load_ensemble.py` applies at inference."
- Betting Strategy bullets: add "- Picks priced longer than +200 are skipped (`max_dog_odds`, adopted 2026-09 after the 2024-26 walk-forward study)".
- React Frontend Structure: add `aggregate.js — browser twin of the export's summary sections; every page recomputes for the URL window (?from=&to=)` and `PeriodFilter.js — presets + custom range`.

- [ ] **Step 2: Verify everything**

```bash
.venv/bin/python -m pytest tests/ -q
cd frontend && CI=true npx react-scripts test --watchAll=false && CI=true npm run build && cd ..
git status --short | grep -v '^??' 
```
Expected: pytest green (the golden test runs against the full cache); all frontend suites green; build clean; only `CLAUDE.md` modified.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Document the tier-2 deployment, the cap, the cache builder and the period filter

Assisted by AI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Plan self-review

**Spec coverage.** A1-A2 → Task 1; A3 → Task 2; A4 → Task 3; B1-B2 → Task 4; C1-C2 → Task 5; D1 → Task 6; D2-D4 → Task 7; E → Task 8 (Methodology disclosure sentence in Task 7). Out-of-scope items untouched.

**Placeholders.** None; every step carries its code or exact command. Compute steps name their log files and completion markers.

**Type consistency.** `FightRow.winner` vocabulary matches `aggregate.js` (`"f1" | "f2" | "push" | "unknown"`); `Bet.stake_frac`/`payout_mult` match `replay()`; `aggregate` returns the summary shape the pages consume, and `viewFor` adds `generated`, `range`, `config`, `window` that `Results.js`/`Methodology.js`/`Home.js`/`Join.js` read; `clampWindow(range, from, to, fallback)` signature matches its test and `App.js`.
