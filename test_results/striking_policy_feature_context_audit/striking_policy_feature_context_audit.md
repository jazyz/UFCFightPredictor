# Striking Policy Feature Context Audit

This audit checks the exact frozen `sigpct_head_raw_pm` challenger inputs.
It is a diagnostic for feature correctness and context, not a new policy
selection run.

## Frozen Policy Checked

- policy: `sigpct_head_raw_pm_forward_paper_challenger`
- logistic L2 C: `0.1`
- event cap: `None`
- min edge: `0.02`
- features: `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff`, `Head differential_pm oppdiff`

## Integrity Checks

| Check | Value |
| --- | ---: |
| hard failures | 0 |
| raw source rows | 7730 |
| supervised feature rows matched from source | 4322 |
| raw sig/head side mismatches | 0 |
| raw sig/head oppdiff mismatches | 0 |
| rows with prior non-binary state | 1138 |
| source-derived pace rows | 4322 |
| pace side-rate checks | 69152 |
| pace side-rate mismatches | 0 |
| aligned rows missing pace features | 0 |
| totalfights chronology checks | 8644 |
| totalfights chronology mismatches | 0 |
| same-day prior feature sides | 0 |
| same-day prior market-aligned sides | 0 |

Same-day prior rows mean the chronological source order included an earlier
fight on the same calendar day for that fighter. The market-aligned count
is the relevant leakage risk for this policy's evaluated odds universe.

## Feature Sign And Reconstruction

| Feature | Rows | Missing | Mean | p01 | p50 | p99 | Oppdiff Mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `market_logit` | 1223 | 0 | 0.0187 | -1.7886 | 0.0433 | 1.8697 |  |
| `Sig. str.% differential oppdiff` | 1223 | 0 | 0.0001 | -0.4017 | 0.0013 | 0.4010 | 0 |
| `Head differential oppdiff` | 1223 | 0 | -0.3125 | -41.2375 | 0.1440 | 39.0300 | 0 |
| `Head differential_pm oppdiff` | 1223 | 0 | 0.0515 | -7.5532 | -0.0583 | 10.4708 |  |

## Coefficient Stability

Coefficients are from standardized, median-imputed, mirrored logistic folds.
Positive direction is expected for all four policy inputs.

| Feature | Mean Coef | Std | Min | Max | Positive Folds | Direction Consistent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `market_logit` | 0.8999 | 0.0413 | 0.8228 | 0.9754 | 7/7 | 7/7 |
| `Sig. str.% differential oppdiff` | 0.1199 | 0.0579 | 0.0466 | 0.2218 | 7/7 | 7/7 |
| `Head differential oppdiff` | 0.1547 | 0.0265 | 0.1079 | 0.1969 | 7/7 | 7/7 |
| `Head differential_pm oppdiff` | -0.0663 | 0.0208 | -0.1089 | -0.0398 | 0/7 | 0/7 |

## Policy Probability Check

| Metric | Value |
| --- | ---: |
| evaluated rows | 961 |
| market log loss | 0.6001 |
| candidate log loss | 0.5921 |
| delta log loss | 0.0081 |
| market Brier | 0.2063 |
| candidate Brier | 0.2034 |
| delta Brier | 0.0030 |
| positive folds | 7 / 7 |
| event-bootstrap P(delta <= 0) | 0.0047 |

## Feature Residual Shape

| Feature | Rows | Spearman vs Actual-Market | Low Bin A-M | High Bin A-M | High-Low |
| --- | ---: | ---: | ---: | ---: | ---: |
| `Sig. str.% differential oppdiff` | 1223 | 0.0625 | -6.53% | 6.45% | 12.98% |
| `Head differential oppdiff` | 1223 | 0.0360 | -5.57% | 5.43% | 11.00% |
| `Head differential_pm oppdiff` | 1223 | -0.0384 | 0.49% | 1.12% | 0.62% |

### `Sig. str.% differential oppdiff` Bins

| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 245 | -0.6315 to -0.1344 | 38.37% | 44.89% | -6.53% |
| 2 | 244 | -0.1341 to -0.0435 | 43.03% | 45.91% | -2.88% |
| 3 | 245 | -0.0433 to 0.0457 | 50.20% | 50.41% | -0.21% |
| 4 | 244 | 0.0460 to 0.1280 | 59.02% | 53.81% | 5.21% |
| 5 | 245 | 0.1282 to 0.7506 | 63.67% | 57.22% | 6.45% |

### `Head differential oppdiff` Bins

| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 245 | -58.9571 to -11.2919 | 37.14% | 42.71% | -5.57% |
| 2 | 244 | -11.2794 to -3.4860 | 45.08% | 46.54% | -1.46% |
| 3 | 245 | -3.4774 to 3.3917 | 53.88% | 51.96% | 1.92% |
| 4 | 244 | 3.3923 to 10.3429 | 55.74% | 54.02% | 1.72% |
| 5 | 245 | 10.4175 to 70.4134 | 62.45% | 57.02% | 5.43% |

### `Head differential_pm oppdiff` Bins

| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 245 | -25.4189 to -1.5596 | 42.86% | 42.36% | 0.49% |
| 2 | 244 | -1.5521 to -0.4755 | 47.13% | 45.85% | 1.28% |
| 3 | 245 | -0.4716 to 0.4076 | 51.84% | 51.20% | 0.64% |
| 4 | 244 | 0.4083 to 1.5301 | 53.28% | 54.77% | -1.49% |
| 5 | 245 | 1.5402 to 25.4471 | 59.18% | 58.07% | 1.12% |

## Interpretation

- The exact frozen policy inputs passed the direct reconstruction and chronology checks in this audit.
- No same-day source-order prior fights were detected in the feature rows or market-aligned evaluated universe.
- Non-binary outcomes still matter as prior fighter state, but they are absent from supervised win/loss labels.
- Some standardized coefficients did not match the simple expected positive direction: `Head differential_pm oppdiff`.
- In this raw-plus-pace policy, `Head differential_pm oppdiff` behaves like a conditional pace-normalizer rather than a standalone 'more head pace is better' feature.
- Residual-shape bins are descriptive; they support feature sanity, not a fresh live-staking claim.
