# Feature Signal After Market Audit

This diagnostic takes the current regularized-LGBM top-importance
features and tests each feature unit one at a time after market
control. For each evaluation fold after fold 1, it trains on prior
folds only, uses direct/swapped fighter-order augmentation, and
compares `market_logit + feature` against a rolling market-only
logistic recalibration. It does not select or promote a new feature
set or betting policy.

## Inputs

- residual predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- feature table: `data/detailed_fights.csv`
- importance file: `test_results/regularized_lgbm_feature_importance.csv`
- merged prediction/feature rows: `704`
- feature units tested: `60`
- rolling eval folds: `2, 3, 4, 5`

## Market Baseline

| Fights | Events | Raw Market LL | Market-Recal LL | Recal Delta LL |
| ---: | ---: | ---: | ---: | ---: |
| 539 | 79 | 0.6022 | 0.6023 | -0.0001 |

## Family Summary

| Family | Units | Importance | Mean Inc Delta LL | Median Inc Delta LL | Positive Units | Wrong-Way Known Priors | Warning Units |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| striking_position | 36 | 1103 | 0.0002 | 0.0000 | 18 | 3 | 18 |
| age_recency | 5 | 251 | -0.0007 | -0.0007 | 0 | 2 | 0 |
| grappling | 12 | 398 | -0.0010 | -0.0008 | 0 | 0 | 2 |
| record_experience | 7 | 385 | -0.0014 | -0.0016 | 0 | 2 | 0 |

## Top Incremental Helpers

| Unit | Family | Rank | Importance | Inc Delta LL | Positive Folds | Boot P(delta<=0) | Latest Delta | Coef | Prior | Q4-Q1 Residual | Warning |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `Sig. str.% differential oppdiff` | striking_position | 10 | 34 | 0.0079 | 4 / 4 | 0.017 | 0.0113 | 0.1939 |  | 14.94% | percentage/rate proxy |
| `Head differential oppdiff` | striking_position | 38 | 22 | 0.0043 | 3 / 4 | 0.060 | 0.0103 | 0.1823 | + | 11.41% |  |
| `Head differential side_pair` | striking_position | 32 | 40 | 0.0043 | 3 / 4 | 0.055 | 0.0102 | 0.1353 | + | 11.41% |  |
| `Head% differential oppdiff` | striking_position | 74 | 17 | 0.0033 | 3 / 4 | 0.083 | 0.0087 | 0.1186 |  | 13.27% | percentage/rate proxy |
| `Distance% differential oppdiff` | striking_position | 45 | 22 | 0.0030 | 3 / 4 | 0.137 | 0.0039 | 0.1310 |  | 10.55% | percentage/rate proxy |
| `Distance% differential side_pair` | striking_position | 58 | 29 | 0.0030 | 3 / 4 | 0.148 | 0.0039 | 0.0942 |  | 10.55% | percentage/rate proxy |
| `Sig. str. differential oppdiff` | striking_position | 27 | 25 | 0.0027 | 4 / 4 | 0.039 | 0.0058 | 0.0984 | + | 10.14% |  |
| `Sig. str. differential side_pair` | striking_position | 15 | 50 | 0.0027 | 4 / 4 | 0.037 | 0.0058 | 0.0721 | + | 10.14% |  |
| `Ground differential oppdiff` | striking_position | 76 | 17 | 0.0023 | 3 / 4 | 0.169 | 0.0009 | 0.1800 | + | 8.22% |  |
| `Total str. differential side_pair` | striking_position | 57 | 37 | 0.0022 | 3 / 4 | 0.170 | 0.0024 | 0.1186 | + | 11.26% |  |
| `Distance% defense oppdiff` | striking_position | 20 | 28 | 0.0016 | 2 / 4 | 0.361 | -0.0084 | 0.2136 | + | 11.75% | percentage/rate proxy; target/position-mix defense proxy |
| `Leg% defense oppdiff` | striking_position | 34 | 24 | 0.0015 | 2 / 4 | 0.381 | -0.0183 | 0.2440 | + | 9.78% | percentage/rate proxy; target/position-mix defense proxy |
| `Leg% defense side_pair` | striking_position | 17 | 54 | 0.0015 | 2 / 4 | 0.383 | -0.0181 | 0.1774 | + | 9.78% | percentage/rate proxy; target/position-mix defense proxy |
| `Clinch% differential side_pair` | striking_position | 69 | 27 | 0.0012 | 3 / 4 | 0.276 | 0.0051 | 0.0603 |  | 7.75% | percentage/rate proxy |
| `Body% differential oppdiff` | striking_position | 12 | 31 | 0.0008 | 2 / 4 | 0.347 | 0.0027 | 0.0973 |  | 7.02% | percentage/rate proxy |

## Largest Incremental Harms

