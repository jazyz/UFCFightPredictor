# Statistical Edge Audit

Ledgers analyzed: 1. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.257; Bonferroni across 1 saved ledgers gives p=0.257.
Model probabilities beat de-vigged market log loss in 0/1 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/1 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| profit_objective | 2023-02-11 to 2026-06-27 | 962 | 220 | 63.1% | 0.642 | 0.601 | $130.83 | 4.3% | 0.257 | $-419.88 to $683.81 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| profit_objective | $130.83 | 220 | 54.5% | 65.8% | 54.5% | 16.7% | 0.257 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
