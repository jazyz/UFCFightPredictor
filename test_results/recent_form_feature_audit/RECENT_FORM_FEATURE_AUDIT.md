# Recent Form Feature Audit

This audit builds an alternate feature table with recent-form and recent-activity
features computed only from source fights strictly before each modeled fight date.

## Feature Build

- source fights: `data/modified_fight_details.csv`
- base features: `data/detailed_fights.csv`
- output features: `test_results/recent_form_feature_audit/detailed_fights_recent_form.csv`
- rows: `4322`
- added columns: `128`

Feature families include last-3/last-5 result score, binary win rate,
finish win/loss rate, non-binary rate, minutes, recent striking/grappling
rates, knockdown rates, and 365/730-day activity counts.

## Leak-Safe Comparison

| Window | Feature Set | Fights | Accuracy | Log Loss | Final Bankroll | PnL | Market LL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-06-27 to 2026-06-27 | current regularized | 298 | 64.43% | 0.6418 | $1,246.65 | 24.66% |  |
| 2025-06-27 to 2026-06-27 | recent-form challenger | 298 | 63.09% | 0.6436 | $1,025.72 | 2.57% |  |
| 2024-06-27 to 2026-06-27 | current regularized | 580 | 65.00% | 0.6318 | $1,611.97 | 61.20% |  |
| 2024-06-27 to 2026-06-27 | recent-form challenger | 580 | 64.66% | 0.6370 | $1,191.24 | 19.12% |  |

## Interpretation

The recent-form challenger does not improve summarized log loss versus the current regularized feature set. Do not promote this feature family.
