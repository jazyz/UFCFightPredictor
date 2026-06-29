# Striking Redesign Selection Audit

This audit tests a small predeclared head-focused striking redesign
family motivated by the component-context result: keep significant
strike efficiency and head-strike concepts, avoid generic
significant-strike pace/volume, and select variants using only prior
folds. It does not change any frozen paper policy.

## Protocol

- aligned men-only rows: `1223`
- candidate variants: `8`
- rolling folds: `7`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- logistic L2 C: `0.1`
- fixed betting threshold: `2.00%`
- event cap: none
- fixed market-null refits: `300`
- selection-null iterations: `200`

## Fixed Variant Probability Results

| Variant | Features | Delta LL | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sigpct_head_raw_pm | 4 | 0.0081 | 0.0030 | 69.51% | 7 / 7 | 0.006 | 0.003 |
| sigpct_head_raw_for_against | 5 | 0.0074 | 0.0026 | 69.09% | 7 / 7 | 0.011 | 0.003 |
| current_sigpct_head | 3 | 0.0071 | 0.0027 | 69.41% | 7 / 7 | 0.015 | 0.003 |
| pace_adjusted_mixed_core | 4 | 0.0068 | 0.0028 | 69.30% | 6 / 7 | 0.022 | 0.003 |
| sigpct_head_raw_against | 4 | 0.0064 | 0.0023 | 68.89% | 7 / 7 | 0.025 | 0.003 |
| sigpct_only | 2 | 0.0056 | 0.0023 | 69.30% | 6 / 7 | 0.034 | 0.003 |
| sigpct_head_pm | 3 | 0.0056 | 0.0024 | 69.30% | 6 / 7 | 0.040 | 0.003 |
| sigpct_head_for_against | 4 | 0.0050 | 0.0020 | 69.20% | 6 / 7 | 0.058 | 0.003 |
| market_recalibrated | 1 | 0.0017 | 0.0007 | 68.68% | 4 / 7 | 0.216 | 0.003 |

## Fixed 2% Positive-Edge Uncapped PnL

| Variant | Bets | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pace_adjusted_mixed_core | 695 | +41.97u | 6.04% | 5.85% | 6 / 7 | 0.020 | <0.001 |
| sigpct_head_raw_pm | 730 | +38.04u | 5.21% | 5.49% | 7 / 7 | 0.042 | 0.002 |
| current_sigpct_head | 705 | +31.85u | 4.52% | 4.74% | 5 / 7 | 0.069 | 0.002 |
| sigpct_only | 706 | +30.18u | 4.27% | 5.25% | 6 / 7 | 0.059 | 0.003 |
| sigpct_head_pm | 700 | +28.39u | 4.06% | 5.04% | 6 / 7 | 0.074 | 0.004 |
| sigpct_head_raw_for_against | 720 | +20.33u | 2.82% | 4.11% | 5 / 7 | 0.189 | 0.011 |
| sigpct_head_for_against | 682 | +11.58u | 1.70% | 3.73% | 5 / 7 | 0.272 | 0.019 |
| sigpct_head_raw_against | 720 | +8.72u | 1.21% | 3.12% | 4 / 7 | 0.349 | 0.036 |

## Rolling Prior-Fold Selectors

