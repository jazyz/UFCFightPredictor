# Residual Negative-Control Audit Summary

Run date: 2026-06-28.

## Purpose

This audit tests whether the residual market/meta probability improvement
survives deliberately broken residual controls. It uses the saved holdout
predictions from:

```text
test_results/market_residual_meta_audit/holdout_meta_predictions.csv
```

Variant tested:

```text
market_plus_regularized_lgbm
```

## Fixed Controls

| Control | Log Loss | Market - Candidate LL |
| --- | ---: | ---: |
| observed residual | 0.5979 | +0.0030 |
| market only | 0.6009 | 0.0000 |
| flipped residual | 0.6146 | -0.0137 |
| half residual | 0.5979 | +0.0030 |
| 1.5x residual | 0.6019 | -0.0010 |

Flipping the residual makes performance much worse than market, which is a
useful negative control. Increasing the residual magnitude to `1.5x` also
loses to market. A half-strength residual is slightly better than the observed
residual (`+0.003026` versus `+0.002993` Delta LL), suggesting the saved
residual transform may still be a little too aggressive.

## Permutation Controls

The permutation controls keep market probabilities and outcomes fixed, but
shuffle residual adjustments.

| Control | Null Mean Delta LL | Null 95% Interval | P-value | Prob Null Positive |
| --- | ---: | --- | ---: | ---: |
| global residual permutation | -0.0057 | -0.0131 to +0.0017 | 0.012 | 0.067 |
| within-fold residual permutation | -0.0056 | -0.0130 to +0.0018 | 0.010 | 0.069 |
| within-year residual permutation | -0.0058 | -0.0133 to +0.0015 | 0.010 | 0.060 |

The observed residual improvement beats the shuffled-residual controls. This
supports the idea that the model residual is aligned with outcomes after
controlling for market price.

## Temporal Caveat

The same audit still shows temporal weakness:

| Year | Fights | Delta LL |
| --- | ---: | ---: |
| 2024 | 275 | +0.0098 |
| 2025 | 285 | +0.0018 |
| 2026 | 144 | -0.0077 |

## Interpretation

This is one of the cleaner pieces of evidence that the residual probability
signal is not just arbitrary noise: aligned residuals beat sign-flipped and
permuted residuals. It still does not prove a live edge. The 2026 slice is
negative, monetized PnL remains weak, and the half-strength control hints that
the transform may need future predeclared shrinkage if post-freeze evidence
supports it.
