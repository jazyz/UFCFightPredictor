# Tier-2 deploy, longshot cap, and a site period selector

Date: 2026-09-03
Status: approved design, awaiting implementation plan
Builds on: `docs/superpowers/specs/2026-09-02-website-revamp-design.md` (the site this changes)

## Goal

Put the best model into production, then let the public site show its record over
any time period, headlining the best honest number. Today the site shows the tier-0
model over one fixed year (+1.2% Kelly). The tier-2 model with a +200 longshot cap
measured about +24.7% over 2024-01 → 2026-07 in the walk-forward study, but neither
the model nor the cap is on `main`, and the site cannot show any window but the one
the export was run for.

## Decisions already made

- Deploy tier-2 (seed-diverse ensemble members plus a temperature calibrator) and
  adopt the cap: skip a pick priced longer than +200.
- One full-range walk-forward cache, rebuilt from the merged pipeline, replaces the
  one-year tier-0 cache as the site's single source of numbers.
- The export emits per-fight rows; the browser aggregates any window. The default
  window is the full range, which is the best honest number.
- Methodology discloses that the tier-2 model and the cap were adopted after the
  backtest window they are shown on.

## Out of scope

- The live ledger, scraping, the Flask API, and the membership page.
- Re-tuning hyperparameters. `data/best_params.json` stays as is.
- Filtering the live ledger by the selected window; it is a small growing record and
  always shows in full.

## Part A: deploy tier-2 and the cap

### A1. Commit the backtest twin on the tier-2 branch

The worktree `.claude/worktrees/tier2-model-upgrades` (branch
`worktree-tier2-model-upgrades`) holds uncommitted changes to
`testing/ml_alpha_testing.py` (per-member seeds, per-split out-of-fold temperature
calibration, 39 lines) and an untracked `testing/devig_cap_experiment.py`. Commit
both to that branch. Do not commit the worktree's modified `data/*` and
`test_results/*.txt` files; restore them.

### A2. Merge into main

`git merge worktree-tier2-model-upgrades` on the working branch (a dry run shows no
conflicts). The merge brings `calibration.py`, the calibrator in `load_ensemble.py`,
`predict_event.py` and `ml_web.py`, the calibrating `ml_ensemble.py`, tier-2
`saved_models/*.joblib`, and `saved_preprocessing/calibrator.joblib`.

### A3. Regenerate features and models under the merged code

Run `python auto_retrain.py --skip-scrape`. It rebuilds features with the seed, retrains
the tier-2 ensemble and calibrator, and validates on the chronological holdout with
the existing 60% accuracy gate. A gate failure stops the work; nothing else proceeds.

### A4. The cap in `betting_math.decide_bet`

New keyword argument `max_dog_odds=200`. After the pick side is chosen, if the pick's
American price is greater than `max_dog_odds`, return `None`. Docstring and module
doctrine updated. All callers (`predict_event.py`, `betting_alpha.py`,
`testing/testing_time_period.py`, the export) inherit the default.

Tests in a new `tests/test_betting_math.py`: a +200 pick is still bet; a +201 pick
returns `None`; a favorite is unaffected; `max_dog_odds=None` disables the cap.

## Part B: full-range walk-forward cache

### B1. `testing/build_walk_forward_cache.py`

```
python testing/build_walk_forward_cache.py --start 2024-01-01 --end 2026-08-30 \
    --cache test_results/.tier2_full_cache
```

Runs `testing.testing_time_period.process_dates(start, end, strategy)` with `train_ml`
replaced by a function that trains through `testing.ml_alpha_testing.main(date)` once
per retrain date, copies `data/predicted_results.csv` to `<cache>/pred_<date>.csv`,
and reuses an existing file on later runs. Prints each retrain date and the final
bankroll. Strategy is the production config. The retrain schedule is the one
`find_fights` produces: 2024-01-01, 2024-07-13, 2025-01-11, 2025-07-12, 2026-01-24,
2026-07-25 for this window.

### B2. Build and commit

Build the six files on the merged pipeline (about an hour of training). Commit them.
Remove `test_results/.lastyear_tier0_cache/` from git; the export no longer reads it.

## Part C: export v2

`testing/export_site_data.py` defaults change to `--cache test_results/.tier2_full_cache`,
`--start 2024-01-01`, `--end 2026-08-30`. The existing aggregation code stays and
computes the `summary` for the default window; the golden test moves to this window.

### C1. Payload shape

```
{
  "generated": "2026-09-03T12:00:00",
  "range": {"start": "2024-01-01", "end": "2026-08-30", "retrains": ["2024-01-01", ...]},
  "config": {"blend_w": 0.8, "min_edge": 0.05, "kelly_fraction": 0.05, "kelly_cap": 0.05,
             "max_dog_odds": 200, "start_bankroll": 1000.0, "flat_stake": 10.0},
  "default_window": {"start": "2024-01-01", "end": "2026-08-30"},
  "summary": {coverage, metrics, bands, monthly, market, flat, betting, bankroll, bets},
  "fights": [FightRow, ...]
}
```

`summary` sections keep their v1 shapes. `FightRow`:

```
{"date": "2024-01-13", "event": "ufc-fight-night-january-13-2024",
 "f1": "A", "f2": "B", "winner": "f1" | "f2" | "push",
 "model_p1": 0.61 | null, "market_p1": 0.55 | null,
 "odds1": -130 | null, "odds2": 110 | null,
 "bet": null | {"side": 1 | 2, "odds": -130, "prob": 0.62, "market_prob": 0.57,
                "edge": 0.05, "kc": 0.11, "stake_frac": 0.0055, "payout_mult": 0.769}}
```

