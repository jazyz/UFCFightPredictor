# Striking Core Betting And Calibration Audit

This audit asks whether the striking-core probability edge translates
into uncapped flat betting at fixed positive-edge thresholds, and whether
Brier/ECE calibration diagnostics agree with the log-loss result.

## Protocol

- aligned men-only rows: `1223`
- rolling folds: `7`
- rolling selection eval folds: `2, 3, 4, 5, 6, 7`
- edge thresholds: `0.00%, 2.00%, 5.00%`
- event cap: none
- bet market-null iterations: `20000`

## Calibration And Probability Metrics

| Policy | Rows | Market Delta LL | Brier Delta | Market ECE | Candidate ECE | Candidate-Market ECE | Mean Abs Move |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_selected_prior_delta` | 718 | 0.0040 | 0.0016 | 3.30% | 4.14% | 0.84% | 3.70% |
| `mixed_core|all` | 840 | 0.0067 | 0.0026 | 3.47% | 4.05% | 0.58% | 4.01% |
| `sigpct_head|all` | 840 | 0.0072 | 0.0029 | 3.47% | 3.59% | 0.12% | 3.90% |
| `mixed_core|min5` | 509 | 0.0081 | 0.0030 | 3.58% | 4.34% | 0.76% | 3.73% |
| `sigpct_head|min5` | 509 | 0.0084 | 0.0031 | 3.58% | 5.01% | 1.43% | 3.61% |

## Uncapped Flat Betting

| Policy | Threshold | Bets | Profit | ROI | Positive Folds | Mean Edge | Market-Null p | Boot P(profit<=0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_selected_prior_delta` | 0.00% | 718 | -1.96u | -0.27% | 3 / 6 | 3.70% | 0.097 | 0.542 |
| `rolling_selected_prior_delta` | 2.00% | 526 | +20.98u | 3.99% | 5 / 6 | 4.66% | 0.006 | 0.090 |
| `rolling_selected_prior_delta` | 5.00% | 163 | +12.32u | 7.56% | 5 / 6 | 7.21% | 0.017 | 0.091 |
| `mixed_core|all` | 0.00% | 840 | +8.71u | 1.04% | 3 / 6 | 4.01% | 0.051 | 0.352 |
| `mixed_core|all` | 2.00% | 627 | +32.48u | 5.18% | 5 / 6 | 5.04% | 0.001 | 0.046 |
| `mixed_core|all` | 5.00% | 250 | +11.27u | 4.51% | 5 / 6 | 7.35% | 0.037 | 0.181 |
| `sigpct_head|all` | 0.00% | 840 | +7.75u | 0.92% | 4 / 6 | 3.90% | 0.054 | 0.373 |
| `sigpct_head|all` | 2.00% | 619 | +32.78u | 5.29% | 5 / 6 | 4.91% | 0.002 | 0.052 |
| `sigpct_head|all` | 5.00% | 218 | +23.37u | 10.72% | 5 / 6 | 7.42% | 0.002 | 0.018 |
| `mixed_core|min5` | 0.00% | 509 | +13.48u | 2.65% | 4 / 6 | 3.73% | 0.028 | 0.235 |
| `mixed_core|min5` | 2.00% | 372 | +23.10u | 6.21% | 6 / 6 | 4.76% | 0.005 | 0.062 |
| `mixed_core|min5` | 5.00% | 138 | +15.24u | 11.04% | 5 / 6 | 6.95% | 0.008 | 0.044 |
| `sigpct_head|min5` | 0.00% | 509 | +11.82u | 2.32% | 4 / 6 | 3.61% | 0.035 | 0.252 |
| `sigpct_head|min5` | 2.00% | 363 | +28.17u | 7.76% | 5 / 6 | 4.64% | 0.001 | 0.033 |
| `sigpct_head|min5` | 5.00% | 117 | +16.15u | 13.80% | 5 / 6 | 7.01% | 0.004 | 0.022 |

## Interpretation

- The rolling-selected policy's fixed 2% edge ledger is profitable and clears the conditional market-null PnL screen.
- PnL market-null tests here are conditional on the selected historical bets; the probability selection-null result remains in the robustness audit.
- Calibration is mixed: log loss and Brier improve, but ECE often worsens versus market, so this looks more like an edge-ranking signal than a globally better probability surface.
- The main edge claim still depends on future frozen pre-outcome paper tracking, not these retrospective threshold rows.
- Primary 2% ledger: profit +20.98u, ROI 3.99%, market-null p 0.006, bootstrap P(profit<=0) 0.090.
