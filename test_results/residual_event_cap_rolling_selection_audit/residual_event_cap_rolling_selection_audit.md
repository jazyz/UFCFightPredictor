# Residual Event-Cap Rolling Selection Audit

This audit tests whether capped residual policies would have been selected
using only earlier folds. For each evaluation fold after fold 1, the
selector chooses a cap/policy from prior folds only, then scores the
chosen variant on the next fold.

## Inputs

- capped shrinkage bets: `test_results/residual_event_cap_audit/capped_fixed_policy_bets.csv`
- fixed residual-meta bets: `test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv`
- minimum development bets: `35`
- market-null iterations: `20000`

## Rolling Results

| Family | Objective | Variants | Eval Folds | Bets | Profit | ROI | Positive Folds | Bootstrap P(profit <= 0) | Rolling Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen_residual_meta_caps | profit | 5 | 4 | 170 | +9.52u | 5.60% | 3 / 4 | 0.083 | 0.017 |
| frozen_residual_meta_caps | roi | 5 | 4 | 145 | +11.89u | 8.20% | 3 / 4 | 0.048 | 0.008 |
| selected_shrinkage_caps | profit | 5 | 4 | 210 | +12.15u | 5.79% | 3 / 4 | 0.068 | 0.008 |
| selected_shrinkage_caps | roi | 5 | 4 | 111 | +6.83u | 6.15% | 3 / 4 | 0.132 | 0.042 |
| all_shrinkage_policy_caps | profit | 15 | 4 | 189 | +10.81u | 5.72% | 3 / 4 | 0.090 | 0.011 |
| all_shrinkage_policy_caps | roi | 15 | 4 | 100 | +6.28u | 6.28% | 3 / 4 | 0.150 | 0.047 |

## Fold Selections

| Family | Objective | Eval Fold | Selected Variant | Dev Profit | Dev Bets | Eval Bets | Eval Profit | Eval ROI |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| frozen_residual_meta_caps | profit | 2 | frozen_residual_meta|cap=3 | +7.37u | 67 | 44 | +6.98u | 15.86% |
| frozen_residual_meta_caps | profit | 3 | frozen_residual_meta|cap=3 | +14.34u | 111 | 60 | +3.71u | 6.18% |
| frozen_residual_meta_caps | profit | 4 | frozen_residual_meta|cap=2 | +20.30u | 125 | 33 | +0.83u | 2.53% |
| frozen_residual_meta_caps | profit | 5 | frozen_residual_meta|cap=2 | +21.14u | 158 | 33 | -2.00u | -6.06% |
| frozen_residual_meta_caps | roi | 2 | frozen_residual_meta|cap=2 | +7.24u | 46 | 35 | +6.53u | 18.67% |
| frozen_residual_meta_caps | roi | 3 | frozen_residual_meta|cap=2 | +13.78u | 81 | 44 | +6.53u | 14.83% |
| frozen_residual_meta_caps | roi | 4 | frozen_residual_meta|cap=2 | +20.30u | 125 | 33 | +0.83u | 2.53% |
| frozen_residual_meta_caps | roi | 5 | frozen_residual_meta|cap=2 | +21.14u | 158 | 33 | -2.00u | -6.06% |
| selected_shrinkage_caps | profit | 2 | selected_shrinkage|cap=3 | +5.30u | 69 | 53 | +6.74u | 12.72% |
| selected_shrinkage_caps | profit | 3 | selected_shrinkage|cap=3 | +12.04u | 122 | 64 | +3.74u | 5.84% |
| selected_shrinkage_caps | profit | 4 | selected_shrinkage|cap=3 | +15.77u | 186 | 47 | +3.21u | 6.83% |
| selected_shrinkage_caps | profit | 5 | selected_shrinkage|cap=3 | +18.98u | 233 | 46 | -1.54u | -3.34% |
| selected_shrinkage_caps | roi | 2 | selected_shrinkage|cap=3 | +5.30u | 69 | 53 | +6.74u | 12.72% |
| selected_shrinkage_caps | roi | 3 | selected_shrinkage|cap=1 | +11.83u | 42 | 23 | +0.86u | 3.72% |
| selected_shrinkage_caps | roi | 4 | selected_shrinkage|cap=1 | +12.69u | 65 | 18 | +3.80u | 21.12% |
| selected_shrinkage_caps | roi | 5 | selected_shrinkage|cap=1 | +16.49u | 83 | 17 | -4.57u | -26.87% |
| all_shrinkage_policy_caps | profit | 2 | fixed_half_residual|cap=3 | +6.20u | 59 | 42 | +7.35u | 17.49% |
| all_shrinkage_policy_caps | profit | 3 | fixed_half_residual|cap=3 | +13.55u | 101 | 50 | +1.82u | 3.64% |
| all_shrinkage_policy_caps | profit | 4 | unshrunk_meta|cap=3 | +15.77u | 186 | 51 | +3.18u | 6.24% |
| all_shrinkage_policy_caps | profit | 5 | selected_shrinkage|cap=3 | +18.98u | 233 | 46 | -1.54u | -3.34% |
| all_shrinkage_policy_caps | roi | 2 | fixed_half_residual|cap=3 | +6.20u | 59 | 42 | +7.35u | 17.49% |
| all_shrinkage_policy_caps | roi | 3 | unshrunk_meta|cap=1 | +11.83u | 42 | 23 | +0.86u | 3.72% |
| all_shrinkage_policy_caps | roi | 4 | unshrunk_meta|cap=1 | +12.69u | 65 | 18 | +2.64u | 14.68% |
| all_shrinkage_policy_caps | roi | 5 | selected_shrinkage|cap=1 | +16.49u | 83 | 17 | -4.57u | -26.87% |

## Interpretation

This is a stricter check than the static event-cap audit. It does not ask
whether cap `3` looked best after all outcomes were known; it asks whether
a simple rolling selector using only earlier folds would keep choosing
capped residual variants that work on later folds.

The result should be read alongside the frozen capped paper policy: a
positive rolling result strengthens the case for forward paper tracking,
but it still does not replace genuinely post-freeze evidence.
