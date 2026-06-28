# Market-Aware Feature Audit

This audit asks whether pre-fight feature groups add log-loss signal after
controlling for de-vigged market probability. Positive `Delta LL` means
the candidate probability beat the market probability.

## Protocol

- feature table: `data/detailed_fights.csv`
- odds table: `data/fight_results_with_odds.csv`
- aligned feature/odds rows: `1223`
- evaluated holdout fights: `704`
- folds evaluated: `5`
- first holdout start: `2024-02-05`
- last holdout end: `2026-06-27`
- development window: `730` days
- holdout window: `182` days
- logistic L2 C: `0.1`
- bootstrap iterations: `20000`
- market-null iterations: `100`

The logistic candidates are trained only on prior development folds. Training
rows are red/blue mirrored so the model sees each fight from both sides;
holdout probabilities average direct and mirrored orientations.

## Results

| Variant | Features | Fights | Market LL | Candidate LL | Delta LL | Accuracy | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| market_recalibrated | 1 | 704 | 0.6009 | 0.6000 | 0.0008 | 68.75% | 3 / 5 | 0.351 | 0.099 |
| market_plus_age_recency | 3 | 704 | 0.6009 | 0.6025 | -0.0017 | 68.75% | 2 / 5 | 0.692 | 0.257 |
| market_plus_combat_stats | 11 | 704 | 0.6009 | 0.6037 | -0.0028 | 68.75% | 2 / 5 | 0.664 | 0.158 |
| market_plus_top_importance | 24 | 704 | 0.6009 | 0.6088 | -0.0080 | 68.32% | 2 / 5 | 0.841 | 0.158 |
| market_plus_elo_experience | 9 | 704 | 0.6009 | 0.6112 | -0.0103 | 68.18% | 2 / 5 | 0.947 | 0.683 |

## Variants

| Variant | Note | Feature Columns |
| --- | --- | --- |
| market_recalibrated | logistic recalibration of market logit only | `market_logit` |
| market_plus_elo_experience | market plus Elo, experience, streak, and title-count deltas | `market_logit`, `oppelo oppdiff`, `elo oppdiff`, `wins oppdiff`, `totalfights oppdiff`, `avg age oppdiff`, `winstreak oppdiff`, `losestreak oppdiff`, `titlewins oppdiff` |
| market_plus_age_recency | market plus age and layoff deltas | `market_logit`, `age oppdiff`, `last_fight oppdiff` |
| market_plus_combat_stats | market plus selected historical striking/grappling stat deltas | `market_logit`, `Clinch oppdiff`, `KD differential oppdiff`, `Sig. str.% differential oppdiff`, `Body% differential oppdiff`, `Td% defense oppdiff`, `Distance% defense oppdiff`, `Sub. att oppdiff`, `Td differential oppdiff`, `Head differential oppdiff`, `Ctrl oppdiff` |
| market_plus_top_importance | market plus top 23 retrained-LGBM importance features | `market_logit`, `oppelo oppdiff`, `elo oppdiff`, `age oppdiff`, `wins oppdiff`, `avg age oppdiff`, `Clinch oppdiff`, `KD differential oppdiff`, `Red avg age`, `Blue avg age`, `totalfights oppdiff`, `Sig. str.% differential oppdiff`, `Red Sub. att differential`, `Blue Sub. att differential`, `Body% differential oppdiff`, `Blue Sig. str. differential`, `Red Sig. str. differential`, `Td% defense oppdiff`, `Blue Leg% defense`, `Red Leg% defense`, `Total str.% defense oppdiff`, `Blue Clinch`, `Red Clinch`, `Distance% defense oppdiff` |

## Fold Deltas

| Fold | Holdout | Market LL | market_recalibrated | market_plus_elo_experience | market_plus_age_recency | market_plus_combat_stats | market_plus_top_importance |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2024-02-05 to 2024-08-04 | 0.5967 | 0.0048 | -0.0000 | 0.0010 | -0.0018 | -0.0093 |
| 2 | 2024-08-05 to 2025-02-02 | 0.5789 | 0.0024 | 0.0160 | 0.0020 | -0.0039 | -0.0047 |
| 3 | 2025-02-03 to 2025-08-03 | 0.6181 | -0.0031 | 0.0013 | -0.0028 | 0.0142 | 0.0214 |
| 4 | 2025-08-04 to 2026-02-01 | 0.5822 | 0.0036 | -0.0543 | -0.0054 | 0.0062 | 0.0013 |
| 5 | 2026-02-02 to 2026-06-27 | 0.6273 | -0.0039 | -0.0193 | -0.0038 | -0.0318 | -0.0531 |

## Interpretation

Best raw candidate: `market_recalibrated` with Delta LL `0.0008`.
Its event-bootstrap `P(delta <= 0)` was `0.351` and its market-null p-value was `0.099`.
The result is useful diagnostics, but not strong enough to promote a new market-aware feature model.

## Outputs

- `test_results/market_aware_feature_audit/market_aware_feature_predictions.csv`
- `test_results/market_aware_feature_audit/market_aware_feature_audit.json`
- `test_results/market_aware_feature_audit/market_aware_feature_audit.md`
