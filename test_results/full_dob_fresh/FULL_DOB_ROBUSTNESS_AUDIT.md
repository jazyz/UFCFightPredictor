# Full-DOB Robustness Audit

Date run: 2026-06-28

## Purpose

This audit reruns the leak-safe rolling backtests from scratch after restoring
the seven previously masked DOB/age feature rows:

- Andrey Pulyaev
- Brando Pericic
- Chris Padilla
- Jose Ochoa
- Josh Hokit
- Kaan Ofli
- Myktybek Orolbai

The normal `data/detailed_fights.csv` still masks these rows through
`data/excluded_fighter_dobs.csv`. The fresh feature file here was generated
with `--include-excluded-dobs`, then every backtest was run with
`--include-excluded-dobs` so the loader did not mask them again.

## Generated Artifacts

- Full-DOB feature table: `test_results/full_dob_fresh/detailed_fights_full_dobs.csv`
- Full-DOB fighter stats: `test_results/full_dob_fresh/detailed_fighter_stats_full_dobs.csv`
- Fresh backtest ledgers: `test_results/full_dob_fresh/backtests/*/no_leakage_backtest.csv`
- Fresh statistical audit: `test_results/full_dob_fresh/statistical_edge_audit/edge_audit.md`

## Commands

```bash
.venv/bin/python process_fights_alpha.py \
  --include-excluded-dobs \
  --output-features test_results/full_dob_fresh/detailed_fights_full_dobs.csv \
  --output-fighter-stats test_results/full_dob_fresh/detailed_fighter_stats_full_dobs.csv \
  --output-processed-readable test_results/full_dob_fresh/readable/processed_fights_readable.txt \
  --output-fighter-readable test_results/full_dob_fresh/readable/fighter_stats_readable.txt
```

Each backtest used:

```text
--features test_results/full_dob_fresh/detailed_fights_full_dobs.csv
--include-excluded-dobs
```

The fresh statistical audit used 50,000 market-null/bootstrap iterations:

```bash
.venv/bin/python testing/statistical_edge_audit.py \
  test_results/full_dob_fresh/backtests/*/no_leakage_backtest.csv \
  --iterations 50000 \
  --output-dir test_results/full_dob_fresh/statistical_edge_audit
```

## DOB Restoration Check

Compared with `data/detailed_fights.csv`, the full-DOB feature file restores
known `age`, `dob`, and `avg age` values for all rows involving the seven
formerly masked fighters:

| Fighter | Rows in Full-DOB File | Rows With Known Age/DOB/Avg Age |
| --- | ---: | ---: |
| Andrey Pulyaev | 2 | 2 |
| Brando Pericic | 1 | 1 |
| Chris Padilla | 2 | 2 |
| Jose Ochoa | 2 | 2 |
| Josh Hokit | 2 | 2 |
| Kaan Ofli | 2 | 2 |
| Myktybek Orolbai | 3 | 3 |

## Fresh Results

| Run | Window | Accuracy | Log Loss | Profit | Market-Null p | Event Bootstrap Profit CI |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| default_1y | 2025-06-27 to 2026-06-27 | 59.7% | 0.661 | -$49.36 | 0.506 | -$502.69 to $432.60 |
| edge2_no_flat_1y | 2025-06-27 to 2026-06-27 | 59.7% | 0.661 | -$50.56 | 0.540 | -$502.51 to $432.01 |
| conservative_1y | 2025-06-27 to 2026-06-27 | 59.7% | 0.661 | -$29.17 | 0.501 | -$263.09 to $216.61 |
| best_params_1y | 2025-06-27 to 2026-06-27 | 61.4% | 0.679 | $3.20 | 0.411 | -$506.71 to $533.88 |
| default_2y | 2024-06-27 to 2026-06-27 | 62.4% | 0.644 | $167.56 | 0.178 | -$513.15 to $876.19 |
| edge2_no_flat_2y | 2024-06-27 to 2026-06-27 | 62.4% | 0.644 | $181.22 | 0.201 | -$517.48 to $914.83 |
| conservative_2y | 2024-06-27 to 2026-06-27 | 62.4% | 0.644 | $83.71 | 0.169 | -$252.20 to $427.48 |
| best_params_2y | 2024-06-27 to 2026-06-27 | 63.3% | 0.659 | $280.57 | 0.125 | -$483.58 to $1,054.73 |

## Conclusion

The full-DOB retraining suite does not support a robust live betting edge.

- Best market-null p-value among the eight fresh ledgers was `0.125`.
- Bonferroni-adjusted p-value across the eight fresh ledgers was `0.996`.
- Model probabilities beat de-vigged market log loss in `0/8` fresh ledgers.
- Event-bootstrap profit confidence intervals were strictly positive in `0/8`
  fresh ledgers.
- All one-year full-DOB runs were negative or essentially breakeven.

The previous high-PnL masked-DOB results are therefore much more consistent
with backtest/feature-policy fitting than with a stable edge.
