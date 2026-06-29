# Residual Directional Gate Audit

This audit tests whether a simple drift-aware residual transform can be
selected without looking at the evaluation fold. For each future fold,
it chooses separate scales for upward and downward residual logit
adjustments using only prior folds, then evaluates the chosen gate.

## Inputs

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- scale grid: `[0.0, 0.5, 1.0]`
- directional candidates: `9`
- event-bootstrap iterations: `20000`
- market-null iterations: `10000`

## Key Diagnostics

- Rolling directional selection chose `up1_down0`, `up1_down0.5`, `up1_down1` across folds 2-5.
- Combined rolling evaluation: delta LL `0.0012`, bootstrap P(delta <= 0) `0.366`, market-null p `0.072`.
- Latest fold selected `up1_down1` and scored delta LL `-0.0047`.
- On the same folds 2-5 evaluation set, selected_shrinkage scored delta LL `0.0028`; the rolling gate scored `0.0012`.
- The best fixed latest-fold gate was `up0_down1` with delta LL `0.0080`, but that is visible only after seeing fold 5.

## Fixed Candidate Summary

| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| market | 704 | 0.6009 | 0.6009 | 0.0000 | 0.00% | 1.000 |
| selected_shrinkage | 704 | 0.6009 | 0.5971 | 0.0038 | 1.49% | 0.143 |
| up0_down1 | 704 | 0.6009 | 0.5986 | 0.0023 | -1.07% | 0.082 |
| up1_down0 | 704 | 0.6009 | 0.5995 | 0.0014 | 2.56% | 0.331 |
| up0_down0.5 | 704 | 0.6009 | 0.5994 | 0.0015 | -0.55% | 0.040 |
| up0.5_down1 | 704 | 0.6009 | 0.5970 | 0.0039 | 0.25% | 0.040 |

## Folds 2-5 Fixed Candidate Baselines

| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| market | 539 | 0.6022 | 0.6022 | 0.0000 | 0.00% | 1.000 |
| selected_shrinkage | 539 | 0.6022 | 0.5994 | 0.0028 | 1.65% | 0.253 |
| up0_down1 | 539 | 0.6022 | 0.5980 | 0.0042 | -0.96% | 0.006 |
| up1_down0 | 539 | 0.6022 | 0.6036 | -0.0015 | 2.61% | 0.642 |
| up0_down0.5 | 539 | 0.6022 | 0.5998 | 0.0024 | -0.49% | 0.003 |
| up0.5_down1 | 539 | 0.6022 | 0.5978 | 0.0044 | 0.38% | 0.041 |

## Latest Fold Fixed Candidates

| Candidate | Fights | Market LL | Candidate LL | Delta LL | Mean Adj |
| --- | ---: | ---: | ---: | ---: | ---: |
| market | 129 | 0.6273 | 0.6273 | 0.0000 | 0.00% |
| selected_shrinkage | 129 | 0.6273 | 0.6320 | -0.0047 | 0.93% |
| up0_down1 | 129 | 0.6273 | 0.6192 | 0.0080 | -1.37% |
| up1_down0 | 129 | 0.6273 | 0.6400 | -0.0128 | 2.30% |
| up0_down0.5 | 129 | 0.6273 | 0.6229 | 0.0044 | -0.70% |
| up0.5_down1 | 129 | 0.6273 | 0.6248 | 0.0025 | -0.19% |

## Rolling Directional Gate

| Eval Fold | Selected Gate | Dev Delta LL | Eval Fights | Eval Delta LL | Eval Mean Adj |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `up1_down0` | 0.0108 | 130 | 0.0052 | 2.87% |
| 3 | `up1_down0` | 0.0083 | 150 | 0.0017 | 3.06% |
| 4 | `up1_down0.5` | 0.0062 | 130 | 0.0026 | 1.72% |
| 5 | `up1_down1` | 0.0057 | 129 | -0.0047 | 0.93% |

| Combined Eval | Fights | Market LL | Candidate LL | Delta LL | Mean Adj | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected gates | 539 | 0.6022 | 0.6010 | 0.0012 | 2.18% | 0.366 | 0.072 |

## Interpretation

- This is an exploratory validation audit, not a frozen policy change.
- A useful drift-aware transform should improve the latest fold while preserving positive rolling selection evidence.
- If rolling selection keeps choosing the original full adjustment, the calibration drift cannot be fixed by this simple gate.
- If it mutes upward adjustments only after the damage is already visible, the result is still historical and needs future paper validation.
