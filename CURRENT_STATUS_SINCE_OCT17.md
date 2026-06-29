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
audit outputs, retrained single-model artifact, frozen paper-tracking policies,
universe audits, feature audits, residual audits, and recency-weighted training
audit are documented on `feature/auto-retraining`.

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

### Market Residual Meta Audit

Residual meta audit:

```text
testing/market_residual_meta_audit.py
test_results/market_residual_meta_audit/MARKET_RESIDUAL_META_AUDIT_SUMMARY.md
```

This audit asks a narrower probability question: after controlling for the
de-vigged market logit, do the saved leak-safe model probabilities contain
incremental information about future fight outcomes?

It aligns the baseline-default and regularized-LGBM long ledgers by fight,
then trains only a small logistic meta-model inside each forward development
window. The primary residual feature is:

```text
logit(model probability) - logit(market probability)
```

Primary protocol:

- aligned fights: `1220`
- development window: `730` days
- holdout window: `182` days
- forward folds: `5`
- logistic L2 inverse regularization: `C = 1.0`
- market-null simulations: `1000`

Primary holdout results:

| Variant | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| market recalibrated | 0.6009 | 0.6011 | -0.0002 | 3 / 5 | 0.519 | 0.160 |
| market + baseline residual | 0.6009 | 0.5993 | +0.0015 | 4 / 5 | 0.346 | 0.030 |
| market + regularized residual | 0.6009 | 0.5979 | +0.0030 | 4 / 5 | 0.218 | 0.012 |
| market + both residuals | 0.6009 | 0.5983 | +0.0026 | 4 / 5 | 0.259 | 0.012 |

The strongest primary variant is `market + regularized residual`. Its
uncorrected market-null p-value is `0.012`; a simple Bonferroni correction
across four primary variants gives about `0.048`. The average regularized
residual coefficient across folds was positive at `+0.2616`.

Sensitivity checks kept the regularized residual positive:

| Config | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 730d dev, C=1.0 | 0.6009 | 0.5979 | +0.0030 | 4 / 5 | 0.218 | 0.012 |
| 365d dev, C=1.0 | 0.6009 | 0.5962 | +0.0047 | 4 / 5 | 0.126 | 0.003 |
| 730d dev, C=0.25 | 0.6009 | 0.5981 | +0.0028 | 4 / 5 | 0.173 | 0.012 |

Interpretation: this is the strongest current evidence that the model has a
small probability edge after controlling for market price. It still should not
be treated as a live betting edge claim by itself: the absolute log-loss gain
is small, and event-bootstrap intervals still cross zero.

Residual-meta config-selection audit:

```text
testing/residual_meta_config_selection_audit.py
test_results/residual_meta_config_selection_audit/residual_meta_config_selection_audit.md
test_results/residual_meta_config_selection_audit/residual_meta_config_selection_audit.json
test_results/residual_meta_config_selection_audit/rolling_selected_predictions.csv
```

This audit checks whether the tempting residual-meta config choices can be
selected without looking at future folds. It compares the inspected configs
(`365d/C=1.0`, `730d/C=1.0`, and `730d/C=0.25`) and all residual variants.
For each evaluation fold after fold 1, it selects the candidate with the best
prior holdout log-loss delta, then scores that candidate on the next fold.

Rolling config-selection result:

| Metric | Value |
| --- | ---: |
| eval folds | 4 |
| fights | 539 |
| market log loss | 0.6022 |
| selected meta log loss | 0.6017 |
| market - selected meta log loss | +0.0005 |
| positive eval folds | 3 / 4 |
| event-bootstrap P(delta <= 0) | 0.458 |
| rolling market-null p | 0.084 |

Interpretation: this weakens the case for promoting the best-looking `365d`
residual-meta configuration. The full-holdout `365d/C=1.0` regularized-residual
candidate has `+0.0047` delta LL, but a rolling selector over the inspected
config family only achieves `+0.0005` with weak event-bootstrap support and a
non-significant rolling market-null p-value.

Conservative residual transform freeze:

```text
testing/freeze_market_residual_meta.py
test_results/frozen_market_residual_meta/frozen_market_residual_meta.md
test_results/frozen_market_residual_meta/frozen_market_residual_meta.json
```

As of `2026-06-28`, the frozen residual transform uses the trailing
`2024-06-28` to `2026-06-27` training window, the `regularized_lgbm` residual,
and stronger regularization (`C = 0.25`) rather than the best-looking
sensitivity configuration.

Frozen coefficients:

| Term | Value |
| --- | ---: |
| intercept | -0.00677046 |
| market logit | 1.21510222 |
| regularized residual logit delta | 0.31975697 |

This gives the probability-edge hypothesis a pre-outcome transform for future
paper tracking. It still has no post-freeze evidence yet.

### Residual Negative-Control Audit

Residual negative-control audit:

```text
testing/residual_negative_control_audit.py
test_results/residual_negative_control_audit/RESIDUAL_NEGATIVE_CONTROL_AUDIT_SUMMARY.md
```

This audit keeps market probabilities and outcomes fixed, then breaks the
residual adjustment by sign-flipping or permuting it. The tested variant is
`market_plus_regularized_lgbm`.

Fixed controls:

| Control | Log Loss | Market - Candidate LL |
| --- | ---: | ---: |
| observed residual | 0.5979 | +0.0030 |
| market only | 0.6009 | 0.0000 |
| flipped residual | 0.6146 | -0.0137 |
| half residual | 0.5979 | +0.0030 |
| 1.5x residual | 0.6019 | -0.0010 |

Permutation controls:

| Control | Null Mean Delta LL | Null 95% Interval | P-value |
| --- | ---: | --- | ---: |
| global residual permutation | -0.0057 | -0.0131 to +0.0017 | 0.012 |
| within-fold residual permutation | -0.0056 | -0.0130 to +0.0018 | 0.010 |
| within-year residual permutation | -0.0058 | -0.0133 to +0.0015 | 0.010 |

Interpretation: this is a useful positive robustness check. The aligned
residual beats sign-flipped and permuted controls, which supports a real
model-after-market probability signal. It still does not prove a live betting
edge: the 2026 slice is negative, monetized PnL remains weak, and the
half-strength residual control was slightly better than the observed residual.

### Residual Shrinkage Audit

Residual shrinkage audit:

```text
testing/residual_shrinkage_audit.py
test_results/residual_shrinkage_audit/RESIDUAL_SHRINKAGE_AUDIT_SUMMARY.md
test_results/residual_shrinkage_audit/residual_shrinkage_audit.json
test_results/residual_shrinkage_audit_expanded/RESIDUAL_SHRINKAGE_AUDIT_SUMMARY.md
```

This audit tests whether the post-hoc half-residual hint can be converted into
a rule selected without future holdout outcomes. Each outer fold fits the
residual meta model on the first part of the development window, chooses a
residual scale on the later development slice, refits on the full development
window, then applies the chosen scale to the future holdout.

Primary capped-grid protocol:

| Policy | Fights | Log Loss | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| market | 704 | 0.6009 | 0.0000 | 0 / 5 | n/a | n/a |
| selected shrinkage, grid 0.00-1.00 | 704 | 0.5971 | +0.0038 | 4 / 5 | 0.140 | 0.005 |
| fixed half residual | 704 | 0.5979 | +0.0030 | 4 / 5 | 0.051 | 0.015 |
| unshrunk residual meta | 704 | 0.5979 | +0.0030 | 4 / 5 | 0.218 | 0.015 |

Selected shrinkage by outer fold:

| Fold | Holdout Window | Selected Scale | Holdout Delta LL |
| ---: | --- | ---: | ---: |
| 1 | 2024-02-05 to 2024-08-04 | 1.00 | +0.0070 |
| 2 | 2024-08-05 to 2025-02-02 | 1.00 | +0.0077 |
| 3 | 2025-02-03 to 2025-08-03 | 1.00 | +0.0026 |
| 4 | 2025-08-04 to 2026-02-01 | 0.75 | +0.0053 |
| 5 | 2026-02-02 to 2026-06-27 | 0.75 | -0.0047 |

