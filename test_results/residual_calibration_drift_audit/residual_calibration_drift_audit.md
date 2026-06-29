# Residual Calibration Drift Audit

This diagnostic asks why the residual edge decayed recently. It compares
market probabilities against selected-shrinkage, fixed-half, and unshrunk
residual probabilities by period, then checks whether selected-shrinkage
adjustments still align with realized market residuals.

## Input

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`

## Selected-Shrinkage Calibration By Period

| Period | Fights | Actual | Market P | Selected P | Adj | Realized Residual | Policy Gap | Market LL | Selected LL | Delta LL | Market ECE | Selected ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| aggregate | 704 | 49.43% | 49.78% | 51.27% | 1.49% | -0.35% | -1.84% | 0.6009 | 0.5971 | 0.0038 | 3.45% | 2.43% |
| calendar 2024 | 275 | 51.64% | 48.57% | 50.00% | 1.43% | 3.07% | 1.63% | 0.5800 | 0.5702 | 0.0098 | 7.70% | 7.67% |
| calendar 2025 | 285 | 49.47% | 50.75% | 52.52% | 1.77% | -1.28% | -3.05% | 0.6136 | 0.6120 | 0.0016 | 4.63% | 3.80% |
| calendar 2026 | 144 | 45.14% | 50.20% | 51.23% | 1.03% | -5.06% | -6.09% | 0.6156 | 0.6192 | -0.0036 | 8.10% | 10.49% |
| 2025-2026 only | 429 | 48.02% | 50.56% | 52.09% | 1.52% | -2.54% | -4.07% | 0.6143 | 0.6144 | -0.0001 | 4.52% | 5.07% |
| last 365 days | 298 | 45.97% | 50.80% | 52.12% | 1.32% | -4.83% | -6.15% | 0.6127 | 0.6159 | -0.0032 | 7.72% | 7.66% |
| latest fold 5 | 129 | 44.19% | 50.09% | 51.02% | 0.93% | -5.90% | -6.84% | 0.6273 | 0.6320 | -0.0047 | 8.83% | 11.41% |

## Policy Comparison

| Period | Policy | Fights | Delta LL | Delta Brier | Mean Adj | Policy ECE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| aggregate | selected_shrinkage | 704 | 0.0038 | 0.0018 | 1.49% | 2.43% |
| aggregate | fixed_half_residual | 704 | 0.0030 | 0.0014 | 0.81% | 2.62% |
| aggregate | unshrunk_meta | 704 | 0.0030 | 0.0016 | 1.63% | 2.52% |
| calendar 2025 | selected_shrinkage | 285 | 0.0016 | 0.0010 | 1.77% | 3.80% |
| calendar 2025 | fixed_half_residual | 285 | 0.0024 | 0.0011 | 0.97% | 3.08% |
| calendar 2025 | unshrunk_meta | 285 | 0.0018 | 0.0010 | 1.94% | 4.90% |
| calendar 2026 | selected_shrinkage | 144 | -0.0036 | -0.0003 | 1.03% | 10.49% |
| calendar 2026 | fixed_half_residual | 144 | -0.0011 | 0.0002 | 0.69% | 10.37% |
| calendar 2026 | unshrunk_meta | 144 | -0.0077 | -0.0013 | 1.38% | 7.39% |
| last 365 days | selected_shrinkage | 298 | -0.0032 | -0.0009 | 1.32% | 7.66% |
| last 365 days | fixed_half_residual | 298 | -0.0004 | 0.0001 | 0.82% | 8.12% |
| last 365 days | unshrunk_meta | 298 | -0.0050 | -0.0013 | 1.64% | 7.42% |
| latest fold 5 | selected_shrinkage | 129 | -0.0047 | -0.0004 | 0.93% | 11.41% |
| latest fold 5 | fixed_half_residual | 129 | -0.0018 | 0.0002 | 0.62% | 11.39% |
| latest fold 5 | unshrunk_meta | 129 | -0.0093 | -0.0013 | 1.25% | 9.23% |

## Adjustment Direction

| Period | Direction | Fights | Mean Adj | Realized Residual | Directional Hit | Delta LL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| aggregate | meta_down_on_red | 279 | -2.69% | -4.55% | 70.61% | 0.0059 |
| aggregate | meta_up_on_red | 425 | 4.23% | 2.41% | 62.59% | 0.0024 |
| calendar 2024 | meta_down_on_red | 114 | -2.63% | -0.74% | 69.30% | -0.0029 |
| calendar 2024 | meta_up_on_red | 161 | 4.31% | 5.76% | 66.46% | 0.0188 |
| calendar 2025 | meta_down_on_red | 99 | -2.63% | -7.29% | 73.74% | 0.0087 |
| calendar 2025 | meta_up_on_red | 186 | 4.12% | 1.92% | 61.83% | -0.0021 |
| calendar 2026 | meta_down_on_red | 66 | -2.89% | -7.05% | 68.18% | 0.0168 |
| calendar 2026 | meta_up_on_red | 78 | 4.35% | -3.37% | 56.41% | -0.0209 |
| last 365 days | meta_down_on_red | 124 | -2.69% | -7.81% | 70.16% | 0.0112 |
| last 365 days | meta_up_on_red | 174 | 4.18% | -2.71% | 57.47% | -0.0135 |
| latest fold 5 | meta_down_on_red | 61 | -2.89% | -8.36% | 68.85% | 0.0170 |
| latest fold 5 | meta_up_on_red | 68 | 4.37% | -3.70% | 55.88% | -0.0242 |

## In-Sample Residual Coefficient Diagnostic

Each row fits `outcome ~ market_logit + selected_residual_logit_adjustment`
inside the same period. This is diagnostic only, not a validation test.

| Period | Fights | Market Logit Coef | Residual Adjustment Coef | Intercept |
| --- | ---: | ---: | ---: | ---: |
| aggregate | 704 | 0.7690 | 1.7364 | -0.1466 |
| calendar 2024 | 275 | 0.9815 | 1.6160 | 0.0421 |
| calendar 2025 | 285 | 0.6446 | 2.0297 | -0.2290 |
| calendar 2026 | 144 | 0.8222 | 0.8382 | -0.2798 |
| 2025-2026 only | 429 | 0.7367 | 1.4980 | -0.2279 |
| last 365 days | 298 | 0.8903 | 0.8447 | -0.2819 |
| latest fold 5 | 129 | 0.7554 | 0.8780 | -0.3111 |

## Interpretation

- The selected residual adjustment is positive on average in every period, but realized market residuals turn negative in 2026 and the latest fold.
- In 2026, the market already overestimates red-side outcomes on this aligned sample; the residual layer nudges probabilities further upward on average, worsening calibration and log loss.
- The residual adjustment direction is not reliably informative recently: latest-fold upward adjustments have negative realized residuals and negative log-loss contribution.
- This points to residual/model drift rather than a simple staking-threshold problem. Future work should require fresh post-freeze evidence or a genuinely pre-registered drift-aware transform.
