# Striking Head-Pace Semantic Audit

This exploratory audit asks whether the head pace feature adds clean,
interpretable value beyond the simpler sigpct/raw-head anchor. It does
not freeze or alter any paper policy.

## Protocol

- aligned men-only rows: `1223`
- folds: `7`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- logistic L2 C: `0.1`
- bootstrap iterations: `20000`

The residualized variant fits the head-pace residual using only each
development fold's feature values, then applies that transform to the
holdout fold before fitting the mirrored logistic model.

## Probability Results

| Variant | Features | Delta LL vs Market | Brier Delta | Accuracy | Positive Folds | Boot P(delta<=0) | Pace Term Mean Coef | Pace Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sigpct_head_raw_pm_residualized | 4 | 0.0081 | 0.0030 | 69.41% | 7/7 | 0.006 | -0.0630 | 0/7 |
| sigpct_head_raw_pm | 4 | 0.0081 | 0.0030 | 69.51% | 7/7 | 0.006 | -0.0663 | 0/7 |
| sigpct_head_raw | 3 | 0.0071 | 0.0027 | 69.41% | 7/7 | 0.013 |  |  |
| sigpct_only | 2 | 0.0056 | 0.0023 | 69.30% | 6/7 | 0.034 |  |  |
| sigpct_head_pm | 3 | 0.0056 | 0.0024 | 69.30% | 6/7 | 0.038 | -0.0007 | 4/7 |
| market_recalibrated | 1 | 0.0017 | 0.0007 | 68.68% | 4/7 | 0.221 |  |  |

## Incremental Head Pace Value

| Candidate | Base | Rows | Incremental Delta LL | Incremental Brier | Positive Folds |
| --- | --- | ---: | ---: | ---: | ---: |
| `sigpct_head_raw_pm` | `sigpct_head_raw` | 961 | 0.0010 | 0.0003 | 6/7 |
| `sigpct_head_raw_pm_residualized` | `sigpct_head_raw` | 961 | 0.0010 | 0.0003 | 6/7 |

Fold-level raw-plus-pace increment over raw-head anchor:

| Fold | Rows | Delta LL | Delta Brier |
| ---: | ---: | ---: | ---: |
| 1 | 121 | 0.0002 | 0.0000 |
| 2 | 118 | 0.0007 | 0.0002 |
| 3 | 151 | 0.0006 | 0.0003 |
| 4 | 142 | -0.0003 | -0.0002 |
| 5 | 138 | 0.0016 | -0.0004 |
| 6 | 147 | 0.0020 | 0.0008 |
| 7 | 144 | 0.0020 | 0.0010 |

## Head Pace Semantics

| Relationship | Spearman |
| --- | ---: |
| `Head differential oppdiff` vs `Head differential_pm oppdiff` | 0.6683 |
| `Sig. str.% differential oppdiff` vs `Head differential_pm oppdiff` | 0.3539 |
| global head-pace residual vs actual-minus-market | -0.0846 |

Global descriptive residual fit:

```text
Head differential_pm oppdiff ~= 0.0774 + 3.5148 * Sig. str.% differential oppdiff + 0.0840 * Head differential oppdiff
```

Conditional bins by raw head differential quintile and head-pace residual:

| Raw Bin | Pace Residual Bin | Rows | Mean Raw Head | Mean Pace Residual | Actual Red Win | Mean Market P | Actual - Market |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | low_excess_pace | 123 | -19.4887 | -1.4860 | 36.59% | 42.02% | -5.44% |
| 1 | high_excess_pace | 122 | -23.4110 | 1.4891 | 37.70% | 43.41% | -5.70% |
| 2 | low_excess_pace | 122 | -7.1913 | -1.5328 | 54.92% | 47.11% | 7.81% |
| 2 | high_excess_pace | 122 | -7.3376 | 0.7745 | 35.25% | 45.98% | -10.74% |
| 3 | low_excess_pace | 123 | 0.2240 | -1.3427 | 56.91% | 52.67% | 4.24% |
| 3 | high_excess_pace | 122 | -0.1352 | 1.4897 | 50.82% | 51.25% | -0.43% |
| 4 | low_excess_pace | 122 | 6.4357 | -1.0746 | 59.02% | 51.97% | 7.04% |
| 4 | high_excess_pace | 122 | 6.8639 | 1.8637 | 52.46% | 56.06% | -3.60% |
| 5 | low_excess_pace | 123 | 22.4044 | -1.4564 | 56.91% | 53.70% | 3.21% |
| 5 | high_excess_pace | 122 | 18.4769 | 1.3107 | 68.03% | 60.36% | 7.67% |

## Interpretation

- Adding raw `Head differential_pm oppdiff` to the clean sigpct/raw-head anchor adds only `0.0010` incremental LL over `961` evaluated fights.
- The head-pace term is highly correlated with raw head differential, so its coefficient should be read as a conditional effect rather than standalone feature importance.
- Residualized head pace does not create a clearer stronger model; the main clean signal remains sig-strike efficiency plus raw head differential.
- This supports leaving `sigpct_head_raw_pm` as a frozen paper challenger, while treating future feature work as a search for cleaner sustained-damage or duration-aware representations.
