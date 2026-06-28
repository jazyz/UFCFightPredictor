# Disagreement Forward-Selection Summary

Run date: 2026-06-28.

## Purpose

This audit tests whether the model-vs-market disagreement pockets survive a
stricter forward-selection setup. Each fold selects a simple flat-stake policy
on the prior 365 days, then freezes that policy and evaluates the next 182-day
holdout window.

The script does not retrain a model. It reads the saved leak-safe long ledgers:

```text
test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv
test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv
```

## Policy Family

Each candidate policy bets the side with the largest model probability edge
over the de-vigged market, subject to:

- model label: `baseline_default` or `regularized_lgbm`
- minimum model-minus-market edge: `0.00`, `0.02`, `0.05`, `0.08`, `0.12`, `0.16`
- minimum selected model probability: `0.50`, `0.55`, `0.60`, `0.65`
- maximum underdog odds: `+300` or no cap

Each bet is flat 1 unit. There is no Kelly sizing or bankroll compounding.

## Results

`Market-Null p` is conditional on the selected holdout bets. `Selection-Null p`
simulates fight outcomes from market probabilities and reruns the same
fold-level policy selection in each simulated world.

| Selection Objective | Bets | Profit | Flat ROI | Actual - Market | Positive Folds | Market-Null p | Selection-Null p | Event Bootstrap P(profit <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| profit | 373 | -3.49u | -0.93% | +2.47% | 4 / 7 | 0.342 | 0.360 | 0.570 |
| ROI | 161 | +10.15u | +6.30% | +5.07% | 4 / 7 | 0.107 | 0.130 | 0.226 |
| actual - market | 167 | +15.22u | +9.11% | +6.72% | 5 / 7 | 0.090 | 0.076 | 0.124 |

Output reports:

```text
test_results/disagreement_forward_selection_audit/profit_objective/disagreement_forward_selection_audit.md
test_results/disagreement_forward_selection_audit/roi_objective/disagreement_forward_selection_audit.md
test_results/disagreement_forward_selection_audit/market_edge_objective/disagreement_forward_selection_audit.md
```

## Interpretation

The simple disagreement rule family does not establish a real edge claim.

The strongest run is the actual-minus-market objective, with `+15.22u`,
`+9.11%` flat ROI, an uncorrected conditional market-null p-value of `0.090`,
and a selection-adjusted market-null p-value of `0.076`. Because three
objectives were inspected, a simple Bonferroni correction puts the best
selection-adjusted p-value around `0.23`.

That does not invalidate the signal. It does mean the evidence is still in the
"interesting enough to paper-track" bucket, not the "proven market edge" bucket.
The profit-selected objective going slightly negative is an especially useful
warning against trusting the all-period positive slices from the static
disagreement audit.

## Next Implication

Do not promote a new feature set or betting policy from this audit alone. The
current frozen forward paper-tracking policy remains the right operational path.
Future post-freeze results need to beat market-null and event-bootstrap tests
without changing the model family, thresholds, objective, or staking rules.