| Unit | Family | Rank | Importance | Inc Delta LL | Positive Folds | Boot P(delta<=0) | Latest Delta | Coef | Prior | Q4-Q1 Residual | Warning |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `Leg differential side_pair` | striking_position | 52 | 32 | -0.0040 | 1 / 4 | 0.946 | 0.0001 | -0.1136 | + | -0.60% |  |
| `Leg% side_pair` | striking_position | 28 | 39 | -0.0030 | 2 / 4 | 0.904 | 0.0003 | -0.0051 |  | -4.38% | percentage/rate proxy |
| `Total str.% defense oppdiff` | striking_position | 18 | 28 | -0.0029 | 1 / 4 | 0.839 | -0.0003 | 0.1004 | + | 0.98% | percentage/rate proxy |
| `Td% differential side_pair` | grappling | 49 | 39 | -0.0028 | 0 / 4 | 0.927 | -0.0011 | -0.0050 |  | 3.67% | percentage/rate proxy |
| `Head% defense oppdiff` | striking_position | 60 | 18 | -0.0027 | 3 / 4 | 0.762 | 0.0009 | 0.1327 | + | 6.78% | percentage/rate proxy; target/position-mix defense proxy |
| `Head% defense side_pair` | striking_position | 70 | 26 | -0.0027 | 3 / 4 | 0.770 | 0.0009 | 0.0954 | + | 6.78% | percentage/rate proxy; target/position-mix defense proxy |
| `elo oppdiff` | record_experience | 2 | 70 | -0.0024 | 1 / 4 | 0.897 | -0.0004 | 0.1120 | + | 3.58% |  |
| `Ground side_pair` | striking_position | 33 | 43 | -0.0022 | 2 / 4 | 0.945 | -0.0004 | -0.0281 |  | -0.25% |  |
| `Ground oppdiff` | striking_position | 73 | 17 | -0.0022 | 2 / 4 | 0.952 | -0.0004 | -0.0403 |  | -0.25% |  |
| `Head oppdiff` | striking_position | 48 | 21 | -0.0022 | 2 / 4 | 0.674 | -0.0038 | -0.0988 |  | -6.22% |  |
| `Sig. str. side_pair` | striking_position | 63 | 36 | -0.0020 | 2 / 4 | 0.631 | -0.0063 | -0.1139 |  | -7.88% |  |
| `wins oppdiff` | record_experience | 4 | 44 | -0.0020 | 1 / 4 | 0.823 | -0.0012 | 0.1149 | + | 4.30% |  |
| `KD differential oppdiff` | striking_position | 7 | 37 | -0.0020 | 2 / 4 | 0.906 | -0.0002 | -0.0455 | + | 1.86% |  |
| `elo side_pair` | record_experience | 23 | 52 | -0.0020 | 1 / 4 | 0.882 | -0.0004 | 0.1136 | + | 3.58% |  |
| `KD differential side_pair` | striking_position | 54 | 36 | -0.0020 | 2 / 4 | 0.906 | -0.0002 | -0.0327 | + | 1.86% |  |

## Known-Prior Sign Warnings

| Unit | Family | Rank | Importance | Inc Delta LL | Positive Folds | Boot P(delta<=0) | Latest Delta | Coef | Prior | Q4-Q1 Residual | Warning |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `Leg differential side_pair` | striking_position | 52 | 32 | -0.0040 | 1 / 4 | 0.946 | 0.0001 | -0.1136 | + | -0.60% |  |
| `KD differential oppdiff` | striking_position | 7 | 37 | -0.0020 | 2 / 4 | 0.906 | -0.0002 | -0.0455 | + | 1.86% |  |
| `KD differential side_pair` | striking_position | 54 | 36 | -0.0020 | 2 / 4 | 0.906 | -0.0002 | -0.0327 | + | 1.86% |  |
| `age oppdiff` | age_recency | 3 | 69 | -0.0005 | 1 / 4 | 0.752 | -0.0003 | 0.0064 | - | -5.03% |  |
| `totalfights oppdiff` | record_experience | 9 | 36 | -0.0003 | 1 / 4 | 0.559 | -0.0016 | -0.0966 | + | -8.19% |  |
| `totalfights side_pair` | record_experience | 44 | 37 | -0.0003 | 2 / 4 | 0.550 | -0.0016 | -0.0723 | + | -8.19% |  |
| `age side_pair` | age_recency | 65 | 30 | -0.0003 | 2 / 4 | 0.626 | 0.0000 | 0.0051 | - | -5.03% |  |

## Interpretation

- Positive incremental units: `18 / 60`.
- Robust-looking diagnostic units by the loose bootstrap/sign-consistency screen: `6`.
- Best one-feature after-market delta LL: `Sig. str.% differential oppdiff` at `0.0079`.
- Worst one-feature after-market delta LL: `Leg differential side_pair` at `-0.0040`.
- The positive units are concentrated in `striking_position` features; record/experience, age/recency, and grappling units do not show broad individual lift after market control.
- Several helpers are duplicate encodings of the same underlying striking-differential theme, so they should be treated as clues for feature redesign rather than independent alpha discoveries.
- The strongest helper is still a percentage/rate proxy, so its formula should be audited in fight context before using it as a promoted signal.
- Treat this as a feature-forensics map, not feature selection. A promoted feature set still needs a predeclared rolling backtest and market-null/bootstrap validation.
