# Residual Negative-Control Audit

Prediction variant: `market_plus_regularized_lgbm`
Prediction file: `test_results/market_residual_meta_audit/holdout_meta_predictions.csv`

This audit keeps market probabilities and outcomes fixed, then tests
whether the observed residual adjustment beats deliberately broken
residual adjustments.

## Fixed Controls

| Control | Log Loss | Market - Candidate LL |
| --- | ---: | ---: |
| observed | 0.5979 | 0.0030 |
| market_only | 0.6009 | 0.0000 |
| flipped_residual | 0.6146 | -0.0137 |
| half_residual | 0.5979 | 0.0030 |
| one_and_half_residual | 0.6019 | -0.0010 |

## Permutation Controls

`p-value` is the probability that a scrambled residual adjustment beats
or matches the observed residual log-loss improvement.

| Control | Null Mean Delta LL | Null 95% Interval | P-value | Prob Null Positive |
| --- | ---: | --- | ---: | ---: |
| global residual permutation | -0.0057 | -0.0131 to 0.0017 | 0.012 | 0.067 |
| within-fold residual permutation | -0.0056 | -0.0130 to 0.0018 | 0.010 | 0.069 |
| within-year residual permutation | -0.0058 | -0.0133 to 0.0015 | 0.010 | 0.060 |

## Year Scores

| Year | Fights | Market LL | Meta LL | Delta LL |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 275 | 0.5800 | 0.5702 | 0.0098 |
| 2025 | 285 | 0.6136 | 0.6118 | 0.0018 |
| 2026 | 144 | 0.6156 | 0.6232 | -0.0077 |

## Interpretation

A healthy residual signal should beat sign-flipped and permuted
residual controls. This audit is still conditional on the saved
residual predictions; it does not replace future post-freeze evidence.
