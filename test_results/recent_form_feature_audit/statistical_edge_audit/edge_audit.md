# Statistical Edge Audit

Ledgers analyzed: 2. Simulation/bootstrap iterations per run: 10,000.

## Bottom Line

The best saved ledger has market-null p=0.166; Bonferroni across 2 saved ledgers gives p=0.333.
Model probabilities beat de-vigged market log loss in 0/2 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/2 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| regularized_recent_form_2y | 2024-06-27 to 2026-06-27 | 580 | 436 | 64.7% | 0.637 | 0.600 | $191.24 | 4.6% | 0.166 | $-365.38 to $749.47 |
| regularized_recent_form_1y | 2025-06-27 to 2026-06-27 | 298 | 228 | 63.1% | 0.644 | 0.613 | $25.72 | 1.3% | 0.426 | $-326.64 to $384.17 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| regularized_recent_form_2y | $191.24 | 436 | 59.4% | 62.1% | 59.4% | 6.5% | 0.166 |
| regularized_recent_form_1y | $25.72 | 228 | 58.3% | 62.5% | 58.3% | 6.2% | 0.426 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
