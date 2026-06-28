# Frozen Market Residual Meta Transform

As-of date: `2026-06-28`
Training window: `2024-06-28` to `2026-06-27`
Base model residual: `regularized_lgbm`
Logistic L2 inverse regularization C: `0.25`
Source audit: `test_results/market_residual_meta_audit/MARKET_RESIDUAL_META_AUDIT_SUMMARY.md`

This is a frozen forward probability-transform contract. It should be
used only for future paper tracking until enough post-freeze outcomes
accrue. Do not refit or alter this artifact after future outcomes are
known.

## Formula

```text
market_logit = logit(de-vigged market probability)
regularized_lgbm_logit_delta = logit(regularized_lgbm probability) - market_logit
meta_logit = intercept + sum(coefficient_i * feature_i)
meta_probability = sigmoid(meta_logit)
```

## Coefficients

| Term | Value |
| --- | ---: |
| intercept | -0.00677046 |
| `market_logit` | 1.21510222 |
| `regularized_lgbm_logit_delta` | 0.31975697 |

## Training-Window Diagnostics

These are fit diagnostics on the frozen training window, not fresh
evidence of edge. The out-of-sample evidence is in the source audit.

| Metric | Value |
| --- | ---: |
| rows | 577 |
| actual red win rate | 49.91% |
| market log loss | 0.5995 |
| frozen meta log loss | 0.5943 |
| market - meta log loss | 0.0052 |

## Frozen Rules

- Use the exact feature columns, coefficients, intercept, and de-vigging convention above.
- Keep the base model label fixed to the saved `regularized_lgbm` probability stream unless a new pre-outcome freeze replaces this artifact.
- Score future outcomes against market log loss, market-null simulations, and any predeclared PnL policy without changing this transform.
