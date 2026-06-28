# Walk-Forward Strategy Search

Development window: 2024-06-27 to 2025-06-26
Holdout window: 2025-06-27 to 2026-06-27
Settlement mode: event
Max event exposure fraction: None
Candidate strategies evaluated on development window: 288

## Selected Strategy

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

## Development Result

Profit: $379.00 (37.90%)
Bets: 44
ROI on staked: 39.82%
Max drawdown: 7.70%

## Holdout Result

Profit: $198.17 (19.82%)
Bets: 51
ROI on staked: 19.32%
Max drawdown: 9.29%

## Top Development Candidates

| Rank | Model | Side Policy | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | regularized_lgbm | predicted_winner | 1.00 | 0.16 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $379.00 | 44 | 39.82% |
| 2 | regularized_lgbm | predicted_winner | 1.00 | 0.16 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $379.00 | 44 | 39.82% |
| 3 | regularized_lgbm | best_edge | 1.00 | 0.16 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $379.00 | 44 | 39.82% |
| 4 | regularized_lgbm | best_edge | 1.00 | 0.16 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $379.00 | 44 | 39.82% |
| 5 | regularized_lgbm | predicted_winner | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $366.74 | 83 | 26.92% |
| 6 | regularized_lgbm | best_edge | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $366.74 | 83 | 26.92% |
| 7 | regularized_lgbm | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $357.73 | 76 | 27.27% |
| 8 | regularized_lgbm | predicted_winner | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $357.73 | 76 | 27.27% |
| 9 | regularized_lgbm | best_edge | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $357.73 | 76 | 27.27% |
| 10 | regularized_lgbm | best_edge | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $357.73 | 76 | 27.27% |
| 11 | regularized_lgbm | predicted_winner | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $350.82 | 109 | 24.61% |
| 12 | regularized_lgbm | best_edge | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $350.82 | 109 | 24.61% |
| 13 | regularized_lgbm | predicted_winner | 1.00 | 0.02 | 0.60 | 0.10 | none | 0.050 | 0.050 | $297.29 | 45 | 37.82% |
| 14 | regularized_lgbm | best_edge | 1.00 | 0.02 | 0.60 | 0.10 | none | 0.050 | 0.050 | $297.29 | 45 | 37.82% |
| 15 | regularized_lgbm | predicted_winner | 1.00 | 0.02 | 0.60 | 0.00 | none | 0.050 | 0.050 | $283.77 | 64 | 34.09% |
| 16 | regularized_lgbm | best_edge | 1.00 | 0.02 | 0.60 | 0.00 | none | 0.050 | 0.050 | $283.77 | 64 | 34.09% |
| 17 | regularized_lgbm | predicted_winner | 1.00 | 0.16 | 0.50 | 0.00 | none | 0.050 | 0.050 | $280.50 | 52 | 25.27% |
| 18 | regularized_lgbm | predicted_winner | 1.00 | 0.16 | 0.50 | 0.10 | none | 0.050 | 0.050 | $280.50 | 52 | 25.27% |
| 19 | regularized_lgbm | best_edge | 1.00 | 0.16 | 0.50 | 0.00 | none | 0.050 | 0.050 | $280.50 | 52 | 25.27% |
| 20 | regularized_lgbm | best_edge | 1.00 | 0.16 | 0.50 | 0.10 | none | 0.050 | 0.050 | $280.50 | 52 | 25.27% |

The selected strategy is evaluated once on holdout; use the holdout ledger with
`testing/statistical_edge_audit.py` for market-null and bootstrap inference.