Expanded-grid sensitivity (`0.00` to `1.50`) also stayed positive:
selected-scale Delta LL `+0.0035`, market-null p-value `0.007`, and
bootstrap `P(delta <= 0) = 0.217`.

Interpretation: this is the strongest probability-translation evidence so far
that the model has some incremental information after market prices. The
market-null p-value reruns the inner shrinkage selection under simulated market
outcomes, which is a better guard against selection overfit than the earlier
half-residual diagnostic. It still is not a live edge claim: event-bootstrap
uncertainty crosses zero, one of five folds is negative, and the negative fold
is the most recent 2026 holdout.

### Residual Edge Concentration Audit

Residual edge concentration audit:

```text
testing/residual_edge_concentration_audit.py
test_results/residual_edge_concentration_audit/residual_edge_concentration_audit.md
test_results/residual_edge_concentration_audit/residual_edge_concentration_audit.json
```

This audit checks whether the residual-shrinkage probability gain is broad or
carried by a small number of events/fights. It reads the selected-shrinkage
holdout predictions and computes per-fight/event log-loss deltas versus the
de-vigged market.

Policy concentration:

| Policy | Fights | Events | Delta LL | Positive Fights | Positive Events | Events To Erase Edge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selected shrinkage | 704 | 102 | +0.0038 | 65.8% | 63.7% | 7 |
| fixed half residual | 704 | 102 | +0.0030 | 65.8% | 64.7% | 11 |
| unshrunk meta | 704 | 102 | +0.0030 | 65.8% | 62.7% | 5 |

Removal sensitivity:

| Policy | Remove Top Events | Remaining Delta LL | Remaining Sum Delta |
| --- | ---: | ---: | ---: |
| selected shrinkage | 1 | +0.0031 | +2.1669 |
| selected shrinkage | 3 | +0.0019 | +1.2687 |
| selected shrinkage | 5 | +0.0007 | +0.4979 |
| selected shrinkage | 10 | -0.0020 | -1.2202 |
| fixed half residual | 10 | +0.0000 | +0.0295 |
| unshrunk meta | 5 | -0.0003 | -0.1817 |

Interpretation: the residual probability edge is positive, but not broad or
high-margin. Removing only the top seven selected-shrinkage events erases the
aggregate log-loss edge; removing the top ten makes it clearly negative. This
does not invalidate the residual signal, but it does make the live-edge claim
more fragile and reinforces the paper-tracking-only stance.

### Residual Shrinkage Fixed PnL Audit

Residual shrinkage fixed-policy PnL audit:

```text
testing/residual_shrinkage_fixed_pnl_audit.py
test_results/residual_shrinkage_fixed_pnl_audit/RESIDUAL_SHRINKAGE_FIXED_PNL_AUDIT_SUMMARY.md
test_results/residual_shrinkage_fixed_pnl_audit/residual_shrinkage_fixed_pnl_audit.json
```

This audit applies the already frozen residual-meta paper thresholds to the
out-of-sample shrinkage probabilities. It does not select new betting
thresholds from the shrinkage holdout outcomes. Fixed rule: best residual edge,
minimum edge `0.02`, minimum probability `0.60`, maximum underdog odds `+300`,
flat `1u`.

| Probability Policy | Bets | Profit | ROI | Actual - Market | Positive Folds | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected shrinkage | 399 | +4.55u | 1.14% | +3.65% | 3 / 5 | 0.354 | 0.046 |
| fixed half residual | 288 | +8.39u | 2.91% | +4.78% | 3 / 5 | 0.197 | 0.024 |
| unshrunk residual meta | 418 | +3.40u | 0.81% | +3.50% | 3 / 5 | 0.389 | 0.049 |

Interpretation: this is directionally supportive but not enough for a live
edge claim. The best conditional market-null p-value is `0.024` for fixed-half
residual, or about `0.071` after a simple correction across the three
probability policies. Event-bootstrap profit intervals still cross zero, and
only `3/5` folds are positive for every policy.

### Residual Event-Cap Audit

Residual event-cap audit:

```text
testing/residual_event_cap_audit.py
test_results/residual_event_cap_audit/residual_event_cap_audit.md
test_results/residual_event_cap_audit/residual_event_cap_audit.json
```

This diagnostic applies simple per-event bet caps to the fixed residual
paper-policy bets. Within each event, bets are ranked by residual edge; cap
`1` keeps only the highest-edge bet on each card, and cap `all` keeps the
original fixed-policy bet set. This is exploratory because the cap family is
being inspected after the historical ledger exists.

Selected-shrinkage cap results:

| Cap/Event | Bets | Events | Profit | ROI | Positive Folds | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100 | 100 | +11.92u | 11.92% | 4 / 5 | 0.021 | 0.006 |
| 2 | 196 | 100 | +15.75u | 8.04% | 4 / 5 | 0.026 | 0.003 |
| 3 | 279 | 100 | +17.45u | 6.25% | 4 / 5 | 0.022 | 0.003 |
| 5 | 374 | 100 | +8.32u | 2.22% | 3 / 5 | 0.238 | 0.026 |
| all | 399 | 100 | +4.55u | 1.14% | 3 / 5 | 0.350 | 0.044 |

The best historical cap across all 15 inspected policy/cap variants was
`unshrunk_meta|cap=3`, with `+17.52u`. A market-null simulation that reruns the
same 15-way variant selection under simulated fight outcomes gave a
selection-adjusted p-value of `0.011`.

Interpretation: per-event caps are a promising risk-control direction because
lower-ranked same-card bets appear dilutive. But this still should not be
promoted as a live edge claim: the cap family was discovered on the same
historical residual ledger. The honest next step is to freeze one simple capped
variant before future outcomes and paper-track it unchanged.

### Residual Event-Cap Rolling Selection Audit

Rolling cap-selection audit:

```text
testing/residual_event_cap_rolling_selection_audit.py
test_results/residual_event_cap_rolling_selection_audit/residual_event_cap_rolling_selection_audit.md
test_results/residual_event_cap_rolling_selection_audit/residual_event_cap_rolling_selection_audit.json
test_results/residual_event_cap_rolling_selection_audit/rolling_selected_bets.csv
```

This is a stricter check than the static event-cap audit: for each evaluation
fold after fold 1, it selects a cap/policy using only prior folds, then scores
that selected variant on the next fold. Minimum development bets: `35`.
Market-null simulations rerun the same rolling selection under simulated
market outcomes.

| Family | Objective | Variants | Eval Folds | Bets | Profit | ROI | Positive Folds | Bootstrap P(profit <= 0) | Rolling Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen residual-meta caps | profit | 5 | 4 | 170 | +9.52u | 5.60% | 3 / 4 | 0.083 | 0.017 |
| frozen residual-meta caps | ROI | 5 | 4 | 145 | +11.89u | 8.20% | 3 / 4 | 0.048 | 0.008 |
| selected-shrinkage caps | profit | 5 | 4 | 210 | +12.15u | 5.79% | 3 / 4 | 0.068 | 0.008 |
| selected-shrinkage caps | ROI | 5 | 4 | 111 | +6.83u | 6.15% | 3 / 4 | 0.132 | 0.042 |
| all shrinkage policy caps | profit | 15 | 4 | 189 | +10.81u | 5.72% | 3 / 4 | 0.090 | 0.011 |
| all shrinkage policy caps | ROI | 15 | 4 | 100 | +6.28u | 6.28% | 3 / 4 | 0.150 | 0.047 |

Interpretation: the cap idea survives a rolling prior-fold selection check,
which meaningfully reduces the concern that cap `3` is pure full-sample
overfit. The caveats remain material: only four evaluation folds are available,
the latest fold is still negative for every rolling selector, and this remains
historical evidence rather than post-freeze proof. It does, however,
strengthen the case for the frozen capped residual policy as the next
paper-tracked hypothesis.

### Residual Event-Cap Ranking Audit

Ranking audit:

