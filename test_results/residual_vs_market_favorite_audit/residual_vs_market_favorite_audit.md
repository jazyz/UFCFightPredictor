# Residual Vs Market Favorite Audit

This diagnostic compares the frozen residual-meta top-edge cap-3 ledger
against market-only favorite benchmarks on the same historical event
dates. It does not retrain the model or change any frozen policy.

## Inputs

- market/source ledger: `test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv`
- residual ranked bets: `test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv`
- residual window: `2024-02-10` to `2026-06-27`
- residual events: `99`
- same-event market favorite rows: `680`
- event-bootstrap iterations: `20000`
- market-null iterations: `20000`
- random favorite iterations: `20000`

## Key Diagnostics

- Residual cap-3 made +19.12u on 262 bets.
- Top market favorites with the same per-event bet counts made +0.07u; paired event-bootstrap P(residual <= top-market) was `0.018`.
- Low-confidence market favorites with the same per-event bet counts made -2.16u; paired event-bootstrap P(residual <= low-confidence) was `0.046`.
- Random same-event favorite selections averaged -2.95u; P(random >= residual) was `0.005`.
- The recent caveat remains: over the last 365 days residual cap-3 made +0.38u, top-market same-count favorites made -2.20u, and low-confidence same-count favorites made +3.29u.

## Benchmark Summary

| Benchmark | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| residual_cap3 | 262 | 99 | +19.12u | 7.30% | 77.86% | 70.19% | 7.68% | 0.015 | 0.001 |
| market_top_same_count | 262 | 99 | +0.07u | 0.03% | 78.63% | 75.29% | 3.34% | 0.494 | 0.113 |
| market_low_conf_same_count | 262 | 99 | -2.16u | -0.83% | 61.07% | 58.65% | 2.41% | 0.570 | 0.354 |
| market_top3_same_events | 297 | 99 | +3.99u | 1.34% | 78.11% | 74.12% | 3.99% | 0.339 | 0.049 |
| market_low_conf3_same_events | 297 | 99 | +2.95u | 0.99% | 62.96% | 59.42% | 3.54% | 0.407 | 0.207 |
| all_market_favorites_same_events | 680 | 99 | -12.77u | -1.88% | 68.38% | 66.68% | 1.70% | 0.777 | 0.257 |
| all_market_favorites_same_period | 704 | 102 | -5.82u | -0.83% | 68.75% | 66.45% | 2.30% | 0.632 | 0.141 |

## Same-Event Paired Bootstrap

| Benchmark | Residual - Benchmark Profit | Bootstrap P(diff <= 0) | 95% Diff CI |
| --- | ---: | ---: | --- |
| market_top_same_count | +19.05u | 0.018 | +1.11u to +37.14u |
| market_low_conf_same_count | +21.28u | 0.046 | -3.26u to +46.19u |
| market_top3_same_events | +15.13u | 0.053 | -3.25u to +33.80u |
| market_low_conf3_same_events | +16.16u | 0.094 | -7.91u to +40.11u |
| all_market_favorites_same_events | +31.89u | 0.007 | +5.87u to +58.16u |
| all_market_favorites_same_period | +24.94u | 0.037 | -2.45u to +52.47u |

## Random Same-Event Favorite Selection

| Metric | Value |
| --- | ---: |
| iterations | 20000 |
| events | 99 |
| mean profit | -2.95u |
| 95% profit interval | -19.91u to +13.66u |
| probability random profit > 0 | 36.41% |
| P(random >= residual) | 0.005 |

## Period Summary

| Period | Benchmark | Bets | Profit | ROI | Actual - Market | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | residual_cap3 | 103 | +14.39u | 13.97% | 12.79% | 0.001 |
| 2025-2026 | residual_cap3 | 159 | +4.73u | 2.97% | 4.36% | 0.072 |
| last_365d | residual_cap3 | 105 | +0.38u | 0.36% | 2.55% | 0.218 |
| 2024 | market_top_same_count | 103 | +5.55u | 5.38% | 7.42% | 0.045 |
| 2025-2026 | market_top_same_count | 159 | -5.47u | -3.44% | 0.70% | 0.431 |
| last_365d | market_top_same_count | 105 | -2.20u | -2.10% | 1.57% | 0.332 |
| 2024 | market_low_conf_same_count | 103 | +8.01u | 7.77% | 7.86% | 0.072 |
| 2025-2026 | market_low_conf_same_count | 159 | -10.17u | -6.40% | -1.12% | 0.737 |
| last_365d | market_low_conf_same_count | 105 | +3.29u | 3.14% | 4.86% | 0.340 |

## Interpretation

- This is a benchmark diagnostic, not a policy change.
- If residual cap-3 cannot beat same-event market-only favorite rules, the model-specific edge claim is weak.
- Here residual cap-3 does beat top-market, low-confidence, all-favorite, and random same-event favorite exposure historically, which supports residual selection as more than generic favorite betting.
- The support is still not a live-edge claim: the low-confidence paired interval crosses zero, and the last-365-day residual result remains only slightly positive.
- Any such narrower hypothesis still needs future paper tracking before live staking escalation.
