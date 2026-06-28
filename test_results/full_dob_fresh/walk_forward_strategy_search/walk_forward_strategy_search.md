# Walk-Forward Strategy Search

Development window: 2024-06-27 to 2025-06-26
Holdout window: 2025-06-27 to 2026-06-27
Candidate strategies evaluated on development window: 576

## Selected Strategy

```json
{
  "model_label": "best_params_full_dob",
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

Profit: $381.52 (38.15%)
Bets: 64
ROI on staked: 26.46%
Max drawdown: 9.43%

## Holdout Result

Profit: $30.70 (3.07%)
Bets: 67
ROI on staked: 2.19%
Max drawdown: 16.60%

## Top Development Candidates

| Rank | Model | Side Policy | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | best_params_full_dob | predicted_winner | 1.00 | 0.16 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $381.52 | 64 | 26.46% |
| 2 | best_params_full_dob | predicted_winner | 1.00 | 0.16 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $381.52 | 64 | 26.46% |
| 3 | best_params_full_dob | best_edge | 1.00 | 0.16 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $381.52 | 64 | 26.46% |
| 4 | best_params_full_dob | best_edge | 1.00 | 0.16 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $381.52 | 64 | 26.46% |
| 5 | best_params_full_dob | predicted_winner | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $376.23 | 144 | 17.60% |
| 6 | best_params_full_dob | best_edge | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $376.23 | 144 | 17.60% |
| 7 | best_params_full_dob | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $369.37 | 111 | 18.35% |
| 8 | best_params_full_dob | predicted_winner | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $369.37 | 111 | 18.35% |
| 9 | best_params_full_dob | best_edge | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $369.37 | 111 | 18.35% |
| 10 | best_params_full_dob | best_edge | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $369.37 | 111 | 18.35% |
| 11 | best_params_full_dob | predicted_winner | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $363.04 | 118 | 17.58% |
| 12 | best_params_full_dob | best_edge | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $363.04 | 118 | 17.58% |
| 13 | default_full_dob | predicted_winner | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $323.00 | 136 | 17.67% |
| 14 | default_full_dob | best_edge | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $323.00 | 136 | 17.67% |
| 15 | default_full_dob | predicted_winner | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $308.55 | 112 | 17.41% |
| 16 | default_full_dob | best_edge | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $308.55 | 112 | 17.41% |
| 17 | default_full_dob | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $299.64 | 98 | 17.98% |
| 18 | default_full_dob | predicted_winner | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $299.64 | 98 | 17.98% |
| 19 | default_full_dob | best_edge | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $299.64 | 98 | 17.98% |
| 20 | default_full_dob | best_edge | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $299.64 | 98 | 17.98% |

The selected strategy is evaluated once on holdout; use the holdout ledger with
`testing/statistical_edge_audit.py` for market-null and bootstrap inference.
