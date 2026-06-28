# Nested Walk-Forward Edge Audit

Selection objective: `roi`
Development window length: 365 days
Holdout window length: 182 days
Minimum holdout length: 120 days
Minimum development bets: 35

## Aggregate Holdout

Folds: 7
Fights: 962
Bets: 140
Profit: $95.31
ROI on staked: 8.10%
Positive folds: 4 / 7
Selected models: `{"baseline_default": 2, "regularized_lgbm": 3, "regularized_women_train_men_eval": 2}`

## Folds

| Fold | Dev Window | Holdout Window | Selected Model | Edge | Min P | Kelly | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2022-02-05 to 2023-02-04 | 2023-02-05 to 2023-08-05 | regularized_women_train_men_eval | 0.02 | 0.60 | 0.025 | $24.13 | 51 | $-20.36 | 21 | -29.93% |
| 2 | 2022-08-06 to 2023-08-05 | 2023-08-06 to 2024-02-03 | baseline_default | 0.02 | 0.60 | 0.025 | $6.67 | 52 | $34.31 | 17 | 27.74% |
| 3 | 2023-02-04 to 2024-02-03 | 2024-02-04 to 2024-08-03 | baseline_default | 0.02 | 0.60 | 0.025 | $44.65 | 43 | $4.15 | 31 | 1.94% |
| 4 | 2023-08-05 to 2024-08-03 | 2024-08-04 to 2025-02-01 | regularized_lgbm | 0.02 | 0.60 | 0.050 | $81.57 | 37 | $16.83 | 8 | 23.07% |
| 5 | 2024-02-03 to 2025-02-01 | 2025-02-02 to 2025-08-02 | regularized_lgbm | 0.02 | 0.60 | 0.025 | $49.54 | 48 | $-1.62 | 20 | -2.07% |
| 6 | 2024-08-03 to 2025-08-02 | 2025-08-03 to 2026-01-31 | regularized_lgbm | 0.16 | 0.50 | 0.025 | $185.08 | 45 | $85.42 | 18 | 51.18% |
| 7 | 2025-02-01 to 2026-01-31 | 2026-02-01 to 2026-06-27 | regularized_women_train_men_eval | 0.16 | 0.50 | 0.050 | $698.49 | 44 | $-23.41 | 25 | -5.17% |

Each fold resets bankroll to $1000. Aggregate profit is the sum of
fold-level holdout profits, so treat it as repeated independent
paper-tracking experiments rather than one continuously compounded
live bankroll.
