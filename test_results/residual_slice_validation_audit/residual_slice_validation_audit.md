# Residual Slice Validation Audit

This audit checks whether residual edge slices selected from earlier
outcomes survive later periods. It is meant to guard against using
full-sample slice tables as after-the-fact strategy tuning.

## Inputs

- probability predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- capped-bet ledger: `test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv`
- probability policy: `selected_shrinkage`
- bet policy: `frozen_residual_meta_top_edge_cap3`
- probability candidate slices: `20`
- betting candidate slices: `18`
- market-null iterations: `10000`

## Key Diagnostics

- The 2024-selected probability slice did not validate: `market_bin=market_0.70_0.80` had 2024 delta LL `0.0580` but 2025-2026 delta LL `-0.0135` and market-null p `0.788`.
- Rolling prior-fold probability selection was positive but thin: combined delta LL `0.0095` on `89` fights, market-null p `0.067`, latest-fold delta `-0.0458`.
- The 2024-selected capped-bet slice was simply `all=all`, with 2025-2026 profit `+4.73u` but last-365-day profit `+0.38u`.
- Rolling prior-fold capped-bet selection chose `all=all` and made `+11.75u` with market-null p `0.003`, but the latest fold was `-1.78u`.

## 2024-Selected Probability Slice

The selector chooses the candidate slice with the best 2024 mean
market-minus-candidate log-loss delta, then evaluates it later.

Selected slice: `market_bin=market_0.70_0.80`
Market-null p-value on 2025-2026 evaluation: `0.788`

| Period | Fights | Market LL | Candidate LL | Delta LL |
| --- | ---: | ---: | ---: | ---: |
| 2024 development | 33 | 0.3714 | 0.3134 | 0.0580 |
| 2025-2026 evaluation | 50 | 0.5672 | 0.5806 | -0.0135 |
| last 365d evaluation | 37 | 0.5831 | 0.6054 | -0.0223 |
| full same slice | 83 | 0.4893 | 0.4744 | 0.0150 |

Top 2024 probability candidates:

| Rank | Candidate | Dev Fights | Dev Delta LL |
| ---: | --- | ---: | ---: |
| 1 | `market_bin=market_0.70_0.80` | 33 | 0.0580 |
| 2 | `abs_edge_bin=abs_edge_0.05_0.08` | 89 | 0.0423 |
| 3 | `title_group=middle_or_welter` | 85 | 0.0294 |
| 4 | `edge_direction=meta_up_on_red` | 161 | 0.0188 |
| 5 | `market_bin=market_0.50_0.60` | 35 | 0.0123 |
| 6 | `market_bin=market_0.60_0.70` | 50 | 0.0099 |
| 7 | `all=all` | 275 | 0.0098 |
| 8 | `title_group=bantam_or_fly` | 59 | 0.0068 |

## Rolling Prior-Fold Probability Selection

Market-null p-value: `0.067`

| Eval Fold | Selected Slice | Dev Fights | Eval Fights | Dev Delta LL | Eval Delta LL |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `abs_edge_bin=abs_edge_0.05_0.08` | 56 | 41 | 0.0365 | 0.0406 |
| 3 | `market_bin=market_0.70_0.80` | 35 | 15 | 0.0590 | -0.0066 |
| 4 | `market_bin=market_0.70_0.80` | 50 | 16 | 0.0393 | 0.0035 |
| 5 | `market_bin=market_0.70_0.80` | 66 | 17 | 0.0306 | -0.0458 |

| Combined Rolling Eval | Fights | Market LL | Candidate LL | Delta LL |
| --- | ---: | ---: | ---: | ---: |
| selected slices | 89 | 0.5352 | 0.5257 | 0.0095 |

## 2024-Selected Capped-Bet Slice

The selector chooses the candidate slice with the best 2024 flat profit,
then evaluates it later.

Selected slice: `all=all`
Market-null p-value on 2025-2026 evaluation: `0.049`

| Period | Bets | Profit | ROI | Actual - Market |
| --- | ---: | ---: | ---: | ---: |
| 2024 development | 103 | +14.39u | 13.97% | 12.79% |
| 2025-2026 evaluation | 159 | +4.73u | 2.97% | 4.36% |
| last 365d evaluation | 105 | +0.38u | 0.36% | 2.55% |
| full same slice | 262 | +19.12u | 7.30% | 7.68% |

Top 2024 betting candidates:

| Rank | Candidate | Dev Bets | Dev Profit |
| ---: | --- | ---: | ---: |
| 1 | `all=all` | 103 | +14.39u |
| 2 | `title_group=middle_or_welter` | 31 | +10.47u |
| 3 | `edge_bin=edge_0.03_0.05` | 70 | +10.22u |
| 4 | `market_bin=market_0.70_0.80` | 37 | +5.89u |
| 5 | `probability_bin=prob_0.70_0.80` | 45 | +5.52u |
| 6 | `edge_bin=edge_0.05_0.08` | 27 | +5.14u |
| 7 | `probability_bin=prob_0.65_0.70` | 24 | +4.76u |
| 8 | `market_bin=market_0.60_0.70` | 45 | +3.74u |

## Rolling Prior-Fold Capped-Bet Selection

Market-null p-value: `0.003`

| Eval Fold | Selected Slice | Dev Bets | Eval Bets | Dev Profit | Eval Profit |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `all=all` | 67 | 44 | +7.37u | +6.98u |
| 3 | `all=all` | 111 | 60 | +14.34u | +3.71u |
| 4 | `all=all` | 171 | 46 | +18.05u | +2.84u |
| 5 | `all=all` | 217 | 45 | +20.89u | -1.78u |

| Combined Rolling Eval | Bets | Profit | ROI | Actual - Market |
| --- | ---: | ---: | ---: | ---: |
| selected slices | 195 | +11.75u | 6.03% | 6.56% |

## Interpretation

- Prior-period slice selection does not create a strong live-edge claim.
- Any positive selected-slice result here is still historical and has only a few evaluation folds.
- Treat this as a guardrail against full-sample slice tuning: useful for deciding what to paper-track, not evidence for staking up.
