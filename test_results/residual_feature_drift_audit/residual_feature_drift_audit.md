# Residual Feature Drift Audit

This audit merges residual-shrinkage holdout probabilities with the
production feature table. It is diagnostic only: no model is retrained,
no threshold is selected, and no new betting policy is proposed.

## Inputs

- predictions: `test_results/residual_shrinkage_audit/holdout_shrinkage_predictions.csv`
- features: `data/detailed_fights.csv`
- feature importance: `test_results/regularized_lgbm_feature_importance.csv`
- merged fights: `704`
- top features inspected: `25`

## Period Drift

| Period | Fights | Actual | Market P | Selected P | Adj | Realized Residual | Delta LL | Fixed-Half Delta LL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| aggregate | 704 | 49.43% | 49.78% | 51.27% | 1.49% | -0.35% | 0.0038 | 0.0030 |
| 2024 | 275 | 51.64% | 48.57% | 50.00% | 1.43% | 3.07% | 0.0098 | 0.0059 |
| 2025 | 285 | 49.47% | 50.75% | 52.52% | 1.77% | -1.28% | 0.0016 | 0.0024 |
| 2026 | 144 | 45.14% | 50.20% | 51.23% | 1.03% | -5.06% | -0.0036 | -0.0011 |
| 2025-2026 | 429 | 48.02% | 50.56% | 52.09% | 1.52% | -2.54% | -0.0001 | 0.0012 |
| last 365 days | 298 | 45.97% | 50.80% | 52.12% | 1.32% | -4.83% | -0.0032 | -0.0004 |
| latest fold 5 | 129 | 44.19% | 50.09% | 51.02% | 0.93% | -5.90% | -0.0047 | -0.0018 |

## Worst Recent Regime Slices

These are market/residual/title slices in 2025-2026 with enough fights
to be meaningful diagnostics.

| Family | Slice | Fights | Actual - Market | Adj | Selected Delta LL | Fixed-Half Delta LL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| market_probability | 0.60-0.70 | 81 | -6.17% | 4.29% | -0.0223 | -0.0116 |
| market_probability | 0.70-0.80 | 50 | -0.84% | 4.53% | -0.0135 | -0.0069 |
| market_probability | 0.40-0.50 | 54 | 3.25% | 1.06% | 0.0018 | 0.0009 |
| market_probability | <0.40 | 149 | -5.06% | -1.51% | 0.0076 | 0.0050 |
| market_probability | 0.50-0.60 | 70 | 1.84% | 2.07% | 0.0262 | 0.0179 |
| selected_adjustment | >= +5% | 102 | -0.14% | 6.53% | -0.0147 | -0.0075 |
| selected_adjustment | +2% to +5% | 102 | 0.45% | 3.64% | -0.0061 | -0.0018 |
| selected_adjustment | -2% to +2% | 126 | -0.44% | 0.02% | 0.0011 | 0.0009 |
| selected_adjustment | -5% to -2% | 76 | -8.85% | -3.31% | 0.0148 | 0.0098 |
| adjustment_direction | meta_up_on_red | 264 | 0.36% | 4.19% | -0.0077 | -0.0033 |
| adjustment_direction | meta_down_on_red | 165 | -7.19% | -2.73% | 0.0119 | 0.0084 |
| title_group | light_heavyweight | 36 | -0.68% | 2.06% | -0.0210 | -0.0097 |
| title_group | bantamweight | 58 | 1.75% | 1.82% | -0.0085 | -0.0018 |
| title_group | lightweight | 77 | -6.54% | 1.84% | -0.0059 | -0.0034 |
| title_group | welterweight | 56 | 2.47% | 1.22% | -0.0038 | 0.0001 |
| title_group | middleweight | 74 | -6.26% | 1.44% | -0.0005 | 0.0009 |

## Latest-Fold Regime Slices

