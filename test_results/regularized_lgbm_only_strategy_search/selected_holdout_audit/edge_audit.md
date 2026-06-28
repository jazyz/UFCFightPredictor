# Statistical Edge Audit

Ledgers analyzed: 1. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.072; Bonferroni across 1 saved ledgers gives p=0.072.
Model probabilities beat de-vigged market log loss in 0/1 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/1 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| selected_holdout | 2025-06-27 to 2026-06-27 | 298 | 51 | 64.4% | 0.642 | 0.613 | $198.17 | 19.3% | 0.072 | $-108.77 to $499.31 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected_holdout | $198.17 | 51 | 49.0% | 63.2% | 49.0% | 23.5% | 0.072 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
