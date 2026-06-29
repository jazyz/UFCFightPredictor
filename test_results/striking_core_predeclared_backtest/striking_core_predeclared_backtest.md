# Striking Core Predeclared Backtest

This audit tests the narrow `mixed_sig_head_core` clue with a fixed
market-aware logistic protocol over rolling date folds. It reuses the
existing odds/feature alignment and men-only universe exclusions. The
primary candidate and comparison variants are fixed before this run;
no threshold is selected for promotion.

## Protocol

- feature table: `data/detailed_fights.csv`
- odds table: `data/fight_results_with_odds.csv`
- aligned rows: `1223`
- rolling folds: `7`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- development window: `730` days
- holdout window: `182` days
- logistic L2 C: `0.1`
- market-null refits: `300`

## Probability Results

| Variant | Fights | Candidate LL | Market Delta LL | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Market-Null p | Candidate ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_sig_head_core | 961 | 0.5933 | 0.0068 | 0.0025 | 68.99% | 6 / 7 | 0.022 | 0.003 | 2.78% |
| pct_sig_head_distance | 961 | 0.5952 | 0.0049 | 0.0019 | 68.99% | 5 / 7 | 0.069 | 0.003 | 2.21% |
| raw_sig_head_oppdiff | 961 | 0.5965 | 0.0037 | 0.0013 | 69.30% | 5 / 7 | 0.095 | 0.003 | 3.59% |
| market_recalibrated | 961 | 0.5985 | 0.0017 | 0.0007 | 68.68% | 4 / 7 | 0.216 | 0.010 | 0.87% |

## Fold Delta LL

| Fold | Holdout | Fights | Market LL | market_recalibrated | mixed_sig_head_core | raw_sig_head_oppdiff | pct_sig_head_distance |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2023-01-01 to 2023-07-01 | 121 | 0.5904 | 0.0057 | 0.0073 | 0.0112 | -0.0007 |
| 2 | 2023-07-02 to 2023-12-30 | 118 | 0.5988 | 0.0035 | -0.0016 | -0.0029 | 0.0074 |
| 3 | 2023-12-31 to 2024-06-29 | 151 | 0.6045 | 0.0025 | 0.0031 | 0.0028 | 0.0007 |
| 4 | 2024-06-30 to 2024-12-28 | 142 | 0.5621 | 0.0079 | 0.0114 | 0.0099 | 0.0119 |
| 5 | 2024-12-29 to 2025-06-28 | 138 | 0.6150 | -0.0045 | 0.0050 | 0.0026 | -0.0024 |
| 6 | 2025-06-29 to 2025-12-27 | 147 | 0.6124 | -0.0007 | 0.0068 | -0.0040 | 0.0075 |
| 7 | 2025-12-28 to 2026-06-27 | 144 | 0.6156 | -0.0021 | 0.0144 | 0.0063 | 0.0096 |

## Flat Positive-Edge PnL: `mixed_sig_head_core`

| Edge Threshold | Bets | Profit | ROI | Positive Folds | Mean Edge | Market-Null p | Bootstrap P(profit<=0) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00% | 961 | +10.94u | 1.14% | 4 / 7 | 3.96% | 0.037 | 0.344 |
| 2.00% | 714 | +33.38u | 4.68% | 6 / 7 | 5.00% | 0.002 | 0.055 |
| 5.00% | 285 | +13.43u | 4.71% | 6 / 7 | 7.26% | 0.027 | 0.164 |

## Variant Definitions

| Variant | Note | Feature Columns |
| --- | --- | --- |
| market_recalibrated | market-logit-only recalibration baseline | `market_logit` |
| mixed_sig_head_core | primary predeclared striking core from grouped audit | `market_logit`, `Sig. str.% differential oppdiff`, `Sig. str. differential oppdiff`, `Head differential oppdiff` |
| raw_sig_head_oppdiff | raw significant-strike/head differential reference | `market_logit`, `Sig. str. differential oppdiff`, `Head differential oppdiff` |
| pct_sig_head_distance | percentage differential reference | `market_logit`, `Sig. str.% differential oppdiff`, `Head% differential oppdiff`, `Distance% differential oppdiff` |

## Interpretation

- Primary probability result: `mixed_sig_head_core` has market Delta LL `0.0068`, Brier Delta `0.0025`, positive folds `6 / 7`, event-bootstrap `P(delta <= 0)` `0.022`, and market-null p `0.003`.
- Best descriptive flat positive-edge threshold for `mixed_sig_head_core` in this report is `2.00%` with profit `+33.38u`, ROI `4.68%`, and market-null p `0.002`.
- The probability result clears the unadjusted market-null screen, but still needs correction for adjacent variants and future pre-outcome paper tracking before it can support staking.