| Selector | Fights | Delta LL | Delta Brier | Accuracy | Positive Folds | Bootstrap P(delta<=0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_prior_probability_delta` | 840 | 0.0066 | 0.0026 | 69.64% | 5 / 6 | 0.036 |

| Variant | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_prior_profit` | 631 | 126 | +34.41u | 5.45% | 5.37% | 5 / 6 | 0.037 |  |

Probability selection path:

| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `sigpct_head_raw_against` | 121 | 0.0068 | 118 | 0.0048 |
| 3 | `sigpct_head_raw_for_against` | 239 | 0.0058 | 151 | 0.0020 |
| 4 | `sigpct_head_raw_pm` | 390 | 0.0046 | 142 | 0.0106 |
| 5 | `pace_adjusted_mixed_core` | 532 | 0.0064 | 138 | -0.0027 |
| 6 | `sigpct_head_raw_pm` | 670 | 0.0063 | 147 | 0.0083 |
| 7 | `sigpct_head_raw_pm` | 817 | 0.0067 | 144 | 0.0161 |

Profit selection path:

| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `sigpct_head_raw_for_against` | 91 | +2.97u | 93 | -0.78u |
| 3 | `sigpct_only` | 168 | +4.12u | 112 | +6.95u |
| 4 | `sigpct_only` | 280 | +11.08u | 102 | +4.80u |
| 5 | `pace_adjusted_mixed_core` | 371 | +18.53u | 101 | +0.83u |
| 6 | `pace_adjusted_mixed_core` | 472 | +19.36u | 113 | +7.98u |
| 7 | `pace_adjusted_mixed_core` | 585 | +27.34u | 110 | +14.64u |

## Selection-Null Results

| Selector | Observed | Null Mean | Null 95% CI | P(null >= observed) | P(null > 0) |
| --- | ---: | ---: | --- | ---: | ---: |
| probability-delta selector | 0.0066 | -0.0034 | -0.0085 to 0.0004 | 0.005 | 0.035 |
| profit selector | +34.41u | -18.28u | -62.37u to +34.43u | 0.030 | 0.210 |

## Variant Definitions

| Variant | Note | Feature Columns |
| --- | --- | --- |
| market_recalibrated | market-logit-only recalibration baseline | `market_logit` |
| current_sigpct_head | current compact sigpct/head challenger anchor | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff` |
| pace_adjusted_mixed_core | frozen pace-adjusted challenger anchor | `market_logit`, `Sig. str.% differential oppdiff`, `Sig. str. differential_pm oppdiff`, `Head differential_pm oppdiff` |
| sigpct_only | efficiency-only reference | `market_logit`, `Sig. str.% differential oppdiff` |
| sigpct_head_pm | efficiency plus head-strike pace differential | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential_pm oppdiff` |
| sigpct_head_for_against | efficiency plus head-strike offense and absorbed-pace split | `market_logit`, `Sig. str.% differential oppdiff`, `Head for_pm oppdiff`, `Head against_pm oppdiff` |
| sigpct_head_raw_pm | efficiency plus raw and pace-adjusted head differential | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff`, `Head differential_pm oppdiff` |
| sigpct_head_raw_for_against | efficiency plus raw head differential and head offense/defense split | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff`, `Head for_pm oppdiff`, `Head against_pm oppdiff` |
| sigpct_head_raw_against | efficiency plus raw head differential and absorbed head pace | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff`, `Head against_pm oppdiff` |

## Interpretation

- Best fixed probability variant: `sigpct_head_raw_pm` with Delta LL `0.0081` and market-null p `0.003`.
- Best fixed uncapped `2%` PnL variant: `pace_adjusted_mixed_core` with profit `+41.97u`, ROI `6.04%`, and market-null p `<0.001`.
- Probability selector chose: `pace_adjusted_mixed_core`, `sigpct_head_raw_against`, `sigpct_head_raw_for_against`, `sigpct_head_raw_pm`.
- Profit selector chose: `pace_adjusted_mixed_core`, `sigpct_head_raw_for_against`, `sigpct_only`.
- The rolling probability selector clears the selection-null screen.
- The rolling profit selector clears the selection-null screen.
- Treat this as feature-design evidence only. A new frozen policy would need future pre-outcome paper validation and should not be promoted merely because this historical redesign family is positive.

## Outputs

- `test_results/striking_redesign_selection_audit/fixed_variant_predictions.csv`
- `test_results/striking_redesign_selection_audit/fixed_edge02_bets.csv`
- `test_results/striking_redesign_selection_audit/observed_rolling_probability_predictions.csv`
- `test_results/striking_redesign_selection_audit/observed_rolling_profit_bets.csv`
- `test_results/striking_redesign_selection_audit/selection_null_distribution.csv`
- `test_results/striking_redesign_selection_audit/striking_redesign_selection_audit.json`
- `test_results/striking_redesign_selection_audit/striking_redesign_selection_audit.md`
