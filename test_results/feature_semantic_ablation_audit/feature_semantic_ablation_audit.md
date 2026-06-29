# Feature Semantic Ablation Audit

This audit removes semantically muddy feature families identified by the
feature semantic-integrity audit, then reruns the same regularized
leak-safe LightGBM backtests. It tests whether those feature families
look helpful, harmful, or merely noisy.

## Variants

| Variant | Dropped Columns | Remaining Columns | Description |
| --- | ---: | ---: | --- |
| drop_target_mix_defense | 18 | 179 | drop target/position-mix defense proxies such as Head% defense and Leg% defense |
| drop_muddy_pct_and_dob | 48 | 149 | drop target-mix defense proxies, side percentage proxies scaled by elapsed fight time, and raw DOB proxies |
| drop_all_percentage | 81 | 116 | drop all percentage-derived columns |

## 1y Leak-Safe Results

| Variant | Fights | Feature Columns | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current_regularized | 298 | 182 | 64.43% | 0.6418 | 0.6127 | 0.0290 | 24.66% | 229 |
| drop_target_mix_defense | 298 | 164 | 62.08% | 0.6414 | 0.6127 | 0.0286 | 3.45% | 224 |
| drop_muddy_pct_and_dob | 298 | 144 | 64.43% | 0.6450 | 0.6127 | 0.0323 | 20.13% | 228 |
| drop_all_percentage | 298 | 110 | 63.09% | 0.6543 | 0.6127 | 0.0416 | -5.72% | 222 |

## 2y Leak-Safe Results

| Variant | Fights | Feature Columns | Accuracy | Model LL | Market LL | Model - Market LL | Profit | Bets |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current_regularized | 580 | 182 | 65.00% | 0.6318 | 0.5995 | 0.0324 | 61.20% | 442 |
| drop_target_mix_defense | 580 | 164 | 64.83% | 0.6304 | 0.5995 | 0.0311 | 50.30% | 433 |
| drop_muddy_pct_and_dob | 580 | 144 | 66.90% | 0.6335 | 0.5995 | 0.0343 | 78.75% | 434 |
| drop_all_percentage | 580 | 110 | 65.17% | 0.6366 | 0.5995 | 0.0375 | 20.28% | 428 |

## Interpretation

- 1y: best model log loss was `drop_target_mix_defense` (0.6414), while current regularized was 0.6418; best PnL was `current_regularized` (24.66%), while current regularized was 24.66%.
- 1y: every ablation still trailed the de-vigged market on aligned log loss.
- 2y: best model log loss was `drop_target_mix_defense` (0.6304), while current regularized was 0.6318; best PnL was `drop_muddy_pct_and_dob` (78.75%), while current regularized was 61.20%.
- 2y: every ablation still trailed the de-vigged market on aligned log loss.
- These are ablations, not new feature promotions. The narrow target-mix-defense drop is a probability-cleanup candidate; the broader drop's 2y PnL gain needs nested validation because its log loss worsened.
