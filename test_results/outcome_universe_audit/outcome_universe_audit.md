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

Women-pair rows are counted by fighter identity learned from raw rows whose titles contain `Women`.

| Dataset | Women's Title Rows | Known Women-Pair Rows | Hidden Women-Pair Rows |
| --- | ---: | ---: | ---: |
| data/fight_details_date.csv | 931 | 940 | 9 |
| data/modified_fight_details.csv | 0 | 9 | 9 |
| data/detailed_fights.csv | 0 | 0 | 0 |

Hidden women-pair rows are bouts such as catchweights where the title does not contain `Women` even though both fighters are known from women's divisions.

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
| latest-prior non-binary `last_fight` checks | 157 |
| latest-prior non-binary `last_fight` matches | 157 |
| weighted stat checks where non-binary changed the value | 3697 |
| weighted stat matches including non-binary | 3697 |

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

Examples where the latest prior fight was non-binary and still drove `last_fight`:

| Date | Fighter | Side | Feature Last Fight | Prior Non-Binary Date | Expected Days | Fight |
| --- | --- | --- | ---: | --- | ---: | --- |
| November 02, 2001 | Bobby Hoffman | Red | 252 | 2001-02-23 | 252 | Heavyweight Bout |
| January 31, 2004 | BJ Penn | Blue | 337 | 2003-02-28 | 337 | UFC Welterweight Title Bout |
| May 27, 2006 | Royce Gracie | Red | 4068 | 1995-04-07 | 4068 | Catch Weight Bout |
| November 17, 2007 | Rashad Evans | Blue | 133 | 2007-07-07 | 133 | Light Heavyweight Bout |
| May 24, 2008 | Tito Ortiz | Red | 322 | 2007-07-07 | 322 | Light Heavyweight Bout |
| March 31, 2010 | Nik Lentz | Blue | 79 | 2010-01-11 | 79 | Lightweight Bout |
| March 31, 2010 | Caol Uno | Blue | 130 | 2009-11-21 | 130 | Lightweight Bout |
| November 20, 2010 | Karo Parisyan | Blue | 658 | 2009-01-31 | 658 | Welterweight Bout |

Examples where cumulative weighted fight stats match the calculation that includes prior non-binary bouts:

| Date | Fighter | Side | Feature | Processed | Including Non-Binary | Binary Only | Fight |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| November 02, 2001 | Bobby Hoffman | Red | Sig. str. | 4.771014 | 4.771014 | 0.666667 | Heavyweight Bout |
| November 02, 2001 | Bobby Hoffman | Red | Total str. | 15.160580 | 15.160580 | 1.600000 | Heavyweight Bout |
| November 02, 2001 | Bobby Hoffman | Red | Td | 0.053333 | 0.053333 | 0.266667 | Heavyweight Bout |
| January 11, 2002 | Jens Pulver | Blue | Sig. str. | 2.068053 | 2.068053 | 1.874452 | UFC Lightweight Title Bout |
| January 11, 2002 | Jens Pulver | Blue | Total str. | 4.006834 | 4.006834 | 3.921827 | UFC Lightweight Title Bout |
| January 11, 2002 | Jens Pulver | Blue | Td | 0.017163 | 0.017163 | 0.007099 | UFC Lightweight Title Bout |
| September 27, 2002 | Benji Radach | Red | Sig. str. | 5.831111 | 5.831111 | 1.733333 | Welterweight Bout |
| September 27, 2002 | Benji Radach | Red | Total str. | 8.017778 | 8.017778 | 4.466667 | Welterweight Bout |

## Interpretation

- The current production feature table is men-only: `data/detailed_fights.csv` has zero women's title rows and zero known women-pair rows.
- Future preprocessing/backtests now treat `Women` title matching as fighter-aware, so women-vs-women catchweights are not missed just because the title omits `Women`.
- The current regularized backtests also exclude women's odds rows via `excluded_title_patterns = ["Women"]`.
- Draw/no-contest/overturned rows are absent from supervised labels, which remain binary `win/loss` only.
- Those same non-binary rows are still reflected in future fighter state: checked future fighter-side rows matched prior source fight counts, `last_fight`, and weighted cumulative stat calculations that include non-binary bouts.

This supports the current universe handling: do not train/evaluate on women's fights for the production edge claim, and keep non-binary outcomes as historical state inputs but not supervised labels.
