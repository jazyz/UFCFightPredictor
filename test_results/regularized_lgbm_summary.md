# Regularized LGBM Improvement Summary

Run date: 2026-06-28

## Model Change

Added and evaluated a more regularized LightGBM configuration:

- `n_estimators`: 220
- `learning_rate`: 0.035
- `num_leaves`: 15
- `min_child_samples`: 90
- `subsample`: 0.75
- `colsample_bytree`: 0.70
- `reg_alpha`: 0.05
- `reg_lambda`: 1.5

The deployable single model was retrained through `2026-06-27` using
`test_results/regularized_lgbm_params.json`.

## Leak-Safe Backtest

Two-year window: `2024-06-27` to `2026-06-27`

| Run | Accuracy | Log loss | Final bankroll | Profit |
| --- | ---: | ---: | ---: | ---: |
| Baseline default | 62.59% | 0.6399 | $1402.38 | +40.24% |
| Regularized LGBM | 65.00% | 0.6318 | $1611.97 | +61.20% |

Recent-year holdout slice: `2025-06-27` to `2026-06-27`

| Run | Accuracy | Log loss | Plain-strategy ROI on staked |
| --- | ---: | ---: | ---: |
| Baseline default | 61.74% | 0.6596 | 4.0% |
| Regularized LGBM | 64.43% | 0.6418 | 10.2% |

## Strategy Search

Running the existing walk-forward strategy search on only the regularized ledger
selected:

```json
{
  "model_label": "regularized_lgbm",
  "side_policy": "predicted_winner",
  "model_weight": 1.0,
  "min_edge": 0.16,
  "min_probability": 0.5,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

Holdout result: `$198.17` profit, `19.82%` bankroll growth, `19.32%` ROI on
staked, `9.29%` max drawdown.

Market-null audit on the selected holdout: `p = 0.0717`.

## Market Log Loss

The standalone model still trails market-implied log loss, but a dev-selected
logit blend beats the market on holdout:

| Probability | Dev log loss | Holdout log loss |
| --- | ---: | ---: |
| Model only | 0.6215 | 0.6418 |
| Market only | 0.5854 | 0.6127 |
| 15% model / 85% market logit blend | 0.5843 | 0.6112 |

## Feature Importance Notes

Top retrained-model importance features are dominated by matchup deltas:

- `oppelo oppdiff`
- `elo oppdiff`
- `age oppdiff`
- `wins oppdiff`
- `avg age oppdiff`
- `Clinch oppdiff`
- `KD differential oppdiff`
- `totalfights oppdiff`

Full importance export:
`test_results/regularized_lgbm_feature_importance.csv`

## Dead-End Checked

Experimental title-context and matchup aggregate features were added as an
opt-in `--engineered-features` path.

Follow-up audit:

```text
test_results/feature_variant_engineered_regularized_summary.md
```

Both one-year and two-year leak-safe comparisons failed to justify promotion.
The engineered challenger worsened one-year accuracy, log loss, and PnL; on the
two-year window it had a tiny accuracy increase but worse log loss and lower
PnL. The production model and frozen forward policy therefore keep
`engineered_features=false`.