| Family | Slice | Fights | Actual - Market | Adj | Selected Delta LL | Fixed-Half Delta LL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| market_probability | 0.70-0.80 | 17 | -10.64% | 4.13% | -0.0458 | -0.0273 |
| market_probability | 0.60-0.70 | 21 | -2.90% | 2.58% | -0.0342 | -0.0209 |
| market_probability | <0.40 | 47 | -8.71% | -1.42% | -0.0056 | -0.0030 |
| market_probability | 0.50-0.60 | 26 | -1.19% | 0.55% | 0.0513 | 0.0349 |
| selected_adjustment | >= +5% | 27 | -10.38% | 6.69% | -0.0519 | -0.0308 |
| selected_adjustment | +2% to +5% | 27 | -5.37% | 3.70% | -0.0116 | -0.0068 |
| selected_adjustment | -2% to +2% | 38 | 5.35% | -0.17% | 0.0034 | 0.0023 |
| selected_adjustment | -5% to -2% | 24 | -10.53% | -3.26% | 0.0161 | 0.0114 |
| adjustment_direction | meta_up_on_red | 68 | -3.70% | 4.37% | -0.0242 | -0.0142 |
| adjustment_direction | meta_down_on_red | 61 | -8.36% | -2.89% | 0.0170 | 0.0121 |
| title_group | lightweight | 18 | -13.12% | 2.05% | -0.0482 | -0.0292 |
| title_group | middleweight | 24 | -16.39% | 0.07% | -0.0131 | -0.0072 |
| title_group | flyweight | 15 | -10.36% | -1.20% | -0.0084 | -0.0049 |
| title_group | bantamweight | 19 | -9.41% | 1.64% | 0.0020 | 0.0024 |
| title_group | welterweight | 16 | 2.02% | 1.63% | 0.0125 | 0.0092 |
| title_group | featherweight | 16 | 9.40% | 1.33% | 0.0246 | 0.0170 |

## Worst Recent Top-Feature Bins

Feature bins use quartiles computed on the full residual holdout, then
score only 2025-2026 rows. This is not a selection protocol; it is a
root-cause diagnostic.

| Feature | Bin | Range | Recent Fights | Recent Delta LL | 2024 Delta LL | Delta vs 2024 | Latest Fights | Latest Delta LL | Actual - Market | Adj |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Blue Leg% defense | q1_low | 0.00 to 0.16 | 103 | -0.0189 | 0.0065 | -0.0254 | 33 | -0.0183 | -5.26% | 2.51% |
| Rev. oppdiff | q2 | -0.00 to 0.00 | 175 | -0.0172 | 0.0207 | -0.0379 | 55 | -0.0162 | -1.33% | 1.64% |
| age oppdiff | q2 | -3.00 to 0.00 | 106 | -0.0165 | 0.0199 | -0.0364 | 34 | -0.0371 | -2.75% | 2.46% |
| Blue Clinch | q3 | 0.24 to 0.45 | 110 | -0.0155 | 0.0083 | -0.0239 | 35 | -0.0224 | -5.83% | 1.26% |
| wins oppdiff | q4_high | 0.15 to 1.00 | 109 | -0.0149 | 0.0307 | -0.0456 | 38 | -0.0227 | -3.02% | 4.08% |
| elo oppdiff | q3 | 0.29 to 28.96 | 114 | -0.0126 | 0.0088 | -0.0213 | 27 | -0.0111 | -2.71% | 2.02% |
| Red avg age | q2 | 27.52 to 29.62 | 104 | -0.0111 | 0.0211 | -0.0321 | 30 | -0.0142 | -2.08% | 1.87% |
| Clinch oppdiff | q2 | -0.20 to -0.00 | 113 | -0.0091 | 0.0226 | -0.0317 | 40 | -0.0133 | -4.72% | 1.82% |
| Total str.% defense oppdiff | q3 | 0.01 to 0.09 | 96 | -0.0091 | 0.0017 | -0.0107 | 26 | 0.0010 | -8.94% | 1.54% |
| Blue Clinch differential | q1_low | -14.00 to -0.80 | 95 | -0.0089 | 0.0243 | -0.0332 | 29 | -0.0067 | -0.71% | 1.86% |
| oppelo oppdiff | q1_low | -96.78 to -17.96 | 110 | -0.0085 | 0.0008 | -0.0093 | 31 | 0.0257 | -4.29% | 1.91% |
| KD differential oppdiff | q2 | -0.26 to 0.01 | 122 | -0.0083 | 0.0240 | -0.0323 | 35 | 0.0007 | -6.45% | 1.45% |

## Feature Bins That Broke Versus 2024

