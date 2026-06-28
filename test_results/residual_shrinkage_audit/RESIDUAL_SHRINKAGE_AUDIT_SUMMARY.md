# Residual Shrinkage Audit

This audit asks whether residual shrinkage can be chosen without looking
at future holdout outcomes. Each outer fold first fits the residual meta
model on the first part of the development window, selects a shrinkage
on the later development slice, refits on the full development window,
then evaluates the frozen shrinkage on the future holdout.

## Protocol

- model residual label: `regularized_lgbm`
- feature columns: `market_logit, regularized_lgbm_logit_delta`
- aligned fights: `1220`
- evaluated holdout fights: `704`
- outer folds evaluated: `5`
- development window: `730` days
- inner train window: `365` days
- holdout window: `182` days
- shrinkage grid: `0.0, 0.25, 0.5, 0.75, 1.0`
- logistic meta C: `1.0`

## Results

`Delta LL` is `market log loss - candidate log loss`; positive means the
candidate beat the de-vigged market.

| Policy | Fights | Log Loss | Brier | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market | 704 | 0.6009 | 0.2067 | 0.0000 | 0 / 5 |  |  |
| selected_shrinkage | 704 | 0.5971 | 0.2049 | 0.0038 | 4 / 5 | 0.140 | 0.005 |
| fixed_half_residual | 704 | 0.5979 | 0.2053 | 0.0030 | 4 / 5 | 0.051 | 0.015 |
| unshrunk_meta | 704 | 0.5979 | 0.2050 | 0.0030 | 4 / 5 | 0.218 | 0.015 |

## Fold Selection

| Fold | Holdout | Inner Train | Selection | Selected Shrinkage | Selection Best LL | Holdout Delta LL |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2024-02-05 to 2024-08-04 | 272 | 244 | 1.00 | 0.5952 | 0.0070 |
| 2 | 2024-08-05 to 2025-02-02 | 252 | 276 | 1.00 | 0.5868 | 0.0077 |
| 3 | 2025-02-03 to 2025-08-03 | 248 | 295 | 1.00 | 0.5821 | 0.0026 |
| 4 | 2025-08-04 to 2026-02-01 | 284 | 280 | 0.75 | 0.5964 | 0.0053 |
| 5 | 2026-02-02 to 2026-06-27 | 299 | 280 | 0.75 | 0.5981 | -0.0047 |

## Market-Null Selection Frequency

| Shrinkage | Frequency |
| ---: | ---: |
| 0.0 | 0.561 |
| 0.25 | 0.140 |
| 0.5 | 0.104 |
| 0.75 | 0.073 |
| 1.0 | 0.122 |

## Interpretation

The nested selected-shrinkage policy is the least post-hoc version of
this test. Fixed half residual is shown as a sensitivity because the
negative-control audit hinted at it, but it was not selected by this
audit protocol.

Selected shrinkage Delta LL: `0.0038`.
Fixed half-residual Delta LL: `0.0030`.
Unshrunk residual-meta Delta LL: `0.0030`.

Do not treat this as a betting edge by itself; it is a probability
translation audit that should feed the forward paper-policy evidence.
