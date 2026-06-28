# Women's Fight Retrain PnL Audit

Date run: 2026-06-28

## Objective

Test whether adding women's fights back into preprocessing, retraining on them,
and predicting women's bouts can improve PnL under leak-safe evaluation.

## Data and Protocol

- Generated a separate women-included processed feature table:
  `test_results/womens_retrain/detailed_fights_womens_included.csv`.
- Left production `data/detailed_fights.csv` untouched.
- Evaluation window: `2024-06-27` to `2026-06-27`.
- Development window for strategy search: `2024-06-27` to `2025-06-26`.
- Holdout window for frozen strategy evaluation: `2025-06-27` to `2026-06-27`.
- Rolling backtests retrained before each event date using only prior fights.
- Statistical audit used 20,000 event bootstraps / market-null path simulations.

Processed women-fight coverage:

| Dataset | Women's Rows | Date Range |
| --- | ---: | --- |
| Raw cleaned fight details | 923 | 2013-02-23 to 2026-06-20 |
| Processed feature rows | 546 | 2014-04-19 to 2026-06-20 |
| Processed feature rows in test window | 120 | 2024-06-27 to 2026-06-27 |

Women odds coverage in the test window had 143 rows, 108 matched processed
feature rows, and the latest matched women odds date was `2026-04-18`.

## Base Rolling Backtests

| Run | Training Universe | Params | Fights | Bets | Accuracy | Log Loss | Profit | Market LL | Market-Null p | Bootstrap Profit CI |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| default_all_history_2y | all fights | built-in default | 120 | 83 | 70.0% | 0.612 | -$27.91 | 0.538 | 0.465 | -$197.73 to $137.54 |
| best_params_all_history_2y | all fights | `data/best_params.json` | 120 | 85 | 65.8% | 0.630 | -$115.51 | 0.538 | 0.756 | -$281.44 to $51.28 |
| default_women_only_2y | women's fights only | built-in default | 120 | 98 | 61.7% | 0.660 | -$207.77 | 0.538 | 0.771 | -$503.18 to $88.91 |
| best_params_women_only_2y | women's fights only | `data/best_params.json` | 120 | 91 | 64.2% | 0.622 | -$58.08 | 0.538 | 0.467 | -$377.68 to $291.93 |

The strongest raw accuracy came from training on all historical fights and
evaluating women's fights only, but its probabilities still lost to the
de-vigged market on log loss and its default PnL was negative.

## Accuracy and Cherry-Picking Check

The `70.0%` accuracy result was not produced by tuning specifically for
accuracy after looking at the test rows. It came from one natural base variant:
default built-in LightGBM params, training on all prior processed fights, and
evaluating only women's fights.

That said, it is still the best of four base variants, so spotlighting it has a
small multiple-comparisons caveat. The full base grid was:

| Run | Correct / Fights | Accuracy | Approx. 95% Accuracy Interval |
| --- | ---: | ---: | --- |
| default_all_history_2y | 84 / 120 | 70.0% | 61.8% to 78.2% |
| best_params_all_history_2y | 79 / 120 | 65.8% | 57.3% to 74.3% |
| best_params_women_only_2y | 77 / 120 | 64.2% | 55.6% to 72.7% |
| default_women_only_2y | 74 / 120 | 61.7% | 53.0% to 70.4% |

The bigger reason the accuracy looked high is that this women-only slice was
small and favorite-heavy. On the 108 fights with matched odds, the de-vigged
market favorite was correct `75.0%` of the time, beating every model variant on
accuracy and beating every model variant on log loss. So the high model
accuracy is real in the saved ledger, but it does not imply the model had an
edge over market prices.

## Walk-Forward Strategy Search

Candidate strategies evaluated on development only: 1,152.

Selected strategy:

```json
{
  "model_label": "best_params_women_only",
  "side_policy": "predicted_winner",
  "model_weight": 1.0,
  "min_edge": 0.08,
  "min_probability": 0.6,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

| Split | Profit | Bets | ROI on Staked | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| Development | $19.03 | 24 | 3.63% | 9.30% |
| Holdout | $12.99 | 15 | 3.92% | 6.64% |

Holdout inference:

- market-null p-value: `0.341`
- event-bootstrap profit CI: `-$139.14` to `$144.65`
- probability of bootstrap profit <= 0: `41.34%`
- model log loss: `0.590`
- de-vigged market log loss: `0.488`
- McNemar one-sided p-value versus market favorite: `0.999`

## Conclusion

The women-focused path produced a small holdout PnL improvement after dev-only
strategy selection: `$12.99` on a `$1,000` bankroll. Statistically, it is weak:
the market-null p-value is not close to significant, the event-bootstrap profit
CI crosses zero widely, and market probabilities beat model probabilities on
log loss.

Practical read: including and evaluating women's fights is now supported and
produces useful ledgers, but this experiment does not establish a reliable live
betting edge.
