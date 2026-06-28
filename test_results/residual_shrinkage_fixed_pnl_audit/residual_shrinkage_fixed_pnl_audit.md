# Residual Shrinkage Fixed PnL Audit

This audit applies the already frozen residual-meta paper thresholds to
the out-of-sample residual-shrinkage probabilities. It does not select
new thresholds from these holdout outcomes.

## Inputs

- shrinkage predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- odds ledger: `test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv`
- fights matched: `704`

## Fixed Betting Rule

| Rule | Value |
| --- | ---: |
| minimum residual edge | 2.00% |
| minimum probability | 60.00% |
| max underdog odds | +300 |
| stake | 1u flat |

## Results

| Probability Policy | Bets | Profit | ROI | Actual - Market | Positive Folds | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected_shrinkage | 399 | +4.55u | 1.14% | 3.65% | 3 / 5 | 0.354 | 0.046 |
| fixed_half_residual | 288 | +8.39u | 2.91% | 4.78% | 3 / 5 | 0.197 | 0.024 |
| unshrunk_meta | 418 | +3.40u | 0.81% | 3.50% | 3 / 5 | 0.389 | 0.049 |

## Fold Results

| Policy | Fold | Bets | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| selected_shrinkage | 1 | 109 | +3.64u | 3.34% |
| selected_shrinkage | 2 | 72 | +5.96u | 8.28% |
| selected_shrinkage | 3 | 98 | -5.06u | -5.16% |
| selected_shrinkage | 4 | 60 | +4.29u | 7.16% |
| selected_shrinkage | 5 | 60 | -4.28u | -7.14% |
| fixed_half_residual | 1 | 80 | +4.71u | 5.89% |
| fixed_half_residual | 2 | 48 | +6.70u | 13.97% |
| fixed_half_residual | 3 | 67 | -3.46u | -5.16% |
| fixed_half_residual | 4 | 44 | +2.74u | 6.22% |
| fixed_half_residual | 5 | 49 | -2.30u | -4.70% |
| unshrunk_meta | 1 | 109 | +3.64u | 3.34% |
| unshrunk_meta | 2 | 72 | +5.96u | 8.28% |
| unshrunk_meta | 3 | 98 | -5.06u | -5.16% |
| unshrunk_meta | 4 | 71 | +2.35u | 3.31% |
| unshrunk_meta | 5 | 68 | -3.49u | -5.14% |

## Interpretation

This is a fixed-threshold translation test. It can show whether the
probability improvement survives the existing paper-bet rule, but it
does not replace future paper tracking.

Selected-shrinkage profit: `+4.55u`.
Unshrunk residual-meta profit: `+3.40u`.
