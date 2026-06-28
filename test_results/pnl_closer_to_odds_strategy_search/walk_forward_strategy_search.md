# Walk-Forward Strategy Search

Development window: 2024-06-27 to 2025-06-26
Holdout window: 2025-06-27 to 2026-06-27
Candidate strategies evaluated on development window: 576

## Selected Strategy

```json
{
  "model_label": "average_default",
  "side_policy": "predicted_winner",
  "model_weight": 1.0,
  "min_edge": 0.02,
  "min_probability": 0.6,
  "min_kelly": 0.1,
  "max_underdog_odds": null,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

## Development Result

Profit: $453.47 (45.35%)
Bets: 68
ROI on staked: 35.65%
Max drawdown: 8.14%

## Holdout Result

Profit: $95.70 (9.57%)
Bets: 82
ROI on staked: 6.01%
Max drawdown: 16.09%

## Top Development Candidates

| Rank | Model | Side Policy | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | average_default | predicted_winner | 1.00 | 0.02 | 0.60 | 0.10 | none | 0.050 | 0.050 | $453.47 | 68 | 35.65% |
| 2 | average_default | best_edge | 1.00 | 0.02 | 0.60 | 0.10 | none | 0.050 | 0.050 | $453.47 | 68 | 35.65% |
| 3 | average_default | predicted_winner | 1.00 | 0.02 | 0.60 | 0.00 | none | 0.050 | 0.050 | $452.38 | 90 | 33.88% |
| 4 | average_default | best_edge | 1.00 | 0.02 | 0.60 | 0.00 | none | 0.050 | 0.050 | $452.38 | 90 | 33.88% |
| 5 | average_default | predicted_winner | 1.00 | 0.08 | 0.60 | 0.00 | none | 0.050 | 0.050 | $429.61 | 56 | 36.69% |
| 6 | average_default | predicted_winner | 1.00 | 0.08 | 0.60 | 0.10 | none | 0.050 | 0.050 | $429.61 | 56 | 36.69% |
| 7 | average_default | best_edge | 1.00 | 0.08 | 0.60 | 0.00 | none | 0.050 | 0.050 | $429.61 | 56 | 36.69% |
| 8 | average_default | best_edge | 1.00 | 0.08 | 0.60 | 0.10 | none | 0.050 | 0.050 | $429.61 | 56 | 36.69% |
| 9 | average_default | predicted_winner | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $372.88 | 141 | 19.76% |
| 10 | average_default | best_edge | 1.00 | 0.02 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $372.88 | 141 | 19.76% |
| 11 | average_default | predicted_winner | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $370.07 | 108 | 20.77% |
| 12 | average_default | best_edge | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $370.07 | 108 | 20.77% |
| 13 | average_default | predicted_winner | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $362.84 | 94 | 21.58% |
| 14 | average_default | predicted_winner | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $362.84 | 94 | 21.58% |
| 15 | average_default | best_edge | 1.00 | 0.08 | 0.50 | 0.00 | 300 | 0.050 | 0.050 | $362.84 | 94 | 21.58% |
| 16 | average_default | best_edge | 1.00 | 0.08 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $362.84 | 94 | 21.58% |
| 17 | closer_to_odds | predicted_winner | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $335.72 | 84 | 25.60% |
| 18 | closer_to_odds | best_edge | 1.00 | 0.02 | 0.50 | 0.10 | 300 | 0.050 | 0.050 | $335.72 | 84 | 25.60% |
| 19 | closer_to_odds | predicted_winner | 1.00 | 0.02 | 0.50 | 0.10 | none | 0.050 | 0.050 | $331.86 | 89 | 23.68% |
| 20 | closer_to_odds | best_edge | 1.00 | 0.02 | 0.50 | 0.10 | none | 0.050 | 0.050 | $331.86 | 89 | 23.68% |

The selected strategy is evaluated once on holdout; use the holdout ledger with
`testing/statistical_edge_audit.py` for market-null and bootstrap inference.
