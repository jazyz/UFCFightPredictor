# Residual Reliability Audit

This audit tests the residual alpha claim directly. It compares each
candidate probability adjustment (`candidate - market`) against the
realized market residual (`outcome - market`). A slope near `1` means
the adjustment size was calibrated; a slope near `0` means the residual
direction carried little realized market-error information.

## Aggregate Reliability

| Policy | Fights | Mean Adj | Realized Market Residual | Slope Origin | Slope 95% CI | P(slope<=0) | Market-Null p(slope) | Delta LL | Bootstrap P(delta<=0) | Market-Null p(delta) |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| selected_shrinkage | 704 | 1.49% | -0.35% | 1.0089 | 0.2797 to 1.7428 | 0.004 | 0.007 | 0.0038 | 0.141 | 0.013 |
| fixed_half_residual | 704 | 0.81% | -0.35% | 1.7349 | 0.4383 to 3.0442 | 0.005 | 0.008 | 0.0030 | 0.055 | 0.013 |
| unshrunk_meta | 704 | 1.63% | -0.35% | 0.8674 | 0.2104 to 1.5406 | 0.005 | 0.006 | 0.0030 | 0.222 | 0.014 |

## Selected-Shrinkage Period Reliability

| Period | Fights | Mean Adj | Realized Market Residual | Slope Origin | Delta LL | Directional Hit >=2pp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| aggregate | 704 | 1.49% | -0.35% | 1.0089 | 0.0038 | 70.06% |
| calendar 2024 | 275 | 1.43% | 3.07% | 1.5839 | 0.0098 | 73.23% |
| 2025-2026 | 429 | 1.52% | -2.54% | 0.6522 | -0.0001 | 67.99% |
| last 365 days | 298 | 1.32% | -4.83% | 0.2504 | -0.0032 | 64.88% |
| latest fold 5 | 129 | 0.93% | -5.90% | 0.3958 | -0.0047 | 63.74% |

## Selected-Shrinkage Signed Buckets

| Adjustment Bucket | Fights | Mean Adj | Realized Market Residual | Actual - Candidate | Delta LL | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| <= -5% | 34 | -5.77% | -13.25% | -7.48% | 0.0270 | 3 / 4 |
| -5% to -2% | 135 | -3.34% | -5.09% | -1.75% | 0.0037 | 4 / 5 |
| -2% to +2% | 203 | -0.02% | -1.17% | -1.15% | 0.0008 | 3 / 5 |
| +2% to +5% | 152 | 3.71% | -1.60% | -5.30% | -0.0071 | 1 / 5 |
| >= +5% | 180 | 6.31% | 7.61% | 1.30% | 0.0119 | 3 / 5 |

## Interpretation

- Aggregate selected-shrinkage slope is `1.0089`, which looks calibrated in full sample, with Delta LL `0.0038`.
- That aggregate masks drift: selected-shrinkage slope falls to `0.6522` in 2025-2026 and `0.3958` in the latest fold.
- The residual remains a weak historical signal, but recent reliability is not strong enough for a live edge claim.
- A future transform should be judged on forward reliability slope and recent Delta LL, not just aggregate log-loss gain.
