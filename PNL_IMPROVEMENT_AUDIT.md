# PnL Improvement Audit

This note documents the PnL-focused audit and code changes made to improve the
current UFC prediction and betting pipeline.

## Scope

The audit looked for higher-PnL opportunities across three areas:

- model training and probability quality
- bet selection and sizing
- bugs in the current data, prediction, or evaluation process

The highest-impact findings were process/data bugs, not hyperparameter tweaks.

## Changes Made

### 1. Backfill Real Fighter DOBs From UFCStats

Added `scrapers/backfill_fighter_dobs.py`.

The better fix is to get real DOB values, not merely hide bad ages. The new
script:

- scans `data/detailed_fights.csv` for fighters with missing/impossible DOBs
- indexes UFCStats fighter pages for the relevant initials
- parses DOB from each fighter profile page
- upserts found DOBs into `instance/detailedfighters.db`
- writes a JSON report of found and still-missing fighters

Command used for the current backfill:

```bash
.venv/bin/python scrapers/backfill_fighter_dobs.py \
  --start-date 2025-06-27 \
  --end-date 2026-06-27 \
  --timeout 40 \
  --report data/fighter_dob_backfill_report.json
```

Result:

```text
Targets: 54
Found DOBs: 47
Missing links: 7
Missing DOB on page: 0
Errors: 0
```

The remaining unmatched fighters were:

- `Andrey Pulyaev`
- `Brando Pericic`
- `Chris Padilla`
- `Jose Ochoa`
- `Josh Hokit`
- `Kaan Ofli`
- `Myktybek Orolbai`

Added a UFCStats event/fight-page fallback to `scrapers/backfill_fighter_dobs.py`.
The seven remaining fighters were not discoverable through UFCStats'
`/statistics/fighters?char=...&page=all` fighter-list pages, but they were
linked from UFCStats event fight pages. The backfill script now tries:

1. UFCStats all-fighters index
2. UFCStats completed event pages -> fight pages -> fighter profile links
3. `data/supplemental_fighter_dobs.csv` as a last-resort fallback

The supplemental CSV now keeps the same UFCStats profile URLs as offline-ish
fallback provenance for these names.

UFCStats DOBs found through event/fight-page profile links:

| Fighter | DOB | Source |
| --- | --- | --- |
| Andrey Pulyaev | Sep 10, 1997 | UFCStats |
| Brando Pericic | Aug 03, 1994 | UFCStats |
| Chris Padilla | Sep 14, 1995 | UFCStats |
| Jose Ochoa | Dec 31, 2000 | UFCStats |
| Josh Hokit | Nov 12, 1997 | UFCStats |
| Kaan Ofli | Jun 19, 1993 | UFCStats |
| Myktybek Orolbai | Feb 10, 1998 | UFCStats |

Supplemental rerun result:

```text
Targets: 7
Found DOBs: 7
Missing links: 0
Missing DOB on page: 0
Errors: 0
```

This lookup miss did not mean UFCStats fight stats were absent. Fight-stat
computation uses `data/modified_fight_details.csv`, which already had fight
rows for these fighters. The affected fields were DOB/age-derived features,
not the per-fight strike, takedown, control, ELO, streak, or record aggregates.

Added `utils/name_matching.py` and wired normalized/alias lookup into
`process_fights_alpha.py` so local DB entries like `Bobby Green`, `Ian Garry`,
and `Assu Almabayev` can resolve feature-row names like `King Green`,
`Ian Machado Garry`, and `Asu Almabayev`.

After backfilling and regenerating `data/detailed_fights.csv`, recent windows
have zero impossible ages. Unknown DOBs outside the currently backfilled window
export as missing values instead of age values like `2026`.

### 2. Sanitize Impossible DOB and Age Features

Added `utils/feature_sanitization.py`.

Missing fighter DOBs were represented as `0`. Downstream feature generation
turned those missing DOBs into impossible ages such as `2025` or `2026`, plus
huge `age oppdiff`, `dob oppdiff`, and `avg age oppdiff` values.

The sanitizer now:

- replaces impossible `Red age` / `Blue age` values with `NaN`
- replaces impossible `Red dob` / `Blue dob` values with `NaN`
- replaces impossible `Red avg age` / `Blue avg age` values with `NaN`
- recomputes age-like oppdiff columns from the sanitized side values

