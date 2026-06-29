# Residual Meta Recency Weight Audit

This audit tests whether recent residual drift can be repaired at the
small logistic residual-meta layer by using shorter development windows
or exponential recency weights. It uses only saved leak-safe ledgers and
does not retrain the base UFC model.

## Candidate Configs

| Candidate | Dev Days | C | Half-Life Days |
| --- | ---: | ---: | ---: |
| dev365_c1_unweighted | 365 | 1.0 | unweighted |
| dev365_c1_hl365 | 365 | 1.0 | 365.0 |
| dev365_c1_hl182 | 365 | 1.0 | 182.0 |
| dev365_c1_hl91 | 365 | 1.0 | 91.0 |
| dev730_c1_unweighted | 730 | 1.0 | unweighted |
| dev730_c1_hl365 | 730 | 1.0 | 365.0 |
| dev730_c1_hl182 | 730 | 1.0 | 182.0 |
| dev730_c025_unweighted | 730 | 0.25 | unweighted |

## Full-Holdout Candidate Results

| Candidate | Fights | Market LL | Meta LL | Delta LL | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev365_c1_hl182 | 704 | 0.6009 | 0.5958 | 0.0050 | 5 / 5 |
| dev365_c1_hl365 | 704 | 0.6009 | 0.5960 | 0.0049 | 5 / 5 |
| dev365_c1_hl91 | 704 | 0.6009 | 0.5960 | 0.0049 | 4 / 5 |
| dev365_c1_unweighted | 704 | 0.6009 | 0.5962 | 0.0047 | 4 / 5 |
| dev730_c1_hl182 | 704 | 0.6009 | 0.5964 | 0.0045 | 4 / 5 |
| dev730_c1_hl365 | 704 | 0.6009 | 0.5970 | 0.0038 | 4 / 5 |
| dev730_c1_unweighted | 704 | 0.6009 | 0.5979 | 0.0030 | 4 / 5 |
| dev730_c025_unweighted | 704 | 0.6009 | 0.5981 | 0.0028 | 4 / 5 |

## Fixed Candidates On Rolling Evaluation Folds

| Candidate | Fights | Market LL | Meta LL | Delta LL |
| --- | ---: | ---: | ---: | ---: |
| dev365_c1_hl182 | 539 | 0.6022 | 0.5975 | 0.0047 |
| dev365_c1_hl91 | 539 | 0.6022 | 0.5977 | 0.0045 |
| dev365_c1_hl365 | 539 | 0.6022 | 0.5977 | 0.0045 |
| dev365_c1_unweighted | 539 | 0.6022 | 0.5980 | 0.0041 |
| dev730_c1_hl182 | 539 | 0.6022 | 0.5984 | 0.0038 |
| dev730_c1_hl365 | 539 | 0.6022 | 0.5993 | 0.0029 |
| dev730_c1_unweighted | 539 | 0.6022 | 0.6004 | 0.0018 |
| dev730_c025_unweighted | 539 | 0.6022 | 0.6005 | 0.0017 |

## Rolling Prior-Fold Selection

| Eval Fold | Selected Candidate | Prior Delta LL | Eval Fights | Eval Delta LL |
| ---: | --- | ---: | ---: | ---: |
| 2 | dev730_c1_unweighted | 0.0070 | 130 | 0.0077 |
| 3 | dev365_c1_unweighted | 0.0076 | 150 | 0.0042 |
| 4 | dev365_c1_hl91 | 0.0073 | 130 | 0.0019 |
| 5 | dev730_c1_hl182 | 0.0063 | 129 | -0.0036 |

| Combined Eval | Fights | Market LL | Meta LL | Delta LL | Positive Folds | Bootstrap P(delta <= 0) | Market-Null p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rolling selected recency meta | 539 | 0.6022 | 0.5995 | 0.0026 | 3 / 4 | 0.286 | 0.016 |

## Interpretation

- Rolling selection chose: `dev365_c1_hl91, dev365_c1_unweighted, dev730_c1_hl182, dev730_c1_unweighted`.
- This is the validation result; fixed full-holdout candidate wins are diagnostic only.
- At least one recency-weighted candidate was selected before an evaluation fold, so the weighting idea has some prior-fold support.
- The market-null result is supportive, but event-bootstrap uncertainty and the negative latest fold still block changing the residual transform or edge claim.
