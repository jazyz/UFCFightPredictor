# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UFC Fight Predictor is a machine learning system that predicts UFC fight outcomes and recommends bets using the Kelly Criterion. Website: http://betufc.ca/

Measured out-of-sample accuracy is **~63%**: 62.9% on the 159 fights of 2026-02-28 → 2026-08-30, and 63.5% across the 762 fights that followed the previous training cutoff. Accuracy alone understates what changed most recently — see "Calibration matters more than accuracy" below.

## Key Commands

### Auto-Retraining Pipeline (Full Automation)
```bash
python auto_retrain.py                      # Full pipeline: scrape → process → train → validate
python auto_retrain.py --skip-training      # Scrape and process only
python auto_retrain.py --skip-scrape        # Rebuild and retrain from data already on disk
python auto_retrain.py --force-full-scrape  # Rescrape every event from scratch
python auto_retrain.py --dry-run            # Preview without changing anything
```

### Individual Pipeline Components
```bash
python scrapers/scrape_incremental.py       # Scrape new fights (also updates the fighter DB)
python scrapers/update_fighters.py          # Fill in fighters missing from the DB
python utils/incremental_processing.py      # Clean raw fights → modified_fight_details.csv
python process_fights_alpha.py              # Feature engineering (180+ features)
python ml_ensemble.py                       # Train the 5-model ensemble AND save it
```

`ml_alpha_date.py` trains a single model and prints metrics, but **never writes to
`saved_models/`** and ends in a blocking `plt.show()`. It is an exploration script.
`ml_ensemble.py` is what produces the deployed models.

### Predictions & Testing
```bash
python predict_event.py                     # Predict the next event
python predict_event.py --list              # Show the upcoming schedule
python predict_event.py --event <url>       # Predict a specific ufcstats event
python predict_event.py --odds              # Also pull odds and size bets with Kelly
python betting_alpha.py                     # Betting recs from data/betting_predictions.csv
cd testing && python testing_time_period.py # Run backtesting
```

### Flask API & Frontend
```bash
python app.py                               # Start Flask server (localhost:5000)
cd frontend && npm start                    # Start React dev server (localhost:3000)
cd frontend && npm run build                # Production build
```

### Scheduler Management (macOS launchd)
```bash
./setup_launchd.sh                          # Interactive launchd setup
tail -f logs/launchd_error.log              # Scheduler-level failures (job never started)
ls -t logs/auto_retrain_*.log | head -1 | xargs cat  # Latest run log
```

The launchd job runs `.venv/bin/python`, not the shell's default interpreter. If a
dependency is importable in your shell but the scheduled run fails, check `.venv` first.

## Architecture

### Data Pipeline Flow
```
ufcstats.com → scrapers/scrape_incremental.py → data/fight_details_date.csv
    → utils/incremental_processing.py → data/modified_fight_details.csv
    → process_fights_alpha.py → data/detailed_fights.csv (180+ features)
    → ml_ensemble.py → saved_models/lgbm_model_*.joblib + saved_preprocessing/
    → predict_event.py → data/predicted_data.json
    → app.py (Flask API) → frontend/ (React)
```

### Key Files by Function
- **Orchestration**: `auto_retrain.py` — runs the full pipeline on schedule, with backup, validation and rollback
- **HTTP**: `scrapers/ufcnet.py` — ufcstats session that clears the anti-bot challenge
- **Scraping**: `scrapers/scrape_incremental.py` — detects last stored date, scrapes only newer events
- **Fighters**: `scrapers/update_fighters.py` — adds debutants to `instance/detailedfighters.db`
- **Processing**: `utils/incremental_processing.py` — data cleaning, format conversion
- **Features**: `process_fights_alpha.py` — ELO, per-minute stats, weighted averages
- **Training**: `ml_ensemble.py` — 5 LightGBM models with Optuna tuning; saves models and preprocessing
- **Prediction**: `predict_event.py` — event predictions with Kelly betting
- **API**: `app.py` — Flask REST endpoints

### Model Files
- `saved_models/lgbm_model_0.joblib` … `lgbm_model_4.joblib` — five ensemble members. They are **not** corner-specific: each is trained on the same augmented data with its own Optuna-sampled hyperparameters, and inference averages `predict_proba` across all five (see `load_ensemble.py`).
- `saved_preprocessing/selected_columns.json` — the exact feature list the models expect; **always** select columns through this rather than recomputing the prune.
- `saved_preprocessing/label_encoder.joblib` — classes are `['loss', 'win']`, so **class 1 = the red corner wins**.
- `saved_models/backup_YYYYMMDD_HHMMSS/` — timestamped backups written before each retrain, including a copy of `saved_preprocessing/`.

### Data Files
- `data/fight_details_date.csv` — raw scraped fights, stored **newest-first**; new rows are prepended
- `data/modified_fight_details.csv` — cleaned/processed fights (also newest-first)
- `data/detailed_fights.csv` — feature-engineered dataset, oldest-first (full recompute each run)
- `data/detailed_fighter_stats.csv` — per-fighter career state, read by `predict_fights_alpha.py`
- `data/predicted_data.json` — latest predictions; served by `/get_predicted_data`
- `data/fight_results_with_odds.csv` — historical odds, **stops at 2024-03-30**, so betting backtests cannot cover anything more recent

