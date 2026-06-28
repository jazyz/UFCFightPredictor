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
- development window: `365` days
- holdout window: `182` days
- logistic meta regularization C: `1.0`

## Results

`Delta LL` is `market log loss - meta log loss`; positive means the
meta-model beat the de-vigged market.

| Variant | Features | Fights | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market_recalibrated | `market_logit` | 704 | 0.6009 | 0.6001 | 0.0007 | 3 / 5 | 0.401 | 0.046 |
| market_plus_baseline_default | `market_logit, baseline_default_logit_delta` | 704 | 0.6009 | 0.5986 | 0.0023 | 4 / 5 | 0.293 | 0.011 |
| market_plus_regularized_lgbm | `market_logit, regularized_lgbm_logit_delta` | 704 | 0.6009 | 0.5962 | 0.0047 | 4 / 5 | 0.126 | 0.003 |
| market_plus_all_models | `market_logit, baseline_default_logit_delta, regularized_lgbm_logit_delta` | 704 | 0.6009 | 0.5978 | 0.0031 | 4 / 5 | 0.236 | 0.006 |

## Coefficients

Positive delta-feature coefficients mean the meta-model learned to move
with the saved model residual after controlling for market logit.

| Variant | Feature | Mean Coef | Std | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: |
| market_recalibrated | `intercept` | 0.0687 | 0.0745 | -0.0590 | 0.1507 |
| market_recalibrated | `market_logit` | 1.1907 | 0.0947 | 1.0589 | 1.2954 |
| market_plus_baseline_default | `intercept` | 0.0739 | 0.0703 | -0.0423 | 0.1517 |
| market_plus_baseline_default | `market_logit` | 1.3182 | 0.0246 | 1.2792 | 1.3518 |
| market_plus_baseline_default | `baseline_default_logit_delta` | 0.2796 | 0.1443 | 0.1369 | 0.4586 |
| market_plus_regularized_lgbm | `intercept` | 0.0736 | 0.0703 | -0.0434 | 0.1508 |
| market_plus_regularized_lgbm | `market_logit` | 1.3673 | 0.0187 | 1.3324 | 1.3830 |
| market_plus_regularized_lgbm | `regularized_lgbm_logit_delta` | 0.3309 | 0.1637 | 0.1318 | 0.5383 |
| market_plus_all_models | `intercept` | 0.0739 | 0.0699 | -0.0415 | 0.1509 |
| market_plus_all_models | `market_logit` | 1.3506 | 0.0242 | 1.3204 | 1.3793 |
| market_plus_all_models | `baseline_default_logit_delta` | 0.1811 | 0.1268 | 0.0316 | 0.3332 |
| market_plus_all_models | `regularized_lgbm_logit_delta` | 0.1441 | 0.1106 | -0.0583 | 0.2653 |

## Interpretation

The strongest variant by holdout log-loss delta was `market_plus_regularized_lgbm` with
Delta LL `0.0047`.
Its market-null p-value was `0.003` before and `0.012` after a simple Bonferroni correction across `4` variants.

This is an incremental-information test, not a betting-policy selector.
It should be read alongside the disagreement and paper-tracking audits.
