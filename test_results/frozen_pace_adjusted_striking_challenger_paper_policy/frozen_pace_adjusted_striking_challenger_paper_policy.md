# Frozen Pace-Adjusted Striking Challenger Paper Policy

As of `2026-06-29`, this freezes a pace-adjusted striking challenger for
future pre-outcome paper tracking. It is not a replacement for the already
frozen mixed-core or sigpct-head striking paper policies.

## Policy

The policy uses a men-only market-aware logistic model:

```text
market_logit
+ Sig. str.% differential oppdiff
+ Sig. str. differential_pm oppdiff
+ Head differential_pm oppdiff
```

The `*_differential_pm` columns are source-derived pace-adjusted features. The
scorer reconstructs them from chronological `data/modified_fight_details.csv`
through `train_through` for both historical training rows and upcoming feature
rows.

Frozen scoring contract:

- men-only universe; do not train on or evaluate women's fights
- fit L2 logistic regression with `C = 0.1`
- derive pace-adjusted striking features from chronological source fights
- use red/blue mirrored training and mirrored probability averaging
- select the side with highest `policy probability - market probability`
- paper bet only when selected edge is at least `2.00%`
- flat `1u` stake
- no event cap

## Evidence

Feature construction:

| Check | Value |
| --- | ---: |
| source rows | 7,730 |
| feature rows | 4,322 |
| side-rate reconstruction checks | 69,152 |
| side-rate mismatches | 0 |

Fixed pace-adjusted mixed-core probability result:

| Metric | Value |
| --- | ---: |
| fights | 961 |
| market - candidate log loss | +0.0068 |
| Brier delta | +0.0028 |
| accuracy | 69.30% |
| positive folds | 6 / 7 |
| event-bootstrap P(delta <= 0) | 0.0206 |

Fixed `2%` positive-edge uncapped paper ledger diagnostic:

| Metric | Value |
| --- | ---: |
| bets | 695 |
| profit | +41.97u |
| ROI | 6.04% |
| actual - market | 5.85% |
| positive folds | 6 / 7 |
| event-bootstrap P(profit <= 0) | 0.0206 |
| market-null p | 0.0011 |

Rolling prior-fold selector diagnostics:

| Selector | Result | Selection-Null p | Bootstrap P |
| --- | ---: | ---: | ---: |
| probability-delta selector | +0.0039 LL | 0.0149 | 0.1643 |
| profit selector | +30.73u | 0.0398 | 0.0581 |

## Generate Paper Ledger

```bash
.venv/bin/python testing/score_frozen_striking_core_policy.py \
  --policy test_results/frozen_pace_adjusted_striking_challenger_paper_policy/frozen_pace_adjusted_striking_challenger_paper_policy.json \
  --fights path/to/fight_card_odds.csv \
  --event-key unique-event-key \
  --fight-card-link https://example.com/card \
  --output-csv test_results/forward_paper_tracking/latest_pace_adjusted_striking_challenger_paper_bets.csv \
  --output-json test_results/forward_paper_tracking/latest_pace_adjusted_striking_challenger_paper_bets.json
```

Before using a generated ledger as evidence, regenerate
`data/predict_fights_alpha.csv` for the target card before outcomes are known.
The input CSV must include `fighter1`, `fighter2`, `fighter1_odds`, and
`fighter2_odds`; optional `fight_index`, `event_key`, and `fight_card_link`
columns are preserved in the ledger.

## Interpretation

This is stronger historical evidence for the pace-adjusted striking feature
direction, but it is still not a live-edge proof. The feature family was
designed after prior striking-core discovery, the rolling probability
selector's event-bootstrap support is weak, and the rolling profit selector's
event-bootstrap support is marginal. Treat this as a frozen future-evidence
collection contract, not a live staking recommendation.
