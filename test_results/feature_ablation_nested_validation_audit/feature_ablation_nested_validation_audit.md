# Feature Ablation Nested Validation Audit

This audit tests whether semantic feature ablations survive stricter
long-history model/strategy selection. It compares baseline default,
current regularized, and all semantic ablation variants. Each nested
fold selects a model and betting strategy on the previous 365 days and
evaluates the next 182-day holdout.

## Long Ledgers

| Model | Fights | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_default | 1249 | 62.53% | 0.6447 | 0.6006 | 0.0450 | 25.07% | 1019 |
| current_regularized | 1249 | 63.65% | 0.6396 | 0.6006 | 0.0398 | 29.61% | 970 |
| drop_target_mix_defense | 1249 | 62.85% | 0.6398 | 0.6006 | 0.0401 | 7.00% | 968 |
| drop_muddy_pct_and_dob | 1249 | 63.49% | 0.6402 | 0.6006 | 0.0405 | 20.12% | 970 |
| drop_all_percentage | 1249 | 62.45% | 0.6449 | 0.6006 | 0.0450 | -29.99% | 971 |

## Nested Selection

| Objective | Folds | Fights | Bets | Profit | ROI | Positive Folds | Selected Models | Market-Null p | Bootstrap P(profit <= 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| profit | 7 | 962 | 220 | $130.83 | 4.26% | 3 / 7 | baseline_default: 1, current_regularized: 1, drop_muddy_pct_and_dob: 3, drop_target_mix_defense: 2 | 0.257 | 0.330 |
| roi | 7 | 962 | 147 | $-19.65 | -2.00% | 3 / 7 | current_regularized: 2, drop_muddy_pct_and_dob: 3, drop_target_mix_defense: 2 | 0.580 | 0.574 |

## Interpretation

- Long standalone best model log loss was `current_regularized` at 0.6396; best plain-strategy PnL was `current_regularized` at 29.61%.
- Every standalone model ledger still trailed de-vigged market log loss.
- `profit` selected ablation models in 5/7 folds.
- `roi` selected ablation models in 5/7 folds.
- The ablation family does not validate: even when the nested selector often chooses ablated models, the profit objective has weak market-null/bootstrap support and the ROI objective loses money.
- Do not promote these ablations into production or the edge claim. The useful lesson is narrower: percentage/defense semantics deserve redesign, but the tested removals are not a validated improvement.
