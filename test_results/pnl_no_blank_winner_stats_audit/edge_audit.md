# Statistical Edge Audit

Ledgers analyzed: 2. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.275; Bonferroni across 2 saved ledgers gives p=0.550.
Model probabilities beat de-vigged market log loss in 0/2 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/2 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pnl_bugfix_only_men_only_1y | 2025-06-27 to 2026-06-27 | 298 | 240 | 61.7% | 0.660 | 0.613 | $115.97 | 4.0% | 0.275 | $-415.31 to $678.04 |
| pnl_no_blank_winner_stats_1y | 2025-06-27 to 2026-06-27 | 296 | 239 | 61.8% | 0.667 | 0.613 | $39.37 | 1.4% | 0.403 | $-472.56 to $569.62 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pnl_bugfix_only_men_only_1y | $115.97 | 240 | 57.1% | 65.9% | 57.1% | 9.1% | 0.275 |
| pnl_no_blank_winner_stats_1y | $39.37 | 239 | 57.3% | 66.1% | 57.3% | 9.2% | 0.403 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
