# Market Residual Meta Audit

This audit trains only small logistic meta-models on saved leak-safe
ledger probabilities. Each fold uses prior fights for meta-training and
evaluates whether the meta probability beats de-vigged market probability
on future log loss.

## Inputs

| Label | Ledger |
| --- | --- |
| baseline_default | `test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv` |
| regularized_lgbm | `test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv` |

## Protocol

- aligned fights: `1220`
- folds: `5`
- development window: `730` days
- holdout window: `182` days
- logistic meta regularization C: `1.0`

## Results

`Delta LL` is `market log loss - meta log loss`; positive means the
meta-model beat the de-vigged market.

| Variant | Features | Fights | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market_recalibrated | `market_logit` | 704 | 0.6009 | 0.6011 | -0.0002 | 3 / 5 | 0.519 | 0.160 |
| market_plus_baseline_default | `market_logit, baseline_default_logit_delta` | 704 | 0.6009 | 0.5993 | 0.0015 | 4 / 5 | 0.346 | 0.030 |
| market_plus_regularized_lgbm | `market_logit, regularized_lgbm_logit_delta` | 704 | 0.6009 | 0.5979 | 0.0030 | 4 / 5 | 0.218 | 0.012 |
| market_plus_all_models | `market_logit, baseline_default_logit_delta, regularized_lgbm_logit_delta` | 704 | 0.6009 | 0.5983 | 0.0026 | 4 / 5 | 0.259 | 0.012 |

## Coefficients

Positive delta-feature coefficients mean the meta-model learned to move
with the saved model residual after controlling for market logit.

| Variant | Feature | Mean Coef | Std | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: |
| market_recalibrated | `intercept` | 0.0834 | 0.0283 | 0.0517 | 0.1217 |
| market_recalibrated | `market_logit` | 1.2285 | 0.0443 | 1.1738 | 1.2918 |
| market_plus_baseline_default | `intercept` | 0.0883 | 0.0263 | 0.0574 | 0.1244 |
| market_plus_baseline_default | `market_logit` | 1.3203 | 0.0318 | 1.2650 | 1.3480 |
| market_plus_baseline_default | `baseline_default_logit_delta` | 0.2113 | 0.0938 | 0.0865 | 0.3485 |
| market_plus_regularized_lgbm | `intercept` | 0.0880 | 0.0265 | 0.0575 | 0.1251 |
| market_plus_regularized_lgbm | `market_logit` | 1.3634 | 0.0490 | 1.2787 | 1.4287 |
| market_plus_regularized_lgbm | `regularized_lgbm_logit_delta` | 0.2616 | 0.1365 | 0.1041 | 0.4529 |
| market_plus_all_models | `intercept` | 0.0876 | 0.0270 | 0.0547 | 0.1248 |
| market_plus_all_models | `market_logit` | 1.3470 | 0.0482 | 1.2714 | 1.4123 |
| market_plus_all_models | `baseline_default_logit_delta` | 0.1259 | 0.0648 | 0.0636 | 0.2484 |
| market_plus_all_models | `regularized_lgbm_logit_delta` | 0.1232 | 0.1669 | -0.1436 | 0.3127 |

## Interpretation

The strongest variant by holdout log-loss delta was `market_plus_regularized_lgbm` with
Delta LL `0.0030`.
Its market-null p-value was `0.012` before and `0.048` after a simple Bonferroni correction across `4` variants.

This is an incremental-information test, not a betting-policy selector.
It should be read alongside the disagreement and paper-tracking audits.
