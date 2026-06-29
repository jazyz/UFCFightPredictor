# Frozen Striking-Core Paper Policy

As-of date: `2026-06-29`
Source backtest: `test_results/striking_core_predeclared_backtest/striking_core_predeclared_backtest.json`
Source report: `test_results/striking_core_predeclared_backtest/striking_core_predeclared_backtest.md`

This is a paper-tracking contract only. It is not a live staking
recommendation. The feature group came from earlier exploration, so future
pre-outcome ledgers must be tracked unchanged before making an edge claim.

## Probability Model

Primary candidate:

```text
mixed_sig_head_core =
market_logit
+ Sig. str.% differential oppdiff
+ Sig. str. differential oppdiff
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
2. Score both sides with the frozen striking-core model.
3. Select the side with the larger edge: `policy probability - market probability`.
4. Paper bet only when the selected edge is at least `2.00%`.
5. Use a flat `1.00u` paper stake.

| Rule | Value |
| --- | ---: |
| model variant | `mixed_sig_head_core` |
| logistic C | 0.1 |
| minimum edge | 2.00% |
| minimum probability | 0.00% |
| event cap | none |
| stake | 1.00u flat paper stake |

## Historical Evidence

The predeclared backtest used men-only aligned odds/features, seven rolling
date folds, and `300` market-null refits.

| Metric | Value |
| --- | ---: |
| aligned rows | 1,223 |
| evaluated fights | 961 |
| market delta log loss | +0.0068 |
| Brier delta | +0.0025 |
| accuracy | 68.99% |
| positive folds | 6 / 7 |
| event-bootstrap P(delta <= 0) | 0.022 |
| market-null p-value | 0.003 |
| candidate ECE | 2.78% |

Descriptive uncapped `2%` positive-edge flat ledger:

| Metric | Value |
| --- | ---: |
| paper bets | 714 |
| flat profit | +33.38u |
| ROI | 4.68% |
| positive folds | 6 / 7 |
| mean edge | 5.00% |
| market-null p-value | 0.002 |
| event-bootstrap P(profit <= 0) | 0.055 |

## Generate A Forward Ledger

Regenerate `data/predict_fights_alpha.csv` before the card and before outcomes
are known, then run:

```bash
.venv/bin/python testing/score_frozen_striking_core_policy.py \
  --fights path/to/fight_card_odds.csv \
  --event-key unique-event-key \
  --fight-card-link https://example.com/card \
  --output-csv test_results/forward_paper_tracking/latest_striking_core_paper_bets.csv \
  --output-json test_results/forward_paper_tracking/latest_striking_core_paper_bets.json
```

The fight-card CSV must include `fighter1`, `fighter2`, `fighter1_odds`, and
`fighter2_odds`; optional `fight_index`, `event_key`, and `fight_card_link`
columns are preserved in the ledger.

## Frozen Rules

- Do not alter feature columns, regularization strength, universe, thresholds,
  side-selection rule, event-cap setting, or stake size after outcomes are
  known.
- Keep this ledger separate from the capped residual policy and from live
  staking.
- Archive generated CSV/JSON ledgers before outcomes are known.
- Settle future paper bets with `testing/settle_forward_paper_ledger.py` and
  require market-null plus event-bootstrap evidence before making a live-edge
  claim.
