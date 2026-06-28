# Statistical Edge Audit

Ledgers analyzed: 1. Simulation/bootstrap iterations per run: 50,000.

## Bottom Line

The best saved ledger has market-null p=0.288; Bonferroni across 1 saved ledgers gives p=0.288.
Model probabilities beat de-vigged market log loss in 0/1 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/1 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| selected_holdout | 2025-06-27 to 2026-06-27 | 298 | 67 | 61.4% | 0.679 | 0.613 | $30.70 | 2.2% | 0.288 | $-338.51 to $409.99 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected_holdout | $30.70 | 67 | 46.3% | 67.3% | 46.3% | 26.2% | 0.288 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
