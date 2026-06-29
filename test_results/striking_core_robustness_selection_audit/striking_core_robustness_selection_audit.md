# Striking Core Robustness Selection Audit

This audit tests whether the striking-core clue survives a stricter
rolling policy-selection protocol. A small family of feature variants
and pre-fight experience gates is predefined, then one policy is selected
for each evaluation fold using only prior fold log-loss deltas.

## Protocol

- feature table: `data/detailed_fights.csv`
- odds table: `data/fight_results_with_odds.csv`
- aligned men-only rows: `1223`
- rolling folds: `7`
- candidate policies: `15`
- first holdout start: `2023-01-01`
- last holdout end: `2026-06-27`
- logistic L2 C: `0.1`
- selection minimum prior rows: `80`
- market-null iterations: `200`

## Rolling Selection Result

| Policy | Rows | Candidate LL | Market Delta LL | Brier Delta | Positive Folds | Bootstrap P(delta<=0) | Selection-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_selected_prior_delta` | 718 | 0.5983 | 0.0040 | 0.0016 | 4 / 6 | 0.131 | 0.035 |

Selection path:

| Fold | Selected Policy | Prior Rows | Prior Score | Eval Rows | Eval Delta LL |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | `raw_sig_head|all` | 121 | 0.0112 | 118 | -0.0029 |
| 3 | `sigpct_head|all` | 239 | 0.0049 | 151 | 0.0030 |
| 4 | `sigpct_head|all` | 390 | 0.0042 | 142 | 0.0110 |
| 5 | `sigpct_head|all` | 532 | 0.0060 | 138 | 0.0049 |
| 6 | `raw_sig_head|min5` | 413 | 0.0062 | 89 | -0.0004 |
| 7 | `mixed_core|min5` | 502 | 0.0072 | 80 | 0.0069 |

## Best Fixed Policies In Hindsight

| Policy | Rows | Market Delta LL | Brier Delta | Positive Folds | Bootstrap P(delta<=0) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `sigpct_head|min10` | 202 | 0.0075 | 0.0024 | 4 / 7 | 0.087 |
| `mixed_core|min5` | 582 | 0.0072 | 0.0026 | 6 / 7 | 0.031 |
| `sigpct_head|all` | 961 | 0.0071 | 0.0027 | 7 / 7 | 0.013 |
| `mixed_core_clip99|min5` | 582 | 0.0071 | 0.0025 | 6 / 7 | 0.034 |
| `sigpct_head|min5` | 582 | 0.0069 | 0.0024 | 5 / 7 | 0.031 |
| `mixed_core|all` | 961 | 0.0068 | 0.0025 | 6 / 7 | 0.020 |
| `mixed_core_clip99|all` | 961 | 0.0066 | 0.0025 | 6 / 7 | 0.025 |
| `sigpct_only|min10` | 202 | 0.0057 | 0.0021 | 5 / 7 | 0.107 |
| `sigpct_only|all` | 961 | 0.0056 | 0.0023 | 6 / 7 | 0.034 |
| `mixed_core|min10` | 202 | 0.0056 | 0.0016 | 5 / 7 | 0.163 |
| `mixed_core_clip99|min10` | 202 | 0.0055 | 0.0016 | 5 / 7 | 0.164 |
| `sigpct_only|min5` | 582 | 0.0053 | 0.0020 | 5 / 7 | 0.055 |

## Candidate Family

| Policy | Note |
| --- | --- |
| `mixed_core|all` | frozen mixed significant-strike/head core; gate: all aligned men-only fights |
| `mixed_core|min5` | frozen mixed significant-strike/head core; gate: both fighters have at least five prior fights |
| `mixed_core|min10` | frozen mixed significant-strike/head core; gate: both fighters have at least ten prior fights |
| `mixed_core_clip99|all` | same core with train-only symmetric absolute clipping; gate: all aligned men-only fights |
| `mixed_core_clip99|min5` | same core with train-only symmetric absolute clipping; gate: both fighters have at least five prior fights |
| `mixed_core_clip99|min10` | same core with train-only symmetric absolute clipping; gate: both fighters have at least ten prior fights |
| `sigpct_head|all` | drops raw significant-strike differential to reduce collinearity; gate: all aligned men-only fights |
| `sigpct_head|min5` | drops raw significant-strike differential to reduce collinearity; gate: both fighters have at least five prior fights |
| `sigpct_head|min10` | drops raw significant-strike differential to reduce collinearity; gate: both fighters have at least ten prior fights |
| `sigpct_only|all` | market plus strongest single forensics residual-shape feature; gate: all aligned men-only fights |
| `sigpct_only|min5` | market plus strongest single forensics residual-shape feature; gate: both fighters have at least five prior fights |
| `sigpct_only|min10` | market plus strongest single forensics residual-shape feature; gate: both fighters have at least ten prior fights |
| `raw_sig_head|all` | raw significant-strike/head differential reference; gate: all aligned men-only fights |
| `raw_sig_head|min5` | raw significant-strike/head differential reference; gate: both fighters have at least five prior fights |
| `raw_sig_head|min10` | raw significant-strike/head differential reference; gate: both fighters have at least ten prior fights |

## Interpretation

- Rolling prior-fold selection preserved a positive edge and cleared the unadjusted selection-null screen.
- The fixed-policy table is hindsight context only; the rolling-selected row is the main robustness result.
- This is still not proof of a live edge: the event-bootstrap interval crosses zero, and the candidate family was designed after earlier striking-feature discovery.
