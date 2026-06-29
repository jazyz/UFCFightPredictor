# Striking Feature Engineering Selection-Null Audit

This audit reruns the rolling feature-variant selectors under
market-implied outcomes. Each null iteration simulates fight outcomes
from de-vigged market probabilities, refits every feature variant on the
simulated labels, reruns prior-fold selection, and scores the selected
next-fold result.

## Protocol

- aligned men-only rows: `1223`
- candidate feature variants: `7`
- rolling folds: `7`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- logistic L2 C: `0.1`
- fixed betting threshold: `2.00%`
- event cap: none
- selection-null iterations: `200`

## Observed Rolling Selectors

| Selector | Fights | Delta LL | Delta Brier | Accuracy | Positive Folds | Bootstrap P(delta<=0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_prior_probability_delta` | 840 | 0.0039 | 0.0016 | 69.52% | 4 / 6 | 0.164 |

| Variant | Bets | Events | Profit | ROI | Actual - Market | Positive Folds | Boot P(profit<=0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_prior_profit` | 615 | 125 | +30.73u | 5.00% | 4.95% | 6 / 6 | 0.058 |  |

Probability selection path:

| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `current_mixed_core` | 121 | 0.0073 | 118 | -0.0016 |
| 3 | `current_sigpct_head` | 239 | 0.0049 | 151 | 0.0030 |
| 4 | `pace_adjusted_mixed_core` | 390 | 0.0045 | 142 | 0.0115 |
| 5 | `pace_adjusted_mixed_core` | 532 | 0.0064 | 138 | -0.0027 |
| 6 | `current_sigpct_head` | 670 | 0.0057 | 147 | 0.0064 |
| 7 | `rate_volume_core` | 817 | 0.0064 | 144 | 0.0054 |

Profit selection path:

| Eval Fold | Selected Variant | Prior Rows/Bets | Prior Score | Eval Rows/Bets | Eval Score |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `current_mixed_core` | 87 | +0.91u | 92 | +2.85u |
| 3 | `rate_volume_core` | 160 | +6.03u | 103 | +2.54u |
| 4 | `rate_volume_core` | 263 | +8.57u | 96 | +1.90u |
| 5 | `pace_adjusted_mixed_core` | 371 | +18.53u | 101 | +0.83u |
| 6 | `pace_adjusted_mixed_core` | 472 | +19.36u | 113 | +7.98u |
| 7 | `pace_adjusted_mixed_core` | 585 | +27.34u | 110 | +14.64u |

## Selection-Null Results

| Selector | Observed | Null Mean | Null 95% CI | P(null >= observed) | P(null > 0) |
| --- | ---: | ---: | --- | ---: | ---: |
| probability-delta selector | 0.0039 | -0.0043 | -0.0102 to 0.0019 | 0.015 | 0.080 |
| profit selector | +30.73u | -17.41u | -69.27u to +39.17u | 0.040 | 0.215 |

## Interpretation

- The rolling probability selector clears the 200-path selection-null screen.
- The rolling profit selector clears the 200-path selection-null screen.
- This is still historical evidence over a feature family designed after prior striking-core discovery; it is not a live-edge proof or a reason to alter the frozen paper policies without future validation.

## Outputs

- `test_results/striking_feature_engineering_selection_null_audit/observed_rolling_probability_predictions.csv`
- `test_results/striking_feature_engineering_selection_null_audit/observed_rolling_profit_bets.csv`
- `test_results/striking_feature_engineering_selection_null_audit/selection_null_distribution.csv`
- `test_results/striking_feature_engineering_selection_null_audit/striking_feature_engineering_selection_null_audit.json`
- `test_results/striking_feature_engineering_selection_null_audit/striking_feature_engineering_selection_null_audit.md`