## Important Patterns

### ufcstats.com serves an anti-bot challenge
Every page is fronted by a JavaScript proof-of-work interstitial: find `n` such that
`sha256(f"{nonce}:{n}")` starts with a run of zeros, POST it to `/__c`, then retry. One
cookie then covers the rest of the session. `scrapers/ufcnet.py` handles this; always
fetch ufcstats pages through it rather than calling `requests.get` directly.

**A parse that yields nothing is a failure, not "no new data."** This is the single most
important invariant in the scraper. The pre-2026 version of this pipeline used a plain
`requests.get`, parsed the challenge page, found zero rows, and logged
`✓ Scraping completed: 0 new fights added` on every scheduled run for two and a half
years. Keep raising `ScrapeError` on empty parses; "already up to date" must only be
reachable after successfully parsing the event index.

### Calibration matters more than accuracy
For betting, the useful property is that higher confidence means more often right — that
is what Kelly sizing consumes. A stale model degrades here long before its headline
accuracy moves. When the models were last left untrained for two years, accuracy held
around 64% while the 70%+ confidence band fell to 64% — no better than its weakest picks.
After retraining, accuracy was flat (62.9%) but the bands became monotonic again and the
70%+ band reached 79%. **Judge a retrain on AUC, log loss, Brier and the calibration
bands, not on accuracy alone.**

### Feature Engineering
For each fighter stat, generates: per-minute rates, accuracy %, differentials, weighted
moving averages (recent fights weighted higher), career totals. Features for a fight use
only bouts that preceded it, so there is no lookahead.

`process_fights_alpha.py` chooses each fight's red/blue orientation with `random.choice`,
so it is **not reproducible unless seeded**. `auto_retrain.py` seeds it at 42.

### Red/Blue symmetry is a hard requirement
Training augments every row with a Red↔Blue-swapped copy, so the retained feature set must
be closed under that swap. The correlation prune in `ml_ensemble.py` is order-dependent and
will otherwise drop only one side of a pair; `pd.concat` then unions the two frames and
**silently fills the orphaned columns with NaN**. `ml_ensemble.py` now drops both halves of
any such pair and asserts that mirroring did not change the column set. Do not remove that
guard.

### Betting Strategy
Fractional Kelly with conservative defaults:
- 5% Kelly fraction, 5% max cap
- Requires >5% edge (model prob − implied prob) to bet
- Where odds exist, sizing uses whichever corner orientation is closer to the market price
  (`closerToOdds`), which can differ from the plain average of the two orientations

### Auto-Retraining System
Runs Monday & Friday at 2:00 AM via launchd:
1. Incremental scrape of new events; new fighters added to the fighter DB
2. New rows prepended to `fight_details_date.csv` (backup written first)
3. Full feature recomputation (needed for ELO consistency)
4. Backup of `saved_models/` + `saved_preprocessing/`, then training via `ml_ensemble.py`
5. Validation on `ml_ensemble.py`'s own chronological holdout (the last 5% of fights, never
   trained on). **Accuracy must exceed 60% or the previous models are restored.** This gate
   lives in `auto_retrain.py`; `ml_ensemble.py` on its own saves unconditionally.

Any step that fails, or produces nothing, exits non-zero.

### Known quirks
- The cleaning step drops every `Title` containing "Women", so **women's bouts are absent
  from training and cannot be predicted**. `predict_event.py` reports them as fighters with
  no history.
- `Time Format` and `Details` are empty for every row: ufcstats labels them differently and
  the original scraper never captured them. New rows match this on purpose.
- The `shap` block in `ml_ensemble.py` is optional diagnostics — `shap` is not in
  `requirements.txt` and `summary_plot` blocks on render, so it is skipped when absent.

### Leakage fixes to preserve
Several are load-bearing and easy to undo by accident:
- `ml_ensemble.py` computes the correlation matrix on **training rows only**; computing it
  over the full frame lets feature selection see the test set.
- Optuna CV runs on the **un-augmented** training set. With the mirrored copies appended,
  `TimeSeriesSplit` folds validate on swapped duplicates of fights already trained on.
- `predict_fights_alpha.py` divides differential features by `sqrSum(totalfights)` exactly
  as `process_fights_alpha.py` does at training time. These drifted apart once and produced
  training/serving skew.
- `tests/test_no_data_leakage.py` and `validation/` exist to guard this; run them after
  touching the feature or training path.

### File Naming
- `*_alpha.py` — Alpha model variants
- `*_date.py` — Date-aware processing
- `ml_*.py` — Machine learning scripts
- `predict_*.py` — Prediction scripts

## React Frontend Structure

Components in `frontend/src/components/`:
- `Home.js` — landing page
- `FightPredictor.js` — single fight prediction
- `FightersPage.js` / `FightersDropdown.js` — fighter stats browser
- `Bets.js` — betting recommendations
- `Testing.js` — backtesting interface
- `About.js`, `Navbar.js` — supporting pages/chrome

## Dependencies

Python: Flask, Flask-CORS, Flask-SQLAlchemy, pandas, numpy, lightgbm, scikit-learn, joblib,
optuna, beautifulsoup4, requests, matplotlib. `shap` is optional (diagnostics only).

Frontend: React 18, Tailwind CSS
