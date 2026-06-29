# Nested Walk-Forward Edge Audit

Selection objective: `profit`
Development window length: 365 days
Holdout window length: 182 days
Minimum holdout length: 120 days
Minimum development bets: 35

## Aggregate Holdout

Folds: 7
Fights: 962
Bets: 220
Profit: $130.83
ROI on staked: 4.26%
Positive folds: 3 / 7
Selected models: `{"baseline_default": 1, "current_regularized": 1, "drop_muddy_pct_and_dob": 3, "drop_target_mix_defense": 2}`

## Folds

| Fold | Dev Window | Holdout Window | Selected Model | Edge | Min P | Kelly | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2022-02-05 to 2023-02-04 | 2023-02-05 to 2023-08-05 | drop_muddy_pct_and_dob | 0.02 | 0.60 | 0.050 | $37.51 | 62 | $-1.04 | 21 | -0.78% |
| 2 | 2022-08-06 to 2023-08-05 | 2023-08-06 to 2024-02-03 | drop_muddy_pct_and_dob | 0.02 | 0.60 | 0.050 | $31.77 | 51 | $-4.63 | 18 | -2.89% |
| 3 | 2023-02-04 to 2024-02-03 | 2024-02-04 to 2024-08-03 | drop_target_mix_defense | 0.16 | 0.50 | 0.050 | $176.85 | 51 | $-111.56 | 31 | -19.71% |
| 4 | 2023-08-05 to 2024-08-03 | 2024-08-04 to 2025-02-01 | drop_target_mix_defense | 0.02 | 0.60 | 0.050 | $123.42 | 62 | $-36.47 | 22 | -10.02% |
| 5 | 2024-02-03 to 2025-02-01 | 2025-02-02 to 2025-08-02 | current_regularized | 0.02 | 0.60 | 0.050 | $107.94 | 75 | $148.01 | 33 | 33.56% |
| 6 | 2024-08-03 to 2025-08-02 | 2025-08-03 to 2026-01-31 | baseline_default | 0.02 | 0.50 | 0.050 | $579.07 | 117 | $132.75 | 37 | 20.38% |
| 7 | 2025-02-01 to 2026-01-31 | 2026-02-01 to 2026-06-27 | drop_muddy_pct_and_dob | 0.02 | 0.50 | 0.050 | $690.94 | 116 | $3.78 | 58 | 0.50% |

Each fold resets bankroll to $1000. Aggregate profit is the sum of
fold-level holdout profits, so treat it as repeated independent
paper-tracking experiments rather than one continuously compounded
live bankroll.
