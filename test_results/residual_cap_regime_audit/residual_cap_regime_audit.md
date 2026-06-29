# Residual Cap Regime Audit

This diagnostic decomposes the frozen residual-meta top-edge cap-3
historical paper ledger by market regime. It does not retrain the model,
select new thresholds, or alter any frozen paper policy.

## Inputs

- ranked cap bets: `test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv`
- filter: `probability_policy == frozen_residual_meta` and `ranking_mode == top_edge`
- event-bootstrap iterations: `20000`
- market-null iterations: `20000`

## Aggregate

| Metric | Value |
| --- | ---: |
| bets | 262 |
| events | 99 |
| profit | +19.12u |
| ROI | 7.30% |
| actual - market | 7.68% |
| event-bootstrap P(profit <= 0) | 0.015 |
| market-null p-value | 0.001 |

## Key Diagnostics

- Period stability is weak: 2024 produced +14.39u, while 2025-2026 produced +4.73u with market-null p `0.071` and event-bootstrap P(profit <= 0) `0.252`.
- Residual-edge rank is not monotonic: rank 2 made +14.15u, rank 1 made +4.99u, and rank 3 was -0.02u. This argues against assuming every additional cap-3 slot carries the same edge.
- The strongest price-regime result is lower-confidence favorites: market P `<0.60` made +12.31u overall and +9.13u in 2025-2026, but this is only 21 recent bets and was identified after seeing the ledger.
- More residual edge was not automatically better: `0.03-0.05` edge made +16.63u, while `>=0.08` edge made -0.55u.
- Weight-class behavior is uneven: middle/welter made +15.99u, while light/feather made -6.36u.
- Event concentration is moderate: removing the top 10 events leaves +5.52u, and 15 top events erase the aggregate profit.

## By Period

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 103 | 39 | +14.39u | 13.97% | 82.52% | 69.73% | 12.79% | 4.40% | <0.001 | 0.002 |
| 2025-2026 | 159 | 60 | +4.73u | 2.97% | 74.84% | 70.48% | 4.36% | 4.91% | 0.252 | 0.071 |

## By Event Rank

Rank is the residual-edge order within the event after applying cap `3`.

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 99 | 99 | +4.99u | 5.04% | 74.75% | 68.93% | 5.82% | 5.47% | 0.208 | 0.075 |
| 2 | 92 | 92 | +14.15u | 15.38% | 83.70% | 70.28% | 13.42% | 4.54% | 0.005 | 0.001 |
| 3 | 71 | 71 | -0.02u | -0.03% | 74.65% | 71.82% | 2.83% | 3.87% | 0.498 | 0.293 |

## By Period And Rank

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | rank 1 | 39 | 39 | +5.11u | 13.10% | 82.05% | 69.95% | 12.10% | 4.82% | 0.071 | 0.041 |
| 2024 | rank 2 | 36 | 36 | +8.99u | 24.98% | 88.89% | 69.00% | 19.89% | 4.34% | 0.002 | 0.002 |
| 2024 | rank 3 | 28 | 28 | +0.28u | 1.01% | 75.00% | 70.36% | 4.64% | 3.90% | 0.444 | 0.359 |
| 2025-2026 | rank 1 | 60 | 60 | -0.12u | -0.20% | 70.00% | 68.27% | 1.73% | 5.90% | 0.500 | 0.324 |
| 2025-2026 | rank 2 | 56 | 56 | +5.15u | 9.20% | 80.36% | 71.10% | 9.26% | 4.67% | 0.112 | 0.048 |
| 2025-2026 | rank 3 | 43 | 43 | -0.30u | -0.71% | 74.42% | 72.78% | 1.64% | 3.86% | 0.517 | 0.352 |

## By Market Probability

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| <0.60 | 31 | 29 | +12.31u | 39.71% | 83.87% | 57.46% | 26.41% | 4.82% | <0.001 | 0.001 |
| 0.60-0.70 | 104 | 74 | +3.19u | 3.07% | 70.19% | 65.51% | 4.68% | 4.95% | 0.313 | 0.136 |
| 0.70-0.80 | 92 | 66 | +2.14u | 2.33% | 79.35% | 74.45% | 4.90% | 4.70% | 0.325 | 0.118 |
| >=0.80 | 35 | 30 | +1.48u | 4.21% | 91.43% | 84.14% | 7.29% | 3.91% | 0.210 | 0.127 |

## By Period And Market Probability

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 0.60-0.70 | 45 | 29 | +3.74u | 8.32% | 73.33% | 65.19% | 8.14% | 4.34% | 0.190 | 0.100 |
| 2024 | 0.70-0.80 | 37 | 24 | +5.89u | 15.93% | 89.19% | 74.14% | 15.05% | 4.68% | 0.017 | 0.007 |
| 2024 | <0.60 | 10 | 9 | +3.18u | 31.78% | 80.00% | 58.02% | 21.98% | 4.00% | 0.049 | 0.118 |
| 2024 | >=0.80 | 11 | 9 | +1.57u | 14.30% | 100.00% | 84.13% | 15.87% | 4.06% | <0.001 | 0.147 |
| 2025-2026 | 0.60-0.70 | 59 | 45 | -0.55u | -0.93% | 67.80% | 65.76% | 2.03% | 5.42% | 0.537 | 0.336 |
| 2025-2026 | 0.70-0.80 | 55 | 42 | -3.75u | -6.82% | 72.73% | 74.66% | -1.94% | 4.72% | 0.833 | 0.629 |
| 2025-2026 | <0.60 | 21 | 20 | +9.13u | 43.48% | 85.71% | 57.19% | 28.53% | 5.21% | 0.001 | 0.003 |
| 2025-2026 | >=0.80 | 24 | 21 | -0.10u | -0.41% | 87.50% | 84.14% | 3.36% | 3.84% | 0.509 | 0.371 |

