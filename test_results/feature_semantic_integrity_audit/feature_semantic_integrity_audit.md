# Feature Semantic Integrity Audit

This audit checks whether the current feature table obeys mechanical
feature invariants and whether high-importance feature names mean what
they appear to mean in fight context. It does not train or select a new
model.

## Mechanical Checks

| Check | Value |
| --- | ---: |
| feature rows | 4322 |
| feature columns | 197 |
| active model features | 182 |
| oppdiff pairs checked | 64 |
| oppdiff row-level checks | 276527 |
| oppdiff mismatches | 0 |
| expected supervised rows from source | 4322 |
| matched source rows | 4322 |
| missing feature rows | 0 |
| extra feature rows | 0 |
| core pre-fight state checks | 69152 |
| core pre-fight state mismatches | 0 |
| side-specific active features | 122 |
| active features missing table counterpart | 0 |
| active features missing model counterpart | 0 |
| feature rows with same-day prior fighter state | 0 |

## Semantic Warnings

| Warning Family | Active Features | Importance Sum |
| --- | ---: | ---: |
| raw DOB / birth-year proxies | 2 | 13 |
| target/position-mix defense proxies | 18 | 282 |
| side percentage values scaled by elapsed fight time | 18 | 239 |

Top flagged active features by current regularized-LGBM importance:

| Feature | Importance | Why Flagged |
| --- | ---: | --- |
| `Blue Leg% defense` | 28 | target/position mix defense proxy, not conventional defensive success |
| `Distance% defense oppdiff` | 28 | target/position mix defense proxy, not conventional defensive success |
| `Red Leg% defense` | 26 | target/position mix defense proxy, not conventional defensive success |
| `Red Leg%` | 25 | weighted percentage-side feature; generator scales side values by elapsed fight time |
| `Red Clinch%` | 24 | weighted percentage-side feature; generator scales side values by elapsed fight time |
| `Leg% defense oppdiff` | 24 | target/position mix defense proxy, not conventional defensive success |
| `Head% defense oppdiff` | 18 | target/position mix defense proxy, not conventional defensive success |
| `Blue Head% defense` | 17 | target/position mix defense proxy, not conventional defensive success |
| `Ground% defense oppdiff` | 17 | target/position mix defense proxy, not conventional defensive success |
| `Blue Body%` | 16 | weighted percentage-side feature; generator scales side values by elapsed fight time |
| `Body% oppdiff` | 15 | weighted percentage-side feature; generator scales side values by elapsed fight time |
| `Clinch% defense oppdiff` | 15 | target/position mix defense proxy, not conventional defensive success |
| `Red Td%` | 14 | weighted percentage-side feature; generator scales side values by elapsed fight time |
| `Blue Body% defense` | 14 | target/position mix defense proxy, not conventional defensive success |
| `Blue Leg%` | 14 | weighted percentage-side feature; generator scales side values by elapsed fight time |

## Interpretation

- No hard arithmetic, source-row matching, core pre-fight state, or active side-swap coverage failure was found.
- No supervised feature rows used same-day prior state for the same fighter, so card-level chronological leakage was not detected in this table.
- The bigger issue is semantic, not arithmetic: several active percentage/defense columns are proxies created by the historical generator, not literal fight-skill concepts.
- Treat these columns as empirical model inputs unless a follow-up feature redesign gives them clearer fight meaning and validates after market control.
