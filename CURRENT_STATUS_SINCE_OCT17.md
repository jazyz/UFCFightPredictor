# Current Status Since Oct 17 Baseline

Date written: 2026-06-28

## Baseline

The Friday Oct 17 baseline is:

```text
09d6eec 2025-10-17 23:38:39 -0400 Auto-retraining
```

Current branch:

```text
feature/auto-retraining
```

Notable commits on this branch since that baseline through the regularized
model update:

```text
9903615 Add leak-safe retraining backtest
f3259e9 Fix leak-safe backtest coverage joins
3fe505d Audit DOB handling for PnL backtests
be2b19c add doc
577e88a Improve live betting PNL path
b5695b7 Improve UFC model PnL with regularized LGBM
```

Note: other later commits exist in `git log --all`. The list above highlights
the main direct-ancestry changes from the Oct 17 baseline through the current
regularized-model work.

## Major Changes Since Oct 17

### Leak-Safe Backtesting and Retraining

Added a rolling no-leakage evaluator:

```text
testing/no_leakage_backtest.py
```

It retrains a fresh LightGBM model before each event date using only fights
before that date, then scores predictions and betting PnL after the fact.

Added final-model training:

```text
train_final_model.py
```

This trains the deployable single model through a selected date and saves model
metadata.

### Data Repair and Feature Cleanup

Added DOB backfill tooling:

```text
scrapers/backfill_fighter_dobs.py
data/fighter_dob_backfill_report.json
data/supplemental_fighter_dobs.csv
```

Added odds repair/backfill tooling:

```text
scrapers/backfill_bestfightodds.py
data/supplemental_fight_odds.csv
```

Added shared feature cleanup and fighter-name normalization:

```text
utils/feature_sanitization.py
utils/name_matching.py
```

The sanitizer prevents missing DOBs from becoming impossible age values such as
2025 or 2026. The name matching handles aliases across UFCStats, UFC.com, and
odds sources.

### Live Prediction and Betting Fixes

Updated live prediction/betting code:

```text
predict_fights_alpha.py
betting_alpha.py
ml_web.py
load_ensemble.py
predict_single_model.py
app.py
```

Key fixes:

- live upcoming-fight features now better match historical training scale
- betting probability lookup uses canonical fighter names
- mirrored fighter-order probabilities are averaged consistently
- web/ensemble loaders avoid mixing single-model and ensemble artifacts
- `/predict` accepts an optional event date

### Documentation and Audit Notes

Added or updated:

```text
LEAK_SAFE_RETRAIN_BACKTEST_SUMMARY.md
PNL_IMPROVEMENT_AUDIT.md
AUTO_RETRAIN_GUIDE.md
```

These document the leak-safe backtester, retraining flow, DOB/age fixes, odds
coverage fixes, and PnL diagnostics.

## Current Worktree Status

As of this status update, the regularized LGBM implementation, backtest ledgers,
audit outputs, retrained single-model artifact, and summary documentation have
been committed and pushed on `feature/auto-retraining`.

Primary regularized-model documentation:

```text
test_results/regularized_lgbm_summary.md
```

## Current Statistical Status

### Full-DOB Robustness Audit

Main report:

```text
test_results/full_dob_fresh/FULL_DOB_ROBUSTNESS_AUDIT.md
```

This audit restored the seven previously masked DOB/age rows:

- Andrey Pulyaev
- Brando Pericic
- Chris Padilla
- Jose Ochoa
- Josh Hokit
- Kaan Ofli
- Myktybek Orolbai

Fresh full-DOB results:

| Run | Window | Accuracy | Log Loss | Profit | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: |
| default_1y | 2025-06-27 to 2026-06-27 | 59.7% | 0.661 | -$49.36 | 0.506 |
| edge2_no_flat_1y | 2025-06-27 to 2026-06-27 | 59.7% | 0.661 | -$50.56 | 0.540 |
| conservative_1y | 2025-06-27 to 2026-06-27 | 59.7% | 0.661 | -$29.17 | 0.501 |
| best_params_1y | 2025-06-27 to 2026-06-27 | 61.4% | 0.679 | $3.20 | 0.411 |
| default_2y | 2024-06-27 to 2026-06-27 | 62.4% | 0.644 | $167.56 | 0.178 |
| edge2_no_flat_2y | 2024-06-27 to 2026-06-27 | 62.4% | 0.644 | $181.22 | 0.201 |
| conservative_2y | 2024-06-27 to 2026-06-27 | 62.4% | 0.644 | $83.71 | 0.169 |
| best_params_2y | 2024-06-27 to 2026-06-27 | 63.3% | 0.659 | $280.57 | 0.125 |

