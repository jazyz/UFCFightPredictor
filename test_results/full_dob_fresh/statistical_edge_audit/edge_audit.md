# Statistical Edge Audit

Ledgers analyzed: 8. Simulation/bootstrap iterations per run: 50,000.

## Bottom Line

The best saved ledger has market-null p=0.125; Bonferroni across 8 saved ledgers gives p=0.996.
Model probabilities beat de-vigged market log loss in 0/8 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/8 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| best_params_2y | 2024-06-27 to 2026-06-27 | 580 | 469 | 63.3% | 0.659 | 0.600 | $280.57 | 4.4% | 0.125 | $-483.58 to $1,054.73 |
| conservative_2y | 2024-06-27 to 2026-06-27 | 580 | 468 | 62.4% | 0.644 | 0.600 | $83.71 | 2.5% | 0.169 | $-252.20 to $427.48 |
| default_2y | 2024-06-27 to 2026-06-27 | 580 | 468 | 62.4% | 0.644 | 0.600 | $167.56 | 2.9% | 0.178 | $-513.15 to $876.19 |
| edge2_no_flat_2y | 2024-06-27 to 2026-06-27 | 580 | 270 | 62.4% | 0.644 | 0.600 | $181.22 | 4.0% | 0.201 | $-517.48 to $914.83 |
| best_params_1y | 2025-06-27 to 2026-06-27 | 298 | 243 | 61.4% | 0.679 | 0.613 | $3.20 | 0.1% | 0.411 | $-506.71 to $533.88 |
| conservative_1y | 2025-06-27 to 2026-06-27 | 298 | 243 | 59.7% | 0.661 | 0.613 | $-29.17 | -1.8% | 0.501 | $-263.09 to $216.61 |
| default_1y | 2025-06-27 to 2026-06-27 | 298 | 243 | 59.7% | 0.661 | 0.613 | $-49.36 | -1.8% | 0.506 | $-502.69 to $432.60 |
| edge2_no_flat_1y | 2025-06-27 to 2026-06-27 | 298 | 145 | 59.7% | 0.661 | 0.613 | $-50.56 | -2.3% | 0.540 | $-502.51 to $432.01 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| best_params_2y | $280.57 | 469 | 58.6% | 65.5% | 58.6% | 10.5% | 0.125 |
| edge2_no_flat_2y | $181.22 | 270 | 49.6% | 65.3% | 49.6% | 17.9% | 0.201 |
| default_2y | $167.56 | 468 | 57.9% | 65.0% | 57.9% | 9.4% | 0.178 |
| conservative_2y | $83.71 | 468 | 57.9% | 65.0% | 57.9% | 9.4% | 0.169 |
| best_params_1y | $3.20 | 243 | 57.2% | 66.0% | 57.2% | 10.3% | 0.411 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
