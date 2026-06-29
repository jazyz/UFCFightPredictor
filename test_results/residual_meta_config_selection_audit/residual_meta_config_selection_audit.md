# Residual Meta Config Selection Audit

This audit tests whether the residual-meta development window and
regularization choices can be selected without looking at future folds.
Each evaluation fold after fold 1 chooses the candidate with the best
prior holdout log-loss delta, then scores that candidate on the next fold.

## Inputs

| Label | Ledger |
| --- | --- |
| baseline_default | `test_results/nested_edge_long/ledgers/baseline_default_2022_2026/no_leakage_backtest.csv` |
| regularized_lgbm | `test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv` |

## Candidate Configs

| Config | Development Days | Logistic C |
| --- | ---: | ---: |
| dev365_c1.0 | 365 | 1.0 |
| dev730_c1.0 | 730 | 1.0 |
| dev730_c0.25 | 730 | 0.25 |

## Full-Holdout Candidate Results

| Candidate | Fights | Market LL | Meta LL | Delta LL | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev365_c1.0|market_plus_all_models | 704 | 0.6009 | 0.5978 | 0.0031 | 4 / 5 |
| dev365_c1.0|market_plus_baseline_default | 704 | 0.6009 | 0.5986 | 0.0023 | 4 / 5 |
| dev365_c1.0|market_plus_regularized_lgbm | 704 | 0.6009 | 0.5962 | 0.0047 | 4 / 5 |
| dev365_c1.0|market_recalibrated | 704 | 0.6009 | 0.6001 | 0.0007 | 3 / 5 |
| dev730_c0.25|market_plus_all_models | 704 | 0.6009 | 0.5985 | 0.0024 | 4 / 5 |
| dev730_c0.25|market_plus_baseline_default | 704 | 0.6009 | 0.5990 | 0.0019 | 4 / 5 |
| dev730_c0.25|market_plus_regularized_lgbm | 704 | 0.6009 | 0.5981 | 0.0028 | 4 / 5 |
| dev730_c0.25|market_recalibrated | 704 | 0.6009 | 0.6006 | 0.0003 | 2 / 5 |
| dev730_c1.0|market_plus_all_models | 704 | 0.6009 | 0.5983 | 0.0026 | 4 / 5 |
| dev730_c1.0|market_plus_baseline_default | 704 | 0.6009 | 0.5993 | 0.0015 | 4 / 5 |
| dev730_c1.0|market_plus_regularized_lgbm | 704 | 0.6009 | 0.5979 | 0.0030 | 4 / 5 |
| dev730_c1.0|market_recalibrated | 704 | 0.6009 | 0.6011 | -0.0002 | 3 / 5 |

## Rolling Selection Result

| Metric | Value |
| --- | ---: |
| eval folds | 4 |
| fights | 539 |
| events | 79 |
| market log loss | 0.6022 |
| selected meta log loss | 0.6017 |
| market - selected meta log loss | 0.0005 |
| positive eval folds | 3 / 4 |
| event-bootstrap P(delta <= 0) | 0.458 |
| rolling market-null p | 0.084 |

## Fold Selections

| Eval Fold | Selected Candidate | Prior Delta LL | Eval Fights | Eval Delta LL |
| ---: | --- | ---: | ---: | ---: |
| 2 | dev730_c1.0|market_plus_baseline_default | 0.0071 | 130 | 0.0071 |
| 3 | dev365_c1.0|market_plus_regularized_lgbm | 0.0076 | 150 | 0.0042 |
| 4 | dev365_c1.0|market_plus_all_models | 0.0066 | 130 | 0.0018 |
| 5 | dev730_c1.0|market_plus_all_models | 0.0058 | 129 | -0.0118 |

## Interpretation

This is a configuration-selection audit, not a new betting-policy search.
A positive result means the residual-meta setup choice had a plausible
prior-fold selection path. It still remains historical evidence and
should not replace post-freeze paper tracking.
