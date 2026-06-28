# Statistical Edge Audit

Ledgers analyzed: 21. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.008; Bonferroni across 21 saved ledgers gives p=0.166.
Model probabilities beat de-vigged market log loss in 0/21 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/21 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| no_leakage_backtest_2y | 2024-06-27 to 2026-06-27 | 576 | 455 | 64.1% | 0.650 | 0.598 | $315.35 | 5.5% | 0.055 | $-437.50 to $1,111.49 |
| pnl_after_first4_2y | 2024-06-27 to 2026-06-27 | 580 | 467 | 62.6% | 0.640 | 0.600 | $430.48 | 7.1% | 0.030 | $-361.09 to $1,249.64 |
| pnl_bugfix_only_men_only_2y | 2024-06-27 to 2026-06-27 | 580 | 467 | 62.6% | 0.640 | 0.600 | $402.38 | 6.6% | 0.076 | $-375.80 to $1,214.12 |
| pnl_coverage_fixed_men_only_2y | 2024-06-27 to 2026-06-27 | 706 | 542 | 62.5% | 0.645 | 0.595 | $132.87 | 2.1% | 0.181 | $-567.06 to $847.56 |
| pnl_diag_age_nan_2y | 2024-06-27 to 2026-06-27 | 576 | 467 | 64.2% | 0.640 | 0.598 | $599.68 | 9.3% | 0.017 | $-200.63 to $1,422.87 |
| pnl_diag_dob_backfilled_2y | 2024-06-27 to 2026-06-27 | 576 | 467 | 64.9% | 0.633 | 0.598 | $804.15 | 12.0% | 0.008 | $-62.66 to $1,713.53 |
| pnl_diag_excluded_dob_policy_2y | 2024-06-27 to 2026-06-27 | 576 | 467 | 64.9% | 0.633 | 0.598 | $804.15 | 12.0% | 0.008 | $-49.94 to $1,696.81 |
| pnl_edge2_no_flat_2y | 2024-06-27 to 2026-06-27 | 580 | 257 | 62.6% | 0.640 | 0.600 | $541.94 | 10.8% | 0.060 | $-281.95 to $1,423.83 |
| pnl_after_first4_1y | 2025-06-27 to 2026-06-27 | 298 | 240 | 61.7% | 0.660 | 0.613 | $138.33 | 4.8% | 0.122 | $-387.95 to $709.55 |
| pnl_bugfix_only_men_only_1y | 2025-06-27 to 2026-06-27 | 298 | 240 | 61.7% | 0.660 | 0.613 | $115.97 | 4.0% | 0.275 | $-414.23 to $682.65 |
| pnl_coverage_fixed_men_only_1y | 2025-06-27 to 2026-06-27 | 361 | 273 | 60.4% | 0.658 | 0.612 | $-43.00 | -1.5% | 0.465 | $-503.97 to $440.44 |
| pnl_diag_age_nan_1y | 2025-06-27 to 2026-06-27 | 295 | 235 | 62.4% | 0.653 | 0.611 | $237.06 | 7.9% | 0.070 | $-276.32 to $763.36 |
| pnl_diag_all_missing_dobs_resolved_1y | 2025-06-27 to 2026-06-27 | 295 | 237 | 59.7% | 0.655 | 0.611 | $-37.82 | -1.6% | 0.316 | $-442.51 to $410.90 |
| pnl_diag_all_missing_dobs_resolved_1y_no_flat | 2025-06-27 to 2026-06-27 | 295 | 139 | 59.7% | 0.655 | 0.611 | $-37.34 | -1.9% | 0.358 | $-436.94 to $387.09 |
| pnl_diag_best_params_1y | 2025-06-27 to 2026-06-27 | 295 | 235 | 63.4% | 0.663 | 0.611 | $228.02 | 7.1% | 0.083 | $-375.29 to $840.73 |
| pnl_diag_dob_backfilled_1y | 2025-06-27 to 2026-06-27 | 295 | 234 | 64.4% | 0.646 | 0.611 | $317.45 | 11.1% | 0.044 | $-230.66 to $897.29 |
| pnl_diag_exclude_7_dobs_1y | 2025-06-27 to 2026-06-27 | 295 | 234 | 64.4% | 0.646 | 0.611 | $317.45 | 11.1% | 0.044 | $-229.63 to $896.92 |
| pnl_diag_excluded_dob_policy_1y | 2025-06-27 to 2026-06-27 | 295 | 234 | 64.4% | 0.646 | 0.611 | $317.45 | 11.1% | 0.042 | $-233.41 to $891.01 |
| pnl_diag_patched_1y | 2025-06-27 to 2026-06-27 | 295 | 235 | 62.4% | 0.653 | 0.611 | $237.06 | 7.9% | 0.068 | $-269.22 to $766.35 |
| pnl_edge2_no_flat_1y | 2025-06-27 to 2026-06-27 | 298 | 128 | 61.7% | 0.660 | 0.613 | $168.91 | 7.3% | 0.254 | $-367.07 to $760.92 |
| test_results_current | 2025-06-27 to 2026-06-27 | 295 | 229 | 62.7% | 0.673 | 0.611 | $68.36 | 2.6% | 0.186 | $-431.73 to $602.27 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pnl_diag_dob_backfilled_2y | $804.15 | 467 | 60.8% | 65.3% | 60.8% | 10.1% | 0.008 |
| pnl_diag_excluded_dob_policy_2y | $804.15 | 467 | 60.8% | 65.3% | 60.8% | 10.1% | 0.008 |
| pnl_diag_age_nan_2y | $599.68 | 467 | 60.2% | 65.3% | 60.2% | 10.1% | 0.017 |
| pnl_edge2_no_flat_2y | $541.94 | 257 | 52.1% | 65.5% | 52.1% | 18.4% | 0.060 |
| pnl_after_first4_2y | $430.48 | 467 | 57.6% | 65.1% | 57.6% | 9.4% | 0.030 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
