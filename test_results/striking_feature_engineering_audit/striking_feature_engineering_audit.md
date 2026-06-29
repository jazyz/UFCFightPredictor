# Striking Feature Engineering Audit

This audit tests whether more fight-interpretable pace-adjusted striking
features improve the market-aware striking-core signal. It keeps the
same rolling date folds and no event cap.

## Protocol

- aligned men-only feature/odds rows: `1223`
- rolling folds: `7`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- logistic L2 C: `0.1`
- fixed betting threshold: `2.00%`
- event cap: none

## Feature Reconstruction

| Check | Value |
| --- | ---: |
| source_rows | 7730 |
| feature_rows | 4322 |
| expected_supervised_rows | 4322 |
| matched_supervised_rows | 4322 |
| missing_feature_rows | 0 |
| extra_feature_rows | 0 |
| side_rate_checks | 69152 |
| side_rate_mismatches | 0 |
| side_rate_max_abs_error | 2.1316282072803006e-14 |
| derived_feature_rows | 4322 |

The current side rate columns such as `Red Sig. str.` reconstruct as
weighted prior per-minute rates. The frozen raw differential columns
remain weighted count differentials per fight; the `*_differential_pm`
columns created here are the pace-adjusted alternatives.

## Probability Results

| Variant | Features | Fights | Delta LL | Delta Brier | Accuracy | Mean Abs Move | Positive Folds | Boot P(delta<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_sigpct_head` | 3 | 961 | 0.0071 | 0.0027 | 69.41% | 3.84% | 7 / 7 | 0.015 | 0.005 |
| `pace_adjusted_mixed_core` | 4 | 961 | 0.0068 | 0.0028 | 69.30% | 3.73% | 6 / 7 | 0.021 | 0.005 |
| `current_mixed_core` | 4 | 961 | 0.0068 | 0.0025 | 68.99% | 3.96% | 6 / 7 | 0.022 | 0.005 |
| `location_rate_core` | 5 | 961 | 0.0064 | 0.0027 | 68.57% | 4.05% | 5 / 7 | 0.035 | 0.005 |
| `rate_volume_core` | 5 | 961 | 0.0063 | 0.0026 | 69.51% | 3.80% | 6 / 7 | 0.040 | 0.005 |
| `position_rate_core` | 5 | 961 | 0.0049 | 0.0020 | 68.89% | 3.90% | 6 / 7 | 0.111 | 0.005 |
| `damage_rate_core` | 4 | 961 | 0.0029 | 0.0014 | 69.51% | 3.77% | 4 / 7 | 0.201 | 0.005 |
| `market_recalibrated` | 1 | 961 | 0.0017 | 0.0007 | 68.68% | 2.58% | 4 / 7 | 0.216 | 0.030 |

## Fixed 2% Positive-Edge PnL

| Variant | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pace_adjusted_mixed_core` | 695 | 148 | +41.97u | 6.04% | 5.85% | 6 / 7 | 0.021 | 0.001 |
| `location_rate_core` | 710 | 148 | +34.06u | 4.80% | 4.90% | 5 / 7 | 0.049 | 0.003 |
| `current_mixed_core` | 714 | 148 | +33.38u | 4.68% | 5.12% | 6 / 7 | 0.054 | 0.002 |
| `current_sigpct_head` | 705 | 148 | +31.85u | 4.52% | 4.74% | 5 / 7 | 0.066 | 0.002 |
| `rate_volume_core` | 681 | 147 | +25.66u | 3.77% | 4.79% | 6 / 7 | 0.111 | 0.003 |
| `damage_rate_core` | 713 | 148 | +25.52u | 3.58% | 4.64% | 6 / 7 | 0.102 | 0.007 |
| `position_rate_core` | 694 | 147 | +13.25u | 1.91% | 4.14% | 4 / 7 | 0.266 | 0.035 |
| `market_recalibrated` | 615 | 144 | -1.63u | -0.27% | 2.84% | 4 / 7 | 0.537 | 0.061 |

## Rolling Prior-Fold Selection Diagnostics

These selectors are diagnostic only. They choose among the inspected
feature variants using prior folds, then score the next fold. The
market-null p-values above do not adjust for this rolling selection.

| Selector | Fights | Delta LL | Delta Brier | Accuracy | Mean Abs Move | Positive Folds | Boot P(delta<=0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_prior_probability_delta` | 840 | 0.0039 | 0.0016 | 69.52% | 4.18% | 4 / 6 | 0.167 |

Probability selection path:

| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `current_mixed_core` | 121 | 0.0073 | 118 | -0.0016 |
| 3 | `current_sigpct_head` | 239 | 0.0049 | 151 | 0.0030 |
| 4 | `pace_adjusted_mixed_core` | 390 | 0.0045 | 142 | 0.0115 |
| 5 | `pace_adjusted_mixed_core` | 532 | 0.0064 | 138 | -0.0027 |
| 6 | `current_sigpct_head` | 670 | 0.0057 | 147 | 0.0064 |
| 7 | `rate_volume_core` | 817 | 0.0064 | 144 | 0.0054 |

Betting selection path:

| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `current_mixed_core` | 87 | +0.91u | 92 | +2.85u |
| 3 | `rate_volume_core` | 160 | +6.03u | 103 | +2.54u |
| 4 | `rate_volume_core` | 263 | +8.57u | 96 | +1.90u |
| 5 | `pace_adjusted_mixed_core` | 371 | +18.53u | 101 | +0.83u |
| 6 | `pace_adjusted_mixed_core` | 472 | +19.36u | 113 | +7.98u |
| 7 | `pace_adjusted_mixed_core` | 585 | +27.34u | 110 | +14.64u |

Rolling selected betting result:

| Variant | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_prior_profit` | 615 | 125 | +30.73u | 5.00% | 4.95% | 6 / 6 | 0.056 | 0.004 |

## Variants

| Variant | Feature Columns | Note |
| --- | --- | --- |
| `market_recalibrated` | `market_logit` | market logit recalibration only |
| `current_mixed_core` | `market_logit`, `Sig. str.% differential oppdiff`, `Sig. str. differential oppdiff`, `Head differential oppdiff` | frozen current count-differential mixed striking core |
| `current_sigpct_head` | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff` | frozen challenger-style count-differential sigpct/head core |
| `pace_adjusted_mixed_core` | `market_logit`, `Sig. str.% differential oppdiff`, `Sig. str. differential_pm oppdiff`, `Head differential_pm oppdiff` | replace raw significant/head count differentials with per-minute differentials |
| `rate_volume_core` | `market_logit`, `Sig. str.% differential oppdiff`, `Sig. str. for_pm oppdiff`, `Sig. str. differential_pm oppdiff`, `Head differential_pm oppdiff` | pace-adjusted efficiency plus own significant-strike volume |
| `location_rate_core` | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential_pm oppdiff`, `Body differential_pm oppdiff`, `Leg differential_pm oppdiff` | pace-adjusted head/body/leg differential mix |
| `position_rate_core` | `market_logit`, `Sig. str.% differential oppdiff`, `Distance differential_pm oppdiff`, `Clinch differential_pm oppdiff`, `Ground differential_pm oppdiff` | pace-adjusted distance/clinch/ground differential mix |
| `damage_rate_core` | `market_logit`, `Sig. str.% differential oppdiff`, `KD differential_pf oppdiff`, `Head differential_pm oppdiff` | knockdown differential plus pace-adjusted head striking |

## Interpretation

- Best probability variant: `current_sigpct_head` with Delta LL `0.0071`.
- Best uncapped PnL variant: `pace_adjusted_mixed_core` with `+41.97u` at `6.04%` ROI.
- The current count-differential variants remain best or effectively tied on probability diagnostics.
- Do not change the frozen paper policy from this audit alone; these variants were designed after seeing the striking-core evidence and need selection-adjusted validation or future paper evidence.
