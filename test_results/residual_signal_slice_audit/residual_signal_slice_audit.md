# Residual Signal Slice Audit

Prediction variant: `market_plus_regularized_lgbm`
Prediction file: `test_results/market_residual_meta_audit/holdout_meta_predictions.csv`
Bet file: `test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv`

## Prediction Signal

| Metric | Value |
| --- | ---: |
| fights | 704 |
| market log loss | 0.6009 |
| meta log loss | 0.5979 |
| market - meta log loss | 0.0030 |

### By Market Probability

| Slice | Fights | Market LL | Meta LL | Delta LL | Actual | Market P | Meta P |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| <0.40 | 250 | 0.5600 | 0.5576 | 0.0024 | 25.20% | 28.63% | 26.55% |
| 0.40-0.50 | 102 | 0.6896 | 0.6904 | -0.0008 | 44.12% | 44.88% | 45.77% |
| 0.50-0.60 | 105 | 0.6763 | 0.6499 | 0.0264 | 58.10% | 55.39% | 58.04% |
| 0.60-0.70 | 131 | 0.6653 | 0.6795 | -0.0143 | 63.36% | 65.11% | 70.17% |
| 0.70-0.80 | 83 | 0.4893 | 0.4792 | 0.0101 | 81.93% | 74.57% | 80.24% |
| >=0.80 | 33 | 0.4212 | 0.4260 | -0.0048 | 84.85% | 84.21% | 89.13% |

### By Absolute Residual Edge

| Slice | Fights | Market LL | Meta LL | Delta LL | Actual | Market P | Meta P |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| <0.01 | 96 | 0.6647 | 0.6655 | -0.0008 | 43.75% | 42.04% | 41.93% |
| 0.01-0.02 | 77 | 0.6333 | 0.6306 | 0.0027 | 33.77% | 41.25% | 41.17% |
| 0.02-0.03 | 91 | 0.5798 | 0.5754 | 0.0043 | 40.66% | 44.80% | 44.67% |
| 0.03-0.05 | 183 | 0.6414 | 0.6543 | -0.0129 | 43.72% | 45.52% | 45.72% |
| 0.05-0.08 | 219 | 0.5206 | 0.4972 | 0.0234 | 66.21% | 60.50% | 64.62% |
| >=0.08 | 38 | 0.6923 | 0.7233 | -0.0310 | 47.37% | 57.36% | 63.53% |

### By Year

| Slice | Fights | Market LL | Meta LL | Delta LL | Actual | Market P | Meta P |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 275 | 0.5800 | 0.5702 | 0.0098 | 51.64% | 48.57% | 50.00% |
| 2025 | 285 | 0.6136 | 0.6118 | 0.0018 | 49.47% | 50.75% | 52.69% |
| 2026 | 144 | 0.6156 | 0.6232 | -0.0077 | 45.14% | 50.20% | 51.57% |

### By Title Group

| Slice | Fights | Market LL | Meta LL | Delta LL | Actual | Market P | Meta P |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bantam_or_fly | 159 | 0.5945 | 0.5928 | 0.0017 | 47.17% | 48.85% | 50.30% |
| catch_or_open | 8 | 0.5804 | 0.5505 | 0.0299 | 50.00% | 43.81% | 43.92% |
| heavy_or_lhw | 106 | 0.6153 | 0.6146 | 0.0007 | 55.66% | 50.54% | 52.41% |
| light_or_feather | 216 | 0.6246 | 0.6276 | -0.0031 | 46.76% | 50.99% | 53.02% |
| middle_or_welter | 215 | 0.5755 | 0.5653 | 0.0102 | 50.70% | 49.11% | 50.40% |

## Fixed Paper-Policy Bets

| Metric | Value |
| --- | ---: |
| bets | 354 |
| profit | +2.44u |
| ROI | 0.69% |
| actual - market | 3.19% |

### Bets By Market Probability

| Slice | Bets | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50-0.60 | 42 | +7.93u | 18.87% | 71.43% | 57.62% | 13.81% | 4.50% |
| 0.60-0.70 | 135 | -6.91u | -5.12% | 64.44% | 65.33% | -0.88% | 4.57% |
| 0.70-0.80 | 122 | +4.10u | 3.36% | 80.33% | 74.58% | 5.75% | 4.37% |
| >=0.80 | 55 | -2.68u | -4.87% | 83.64% | 84.26% | -0.63% | 3.66% |

### Bets By Residual Edge

| Slice | Bets | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.02-0.03 | 66 | -5.73u | -8.68% | 69.70% | 72.51% | -2.81% | 2.49% |
| 0.03-0.05 | 185 | +7.05u | 3.81% | 75.68% | 70.47% | 5.21% | 4.12% |
| 0.05-0.08 | 99 | +1.67u | 1.69% | 73.74% | 69.65% | 4.09% | 5.81% |
| >=0.08 | 4 | -0.55u | -13.74% | 50.00% | 63.59% | -13.59% | 9.32% |

### Bets By Odds Side

| Slice | Bets | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| favorite | 354 | +2.44u | 0.69% | 73.73% | 70.54% | 3.19% | 4.35% |

### Bets By Year

| Slice | Bets | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 144 | +11.60u | 8.06% | 78.47% | 70.05% | 8.43% | 4.09% |
| 2025 | 143 | -4.64u | -3.25% | 70.63% | 70.08% | 0.55% | 4.38% |
| 2026 | 67 | -4.52u | -6.74% | 70.15% | 72.61% | -2.46% | 4.84% |

## Interpretation

This audit is diagnostic only. It identifies where the residual signal
has historically appeared, and where the fixed paper policy was fragile.
It should not be used to tune the frozen paper policy after the fact.
