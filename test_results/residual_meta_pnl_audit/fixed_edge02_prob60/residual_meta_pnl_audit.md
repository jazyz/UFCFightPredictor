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
| bets | 354 |
| events with bets | 99 |
| flat profit | +2.44u |
| flat ROI | 0.69% |
| actual win rate | 73.73% |
| mean market probability | 70.54% |
| actual - market | 3.19% |
| positive folds | 3 / 5 |
| event-bootstrap P(profit <= 0) | 0.421 |
| selection-adjusted market-null p-value | 0.117 |

## Market Null

This null simulates outcomes from de-vigged market probabilities and
reruns the full inner meta-training, threshold selection, and outer
holdout evaluation loop.

| Metric | Value |
| --- | ---: |
| iterations | 1000 |
| observed profit | +2.44u |
| null mean profit | -3.87u |
| null 95% interval | -17.99u to +7.77u |
| p-value observed or better | 0.117 |
| probability null profitable | 0.252 |

## Fold Results

| Fold | Policy-Dev Window | Holdout Window | Selected Policy | Dev Bets | Dev Profit | Holdout Bets | Holdout Profit | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2023-02-05 to 2024-02-04 | 2024-02-05 to 2024-08-04 | edge>=0.02, p>=0.60, max dog +300 | 112 | +1.34u | 99 | +4.54u | 4.58% |
| 2 | 2023-08-06 to 2024-08-04 | 2024-08-05 to 2025-02-02 | edge>=0.02, p>=0.60, max dog +300 | 88 | +4.20u | 55 | +5.02u | 9.13% |
| 3 | 2024-02-04 to 2025-02-02 | 2025-02-03 to 2025-08-03 | edge>=0.02, p>=0.60, max dog +300 | 109 | +11.83u | 86 | -5.47u | -6.36% |
| 4 | 2024-08-04 to 2025-08-03 | 2025-08-04 to 2026-02-01 | edge>=0.02, p>=0.60, max dog +300 | 146 | +3.82u | 56 | +2.94u | 5.25% |
| 5 | 2025-02-02 to 2026-02-01 | 2026-02-02 to 2026-06-27 | edge>=0.02, p>=0.60, max dog +300 | 127 | -6.98u | 58 | -4.59u | -7.92% |

## Interpretation

A positive result here would support turning the residual probability
signal into a predeclared betting policy. A weak or negative result
means the probability edge is not yet clearly monetizable after vig,
threshold selection, and schedule variance.
