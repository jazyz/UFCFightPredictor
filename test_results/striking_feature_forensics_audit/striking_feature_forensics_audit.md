# Striking Feature Forensics Audit

This audit reconstructs the exact frozen striking-core feature columns
from chronological fight details and checks whether their market residual
shape looks coherent. It does not select or train a new production model.

## Feature Definitions Checked

- `Sig. str.% differential`: weighted average of prior fight significant-strike accuracy minus opponent significant-strike accuracy.
- `Sig. str. differential`: weighted average of prior fight significant strikes landed minus opponent significant strikes landed.
- `Head differential`: weighted average of prior fight head strikes landed minus opponent head strikes landed.
- Each prior fight is weighted by the fighter's chronological fight number squared, then divided by the triangular square sum of prior fights.
- The frozen `oppdiff` feature is the red fighter's pre-fight differential minus the blue fighter's pre-fight differential.

## Reconstruction Checks

| Check | Value |
| --- | ---: |
| source rows | 7730 |
| feature rows | 4322 |
| non-binary source rows | 154 |
| expected supervised feature rows | 4322 |
| matched supervised feature rows | 4322 |
| missing feature rows | 0 |
| extra feature rows | 0 |
| supervised rows with prior non-binary state | 1138 |
| hard reconstruction failures | 0 |

| Feature | Side Checks | Side Mismatches | Side Max Error | Oppdiff Checks | Oppdiff Mismatches | Oppdiff Max Error | Binary-Only Changed Rows | Mean Abs Nonbinary Change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Sig. str.%` | 8644 | 0 | 0.00000000 | 4322 | 0 | 0.00000000 | 1138 | 0.028064 |
| `Sig. str.` | 8644 | 0 | 0.00000000 | 4322 | 0 | 0.00000000 | 1138 | 2.783916 |
| `Head` | 8644 | 0 | 0.00000000 | 4322 | 0 | 0.00000000 | 1136 | 2.175472 |

## Market Residual Shape

| Feature | Rows | Spearman vs Actual-Market | Low Bin A-M | High Bin A-M | High-Low | p01 | p50 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Sig. str.% differential oppdiff` | 1223 | 0.0625 | -6.53% | 6.45% | 12.98% | -0.4017 | 0.0013 | 0.4010 |
| `Sig. str. differential oppdiff` | 1223 | 0.0291 | -5.66% | 5.99% | 11.65% | -50.9488 | 0.0866 | 49.4200 |
| `Head differential oppdiff` | 1223 | 0.0360 | -5.57% | 5.43% | 11.00% | -41.2375 | 0.1440 | 39.0300 |

### `Sig. str.% differential oppdiff` Bins

| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 245 | -0.6315 to -0.1344 | 38.37% | 44.89% | -6.53% |
| 2 | 244 | -0.1341 to -0.0435 | 43.03% | 45.91% | -2.88% |
| 3 | 245 | -0.0433 to 0.0457 | 50.20% | 50.41% | -0.21% |
| 4 | 244 | 0.0460 to 0.1280 | 59.02% | 53.81% | 5.21% |
| 5 | 245 | 0.1282 to 0.7506 | 63.67% | 57.22% | 6.45% |

### `Sig. str. differential oppdiff` Bins

| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 245 | -74.8036 to -13.4518 | 36.73% | 42.39% | -5.66% |
| 2 | 244 | -13.4452 to -3.7500 | 47.95% | 47.39% | 0.57% |
| 3 | 245 | -3.7261 to 3.3797 | 52.24% | 50.60% | 1.64% |
| 4 | 244 | 3.4282 to 12.0740 | 53.28% | 53.79% | -0.51% |
| 5 | 245 | 12.1108 to 59.1199 | 64.08% | 58.09% | 5.99% |

### `Head differential oppdiff` Bins

| Bin | Rows | Feature Range | Actual Red Win | Mean Market P | Actual - Market |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 245 | -58.9571 to -11.2919 | 37.14% | 42.71% | -5.57% |
| 2 | 244 | -11.2794 to -3.4860 | 45.08% | 46.54% | -1.46% |
| 3 | 245 | -3.4774 to 3.3917 | 53.88% | 51.96% | 1.92% |
| 4 | 244 | 3.3923 to 10.3429 | 55.74% | 54.02% | 1.72% |
| 5 | 245 | 10.4175 to 70.4134 | 62.45% | 57.02% | 5.43% |

## Experience Split

| Min Prior Fights | Rows | Mean Actual-Market | Sig% Spearman | Sig Raw Spearman | Head Spearman |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2-4 | 493 | -1.95% | 0.0922 | 0.0080 | 0.0483 |
| 5-9 | 480 | 2.57% | 0.0100 | 0.0445 | 0.0286 |
| 10+ | 250 | 0.92% | 0.0853 | 0.0379 | 0.0348 |

## Spearman Correlations Between Frozen Feature Inputs

| Feature Pair | Correlation |
| --- | ---: |
| `Sig. str. differential oppdiff` vs `Sig. str.% differential oppdiff` | 0.3949 |
| `Head differential oppdiff` vs `Sig. str.% differential oppdiff` | 0.2716 |
| `Head differential oppdiff` vs `Sig. str. differential oppdiff` | 0.7539 |

## Interpretation

- Reconstruction found zero hard mismatches for the frozen striking-core side and oppdiff columns.
- Non-binary outcomes do not create supervised training rows here, but they do flow into later striking state when fighters have prior draws/no contests/overturns.
- All three frozen inputs have positive top-minus-bottom quintile market-residual spreads, which is directionally coherent with the fight meaning of better prior striking differential.
- The rank correlations to market residual are small, and raw significant-strike differential is strongly correlated with head-strike differential, so this supports a weak compact feature clue rather than three independent alphas.
- The residual-shape tables are descriptive diagnostics, not a fresh strategy-selection result.
