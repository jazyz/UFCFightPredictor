# Outcome Universe Audit

This audit verifies that the current production universe excludes women's
fights while draw/no-contest/overturned bouts still update future fighter
state without becoming supervised training labels.

## Dataset Universe

| Dataset | Rows | Women's Title Rows | Non-Binary / Blank Winner Rows | Non-Binary Result Rows |
| --- | ---: | ---: | ---: | ---: |
| data/fight_details_date.csv | 8910 | 931 | 312 |  |
| data/modified_fight_details.csv | 7730 | 0 | 148 |  |
| data/detailed_fights.csv | 4322 | 0 |  | 0 |

## Regularized Backtest Universe

| Summary | Window | Features | Excluded Titles | Predicted Fights | Accuracy | Log Loss | PnL | Excluded Odds Rows | Non-Binary Odds Rows |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| test_results/regularized_lgbm_1y/no_leakage_backtest_summary.json | 2025-06-27 to 2026-06-27 | data/detailed_fights.csv | Women | 298 | 64.43% | 0.6418 | 24.66% | 57 | 5 |
| test_results/regularized_lgbm_2y/no_leakage_backtest_summary.json | 2024-06-27 to 2026-06-27 | data/detailed_fights.csv | Women | 580 | 65.00% | 0.6318 | 61.20% | 143 | 6 |
| test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest_summary.json | 2022-02-05 to 2026-06-27 | data/detailed_fights.csv | Women | 1249 | 63.65% | 0.6396 | 29.61% | 345 | 7 |

## Non-Binary Outcome State Check

| Metric | Value |
| --- | ---: |
| source non-binary / blank-winner rows retained | 148 |
| supervised feature non-binary labels | 0 |
| fighter-side feature rows checked | 1263 |
| rows matching source prior fights including non-binary | 1263 |
| mismatches | 0 |

Examples where a prior non-binary fight is included in future `totalfights`:

| Date | Fighter | Side | Feature TotalFights | Prior Source Fights | Prior Binary Only | Prior Non-Binary | Fight |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| November 02, 2001 | Bobby Hoffman | Red | 2 | 2 | 1 | 1 | Heavyweight Bout |
| January 11, 2002 | Jens Pulver | Blue | 6 | 6 | 5 | 1 | UFC Lightweight Title Bout |
| September 27, 2002 | Benji Radach | Red | 2 | 2 | 1 | 1 | Welterweight Bout |
| November 22, 2002 | Ken Shamrock | Blue | 5 | 5 | 3 | 2 | UFC Light Heavyweight Title Bout |
| January 31, 2004 | BJ Penn | Blue | 7 | 7 | 6 | 1 | UFC Welterweight Title Bout |
| June 19, 2004 | Ken Shamrock | Blue | 6 | 6 | 4 | 2 | Heavyweight Bout |
| April 09, 2005 | Ken Shamrock | Blue | 7 | 7 | 5 | 2 | Light Heavyweight Bout |
| March 04, 2006 | BJ Penn | Red | 8 | 8 | 7 | 1 | Welterweight Bout |
| May 27, 2006 | Royce Gracie | Red | 3 | 3 | 2 | 1 | Catch Weight Bout |
| July 08, 2006 | Ken Shamrock | Red | 8 | 8 | 6 | 2 | Light Heavyweight Bout |
| September 23, 2006 | BJ Penn | Red | 9 | 9 | 8 | 1 | UFC Welterweight Title Bout |
| October 10, 2006 | Ken Shamrock | Blue | 9 | 9 | 7 | 2 | Light Heavyweight Bout |

## Interpretation

- The current production feature table is men-only: `data/detailed_fights.csv` has zero women's title rows.
- The current regularized backtests also exclude women's odds rows via `excluded_title_patterns = ["Women"]`.
- Draw/no-contest/overturned rows are absent from supervised labels, which remain binary `win/loss` only.
- Those same non-binary rows are still reflected in future fighter state: every checked future fighter-side row matched the source prior-fight count that includes non-binary bouts.

This supports the current universe handling: do not train/evaluate on women's fights for the production edge claim, and keep non-binary outcomes as historical state inputs but not supervised labels.
