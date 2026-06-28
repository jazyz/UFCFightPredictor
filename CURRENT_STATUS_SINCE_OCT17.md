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

Commits on this branch since that baseline:

```text
9903615 Add leak-safe retraining backtest
f3259e9 Fix leak-safe backtest coverage joins
3fe505d Audit DOB handling for PnL backtests
be2b19c add doc
577e88a Improve live betting PNL path
```

Note: other later commits exist in `git log --all`, but the list above is the
direct ancestry from the Oct 17 baseline to the current branch HEAD.

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

## Current Worktree Before Commit

As of this status update, `git status --short` shows no tracked-file
modifications. The current uncommitted worktree consists of generated audit,
diagnostic, and retraining artifacts under `test_results/`, plus `tester.py`.

Untracked result groups to be committed:

```text
test_results/feature_regression_audit_oct17/
test_results/pnl_after_first4_1y/
test_results/pnl_after_first4_2y/
test_results/pnl_diag_age_nan_1y/
test_results/pnl_diag_age_nan_2y/
test_results/pnl_diag_all_missing_dobs_resolved_1y/
test_results/pnl_diag_all_missing_dobs_resolved_1y_no_flat/
test_results/pnl_diag_best_params_1y/
test_results/pnl_diag_dob_backfilled_1y/
test_results/pnl_diag_dob_backfilled_2y/
test_results/pnl_diag_exclude_7_dobs_1y/
test_results/pnl_diag_excluded_dob_policy_1y/
test_results/pnl_diag_excluded_dob_policy_2y/
test_results/pnl_diag_patched_1y/
test_results/pnl_no_blank_winner_stats_1y/
test_results/pnl_no_blank_winner_stats_audit/
test_results/pnl_policy_smoke_closer/
test_results/womens_retrain/
tester.py
```

The latest audit-specific scratch outputs from independent analysis were written
under `/private/tmp` and are intentionally not part of the repository.

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

## Current Bottom Line

The repo is now much better instrumented than it was on Oct 17:

- leak-safe rolling retraining exists
- DOB/age leakage and corruption are explicitly testable
- odds coverage and date joins are more robust
- market-null simulations and event bootstraps exist
- walk-forward strategy search exists

However, the current evidence does not prove a live betting edge.

The most honest read:

- the model may contain weak predictive signal
- the raw probabilities are overconfident relative to market odds
- profitable PnL variants are sensitive to feature policy and threshold search
- the full-DOB and walk-forward holdout tests do not clear statistical evidence
  thresholds

Recommendation:

Do not increase staking based on the current backtests. Treat the selected
walk-forward strategy, at most, as a cautious risk-control heuristic to paper
track on future cards. A real edge claim needs future out-of-sample results
that beat market-null and bootstrap tests after the strategy is frozen.

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

Best risk-adjusted policy from the fresh ledger:

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

Operational PnL risk:

- `betting_alpha.py` consumes `data/betting_predictions.csv`
- `ml_web.py` writes that file from the single production model
- `load_ensemble.py` also writes that file from the older ensemble artifacts
- whichever prediction script ran last controls live betting recommendations

Recommended next implementation step: make `betting_predictions.csv` generation
single-source and freeze the live betting policy above for forward paper
tracking before increasing real staking.
