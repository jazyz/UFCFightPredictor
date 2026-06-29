# Residual Uncapped Alpha Audit

This report reframes the current evidence around uncapped residual alpha.
A per-event cap is treated as an exposure/risk overlay, not as the
fundamental alpha claim.

## Bottom Line

- The best current alpha is a weak historical model-after-market probability residual, not an event-cap betting rule.
- The probability evidence is directionally positive on aggregate, especially selected shrinkage, but recent 2026/last-365-day slices are negative.
- Uncapped flat-bet PnL is positive but statistically fragile: corrected market-null p-values and event-bootstrap intervals do not support a live staking claim.
- The production universe/no-contest handling is already aligned with the requested policy: no women's fights in production training/evaluation, while non-binary bouts update future fighter state but are not supervised labels.

## Inputs

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- market residual meta: `test_results/market_residual_meta_audit/market_residual_meta_audit.json`
- residual shrinkage: `test_results/residual_shrinkage_audit/residual_shrinkage_audit.json`
- recent stress: `test_results/residual_recent_stress_audit/residual_recent_stress_audit.json`
- shrinkage fixed PnL: `test_results/residual_shrinkage_fixed_pnl_audit/residual_shrinkage_fixed_pnl_audit.json`
- outcome universe: `test_results/outcome_universe_audit/outcome_universe_audit.json`

## Probability Metrics

Lower log loss is useful because it is a proper scoring rule, but it is
not sufficient by itself. The table also tracks Brier score, directional
accuracy, calibration slope/intercept, and reliability-style bin gaps.

| Policy | LL | Brier | Accuracy | Calibration Intercept | Calibration Slope | ECE 10-bin | Max Bin Gap | Actual - Pred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market | 0.6009 | 0.2067 | 68.75% | -0.0166 | 1.1221 | 3.22% | 9.07% | -0.35% |
| selected_shrinkage | 0.5971 | 0.2049 | 69.32% | -0.0874 | 0.9454 | 4.17% | 8.42% | -1.84% |
| fixed_half_residual | 0.5979 | 0.2053 | 69.60% | -0.0574 | 1.0254 | 2.50% | 15.82% | -1.17% |
| unshrunk_meta | 0.5979 | 0.2050 | 69.03% | -0.0927 | 0.9245 | 3.45% | 8.43% | -1.98% |

## Probability Evidence After Market Control

`Delta LL` is market log loss minus candidate log loss; positive means the
candidate improved over de-vigged market probability on future holdouts.

| Test | Fights | Market LL | Candidate LL | Delta LL | Delta Brier | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p | Corrected p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market + regularized residual meta | 704 | 0.6009 | 0.5979 | 0.0030 | 0.0016 | 4 / 5 | 0.218 | 0.012 | 0.048 |
| selected_shrinkage | 704 | 0.6009 | 0.5971 | 0.0038 | 0.0018 | 4 / 5 | 0.140 | 0.005 | 0.015 |
| fixed_half_residual | 704 | 0.6009 | 0.5979 | 0.0030 | 0.0014 | 4 / 5 | 0.051 | 0.015 | 0.045 |
| unshrunk_meta | 704 | 0.6009 | 0.5979 | 0.0030 | 0.0016 | 4 / 5 | 0.218 | 0.015 | 0.045 |

## Selected-Shrinkage Residual Buckets

These buckets check whether the model's signed disagreement with market
corresponds to realized market error. If the residual is real, positive
candidate-minus-market buckets should usually have positive actual-minus-market,
and negative buckets should usually have negative actual-minus-market.

| Selected Residual Bucket | Fights | Mean Candidate - Market | Actual - Market | Actual - Candidate | Delta LL |
| --- | ---: | ---: | ---: | ---: | ---: |
| <= -5% | 34 | -5.77% | -13.25% | -7.48% | 0.0270 |
| -5% to -2% | 135 | -3.34% | -5.09% | -1.75% | 0.0037 |
| -2% to +2% | 203 | -0.02% | -1.17% | -1.15% | 0.0008 |
| +2% to +5% | 152 | 3.71% | -1.60% | -5.30% | -0.0071 |
| >= +5% | 180 | 6.31% | 7.61% | 1.30% | 0.0119 |

