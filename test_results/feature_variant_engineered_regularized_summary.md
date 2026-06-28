# Engineered Feature Variant Audit

Run date: 2026-06-28

## Purpose

Test whether the opt-in `--engineered-features` path should become a challenger
to the current regularized production feature set.

The variant adds:

- title/context features from `utils/feature_engineering.py`
- matchup aggregate features such as absolute differences, means, log
  differences, and totals for selected Red/Blue stat pairs

This audit keeps the LightGBM config fixed to
`test_results/regularized_lgbm_params.json` and changes only the feature set.
It is still exploratory because the feature family was manually designed after
earlier diagnostics.

## Commands

```bash
.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2025-06-27 \
  --end-date 2026-06-27 \
  --params test_results/regularized_lgbm_params.json \
  --engineered-features \
  --output-dir test_results/feature_variant_engineered_regularized_1y

.venv/bin/python testing/no_leakage_backtest.py \
  --start-date 2024-06-27 \
  --end-date 2026-06-27 \
  --params test_results/regularized_lgbm_params.json \
  --engineered-features \
  --output-dir test_results/feature_variant_engineered_regularized_2y

.venv/bin/python testing/statistical_edge_audit.py \
  test_results/feature_variant_engineered_regularized_1y/no_leakage_backtest.csv \
  test_results/feature_variant_engineered_regularized_2y/no_leakage_backtest.csv \
  --iterations 10000 \
  --output-dir test_results/feature_variant_engineered_regularized_audit
```

## Leak-Safe Comparison

| Window | Feature Set | Fights | Accuracy | Log Loss | Final Bankroll | PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | current regularized | 298 | 64.43% | 0.6418 | $1246.65 | +24.66% |
| 2025-06-27 to 2026-06-27 | engineered challenger | 298 | 62.75% | 0.6506 | $1041.19 | +4.12% |
| 2024-06-27 to 2026-06-27 | current regularized | 580 | 65.00% | 0.6318 | $1611.97 | +61.20% |
| 2024-06-27 to 2026-06-27 | engineered challenger | 580 | 65.17% | 0.6364 | $1479.54 | +47.95% |

## Statistical Audit

Report:

```text
test_results/feature_variant_engineered_regularized_audit/edge_audit.md
```

The engineered challenger:

- beats market-null only weakly on the two-year ledger: `p = 0.059`
- has Bonferroni-adjusted p-value `0.117` across the two saved engineered
  ledgers
- beats de-vigged market log loss in `0/2` engineered ledgers
- has strictly positive event-bootstrap profit CI in `0/2` engineered ledgers

## Decision

Do not promote these engineered features.

They do not improve the current regularized model on the one-year window, and
they worsen two-year log loss and PnL despite a tiny accuracy increase. Because
the main edge question is already vulnerable to selection bias, adding this
feature family would increase researcher degrees of freedom without improving
the evidence.

Current production/frozen policy should remain on `engineered_features=false`.
