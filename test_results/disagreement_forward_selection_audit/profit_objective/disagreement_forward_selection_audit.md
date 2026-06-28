# Disagreement Forward-Selection Audit

This audit selects simple model-vs-market disagreement policies only on
past data, then evaluates the frozen policy on the next holdout window.
Each bet is flat 1 unit; no Kelly sizing or bankroll compounding is used.

Selection objective: `profit`
Candidate policies: 96
Development window length: 365 days
Holdout window length: 182 days
Minimum development bets: 35

## Aggregate Holdout

| Metric | Value |
| --- | ---: |
| folds | 7 |
| holdout fights | 948 |
| bets | 373 |
| events with bets | 136 |
| profit | -3.49u |
| flat ROI | -0.93% |
| actual win rate | 52.28% |
| mean market probability | 49.81% |
| actual - market | 2.47% |
| positive folds | 4 / 7 |
| market-null p-value | 0.342 |
| event-bootstrap P(profit <= 0) | 0.570 |

## Selected Policy Counts

| Policy | Folds |
| --- | ---: |
| baseline_default edge>=0.00 p>=0.60 maxdog=300 | 1 |
| baseline_default edge>=0.02 p>=0.55 maxdog=300 | 1 |
| regularized_lgbm edge>=0.02 p>=0.60 maxdog=300 | 1 |
| baseline_default edge>=0.08 p>=0.50 maxdog=300 | 1 |
| regularized_lgbm edge>=0.00 p>=0.50 maxdog=none | 1 |
| baseline_default edge>=0.08 p>=0.50 maxdog=none | 1 |
| baseline_default edge>=0.12 p>=0.50 maxdog=none | 1 |

## Folds

| Fold | Dev Window | Holdout Window | Selected Policy | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI | Actual - Market |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2022-02-05 to 2023-02-04 | 2023-02-05 to 2023-08-05 | baseline_default edge>=0.00 p>=0.60 maxdog=300 | +6.35u | 134 | +1.00u | 63 | 1.60% | 2.95% |
| 2 | 2022-08-06 to 2023-08-05 | 2023-08-06 to 2024-02-03 | baseline_default edge>=0.08 p>=0.50 maxdog=300 | +4.75u | 109 | -3.86u | 42 | -9.19% | 0.08% |
| 3 | 2023-02-04 to 2024-02-03 | 2024-02-04 to 2024-08-03 | baseline_default edge>=0.08 p>=0.50 maxdog=none | +7.76u | 107 | -10.19u | 65 | -15.68% | -1.49% |
| 4 | 2023-08-05 to 2024-08-03 | 2024-08-04 to 2025-02-01 | regularized_lgbm edge>=0.02 p>=0.60 maxdog=300 | +7.75u | 81 | +2.96u | 32 | 9.24% | 7.28% |
| 5 | 2024-02-03 to 2025-02-01 | 2025-02-02 to 2025-08-02 | baseline_default edge>=0.02 p>=0.55 maxdog=300 | +11.48u | 127 | +6.27u | 64 | 9.79% | 6.27% |
| 6 | 2024-08-03 to 2025-08-02 | 2025-08-03 to 2026-01-31 | regularized_lgbm edge>=0.00 p>=0.50 maxdog=none | +26.79u | 135 | +2.88u | 62 | 4.65% | 2.24% |
| 7 | 2025-02-01 to 2026-01-31 | 2026-02-01 to 2026-06-27 | baseline_default edge>=0.12 p>=0.50 maxdog=none | +25.01u | 72 | -2.55u | 45 | -5.66% | 1.25% |

## Decision Note

This reduces threshold-picking bias relative to a static all-period slice,
but it still does not remove researcher degrees of freedom from choosing
this policy family after earlier diagnostics. Treat positive results as
support for forward paper tracking unless they remain strong after future
post-freeze outcomes.
