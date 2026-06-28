# Statistical Edge Audit

Ledgers analyzed: 2. Simulation/bootstrap iterations per run: 10,000.

## Bottom Line

The best saved ledger has market-null p=0.059; Bonferroni across 2 saved ledgers gives p=0.117.
Model probabilities beat de-vigged market log loss in 0/2 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/2 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| feature_variant_engineered_regularized_2y | 2024-06-27 to 2026-06-27 | 580 | 436 | 65.2% | 0.636 | 0.600 | $479.54 | 8.9% | 0.059 | $-251.25 to $1,192.20 |
| feature_variant_engineered_regularized_1y | 2025-06-27 to 2026-06-27 | 298 | 225 | 62.8% | 0.651 | 0.613 | $41.19 | 1.9% | 0.417 | $-356.23 to $440.49 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| feature_variant_engineered_regularized_2y | $479.54 | 436 | 59.6% | 62.4% | 59.6% | 7.4% | 0.059 |
| feature_variant_engineered_regularized_1y | $41.19 | 225 | 56.4% | 62.9% | 56.4% | 7.0% | 0.417 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
