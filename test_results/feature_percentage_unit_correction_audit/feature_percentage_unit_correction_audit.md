# Feature Percentage Unit Correction Audit

This audit tests a surgical feature redesign: side percentage columns
such as `Red Leg%` are rebuilt as weighted percentages instead of the
current percentage-per-minute proxy. Existing differential and defense
percentage features are checked but left unchanged.

## Reconstruction Checks

| Check | Value |
| --- | ---: |
| percentage bases | 9 |
| matched feature rows | 4322 |
| missing feature rows | 0 |
| current scaled side checks | 77796 |
| current scaled side mismatches | 0 |
| percentage differential checks | 77796 |
| percentage differential mismatches | 0 |
| percentage defense checks | 77796 |
| percentage defense mismatches | 0 |

Largest active/imported percentage unit shifts:

| Feature | Importance Sum | Current Mean | Corrected Mean | Mean Abs Diff | Corr |
| --- | ---: | ---: | ---: | ---: | ---: |
| `Clinch%` | 48 | 0.0765 | 0.5155 | 0.4417 | 0.3746 |
| `Leg%` | 46 | 0.1152 | 0.6666 | 0.5594 | 0.2967 |
| `Body%` | 42 | 0.1100 | 0.6288 | 0.5269 | 0.2760 |
| `Td%` | 37 | 0.0427 | 0.2832 | 0.2430 | 0.4718 |
| `Ground%` | 35 | 0.1031 | 0.4468 | 0.3654 | 0.3053 |
| `Sig. str.%` | 31 | 0.1258 | 0.4733 | 0.3732 | 0.3298 |
| `Total str.%` | 0 | 0.1354 | 0.5435 | 0.4326 | 0.2480 |
| `Distance%` | 0 | 0.1090 | 0.3986 | 0.3163 | 0.3254 |
| `Head%` | 0 | 0.1057 | 0.3836 | 0.3036 | 0.3697 |

## Leak-Safe Backtests

| Window | Variant | Fights | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1y | current_regularized | 298 | 64.43% | 0.6418 | 0.6127 | 0.0290 | 24.66% | 229 |
| 1y | pct_unit_corrected | 298 | 62.42% | 0.6452 | 0.6127 | 0.0324 | -1.35% | 221 |
| 2y | current_regularized | 580 | 65.00% | 0.6318 | 0.5995 | 0.0324 | 61.20% | 442 |
| 2y | pct_unit_corrected | 580 | 64.83% | 0.6352 | 0.5995 | 0.0360 | 38.82% | 424 |

## Interpretation

- 1y: unit correction changed model LL from 0.6418 to 0.6452 and PnL from 24.66% to -1.35%.
- 2y: unit correction changed model LL from 0.6318 to 0.6352 and PnL from 61.20% to 38.82%.
- This is a direct test of one feature-unit hypothesis. It should not be promoted unless it improves both probability evidence and downstream nested validation.
