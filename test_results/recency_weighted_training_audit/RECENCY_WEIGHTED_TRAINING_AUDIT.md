# Recency-Weighted Training Audit

Date: 2026-06-28

## Purpose

This audit tested whether the recent residual/performance decay could be
improved by weighting newer training fights more heavily during leak-safe
rolling LightGBM retraining.

This is a training-only experiment. It does not change betting thresholds,
event filters, odds handling, or the production feature set.

## Implementation

`testing/no_leakage_backtest.py` now has an optional flag:

```text
--training-recency-half-life-days
```

For each event-date retrain, the backtester computes sample weights only from
rows in the training set:

```text
weight = 0.5 ** (days_before_event / half_life_days)
```

Weights are normalized to mean `1.0` inside each training window. The mirrored
fighter-order training rows receive the same weights as their source rows.

The default remains `None`, so existing backtests and production-style runs are
unchanged unless the flag is explicitly set.

## Runs

Fixed model params:

```text
test_results/regularized_lgbm_params.json
```

Commands:

```text
PYTHONPYCACHEPREFIX=/private/tmp/ufc_pycache .venv/bin/python testing/no_leakage_backtest.py --start-date 2025-06-27 --end-date 2026-06-27 --params test_results/regularized_lgbm_params.json --training-recency-half-life-days 365 --output-dir test_results/recency_weighted_training_audit/regularized_half_life_365_1y
PYTHONPYCACHEPREFIX=/private/tmp/ufc_pycache .venv/bin/python testing/no_leakage_backtest.py --start-date 2024-06-27 --end-date 2026-06-27 --params test_results/regularized_lgbm_params.json --training-recency-half-life-days 365 --output-dir test_results/recency_weighted_training_audit/regularized_half_life_365_2y
PYTHONPYCACHEPREFIX=/private/tmp/ufc_pycache .venv/bin/python testing/no_leakage_backtest.py --start-date 2025-06-27 --end-date 2026-06-27 --params test_results/regularized_lgbm_params.json --training-recency-half-life-days 730 --output-dir test_results/recency_weighted_training_audit/regularized_half_life_730_1y
PYTHONPYCACHEPREFIX=/private/tmp/ufc_pycache .venv/bin/python testing/no_leakage_backtest.py --start-date 2024-06-27 --end-date 2026-06-27 --params test_results/regularized_lgbm_params.json --training-recency-half-life-days 730 --output-dir test_results/recency_weighted_training_audit/regularized_half_life_730_2y
PYTHONPYCACHEPREFIX=/private/tmp/ufc_pycache .venv/bin/python testing/statistical_edge_audit.py test_results/recency_weighted_training_audit/regularized_half_life_365_1y/no_leakage_backtest.csv test_results/recency_weighted_training_audit/regularized_half_life_365_2y/no_leakage_backtest.csv test_results/recency_weighted_training_audit/regularized_half_life_730_1y/no_leakage_backtest.csv test_results/recency_weighted_training_audit/regularized_half_life_730_2y/no_leakage_backtest.csv --iterations 10000 --output-dir test_results/recency_weighted_training_audit/statistical_edge_audit
```

## Results

| Window | Training Policy | Accuracy | Log Loss | PnL |
| --- | --- | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | current regularized | 64.43% | 0.6418 | +24.66% |
| 2025-06-27 to 2026-06-27 | half-life 365d | 65.10% | 0.6588 | +11.08% |
| 2025-06-27 to 2026-06-27 | half-life 730d | 65.10% | 0.6396 | +15.46% |
| 2024-06-27 to 2026-06-27 | current regularized | 65.00% | 0.6318 | +61.20% |
| 2024-06-27 to 2026-06-27 | half-life 365d | 65.17% | 0.6480 | +26.28% |
| 2024-06-27 to 2026-06-27 | half-life 730d | 64.66% | 0.6372 | +31.41% |

Statistical edge audit:

```text
test_results/recency_weighted_training_audit/statistical_edge_audit/edge_audit.md
```

| Run | Fights | Bets | Model LL | Market LL | Profit | Market-Null p | Bootstrap Profit CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| half-life 365d, 2y | 580 | 482 | 0.648 | 0.600 | +$262.85 | 0.125 | -$497.41 to +$1,011.06 |
| half-life 730d, 2y | 580 | 468 | 0.637 | 0.600 | +$314.08 | 0.103 | -$357.20 to +$991.17 |
| half-life 365d, 1y | 298 | 252 | 0.659 | 0.613 | +$110.83 | 0.266 | -$442.84 to +$661.77 |
| half-life 730d, 1y | 298 | 241 | 0.640 | 0.613 | +$154.59 | 0.241 | -$328.59 to +$647.94 |

The best saved recency-weighted ledger has market-null p-value `0.103`;
Bonferroni across the four saved ledgers gives `0.414`. Model probabilities
beat de-vigged market log loss in `0/4` ledgers. Event-bootstrap profit
confidence intervals are strictly positive in `0/4` ledgers.

## Interpretation

Do not promote recency-weighted LightGBM training.

The 730-day half-life is mildly interesting because it improved one-year log
loss versus the current regularized model (`0.6396` vs `0.6418`), but that gain
did not transfer to the two-year window, did not improve PnL, and did not beat
the de-vigged market on log loss. The 365-day half-life worsened log loss in
both windows.

This looks like a useful diagnostic about recency drift, not a current edge
improvement. If revisited, it should be inside a pre-registered or nested model
selection protocol rather than manually selected from these backtest outcomes.
