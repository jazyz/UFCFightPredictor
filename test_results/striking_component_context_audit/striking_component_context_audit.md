# Striking Component Context Audit

This diagnostic decomposes the current striking alpha into compact
fight-context components after controlling for the de-vigged market.
It uses the same men-only market-aware rolling protocol as the frozen
striking policies and keeps every fixed `2%` betting ledger uncapped by
event.

## Protocol

- source fights: `data/modified_fight_details.csv`
- feature table: `data/detailed_fights.csv`
- odds table: `data/fight_results_with_odds.csv`
- aligned rows: `1223`
- rolling folds: `7`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- logistic L2 C: `0.1`
- market-null refits: `300`
- fixed betting threshold: `2.00%`

## Probability Results

| Variant | Features | Delta LL | Inc vs Recal | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current_sigpct_head | 3 | 0.0071 | 0.0054 | 0.0027 | 69.41% | 7 / 7 | 0.015 | 0.003 |
| pace_offense_split | 4 | 0.0071 | 0.0054 | 0.0030 | 68.99% | 6 / 7 | 0.023 | 0.003 |
| pace_adjusted_mixed_core | 4 | 0.0068 | 0.0052 | 0.0028 | 69.30% | 6 / 7 | 0.021 | 0.003 |
| current_mixed_core | 4 | 0.0068 | 0.0051 | 0.0025 | 68.99% | 6 / 7 | 0.022 | 0.003 |
| pace_for_against_split | 6 | 0.0061 | 0.0044 | 0.0024 | 69.30% | 6 / 7 | 0.045 | 0.003 |
| pace_sigpm_only | 3 | 0.0060 | 0.0044 | 0.0024 | 69.30% | 6 / 7 | 0.035 | 0.003 |
| sigpct_only | 2 | 0.0056 | 0.0040 | 0.0023 | 69.30% | 6 / 7 | 0.034 | 0.003 |
| pace_headpm_only | 3 | 0.0056 | 0.0039 | 0.0024 | 69.30% | 6 / 7 | 0.037 | 0.003 |
| raw_head_only | 2 | 0.0044 | 0.0027 | 0.0017 | 68.89% | 6 / 7 | 0.051 | 0.003 |
| pace_defense_split | 4 | 0.0042 | 0.0025 | 0.0017 | 69.30% | 6 / 7 | 0.099 | 0.003 |
| raw_sig_only | 2 | 0.0023 | 0.0006 | 0.0009 | 68.78% | 4 / 7 | 0.192 | 0.003 |
| market_recalibrated | 1 | 0.0017 | 0.0000 | 0.0007 | 68.68% | 4 / 7 | 0.216 | 0.027 |

## Fixed 2% Positive-Edge Uncapped PnL

| Variant | Bets | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pace_adjusted_mixed_core | 695 | +41.97u | 6.04% | 5.85% | 6 / 7 | 0.020 | <0.001 |
| pace_for_against_split | 699 | +38.91u | 5.57% | 5.39% | 6 / 7 | 0.050 | 0.002 |
| current_mixed_core | 714 | +33.38u | 4.68% | 5.12% | 6 / 7 | 0.053 | 0.002 |
| pace_sigpm_only | 704 | +32.87u | 4.67% | 5.56% | 6 / 7 | 0.048 | 0.003 |
| current_sigpct_head | 705 | +31.85u | 4.52% | 4.74% | 5 / 7 | 0.068 | 0.002 |
| sigpct_only | 706 | +30.18u | 4.27% | 5.25% | 6 / 7 | 0.060 | 0.003 |
| pace_headpm_only | 700 | +28.39u | 4.06% | 5.04% | 6 / 7 | 0.072 | 0.005 |
| raw_head_only | 647 | +26.31u | 4.07% | 4.14% | 5 / 7 | 0.095 | 0.005 |
| pace_offense_split | 697 | +19.37u | 2.78% | 4.29% | 5 / 7 | 0.178 | 0.011 |
| pace_defense_split | 677 | +3.48u | 0.51% | 3.19% | 4 / 7 | 0.432 | 0.052 |
| raw_sig_only | 643 | +0.61u | 0.09% | 3.08% | 5 / 7 | 0.479 | 0.062 |

## Component Coefficient Signs

