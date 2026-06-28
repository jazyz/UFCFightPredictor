# Residual Meta PnL Audit Summary

Run date: 2026-06-28.

## Purpose

This audit tests whether the residual probability edge from the market-residual
meta audit can be converted into a simple flat-stake betting edge.

It uses the saved leak-safe long ledgers and does not retrain the base UFC
model. For each outer fold:

1. Fit the residual meta layer on the first part of the development window.
2. Select betting thresholds on the second part of the development window,
   using out-of-sample meta probabilities.
3. Refit the residual meta layer on the full development window.
4. Freeze the selected threshold policy onto the next holdout window.

The market-null simulation reruns the full inner meta-training, threshold
selection, and outer holdout evaluation loop under outcomes sampled from
de-vigged market probabilities.

## Inputs

```text
test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv
test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv
```

Frozen-style residual settings:

- residual model: `regularized_lgbm`
- meta features: `market_logit`, `regularized_lgbm_logit_delta`
- meta logistic `C = 0.25`
- outer development window: `730` days
- inner meta-training window: `365` days
- holdout window: `182` days
- folds: `5`

## Results

| Selection Objective | Bets | Profit | Flat ROI | Actual - Market | Positive Folds | Selection-Adjusted Market-Null p | Event Bootstrap P(profit <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| profit | 363 | +7.46u | +2.06% | +4.10% | 4 / 5 | 0.066 | 0.258 |
| ROI | 304 | +4.31u | +1.42% | +3.56% | 4 / 5 | 0.144 | 0.344 |
| actual - market | 311 | +6.67u | +2.14% | +4.08% | 4 / 5 | 0.083 | 0.265 |
| fixed edge>=0.02, p>=0.60 | 354 | +2.44u | +0.69% | +3.19% | 3 / 5 | 0.117 | 0.421 |

Output reports:

```text
test_results/residual_meta_pnl_audit/profit_objective/residual_meta_pnl_audit.md
test_results/residual_meta_pnl_audit/roi_objective/residual_meta_pnl_audit.md
test_results/residual_meta_pnl_audit/market_edge_objective/residual_meta_pnl_audit.md
test_results/residual_meta_pnl_audit/fixed_edge02_prob60/residual_meta_pnl_audit.md
```

## Interpretation

The residual meta probabilities produce positive flat-bet PnL across all three
threshold-selection objectives, and four of five folds are profitable. That is
directionally consistent with the probability-edge audit.

The evidence is still not strong enough for a real live edge claim. The best
selection-adjusted market-null p-value is `0.066` before correcting for the
three inspected objectives, and the event-bootstrap intervals still cross zero.
A simple Bonferroni correction across the three objectives would put the best
p-value around `0.20`.

Practical read: the residual meta transform is worth paper tracking, but the
current nested PnL evidence is weaker than the log-loss evidence. Do not promote
or increase staking from this audit alone.

## Frozen Paper Policy

A conservative residual-meta paper policy has been frozen:

```text
testing/freeze_residual_meta_paper_policy.py
test_results/frozen_residual_meta_paper_policy/frozen_residual_meta_paper_policy.md
test_results/frozen_residual_meta_paper_policy/frozen_residual_meta_paper_policy.json
```

Frozen rule:

- use the frozen residual probability transform from
  `test_results/frozen_market_residual_meta/`
- bet the side with the largest residual edge
- minimum residual edge: `0.02`
- minimum meta probability: `0.60`
- maximum underdog odds: `+300`
- stake: `1u` flat paper stake

This policy is intentionally paper-only. Its fixed-policy historical diagnostic
was only `+2.44u` with market-null p-value `0.117`, so it should be used to
collect future evidence rather than to justify staking.