Every odds-file fight in the range is a row. `model_p1` is null when the model did
not score the fight; `market_p1`, `odds1`, `odds2` are null when odds are missing.
`bet` is the production `decide_bet` decision (cap included) for priced, scored fights;
`stake_frac` is `min(kelly_fraction × kc, kelly_cap) × dog_multiplier`, which equals
`stake / bankroll` in the reference backtest, and `payout_mult` is `100 / -odds` for
negative prices and `odds / 100` for positive ones. `config` values are read from
`betting_math.decide_bet`'s defaults and the export's constants, never retyped.

Dataclasses `Range`, `Config`, `Window` (start, end), `Bet`, `FightRow`, and a new
top-level `SitePayload` are defined next to the existing ones.

### C2. Tests

Unit tests on the synthetic fixture: an unscored row carries nulls; a bet row's
`stake_frac × start_bankroll` equals the reference stake; `summary` equals
`build_payload` over the default window; `config` matches `decide_bet`'s defaults.
The golden test asserts parity with `process_dates` over the full range against
`.tier2_full_cache` (skipped when the cache is absent).

## Part D: browser-side windows

### D1. `frontend/src/aggregate.js`

`aggregate(fights, start, end, config)` returns an object with exactly the `summary`
shape (`coverage, metrics, bands, monthly, market, flat, betting, bankroll, bets`),
computed over rows with `start <= date <= end`:

- scored = rows with `model_p1 != null` and `winner != "push"` → `metrics`
  (accuracy, AUC by average-rank Mann–Whitney, log loss and Brier with probabilities
  clipped to [1e-6, 1 − 1e-6]), `bands` on the pick's stated probability with the same
  five bands, `monthly`.
- priced = scored with `market_p1 != null` → `market` rows (market, model, blend at
  `config.blend_w`), agreement, `flat` at `config.flat_stake`.
- Bankroll starts at `config.start_bankroll` and updates on every row in the window
  with both `model_p1 != null` and `market_p1 != null` (pushes included, exactly the
  rows the Python replay walks), in date order: with a bet, win →
  `× (1 + stake_frac × payout_mult)`, loss → `× (1 − stake_frac)`, push → unchanged.
  A `bankroll` point is appended after every such row. `bets` carries the v1
  `BetRecord` shape with dollar `stake`, `pnl`, `bankroll_after` derived from the
  running bankroll; `betting` carries the v1 summary with favorites (`odds < 0`) and
  underdogs, hit rate, max drawdown from the series including the start value, low.
- `coverage` counts all rows in the window, scored, and priced-and-decided.
- An empty window returns zero counts and null rates without throwing.

`windowRetrains(range, start, end)` returns the latest retrain on or before `start`
followed by the retrains inside `(start, end]`; pages use it where they showed
`window.retrains`.

`presets(range)` returns `[["All time", range.start, range.end], ["Last 12 months",
end − 1 year, end], ["<year> YTD", ...], ["2025", ...], ["2024", ...]]` computed from
`range`, omitting any preset that falls entirely outside the range.

### D2. `PeriodFilter`

One row under the navbar on `/`, `/results`, `/bets`: preset buttons (the active one
marked, `aria-pressed`) and two date inputs for a custom range, clamped to `range`.
State lives in the URL query (`?from=YYYY-MM-DD&to=YYYY-MM-DD`) through
`useSearchParams`, so links are shareable; missing or invalid params mean the default
window. `/methodology` and `/join` do not show the filter and use the default window.

### D3. Pages

`App.js` reads the query, computes `view = { window: {start, end, retrains}, config,
range, ...aggregate(fights, start, end, config) }` once per change, and passes it as
`data`. Page components keep their current props and read `data.config` for the
doctrine sentences (edge gate, Kelly fraction and cap, dog cap, flat stake) instead of
literals. Copy that assumes one year becomes range-generic: the Results title becomes
"Out of sample" with the window in the eyebrow; the Bets intro names the window. The
live ledger is not filtered.

### D4. Frontend tests

- `aggregate.test.js`: (a) parity — `aggregate(backtest.fights, default_window)`
  equals `backtest.summary` from the real `frontend/src/data/backtest.json`: final
  bankroll and every bet's `stake`/`pnl` within $0.005, counts exactly, rates and
  metrics within 1e-4; (b) a small hand-built fixture: window slicing, a push, an
  unscored row, an empty window.
- `PeriodFilter.test.js`: clicking a preset writes `from`/`to` to the URL; an invalid
  query falls back to the default window.
- Existing page tests keep passing with the fixture extended to the v2 shape (the
  pages still receive the summary shape as `data`).
- `CI=true npm run build` passes with zero warnings.

## Part E: docs

`CLAUDE.md`: Model Files (seed-diverse members, `calibrator.joblib`), Betting Strategy
(the +200 cap), Key Commands (the cache builder, the new export defaults), Data Files
(`.tier2_full_cache`), React Frontend Structure (`aggregate.js`, `PeriodFilter`),
and the measured-accuracy paragraph refreshed from the new export. Methodology page:
one sentence disclosing that the model version and the cap were adopted after the
shown window.

## Verification checklist

- `auto_retrain.py --skip-scrape` passes the holdout gate on the merged code.
- `tests/test_betting_math.py`, export tests, ledger tests, and the full-range golden
  test pass; `pytest tests/` is green.
- The cache builder reproduces the six retrain dates listed in B1.
- The JS parity test matches the Python summary to the cent.
- All five pages render for the default window and for a custom window in the
  browser with no console errors; the URL round-trips the window.
- `CI=true npm run build` is clean.
