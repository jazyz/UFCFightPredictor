# Residual Edge Concentration Audit

This diagnostic asks whether the residual market/meta log-loss edge is broad
or concentrated in a small number of events/fights. `Delta LL` is market
log loss minus candidate log loss; positive means the residual candidate
beat the market.

## Input

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- rows: `704`
- policies: `selected_shrinkage, fixed_half_residual, unshrunk_meta`

## Policy Summary

| Policy | Fights | Events | Candidate LL | Delta LL | Positive Fights | Positive Events | Events To Erase Edge | Top-10 Positive Share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selected_shrinkage | 704 | 102 | 0.5971 | 0.0038 | 65.8% | 63.7% | 7 | 34.3% |
| fixed_half_residual | 704 | 102 | 0.5979 | 0.0030 | 65.8% | 64.7% | 11 | 32.3% |
| unshrunk_meta | 704 | 102 | 0.5979 | 0.0030 | 65.8% | 62.7% | 5 | 33.5% |

## Removal Sensitivity

| Policy | Remove Top Events | Removed Fights | Remaining Delta LL | Remaining Sum Delta |
| --- | ---: | ---: | ---: | ---: |
| selected_shrinkage | 1 | 9 | 0.0031 | 2.1669 |
| selected_shrinkage | 3 | 25 | 0.0019 | 1.2687 |
| selected_shrinkage | 5 | 39 | 0.0007 | 0.4979 |
| selected_shrinkage | 10 | 81 | -0.0020 | -1.2202 |
| fixed_half_residual | 1 | 7 | 0.0026 | 1.8209 |
| fixed_half_residual | 3 | 25 | 0.0020 | 1.3546 |
| fixed_half_residual | 5 | 39 | 0.0014 | 0.9549 |
| fixed_half_residual | 10 | 82 | 0.0000 | 0.0295 |
| unshrunk_meta | 1 | 7 | 0.0022 | 1.5066 |
| unshrunk_meta | 3 | 25 | 0.0009 | 0.5891 |
| unshrunk_meta | 5 | 39 | -0.0003 | -0.1817 |
| unshrunk_meta | 10 | 82 | -0.0032 | -1.9720 |

## Year And Fold Deltas

| Policy | Group | Fights | Delta LL | Sum Delta |
| --- | --- | ---: | ---: | ---: |
| selected_shrinkage | year 2024 | 275 | 0.0098 | 2.7046 |
| selected_shrinkage | year 2025 | 285 | 0.0016 | 0.4617 |
| selected_shrinkage | year 2026 | 144 | -0.0036 | -0.5228 |
| selected_shrinkage | fold 1 | 165 | 0.0070 | 1.1590 |
| selected_shrinkage | fold 2 | 130 | 0.0077 | 1.0066 |
| selected_shrinkage | fold 3 | 150 | 0.0026 | 0.3942 |
| selected_shrinkage | fold 4 | 130 | 0.0053 | 0.6935 |
| selected_shrinkage | fold 5 | 129 | -0.0047 | -0.6098 |
| fixed_half_residual | year 2024 | 275 | 0.0059 | 1.6196 |
| fixed_half_residual | year 2025 | 285 | 0.0024 | 0.6751 |
| fixed_half_residual | year 2026 | 144 | -0.0011 | -0.1643 |
| fixed_half_residual | fold 1 | 165 | 0.0046 | 0.7631 |
| fixed_half_residual | fold 2 | 130 | 0.0050 | 0.6505 |
| fixed_half_residual | fold 3 | 150 | 0.0027 | 0.4013 |
| fixed_half_residual | fold 4 | 130 | 0.0042 | 0.5482 |
| fixed_half_residual | fold 5 | 129 | -0.0018 | -0.2326 |
| unshrunk_meta | year 2024 | 275 | 0.0098 | 2.7046 |
| unshrunk_meta | year 2025 | 285 | 0.0018 | 0.5063 |
| unshrunk_meta | year 2026 | 144 | -0.0077 | -1.1037 |
| unshrunk_meta | fold 1 | 165 | 0.0070 | 1.1590 |
| unshrunk_meta | fold 2 | 130 | 0.0077 | 1.0066 |
| unshrunk_meta | fold 3 | 150 | 0.0026 | 0.3942 |
| unshrunk_meta | fold 4 | 130 | 0.0057 | 0.7458 |
| unshrunk_meta | fold 5 | 129 | -0.0093 | -1.1983 |

## Top Selected-Shrinkage Events

| Event | Fights | Sum Delta | Mean Delta |
| --- | ---: | ---: | ---: |
| 2024-08-03 | 9 | 0.4766 | 0.0530 |
| 2026-06-27 | 7 | 0.4572 | 0.0653 |
| 2025-04-26 | 9 | 0.4409 | 0.0490 |
| 2025-06-07 | 6 | 0.3898 | 0.0650 |
| 2024-06-01 | 8 | 0.3810 | 0.0476 |
| 2024-10-26 | 10 | 0.3599 | 0.0360 |
| 2024-12-07 | 13 | 0.3584 | 0.0276 |
| 2024-06-29 | 6 | 0.3435 | 0.0572 |
| 2024-02-17 | 6 | 0.3317 | 0.0553 |
| 2025-05-10 | 7 | 0.3247 | 0.0464 |

## Worst Selected-Shrinkage Events

| Event | Fights | Sum Delta | Mean Delta |
| --- | ---: | ---: | ---: |
| 2025-01-18 | 8 | -0.8256 | -0.1032 |
| 2025-07-19 | 9 | -0.6537 | -0.0726 |
| 2025-07-26 | 8 | -0.6365 | -0.0796 |
| 2026-05-09 | 12 | -0.4592 | -0.0383 |
| 2024-10-19 | 6 | -0.4162 | -0.0694 |
| 2025-03-01 | 6 | -0.4079 | -0.0680 |
| 2025-08-23 | 9 | -0.3743 | -0.0416 |
| 2026-04-25 | 7 | -0.3477 | -0.0497 |
| 2025-02-15 | 7 | -0.3470 | -0.0496 |
| 2025-10-11 | 7 | -0.3141 | -0.0449 |

## Interpretation

The residual probability edge is not a broad, high-margin effect. For the
`selected_shrinkage` policy, the aggregate Delta LL is positive, but the
top five positive events reduce it to a very small value when removed,
and the top ten positive events erase it entirely. The fixed-half
residual policy is slightly less volatile, but still depends heavily
on the top event cluster.

Practical read: this supports continued paper tracking of the residual
hypothesis, not live staking confidence. Future evidence should be judged
by whether post-freeze gains are broad across cards and years, not only
by aggregate log loss or PnL.
