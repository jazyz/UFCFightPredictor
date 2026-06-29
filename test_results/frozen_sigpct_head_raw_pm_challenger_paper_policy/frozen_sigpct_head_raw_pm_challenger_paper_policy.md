# Frozen SigPct-Head-RawPM Challenger Paper Policy

As of `2026-06-29`, this freezes a head-focused striking redesign challenger
for future pre-outcome paper tracking. It is not a replacement for the already
frozen mixed-core, sigpct-head, or pace-adjusted striking paper policies.

## Policy

The policy uses a men-only market-aware logistic model:

```text
market_logit
+ Sig. str.% differential oppdiff
+ Head differential oppdiff
+ Head differential_pm oppdiff
```

`Head differential_pm oppdiff` is source-derived from chronological
`data/modified_fight_details.csv`. The scorer reconstructs that pace-adjusted
feature through `train_through` for historical training rows and upcoming
feature rows.

Frozen scoring contract:

- men-only universe; do not train on or evaluate women's fights
- fit L2 logistic regression with `C = 0.1`
- derive pace-adjusted head-strike features from chronological source fights
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
| aligned rows missing pace features | 0 |

Fixed `sigpct_head_raw_pm` probability result:

| Metric | Value |
| --- | ---: |
| fights | 961 |
| market - candidate log loss | +0.0081 |
| Brier delta | +0.0030 |
| accuracy | 69.51% |
| positive folds | 7 / 7 |
| event-bootstrap P(delta <= 0) | 0.0060 |
| market-null p | 0.0033 |

Fixed `2%` positive-edge uncapped paper ledger diagnostic:

| Metric | Value |
| --- | ---: |
| bets | 730 |
| profit | +38.04u |
| ROI | 5.21% |
| actual - market | 5.49% |
| positive folds | 7 / 7 |
| event-bootstrap P(profit <= 0) | 0.0423 |
| market-null p | 0.0015 |

Rolling prior-fold redesign-selector diagnostics:

| Selector | Result | Selection-Null p | Bootstrap P |
| --- | ---: | ---: | ---: |
| probability-delta selector | +0.0066 LL | 0.0050 | 0.0365 |
| profit selector | +34.41u | 0.0299 | 0.0368 |

Follow-up feature-context audit:

```text
test_results/striking_policy_feature_context_audit/striking_policy_feature_context_audit.md
```

That audit found `0` hard reconstruction/chronology failures for the exact
frozen inputs and no same-day market-aligned source-order leakage. It also
found that `Head differential_pm oppdiff` has a negative standardized
coefficient in all seven folds when paired with raw `Head differential
oppdiff`, so read it as a conditional pace-normalizer rather than a standalone
"more head pace is better" feature.

## Generate Paper Ledger

```bash
.venv/bin/python testing/score_frozen_striking_core_policy.py \
  --policy test_results/frozen_sigpct_head_raw_pm_challenger_paper_policy/frozen_sigpct_head_raw_pm_challenger_paper_policy.json \
  --fights path/to/fight_card_odds.csv \
  --event-key unique-event-key \
  --fight-card-link https://example.com/card \
  --output-csv test_results/forward_paper_tracking/latest_sigpct_head_raw_pm_challenger_paper_bets.csv \
  --output-json test_results/forward_paper_tracking/latest_sigpct_head_raw_pm_challenger_paper_bets.json
```

Before using a generated ledger as evidence, regenerate
`data/predict_fights_alpha.csv` for the target card before outcomes are known.
The input CSV must include `fighter1`, `fighter2`, `fighter1_odds`, and
`fighter2_odds`; optional `fight_index`, `event_key`, and `fight_card_link`
columns are preserved in the ledger.

## Interpretation

This is the strongest historical feature-redesign evidence so far, but it is
still not a live-edge proof. The redesign family was motivated by prior
striking feature forensics, the selection-null run has only `200` simulations,
the head pace term is semantically conditional, and no post-freeze outcomes
exist. Treat this as a frozen future-evidence collection contract, not a live
staking recommendation.
