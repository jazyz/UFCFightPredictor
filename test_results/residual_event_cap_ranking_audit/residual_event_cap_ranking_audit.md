# Residual Event-Cap Ranking Audit

This diagnostic checks whether the event-cap ranking rule itself matters.
For each policy, it compares the frozen top-residual-edge cap against
bottom-edge, probability-ranked, market-probability-ranked, and random
same-event selections with the same cap.

## Inputs

- frozen residual-meta fixed bets: `test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv`
- shrinkage fixed-policy bets: `test_results/residual_shrinkage_fixed_pnl_audit/fixed_policy_bets.csv`
- cap per event: `3`
- random iterations: `20000`

## Ranking Results

| Policy | Ranking | Bets | Events | Profit | ROI | Actual - Market | Positive Folds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen_residual_meta | top_edge | 262 | 99 | +19.12u | 7.30% | 7.68% | 4 / 5 |
| frozen_residual_meta | bottom_edge | 262 | 99 | +4.99u | 1.91% | 3.95% | 4 / 5 |
| frozen_residual_meta | top_probability | 262 | 99 | +9.29u | 3.54% | 5.25% | 3 / 5 |
| frozen_residual_meta | top_market_probability | 262 | 99 | +6.58u | 2.51% | 4.46% | 3 / 5 |
| fixed_half_residual | top_edge | 234 | 96 | +15.53u | 6.63% | 7.52% | 4 / 5 |
| fixed_half_residual | bottom_edge | 234 | 96 | +3.30u | 1.41% | 3.56% | 4 / 5 |
| fixed_half_residual | top_probability | 234 | 96 | +9.83u | 4.20% | 5.72% | 4 / 5 |
| fixed_half_residual | top_market_probability | 234 | 96 | +9.79u | 4.18% | 5.71% | 4 / 5 |
| selected_shrinkage | top_edge | 279 | 100 | +17.45u | 6.25% | 7.19% | 4 / 5 |
| selected_shrinkage | bottom_edge | 279 | 100 | -3.53u | -1.27% | 1.91% | 3 / 5 |
| selected_shrinkage | top_probability | 279 | 100 | +11.79u | 4.23% | 5.72% | 4 / 5 |
| selected_shrinkage | top_market_probability | 279 | 100 | +11.39u | 4.08% | 5.68% | 4 / 5 |
| unshrunk_meta | top_edge | 288 | 102 | +17.52u | 6.08% | 7.10% | 4 / 5 |
| unshrunk_meta | bottom_edge | 288 | 102 | -5.05u | -1.75% | 1.73% | 2 / 5 |
| unshrunk_meta | top_probability | 288 | 102 | +13.68u | 4.75% | 6.10% | 4 / 5 |
| unshrunk_meta | top_market_probability | 288 | 102 | +13.19u | 4.58% | 6.04% | 4 / 5 |

## Random Cap Comparison

| Policy | Top Edge Profit | Random Mean | Random 95% Interval | P(random >= top edge) | Top - Random Mean |
| --- | ---: | ---: | --- | ---: | ---: |
| frozen_residual_meta | +19.12u | +6.63u | -2.41u to +15.86u | 0.004 | +12.48u |
| fixed_half_residual | +15.53u | +9.41u | +2.86u to +16.23u | 0.040 | +6.12u |
| selected_shrinkage | +17.45u | +8.44u | -1.64u to +18.68u | 0.042 | +9.01u |
| unshrunk_meta | +17.52u | +7.64u | -2.76u to +18.30u | 0.034 | +9.89u |

## Interpretation

The frozen cap rule is stronger if top residual-edge ranking beats random
same-event caps and bottom-edge caps. If random caps perform similarly,
then the main value is exposure reduction rather than residual ordering.

For the frozen residual-meta ledger, top residual-edge ranking produced
`+19.12u` versus
`+4.99u` for bottom-edge ranking
and a random-cap mean of `+6.63u`.
Only `0.004` of random caps matched or beat the top-edge result.
That supports the ranking rule as more than generic exposure reduction,
though it remains historical evidence rather than post-freeze proof.
