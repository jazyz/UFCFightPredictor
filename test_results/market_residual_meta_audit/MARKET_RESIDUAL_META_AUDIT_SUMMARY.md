# Market Residual Meta Audit Summary

Run date: 2026-06-28.

## Purpose

This audit tests whether the saved leak-safe model probabilities contain
incremental information beyond de-vigged market probabilities.

It does not retrain the base UFC model. It aligns the saved long ledgers by
fight, then trains only a small logistic meta-model inside each forward
development window. The main residual feature is:

```text
logit(model probability) - logit(market probability)
```

Positive holdout `Delta LL` means:

```text
market log loss - meta-model log loss > 0
```

## Inputs

```text
test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv
test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv
```

Aligned fights: `1220`.

## Primary Result

Primary protocol:

- development window: `730` days
- holdout window: `182` days
- folds: `5`
- logistic L2 inverse regularization: `C = 1.0`
- market-null simulations: `1000`

| Variant | Market LL | Meta LL | Delta LL | Positive Folds | Event Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| market recalibrated | 0.6009 | 0.6011 | -0.0002 | 3 / 5 | 0.519 | 0.160 |
| market + baseline residual | 0.6009 | 0.5993 | +0.0015 | 4 / 5 | 0.346 | 0.030 |
| market + regularized residual | 0.6009 | 0.5979 | +0.0030 | 4 / 5 | 0.218 | 0.012 |
| market + both residuals | 0.6009 | 0.5983 | +0.0026 | 4 / 5 | 0.259 | 0.012 |

The strongest primary variant is `market + regularized residual`. Its
uncorrected market-null p-value is `0.012`; a simple Bonferroni correction
across the four primary variants gives about `0.048`.

Mean regularized-residual coefficient across folds: `+0.2616`.

## Sensitivity Checks

The regularized-residual variant stayed positive under two nearby protocol
checks:

| Config | Market LL | Meta LL | Delta LL | Positive Folds | Event Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 730d dev, C=1.0 | 0.6009 | 0.5979 | +0.0030 | 4 / 5 | 0.218 | 0.012 |
| 365d dev, C=1.0 | 0.6009 | 0.5962 | +0.0047 | 4 / 5 | 0.126 | 0.003 |
| 730d dev, C=0.25 | 0.6009 | 0.5981 | +0.0028 | 4 / 5 | 0.173 | 0.012 |

These sensitivity checks support the direction of the signal. They should not
be used to pick the best configuration after the fact.

## Interpretation

This is the strongest current evidence that the model has a small probability
edge over the market after controlling for market price. It is more favorable
than the earlier fixed-weight blend audit, which selected pure market on the
long split.

The caveat is important: the absolute log-loss gain is small, and event
bootstrap intervals still cross zero. This is not yet a live betting edge
claim. It is a good candidate for a frozen forward probability transform and a
future paper-tracked betting policy.

Recommended next step: freeze one conservative residual meta transform before
looking at future results, then evaluate future cards against market log loss,
market-null simulations, and a predeclared PnL policy.
