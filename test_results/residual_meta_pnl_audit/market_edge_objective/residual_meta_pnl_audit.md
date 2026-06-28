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
- selection objective: `market_edge`

Within each outer fold, the first part of the development window fits the
meta layer, the second part selects betting thresholds using out-of-sample
meta probabilities, and the selected policy is then frozen onto the outer
holdout.

## Aggregate Holdout

| Metric | Value |
| --- | ---: |
| folds | 5 |
| holdout fights | 704 |
| bets | 311 |
| events with bets | 99 |
| flat profit | +6.67u |
| flat ROI | 2.14% |
| actual win rate | 74.28% |
| mean market probability | 70.20% |
| actual - market | 4.08% |
| positive folds | 4 / 5 |
| event-bootstrap P(profit <= 0) | 0.265 |
| selection-adjusted market-null p-value | 0.083 |

## Market Null

This null simulates outcomes from de-vigged market probabilities and
reruns the full inner meta-training, threshold selection, and outer
holdout evaluation loop.

| Metric | Value |
| --- | ---: |
| iterations | 1000 |
| observed profit | +6.67u |
| null mean profit | -4.56u |
| null 95% interval | -20.72u to +10.95u |
| p-value observed or better | 0.083 |
| probability null profitable | 0.288 |

## Fold Results

| Fold | Policy-Dev Window | Holdout Window | Selected Policy | Dev Bets | Dev Profit | Holdout Bets | Holdout Profit | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2023-02-05 to 2024-02-04 | 2024-02-05 to 2024-08-04 | edge>=0.01, p>=0.65, max dog +300 | 114 | +8.66u | 94 | +3.38u | 3.59% |
| 2 | 2023-08-06 to 2024-08-04 | 2024-08-05 to 2025-02-02 | edge>=0.03, p>=0.65, max dog +300 | 26 | +5.44u | 45 | +4.66u | 10.35% |
| 3 | 2024-02-04 to 2025-02-02 | 2025-02-03 to 2025-08-03 | edge>=0.02, p>=0.60, max dog +300 | 109 | +11.83u | 86 | -5.47u | -6.36% |
| 4 | 2024-08-04 to 2025-08-03 | 2025-08-04 to 2026-02-01 | edge>=0.02, p>=0.60, max dog +300 | 146 | +3.82u | 56 | +2.94u | 5.25% |
| 5 | 2025-02-02 to 2026-02-01 | 2026-02-02 to 2026-06-27 | edge>=0.05, p>=0.50, max dog +300 | 80 | +0.82u | 30 | +1.16u | 3.86% |

## Interpretation

A positive result here would support turning the residual probability
signal into a predeclared betting policy. A weak or negative result
means the probability edge is not yet clearly monetizable after vig,
threshold selection, and schedule variance.
