# Residual Meta PnL Audit

This audit tests whether the residual market/meta probability signal can
be converted into a simple flat-stake betting rule without using holdout
outcomes for threshold selection.

## Protocol

- model residual: `regularized_lgbm`
- meta feature columns: `market_logit, regularized_lgbm_logit_delta`
- outer development window: `730` days
- inner meta-training window: `365` days
- holdout window: `182` days
- meta logistic C: `0.25`
- selection objective: `profit`

Within each outer fold, the first part of the development window fits the
meta layer, the second part selects betting thresholds using out-of-sample
meta probabilities, and the selected policy is then frozen onto the outer
holdout.

## Aggregate Holdout

| Metric | Value |
| --- | ---: |
| folds | 5 |
| holdout fights | 704 |
| bets | 363 |
| events with bets | 101 |
| flat profit | +7.46u |
| flat ROI | 2.06% |
| actual win rate | 73.83% |
| mean market probability | 69.73% |
| actual - market | 4.10% |
| positive folds | 4 / 5 |
| event-bootstrap P(profit <= 0) | 0.258 |
| selection-adjusted market-null p-value | 0.066 |

## Market Null

This null simulates outcomes from de-vigged market probabilities and
reruns the full inner meta-training, threshold selection, and outer
holdout evaluation loop.

| Metric | Value |
| --- | ---: |
| iterations | 1000 |
| observed profit | +7.46u |
| null mean profit | -5.17u |
| null 95% interval | -21.36u to +12.21u |
| p-value observed or better | 0.066 |
| probability null profitable | 0.250 |

## Fold Results

| Fold | Policy-Dev Window | Holdout Window | Selected Policy | Dev Bets | Dev Profit | Holdout Bets | Holdout Profit | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2023-02-05 to 2024-02-04 | 2024-02-05 to 2024-08-04 | edge>=0.01, p>=0.65, max dog +300 | 114 | +8.66u | 94 | +3.38u | 3.59% |
| 2 | 2023-08-06 to 2024-08-04 | 2024-08-05 to 2025-02-02 | edge>=0.00, p>=0.55, max dog +300 | 142 | +15.15u | 87 | +4.50u | 5.17% |
| 3 | 2024-02-04 to 2025-02-02 | 2025-02-03 to 2025-08-03 | edge>=0.02, p>=0.60, max dog +300 | 109 | +11.83u | 86 | -5.47u | -6.36% |
| 4 | 2024-08-04 to 2025-08-03 | 2025-08-04 to 2026-02-01 | edge>=0.02, p>=0.50, max dog +300 | 160 | +4.01u | 66 | +3.90u | 5.90% |
| 5 | 2025-02-02 to 2026-02-01 | 2026-02-02 to 2026-06-27 | edge>=0.05, p>=0.50, max dog +300 | 80 | +0.82u | 30 | +1.16u | 3.86% |

## Interpretation

A positive result here would support turning the residual probability
signal into a predeclared betting policy. A weak or negative result
means the probability edge is not yet clearly monetizable after vig,
threshold selection, and schedule variance.