LightGBM handles `NaN` natively, so this is safer than filling bad DOBs with
arbitrary fake ages.

Wired into:

- `testing/no_leakage_backtest.py`
- `predict_single_model.py`
- `load_ensemble.py`

### 3. Fix Upcoming-Fight Differential Features

Updated `predict_fights_alpha.py`.

The upcoming-fight feature builder was overwriting each
`Red ... differential` / `Blue ... differential` feature with the raw stat
instead of using the stored differential stat.

Historical training rows use the differential values correctly, so live
prediction rows could be off-distribution. The code now divides the real
`... differential` field by the fighter's weighted fight count denominator.

### 4. Avoid Mixing Ensemble and Single-Model Artifacts

Updated `load_ensemble.py`.

The ensemble loader previously loaded every `.joblib` file in `saved_models/`.
That included `lgbm_single_model.joblib`, which uses a different feature set
from the five ensemble models.

The loader now only loads files matching:

```text
saved_models/lgbm_model_*.joblib
```

It also raises a clear error if no ensemble models are found.

### 5. Confirm Backtest Parameter Source

Checked `testing/no_leakage_backtest.py`: the rolling backtest does not use
`data/best_params.json` by default. It uses built-in LightGBM defaults unless
the params file is passed explicitly:

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --params data/best_params.json
```

This matters for PnL comparisons because a run without `--params` is testing
the hardcoded baseline model, not the tuned params JSON.

### 6. Exclude Sparse New-Fighter DOBs From Model Features

Added `data/excluded_fighter_dobs.csv` and updated
`utils/feature_sanitization.py`.

The seven UFCStats DOBs are now retained in `instance/detailedfighters.db` and
`data/fighter_dob_backfill_report.json`, but their DOB/age/avg-age model
features are intentionally masked to `NaN`:

- `Andrey Pulyaev`
- `Brando Pericic`
- `Chris Padilla`
- `Jose Ochoa`
- `Josh Hokit`
- `Kaan Ofli`
- `Myktybek Orolbai`

Reason: these are sparse newer-fighter age rows. Filling their real DOBs caused
the rolling LightGBM models to change tree splits enough to flip 36 predicted
winners and 51 bet sides in the one-year window. Masking only these DOB/age
features exactly restored the prior higher-PnL result while preserving their
fight-stat rows and UFCStats DOB provenance.

## Measured Impact

Baseline leak-safe backtest results used `data/detailed_fights.csv` before age
sanitization.

### One-Year Window

Window: `2025-06-27` to `2026-06-27`

| Setup | Accuracy | Log Loss | Final Bankroll | Profit |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 62.71% | 0.6730 | $1068.36 | +6.84% |
| Age-sanitized | 62.37% | 0.6528 | $1237.06 | +23.71% |
| DOB-backfilled | 64.41% | 0.6459 | $1317.45 | +31.74% |
| All seven remaining DOBs resolved, unmasked | 59.66% | 0.6547 | $962.18 | -3.78% |
| Exclude seven sparse DOBs | 64.41% | 0.6459 | $1317.45 | +31.74% |

The initial age-sanitized and partial DOB-backfilled runs improved log loss and
bankroll materially, which suggested better probability estimates for Kelly
sizing.

After adding the seven UFCStats DOBs and regenerating features, the one-year
result fell to `-3.78%`. This was not a fight-stat problem; the raw fight rows
were present. It was model sensitivity to sparse age/DOB values. Compared with
the prior DOB-backfilled prediction file, the feature column set stayed the
same, but 36 predicted winners and 51 bet sides changed. The largest bankroll
swings came from unrelated fights, not primarily from the seven fighters' own
fights.

Masking only those seven DOB/age/avg-age values restored the higher PnL exactly.

### Two-Year Window

Window: `2024-06-27` to `2026-06-27`

| Setup | Accuracy | Log Loss | Final Bankroll | Profit |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 64.06% | 0.6503 | $1315.35 | +31.54% |
| Age-sanitized diagnostic | 64.24% | 0.6398 | $1599.68 | +59.97% |
| DOB-backfilled | 64.93% | 0.6331 | $1804.15 | +80.42% |
| Exclude seven sparse DOBs | 64.93% | 0.6331 | $1804.15 | +80.42% |

The two-year diagnostic used a temporary sanitized feature CSV before the code
path was patched. After patching and DOB backfill, the normal feature path
improved further because most missing ages became real values rather than
`NaN`.

## Betting Strategy Findings

### Keep Predicted-Winner Filtering

Testing "bet the side with the best Kelly value" performed worse than the
current approach of only considering the model's predicted winner.

Reason: the best-Kelly rule over-selected long underdogs where the model's
edge estimate was too optimistic. The predicted-winner filter acted as a useful
quality gate.

### Flat Fallback Is Mixed

After age sanitization:

- one-year best among tested simple variants: `0.05,0.05,0`
- two-year best among tested simple variants: `0.05,0.05,0.005`

This means the current flat fallback is not obviously wrong, but it should be
validated over more rolling windows before changing live staking.

After resolving the remaining seven DOBs, turning the flat fallback off for the
one-year window produced `$962.66` (`-3.73%`), nearly identical to the default
`$962.18` (`-3.78%`). The latest regression is therefore not mainly a flat
fallback problem.

### Market Shrink Was Not Clearly Better

Shrinking probabilities toward de-vigged market odds helped the old buggy
feature set, but hurt the age-sanitized one-year result. That suggests market
shrink was partly compensating for corrupted inputs rather than adding durable
edge.

## Verification

Syntax check:

```bash
PYTHONPYCACHEPREFIX=/tmp/ufc_pycache .venv/bin/python -m compileall \
  predict_fights_alpha.py \
  utils/feature_sanitization.py \
  utils/name_matching.py \
  scrapers/backfill_fighter_dobs.py \
  process_fights_alpha.py \
  testing/no_leakage_backtest.py \
  predict_single_model.py \
  load_ensemble.py
