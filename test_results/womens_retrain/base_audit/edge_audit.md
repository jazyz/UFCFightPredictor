# Statistical Edge Audit

Ledgers analyzed: 4. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.465; Bonferroni across 4 saved ledgers gives p=1.000.
Model probabilities beat de-vigged market log loss in 0/4 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/4 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| best_params_all_history_2y | 2024-06-27 to 2026-06-27 | 120 | 85 | 65.8% | 0.630 | 0.538 | $-115.51 | -16.0% | 0.756 | $-281.44 to $51.28 |
| best_params_women_only_2y | 2024-06-27 to 2026-06-27 | 120 | 91 | 64.2% | 0.622 | 0.538 | $-58.08 | -4.7% | 0.467 | $-377.68 to $291.93 |
| default_all_history_2y | 2024-06-27 to 2026-06-27 | 120 | 83 | 70.0% | 0.612 | 0.538 | $-27.91 | -4.1% | 0.465 | $-197.73 to $137.54 |
| default_women_only_2y | 2024-06-27 to 2026-06-27 | 120 | 98 | 61.7% | 0.660 | 0.538 | $-207.77 | -14.5% | 0.771 | $-503.18 to $88.91 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| default_all_history_2y | $-27.91 | 83 | 65.1% | 63.3% | 65.1% | 4.9% | 0.465 |
| best_params_women_only_2y | $-58.08 | 91 | 60.4% | 69.4% | 60.4% | 11.8% | 0.467 |
| best_params_all_history_2y | $-115.51 | 85 | 58.8% | 64.9% | 58.8% | 6.5% | 0.756 |
| default_women_only_2y | $-207.77 | 98 | 60.2% | 74.0% | 60.2% | 14.3% | 0.771 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
