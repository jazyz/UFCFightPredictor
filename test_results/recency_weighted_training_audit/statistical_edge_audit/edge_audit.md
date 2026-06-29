# Statistical Edge Audit

Ledgers analyzed: 4. Simulation/bootstrap iterations per run: 10,000.

## Bottom Line

The best saved ledger has market-null p=0.103; Bonferroni across 4 saved ledgers gives p=0.414.
Model probabilities beat de-vigged market log loss in 0/4 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/4 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| regularized_half_life_365_2y | 2024-06-27 to 2026-06-27 | 580 | 482 | 65.2% | 0.648 | 0.600 | $262.85 | 4.1% | 0.125 | $-497.41 to $1,011.06 |
| regularized_half_life_730_2y | 2024-06-27 to 2026-06-27 | 580 | 468 | 64.7% | 0.637 | 0.600 | $314.08 | 5.9% | 0.103 | $-357.20 to $991.17 |
| regularized_half_life_365_1y | 2025-06-27 to 2026-06-27 | 298 | 252 | 65.1% | 0.659 | 0.613 | $110.83 | 3.2% | 0.266 | $-442.84 to $661.77 |
| regularized_half_life_730_1y | 2025-06-27 to 2026-06-27 | 298 | 241 | 65.1% | 0.640 | 0.613 | $154.59 | 5.9% | 0.241 | $-328.59 to $647.94 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| regularized_half_life_730_2y | $314.08 | 468 | 60.9% | 65.4% | 60.9% | 8.9% | 0.103 |
| regularized_half_life_365_2y | $262.85 | 482 | 61.8% | 67.3% | 61.8% | 10.9% | 0.125 |
| regularized_half_life_730_1y | $154.59 | 241 | 62.7% | 67.1% | 62.7% | 9.6% | 0.241 |
| regularized_half_life_365_1y | $110.83 | 252 | 62.3% | 68.9% | 62.3% | 12.2% | 0.266 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
