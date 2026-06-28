# Statistical Edge Audit

Ledgers analyzed: 4. Simulation/bootstrap iterations per run: 20,000.

## Bottom Line

The best saved ledger has market-null p=0.058; Bonferroni across 4 saved ledgers gives p=0.230.
Model probabilities beat de-vigged market log loss in 0/4 ledgers.
Event-bootstrap profit CIs are strictly positive in 0/4 ledgers.
These p-values are conditional on the saved bet decisions and do not remove manual researcher degrees of freedom from feature fixes, DOB masking, strategy selection, or unrecorded failed experiments.

## Run Summary

| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pnl_bugfix_only_men_only_2y | 2024-06-27 to 2026-06-27 | 580 | 467 | 62.6% | 0.640 | 0.600 | $402.38 | 6.6% | 0.076 | $-381.61 to $1,226.40 |
| pnl_closer_to_odds_default_2y | 2024-06-27 to 2026-06-27 | 580 | 481 | 62.6% | 0.640 | 0.600 | $441.85 | 8.2% | 0.058 | $-264.57 to $1,173.38 |
| pnl_bugfix_only_men_only_1y | 2025-06-27 to 2026-06-27 | 298 | 240 | 61.7% | 0.660 | 0.613 | $115.97 | 4.0% | 0.275 | $-415.31 to $678.04 |
| pnl_closer_to_odds_default_1y | 2025-06-27 to 2026-06-27 | 298 | 249 | 61.7% | 0.660 | 0.613 | $114.13 | 4.6% | 0.294 | $-347.18 to $626.46 |

## Highest PnL Runs

| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pnl_closer_to_odds_default_2y | $441.85 | 481 | 62.8% | 65.0% | 62.8% | 6.8% | 0.058 |
| pnl_bugfix_only_men_only_2y | $402.38 | 467 | 57.6% | 65.1% | 57.6% | 9.4% | 0.076 |
| pnl_bugfix_only_men_only_1y | $115.97 | 240 | 57.1% | 65.9% | 57.1% | 9.1% | 0.275 |
| pnl_closer_to_odds_default_1y | $114.13 | 249 | 62.2% | 65.5% | 62.2% | 7.0% | 0.294 |

## How To Read This

- `Market LL` uses de-vigged American odds as the market probability.
- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.
- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.
- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.
