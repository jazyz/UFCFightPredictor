# Disagreement Forward-Selection Audit

This audit selects simple model-vs-market disagreement policies only on
past data, then evaluates the frozen policy on the next holdout window.
Each bet is flat 1 unit; no Kelly sizing or bankroll compounding is used.

Selection objective: `market_edge`
Candidate policies: 96
Development window length: 365 days
Holdout window length: 182 days
Minimum development bets: 35

## Aggregate Holdout

| Metric | Value |
| --- | ---: |
| folds | 7 |
| holdout fights | 948 |
| bets | 167 |
| events with bets | 96 |
| profit | +15.22u |
| flat ROI | 9.11% |
| actual win rate | 58.68% |
| mean market probability | 51.96% |
| actual - market | 6.72% |
| positive folds | 5 / 7 |
| market-null p-value | 0.090 |
| selection-adjusted market-null p-value | 0.076 |
| event-bootstrap P(profit <= 0) | 0.124 |

## Selection-Adjusted Market Null

This null simulates fight outcomes from de-vigged market probabilities
and reruns the same fold-level policy selection in each simulated
world. It asks how often the policy search itself finds holdout
profit at least as high as the observed result.

| Metric | Value |
| --- | ---: |
| iterations | 2000 |
| observed profit | +15.22u |
| null mean profit | -7.65u |
| null 95% profit interval | -40.69u to +24.17u |
| p-value observed or better | 0.076 |
| probability null profitable | 0.333 |

## Selected Policy Counts

| Policy | Folds |
| --- | ---: |
| regularized_lgbm edge>=0.02 p>=0.65 maxdog=300 | 2 |
| baseline_default edge>=0.08 p>=0.60 maxdog=300 | 1 |
| regularized_lgbm edge>=0.08 p>=0.60 maxdog=300 | 1 |
| regularized_lgbm edge>=0.08 p>=0.65 maxdog=300 | 1 |
| regularized_lgbm edge>=0.12 p>=0.60 maxdog=300 | 1 |
| baseline_default edge>=0.08 p>=0.65 maxdog=none | 1 |

## Folds

| Fold | Dev Window | Holdout Window | Selected Policy | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI | Actual - Market |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2022-02-05 to 2023-02-04 | 2023-02-05 to 2023-08-05 | baseline_default edge>=0.08 p>=0.60 maxdog=300 | +4.74u | 86 | -0.07u | 44 | -0.16% | 0.99% |
| 2 | 2022-08-06 to 2023-08-05 | 2023-08-06 to 2024-02-03 | regularized_lgbm edge>=0.02 p>=0.65 maxdog=300 | +4.40u | 55 | +5.02u | 23 | 21.85% | 14.59% |
| 3 | 2023-02-04 to 2024-02-03 | 2024-02-04 to 2024-08-03 | regularized_lgbm edge>=0.02 p>=0.65 maxdog=300 | +4.42u | 55 | +1.85u | 30 | 6.16% | 7.46% |
| 4 | 2023-08-05 to 2024-08-03 | 2024-08-04 to 2025-02-01 | regularized_lgbm edge>=0.12 p>=0.60 maxdog=300 | +5.10u | 38 | +1.21u | 14 | 8.62% | 5.12% |
| 5 | 2024-02-03 to 2025-02-01 | 2025-02-02 to 2025-08-02 | regularized_lgbm edge>=0.08 p>=0.65 maxdog=300 | +5.56u | 38 | -0.82u | 12 | -6.82% | -1.46% |
| 6 | 2024-08-03 to 2025-08-02 | 2025-08-03 to 2026-01-31 | regularized_lgbm edge>=0.08 p>=0.60 maxdog=300 | +14.54u | 40 | +4.72u | 17 | 27.76% | 15.20% |
| 7 | 2025-02-01 to 2026-01-31 | 2026-02-01 to 2026-06-27 | baseline_default edge>=0.08 p>=0.65 maxdog=none | +19.74u | 39 | +3.31u | 27 | 12.26% | 7.66% |

## Decision Note

This reduces threshold-picking bias relative to a static all-period slice,
but it still does not remove researcher degrees of freedom from choosing
this policy family after earlier diagnostics. Treat positive results as
support for forward paper tracking unless they remain strong after future
post-freeze outcomes.
