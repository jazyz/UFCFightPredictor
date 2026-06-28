# Walk-Forward PnL Improvement Audit

Date run: 2026-06-28

## Setup

This pass tried to improve betting PnL without reintroducing DOB masking or
backtest fitting.

Inputs:

- `test_results/full_dob_fresh/backtests/default_2y/no_leakage_backtest.csv`
- `test_results/full_dob_fresh/backtests/best_params_2y/no_leakage_backtest.csv`

Both inputs were produced from the full-DOB feature table:

```text
test_results/full_dob_fresh/detailed_fights_full_dobs.csv
```

Search protocol:

- Development window: `2024-06-27` to `2025-06-26`
- Holdout window: `2025-06-27` to `2026-06-27`
- Candidate strategies: `576`
- Selection criterion: highest development profit, with at least 40 development
  bets and max development drawdown no greater than 35%
- Statistical test: market-null path simulation and event bootstrap on the
  single selected holdout ledger

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

Artifacts:

- Search report: `test_results/full_dob_fresh/walk_forward_strategy_search/walk_forward_strategy_search.md`
- Selected holdout ledger: `test_results/full_dob_fresh/walk_forward_strategy_search/selected_holdout/no_leakage_backtest.csv`
- Holdout statistical audit: `test_results/full_dob_fresh/walk_forward_strategy_search/selected_holdout_audit/edge_audit.md`

## Results

Development result:

- Profit: `$381.52` (`+38.15%`)
- Bets: `64`
- ROI on staked: `26.46%`
- Max drawdown: `9.43%`

Holdout result:

- Profit: `$30.70` (`+3.07%`)
- Bets: `67`
- ROI on staked: `2.19%`
- Max drawdown: `16.60%`

Holdout inference:

- Market-null p-value: `0.288`
- Event-bootstrap profit CI: `-$338.51` to `$409.99`
- Probability bootstrap profit <= 0: `43.27%`
- Model log loss: `0.679`
- De-vigged market log loss: `0.613`

## Conclusion

The selected strategy improved holdout PnL versus the full-DOB one-year
baseline, but the improvement is not statistically convincing.

The result should be treated as a weak risk-control/selection heuristic, not a
validated betting edge. I would not deploy larger staking from this evidence.
The strongest conclusion remains: the model is overconfident relative to the
market, and PnL improvements found by threshold search are fragile unless they
survive future out-of-sample cards.