| Variant | Feature | Mean Coef | Positive Folds | Expected Sign Matches |
| --- | --- | ---: | ---: | ---: |
| current_sigpct_head | `Head differential oppdiff` | 0.1270 | 7 / 7 | 7 / 7 |
| current_sigpct_head | `Sig. str.% differential oppdiff` | 0.1077 | 7 / 7 | 7 / 7 |
| pace_adjusted_mixed_core | `Head differential_pm oppdiff` | 0.1478 | 7 / 7 | 7 / 7 |
| pace_adjusted_mixed_core | `Sig. str. differential_pm oppdiff` | -0.1873 | 0 / 7 | 0 / 7 |
| pace_adjusted_mixed_core | `Sig. str.% differential oppdiff` | 0.1690 | 7 / 7 | 7 / 7 |
| pace_for_against_split | `Head against_pm oppdiff` | -0.0198 | 2 / 7 | 5 / 7 |
| pace_for_against_split | `Head for_pm oppdiff` | 0.1718 | 7 / 7 | 7 / 7 |
| pace_for_against_split | `Sig. str. against_pm oppdiff` | 0.0506 | 6 / 7 | 1 / 7 |
| pace_for_against_split | `Sig. str. for_pm oppdiff` | -0.2057 | 0 / 7 | 0 / 7 |
| pace_for_against_split | `Sig. str.% differential oppdiff` | 0.1680 | 7 / 7 | 7 / 7 |
| pace_offense_split | `Head for_pm oppdiff` | 0.1715 | 7 / 7 | 7 / 7 |
| pace_offense_split | `Sig. str. for_pm oppdiff` | -0.1913 | 0 / 7 | 0 / 7 |
| pace_offense_split | `Sig. str.% differential oppdiff` | 0.1533 | 7 / 7 | 7 / 7 |

## Raw Component Residual Shape

| Feature | Expected | Spearman vs A-M | Low Bin A-M | High Bin A-M | Aligned High-Low |
| --- | --- | ---: | ---: | ---: | ---: |
| `Sig. str.% differential oppdiff` | + | 0.0625 | -6.53% | 6.45% | 12.98% |
| `Sig. str. differential oppdiff` | + | 0.0291 | -5.66% | 5.99% | 11.65% |
| `Head differential oppdiff` | + | 0.0360 | -5.57% | 5.43% | 11.00% |
| `Sig. str. differential_pm oppdiff` | + | -0.0348 | 0.49% | -3.81% | -4.30% |
| `Head differential_pm oppdiff` | + | -0.0384 | 0.49% | 1.12% | 0.62% |
| `Sig. str. for_pm oppdiff` | + | -0.0319 | 2.04% | -2.63% | -4.67% |
| `Sig. str. against_pm oppdiff` | - | -0.0011 | 0.80% | -1.96% | 2.77% |
| `Head for_pm oppdiff` | + | -0.0221 | -0.94% | -4.25% | -3.31% |
| `Head against_pm oppdiff` | - | 0.0061 | 3.18% | -3.01% | 6.18% |

## Strongest Component Correlations

| Feature A | Feature B | Spearman |
| --- | --- | ---: |
| `Sig. str. against_pm oppdiff` | `Head against_pm oppdiff` | 0.9024 |
| `Sig. str. for_pm oppdiff` | `Head for_pm oppdiff` | 0.8876 |
| `Sig. str. differential_pm oppdiff` | `Head differential_pm oppdiff` | 0.8433 |
| `Sig. str. differential oppdiff` | `Head differential oppdiff` | 0.7539 |
| `Sig. str. differential oppdiff` | `Sig. str. differential_pm oppdiff` | 0.6778 |
| `Head differential oppdiff` | `Head differential_pm oppdiff` | 0.6683 |
| `Head differential_pm oppdiff` | `Head for_pm oppdiff` | 0.6028 |
| `Sig. str. differential_pm oppdiff` | `Sig. str. for_pm oppdiff` | 0.5734 |

## Interpretation

- Best probability variant: `current_sigpct_head` with Delta LL `0.0071`, positive folds `7` / `7`, and market-null p `0.003`.
- Best fixed `2%` uncapped PnL variant: `pace_adjusted_mixed_core` with profit `+41.97u`, ROI `6.04%`, and market-null p `<0.001`.
- `current_sigpct_head` remains the cleaner probability surface than the frozen pace-adjusted challenger by about `0.0003` Delta LL, while pace-adjusted variants remain competitive for uncapped PnL.
- The component signs are mixed: significant-strike percentage and head-strike components are stable positive contributors, but generic significant-strike pace/volume turns negative once efficiency and head pace are included.
- Raw pace component residual bins are not uniformly monotone after market control, so the pace-adjusted PnL lead should be treated as a correlated feature clue, not a new live-edge proof.
- No event cap is used here. The result supports continued paper tracking and deeper feature design, not increased live staking.
