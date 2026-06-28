# Frozen Residual Meta Paper Policy

As-of date: `2026-06-28`
Frozen transform: `test_results/frozen_market_residual_meta/frozen_market_residual_meta.json`
Historical diagnostic: `test_results/residual_meta_pnl_audit/fixed_edge02_prob60/residual_meta_pnl_audit.json`

This is a paper-tracking contract only. It is intentionally separated
from any live staking recommendation because the nested PnL evidence is
weak and post-freeze outcomes have not accumulated.

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

For each future fight with a regularized model probability and market odds:

1. Compute de-vigged market probabilities for both fighters.
2. Apply the frozen residual transform to the red-side probability.
3. Set blue meta probability to `1 - red meta probability`.
4. Compute `meta probability - market probability` for both sides.
5. Paper bet the side with the largest positive residual edge only if all thresholds pass.

| Rule | Value |
| --- | ---: |
| minimum residual edge | 2.00% |
| minimum meta probability | 60.00% |
| maximum underdog odds | +300 |
| stake | 1.00u flat paper stake |

## Historical Diagnostic

This diagnostic uses the fixed policy historically. It is not post-freeze
evidence and should not be treated as proof of a live edge.

| Metric | Value |
| --- | ---: |
| folds | 5 |
| holdout bets | 354 |
| flat profit | +2.44u |
| flat ROI | 0.69% |
| actual - market | 3.19% |
| positive folds | 3 / 5 |
| event-bootstrap P(profit <= 0) | 0.421 |
| market-null p-value | 0.117 |

## Frozen Rules

- Do not alter the transform coefficients, thresholds, side-selection rule, or stake size after future outcomes are known.
- Archive paper-bet ledgers before outcomes are known.
- Score future paper bets against market-null and event-bootstrap tests before making any real edge claim.
