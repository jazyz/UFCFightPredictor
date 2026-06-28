# Frozen Residual Event-Cap Paper Policy

As-of date: `2026-06-28`
Frozen transform: `test_results/frozen_market_residual_meta/frozen_market_residual_meta.json`
Exploratory cap audit: `test_results/residual_event_cap_audit/residual_event_cap_audit.json`
Historical fixed-policy bet ledger: `test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv`

This is a paper-tracking contract only. It is not a live staking
recommendation. The event cap was chosen after historical diagnostics,
so future outcomes must be tracked unchanged before making an edge claim.

## Probability Transform

- base residual model: `regularized_lgbm`
- transform training window: `2024-06-28` to `2026-06-27`
- logistic C: `0.25`

| Term | Value |
| --- | ---: |
| intercept | -0.00677046 |
| `market_logit` | 1.21510222 |
| `regularized_lgbm_logit_delta` | 0.31975697 |

## Paper Betting Rule

For each future event:

1. Compute de-vigged market probabilities for every fight with available odds.
2. Apply the frozen residual transform to produce red and blue meta probabilities.
3. For each fight, compute each side's residual edge: `meta probability - market probability`.
4. Keep candidate paper bets only when the best side passes the thresholds below.
5. Rank candidates within the event by residual edge, then meta probability, then fight key.
6. Paper bet at most the first `max_bets_per_event` candidates at flat stake.

| Rule | Value |
| --- | ---: |
| minimum residual edge | 2.00% |
| minimum meta probability | 60.00% |
| maximum underdog odds | +300 |
| max bets per event | 3 |
| event ranking | `selected_edge desc, selected_probability desc, fight_key asc` |
| stake | 1.00u flat paper stake |

## Historical Cap Diagnostic

This applies the cap to the historical fixed residual-meta paper-policy
bet ledger. It is discovery evidence only, not post-freeze proof.

| Metric | Value |
| --- | ---: |
| source bets before cap | 354 |
| source events before cap | 99 |
| capped bets | 262 |
| capped events | 99 |
| flat profit | +19.12u |
| flat ROI | 7.30% |
| actual - market | 7.68% |
| positive folds | 4 / 5 |
| event-bootstrap P(profit <= 0) | 0.016 |
| market-null p-value | 0.002 |

## Related Exploratory Cap-Family Evidence

The residual event-cap audit inspected 15 policy/cap variants on the
historical shrinkage fixed-policy ledger.

| Diagnostic | Value |
| --- | ---: |
| selected-shrinkage cap-3 profit | +17.45u |
| selected-shrinkage cap-3 ROI | 6.25% |
| selected-shrinkage cap-3 market-null p | 0.003 |
| selected-shrinkage cap-3 bootstrap P(profit <= 0) | 0.022 |
| variants inspected in selection-null | 15 |
| best inspected variant | `unshrunk_meta|cap=3` |
| selection-adjusted market-null p | 0.011 |

## Frozen Rules

- Do not alter transform coefficients, thresholds, event cap, ranking rule, or stake size after future outcomes are known.
- Generate and archive paper-bet ledgers before outcomes are known.
- Score future paper bets against market-null and event-bootstrap tests before making any real edge claim.
- Keep this capped policy separate from live staking until enough post-freeze evidence accrues.
