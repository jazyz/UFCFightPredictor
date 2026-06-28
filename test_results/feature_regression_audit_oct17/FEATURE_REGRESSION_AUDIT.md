# Feature Regression Audit Since Oct 17

Date: 2026-06-28

## Scope

This pass looked for feature bugs or unintended behavior introduced after the
Oct 17 baseline that could affect PnL.

Code paths checked:

- historical feature generation: `process_fights_alpha.py`
- live/upcoming feature generation: `predict_fights_alpha.py`
- shared feature cleanup: `utils/feature_sanitization.py`
- live inference consumers: `load_ensemble.py`, `ml_web.py`,
  `predict_single_model.py`
- leak-safe PnL/statistical evaluation: `testing/no_leakage_backtest.py`,
  `testing/statistical_edge_audit.py`

## Implemented Fix: Live Feature Artifact Guard

The checked-in `data/predict_fights_alpha.csv` is stale and contains impossible
live feature values from before the recent live feature fixes. Examples include
impossible DOB/age fields and unscaled cumulative features such as `oppelo`.

Current `predict_fights_alpha.py` generates sane rows for the same matchup, so
the bug is stale/off-scale artifacts being consumed directly by inference
scripts, not the current generator formula.

Added `validate_feature_ranges()` to `utils/feature_sanitization.py` and wired
it into:

- `load_ensemble.py`
- `ml_web.py`
- `predict_single_model.py`

The guard compares live feature rows against the historical training feature
envelope and rejects values that are many times outside that range.

Verification:

```text
PYTHONPYCACHEPREFIX=/tmp/ufc_pycache .venv/bin/python -m compileall \
  utils/feature_sanitization.py load_ensemble.py ml_web.py predict_single_model.py
```

Result: compile passed.

Direct validation:

```text
stale_rejected
stale data/predict_fights_alpha.csv has 307 feature values far outside the training range; regenerate live features before inference
fresh_generated_passed
```

Entry-point validation on the stale checked-in artifact:

- `predict_single_model.py`: rejected 307 out-of-range values
- `load_ensemble.py`: rejected 240 out-of-range values
- `ml_web.py`: rejected 240 out-of-range values

This fix protects live predictions from stale/off-scale artifacts. It does not
change historical no-leakage backtests, so it does not create a new historical
PnL result to claim.

## Diagnostic: Blank-Winner Rows In Fighter Histories

Suspicion: rows with blank `Winner` values, such as overturned/no-contest/draw
rows, are not emitted as supervised training examples but do update fighter
history, ELO, last-fight, and rolling stats. This could be unintended.

Diagnostic setup:

- Removed 148 blank-winner rows from `data/modified_fight_details.csv`
- Regenerated a temporary feature table:
  `/tmp/ufc_detailed_no_blank_winners.csv`
- Ran one-year no-leakage backtest using the temporary features
- Audited against the comparable current-feature baseline

Result:

| Run | Window | Fights | Bets | Log Loss | Profit | Market-null p | Bootstrap profit CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Current baseline | 2025-06-27 to 2026-06-27 | 298 | 240 | 0.660 | $115.97 | 0.275 | $-415.31 to $678.04 |
| No blank-winner stats | 2025-06-27 to 2026-06-27 | 296 | 239 | 0.667 | $39.37 | 0.403 | $-472.56 to $569.62 |

Conclusion: removing blank-winner rows from fighter histories worsened the
one-year leak-safe result and did not improve statistical evidence. No code
change was made for this candidate.

Artifacts:

- `test_results/pnl_no_blank_winner_stats_1y/no_leakage_backtest_summary.json`
- `test_results/pnl_no_blank_winner_stats_audit/edge_audit.md`

## Historical Feature Reproducibility

Regenerated current historical features to `/tmp` using current code and data.
Parsed CSV values matched the checked-in artifacts:

```text
data/detailed_fights.csv rows/cols (4322, 197) (4322, 197) columns_equal True
diff columns 0 []
data/detailed_fighter_stats.csv rows/cols (2392, 64) (2392, 64) columns_equal True
diff columns 0 []
```

This reduces the likelihood that current checked-in historical features are
stale relative to `process_fights_alpha.py`.

## PnL/Statistical Conclusion

No beneficial historical feature bug fix was found in this pass.

The only implemented source change is a live-inference guard against stale or
off-scale live feature artifacts. The PnL diagnostics that were testable with
no-leakage historical backtests either did not improve PnL or lacked
statistical support.