```text
testing/residual_event_cap_ranking_audit.py
test_results/residual_event_cap_ranking_audit/residual_event_cap_ranking_audit.md
test_results/residual_event_cap_ranking_audit/residual_event_cap_ranking_audit.json
test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv
```

This diagnostic tests whether the event cap works because of the residual-edge
ranking rule, not merely because exposure is reduced. It compares cap `3` by
top residual edge against bottom-edge, probability-ranked,
market-probability-ranked, and random same-event selections.

| Policy | Top Edge Profit | Bottom Edge Profit | Random Mean | P(random >= top edge) |
| --- | ---: | ---: | ---: | ---: |
| frozen residual-meta | +19.12u | +4.99u | +6.63u | 0.004 |
| fixed half residual | +15.53u | +3.30u | +9.41u | 0.040 |
| selected shrinkage | +17.45u | -3.53u | +8.44u | 0.042 |
| unshrunk meta | +17.52u | -5.05u | +7.64u | 0.034 |

Interpretation: the cap's residual-edge ordering appears to matter. For the
frozen residual-meta ledger, only `0.4%` of random same-event cap simulations
matched or beat the top-edge result. This supports the frozen ranking rule as
more than generic exposure reduction, while remaining historical evidence that
still needs post-freeze confirmation.

### Frozen Residual Event-Cap Paper Policy

Frozen capped residual policy:

```text
testing/freeze_residual_event_cap_paper_policy.py
test_results/frozen_residual_event_cap_paper_policy/frozen_residual_event_cap_paper_policy.md
test_results/frozen_residual_event_cap_paper_policy/frozen_residual_event_cap_paper_policy.json
```

As of `2026-06-28`, a capped residual-meta paper policy is frozen for future
tracking. It uses the already frozen residual transform
(`test_results/frozen_market_residual_meta/frozen_market_residual_meta.json`),
the same fixed thresholds as the residual paper policy, and a maximum of
`3` paper bets per event ranked by residual edge.

Frozen capped rule:

| Rule | Value |
| --- | ---: |
| minimum residual edge | 2.00% |
| minimum meta probability | 60.00% |
| maximum underdog odds | +300 |
| max bets per event | 3 |
| event ranking | residual edge desc, meta probability desc, fight key asc |
| stake | 1u flat paper stake |

Historical fixed-ledger diagnostic after applying the cap:

| Metric | Value |
| --- | ---: |
| source bets before cap | 354 |
| capped bets | 262 |
| capped events | 99 |
| flat profit | +19.12u |
| flat ROI | 7.30% |
| actual - market | 7.68% |
| positive folds | 4 / 5 |
| event-bootstrap P(profit <= 0) | 0.016 |
| market-null p-value | 0.002 |

Interpretation: this is the clean forward-tracking contract for the capped
residual hypothesis. It is intentionally not a live recommendation: the cap
was chosen from historical diagnostics, so the only decisive evidence would be
post-freeze paper performance scored without changing the transform, thresholds,
cap, ranking rule, or stake size.

### Residual Cap Regime Audit

Residual cap-regime audit:

```text
testing/residual_cap_regime_audit.py
test_results/residual_cap_regime_audit/residual_cap_regime_audit.md
test_results/residual_cap_regime_audit/residual_cap_regime_audit.json
```

This diagnostic decomposes the frozen residual-meta top-edge cap-3 historical
paper ledger by market regime. It does not retrain, select thresholds, or
change the frozen policy.

Aggregate cap-3 result:

| Metric | Value |
| --- | ---: |
| bets | 262 |
| events | 99 |
| profit | +19.12u |
| ROI | 7.30% |
| actual - market | 7.68% |
| event-bootstrap P(profit <= 0) | 0.015 |
| market-null p-value | 0.001 |

Key regime diagnostics:

| Slice | Bets | Profit | ROI | Market-Null p |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 103 | +14.39u | 13.97% | 0.002 |
| 2025-2026 | 159 | +4.73u | 2.97% | 0.071 |
| event rank 1 | 99 | +4.99u | 5.04% | 0.075 |
| event rank 2 | 92 | +14.15u | 15.38% | 0.001 |
| event rank 3 | 71 | -0.02u | -0.03% | 0.293 |
| market P < 0.60 | 31 | +12.31u | 39.71% | 0.001 |
| 2025-2026 and market P < 0.60 | 21 | +9.13u | 43.48% | 0.003 |
| residual edge 0.03-0.05 | 137 | +16.63u | 12.14% | 0.001 |
| residual edge >= 0.08 | 4 | -0.55u | -13.74% | 0.553 |
| middle/welter | 79 | +15.99u | 20.24% | <0.001 |
| light/feather | 81 | -6.36u | -7.85% | 0.701 |

Interpretation: the aggregate cap-3 result remains directionally interesting,
but it is not a broad regime-invariant edge. Rank `2` carried most of the
event-rank profit, rank `3` was flat, the recent lower-confidence favorite
pocket is only `21` bets, and removing the top `15` positive events erases
aggregate profit. This is useful for monitoring, not permission to carve a new
live slice from the historical ledger.

### Residual Slice Validation Audit

Residual slice-validation audit:

```text
testing/residual_slice_validation_audit.py
test_results/residual_slice_validation_audit/residual_slice_validation_audit.md
test_results/residual_slice_validation_audit/residual_slice_validation_audit.json
```

This audit checks whether simple residual slices selected from earlier
outcomes survive later periods. The candidate menus are fixed before the audit:
probability slices use market-probability bins, absolute residual-edge bins,
edge direction, and title group; betting slices use market-probability bins,
residual-edge bins, model-probability bins, title group, plus `all`.
Market-null simulations rerun the same slice-selection procedure.

Probability-slice validation:

| Protocol | Selected Slice | Evaluation | Fights | Delta LL | Market-Null p |
| --- | --- | --- | ---: | ---: | ---: |
| 2024 selects, 2025-2026 evaluates | market P 0.70-0.80 | 2025-2026 | 50 | -0.0135 | 0.788 |
| rolling prior-fold selection | mixed prior-fold slices | folds 2-5 | 89 | +0.0095 | 0.067 |

Rolling probability selections:

| Eval Fold | Selected Slice | Eval Fights | Eval Delta LL |
| ---: | --- | ---: | ---: |
| 2 | abs edge 0.05-0.08 | 41 | +0.0406 |
| 3 | market P 0.70-0.80 | 15 | -0.0066 |
| 4 | market P 0.70-0.80 | 16 | +0.0035 |
| 5 | market P 0.70-0.80 | 17 | -0.0458 |

Capped-bet slice validation:

| Protocol | Selected Slice | Evaluation | Bets | Profit | ROI | Market-Null p |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 2024 selects, 2025-2026 evaluates | all cap-3 bets | 2025-2026 | 159 | +4.73u | 2.97% | 0.049 |
| rolling prior-fold selection | all cap-3 bets every fold | folds 2-5 | 195 | +11.75u | 6.03% | 0.003 |

Interpretation: this mostly validates the existing capped residual monitoring
idea rather than a new slice. The 2024-selected probability slice fails badly
out of period, and rolling probability selection is only marginal after
market-null selection adjustment. The capped-bet selector simply chose `all`
cap-3 bets in every rolling fold, which supports the frozen cap-3 policy
diagnostic but does not solve the recent fold weakness: fold `5` remained
negative at `-1.78u`.

### Residual Vs Market Favorite Audit

Residual vs market-favorite benchmark audit:

```text
testing/residual_vs_market_favorite_audit.py
test_results/residual_vs_market_favorite_audit/residual_vs_market_favorite_audit.md
test_results/residual_vs_market_favorite_audit/residual_vs_market_favorite_audit.json
```

This diagnostic checks whether the frozen residual-meta top-edge cap-3 result
is just generic favorite exposure. It compares the residual cap ledger against
market-only favorite benchmarks on the same historical event dates, including
same per-event bet counts.

Aggregate benchmark:

