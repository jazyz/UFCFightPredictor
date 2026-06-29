# Residual Market-Band Shrinkage Audit

This audit tests whether the feature-drift clue can become validation
evidence. Candidate transforms shrink the selected residual adjustment
globally, for positive residuals, and for positive residuals inside
favorite-ish market bands. Each evaluation fold selects from the full
candidate family using only prior folds.

## Inputs

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- scale grid: `[0.0, 0.25, 0.5, 0.75, 1.0]`
- candidates, including market and baselines: `38`
- event-bootstrap iterations: `20000`
- market-null iterations: `10000`

## Candidate Notes

- `global_scale_s`: scale every selected residual logit adjustment by `s`.
- `positive_residual_scale_s`: scale only positive logit residual adjustments by `s`.
- `market_60_80_positive_scale_s`: scale positive residuals only when market P is `0.60` to `0.80`.
- `market_ge_60_adj_ge_2pct_scale_s`: scale adjustments of at least `+2pp` when market P is at least `0.60`.
- All conditional candidates keep the original selected residual outside the named condition.

## Fixed Candidate Diagnostics

These rows are diagnostics only; the validation test is the rolling
prior-fold selection below.

| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `market` | 704 | 0.6009 | 0.6009 | 0.0000 | 0.00% | 1.000 |
| `selected_shrinkage` | 704 | 0.6009 | 0.5971 | 0.0038 | 1.49% | 0.143 |
| `fixed_half_residual` | 704 | 0.6009 | 0.5979 | 0.0030 | 0.81% | 0.050 |
| `global_scale_0.5` | 704 | 0.6009 | 0.5978 | 0.0031 | 0.77% | 0.043 |
| `positive_residual_scale_0.5` | 704 | 0.6009 | 0.5970 | 0.0039 | 0.25% | 0.040 |
| `market_60_80_positive_scale_0` | 704 | 0.6009 | 0.5969 | 0.0040 | -0.02% | 0.077 |
| `market_60_80_positive_scale_0.5` | 704 | 0.6009 | 0.5964 | 0.0045 | 0.76% | 0.061 |
| `market_ge_60_adj_ge_2pct_scale_0` | 704 | 0.6009 | 0.5968 | 0.0041 | -0.20% | 0.034 |
| `market_ge_60_adj_ge_2pct_scale_0.5` | 704 | 0.6009 | 0.5963 | 0.0046 | 0.68% | 0.035 |
| `market_ge_60_positive_scale_0.5` | 704 | 0.6009 | 0.5962 | 0.0047 | 0.67% | 0.032 |
| `market_ge_60_positive_scale_0.25` | 704 | 0.6009 | 0.5963 | 0.0046 | 0.23% | 0.023 |
| `market_ge_60_scale_0.5` | 704 | 0.6009 | 0.5963 | 0.0046 | 0.68% | 0.034 |

## Fixed Candidates On Rolling Evaluation Folds

| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `market` | 539 | 0.6022 | 0.6022 | 0.0000 | 0.00% | 1.000 |
| `selected_shrinkage` | 539 | 0.6022 | 0.5994 | 0.0028 | 1.65% | 0.253 |
| `fixed_half_residual` | 539 | 0.6022 | 0.5996 | 0.0025 | 0.91% | 0.134 |
| `global_scale_0.5` | 539 | 0.6022 | 0.5996 | 0.0025 | 0.85% | 0.112 |
| `positive_residual_scale_0.5` | 539 | 0.6022 | 0.5978 | 0.0044 | 0.38% | 0.039 |
| `market_60_80_positive_scale_0` | 539 | 0.6022 | 0.5964 | 0.0058 | 0.23% | 0.042 |
| `market_60_80_positive_scale_0.5` | 539 | 0.6022 | 0.5974 | 0.0048 | 0.96% | 0.079 |
| `market_ge_60_adj_ge_2pct_scale_0` | 539 | 0.6022 | 0.5961 | 0.0061 | 0.01% | 0.005 |
| `market_ge_60_adj_ge_2pct_scale_0.5` | 539 | 0.6022 | 0.5971 | 0.0051 | 0.86% | 0.043 |
| `market_ge_60_positive_scale_0` | 539 | 0.6022 | 0.5960 | 0.0062 | -0.03% | 0.007 |
| `market_ge_60_scale_0` | 539 | 0.6022 | 0.5962 | 0.0059 | 0.00% | 0.007 |
| `market_ge_60_positive_scale_0.25` | 539 | 0.6022 | 0.5963 | 0.0058 | 0.41% | 0.010 |

## Latest-Fold Fixed Candidates

| Candidate | Fights | Delta LL | Mean Adj |
| --- | ---: | ---: | ---: |
| `market` | 129 | 0.0000 | 0.00% |
| `selected_shrinkage` | 129 | -0.0047 | 0.93% |
| `fixed_half_residual` | 129 | -0.0018 | 0.62% |
| `global_scale_0.5` | 129 | -0.0012 | 0.48% |
| `positive_residual_scale_0.5` | 129 | 0.0025 | -0.19% |
| `market_60_80_positive_scale_0` | 129 | 0.0072 | -0.16% |
| `market_60_80_positive_scale_0.5` | 129 | 0.0017 | 0.41% |
| `market_ge_60_adj_ge_2pct_scale_0` | 129 | 0.0086 | -0.31% |
| `market_ge_60_adj_ge_2pct_scale_0.5` | 129 | 0.0025 | 0.34% |
| `market_ge_60_positive_scale_0` | 129 | 0.0088 | -0.36% |
| `positive_adj_ge_2pct_scale_0` | 129 | 0.0086 | -1.24% |
| `market_ge_60_scale_0` | 129 | 0.0085 | -0.23% |

## Rolling Prior-Fold Selection

| Eval Fold | Selected Candidate | Dev Delta LL | Eval Fights | Eval Delta LL | Eval Mean Adj |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `selected_shrinkage` | 0.0070 | 130 | 0.0077 | 2.28% |
| 3 | `selected_shrinkage` | 0.0073 | 150 | 0.0026 | 2.01% |
| 4 | `selected_shrinkage` | 0.0058 | 130 | 0.0053 | 1.30% |
| 5 | `selected_shrinkage` | 0.0057 | 129 | -0.0047 | 0.93% |

| Combined Eval | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected market-band shrinkage | 539 | 0.6022 | 0.5994 | 0.0028 | 1.65% | 0.251 | 0.023 |

## Interpretation

- Rolling selection chose: `selected_shrinkage`.
- This is the relevant validation result because each fold selects using only prior folds.
- A fixed candidate that looks good on the latest fold is still only diagnostic unless rolling selection chose it before that fold.
- Rolling selection did not choose a new market-band transform; it reverted to existing baselines. The market-band shrinkage clue remains diagnostic, not validated.