| Feature | Bin | Range | Recent Fights | Recent Delta LL | 2024 Delta LL | Delta vs 2024 | Latest Fights | Latest Delta LL | Actual - Market | Adj |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wins oppdiff | q4_high | 0.15 to 1.00 | 109 | -0.0149 | 0.0307 | -0.0456 | 38 | -0.0227 | -3.02% | 4.08% |
| Rev. oppdiff | q2 | -0.00 to 0.00 | 175 | -0.0172 | 0.0207 | -0.0379 | 55 | -0.0162 | -1.33% | 1.64% |
| age oppdiff | q2 | -3.00 to 0.00 | 106 | -0.0165 | 0.0199 | -0.0364 | 34 | -0.0371 | -2.75% | 2.46% |
| Body% differential oppdiff | q4_high | 0.20 to 1.29 | 108 | -0.0011 | 0.0351 | -0.0362 | 34 | -0.0045 | 1.93% | 1.97% |
| Blue Sub. att differential | q3 | 0.00 to 0.27 | 101 | -0.0064 | 0.0283 | -0.0347 | 24 | -0.0392 | 6.19% | 1.64% |
| Blue Clinch differential | q1_low | -14.00 to -0.80 | 95 | -0.0089 | 0.0243 | -0.0332 | 29 | -0.0067 | -0.71% | 1.86% |
| KD differential oppdiff | q2 | -0.26 to 0.01 | 122 | -0.0083 | 0.0240 | -0.0323 | 35 | 0.0007 | -6.45% | 1.45% |
| Red avg age | q2 | 27.52 to 29.62 | 104 | -0.0111 | 0.0211 | -0.0321 | 30 | -0.0142 | -2.08% | 1.87% |
| Clinch oppdiff | q2 | -0.20 to -0.00 | 113 | -0.0091 | 0.0226 | -0.0317 | 40 | -0.0133 | -4.72% | 1.82% |
| elo oppdiff | q4_high | 29.11 to 144.85 | 107 | -0.0029 | 0.0262 | -0.0292 | 37 | -0.0224 | -3.17% | 3.34% |
| KD differential oppdiff | q3 | 0.01 to 0.27 | 105 | -0.0066 | 0.0225 | -0.0291 | 35 | -0.0179 | 0.47% | 1.55% |
| totalfights oppdiff | q1_low | -36.00 to -5.00 | 125 | -0.0046 | 0.0220 | -0.0266 | 37 | -0.0102 | -1.20% | 2.80% |

## Largest Top-Feature Distribution Shifts

| Feature | 2024 Mean | 2025-2026 Mean | Std Shift | Latest Mean | Latest Std Shift | Corr Delta LL | Corr Adj |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Blue Clinch | 0.422 | 0.300 | -0.305 | 0.307 | -0.287 | 0.035 | -0.041 |
| Blue Leg% defense | 0.290 | 0.330 | 0.183 | 0.334 | 0.199 | 0.052 | -0.119 |
| Blue Sig. str. differential | 4.475 | 2.583 | -0.157 | 1.270 | -0.265 | -0.008 | -0.255 |
| wins oppdiff | -0.014 | 0.014 | 0.114 | -0.007 | 0.029 | -0.004 | 0.522 |
| Blue Clinch differential | 0.560 | 0.264 | -0.113 | 0.138 | -0.162 | -0.019 | -0.093 |
| Blue avg age | 29.376 | 29.739 | 0.109 | 29.479 | 0.031 | -0.003 | 0.348 |
| totalfights oppdiff | 0.633 | -0.345 | -0.104 | -0.233 | -0.092 | 0.023 | -0.320 |
| age oppdiff | 0.557 | 0.029 | -0.092 | 0.220 | -0.059 | 0.026 | -0.556 |
| Red Sub. att | 0.052 | 0.043 | -0.091 | 0.036 | -0.165 | 0.006 | -0.032 |
| Total str.% defense oppdiff | 0.006 | -0.005 | -0.080 | -0.008 | -0.105 | 0.009 | 0.231 |
| Clinch oppdiff | -0.013 | 0.036 | 0.078 | 0.012 | 0.041 | -0.020 | -0.007 |
| oppelo oppdiff | 1.540 | -0.647 | -0.071 | 0.632 | -0.030 | 0.047 | -0.104 |

## Interpretation

- The recent 2025-2026 residual is weak: selected-shrinkage Delta LL is `-0.0001` with realized market residual `-2.54%`.
- The latest fold remains the cleanest warning sign: selected-shrinkage Delta LL is `-0.0047` while the model still adjusts red probability by `0.93%` on average.
- The worst recent simple regime is `market_probability` / `0.60-0.70` with Delta LL `-0.0223` and realized market residual `-6.17%`.
- The worst recent top-feature bin is `Blue Leg% defense` `q1_low` with Delta LL `-0.0189` over `103` recent fights; treat this as a drift clue, not a tradable rule.
- This audit does not justify adding capacity or a new hand-picked feature yet. The next feature work should target drift explanations that can be predeclared, then validated in rolling folds or future paper tracking.