## Recent Probability Stress

| Period | Policy | Fights | Delta LL | Bootstrap P(delta <= 0) | Market-Null p |
| --- | --- | ---: | ---: | ---: | ---: |
| aggregate | selected_shrinkage | 704 | 0.0038 | 0.140 | 0.011 |
| aggregate | fixed_half_residual | 704 | 0.0030 | 0.050 | 0.014 |
| aggregate | unshrunk_meta | 704 | 0.0030 | 0.221 | 0.014 |
| 2025-2026 only | selected_shrinkage | 429 | -0.0001 | 0.503 | 0.169 |
| 2025-2026 only | fixed_half_residual | 429 | 0.0012 | 0.320 | 0.158 |
| 2025-2026 only | unshrunk_meta | 429 | -0.0014 | 0.594 | 0.174 |
| last 365 days | selected_shrinkage | 298 | -0.0032 | 0.722 | 0.409 |
| last 365 days | fixed_half_residual | 298 | -0.0004 | 0.544 | 0.339 |
| last 365 days | unshrunk_meta | 298 | -0.0050 | 0.770 | 0.374 |
| latest fold 5 | selected_shrinkage | 129 | -0.0047 | 0.720 | 0.498 |
| latest fold 5 | fixed_half_residual | 129 | -0.0018 | 0.639 | 0.487 |
| latest fold 5 | unshrunk_meta | 129 | -0.0093 | 0.806 | 0.515 |

## Uncapped PnL Translation

These rows do not use a per-event cap. Positive historical PnL is useful
as a translation check, but this is weaker than the probability evidence.

| Family | Policy / Objective | Bets | Profit | ROI | Actual - Market | Positive Folds | Market-Null p | Corrected p | Bootstrap P(profit <= 0) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| residual meta threshold selection | profit | 363 | +7.46u | 2.06% | 4.10% | 4 / 5 | 0.066 | 0.198 | 0.258 |
| residual meta threshold selection | ROI | 304 | +4.31u | 1.42% | 3.56% | 4 / 5 | 0.144 | 0.432 | 0.344 |
| residual meta threshold selection | actual - market | 311 | +6.67u | 2.14% | 4.08% | 4 / 5 | 0.083 | 0.249 | 0.265 |
| residual meta threshold selection | fixed edge>=0.02, p>=0.60 | 354 | +2.44u | 0.69% | 3.19% | 3 / 5 | 0.117 | 0.117 | 0.421 |
| fixed uncapped shrinkage thresholds | selected_shrinkage | 399 | +4.55u | 1.14% | 3.65% | 3 / 5 | 0.046 | 0.139 | 0.354 |
| fixed uncapped shrinkage thresholds | fixed_half_residual | 288 | +8.39u | 2.91% | 4.78% | 3 / 5 | 0.024 | 0.071 | 0.197 |
| fixed uncapped shrinkage thresholds | unshrunk_meta | 418 | +3.40u | 0.81% | 3.50% | 3 / 5 | 0.049 | 0.146 | 0.389 |

## Universe And Non-Binary Outcome Handling

| Check | Value |
| --- | ---: |
| production feature rows | 4322 |
| production women's title rows | 0 |
| production known women-pair rows | 0 |
| supervised non-binary result rows | 0 |
| retained source non-binary / blank-winner rows | 148 |
| future fighter-side rows with prior non-binary history checked | 1263 |
| `totalfights` matches including non-binary bouts | 1263 |
| `last_fight` checks after latest prior non-binary bout | 157 |
| `last_fight` matches | 157 |
| weighted stat checks affected by non-binary bouts | 3697 |
| weighted stat matches including non-binary bouts | 3697 |

## Interpretation

The current edge claim should be stated narrowly: the regularized model
has historically provided a small residual probability signal after
controlling for the market. The selected-shrinkage transform is the
cleanest version of that claim because shrinkage was selected inside
walk-forward development windows.

That does not yet prove a live betting edge. The uncapped PnL checks are
positive but fragile after objective/policy correction, recent probability
stress is negative, and event-bootstrap uncertainty still crosses zero.
Future work should focus on explaining the recent residual drift and on
predeclared forward paper tracking. Per-event caps may still be useful
for risk control, but they should not be presented as the alpha itself.
