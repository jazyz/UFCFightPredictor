# Nested Walk-Forward Edge Audit

Selection objective: `profit`
Development window length: 365 days
Holdout window length: 182 days
Minimum holdout length: 120 days
Minimum development bets: 35

## Aggregate Holdout

Folds: 7
Fights: 962
Bets: 277
Profit: $170.39
ROI on staked: 4.00%
Positive folds: 4 / 7
Selected models: `{"baseline_default": 5, "regularized_lgbm": 2}`

## Folds

| Fold | Dev Window | Holdout Window | Selected Model | Edge | Min P | Kelly | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2022-02-05 to 2023-02-04 | 2023-02-05 to 2023-08-05 | baseline_default | 0.02 | 0.60 | 0.050 | $32.47 | 119 | $-23.15 | 55 | -2.83% |
| 2 | 2022-08-06 to 2023-08-05 | 2023-08-06 to 2024-02-03 | baseline_default | 0.02 | 0.50 | 0.050 | $13.22 | 118 | $-66.51 | 49 | -8.01% |
| 3 | 2023-02-04 to 2024-02-03 | 2024-02-04 to 2024-08-03 | baseline_default | 0.02 | 0.60 | 0.050 | $87.93 | 43 | $7.15 | 31 | 1.65% |
| 4 | 2023-08-05 to 2024-08-03 | 2024-08-04 to 2025-02-01 | regularized_lgbm | 0.02 | 0.60 | 0.050 | $81.57 | 37 | $16.83 | 8 | 23.07% |
| 5 | 2024-02-03 to 2025-02-01 | 2025-02-02 to 2025-08-02 | regularized_lgbm | 0.02 | 0.60 | 0.050 | $107.94 | 75 | $148.01 | 33 | 33.56% |
| 6 | 2024-08-03 to 2025-08-02 | 2025-08-03 to 2026-01-31 | baseline_default | 0.02 | 0.50 | 0.050 | $579.07 | 117 | $132.75 | 37 | 20.38% |
| 7 | 2025-02-01 to 2026-01-31 | 2026-02-01 to 2026-06-27 | baseline_default | 0.02 | 0.50 | 0.050 | $665.87 | 95 | $-44.68 | 64 | -4.42% |

Each fold resets bankroll to $1000. Aggregate profit is the sum of
fold-level holdout profits, so treat it as repeated independent
paper-tracking experiments rather than one continuously compounded
live bankroll.
