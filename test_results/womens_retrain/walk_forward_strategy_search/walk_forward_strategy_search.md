# Walk-Forward Strategy Search

Development window: 2024-06-27 to 2025-06-26
Holdout window: 2025-06-27 to 2026-06-27
Candidate strategies evaluated on development window: 1152

## Selected Strategy

```json
{
  "model_label": "best_params_women_only",
  "side_policy": "predicted_winner",
  "model_weight": 1.0,
  "min_edge": 0.08,
  "min_probability": 0.6,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

## Development Result

Profit: $19.03 (1.90%)
Bets: 24
ROI on staked: 3.63%
Max drawdown: 9.30%

## Holdout Result

Profit: $12.99 (1.30%)
Bets: 15
ROI on staked: 3.92%
Max drawdown: 6.64%

## Top Development Candidates

| Rank | Model | Side Policy | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.050 | 0.050 | $19.03 | 24 | 3.63% |
| 2 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.050 | 0.050 | $19.03 | 24 | 3.63% |
| 3 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.050 | 0.050 | $19.03 | 24 | 3.63% |
| 4 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.050 | 0.050 | $19.03 | 24 | 3.63% |
| 5 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | none | 0.050 | 0.050 | $10.89 | 30 | 1.68% |
| 6 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.50 | 0.10 | none | 0.050 | 0.050 | $10.89 | 30 | 1.68% |
| 7 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.50 | 0.00 | none | 0.050 | 0.050 | $10.89 | 30 | 1.68% |
| 8 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.50 | 0.10 | none | 0.050 | 0.050 | $10.89 | 30 | 1.68% |
| 9 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.025 | 0.025 | $10.75 | 24 | 4.06% |
| 10 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.025 | 0.050 | $10.75 | 24 | 4.06% |
| 11 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.025 | 0.025 | $10.75 | 24 | 4.06% |
| 12 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.025 | 0.050 | $10.75 | 24 | 4.06% |
| 13 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.025 | 0.025 | $10.75 | 24 | 4.06% |
| 14 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.025 | 0.050 | $10.75 | 24 | 4.06% |
| 15 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.025 | 0.025 | $10.75 | 24 | 4.06% |
| 16 | best_params_women_only | best_edge | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.025 | 0.050 | $10.75 | 24 | 4.06% |
| 17 | best_params_women_only | predicted_winner | 1.00 | 0.02 | 0.60 | 0.00 | 300 | 0.050 | 0.050 | $8.74 | 29 | 1.61% |
| 18 | best_params_women_only | best_edge | 1.00 | 0.02 | 0.60 | 0.00 | 300 | 0.050 | 0.050 | $8.74 | 29 | 1.61% |
| 19 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | none | 0.025 | 0.025 | $7.45 | 30 | 2.30% |
| 20 | best_params_women_only | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | none | 0.025 | 0.050 | $7.45 | 30 | 2.30% |

The selected strategy is evaluated once on holdout; use the holdout ledger with
`testing/statistical_edge_audit.py` for market-null and bootstrap inference.
