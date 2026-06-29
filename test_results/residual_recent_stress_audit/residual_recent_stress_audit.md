# Residual Recent Stress Audit

This audit asks whether the residual probability edge and frozen cap-3
residual paper bets survive recent-only slices, or whether early 2024 is
doing most of the historical work.

## Inputs

- probability predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- capped-bet source: `test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv`
- event-bootstrap iterations: `20000`
- market-null iterations: `20000`

## Probability Stress

| Period | Policy | Fights | Events | Market LL | Candidate LL | Delta LL | Bootstrap P(delta <= 0) | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| aggregate | selected_shrinkage | 704 | 102 | 0.6009 | 0.5971 | 0.0038 | 0.140 | 0.011 |
| aggregate | fixed_half_residual | 704 | 102 | 0.6009 | 0.5979 | 0.0030 | 0.050 | 0.014 |
| aggregate | unshrunk_meta | 704 | 102 | 0.6009 | 0.5979 | 0.0030 | 0.221 | 0.014 |
| calendar 2024 | selected_shrinkage | 275 | 39 | 0.5800 | 0.5702 | 0.0098 | 0.014 | 0.007 |
| calendar 2024 | fixed_half_residual | 275 | 39 | 0.5800 | 0.5741 | 0.0059 | 0.003 | 0.006 |
| calendar 2024 | unshrunk_meta | 275 | 39 | 0.5800 | 0.5702 | 0.0098 | 0.014 | 0.007 |
| calendar 2025 | selected_shrinkage | 285 | 42 | 0.6136 | 0.6120 | 0.0016 | 0.385 | 0.141 |
| calendar 2025 | fixed_half_residual | 285 | 42 | 0.6136 | 0.6113 | 0.0024 | 0.230 | 0.111 |
| calendar 2025 | unshrunk_meta | 285 | 42 | 0.6136 | 0.6118 | 0.0018 | 0.389 | 0.122 |
| calendar 2026 | selected_shrinkage | 144 | 21 | 0.6156 | 0.6192 | -0.0036 | 0.690 | 0.449 |
| calendar 2026 | fixed_half_residual | 144 | 21 | 0.6156 | 0.6167 | -0.0011 | 0.594 | 0.438 |
| calendar 2026 | unshrunk_meta | 144 | 21 | 0.6156 | 0.6232 | -0.0077 | 0.776 | 0.461 |
| 2025-2026 only | selected_shrinkage | 429 | 63 | 0.6143 | 0.6144 | -0.0001 | 0.503 | 0.169 |
| 2025-2026 only | fixed_half_residual | 429 | 63 | 0.6143 | 0.6131 | 0.0012 | 0.320 | 0.158 |
| 2025-2026 only | unshrunk_meta | 429 | 63 | 0.6143 | 0.6157 | -0.0014 | 0.594 | 0.174 |
| last 365 days | selected_shrinkage | 298 | 42 | 0.6127 | 0.6159 | -0.0032 | 0.722 | 0.409 |
| last 365 days | fixed_half_residual | 298 | 42 | 0.6127 | 0.6131 | -0.0004 | 0.544 | 0.339 |
| last 365 days | unshrunk_meta | 298 | 42 | 0.6127 | 0.6177 | -0.0050 | 0.770 | 0.374 |
| latest fold 5 | selected_shrinkage | 129 | 19 | 0.6273 | 0.6320 | -0.0047 | 0.720 | 0.498 |
| latest fold 5 | fixed_half_residual | 129 | 19 | 0.6273 | 0.6291 | -0.0018 | 0.639 | 0.487 |
| latest fold 5 | unshrunk_meta | 129 | 19 | 0.6273 | 0.6366 | -0.0093 | 0.806 | 0.515 |

## Frozen Cap-3 PnL Stress

This uses the frozen residual-meta top-edge cap-3 historical ledger.

| Period | Bets | Events | Profit | ROI | Actual - Market | Bootstrap P(profit <= 0) | Market-Null p | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| aggregate | 262 | 99 | +19.12u | 7.30% | 7.68% | 0.015 | 0.001 | 4 / 5 |
| calendar 2024 | 103 | 39 | +14.39u | 13.97% | 12.79% | <0.001 | 0.002 | 2 / 2 |
| calendar 2025 | 108 | 41 | +5.76u | 5.34% | 6.36% | 0.141 | 0.062 | 2 / 3 |
| calendar 2026 | 51 | 19 | -1.03u | -2.03% | 0.12% | 0.577 | 0.394 | 1 / 2 |
| 2025-2026 only | 159 | 60 | +4.73u | 2.97% | 4.36% | 0.251 | 0.071 | 2 / 4 |
| last 365 days | 105 | 39 | +0.38u | 0.36% | 2.55% | 0.465 | 0.217 | 1 / 3 |
| latest fold 5 | 45 | 17 | -1.78u | -3.94% | -1.49% | 0.647 | 0.486 | 0 / 1 |

## Interpretation

- The aggregate residual probability signal remains positive, but the recent-only slices are materially weaker.
- The frozen cap-3 PnL edge is heavily front-loaded: 2024 is positive, while 2025-2026 and the latest fold are not convincing.
- This does not refute the existence of a weak residual signal, but it argues against a strong live edge claim until post-freeze paper results reverse the recent decay.
- Feature work should focus on explaining or fixing recency drift; simply adding more historical-feature capacity is unlikely to be enough.