| Benchmark | Bets | Events | Profit | ROI | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: |
| residual cap-3 | 262 | 99 | +19.12u | 7.30% | 0.001 |
| top market favorites, same event counts | 262 | 99 | +0.07u | 0.03% | 0.113 |
| low-confidence market favorites, same event counts | 262 | 99 | -2.16u | -0.83% | 0.354 |
| top 3 market favorites per same event | 297 | 99 | +3.99u | 1.34% | 0.049 |
| all market favorites on same events | 680 | 99 | -12.77u | -1.88% | 0.257 |

Paired event-bootstrap comparison versus residual cap-3:

| Benchmark | Residual - Benchmark Profit | Bootstrap P(diff <= 0) | 95% Diff CI |
| --- | ---: | ---: | --- |
| top market favorites, same event counts | +19.05u | 0.018 | +1.11u to +37.14u |
| low-confidence market favorites, same event counts | +21.28u | 0.046 | -3.26u to +46.19u |
| top 3 market favorites per same event | +15.13u | 0.053 | -3.25u to +33.80u |
| all market favorites on same events | +31.89u | 0.007 | +5.87u to +58.16u |

Random same-event favorite benchmark:

| Metric | Value |
| --- | ---: |
| random iterations | 20000 |
| random mean profit | -2.95u |
| random 95% interval | -19.91u to +13.66u |
| P(random >= residual) | 0.005 |

Period caveat:

| Period | Residual Cap-3 | Top-Market Same Count | Low-Confidence Same Count |
| --- | ---: | ---: | ---: |
| 2024 | +14.39u | +5.55u | +8.01u |
| 2025-2026 | +4.73u | -5.47u | -10.17u |
| last 365 days | +0.38u | -2.20u | +3.29u |

Interpretation: this strengthens the historical model-specific selection
claim. The residual cap-3 ledger is not explained by simply betting favorites,
top market favorites, or random same-event favorites. But it still is not a
strong live-edge claim: the last-365-day residual result is only `+0.38u`, and
the lower-confidence favorite benchmark beats residual over that recent slice.
Future paper tracking is still the deciding evidence.

### Residual Meta PnL Audit

Residual meta PnL audit:

```text
testing/residual_meta_pnl_audit.py
test_results/residual_meta_pnl_audit/RESIDUAL_META_PNL_AUDIT_SUMMARY.md
```

This audit asks whether the residual probability signal can be converted into
a simple flat-stake betting rule. Each outer fold uses the first part of its
development window to fit the residual meta layer, the second part to select
betting thresholds from out-of-sample meta probabilities, and the next holdout
window to evaluate the frozen threshold policy.

The protocol reruns the whole inner meta-training, threshold selection, and
outer holdout loop under a de-vigged market-null simulation.

Results:

