# Residual Event-Cap Audit

This diagnostic applies simple per-event bet caps to the fixed residual
paper-policy bets. Within each event, bets are ranked by residual edge;
cap `1` keeps only the highest-edge bet on each card, cap `all` keeps the
original fixed-policy bet set.

This is exploratory because the caps are inspected after the historical
fixed-policy ledger exists. Treat this as a future-paper-policy clue, not
a live staking upgrade.

## Inputs

- fixed-policy bets: `test_results/residual_shrinkage_fixed_pnl_audit/fixed_policy_bets.csv`
- source rows: `1105`
- iterations: `20000`

## Results

| Policy | Cap/Event | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Bootstrap P(profit <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_half_residual | 1 | 96 | 96 | +11.02u | 11.48% | 10.83% | 4 / 5 | 0.030 | 0.006 |
| fixed_half_residual | 2 | 181 | 96 | +10.39u | 5.74% | 6.69% | 4 / 5 | 0.095 | 0.017 |
| fixed_half_residual | 3 | 234 | 96 | +15.53u | 6.63% | 7.52% | 4 / 5 | 0.029 | 0.003 |
| fixed_half_residual | 5 | 280 | 96 | +11.13u | 3.98% | 5.62% | 3 / 5 | 0.132 | 0.012 |
| fixed_half_residual | all | 288 | 96 | +8.39u | 2.91% | 4.78% | 3 / 5 | 0.196 | 0.026 |
| selected_shrinkage | 1 | 100 | 100 | +11.92u | 11.92% | 10.78% | 4 / 5 | 0.021 | 0.006 |
| selected_shrinkage | 2 | 196 | 100 | +15.75u | 8.04% | 8.14% | 4 / 5 | 0.026 | 0.003 |
| selected_shrinkage | 3 | 279 | 100 | +17.45u | 6.25% | 7.19% | 4 / 5 | 0.022 | 0.003 |
| selected_shrinkage | 5 | 374 | 100 | +8.32u | 2.22% | 4.47% | 3 / 5 | 0.238 | 0.026 |
| selected_shrinkage | all | 399 | 100 | +4.55u | 1.14% | 3.65% | 3 / 5 | 0.350 | 0.044 |
| unshrunk_meta | 1 | 102 | 102 | +12.44u | 12.20% | 10.80% | 4 / 5 | 0.021 | 0.005 |
| unshrunk_meta | 2 | 201 | 102 | +13.40u | 6.67% | 7.25% | 4 / 5 | 0.054 | 0.006 |
| unshrunk_meta | 3 | 288 | 102 | +17.52u | 6.08% | 7.10% | 4 / 5 | 0.028 | 0.002 |
| unshrunk_meta | 5 | 390 | 102 | +7.37u | 1.89% | 4.32% | 3 / 5 | 0.269 | 0.029 |
| unshrunk_meta | all | 418 | 102 | +3.40u | 0.81% | 3.50% | 3 / 5 | 0.382 | 0.049 |

## Best Historical Cap Per Policy

| Policy | Cap/Event | Bets | Profit | ROI | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: |
| fixed_half_residual | 3 | 234 | +15.53u | 6.63% | 0.003 |
| selected_shrinkage | 3 | 279 | +17.45u | 6.25% | 0.003 |
| unshrunk_meta | 3 | 288 | +17.52u | 6.08% | 0.002 |

## Selection-Adjusted Market Null

| Metric | Value |
| --- | ---: |
| variants inspected | 15 |
| observed best variant | `unshrunk_meta|cap=3` |
| observed best profit | +17.52u |
| null best mean profit | -1.15u |
| null best 95% interval | -14.89u to +14.08u |
| selection-adjusted p-value | 0.011 |

## Fold Results For Selected Shrinkage

| Cap/Event | Fold | Bets | Events | Profit | ROI |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 23 | 23 | +6.30u | 27.39% |
| 1 | 2 | 19 | 19 | +5.53u | 29.13% |
| 1 | 3 | 23 | 23 | +0.86u | 3.72% |
| 1 | 4 | 18 | 18 | +3.80u | 21.12% |
| 1 | 5 | 17 | 17 | -4.57u | -26.87% |
| 2 | 1 | 46 | 23 | +2.77u | 6.02% |
| 2 | 2 | 38 | 19 | +5.95u | 15.65% |
| 2 | 3 | 45 | 23 | +4.82u | 10.71% |
| 2 | 4 | 34 | 18 | +4.22u | 12.40% |
| 2 | 5 | 33 | 17 | -2.00u | -6.06% |
| 3 | 1 | 69 | 23 | +5.30u | 7.68% |
| 3 | 2 | 53 | 19 | +6.74u | 12.72% |
| 3 | 3 | 64 | 23 | +3.74u | 5.84% |
| 3 | 4 | 47 | 18 | +3.21u | 6.83% |
| 3 | 5 | 46 | 17 | -1.54u | -3.34% |
| 5 | 1 | 101 | 23 | +2.98u | 2.95% |
| 5 | 2 | 68 | 19 | +5.86u | 8.62% |
| 5 | 3 | 90 | 23 | -0.78u | -0.87% |
| 5 | 4 | 58 | 18 | +3.74u | 6.44% |
| 5 | 5 | 57 | 17 | -3.48u | -6.11% |
| all | 1 | 109 | 23 | +3.64u | 3.34% |
| all | 2 | 72 | 19 | +5.96u | 8.28% |
| all | 3 | 98 | 23 | -5.06u | -5.16% |
| all | 4 | 60 | 18 | +4.29u | 7.16% |
| all | 5 | 60 | 17 | -4.28u | -7.14% |

## Interpretation

Per-event caps improve the historical fixed-policy PnL because the lower
ranked same-card bets were dilutive. For selected shrinkage, the all-bets
rule made `+4.55u`; caps of `1`, `2`, and `3` produced `+11.92u`,
`+15.75u`, and `+17.45u` respectively.

This should not be promoted as a live edge claim because the cap family was
inspected after seeing the historical residual ledger. The family-level
selection-null is encouraging, but it still uses the same historical
ledger for discovery. The useful next step is to freeze one simple capped
variant for forward paper tracking, then judge future cards under the
same market-null and event-bootstrap tests.
