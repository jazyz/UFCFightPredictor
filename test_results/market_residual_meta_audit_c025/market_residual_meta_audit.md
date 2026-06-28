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
- logistic meta regularization C: `0.25`

## Results

`Delta LL` is `market log loss - meta log loss`; positive means the
meta-model beat the de-vigged market.

| Variant | Features | Fights | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market_recalibrated | `market_logit` | 704 | 0.6009 | 0.6006 | 0.0003 | 2 / 5 | 0.454 | 0.106 |
| market_plus_baseline_default | `market_logit, baseline_default_logit_delta` | 704 | 0.6009 | 0.5990 | 0.0019 | 4 / 5 | 0.272 | 0.021 |
| market_plus_regularized_lgbm | `market_logit, regularized_lgbm_logit_delta` | 704 | 0.6009 | 0.5981 | 0.0028 | 4 / 5 | 0.173 | 0.012 |
| market_plus_all_models | `market_logit, baseline_default_logit_delta, regularized_lgbm_logit_delta` | 704 | 0.6009 | 0.5985 | 0.0024 | 4 / 5 | 0.227 | 0.016 |

## Coefficients

Positive delta-feature coefficients mean the meta-model learned to move
with the saved model residual after controlling for market logit.

| Variant | Feature | Mean Coef | Std | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: |
| market_recalibrated | `intercept` | 0.0837 | 0.0280 | 0.0508 | 0.1215 |
| market_recalibrated | `market_logit` | 1.1660 | 0.0354 | 1.1214 | 1.2152 |
| market_plus_baseline_default | `intercept` | 0.0873 | 0.0262 | 0.0571 | 0.1231 |
| market_plus_baseline_default | `market_logit` | 1.2339 | 0.0284 | 1.1832 | 1.2578 |
| market_plus_baseline_default | `baseline_default_logit_delta` | 0.1658 | 0.0847 | 0.0530 | 0.2887 |
| market_plus_regularized_lgbm | `intercept` | 0.0865 | 0.0266 | 0.0562 | 0.1228 |
| market_plus_regularized_lgbm | `market_logit` | 1.2531 | 0.0413 | 1.1822 | 1.3082 |
| market_plus_regularized_lgbm | `regularized_lgbm_logit_delta` | 0.1777 | 0.1182 | 0.0426 | 0.3424 |
| market_plus_all_models | `intercept` | 0.0867 | 0.0267 | 0.0556 | 0.1227 |
| market_plus_all_models | `market_logit` | 1.2429 | 0.0398 | 1.1776 | 1.2965 |
| market_plus_all_models | `baseline_default_logit_delta` | 0.1403 | 0.0452 | 0.0715 | 0.2006 |
| market_plus_all_models | `regularized_lgbm_logit_delta` | 0.0382 | 0.1131 | -0.1364 | 0.1710 |

## Interpretation

The strongest variant by holdout log-loss delta was `market_plus_regularized_lgbm` with
Delta LL `0.0028`.
Its market-null p-value was `0.012` before and `0.048` after a simple Bonferroni correction across `4` variants.

This is an incremental-information test, not a betting-policy selector.
It should be read alongside the disagreement and paper-tracking audits.
