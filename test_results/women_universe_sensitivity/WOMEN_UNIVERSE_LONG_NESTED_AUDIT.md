# Women Universe Long Nested Audit

Date documented: 2026-06-28

## Question

The 2024-06-27 to 2026-06-27 sensitivity showed better men-only PnL when the
regularized model was trained on a women-included feature table. This follow-up
tests whether that survives longer history and nested model/strategy selection.

## Long Leak-Safe Ledger

All rows below evaluate men's fights only. The women-included variant trains on
all prior processed fights in
`test_results/womens_retrain/detailed_fights_womens_included.csv`, while the
current production regularized ledger uses `data/detailed_fights.csv`.

| Ledger | Fights | Accuracy | Model LL | Full-Window PnL | Conditional Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline default | 1249 | 62.53% | 0.6447 | +25.07% | n/a | n/a |
| regularized men-only | 1249 | 63.65% | 0.6396 | +29.61% | n/a | n/a |
| regularized women-train / men-eval | 1249 | 64.53% | 0.6412 | +36.41% | 0.057 | -$376.02 to $1,119.67 |

For the women-included-training long ledger, de-vigged market log loss was
`0.6006`, far better than the model's `0.6412`. Event bootstrap gave
`P(model not better than market on log loss) = 1.000`.

## Nested Selection With Women-Training Candidate

The nested audit added `regularized_women_train_men_eval` as a third candidate
beside `baseline_default` and `regularized_lgbm`. Each fold selected model and
strategy on the previous 365 days, then evaluated the next 182-day holdout.

| Objective | Folds | Bets | Profit | ROI/Staked | Positive Folds | Women Candidate Selected | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| profit | 7 | 237 | $234.50 | 7.12% | 5 / 7 | 2 / 7 | 0.170 | -$345.64 to $822.43 |
| ROI | 7 | 140 | $95.31 | 8.10% | 4 / 7 | 2 / 7 | 0.155 | -$193.36 to $396.21 |

Compared with the previous two-candidate nested audit:

- Profit objective improved raw profit from `$170.39` to `$234.50`, but the
  conditional market-null p-value remained weak (`0.199` before, `0.170` now).
- ROI objective weakened materially: previous raw profit was `$115.09` with
  market-null p-value `0.048`; adding the women-training candidate produced
  `$95.31` with p-value `0.155`.

## Interpretation

The women-included-training variant is useful as a counterfactual, but it does
not strengthen the real-edge claim. It improves some raw PnL ledgers, yet it
still loses badly to market probabilities on log loss, is selected in only
`2/7` nested folds, and does not produce a convincing nested market-null result.

Practical read: do not change the frozen production policy or staking posture
based on this. At most, treat women-included training as a future hypothesis
that would need a new predeclared paper-tracking freeze before it can count as
fresh evidence.

## Artifacts

- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2022_2026/no_leakage_backtest.csv`
- `test_results/women_universe_sensitivity/regularized_train_all_eval_men_2022_2026_audit/edge_audit.md`
- `test_results/women_universe_sensitivity/nested_edge_with_women_train/profit_objective/nested_walk_forward_edge_audit.md`
- `test_results/women_universe_sensitivity/nested_edge_with_women_train/profit_objective/selected_holdouts_audit/edge_audit.md`
- `test_results/women_universe_sensitivity/nested_edge_with_women_train/roi_objective/nested_walk_forward_edge_audit.md`
- `test_results/women_universe_sensitivity/nested_edge_with_women_train/roi_objective/selected_holdouts_audit/edge_audit.md`
