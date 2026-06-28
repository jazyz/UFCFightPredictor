# Nested Edge Audit Summary

Run date: 2026-06-28

## Purpose

This audit tests whether the current model/strategy choices look like a real
edge after reducing selection bias. Instead of choosing a strategy on one
development window and reporting one holdout, it repeatedly:

1. selects the model and betting strategy on the previous 365 days,
2. freezes that selection,
3. evaluates the next 182-day holdout window,
4. repeats through the available odds history.

Odds-backed window used for long ledgers: `2022-02-05` to `2026-06-27`.

## Long Leak-Safe Ledgers

Both ledgers retrain before each event date and use only prior fights.

| Model | Fights | Rolling Fits | Accuracy | Log Loss | Full-Window PnL |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline default | 1249 | 188 | 62.53% | 0.6447 | +25.07% |
| Regularized LGBM | 1249 | 188 | 63.65% | 0.6396 | +29.61% |

Interpretation: regularization still improves the long-window model metrics and
plain-strategy PnL, but this by itself is not an unbiased edge claim because
the regularized params were chosen after earlier diagnostics.

## Nested Strategy Selection

Candidate models:

- `baseline_default`
- `regularized_lgbm`

Candidate strategies: existing `testing/walk_forward_strategy_search.py` grid.

Fold setup:

- first holdout start: `2023-02-05`
- final holdout end: `2026-06-27`
- development window: 365 days
- holdout window: 182 days
- minimum holdout length: 120 days
- minimum development bets: 35

### Profit Objective

The selector maximizes development-window profit first, matching the existing
walk-forward strategy-search objective.

| Metric | Value |
| --- | ---: |
| Folds | 7 |
| Holdout fights | 962 |
| Bets | 277 |
| Profit | $170.39 |
| ROI on staked | 4.00% |
| Positive folds | 4 / 7 |
| Selected models | baseline 5, regularized 2 |
| Market-null p-value | 0.199 |
| Event-bootstrap probability profit <= 0 | 32.02% |

Interpretation: positive but not statistically convincing.

### ROI Objective Sensitivity

The selector maximizes development-window ROI first. This was run as a
sensitivity check, not as a pre-registered final policy.

| Metric | Value |
| --- | ---: |
| Folds | 7 |
| Holdout fights | 962 |
| Bets | 148 |
| Profit | $115.09 |
| ROI on staked | 12.62% |
| Positive folds | 4 / 7 |
| Selected models | regularized 5, baseline 2 |
| Market-null p-value | 0.048 |
| Event-bootstrap probability profit <= 0 | 9.60% |

Interpretation: this is the strongest evidence found in this pass, but it is
exploratory. Because both profit and ROI objectives were evaluated, a simple
two-objective correction would put the market-null p-value around `0.096`.
That is promising enough to paper-track, not strong enough to claim a proven
live betting edge.

## Market Log-Loss Check

Long regularized-ledger blend audit:

- development: `2022-02-05` to `2024-02-04`
- holdout: `2024-02-05` to `2026-06-27`
- blend mode: logit
- selected model weight: `0.000`

| Probability | Dev Log Loss | Holdout Log Loss |
| --- | ---: | ---: |
| Regularized model | 0.6495 | 0.6337 |
| De-vigged market | 0.6003 | 0.6009 |
| Dev-selected blend | 0.6003 | 0.6009 |

Interpretation: over the longer history, the development window selected pure
market probability for log loss. The model does not currently establish a
market log-loss edge as a standalone probability forecaster or as a selected
blend on this longer split.

## Current Conclusion

No real edge claim is proven yet.

What looks real:

- regularization improves model accuracy/log loss relative to the old model
- selective betting filters can find positive PnL regions
- the ROI-objective nested audit is encouraging

What blocks a strong claim:

- standalone model probabilities still lose clearly to market log loss
- profit-objective nested selection has weak market-null evidence
- ROI-objective evidence is exploratory and needs forward confirmation
- only 7 nested holdout folds are available with current odds history

## Recommended Frozen Forward Test

For future cards, freeze one policy before seeing new outcomes:

- model candidates: baseline default and regularized LGBM
- selection objective: ROI
- development lookback: previous 365 days
- strategy grid: existing `testing/walk_forward_strategy_search.py`
- staking: whatever the selected strategy specifies, capped by the grid

Track future predictions and bets without changing the selector. A stronger
edge claim would require future positive results against market-null and
event-bootstrap tests after this policy is frozen.
