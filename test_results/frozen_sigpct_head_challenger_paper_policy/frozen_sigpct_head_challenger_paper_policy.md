# Frozen SigPct-Head Challenger Paper Policy

As-of date: `2026-06-29`
Source robustness audit: `test_results/striking_core_robustness_selection_audit/striking_core_robustness_selection_audit.json`
Source betting/calibration audit: `test_results/striking_core_betting_calibration_audit/striking_core_betting_calibration_audit.json`

This is a challenger paper-tracking contract only. It does not replace the
already frozen `mixed_sig_head_core` policy and is not a live staking
recommendation. The feature subset was motivated after prior striking-feature
research, so future pre-outcome ledgers must be tracked unchanged before this
can support an edge claim.

## Probability Model

Challenger:

```text
sigpct_head_all =
market_logit
+ Sig. str.% differential oppdiff
+ Head differential oppdiff
```

Training and scoring rules:

1. Use the men-only universe; do not train on or evaluate women's fights.
2. Train on all aligned historical feature/odds rows available before scoring,
   or before an explicit `--train-through` date when replaying a card.
3. Use de-vigged market probability converted to `market_logit`.
4. Fit L2 logistic regression with `C = 0.1`, median imputation, standard
   scaling, red/blue mirrored training, and mirrored probability averaging.
5. Score each future fight from the regenerated upcoming feature table.

## Paper Betting Rule

For each future fight with odds and a feature row:

1. Compute both sides' de-vigged market probabilities.
2. Score both sides with the frozen challenger model.
3. Select the side with the larger edge: `policy probability - market probability`.
4. Paper bet only when the selected edge is at least `2.00%`.
5. Use a flat `1.00u` paper stake.

| Rule | Value |
| --- | ---: |
| model variant | `sigpct_head_all` |
| logistic C | 0.1 |
| minimum edge | 2.00% |
| minimum probability | 0.00% |
| event cap | none |
| stake | 1.00u flat paper stake |

## Historical Evidence

Fixed-policy robustness context over seven rolling folds:

| Metric | Value |
| --- | ---: |
| aligned rows | 1,223 |
| fixed-policy rows | 961 |
| market delta log loss | +0.0071 |
| Brier delta | +0.0027 |
| positive folds | 7 / 7 |
| event-bootstrap P(delta <= 0) | 0.013 |

Betting/calibration context on rolling-selection eval folds `2-7`:

| Metric | Value |
| --- | ---: |
| rows | 840 |
| market delta log loss | +0.0072 |
| Brier delta | +0.0029 |
| market ECE | 3.47% |
| candidate ECE | 3.59% |
| mean absolute probability move | 3.90% |

Descriptive uncapped `2%` positive-edge flat ledger on folds `2-7`:

| Metric | Value |
| --- | ---: |
| paper bets | 619 |
| flat profit | +32.78u |
| ROI | 5.29% |
| positive folds | 5 / 6 |
| mean edge | 4.91% |
| market-null p-value | 0.002 |
| event-bootstrap P(profit <= 0) | 0.052 |

## Generate A Forward Ledger

Regenerate `data/predict_fights_alpha.csv` before the card and before outcomes
are known, then run:

```bash
.venv/bin/python testing/score_frozen_striking_core_policy.py \
  --policy test_results/frozen_sigpct_head_challenger_paper_policy/frozen_sigpct_head_challenger_paper_policy.json \
  --fights path/to/fight_card_odds.csv \
  --event-key unique-event-key \
  --fight-card-link https://example.com/card \
  --output-csv test_results/forward_paper_tracking/latest_sigpct_head_challenger_paper_bets.csv \
  --output-json test_results/forward_paper_tracking/latest_sigpct_head_challenger_paper_bets.json
```

The fight-card CSV must include `fighter1`, `fighter2`, `fighter1_odds`, and
`fighter2_odds`; optional `fight_index`, `event_key`, and `fight_card_link`
columns are preserved in the ledger.

## Frozen Rules

- Do not alter feature columns, regularization strength, universe, thresholds,
  side-selection rule, event-cap setting, or stake size after outcomes are
  known.
- Keep this challenger ledger separate from the primary mixed-core paper policy
  and from live staking.
- Archive generated CSV/JSON ledgers before outcomes are known.
- Settle future paper bets with `testing/settle_forward_paper_ledger.py` and
  require future market-null plus event-bootstrap evidence before making a
  live-edge claim.
