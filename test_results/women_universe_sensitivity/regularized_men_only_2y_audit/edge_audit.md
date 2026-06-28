# Statistical Edge Audit

Ledgers analyzed: 1. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.034; Bonferroni across 1 saved ledgers gives p=0.034.
Model probabilities beat de-vigged market log loss in 0/1 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/1 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| regularized_lgbm_2y | 2024-06-27 to 2026-06-27 | 580 | 442 | 65.0% | 0.632 | 0.600 | $611.97 | 11.5% | 0.034 | $-111.50 to $1,331.47 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| regularized_lgbm_2y | $611.97 | 442 | 60.0% | 62.6% | 60.0% | 7.3% | 0.034 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
