# Nested Walk-Forward Edge Audit

Selection objective: `roi`
Development window length: 365 days
Holdout window length: 182 days
Minimum holdout length: 120 days
Minimum development bets: 35

## Aggregate Holdout

Folds: 7
Fights: 962
Bets: 147
Profit: $-19.65
ROI on staked: -2.00%
Positive folds: 3 / 7
Selected models: `{"current_regularized": 2, "drop_muddy_pct_and_dob": 3, "drop_target_mix_defense": 2}`

## Folds

| Fold | Dev Window | Holdout Window | Selected Model | Edge | Min P | Kelly | Dev Profit | Dev Bets | Holdout Profit | Holdout Bets | Holdout ROI |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2022-02-05 to 2023-02-04 | 2023-02-05 to 2023-08-05 | drop_muddy_pct_and_dob | 0.02 | 0.60 | 0.025 | $19.13 | 62 | $-0.36 | 21 | -0.54% |
| 2 | 2022-08-06 to 2023-08-05 | 2023-08-06 to 2024-02-03 | drop_muddy_pct_and_dob | 0.02 | 0.60 | 0.025 | $16.18 | 51 | $-2.16 | 18 | -2.69% |
| 3 | 2023-02-04 to 2024-02-03 | 2024-02-04 to 2024-08-03 | drop_target_mix_defense | 0.16 | 0.50 | 0.025 | $91.09 | 51 | $-56.10 | 31 | -19.27% |
| 4 | 2023-08-05 to 2024-08-03 | 2024-08-04 to 2025-02-01 | current_regularized | 0.02 | 0.60 | 0.050 | $81.57 | 37 | $16.83 | 8 | 23.07% |
| 5 | 2024-02-03 to 2025-02-01 | 2025-02-02 to 2025-08-02 | current_regularized | 0.02 | 0.60 | 0.025 | $49.54 | 48 | $-1.62 | 20 | -2.07% |
| 6 | 2024-08-03 to 2025-08-02 | 2025-08-03 to 2026-01-31 | drop_target_mix_defense | 0.08 | 0.50 | 0.025 | $124.37 | 50 | $21.99 | 18 | 19.71% |
| 7 | 2025-02-01 to 2026-01-31 | 2026-02-01 to 2026-06-27 | drop_muddy_pct_and_dob | 0.16 | 0.50 | 0.025 | $297.17 | 45 | $1.77 | 31 | 0.63% |

Each fold resets bankroll to $1000. Aggregate profit is the sum of
fold-level holdout profits, so treat it as repeated independent
paper-tracking experiments rather than one continuously compounded
live bankroll.