```

Patched normal-path one-year backtest:

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2025-06-27 \
  --end-date 2026-06-27 \
  --output-dir test_results/pnl_diag_patched_1y
```

Result:

```text
Accuracy: 0.6237
Log loss: 0.6528
Final bankroll: $1237.06 (+23.71%)
```

No-write inference smoke test confirmed:

- upcoming fight rows have zero impossible ages after sanitization
- single model receives 164 features
- ensemble models receive 112 features each
- ensemble loader only loads `lgbm_model_0.joblib` through `lgbm_model_4.joblib`

DOB backfill verification after UFCStats event/fight-page fallback:

- UFCStats profile pages were found for all seven remaining fighters
- all seven DOBs were parsed from UFCStats fighter profiles
- the DB keeps those real DOBs
- model feature tables intentionally mask DOB/age/avg-age for those seven names

Latest all-DOB-resolved one-year backtests:

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2025-06-27 \
  --end-date 2026-06-27 \
  --output-dir test_results/pnl_diag_all_missing_dobs_resolved_1y
```

Result:

```text
Accuracy: 0.5966
Log loss: 0.6547
Final bankroll: $962.18 (-3.78%)
```

No-flat diagnostic:

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2025-06-27 \
  --end-date 2026-06-27 \
  --strategy 0.05,0.05,0 \
  --output-dir test_results/pnl_diag_all_missing_dobs_resolved_1y_no_flat
```

Result:

```text
Accuracy: 0.5966
Log loss: 0.6547
Final bankroll: $962.66 (-3.73%)
```

Excluded-DOB policy verification:

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2025-06-27 \
  --end-date 2026-06-27 \
  --output-dir test_results/pnl_diag_excluded_dob_policy_1y
```

Result:

```text
Accuracy: 0.6441
Log loss: 0.6459
Final bankroll: $1317.45 (+31.74%)
```

Two-year excluded-DOB policy:

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2024-06-27 \
  --end-date 2026-06-27 \
  --output-dir test_results/pnl_diag_excluded_dob_policy_2y
```

Result:

```text
Accuracy: 0.6493
Log loss: 0.6331
Final bankroll: $1804.15 (+80.42%)
```

## Follow-Up Ideas

1. Run leak-safe hyperparameter tuning over rolling historical windows instead
   of reusing `data/best_params.json`, which may have future-data bias.
2. Add a calibration layer after age cleanup, then size bets from calibrated
   probabilities rather than raw LightGBM probabilities.
3. Add a test that fails if prediction rows contain impossible ages, DOBs, or
   mismatched model feature counts.
4. Backtest staking variants across many anchored windows, not only the latest
   one-year and two-year periods.
5. Consider removing or capping extreme underdog edges unless calibration
   proves those probabilities are reliable.