Fresh full-DOB conclusion:

- best market-null p-value across fresh full-DOB runs: `0.125`
- Bonferroni-adjusted p-value across 8 fresh ledgers: `0.996`
- model probabilities beat de-vigged market log loss in `0/8` runs
- event-bootstrap profit confidence intervals were strictly positive in `0/8`
  runs
- all one-year full-DOB runs were negative or essentially breakeven

Interpretation: the earlier high-PnL masked-DOB results look more like
feature-policy/backtest fitting than a stable betting edge.

### Walk-Forward PnL Improvement Attempt

Main report:

```text
test_results/full_dob_fresh/WALK_FORWARD_PNL_IMPROVEMENT_AUDIT.md
```

The walk-forward search tried to improve PnL without reintroducing DOB masking.

Protocol:

- development window: `2024-06-27` to `2025-06-26`
- holdout window: `2025-06-27` to `2026-06-27`
- candidate strategies tested on development only: `576`
- one selected strategy evaluated on holdout

Selected strategy:

```json
{
  "model_label": "best_params_full_dob",
  "side_policy": "predicted_winner",
  "model_weight": 1.0,
  "min_edge": 0.16,
  "min_probability": 0.5,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

Development result:

- profit: `$381.52` (`+38.15%`)
- bets: `64`
- ROI on staked: `26.46%`
- max drawdown: `9.43%`

Holdout result:

- profit: `$30.70` (`+3.07%`)
- bets: `67`
- ROI on staked: `2.19%`
- max drawdown: `16.60%`

Holdout inference:

- market-null p-value: `0.288`
- event-bootstrap profit CI: `-$338.51` to `$409.99`
- probability bootstrap profit <= 0: `43.27%`
- model log loss: `0.679`
- de-vigged market log loss: `0.613`

Interpretation: the selected strategy improved holdout PnL slightly, but the
improvement is not statistically convincing.

### Regularized LGBM Model Update

Main report:

```text
test_results/regularized_lgbm_summary.md
```

Committed change:

```text
b5695b7 Improve UFC model PnL with regularized LGBM
```

The new production single-model artifact was retrained through `2026-06-27`
using:

```text
test_results/regularized_lgbm_params.json
```

This config is deliberately more regularized than the earlier default:

- fewer leaves: `num_leaves = 15`
- larger leaf support: `min_child_samples = 90`
- lower learning rate: `learning_rate = 0.035`
- row subsampling: `subsample = 0.75`
- feature subsampling: `colsample_bytree = 0.70`
- L1/L2 penalties: `reg_alpha = 0.05`, `reg_lambda = 1.5`

Important caveat: this was a hypothesis-driven manual config chosen after
diagnosing model overconfidence. It was not selected by a fully nested,
pre-registered hyperparameter search, so the result still has model-selection
bias risk.

Leak-safe two-year comparison:

| Run | Window | Accuracy | Log Loss | Final Bankroll | Profit |
| --- | --- | ---: | ---: | ---: | ---: |
| baseline default | 2024-06-27 to 2026-06-27 | 62.59% | 0.6399 | $1402.38 | +40.24% |
| regularized LGBM | 2024-06-27 to 2026-06-27 | 65.00% | 0.6318 | $1611.97 | +61.20% |

Recent holdout slice:

| Run | Window | Accuracy | Log Loss | Plain-Strategy ROI on Staked |
| --- | --- | ---: | ---: | ---: |
| baseline default | 2025-06-27 to 2026-06-27 | 61.74% | 0.6596 | 4.0% |
| regularized LGBM | 2025-06-27 to 2026-06-27 | 64.43% | 0.6418 | 10.2% |

Regularized-only walk-forward strategy search selected:

```json
{
  "model_label": "regularized_lgbm",
  "side_policy": "predicted_winner",
  "model_weight": 1.0,
  "min_edge": 0.16,
  "min_probability": 0.5,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

Selected-strategy holdout result:

- profit: `$198.17` (`+19.82%`)
- bets: `51`
- ROI on staked: `19.32%`
- max drawdown: `9.29%`
- market-null p-value: `0.0717`

Market log-loss note:

The standalone regularized model still trails de-vigged market probabilities on
holdout log loss (`0.6418` model vs `0.6127` market). However, a dev-selected
15% model / 85% market logit blend beats the market slightly on holdout:

| Probability | Dev Log Loss | Holdout Log Loss |
| --- | ---: | ---: |
| model only | 0.6215 | 0.6418 |
| market only | 0.5854 | 0.6127 |
| 15% model / 85% market logit blend | 0.5843 | 0.6112 |

Feature-importance export:

```text
test_results/regularized_lgbm_feature_importance.csv
```

Top features remain mostly matchup deltas, led by `oppelo oppdiff`,
`elo oppdiff`, `age oppdiff`, `wins oppdiff`, and `avg age oppdiff`.

### Long Nested Edge Audit

Main report:

```text
test_results/nested_edge_long/NESTED_EDGE_AUDIT_SUMMARY.md
```

New validation script:

```text
testing/nested_walk_forward_edge_audit.py
```

This audit generated long leak-safe ledgers from the available odds-history
start (`2022-02-05`) through `2026-06-27`, then repeatedly selected model and
strategy on the previous 365 days and evaluated the next 182-day holdout.

Long ledger comparison:

| Model | Fights | Rolling Fits | Accuracy | Log Loss | Full-Window PnL |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline default | 1249 | 188 | 62.53% | 0.6447 | +25.07% |
| regularized LGBM | 1249 | 188 | 63.65% | 0.6396 | +29.61% |

Nested selection, profit objective:

| Metric | Value |
| --- | ---: |
| folds | 7 |
| holdout fights | 962 |
| bets | 277 |
| profit | $170.39 |
| ROI on staked | 4.00% |
| positive folds | 4 / 7 |
| market-null p-value | 0.199 |
| event-bootstrap probability profit <= 0 | 32.02% |

Nested selection, ROI objective sensitivity:

| Metric | Value |
| --- | ---: |
| folds | 7 |
| holdout fights | 962 |
| bets | 148 |
| profit | $115.09 |
| ROI on staked | 12.62% |
| positive folds | 4 / 7 |
| market-null p-value | 0.048 |
| event-bootstrap probability profit <= 0 | 9.60% |

Interpretation: the ROI objective is the strongest current evidence, but it was
run as a sensitivity check after the profit objective. A simple two-objective
correction puts the market-null p-value around `0.096`, so this is promising
enough to paper-track, not enough to claim a proven edge.

Long market-log-loss check:

- development: `2022-02-05` to `2024-02-04`
- holdout: `2024-02-05` to `2026-06-27`
- dev-selected model weight in a logit market/model blend: `0.000`

| Probability | Dev Log Loss | Holdout Log Loss |
| --- | ---: | ---: |
| regularized model | 0.6495 | 0.6337 |
| de-vigged market | 0.6003 | 0.6009 |
| dev-selected blend | 0.6003 | 0.6009 |

Interpretation: the earlier 15% model / 85% market blend result did not hold
up on the longer split. On long-history development data, pure market was the
selected log-loss forecaster.

### Frozen Forward Paper-Tracking Policy

Freeze artifact:

```text
testing/freeze_forward_policy.py
test_results/frozen_forward_policy/frozen_forward_policy.md
test_results/frozen_forward_policy/frozen_forward_policy.json
```

As of `2026-06-28`, the ROI-objective nested selector has been frozen for
future paper tracking. It uses the trailing `2025-06-28` to `2026-06-27`
development window, the same baseline-default and regularized-LGBM long
ledgers, the existing walk-forward strategy grid, and the same minimum
development-bet constraint of `35`.

Candidate strategies evaluated: `576`.

Selected frozen strategy:

```json
{
  "model_label": "regularized_lgbm",
  "side_policy": "predicted_winner",
  "model_weight": 0.7,
  "min_edge": 0.02,
  "min_probability": 0.6,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

Development-window evidence:

| Metric | Value |
| --- | ---: |
| fights | 298 |
| bets | 44 |
| profit | $140.04 |
| ROI on staked | 38.76% |
| max drawdown | 3.74% |

Interpretation: this makes the forward test auditable but does not prove edge.
Future cards should be scored against this policy without changing the model
candidate set, selection objective, strategy grid, thresholds, or staking
rules. A real edge claim still requires post-freeze market-null and
event-bootstrap evidence.

### Engineered Feature Variant Audit

Feature audit:

```text
test_results/feature_variant_engineered_regularized_summary.md
```

The opt-in title-context and matchup-aggregate feature path was tested as a
regularized-LGBM challenger with leak-safe rolling retraining.

| Window | Feature Set | Accuracy | Log Loss | PnL |
| --- | --- | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | current regularized | 64.43% | 0.6418 | +24.66% |
| 2025-06-27 to 2026-06-27 | engineered challenger | 62.75% | 0.6506 | +4.12% |
| 2024-06-27 to 2026-06-27 | current regularized | 65.00% | 0.6318 | +61.20% |
| 2024-06-27 to 2026-06-27 | engineered challenger | 65.17% | 0.6364 | +47.95% |

Statistical audit for the engineered challenger:

```text
test_results/feature_variant_engineered_regularized_audit/edge_audit.md
```

Interpretation: do not promote these engineered features. They worsen
one-year metrics and two-year log loss/PnL, and they do not produce a stronger
market-relative edge claim. The production model and frozen forward policy
remain on `engineered_features=false`.

### Market Disagreement Audit

Disagreement audit:

```text
testing/market_disagreement_audit.py
test_results/market_disagreement_audit/market_disagreement_audit.md
test_results/market_disagreement_audit/market_disagreement_audit.json
```

This diagnostic reads the long leak-safe baseline and regularized ledgers,
reconstructs de-vigged market probabilities from the saved American odds, and
tests whether the side with the largest model-minus-market probability edge
actually wins more often than the market implies.

Standalone probability check:

| Model | Fights | Model Acc | Market Acc | Model LL | Market LL |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline default | 1220 | 62.21% | 68.77% | 0.6457 | 0.6006 |
| regularized LGBM | 1220 | 63.36% | 68.77% | 0.6404 | 0.6006 |

Interpretation: regularization improved the model, but standalone model
probabilities still do not beat the de-vigged market on log loss.

For the regularized model, edge-only disagreement remains negative:

| Slice | Fights | Actual Win | Market P | Flat Profit | Flat ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| edge >= 0.08 | 695 | 38.27% | 36.64% | -13.96u | -2.01% |
| edge >= 0.12 | 493 | 35.50% | 34.24% | -5.50u | -1.12% |

Adding a model-probability floor produces more plausible residual pockets:

| Slice | Fights | Actual Win | Market P | Flat Profit | Flat ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| model P >= 0.60, edge >= 0.02 | 355 | 61.13% | 54.60% | +28.69u | +8.08% |
| model P >= 0.60, edge >= 0.08 | 233 | 57.51% | 49.21% | +27.97u | +12.00% |
| model P >= 0.60, edge >= 0.12 | 165 | 53.33% | 45.17% | +20.77u | +12.59% |

The key stability caveat is visible in the `model P >= 0.60, edge >= 0.08`
yearly split:

| Year | Fights | Flat Profit | Flat ROI |
| --- | ---: | ---: | ---: |
| 2022 | 63 | +1.88u | +2.98% |
| 2023 | 50 | -7.62u | -15.24% |
| 2024 | 52 | +7.71u | +14.83% |
| 2025 | 40 | +20.46u | +51.15% |
| 2026 | 28 | +5.53u | +19.76% |

Interpretation: this supports the shape of the frozen policy, which requires
both positive edge and minimum model probability, but it is still diagnostic
and partly post-hoc. It strengthens the case for forward paper tracking, not
for declaring that a live market edge has been proven.

### Disagreement Forward-Selection Audit

Forward-selection audit:

```text
testing/disagreement_forward_selection_audit.py
test_results/disagreement_forward_selection_audit/DISAGREEMENT_FORWARD_SELECTION_SUMMARY.md
```

This follow-up reduces static threshold-picking bias. Each fold selects a
simple model-vs-market disagreement policy on the prior 365 days, freezes it,
and evaluates the next 182-day holdout. The policy family is intentionally
plain: flat 1-unit bets on the side with the largest model-minus-market edge,
with grids over model label, minimum edge, minimum model probability, and a
`+300` underdog cap.

Results across seven forward folds:

| Selection Objective | Bets | Profit | Flat ROI | Actual - Market | Positive Folds | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| profit | 373 | -3.49u | -0.93% | +2.47% | 4 / 7 | 0.342 |
| ROI | 161 | +10.15u | +6.30% | +5.07% | 4 / 7 | 0.107 |
| actual - market | 167 | +15.22u | +9.11% | +6.72% | 5 / 7 | 0.090 |

Interpretation: the forward-selected disagreement rule family is promising but
still not a real edge claim. The profit objective went slightly negative, and
the best uncorrected market-null p-value was only `0.090`. Since three
selection objectives were inspected, a simple Bonferroni adjustment puts the
best p-value around `0.27`.

## Current Bottom Line

The repo is now much better instrumented than it was on Oct 17:

- leak-safe rolling retraining exists
- DOB/age leakage and corruption are explicitly testable
- odds coverage and date joins are more robust
- market-null simulations and event bootstraps exist
- walk-forward strategy search exists

The regularized LGBM update improved the current leak-safe metrics materially,
but the evidence still does not prove a live betting edge.

The most honest read:

- the model likely contains weak predictive signal
- regularization reduced, but did not eliminate, calibration weakness
- de-vigged market probabilities still beat standalone model probabilities on
  raw holdout log loss
- the longer market-blend audit selected pure market probability, not a model
  residual
- edge-only model/market disagreement is negative in flat-bet tests; the more
  interesting pockets require both positive edge and a model-probability floor
- forward-selected simple disagreement policies remain weak after objective
  sensitivity; the best uncorrected market-null p-value is `0.090`
- profitable PnL variants remain sensitive to model policy and threshold search
- the best disagreement pockets are not uniformly stable by year, with the
  regularized `model P >= 0.60, edge >= 0.08` slice losing in 2023
- the best raw market-null p-value is `0.048` from the exploratory ROI
  objective, or about `0.096` after a simple two-objective correction
- this is promising but below a strong statistical-evidence threshold

Recommendation:

Do not materially increase staking based only on these backtests. Use the
frozen forward artifact above as the current paper-tracking policy. A real edge
claim needs future out-of-sample results that beat market-null and bootstrap
tests after the model params, selection objective, strategy grid, and staking
policy have been frozen.

## Independent PnL Investigation Update

Latest independent investigation date: 2026-06-28.

Fresh current-code no-leakage baselines were rerun outside the repository under
`/private/tmp`:

| Window | Fights | Accuracy | Log Loss | Default PnL |
| --- | ---: | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | 298 | 61.7% | 0.6596 | +11.90% |
| 2024-06-27 to 2026-06-27 | 580 | 62.6% | 0.6399 | +41.92% |

Important interpretation:

- de-vigged market probabilities still beat model probabilities on recent
  holdout log loss
- the model appears more useful as a disagreement filter than as a calibrated
  price
- broad positive-Kelly betting has high variance and weak holdout evidence
- high-disagreement underdog-heavy slices can improve PnL, but the sample is
  too thin to claim a proven live edge

Earlier risk-adjusted policy candidate from the fresh ledger, not the current
frozen forward policy:

```text
min_edge = 0.12
min_probability = 0.50
min_kelly = 0.0
kelly_fraction = 0.025
max_fraction = 0.025
positive_floor_fraction = 0.0
negative_flat_fraction = 0.0
```

Fresh split results for that policy:

| Window | Bets | PnL | ROI on Staked | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| 2024-06-27 to 2025-06-26 | 83 | +15.78% | 19.91% | 4.88% |
| 2025-06-27 to 2026-06-27 | 82 | +12.19% | 13.62% | 10.71% |

The holdout market-null p-value was about `0.085`, so this should be treated as
a promising risk-control candidate rather than proof of edge.

Operational PnL implementation update:

- `utils/production_predictions.py` is now the shared production single-model
  prediction writer
- `ml_web.py` and `predict_single_model.py` both use that shared writer
- `load_ensemble.py` now writes `data/ensemble_predictions.csv`, not
  `data/betting_predictions.csv`
- `betting_alpha.py` now loads
  `test_results/frozen_forward_policy/frozen_forward_policy.json` and applies
  the frozen model/market blend, thresholds, and staking settings
- `betting_alpha.py` writes paper-tracking output and labels it as not proof of
  live edge
- `betting_alpha.py` now also writes machine-readable forward paper ledgers:
  `test_results/forward_paper_tracking/latest_forward_paper_bets.csv` and
  `test_results/forward_paper_tracking/latest_forward_paper_bets.json`
- `test_results/forward_paper_tracking/README.md` documents that future ledgers
  only count as evidence if generated and archived before outcomes are known
- `testing/settle_forward_paper_ledger.py` predefines how archived forward
  ledgers are settled after outcomes are known and reports fixed-stake
  market-null plus event-bootstrap checks

Validation:

- compile check passed for `betting_alpha.py`, `ml_web.py`,
  `predict_single_model.py`, `load_ensemble.py`, and
  `utils/production_predictions.py`
- a temporary in-range prediction input generated canonical prediction outputs
  under `/private/tmp/ufc_forward_prediction_smoke`
- a direct frozen-policy betting smoke test selected the expected model/market
  blended candidate and stake
- a synthetic forward-ledger smoke test wrote CSV/JSON paper-bet ledgers under
  `/private/tmp`
- a synthetic settlement smoke test generated an outcome template, settled all
  rows, and wrote settled CSV/JSON/Markdown evidence under `/private/tmp`

Current operational caveat: the checked-in `data/predict_fights_alpha.csv` is
stale and fails the live feature-range guard with out-of-training-range values.
Regenerate that file from the next card before running `predict_single_model.py`
or `ml_web.py` for forward paper scoring.