| Selection Objective | Bets | Profit | Flat ROI | Actual - Market | Positive Folds | Selection-Null p | Bootstrap P(profit <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| profit | 363 | +7.46u | +2.06% | +4.10% | 4 / 5 | 0.066 | 0.258 |
| ROI | 304 | +4.31u | +1.42% | +3.56% | 4 / 5 | 0.144 | 0.344 |
| actual - market | 311 | +6.67u | +2.14% | +4.08% | 4 / 5 | 0.083 | 0.265 |
| fixed edge>=0.02, p>=0.60 | 354 | +2.44u | +0.69% | +3.19% | 3 / 5 | 0.117 | 0.421 |

Interpretation: the residual meta probabilities produce positive PnL across
all three objective sensitivities, which is directionally consistent with the
log-loss edge. The monetization evidence is still weaker than the probability
evidence: the best selection-adjusted market-null p-value is `0.066` before
correcting for three inspected objectives, and the event-bootstrap uncertainty
still crosses zero.

Frozen residual-meta paper policy:

```text
testing/freeze_residual_meta_paper_policy.py
test_results/frozen_residual_meta_paper_policy/frozen_residual_meta_paper_policy.md
test_results/frozen_residual_meta_paper_policy/frozen_residual_meta_paper_policy.json
```

As of `2026-06-28`, a conservative residual-meta paper policy has also been
frozen: best residual edge, minimum residual edge `0.02`, minimum meta
probability `0.60`, max underdog odds `+300`, and flat `1u` paper stake. The
fixed-policy historical diagnostic was only `+2.44u` with market-null p-value
`0.117`, so this is a future-evidence collection contract, not a live staking
recommendation.

### Residual Signal Slice Audit

Residual slice audit:

```text
testing/residual_signal_slice_audit.py
test_results/residual_signal_slice_audit/RESIDUAL_SIGNAL_SLICE_AUDIT_SUMMARY.md
```

This diagnostic decomposes the residual log-loss signal and the fixed
residual-meta paper-policy bets. It does not retrain, select thresholds, or
change the frozen policy.

Key probability-signal slices:

| Slice | Fights | Delta LL |
| --- | ---: | ---: |
| aggregate | 704 | +0.0030 |
| market P 0.50-0.60 | 105 | +0.0264 |
| market P 0.60-0.70 | 131 | -0.0143 |
| market P 0.70-0.80 | 83 | +0.0101 |
| residual edge 0.05-0.08 | 219 | +0.0234 |
| residual edge >=0.08 | 38 | -0.0310 |
| 2024 | 275 | +0.0098 |
| 2025 | 285 | +0.0018 |
| 2026 | 144 | -0.0077 |

Fixed paper-policy bet slices:

| Slice | Bets | Profit | ROI |
| --- | ---: | ---: | ---: |
| aggregate | 354 | +2.44u | +0.69% |
| market P 0.50-0.60 | 42 | +7.93u | +18.87% |
| market P 0.60-0.70 | 135 | -6.91u | -5.12% |
| market P 0.70-0.80 | 122 | +4.10u | +3.36% |
| market P >=0.80 | 55 | -2.68u | -4.87% |
| 2024 | 144 | +11.60u | +8.06% |
| 2025 | 143 | -4.64u | -3.25% |
| 2026 | 67 | -4.52u | -6.74% |

Interpretation: the residual signal is not broad or monotonic. Larger residual
edges were not automatically better, and the fixed paper-policy profit was
mostly a 2024 phenomenon. This strengthens the paper-track-only conclusion.

### Residual Calibration Drift Audit

Residual calibration-drift audit:

```text
testing/residual_calibration_drift_audit.py
test_results/residual_calibration_drift_audit/residual_calibration_drift_audit.md
test_results/residual_calibration_drift_audit/residual_calibration_drift_audit.json
```

This diagnostic asks why the residual probability edge decayed recently. It
compares market probabilities against selected-shrinkage, fixed-half, and
unshrunk residual probabilities by period, then checks whether the
selected-shrinkage adjustment still aligns with realized market residuals.

Selected-shrinkage calibration by period:

| Period | Fights | Actual | Market P | Selected P | Mean Adj | Realized Market Residual | Policy Gap | Delta LL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| aggregate | 704 | 49.43% | 49.78% | 51.27% | +1.49% | -0.35% | -1.84% | +0.0038 |
| 2024 | 275 | 51.64% | 48.57% | 50.00% | +1.43% | +3.07% | +1.63% | +0.0098 |
| 2025 | 285 | 49.47% | 50.75% | 52.52% | +1.77% | -1.28% | -3.05% | +0.0016 |
| 2026 | 144 | 45.14% | 50.20% | 51.23% | +1.03% | -5.06% | -6.09% | -0.0036 |
| last 365 days | 298 | 45.97% | 50.80% | 52.12% | +1.32% | -4.83% | -6.15% | -0.0032 |
| latest fold 5 | 129 | 44.19% | 50.09% | 51.02% | +0.93% | -5.90% | -6.84% | -0.0047 |

Selected-shrinkage adjustment direction:

| Period | Direction | Fights | Mean Adj | Realized Market Residual | Directional Hit | Delta LL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | meta up on red | 161 | +4.31% | +5.76% | 66.46% | +0.0188 |
| 2025 | meta up on red | 186 | +4.12% | +1.92% | 61.83% | -0.0021 |
| 2026 | meta up on red | 78 | +4.35% | -3.37% | 56.41% | -0.0209 |
| latest fold 5 | meta up on red | 68 | +4.37% | -3.70% | 55.88% | -0.0242 |
| latest fold 5 | meta down on red | 61 | -2.89% | -8.36% | 68.85% | +0.0170 |

Interpretation: recent decay looks like residual/model drift, not just a
staking-threshold problem. The residual layer still nudges probabilities
upward on average, but by 2026 the aligned sample's red side underperforms the
market by about `5` to `6` percentage points. Upward residual adjustments were
strongly positive in 2024 but negative in 2026 and the latest fold. This argues
against fixing the issue with generic feature capacity or looser thresholds;
the next legitimate improvement would need a pre-registered drift-aware
transform or fresh post-freeze evidence.

### Residual Directional Gate Audit

Residual directional-gate audit:

```text
testing/residual_directional_gate_audit.py
test_results/residual_directional_gate_audit/residual_directional_gate_audit.md
test_results/residual_directional_gate_audit/residual_directional_gate_audit.json
```

This audit tests whether the calibration-drift problem can be repaired by a
simple, pre-declarable residual transform. It uses the saved selected-shrinkage
probabilities and, for each evaluation fold after fold `1`, selects separate
scales for upward and downward residual logit adjustments using only prior
folds. Scale grid: `0.0`, `0.5`, `1.0`.

Fixed candidate diagnostics:

| Candidate | Fights | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |
| --- | ---: | ---: | ---: | ---: |
| selected shrinkage | 704 | +0.0038 | +1.49% | 0.143 |
| mute up / keep down (`up0_down1`) | 704 | +0.0023 | -1.07% | 0.082 |
| keep up / mute down (`up1_down0`) | 704 | +0.0014 | +2.56% | 0.331 |
| half up / keep down (`up0.5_down1`) | 704 | +0.0039 | +0.25% | 0.040 |

Same folds `2-5` evaluation baseline:

| Candidate | Fights | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |
| --- | ---: | ---: | ---: | ---: |
| selected shrinkage | 539 | +0.0028 | +1.65% | 0.253 |
| mute up / keep down (`up0_down1`) | 539 | +0.0042 | -0.96% | 0.006 |
| half up / keep down (`up0.5_down1`) | 539 | +0.0044 | +0.38% | 0.041 |

Latest fold fixed candidates:

| Candidate | Fights | Delta LL | Mean Adj |
| --- | ---: | ---: | ---: |
| selected shrinkage | 129 | -0.0047 | +0.93% |
| mute up / keep down (`up0_down1`) | 129 | +0.0080 | -1.37% |
| half up / keep down (`up0.5_down1`) | 129 | +0.0025 | -0.19% |

Rolling prior-fold gate selection:

| Eval Fold | Selected Gate | Dev Delta LL | Eval Delta LL |
| ---: | --- | ---: | ---: |
| 2 | `up1_down0` | +0.0108 | +0.0052 |
| 3 | `up1_down0` | +0.0083 | +0.0017 |
| 4 | `up1_down0.5` | +0.0062 | +0.0026 |
| 5 | `up1_down1` | +0.0057 | -0.0047 |

Combined rolling evaluation:

| Metric | Value |
| --- | ---: |
| fights | 539 |
| market log loss | 0.6022 |
| gated log loss | 0.6010 |
| market - gated log loss | +0.0012 |
| bootstrap P(delta <= 0) | 0.366 |
| market-null p-value | 0.072 |

Interpretation: do not promote this simple directional gate. The full-history
and latest-fold diagnostics show why muting upward residual adjustments is
tempting, but prior-fold selection did not choose that fix before fold `5`.
The rolling gate underperformed plain selected-shrinkage on the same folds
(`+0.0012` vs `+0.0028` delta LL) and still failed the latest fold. This is a
useful drift clue, not a validated transform.

### Residual Recent Stress Audit

Residual recent-stress audit:

```text
testing/residual_recent_stress_audit.py
test_results/residual_recent_stress_audit/residual_recent_stress_audit.md
test_results/residual_recent_stress_audit/residual_recent_stress_audit.json
```

This audit stress-tests the residual probability edge and the frozen
residual-meta top-edge cap-3 historical ledger by recent-only periods.

Probability stress, selected-shrinkage policy:

| Period | Fights | Market LL | Candidate LL | Delta LL | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: |
| aggregate | 704 | 0.6009 | 0.5971 | +0.0038 | 0.011 |
| 2024 | 275 | 0.5800 | 0.5702 | +0.0098 | 0.007 |
| 2025 | 285 | 0.6136 | 0.6120 | +0.0016 | 0.141 |
| 2026 | 144 | 0.6156 | 0.6192 | -0.0036 | 0.449 |
| 2025-2026 only | 429 | 0.6143 | 0.6144 | -0.0001 | 0.169 |
| last 365 days | 298 | 0.6127 | 0.6159 | -0.0032 | 0.409 |
| latest fold 5 | 129 | 0.6273 | 0.6320 | -0.0047 | 0.498 |

Frozen residual-meta cap-3 PnL stress:

| Period | Bets | Profit | ROI | Market-Null p | Bootstrap P(profit <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: |
| aggregate | 262 | +19.12u | 7.30% | 0.001 | 0.015 |
| 2024 | 103 | +14.39u | 13.97% | 0.002 | <0.001 |
| 2025 | 108 | +5.76u | 5.34% | 0.062 | 0.141 |
| 2026 | 51 | -1.03u | -2.03% | 0.394 | 0.577 |
| 2025-2026 only | 159 | +4.73u | 2.97% | 0.071 | 0.251 |
| last 365 days | 105 | +0.38u | 0.36% | 0.217 | 0.465 |
| latest fold 5 | 45 | -1.78u | -3.94% | 0.486 | 0.647 |

Interpretation: the aggregate residual/cap evidence is heavily front-loaded.
Recent-only slices do not support a strong live edge claim. This does not
refute a weak residual signal, but it says the next useful work must explain
or reverse recency decay rather than add generic historical feature capacity.

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

### Recent Form Feature Audit

Recent-form feature audit:

```text
testing/recent_form_feature_audit.py
test_results/recent_form_feature_audit/RECENT_FORM_FEATURE_AUDIT.md
test_results/recent_form_feature_audit/recent_form_feature_audit.json
test_results/recent_form_feature_audit/statistical_edge_audit/edge_audit.md
```

This audit builds an alternate feature table with `128` recent-form/activity
columns computed only from source fights strictly before each modeled fight
date. The feature family includes last-3/last-5 result score, binary win rate,
finish win/loss rate, non-binary rate, minutes, recent striking/grappling
rates, knockdown rates, and 365/730-day activity counts.

Leak-safe comparison with fixed regularized LightGBM params:

| Window | Feature Set | Accuracy | Log Loss | PnL |
| --- | --- | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | current regularized | 64.43% | 0.6418 | +24.66% |
| 2025-06-27 to 2026-06-27 | recent-form challenger | 63.09% | 0.6436 | +2.57% |
| 2024-06-27 to 2026-06-27 | current regularized | 65.00% | 0.6318 | +61.20% |
| 2024-06-27 to 2026-06-27 | recent-form challenger | 64.66% | 0.6370 | +19.12% |

Statistical audit for the recent-form challenger:

| Run | Model LL | Market LL | Profit | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | --- |
| recent-form 1y | 0.644 | 0.613 | +$25.72 | 0.426 | -$326.64 to $384.17 |
| recent-form 2y | 0.637 | 0.600 | +$191.24 | 0.166 | -$365.38 to $749.47 |

Interpretation: do not promote recent-form features. This was a plausible
feature-engineering attempt, but it worsened log loss and PnL versus the
current regularized feature set in both summarized windows. Recent-form
capacity alone did not fix the latest-fold/residual-drift problem.

### Recency-Weighted Training Audit

Recency-weighted training audit:

```text
testing/no_leakage_backtest.py
test_results/recency_weighted_training_audit/RECENCY_WEIGHTED_TRAINING_AUDIT.md
test_results/recency_weighted_training_audit/statistical_edge_audit/edge_audit.md
```

This audit added an opt-in `--training-recency-half-life-days` flag to the
leak-safe rolling backtester. For each event-date retrain, sample weights are
computed only from already-eligible training rows as
`0.5 ** (days_before_event / half_life_days)` and normalized to mean `1.0`.
The default remains unchanged, so existing backtests and production-style runs
do not use recency weighting unless explicitly requested.

Leak-safe comparison with fixed regularized LightGBM params:

| Window | Training Policy | Accuracy | Log Loss | PnL |
| --- | --- | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | current regularized | 64.43% | 0.6418 | +24.66% |
| 2025-06-27 to 2026-06-27 | half-life 365d | 65.10% | 0.6588 | +11.08% |
| 2025-06-27 to 2026-06-27 | half-life 730d | 65.10% | 0.6396 | +15.46% |
| 2024-06-27 to 2026-06-27 | current regularized | 65.00% | 0.6318 | +61.20% |
| 2024-06-27 to 2026-06-27 | half-life 365d | 65.17% | 0.6480 | +26.28% |
| 2024-06-27 to 2026-06-27 | half-life 730d | 64.66% | 0.6372 | +31.41% |

Statistical audit for the recency-weighted runs:

| Run | Model LL | Market LL | Profit | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | --- |
| half-life 365d, 2y | 0.648 | 0.600 | +$262.85 | 0.125 | -$497.41 to +$1,011.06 |
| half-life 730d, 2y | 0.637 | 0.600 | +$314.08 | 0.103 | -$357.20 to +$991.17 |
| half-life 365d, 1y | 0.659 | 0.613 | +$110.83 | 0.266 | -$442.84 to +$661.77 |
| half-life 730d, 1y | 0.640 | 0.613 | +$154.59 | 0.241 | -$328.59 to +$647.94 |

Interpretation: do not promote recency-weighted LightGBM training. The
730-day half-life slightly improved one-year log loss, but it worsened the
two-year comparison and reduced PnL in both windows. No recency-weighted ledger
beat the de-vigged market on log loss, the best market-null p-value was only
`0.103`, and all event-bootstrap profit intervals crossed zero.

### Market-Aware Feature Audit

Market-aware feature audit:

```text
testing/market_aware_feature_audit.py
test_results/market_aware_feature_audit/market_aware_feature_audit.md
test_results/market_aware_feature_audit/market_aware_feature_audit.json
```

This audit asks whether raw pre-fight feature groups add log-loss signal after
controlling directly for de-vigged market probability. Each candidate is a
small L2 logistic model trained only on prior folds with `market_logit` plus a
fixed feature group. Training rows are red/blue mirrored; holdout probabilities
average the direct and mirrored orientations.

Protocol:

- aligned feature/odds rows: `1223`
- evaluated holdout fights: `704`
- folds: `5`
- development window: `730` days
- holdout window: `182` days
- logistic L2 inverse regularization: `C = 0.1`
- event-bootstrap iterations: `20000`
- refit-under-market-null simulations: `100`

Results:

| Variant | Features | Market LL | Candidate LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market recalibrated | 1 | 0.6009 | 0.6000 | +0.0008 | 3 / 5 | 0.351 | 0.099 |
| market + age/recency | 3 | 0.6009 | 0.6025 | -0.0017 | 2 / 5 | 0.692 | 0.257 |
| market + combat stats | 11 | 0.6009 | 0.6037 | -0.0028 | 2 / 5 | 0.664 | 0.158 |
| market + top importance | 24 | 0.6009 | 0.6088 | -0.0080 | 2 / 5 | 0.841 | 0.158 |
| market + Elo/experience | 9 | 0.6009 | 0.6112 | -0.0103 | 2 / 5 | 0.947 | 0.683 |

Interpretation: the feature groups most suggested by regularized-LGBM feature
importance did not improve probabilities once market price was included. The
only positive variant was market-only recalibration, and that was small and not
statistically convincing. This argues against promoting raw feature expansion
or direct feature+market logistic models right now; the residual-model signal
remains stronger than the raw-feature-after-market signal.

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

| Selection Objective | Bets | Profit | Flat ROI | Actual - Market | Positive Folds | Market-Null p | Selection-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| profit | 373 | -3.49u | -0.93% | +2.47% | 4 / 7 | 0.342 | 0.360 |
| ROI | 161 | +10.15u | +6.30% | +5.07% | 4 / 7 | 0.107 | 0.130 |
| actual - market | 167 | +15.22u | +9.11% | +6.72% | 5 / 7 | 0.090 | 0.076 |

Interpretation: the forward-selected disagreement rule family is promising but
still not a real edge claim. The profit objective went slightly negative. The
best conditional market-null p-value was `0.090`; the stricter
selection-adjusted market-null p-value, which reruns policy selection under
market-simulated outcomes, was `0.076`. Since three selection objectives were
inspected, a simple Bonferroni adjustment puts the best selection-adjusted
p-value around `0.23`.

### Outcome Universe Audit

Universe/outcome audit:

```text
testing/outcome_universe_audit.py
test_results/outcome_universe_audit/outcome_universe_audit.md
test_results/outcome_universe_audit/outcome_universe_audit.json
```

This audit checked two proposed failure modes: whether the production edge
claim is already excluding women's fights, and whether draw/no-contest/
overturned bouts affect future fighter state without becoming supervised
training labels.

Dataset counts:

| Dataset | Rows | Women's Rows | Non-Binary / Blank-Winner Rows | Non-Binary Labels |
| --- | ---: | ---: | ---: | ---: |
| `data/fight_details_date.csv` | 8910 | 931 | 312 | n/a |
| `data/modified_fight_details.csv` | 7730 | 0 | 148 | n/a |
| `data/detailed_fights.csv` | 4322 | 0 | n/a | 0 |

Women-pair identity check:

| Dataset | Women's Title Rows | Known Women-Pair Rows | Hidden Women-Pair Rows |
| --- | ---: | ---: | ---: |
| `data/fight_details_date.csv` | 931 | 940 | 9 |
| `data/modified_fight_details.csv` | 0 | 9 | 9 |
| `data/detailed_fights.csv` | 0 | 0 | 0 |

The 9 hidden rows are women-vs-women catchweights whose title does not contain
`Women`. The current supervised production feature table still has zero known
women-pair rows, and future preprocessing/backtests now use fighter-aware
`Women` filtering so those catchweights are not missed by title text alone.

Current regularized backtest universe:

| Run | Window | Features | Excluded Titles | Predicted Fights |
| --- | --- | --- | --- | ---: |
| regularized 1y | 2025-06-27 to 2026-06-27 | `data/detailed_fights.csv` | `Women` | 298 |
| regularized 2y | 2024-06-27 to 2026-06-27 | `data/detailed_fights.csv` | `Women` | 580 |
| regularized long | 2022-02-05 to 2026-06-27 | `data/detailed_fights.csv` | `Women` | 1249 |

Non-binary state check:

| Metric | Value |
| --- | ---: |
| retained non-binary / blank-winner source rows | 148 |
| supervised feature non-binary labels | 0 |
| future fighter-side rows with prior non-binary history checked | 1263 |
| rows matching prior source fight count including non-binary bouts | 1263 |
| mismatches | 0 |
| latest-prior non-binary `last_fight` checks | 157 |
| latest-prior non-binary `last_fight` matches | 157 |
| weighted stat checks where non-binary changed `Sig. str.`, `Total str.`, or `Td` | 3697 |
| weighted stat matches including non-binary bouts | 3697 |

Interpretation: the current production edge-claim universe already does not
train on or evaluate women's fights. Draw/no-contest/overturned rows are also
handled in the desired way: they update future fighter state, but they are not
used as supervised `win/loss` labels. The strengthened June 28 audit now checks
more than `totalfights`: when the latest prior fight was non-binary, `last_fight`
matched the non-binary date, and cumulative weighted `Sig. str.`, `Total str.`,
and `Td` features matched the calculation that includes non-binary bouts.

Follow-up implementation hardening: `utils/incremental_processing.py` now uses
the full raw scrape to learn known women's fighters before filtering a new
incremental batch. That makes the incremental production path match
`modify_fights.py` and the backtest universe filter for hidden women-vs-women
catchweights whose title omits `Women`.

### Women Universe Sensitivity

Women-universe sensitivity artifacts:

```text
test_results/women_universe_sensitivity/WOMEN_UNIVERSE_SENSITIVITY.md
test_results/women_universe_sensitivity/WOMEN_UNIVERSE_LONG_NESTED_AUDIT.md
test_results/women_universe_sensitivity/regularized_train_all_eval_men_2y/no_leakage_backtest_summary.json
test_results/women_universe_sensitivity/regularized_train_all_eval_men_2y_audit/edge_audit.md
```

This compared the current regularized men-only 2y run against a counterfactual
using the women-included feature table for training while still evaluating only
men's fights.

| Run | Training Universe | Evaluation Universe | Fights | Accuracy | Model LL | Market LL | Profit | Market-Null p |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| current regularized men-only | men only | men only | 580 | 65.0% | 0.632 | 0.600 | $611.97 | 0.034 |
| women-included training, men-only eval | all prior fights | men only | 580 | 65.9% | 0.633 | 0.600 | $733.69 | 0.013 |

Interpretation: including women's fights in the training history changed the
saved men-only PnL ledger in a favorable direction, but it did not create a
probability edge over the market. In both runs, model log loss is worse than
de-vigged market log loss; the women-included-training run has event-bootstrap
`P(model not better than market on log loss) = 0.9977`. The backtest filter was
also hardened so `Women` excludes known women-vs-women catchweight rows whose
titles do not contain `Women`. Treat the PnL improvement as an exploratory
counterfactual, not a production-policy change.

Long-window sensitivity for the same women-included-training / men-only-eval
idea:

| Window | Fights | Accuracy | Model LL | Market LL | Profit | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2022-02-05 to 2026-06-27 | 1249 | 64.5% | 0.641 | 0.601 | $364.11 | 0.057 | $-376.02 to $1,119.67 |

Interpretation: the long-window result weakens the women-included-training
case. It remains directionally profitable, but no longer clears `p < 0.05`, the
bootstrap profit interval crosses zero, and model probabilities still lose
badly to market log loss.

Nested strategy sensitivity allowing the women-trained model to compete against
the existing baseline and regularized men-only ledgers:

| Objective | Fights | Bets | Profit | Positive Folds | Women-Train Folds Selected | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| profit | 962 | 237 | $234.50 | 5 / 7 | 2 / 7 | 0.170 | $-345.64 to $822.43 |
| ROI | 962 | 140 | $95.31 | 4 / 7 | 2 / 7 | 0.155 | $-193.36 to $396.21 |

Interpretation: this is also directionally positive but weak. It does not
support replacing the frozen men-only production policy with a women-included
training variant.

## Current Bottom Line

The repo is now much better instrumented than it was on Oct 17:

- leak-safe rolling retraining exists
- DOB/age leakage and corruption are explicitly testable
- odds coverage and date joins are more robust
- market-null simulations and event bootstraps exist
- walk-forward strategy search exists
- the production universe is explicitly audited as men-only, while
  non-binary outcomes still feed future fighter-state features

The regularized LGBM update improved the current leak-safe metrics materially,
but the evidence still does not prove a live betting edge.

The most honest read:

- the model likely contains weak predictive signal
- regularization reduced, but did not eliminate, calibration weakness
- de-vigged market probabilities still beat standalone model probabilities on
  raw holdout log loss
- direct market-aware feature modeling did not help: after controlling for
  market logit, Elo/experience, age/recency, combat-stat, and top-importance
  feature groups all worsened log loss; only market-only recalibration was
  slightly positive and still weak
- recent-form/activity feature engineering did not help: adding 128 leak-safe
  last-3/last-5 and recent-activity columns worsened one-year and two-year log
  loss and sharply reduced PnL versus the current regularized feature set
- recency-weighted training also did not help enough: the 730-day half-life
  slightly improved one-year log loss, but both 365-day and 730-day weighting
  reduced PnL versus current regularized training, failed the two-year
  comparison, and beat de-vigged market log loss in `0/4` tested ledgers
- the longer market-blend audit selected pure market probability, not a model
  residual, but the newer residual meta audit finds a small positive
  model-after-market log-loss signal
- residual-meta configuration selection is weak: although the full-holdout
  `365d/C=1.0` residual-meta run shows `+0.0047` delta LL, rolling selection
  across inspected configs/variants only produces `+0.0005` delta LL with
  event-bootstrap `P(delta <= 0) = 0.458` and rolling market-null p `0.084`
- residual negative controls support that signal: sign-flipped residuals lose
  badly, and residual permutations rarely match the observed log-loss gain
- nested residual-shrinkage selection strengthens the probability evidence:
  the capped-grid selected scale has market-null p-value `0.005`, or about
  `0.015` after a simple three-policy correction, but event-bootstrap
  uncertainty still crosses zero and the latest 2026 fold is negative
- residual edge concentration is a major caveat: removing only the top seven
  selected-shrinkage events erases the probability edge, and removing the top
  ten makes the aggregate log-loss delta negative
- fixed-threshold shrinkage PnL is positive but still weak: selected shrinkage
  produced `+4.55u`, fixed-half residual `+8.39u`, and unshrunk meta `+3.40u`;
  the best conditional market-null p-value is `0.024`, or about `0.071` after
  a simple three-policy correction, while event-bootstrap profit uncertainty
  still crosses zero
- per-event risk caps are the most promising PnL translation so far:
  selected-shrinkage cap `3` produced `+17.45u` with market-null p-value
  `0.003`, and the best variant across 15 inspected policy/cap combinations
  had selection-adjusted market-null p-value `0.011`; this is still discovery
  evidence, not a live edge claim, because the cap family was inspected after
  the historical ledger existed
- a capped residual paper policy is now frozen as of `2026-06-28`: it uses
  the frozen residual transform, fixed thresholds, flat `1u`, and max `3`
  bets per event ranked by residual edge; this is for future paper tracking
  only, not live staking
- rolling prior-fold cap selection is positive and market-null resistant:
  the frozen residual-meta cap family made `+9.52u` to `+11.89u` depending on
  objective, selected-shrinkage caps made `+12.15u` under the profit objective,
  and rolling market-null p-values ranged from `0.008` to `0.047`; the latest
  fold remained negative, so this still needs post-freeze evidence
- the event-cap ranking rule itself has support: for the frozen residual-meta
  ledger, top residual-edge cap `3` made `+19.12u` versus a random-cap mean of
  `+6.63u`, with `P(random >= top edge) = 0.004`
- cap-regime diagnostics weaken a broad live-edge claim: the frozen
  residual-meta cap-3 result remains `+19.12u` aggregate, but 2025-2026 is
  only `+4.73u` with market-null p `0.071`, rank `3` is flat, extreme
  residual edge `>=0.08` is negative, and removing the top `15` events erases
  aggregate profit
- prior-period slice validation does not rescue the recency issue: the
  2024-selected probability slice loses in 2025-2026, rolling probability
  selection is only marginal with market-null p `0.067`, and the rolling
  capped-bet selector simply chooses all cap-3 bets every fold; it remains
  positive (`+11.75u`, market-null p `0.003`) but the latest fold is still
  negative
- market-favorite benchmarks strengthen the residual-selection story
  historically: frozen residual cap-3 made `+19.12u`, while top market
  favorites with the same per-event bet counts made only `+0.07u`, random
  same-event favorite selection averaged `-2.95u`, and `P(random >= residual)`
  was `0.005`; this argues the result is not just generic favorite exposure
- the same benchmark still preserves the recency caveat: over the last 365
  days residual cap-3 made only `+0.38u`, top-market same-count favorites made
  `-2.20u`, and low-confidence same-count favorites made `+3.29u`
- nested residual-meta PnL tests are positive across objective sensitivities,
  but their best selection-adjusted market-null p-value is only `0.066`
  before correcting for three inspected objectives
- residual signal slices are uneven: the probability edge was negative in
  2026, negative for market P `0.60-0.70`, and negative for extreme residual
  edge `>=0.08`; fixed-policy PnL was also negative in 2025 and 2026
- residual calibration drift explains the recent decay better than a simple
  threshold problem: selected-shrinkage kept nudging red-side probabilities up
  by about `+1%` on average, but the realized red-vs-market residual was
  `-5.06%` in 2026 and `-5.90%` in the latest fold; upward residual
  adjustments had negative delta LL in 2026 and fold 5
- a simple directional residual gate does not validate as a fix: muting upward
  residual adjustments would have helped the latest fold after the fact
  (`up0_down1` delta LL `+0.0080`), but rolling prior-fold selection chose the
  original full adjustment for fold 5, scored `-0.0047`, and underperformed
  plain selected-shrinkage across folds 2-5 (`+0.0012` vs `+0.0028` delta LL)
- residual recent-stress is a major caveat: selected-shrinkage probability
  delta is negative in 2026, over the last 365 days, and in the latest fold;
  frozen residual-meta cap-3 PnL is `+19.12u` aggregate but only `+4.73u` in
  2025-2026 and `-1.78u` in the latest fold
- edge-only model/market disagreement is negative in flat-bet tests; the more
  interesting pockets require both positive edge and a model-probability floor
- forward-selected simple disagreement policies remain weak after objective
  sensitivity; the best selection-adjusted market-null p-value is `0.076`
  before correcting for three inspected objectives
- profitable PnL variants remain sensitive to model policy and threshold search
- the best disagreement pockets are not uniformly stable by year, with the
  regularized `model P >= 0.60, edge >= 0.08` slice losing in 2023
- the women's-fight investigation does not require a production change:
  production backtests already exclude women's fights; women-included training
  improved the saved two-year men-only PnL ledger but still failed to beat
  market log loss, the longer 2022-2026 window weakened the PnL evidence, and
  nested strategy selection with a women-trained candidate remained weak;
  women-only evaluation also failed to beat market evidence
- the non-binary outcome handling is now audited beyond fight counts:
  draw/no-contest/overturned bouts update `last_fight` and weighted cumulative
  fight-stat features, while remaining out of supervised labels
- the best raw market-null p-value is `0.048` from the exploratory ROI
  objective, or about `0.096` after a simple two-objective correction
- the earlier unshrunk probability-residual result had market-null p-value
  `0.012`, or about `0.048` after a simple four-variant correction; the newer
  nested shrinkage audit is stronger on market-null but still not decisive on
  event-bootstrap stability
- the best residual-meta PnL result has market-null p-value `0.066`, or about
  `0.20` after a simple three-objective correction
- the frozen residual-meta paper policy is intentionally conservative and
  historically weak; it exists to collect clean post-freeze evidence, not to
  justify live staking now
- this is promising but still below a strong live-edge threshold

Recommendation:

Do not materially increase staking based only on these backtests. Use the
frozen forward betting artifact above as the current main PnL paper-tracking
policy, use the frozen residual transform as the current probability
paper-tracking contract, and use the frozen residual-meta paper policy only as
a secondary residual-signal monitor. A real edge claim needs future
out-of-sample results that beat market-null and bootstrap tests after the model
params, probability transform, selection objective, strategy grid, and staking
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
- `testing/score_frozen_residual_event_cap_policy.py` generates separate
  pre-outcome paper ledgers for the frozen capped residual policy:
  `test_results/forward_paper_tracking/latest_residual_event_cap_paper_bets.csv`
  and `.json`

Validation:

- compile check passed for `betting_alpha.py`, `ml_web.py`,
  `predict_single_model.py`, `load_ensemble.py`, and
  `utils/production_predictions.py`
- compile check passed for `testing/score_frozen_residual_event_cap_policy.py`
- compile check passed for `utils/incremental_processing.py`,
  `testing/residual_event_cap_rolling_selection_audit.py`,
  `testing/outcome_universe_audit.py`, and `testing/no_leakage_backtest.py`
- compile check passed for `testing/residual_meta_config_selection_audit.py`
  and `testing/residual_event_cap_ranking_audit.py`
- compile check passed for `testing/recent_form_feature_audit.py` and
  `testing/residual_recent_stress_audit.py`
- a temporary in-range prediction input generated canonical prediction outputs
  under `/private/tmp/ufc_forward_prediction_smoke`
- a direct frozen-policy betting smoke test selected the expected model/market
  blended candidate and stake
- a synthetic forward-ledger smoke test wrote CSV/JSON paper-bet ledgers under
  `/private/tmp`
- a synthetic settlement smoke test generated an outcome template, settled all
  rows, and wrote settled CSV/JSON/Markdown evidence under `/private/tmp`
- a capped residual scorer smoke test wrote a compatible pre-outcome ledger,
  generated a settlement outcome template, and settled a synthetic result under
  `/private/tmp`
- a five-fight capped residual scorer smoke test exercised the event cap itself:
  the scorer placed exactly three paper bets and marked two otherwise eligible
  candidates as `event cap 3 reached`
- an incremental-processing smoke test confirmed a new women-vs-women
  catchweight row is excluded even when its title omits `Women`
- the residual event-cap rolling selection audit regenerated cleanly; best
  result was selected-shrinkage caps with profit objective, `+12.15u`,
  rolling market-null p `0.008`
- the residual event-cap ranking audit regenerated cleanly; frozen
  residual-meta top-edge cap `3` made `+19.12u` and
  `P(random >= top edge) = 0.004`
- the residual-meta config-selection audit regenerated cleanly; rolling
  selection over inspected configs/variants made only `+0.0005` delta LL with
  rolling market-null p `0.084`
- the recent-form feature audit built a 4,322-row alternate feature table with
  128 added columns and ran 1y/2y leak-safe backtests; both worsened log loss
  and PnL versus current regularized features
- the recency-weighted training audit ran 365-day and 730-day half-life
  regularized-LGBM backtests over the 1y and 2y windows; the best one-year
  log-loss variant did not hold up on the two-year window or PnL
- the recency-weighted statistical audit ran across four saved ledgers; best
  market-null p-value was `0.103`, Bonferroni across the four ledgers was
  `0.414`, and `0/4` ledgers beat de-vigged market log loss
- the residual recent-stress audit regenerated cleanly; selected-shrinkage
  probability delta was `-0.0032` over the last 365 days, and frozen
  residual-meta cap-3 PnL was only `+0.38u` over the last 365 days
- the residual cap-regime audit decomposed the frozen cap-3 ledger; aggregate
  remained `+19.12u`, but 2025-2026 fell to `+4.73u`, event rank `3` was
  flat, and the lower-confidence favorite pocket was only `21` recent bets
- the residual slice-validation audit ran prior-period slice selection with
  market-null reruns; the 2024-selected probability slice failed in
  2025-2026, rolling probability selection was marginal at p `0.067`, and
  rolling capped-bet selection chose all cap-3 bets every fold for `+11.75u`
  with market-null p `0.003`
- the residual-vs-market-favorite audit compared frozen residual cap-3 against
  market-only favorite benchmarks on the same event dates; residual cap-3 made
  `+19.12u` versus `+0.07u` for top market favorites with the same per-event
  bet counts, and random same-event favorites matched or beat residual only
  `0.5%` of the time
- the residual calibration-drift audit found the latest selected-shrinkage
  fold had delta LL `-0.0047`, mean residual adjustment `+0.93%`, and realized
  red-vs-market residual `-5.90%`, supporting drift rather than a pure
  threshold/staking explanation
- the residual directional-gate audit tested prior-fold selection over
  up/down residual adjustment scales; the rolling gate reached only `+0.0012`
  delta LL with market-null p `0.072`, selected the failing full adjustment in
  fold `5`, and did not beat plain selected-shrinkage on the same folds

Current operational caveat: the checked-in `data/predict_fights_alpha.csv` is
stale and fails the live feature-range guard with out-of-training-range values.
Regenerate that file from the next card before running `predict_single_model.py`
or `ml_web.py` for forward paper scoring.
