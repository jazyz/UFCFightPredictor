# Frozen Forward Policy

As-of date: `2026-06-28`
Development window: `2025-06-28` to `2026-06-27`
Selection objective: `roi`
Minimum development bets: `35`
Settlement mode: `event`
Max event exposure fraction: `none`
Candidate strategies evaluated: `576`

This is a frozen forward paper-tracking contract, not evidence that a
live betting edge has been proven. The selection uses only historical
ledgers available as of the as-of date; future scoring should not replace
this artifact after outcomes are known.

## Selected Strategy

```json
{
  "model_label": "regularized_lgbm",
  "side_policy": "predicted_winner",
  "model_weight": 0.7,
  "min_edge": 0.02,
  "min_probability": 0.6,
  "min_kelly": 0.0,
  "max_underdog_odds": 300.0,
  "kelly_fraction": 0.05,
  "max_fraction": 0.05
}
```

## Development Evidence

Profit: $140.04 (14.00%)
Fights: 298
Bets: 44
Events with bets: 28
ROI on staked: 38.76%
Max drawdown: 3.74%

## Frozen Rules

- Do not change the model candidate set, objective, or strategy grid before future outcomes are known.
- Ties are resolved by the existing `strategy_grid` iteration order.
- Use this policy only for forward paper tracking until enough new outcomes accrue.
- A future edge claim still requires market-null and event-bootstrap evidence on post-freeze bets.
- If this policy is used for live recommendations, record that implementation separately before placing bets.

## Top Development Candidates

| Rank | Model | Side | Weight | Edge | Min P | Min Kelly | Max Dog | Kelly | Cap | Dev Profit | Dev Bets | Dev ROI | Max DD |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | regularized_lgbm | predicted_winner | 0.70 | 0.02 | 0.60 | 0.00 | 300 | 0.050 | 0.050 | $140.04 | 44 | 38.76% | 3.74% |
| 2 | regularized_lgbm | predicted_winner | 0.70 | 0.02 | 0.60 | 0.00 | none | 0.050 | 0.050 | $140.04 | 44 | 38.76% | 3.74% |
| 3 | regularized_lgbm | best_edge | 0.70 | 0.02 | 0.60 | 0.00 | 300 | 0.050 | 0.050 | $140.04 | 44 | 38.76% | 3.74% |
| 4 | regularized_lgbm | best_edge | 0.70 | 0.02 | 0.60 | 0.00 | none | 0.050 | 0.050 | $140.04 | 44 | 38.76% | 3.74% |
| 5 | regularized_lgbm | predicted_winner | 0.70 | 0.02 | 0.60 | 0.00 | 300 | 0.025 | 0.025 | $68.28 | 44 | 38.42% | 1.88% |
| 6 | regularized_lgbm | predicted_winner | 0.70 | 0.02 | 0.60 | 0.00 | 300 | 0.025 | 0.050 | $68.28 | 44 | 38.42% | 1.88% |
| 7 | regularized_lgbm | predicted_winner | 0.70 | 0.02 | 0.60 | 0.00 | none | 0.025 | 0.025 | $68.28 | 44 | 38.42% | 1.88% |
| 8 | regularized_lgbm | predicted_winner | 0.70 | 0.02 | 0.60 | 0.00 | none | 0.025 | 0.050 | $68.28 | 44 | 38.42% | 1.88% |
| 9 | regularized_lgbm | best_edge | 0.70 | 0.02 | 0.60 | 0.00 | 300 | 0.025 | 0.025 | $68.28 | 44 | 38.42% | 1.88% |
| 10 | regularized_lgbm | best_edge | 0.70 | 0.02 | 0.60 | 0.00 | 300 | 0.025 | 0.050 | $68.28 | 44 | 38.42% | 1.88% |
| 11 | regularized_lgbm | best_edge | 0.70 | 0.02 | 0.60 | 0.00 | none | 0.025 | 0.025 | $68.28 | 44 | 38.42% | 1.88% |
| 12 | regularized_lgbm | best_edge | 0.70 | 0.02 | 0.60 | 0.00 | none | 0.025 | 0.050 | $68.28 | 44 | 38.42% | 1.88% |
| 13 | regularized_lgbm | predicted_winner | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.025 | 0.025 | $120.14 | 49 | 27.64% | 4.93% |
| 14 | regularized_lgbm | predicted_winner | 1.00 | 0.08 | 0.60 | 0.00 | 300 | 0.025 | 0.050 | $120.14 | 49 | 27.64% | 4.93% |
| 15 | regularized_lgbm | predicted_winner | 1.00 | 0.08 | 0.60 | 0.10 | 300 | 0.025 | 0.025 | $120.14 | 49 | 27.64% | 4.93% |
