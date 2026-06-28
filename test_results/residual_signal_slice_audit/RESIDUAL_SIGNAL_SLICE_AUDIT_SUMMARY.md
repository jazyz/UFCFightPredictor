# Residual Signal Slice Audit Summary

Run date: 2026-06-28.

## Purpose

This diagnostic checks where the residual market/meta signal appears after the
market-residual meta audit. It does not retrain models or select policies. It
uses:

```text
test_results/market_residual_meta_audit/holdout_meta_predictions.csv
test_results/residual_meta_pnl_audit/fixed_edge02_prob60/selected_holdout_bets.csv
```

## Probability Signal

Aggregate holdout result for `market_plus_regularized_lgbm`:

| Fights | Market LL | Meta LL | Delta LL |
| ---: | ---: | ---: | ---: |
| 704 | 0.6009 | 0.5979 | +0.0030 |

The signal is not uniform by market-probability band:

| Market Probability Band | Fights | Delta LL |
| --- | ---: | ---: |
| <0.40 | 250 | +0.0024 |
| 0.40-0.50 | 102 | -0.0008 |
| 0.50-0.60 | 105 | +0.0264 |
| 0.60-0.70 | 131 | -0.0143 |
| 0.70-0.80 | 83 | +0.0101 |
| >=0.80 | 33 | -0.0048 |

By absolute residual edge, the strongest positive slice was `0.05-0.08`
(`+0.0234` Delta LL), while the extreme `>=0.08` slice was negative
(`-0.0310` Delta LL). This argues against blindly trusting the largest model
residuals.

By year, the signal was positive in `2024` (`+0.0098`), small in `2025`
(`+0.0018`), and negative in `2026` (`-0.0077`).

## Fixed Paper-Policy Bets

The frozen-style fixed paper policy:

- minimum residual edge: `0.02`
- minimum meta probability: `0.60`
- max underdog odds: `+300`
- flat stake: `1u`

Aggregate historical diagnostic:

| Bets | Profit | ROI | Actual - Market |
| ---: | ---: | ---: | ---: |
| 354 | +2.44u | +0.69% | +3.19% |

Bet-level fragility:

| Slice | Bets | Profit | ROI |
| --- | ---: | ---: | ---: |
| market P 0.50-0.60 | 42 | +7.93u | +18.87% |
| market P 0.60-0.70 | 135 | -6.91u | -5.12% |
| market P 0.70-0.80 | 122 | +4.10u | +3.36% |
| market P >=0.80 | 55 | -2.68u | -4.87% |
| residual edge 0.02-0.03 | 66 | -5.73u | -8.68% |
| residual edge 0.03-0.05 | 185 | +7.05u | +3.81% |
| residual edge 0.05-0.08 | 99 | +1.67u | +1.69% |
| residual edge >=0.08 | 4 | -0.55u | -13.74% |

All fixed-policy historical bets were favorites. By year, the policy was
positive in `2024` (`+11.60u`) but negative in `2025` (`-4.64u`) and `2026`
(`-4.52u`).

## Interpretation

This strengthens the “paper-track, do not stake up” conclusion. The residual
probability edge is real enough to keep monitoring, but it is not broad or
stable enough to support a live edge claim. The strongest warning is that
larger residuals are not monotonically better: the extreme residual-edge slice
was historically negative.

Use this audit as a diagnostic baseline only. Do not tune the already-frozen
residual paper policy from these slices.
