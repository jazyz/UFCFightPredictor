# Striking Group Rolling Selection Audit

This audit validates the post-hoc grouped striking result with a stricter
prior-fold selection protocol. Fold `2` is used only as prior evidence;
evaluation starts at fold `3`. For each later fold, the selector chooses
the grouped striking variant with the best mean prior fold delta.

## Protocol

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- features: `data/detailed_fights.csv`
- merged rows: `704`
- rolling selection eval folds: `3, 4, 5`
- rolling selection fights: `409`
- grouped variants available: `9`
- logistic L2 C: `0.1`
- bootstrap iterations: `20000`
- market-null iterations: `300`

## Rolling Selected Policies

| Policy | Fights | Market Delta LL | Inc Delta vs Recal | Positive Folds | Boot P(inc<=0) | Null p(market) | Null p(inc) | Latest Inc Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| incremental_delta | 409 | 0.0071 | 0.0079 | 3 / 3 | 0.100 | 0.010 | 0.010 | 0.0175 |
| market_delta | 409 | 0.0071 | 0.0079 | 3 / 3 | 0.103 | 0.010 | 0.010 | 0.0175 |

## Same-Fold References

| Policy | Fights | Market Delta LL | Inc Delta vs Recal | Positive Folds | Boot P(inc<=0) | Null p(market) | Null p(inc) | Latest Inc Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market_recalibrated | 409 | -0.0008 | 0.0000 | 1 / 3 | 1.000 |  |  | 0.0000 |
| selected_shrinkage | 409 | 0.0012 | 0.0020 | 2 / 3 | 0.301 |  |  | -0.0012 |
| fixed_half_residual | 409 | 0.0018 | 0.0025 | 2 / 3 | 0.130 |  |  | 0.0018 |
| fixed_mixed_sig_head_core | 409 | 0.0105 | 0.0113 | 3 / 3 | 0.014 |  |  | 0.0175 |

## Incremental-Objective Selection Path

| Fold | Selected Variant | Prior Score | Eval Market Delta LL | Eval Inc Delta LL | Fights |
| ---: | --- | ---: | ---: | ---: | ---: |
| 3 | `defense_proxy_clues` | 0.0083 | 0.0040 | 0.0052 | 150 |
| 4 | `defense_proxy_clues` | 0.0067 | 0.0038 | 0.0013 | 130 |
| 5 | `mixed_sig_head_core` | 0.0064 | 0.0140 | 0.0175 | 129 |

## Market-Objective Selection Path

| Fold | Selected Variant | Prior Score | Eval Market Delta LL | Eval Inc Delta LL | Fights |
| ---: | --- | ---: | ---: | ---: | ---: |
| 3 | `defense_proxy_clues` | 0.0103 | 0.0040 | 0.0052 | 150 |
| 4 | `defense_proxy_clues` | 0.0069 | 0.0038 | 0.0013 | 130 |
| 5 | `mixed_sig_head_core` | 0.0074 | 0.0140 | 0.0175 | 129 |

## Interpretation

- Best rolling selector: `incremental_delta` with market Delta LL `0.0071` and incremental Delta LL `0.0079`.
- Selector market-null p-values: `0.010` versus raw market and `0.010` versus market recalibration.
- Fixed `mixed_sig_head_core` on the same folds has incremental Delta LL `0.0113`; rolling selection is `-0.0034` relative to fixed mixed.
- Rolling selection clears the unadjusted market-null screen, but the grouped family is still post-hoc and needs a predeclared leak-safe model/backtest.