## By Residual Edge

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| <0.03 | 26 | 22 | +0.05u | 0.20% | 76.92% | 74.45% | 2.47% | 2.55% | 0.487 | 0.348 |
| 0.03-0.05 | 137 | 78 | +16.63u | 12.14% | 81.02% | 69.90% | 11.12% | 4.21% | 0.003 | 0.001 |
| 0.05-0.08 | 95 | 58 | +2.99u | 3.15% | 74.74% | 69.71% | 5.03% | 5.84% | 0.305 | 0.127 |
| >=0.08 | 4 | 4 | -0.55u | -13.74% | 50.00% | 63.59% | -13.59% | 9.32% | 0.684 | 0.553 |

## By Model Probability

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| <0.65 | 32 | 30 | +11.28u | 35.25% | 81.25% | 57.62% | 23.63% | 4.68% | <0.001 | 0.002 |
| 0.65-0.70 | 47 | 40 | +9.28u | 19.75% | 78.72% | 63.32% | 15.40% | 4.49% | 0.021 | 0.008 |
| 0.70-0.80 | 114 | 74 | -0.99u | -0.87% | 72.81% | 70.01% | 2.80% | 4.97% | 0.554 | 0.292 |
| >=0.80 | 69 | 56 | -0.45u | -0.66% | 84.06% | 80.99% | 3.07% | 4.46% | 0.537 | 0.293 |

## By Odds Band

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| -150 to -100 | 15 | 15 | +5.51u | 36.74% | 80.00% | 55.99% | 24.01% | 5.59% | 0.017 | 0.020 |
| -250 to -150 | 102 | 74 | +11.39u | 11.16% | 73.53% | 63.86% | 9.67% | 4.65% | 0.048 | 0.013 |
| -400 to -250 | 84 | 64 | +2.31u | 2.75% | 77.38% | 72.01% | 5.37% | 4.98% | 0.322 | 0.140 |
| <= -400 | 61 | 50 | -0.09u | -0.15% | 85.25% | 81.75% | 3.49% | 4.23% | 0.494 | 0.269 |

## By Title Group

| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bantam_or_fly | 56 | 41 | +7.79u | 13.92% | 82.14% | 70.31% | 11.83% | 4.72% | 0.028 | 0.014 |
| catch_or_open | 2 | 2 | +0.89u | 44.72% | 100.00% | 66.39% | 33.61% | 4.17% | <0.001 | 0.440 |
| heavy_or_lhw | 44 | 36 | +0.80u | 1.83% | 77.27% | 71.83% | 5.44% | 4.93% | 0.406 | 0.258 |
| light_or_feather | 81 | 65 | -6.36u | -7.85% | 66.67% | 69.83% | -3.16% | 4.73% | 0.884 | 0.701 |
| middle_or_welter | 79 | 65 | +15.99u | 20.24% | 86.08% | 69.65% | 16.42% | 4.58% | 0.001 | <0.001 |

## Event Concentration

Events to erase aggregate profit: `15`

| Remove Top Events | Remaining Events | Remaining Profit |
| ---: | ---: | ---: |
| 1 | 98 | +17.39u |
| 3 | 96 | +14.50u |
| 5 | 94 | +11.88u |
| 10 | 89 | +5.52u |

### Top Positive Events

| Event Date | Bets | Profit | Mean Edge |
| --- | ---: | ---: | ---: |
| 2026-02-21 | 3 | +1.73u | 6.71% |
| 2025-11-22 | 3 | +1.55u | 4.98% |
| 2026-01-31 | 3 | +1.34u | 5.64% |
| 2024-03-16 | 3 | +1.32u | 4.33% |
| 2024-08-10 | 3 | +1.30u | 5.01% |
| 2025-08-16 | 3 | +1.29u | 4.25% |
| 2025-04-26 | 3 | +1.29u | 4.27% |
| 2024-11-02 | 3 | +1.28u | 4.92% |
| 2024-02-17 | 3 | +1.26u | 4.25% |
| 2024-10-26 | 3 | +1.24u | 5.39% |

## Interpretation

- This is a diagnostic only; it is not permission to tune the frozen cap-3 policy after the fact.
- The aggregate cap-3 result remains directionally interesting, but the regime tables weaken a broad live-edge claim.
- A robust live edge claim would want positive results across recent periods, event ranks, and price bands; this ledger is too uneven for that.
- The lower-confidence favorite pocket is worth watching in forward paper tracking, but should not be carved out as a new live policy from this same historical ledger.
