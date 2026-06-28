# Women Universe Sensitivity

Date documented: 2026-06-28

## Question

Check whether the current men-only production universe matters, and whether
letting women's fights into training changes men-only evaluation.

## Runs Compared

| Run | Feature Table | Training Universe | Evaluation Universe | Fights | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-Null p | Bootstrap Profit CI |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| current regularized men-only | `data/detailed_fights.csv` | men only | men only | 580 | 65.0% | 0.632 | 0.600 | $611.97 | 11.5% | 0.034 | $-111.50 to $1,331.47 |
| women-included training, men-only eval | `test_results/womens_retrain/detailed_fights_womens_included.csv` | all prior fights | men only | 580 | 65.9% | 0.633 | 0.600 | $733.69 | 14.4% | 0.013 | $11.32 to $1,475.00 |

Both rows use the regularized LightGBM params from
`test_results/regularized_lgbm_params.json`, the 2024-06-27 to 2026-06-27
window, and 20,000 market-null/bootstrap iterations in the statistical audit.
The men-only evaluation filter now treats `Women` as a universe concept, not
only a title substring, so known women-vs-women catchweight rows such as
`Catch Weight Bout` are excluded too.

## Interpretation

Adding women's fights to training while evaluating only men's fights changed the
saved ledger: PnL rose from `$611.97` to `$733.69`, and the conditional
market-null p-value improved from `0.034` to `0.013`.

That is not enough to claim a better edge. In both runs, model probabilities
still lose to the de-vigged market on log loss. The women-included-training run
has model LL `0.6327` versus market LL `0.5995`; event bootstrap estimates
`P(model not better than market on log loss) = 0.9977`.

Practical read: the current production claim remains men-only, and that is
already audited. Women-included training is worth keeping as an exploratory
counterfactual, but it should not replace the frozen production policy unless a
pre-registered walk-forward probability/PnL test beats the market after
selection adjustment.

## Long-Window Sensitivity

The same women-included-training / men-only-evaluation idea was also checked on
the longer 2022-02-05 to 2026-06-27 window.

| Run | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| women-included training, men-only eval 2022-2026 | 1249 | 945 | 64.5% | 0.641 | 0.601 | $364.11 | 4.7% | 0.057 | $-376.02 to $1,119.67 |

This weakens the two-year PnL bump as an edge claim. The long window remains
profitable, but the market-null p-value is no longer below `0.05`, the event
bootstrap interval crosses zero, and model probabilities lose badly to market
log loss. The log-loss bootstrap estimates `P(model not better than market) =
1.0`.

## Nested Strategy Sensitivity

A nested walk-forward strategy-selection audit also allowed the
women-included-training model to compete against the existing baseline and
regularized men-only ledgers.

| Objective | Folds | Fights | Bets | Profit | ROI/Staked | Positive Folds | Selected Women-Train Folds | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| profit | 7 | 962 | 237 | $234.50 | 7.1% | 5 / 7 | 2 / 7 | 0.170 | $-345.64 to $822.43 |
| ROI | 7 | 962 | 140 | $95.31 | 8.1% | 4 / 7 | 2 / 7 | 0.155 | $-193.36 to $396.21 |

This is directionally positive but weak after market-null and bootstrap checks.
It does not support replacing the frozen men-only production policy with a
women-included-training variant.

## Artifacts

- `test_results/women_universe_sensitivity/WOMEN_UNIVERSE_LONG_NESTED_AUDIT.md`
- `test_results/women_universe_sensitivity/regularized_men_only_2y_audit/edge_audit.md`
- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2y/no_leakage_backtest.csv`
- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2y/no_leakage_backtest_summary.json`
- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2y_audit/edge_audit.md`
- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2022_2026/no_leakage_backtest_summary.json`
- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2022_2026_audit/edge_audit.md`
- `test_results/women_universe_sensitivity/nested_edge_with_women_train/profit_objective/nested_walk_forward_edge_audit.md`
- `test_results/women_universe_sensitivity/nested_edge_with_women_train/roi_objective/nested_walk_forward_edge_audit.md`
