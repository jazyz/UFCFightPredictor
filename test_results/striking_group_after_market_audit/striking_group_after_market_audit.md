# Striking Group After Market Audit

This discovery audit tests whether the one-feature striking-differential
clues survive as compact grouped models after market control. Each
candidate is a rolling prior-fold logistic model with red/blue mirrored
training and mirrored holdout averaging. It is not a promoted feature
set or betting policy.

## Protocol

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- features: `data/detailed_fights.csv`
- merged rows: `704`
- rolling eval folds: `2, 3, 4, 5`
- rolling eval fights: `539`
- logistic L2 C: `0.1`
- bootstrap iterations: `20000`
- market-null iterations: `300`

## References On Same Folds

| Reference | Fights | Candidate LL | Market Delta LL | Inc Delta vs Recal | Positive Market Folds | Boot P(market<=0) | Latest Market Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market_recalibrated | 539 | 0.6023 | -0.0001 | 0.0000 | 2 / 4 | 0.515 | -0.0036 |
| selected_shrinkage | 539 | 0.5994 | 0.0028 | 0.0029 | 3 / 4 | 0.255 | -0.0047 |
| fixed_half_residual | 539 | 0.5996 | 0.0025 | 0.0027 | 3 / 4 | 0.129 | -0.0018 |

## Grouped Striking Results

| Variant | Features | Market Delta LL | Inc Delta vs Recal | Positive Market Folds | Boot P(inc<=0) | Null p(market) | Null p(inc) | Latest Inc Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_sig_head_core | 4 | 0.0090 | 0.0091 | 4 / 4 | 0.014 | 0.007 | 0.003 | 0.0175 |
| pct_sig_head_distance | 4 | 0.0056 | 0.0057 | 3 / 4 | 0.072 | 0.003 | 0.003 | 0.0100 |
| pct_striking_diff_core | 6 | 0.0048 | 0.0050 | 3 / 4 | 0.114 | 0.010 | 0.007 | 0.0109 |
| all_positive_striking_clues | 12 | 0.0039 | 0.0040 | 3 / 4 | 0.219 | 0.007 | 0.007 | 0.0065 |
| raw_sig_head_side_pairs | 5 | 0.0036 | 0.0037 | 4 / 4 | 0.074 | 0.023 | 0.017 | 0.0102 |
| raw_sig_head_oppdiff | 3 | 0.0036 | 0.0037 | 4 / 4 | 0.077 | 0.023 | 0.017 | 0.0103 |
| raw_striking_diff_core | 7 | 0.0019 | 0.0020 | 3 / 4 | 0.241 | 0.033 | 0.020 | 0.0053 |
| defense_proxy_clues | 5 | -0.0020 | -0.0019 | 3 / 4 | 0.618 | 0.133 | 0.159 | -0.0238 |
| wrong_way_striking_control | 5 | -0.0071 | -0.0070 | 1 / 4 | 0.894 | 0.588 | 0.741 | -0.0073 |

## Best Group Coefficients: `mixed_sig_head_core`

| Feature | Mean Coef | Min | Max |
| --- | ---: | ---: | ---: |
| `market_logit` | 0.8678 | 0.8072 | 0.8990 |
| `Head differential oppdiff` | 0.2101 | 0.1684 | 0.2500 |
| `Sig. str.% differential oppdiff` | 0.1783 | 0.1405 | 0.2466 |
| `Sig. str. differential oppdiff` | -0.1049 | -0.1704 | -0.0679 |

## Variant Definitions

| Variant | Note | Feature Columns |
| --- | --- | --- |
| raw_sig_head_oppdiff | raw significant-strike and head-strike differential oppdiffs | `market_logit`, `Sig. str. differential oppdiff`, `Head differential oppdiff` |
| raw_sig_head_side_pairs | side-pair version of the same raw sig-str/head differential theme | `market_logit`, `Red Sig. str. differential`, `Blue Sig. str. differential`, `Red Head differential`, `Blue Head differential` |
| pct_sig_head_distance | percentage/rate proxy differentials that scored well one at a time | `market_logit`, `Sig. str.% differential oppdiff`, `Head% differential oppdiff`, `Distance% differential oppdiff` |
| mixed_sig_head_core | best percentage proxy plus raw sig-str/head differential clues | `market_logit`, `Sig. str.% differential oppdiff`, `Sig. str. differential oppdiff`, `Head differential oppdiff` |
| raw_striking_diff_core | raw striking and position differential core without percentage proxies | `market_logit`, `Sig. str. differential oppdiff`, `Head differential oppdiff`, `Distance differential oppdiff`, `Total str. differential oppdiff`, `Ground differential oppdiff`, `Clinch differential oppdiff` |
| pct_striking_diff_core | percentage/rate proxy striking differential core | `market_logit`, `Sig. str.% differential oppdiff`, `Head% differential oppdiff`, `Distance% differential oppdiff`, `Body% differential oppdiff`, `Clinch% differential oppdiff` |
| all_positive_striking_clues | union of non-defense positive striking clues from the one-feature audit | `market_logit`, `Sig. str.% differential oppdiff`, `Head differential oppdiff`, `Head% differential oppdiff`, `Distance% differential oppdiff`, `Sig. str. differential oppdiff`, `Ground differential oppdiff`, `Total str. differential oppdiff`, `Clinch% differential oppdiff`, `Body% differential oppdiff`, `Clinch differential oppdiff`, `Distance differential oppdiff` |
| defense_proxy_clues | target/position-mix defense proxies, separated from cleaner differentials | `market_logit`, `Distance% defense oppdiff`, `Leg% defense oppdiff`, `Head% defense oppdiff`, `Total str.% defense oppdiff` |
| wrong_way_striking_control | features that were weak or wrong-way in one-feature probes | `market_logit`, `Leg differential oppdiff`, `KD differential oppdiff`, `Head oppdiff`, `Sig. str. oppdiff` |

## Interpretation

- Best grouped candidate by incremental log loss: `mixed_sig_head_core` with market Delta LL `0.0090` and incremental Delta LL `0.0091`.
- Its event-bootstrap `P(incremental delta <= 0)` is `0.014`; market-null p-values are `0.007` versus raw market and `0.003` versus market recalibration.
- On the same folds, selected-shrinkage residual Delta LL is `0.0028`; the best grouped candidate is `0.0062` relative to that reference.
- This clears the unadjusted market-null screen, but it is still post-hoc discovery evidence and would need a predeclared leak-safe model/backtest before promotion.
- The practical next step is not broad feature expansion; it is a narrow, predeclared redesign/backtest of striking-differential features if we choose to pursue this clue.
