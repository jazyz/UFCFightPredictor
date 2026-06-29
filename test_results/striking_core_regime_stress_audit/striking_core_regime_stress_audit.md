# Striking Core Regime Stress Audit

This audit stress-tests fixed uncapped `2%` striking-core paper ledgers
by fold, time period, price band, edge band, and event concentration.
It does not select a new policy or threshold.

## Protocol

- aligned men-only rows: `1223`
- rolling folds: `7`
- evaluated folds for betting: `2, 3, 4, 5, 6, 7`
- edge threshold: `2.00%`
- event cap: none
- market-null iterations per slice: `20000`

## Summary

| Policy | Bets | Events | Profit | ROI | Actual - Market | Pos Folds | Boot P(profit<=0) | Market-Null p | Events To Erase Profit | Profit After Removing Top 5 Events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_selected_prior_delta` | 526 | 124 | +20.98u | 3.99% | 4.52% | 5 / 6 | 0.088 | 0.006 | 7 | +3.39u |
| `mixed_core|all` | 627 | 126 | +32.48u | 5.18% | 5.19% | 5 / 6 | 0.045 | 0.002 | 9 | +10.23u |
| `sigpct_head|all` | 619 | 126 | +32.78u | 5.29% | 4.94% | 5 / 6 | 0.050 | 0.001 | 9 | +8.35u |
| `mixed_core|min5` | 372 | 123 | +23.10u | 6.21% | 5.67% | 6 / 6 | 0.066 | 0.004 | 7 | +3.93u |
| `sigpct_head|min5` | 363 | 122 | +28.17u | 7.76% | 6.39% | 5 / 6 | 0.033 | 0.001 | 8 | +6.44u |

## Detailed Slices

## `rolling_selected_prior_delta`

Overall:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 526 | 124 | +20.98u | 3.99% | 69.58% | 65.06% | 4.52% | 4.66% | 5 / 6 | 0.088 | 0.006 |

By fold:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fold 2 | 93 | 21 | +1.60u | 1.72% | 66.67% | 63.41% | 3.26% | 5.52% | 1 / 1 | 0.442 | 0.236 |
| fold 3 | 115 | 22 | -0.03u | -0.03% | 66.96% | 64.13% | 2.83% | 5.27% | 0 / 1 | 0.491 | 0.278 |
| fold 4 | 99 | 20 | +2.24u | 2.26% | 74.75% | 69.44% | 5.31% | 3.48% | 1 / 1 | 0.300 | 0.171 |
| fold 5 | 103 | 22 | +6.85u | 6.65% | 70.87% | 66.11% | 4.77% | 4.82% | 1 / 1 | 0.142 | 0.071 |
| fold 6 | 57 | 19 | +2.65u | 4.66% | 70.18% | 66.00% | 4.18% | 3.80% | 1 / 1 | 0.322 | 0.175 |
| fold 7 | 59 | 20 | +7.67u | 13.00% | 67.80% | 59.42% | 8.37% | 4.69% | 1 / 1 | 0.082 | 0.063 |

By period:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-2024 | 307 | 63 | +3.81u | 1.24% | 69.38% | 65.62% | 3.76% | 4.77% | 2 / 3 | 0.379 | 0.102 |
| 2025-2026 | 219 | 61 | +17.17u | 7.84% | 69.86% | 64.28% | 5.59% | 4.52% | 3 / 3 | 0.041 | 0.011 |

By market probability bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50-0.60 | 81 | 62 | +5.10u | 6.30% | 61.73% | 55.76% | 5.97% | 5.02% | 4 / 6 | 0.258 | 0.132 |
| 0.60-0.70 | 178 | 94 | +2.84u | 1.60% | 69.10% | 65.36% | 3.74% | 4.63% | 4 / 6 | 0.359 | 0.130 |
| <0.50 | 69 | 51 | +8.32u | 12.06% | 43.48% | 40.47% | 3.01% | 4.08% | 3 / 6 | 0.229 | 0.126 |
| >=0.70 | 198 | 102 | +4.71u | 2.38% | 82.32% | 77.17% | 5.15% | 4.75% | 5 / 6 | 0.232 | 0.039 |

By edge bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.02-0.035 | 181 | 97 | +7.53u | 4.16% | 65.19% | 62.20% | 3.00% | 2.79% | 4 / 6 | 0.249 | 0.086 |
| 0.035-0.05 | 182 | 95 | +1.14u | 0.62% | 70.88% | 66.85% | 4.03% | 4.24% | 2 / 6 | 0.445 | 0.188 |
| 0.05-0.075 | 115 | 67 | +6.32u | 5.50% | 72.17% | 67.12% | 5.05% | 6.23% | 4 / 6 | 0.202 | 0.072 |
| >=0.075 | 48 | 39 | +5.99u | 12.48% | 75.00% | 64.17% | 10.83% | 9.56% | 2 / 5 | 0.116 | 0.059 |

Event concentration:

- events to erase aggregate profit: `7`

| Remove Top Events | Remaining Events | Remaining Profit |
| ---: | ---: | ---: |
| 1 | 123 | +14.81u |
| 3 | 121 | +8.48u |
| 5 | 119 | +3.39u |
| 10 | 114 | -6.95u |

Top profit events:

| Event Date | Bets | Profit | Mean Edge |
| --- | ---: | ---: | ---: |
| 2023-09-09 | 4 | +6.17u | 4.90% |
| 2025-11-15 | 6 | +3.33u | 3.14% |
| 2026-02-28 | 1 | +3.00u | 5.38% |
| 2025-04-26 | 7 | +2.61u | 5.23% |
| 2025-07-12 | 4 | +2.48u | 2.87% |

## `mixed_core|all`

Overall:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 627 | 126 | +32.48u | 5.18% | 69.06% | 63.87% | 5.19% | 5.04% | 5 / 6 | 0.045 | 0.002 |

By fold:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fold 2 | 92 | 21 | +2.85u | 3.10% | 67.39% | 63.52% | 3.87% | 5.59% | 1 / 1 | 0.387 | 0.191 |
| fold 3 | 118 | 22 | -0.82u | -0.70% | 66.95% | 64.16% | 2.78% | 5.17% | 0 / 1 | 0.537 | 0.311 |
| fold 4 | 99 | 20 | +3.75u | 3.79% | 75.76% | 69.56% | 6.20% | 3.62% | 1 / 1 | 0.197 | 0.113 |
| fold 5 | 103 | 22 | +7.44u | 7.22% | 70.87% | 65.32% | 5.55% | 4.99% | 1 / 1 | 0.108 | 0.064 |
| fold 6 | 106 | 20 | +4.54u | 4.29% | 66.04% | 61.13% | 4.91% | 5.07% | 1 / 1 | 0.333 | 0.145 |
| fold 7 | 109 | 21 | +14.71u | 13.50% | 67.89% | 59.96% | 7.93% | 5.72% | 1 / 1 | 0.036 | 0.018 |

By period:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-2024 | 309 | 63 | +5.78u | 1.87% | 69.90% | 65.70% | 4.20% | 4.80% | 2 / 3 | 0.322 | 0.076 |
| 2025-2026 | 318 | 63 | +26.70u | 8.40% | 68.24% | 62.09% | 6.15% | 5.27% | 3 / 3 | 0.033 | 0.004 |

By market probability bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50-0.60 | 102 | 78 | +10.37u | 10.17% | 63.73% | 55.64% | 8.09% | 5.68% | 4 / 6 | 0.118 | 0.042 |
| 0.60-0.70 | 192 | 108 | -2.60u | -1.36% | 67.19% | 65.36% | 1.83% | 4.82% | 3 / 6 | 0.611 | 0.278 |
| <0.50 | 103 | 60 | +13.79u | 13.39% | 43.69% | 39.28% | 4.41% | 4.73% | 4 / 6 | 0.165 | 0.075 |
| >=0.70 | 230 | 109 | +10.92u | 4.75% | 84.35% | 77.29% | 7.06% | 5.07% | 5 / 6 | 0.061 | 0.003 |

By edge bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.02-0.035 | 187 | 96 | +0.88u | 0.47% | 62.03% | 61.62% | 0.42% | 2.79% | 3 / 6 | 0.484 | 0.217 |
| 0.035-0.05 | 190 | 101 | +20.33u | 10.70% | 74.74% | 65.44% | 9.30% | 4.20% | 5 / 6 | 0.016 | 0.003 |
| 0.05-0.075 | 169 | 91 | -1.13u | -0.67% | 68.05% | 65.24% | 2.81% | 6.14% | 3 / 6 | 0.549 | 0.272 |
| >=0.075 | 81 | 61 | +12.40u | 15.31% | 74.07% | 62.53% | 11.54% | 9.88% | 3 / 5 | 0.036 | 0.013 |

Event concentration:

- events to erase aggregate profit: `9`

| Remove Top Events | Remaining Events | Remaining Profit |
| ---: | ---: | ---: |
| 1 | 125 | +26.30u |
| 3 | 123 | +17.39u |
| 5 | 121 | +10.23u |
| 10 | 116 | -2.92u |

Top profit events:

| Event Date | Bets | Profit | Mean Edge |
| --- | ---: | ---: | ---: |
| 2023-09-09 | 4 | +6.17u | 5.26% |
| 2026-04-04 | 1 | +4.75u | 2.48% |
| 2025-12-06 | 7 | +4.16u | 5.02% |
| 2025-09-13 | 5 | +3.88u | 4.53% |
| 2025-10-18 | 6 | +3.28u | 5.22% |

## `sigpct_head|all`

Overall:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 619 | 126 | +32.78u | 5.29% | 68.98% | 64.05% | 4.94% | 4.91% | 5 / 6 | 0.050 | 0.001 |

By fold:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fold 2 | 89 | 21 | +0.72u | 0.81% | 66.29% | 63.97% | 2.32% | 5.27% | 1 / 1 | 0.492 | 0.272 |
| fold 3 | 115 | 22 | -0.03u | -0.03% | 66.96% | 64.13% | 2.83% | 5.27% | 0 / 1 | 0.499 | 0.279 |
| fold 4 | 99 | 20 | +2.24u | 2.26% | 74.75% | 69.44% | 5.31% | 3.48% | 1 / 1 | 0.304 | 0.172 |
| fold 5 | 103 | 22 | +6.85u | 6.65% | 70.87% | 66.11% | 4.77% | 4.82% | 1 / 1 | 0.143 | 0.072 |
| fold 6 | 106 | 20 | +8.03u | 7.58% | 66.98% | 60.99% | 5.99% | 4.87% | 1 / 1 | 0.240 | 0.073 |
| fold 7 | 107 | 21 | +14.96u | 13.98% | 68.22% | 60.07% | 8.15% | 5.66% | 1 / 1 | 0.034 | 0.016 |

By period:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-2024 | 303 | 63 | +2.93u | 0.97% | 69.31% | 65.82% | 3.49% | 4.68% | 2 / 3 | 0.412 | 0.114 |
| 2025-2026 | 316 | 63 | +29.85u | 9.45% | 68.67% | 62.35% | 6.32% | 5.12% | 3 / 3 | 0.029 | 0.002 |

By market probability bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50-0.60 | 97 | 74 | +8.54u | 8.80% | 62.89% | 55.70% | 7.18% | 5.64% | 3 / 6 | 0.160 | 0.064 |
| 0.60-0.70 | 190 | 107 | -1.83u | -0.96% | 67.37% | 65.33% | 2.03% | 4.68% | 3 / 6 | 0.578 | 0.264 |
| <0.50 | 102 | 60 | +17.56u | 17.21% | 45.10% | 39.57% | 5.53% | 4.51% | 3 / 6 | 0.103 | 0.042 |
| >=0.70 | 230 | 105 | +8.51u | 3.70% | 83.48% | 77.35% | 6.12% | 4.96% | 5 / 6 | 0.117 | 0.009 |

By edge bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.02-0.035 | 194 | 99 | +8.80u | 4.53% | 63.40% | 60.88% | 2.52% | 2.79% | 4 / 6 | 0.239 | 0.076 |
| 0.035-0.05 | 207 | 99 | +0.61u | 0.30% | 69.08% | 66.32% | 2.76% | 4.23% | 2 / 6 | 0.484 | 0.190 |
| 0.05-0.075 | 149 | 84 | +7.25u | 4.86% | 71.14% | 65.46% | 5.68% | 6.19% | 4 / 6 | 0.224 | 0.072 |
| >=0.075 | 69 | 51 | +16.12u | 23.36% | 79.71% | 63.07% | 16.64% | 10.10% | 4 / 5 | 0.003 | <0.001 |

Event concentration:

- events to erase aggregate profit: `9`

| Remove Top Events | Remaining Events | Remaining Profit |
| ---: | ---: | ---: |
| 1 | 125 | +26.06u |
| 3 | 123 | +16.15u |
| 5 | 121 | +8.35u |
| 10 | 116 | -4.86u |

Top profit events:

| Event Date | Bets | Profit | Mean Edge |
| --- | ---: | ---: | ---: |
| 2023-09-09 | 5 | +6.71u | 4.74% |
| 2025-12-06 | 8 | +5.16u | 4.16% |
| 2026-04-04 | 1 | +4.75u | 2.05% |
| 2025-11-22 | 6 | +3.92u | 3.32% |
| 2025-09-13 | 5 | +3.88u | 3.76% |

## `mixed_core|min5`

Overall:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 372 | 123 | +23.10u | 6.21% | 69.62% | 63.95% | 5.67% | 4.76% | 6 / 6 | 0.066 | 0.004 |

By fold:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fold 2 | 55 | 20 | +0.19u | 0.35% | 61.82% | 62.46% | -0.64% | 5.39% | 1 / 1 | 0.500 | 0.340 |
| fold 3 | 73 | 22 | +2.79u | 3.82% | 69.86% | 63.75% | 6.12% | 5.06% | 1 / 1 | 0.322 | 0.182 |
| fold 4 | 62 | 19 | +0.37u | 0.59% | 72.58% | 68.76% | 3.82% | 3.66% | 1 / 1 | 0.455 | 0.293 |
| fold 5 | 63 | 22 | +3.88u | 6.16% | 73.02% | 66.00% | 7.02% | 5.12% | 1 / 1 | 0.233 | 0.129 |
| fold 6 | 60 | 20 | +8.20u | 13.67% | 71.67% | 62.90% | 8.77% | 4.61% | 1 / 1 | 0.129 | 0.038 |
| fold 7 | 59 | 20 | +7.67u | 13.00% | 67.80% | 59.42% | 8.37% | 4.69% | 1 / 1 | 0.085 | 0.065 |

By period:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-2024 | 190 | 61 | +3.35u | 1.76% | 68.42% | 65.01% | 3.41% | 4.70% | 3 / 3 | 0.381 | 0.137 |
| 2025-2026 | 182 | 62 | +19.75u | 10.85% | 70.88% | 62.84% | 8.03% | 4.81% | 3 / 3 | 0.028 | 0.005 |

By market probability bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50-0.60 | 64 | 54 | +4.85u | 7.58% | 62.50% | 55.82% | 6.68% | 4.94% | 5 / 6 | 0.218 | 0.134 |
| 0.60-0.70 | 135 | 85 | -1.70u | -1.26% | 67.41% | 65.49% | 1.92% | 4.67% | 3 / 6 | 0.593 | 0.307 |
| <0.50 | 52 | 39 | +12.29u | 23.63% | 48.08% | 40.27% | 7.81% | 4.40% | 4 / 5 | 0.100 | 0.049 |
| >=0.70 | 121 | 83 | +7.66u | 6.33% | 85.12% | 76.71% | 8.42% | 4.91% | 5 / 6 | 0.067 | 0.012 |

By edge bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.02-0.035 | 119 | 81 | -0.76u | -0.64% | 61.34% | 62.15% | -0.81% | 2.75% | 3 / 6 | 0.539 | 0.312 |
| 0.035-0.05 | 115 | 78 | +8.62u | 7.50% | 73.04% | 64.82% | 8.22% | 4.20% | 4 / 6 | 0.137 | 0.046 |
| 0.05-0.075 | 102 | 69 | +7.46u | 7.31% | 72.55% | 65.33% | 7.22% | 6.13% | 3 / 6 | 0.152 | 0.059 |
| >=0.075 | 36 | 30 | +7.78u | 21.61% | 77.78% | 63.19% | 14.59% | 9.27% | 3 / 5 | 0.039 | 0.021 |

Event concentration:

- events to erase aggregate profit: `7`

| Remove Top Events | Remaining Events | Remaining Profit |
| ---: | ---: | ---: |
| 1 | 122 | +17.83u |
| 3 | 120 | +9.16u |
| 5 | 118 | +3.93u |
| 10 | 113 | -6.81u |

Top profit events:

| Event Date | Bets | Profit | Mean Edge |
| --- | ---: | ---: | ---: |
| 2023-09-09 | 3 | +5.26u | 5.94% |
| 2025-12-06 | 5 | +5.09u | 5.77% |
| 2025-09-13 | 4 | +3.58u | 3.66% |
| 2026-02-28 | 1 | +3.00u | 5.38% |
| 2025-04-26 | 5 | +2.24u | 6.22% |

## `sigpct_head|min5`

Overall:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 363 | 122 | +28.17u | 7.76% | 70.52% | 64.13% | 6.39% | 4.64% | 5 / 6 | 0.033 | 0.001 |

By fold:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fold 2 | 53 | 19 | +1.03u | 1.95% | 64.15% | 63.66% | 0.49% | 4.99% | 1 / 1 | 0.464 | 0.286 |
| fold 3 | 71 | 22 | +1.69u | 2.38% | 69.01% | 63.83% | 5.18% | 5.18% | 1 / 1 | 0.377 | 0.235 |
| fold 4 | 61 | 20 | -0.23u | -0.38% | 72.13% | 69.03% | 3.10% | 3.51% | 0 / 1 | 0.527 | 0.335 |
| fold 5 | 63 | 22 | +3.05u | 4.85% | 73.02% | 66.13% | 6.88% | 4.91% | 1 / 1 | 0.296 | 0.162 |
| fold 6 | 59 | 20 | +14.58u | 24.71% | 76.27% | 62.61% | 13.66% | 4.48% | 1 / 1 | 0.031 | 0.002 |
| fold 7 | 56 | 19 | +8.04u | 14.36% | 67.86% | 58.95% | 8.90% | 4.74% | 1 / 1 | 0.073 | 0.056 |

By period:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-2024 | 185 | 61 | +2.49u | 1.35% | 68.65% | 65.50% | 3.15% | 4.57% | 2 / 3 | 0.410 | 0.158 |
| 2025-2026 | 178 | 61 | +25.68u | 14.43% | 72.47% | 62.71% | 9.76% | 4.71% | 3 / 3 | 0.010 | 0.001 |

By market probability bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50-0.60 | 61 | 53 | +4.44u | 7.27% | 62.30% | 55.86% | 6.43% | 4.96% | 4 / 6 | 0.240 | 0.142 |
| 0.60-0.70 | 131 | 84 | -0.30u | -0.23% | 67.94% | 65.39% | 2.55% | 4.52% | 3 / 6 | 0.511 | 0.249 |
| <0.50 | 50 | 36 | +14.95u | 29.91% | 50.00% | 40.55% | 9.45% | 4.22% | 4 / 5 | 0.057 | 0.024 |
| >=0.70 | 121 | 81 | +9.08u | 7.50% | 85.95% | 76.67% | 9.28% | 4.79% | 6 / 6 | 0.033 | 0.006 |

By edge bin:

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Pos Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.02-0.035 | 124 | 78 | +10.50u | 8.47% | 66.94% | 62.16% | 4.78% | 2.78% | 4 / 6 | 0.118 | 0.038 |
| 0.035-0.05 | 122 | 78 | +1.52u | 1.25% | 68.85% | 65.00% | 3.86% | 4.27% | 3 / 6 | 0.438 | 0.211 |
| 0.05-0.075 | 85 | 57 | +8.21u | 9.66% | 75.29% | 66.70% | 8.59% | 6.18% | 4 / 6 | 0.098 | 0.035 |
| >=0.075 | 32 | 26 | +7.94u | 24.81% | 78.12% | 61.62% | 16.50% | 9.22% | 3 / 5 | 0.035 | 0.020 |

Event concentration:

- events to erase aggregate profit: `8`

| Remove Top Events | Remaining Events | Remaining Profit |
| ---: | ---: | ---: |
| 1 | 121 | +22.08u |
| 3 | 119 | +12.70u |
| 5 | 117 | +6.44u |
| 10 | 112 | -3.67u |

Top profit events:

| Event Date | Bets | Profit | Mean Edge |
| --- | ---: | ---: | ---: |
| 2025-12-06 | 6 | +6.09u | 4.66% |
| 2023-09-09 | 4 | +5.81u | 5.27% |
| 2025-09-13 | 4 | +3.58u | 2.89% |
| 2025-11-22 | 5 | +3.25u | 2.92% |
| 2026-02-28 | 1 | +3.00u | 6.50% |

## Interpretation

- The sigpct/head challenger remains profitable after removing its top five profit events, which is a useful concentration check.
- Its event-bootstrap PnL screen is positive at the aggregate level.
- These are retrospective stress diagnostics. The frozen challenger and mixed-core policies still need future pre-outcome paper settlement before a live edge claim.
