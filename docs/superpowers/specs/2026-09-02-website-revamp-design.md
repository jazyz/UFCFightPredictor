# Website revamp: public results site with a membership funnel

Date: 2026-09-02
Status: approved design, awaiting implementation plan

## Goal

Turn ufcalpha.com from an internal tool into a public site that sells the model's
track record and sends visitors to a paid membership (Patreon or Discord) for the
upcoming card's picks. The public site shows backtest results, a graded bet log,
and methodology. It does not serve predictions.

## Decisions already made

- Static-first. Cloudflare Pages serves the React app; every public page reads
  JSON bundled at build time. No public page calls the Flask API.
- The free head-to-head predictor and the live backtest page are removed.
- All published numbers are regenerated from the deployed pipeline (tier-0
  last-year walk-forward cache) under current `betting_math` semantics.
- The bet record is the walk-forward backtest ledger now, plus a live ledger that
  `predict_event.py` writes and the retrain pipeline grades.
- Brand: UFC Alpha. Membership link lives in one constant, `MEMBERSHIP_URL`, in
  `frontend/src/constants.js`, initially a placeholder.
- Python payload types are stdlib dataclasses. Pydantic is not installed and the
  runtime is Python 3.9.6.

## Out of scope

- Any change to `app.py`, model training, feature engineering, or scraping.
- Automatic `git push` from `auto_retrain.py`.
- Deleting the unrouted `FightersPage.js` and `FightersDropdown.js`, or pruning
  now-unused npm dependencies (`react-slick`, `slick-carousel`, `react-window`,
  `react-markdown`, `lodash.debounce`). Both are noted for follow-up.
- Payment handling. The paywall is external.

## Part A: data export

### `testing/export_site_data.py`

Replays the odds file over a walk-forward prediction cache and writes the site's
data file. Runs from the repo root:

```
python testing/export_site_data.py \
    --cache test_results/.lastyear_tier0_cache \
    --start 2025-08-30 --end 2026-08-30 \
    --out frontend/src/data/backtest.json
```

Defaults are the values above.

Algorithm:

1. List `pred_YYYY-MM-DD.csv` in the cache directory. For each fight in
   `data/fight_results_with_odds.csv` inside the window, use the cache whose date
   is the latest one on or before the fight date. This reproduces the retrain
   boundaries `testing_time_period.find_fights` produced when it built the cache.
2. Model probability for fighter 1 is the two-orientation average, exactly as
   `testing_time_period.process_fight` computes `model_a`. Fights missing either
   orientation are skipped, as are draws and no contests for accuracy and
   betting (they still count toward the coverage denominator).
3. Prediction metrics over every scored fight with a decided result: accuracy,
   AUC, log loss, Brier, sample size. Calibration bands on the pick's stated
   probability: 50-55, 55-60, 60-65, 65-70, 70+. Monthly accuracy by event
   month.
4. Market comparison over scored fights with usable odds: the same four metrics
   for the de-vigged market, the model, and the 0.8 blend. Agreement counts:
   fights where model and market pick the same side and that subset's hit rate;
   disagreement count and the model's hit rate on it.
5. Betting replay with `betting_math.decide_bet` at the production config
   (`blend_w=0.8`, `min_edge=0.05`, `fraction=0.05`, `cap=0.05`,
   `dog_multiplier=1.0`) from a $1,000 bankroll, compounding in file order.
   Records every bet and the bankroll after each scored fight with odds. Also
   computes the flat-stake per-bet return of "always bet the market favorite"
   and "always bet the model's pick" over the same fights, $10 per bet.
6. Summary: final bankroll, return %, bet count, hit rate, favorites won/total,
   underdogs won/total, max drawdown %, low point.

Output shape (`BacktestPayload`, serialized once with `dataclasses.asdict`):

```
{
  "generated": "2026-09-02T14:05:00",
  "window": {"start": "2025-08-30", "end": "2026-08-30"},
  "coverage": {"fights_in_window": 547, "scored": 282, "with_odds": 281},
  "metrics": {"accuracy": 0.67, "auc": 0.704, "log_loss": 0.638, "brier": 0.223, "n": 282},
  "bands": [{"label": "70%+", "lo": 0.70, "hi": 1.0, "n": 22, "stated": 0.74, "hit": 0.818}, ...],
  "monthly": [{"month": "2025-09", "n": 33, "hit": 0.667}, ...],
  "market": {
    "rows": [{"name": "De-vigged market", "accuracy": ..., "auc": ..., "log_loss": ..., "brier": ...}, ...],
    "agree": {"n": 212, "hit": 0.741},
    "disagree": {"n": 69, "model_hit": 0.464}
  },
  "flat": {"market_favorite_per_bet": 0.008, "model_pick_per_bet": 0.081, "stake": 10},
  "betting": {"final": 1132.93, "return_pct": 13.3, "bets": 199, "hit": 0.618,
              "favorites": {"won": 102, "total": 152}, "underdogs": {"won": 21, "total": 47},
              "max_drawdown_pct": 7.5, "low": 991.50},
  "bankroll": [{"date": "2025-09-06", "event": "...", "bankroll": 1003.2}, ...],
  "bets": [BetRecord, ...]
}
```

`BetRecord`:

```
{"date": "2025-09-06", "event": "ufc-fight-night-september-06-2025",
 "fighter": "A", "opponent": "B", "odds": -150,
 "model_prob": 0.66, "market_prob": 0.58, "edge": 0.08,
 "stake": 12.40, "result": "win" | "loss" | "push", "pnl": 8.27,
 "bankroll_after": 1008.27, "source": "backtest"}
```

The numbers above are illustrative placeholders from the previous report; the
script fills real values.

### Dataclasses

Defined in `testing/export_site_data.py` next to the code that produces them:
`Window`, `Coverage`, `Metrics`, `Band`, `MonthRow`, `MarketRow`, `Agreement`,
`MarketSection`, `FlatSection`, `SideRecord`, `BettingSummary`,
`BankrollPoint`, `BetRecord`, `BacktestPayload`. Field names match the JSON
keys above. Odds are `int`; probabilities and money are `float`; dates are ISO
strings.

### Golden test: `tests/test_export_site_data.py`

Runs `testing_time_period.process_dates(start, end, [0.05, 0.05, 0, 0.05, 0.8])`
with `train_ml` replaced by a function that copies the matching cache file into
`data/predicted_results.csv`, then runs the export on the same cache and asserts:

- final bankroll equal to the cent,
- bet count equal,
- favorites and underdogs totals equal.

Marked so it can be skipped when the cache directory is absent, since the cache
is gitignored.

## Part B: live ledger

### `bet_ledger.py` (repo root, next to `betting_math.py`)

`LEDGER_PATH = data/bet_ledger.json`. One JSON list of `LedgerEntry`:

```
{"event": "UFC Fight Night: X vs Y", "event_date": "2026-09-06",
 "generated": "2026-09-04T02:10:00",
 "fighter": "A", "opponent": "B", "odds": -150,
 "model_prob": 0.66, "market_prob": 0.58, "edge": 0.08,
 "kelly": 0.12, "stake_pct": 0.6,
 "result": "pending" | "win" | "loss" | "push",
 "pnl_per_unit": null | 0.667 | -1.0 | 0.0,
 "graded": null | "2026-09-08T02:05:00"}
```

`stake_pct` is percent of bankroll, matching what `predict_event.recommend`
already emits. `pnl_per_unit` is profit per $1 staked at the recorded odds.

Functions:

- `record(event: str, event_date: str, generated: str, bets: list[dict]) -> int`
  Appends one pending entry per pick. Skips a pick whose `(event, fighter)` is
  already present. Returns the number added. Writes atomically (temp file then
  rename).
- `grade(results_csv=data/fight_details_date.csv) -> int`
  For every pending entry, find a row whose `Red Fighter`/`Blue Fighter` pair is
  `{fighter, opponent}` and whose `Date` is within 3 days of `event_date`. Set
  `result` from `Winner`, `Draw`, and compute `pnl_per_unit` with
  `betting_math`'s payout arithmetic. Entries with no matching row stay pending.
  Returns the number graded.

Dataclass `LedgerEntry` defined in `bet_ledger.py`.

### Hooks

- `predict_event.py`: `write_outputs` gains an `event_date` argument and, when
  `bets` is non-empty, calls `bet_ledger.record(event, event_date, generated, bets)`.
  `main` already has `when` for the default next event. For `--event <url>`,
  `main` looks the URL up in `upcoming_events(session)` to get its date and
  falls back to today's date when the URL is not listed there.
- `auto_retrain.py`: a new `step_grade_ledger()` runs right after `step_process()`
  and logs how many entries it graded. It never fails the run: a grading error is
  logged and swallowed, because a broken ledger must not block a retrain.

### Tests: `tests/test_bet_ledger.py`

Using a temp directory for `LEDGER_PATH`:

- `record` adds N entries; calling it again with the same picks adds 0.
- `grade` settles a win, a loss, and a draw from a fixture CSV, computes
  `pnl_per_unit` correctly for a negative and a positive price, and leaves an
  unmatched entry pending.

## Part C: frontend

### Stack

CRA 5, React 18, react-router 6, Tailwind 3. One new dependency: `recharts`.
Google Fonts link in `public/index.html` for Barlow Condensed (600, 700) and
Barlow (400, 500, 600) with a system-ui fallback stack.

### Files

```
frontend/src/
  App.js                      routes: / results bets methodology join
  constants.js                baseURL (kept), MEMBERSHIP_URL, SITE_NAME
  data/backtest.json          written by the export
  data/ledger.json            copied from data/bet_ledger.json by the export
  components/
    Navbar.js                 logo, links, "Get the picks" button
    Footer.js                 disclaimer, responsible-gambling link, GitHub link
    Home.js                   landing page
    Results.js                full report
    Bets.js                   bet log (backtest + live)
    Methodology.js            how it works
    Join.js                   membership page
    StatTile.js               label / value / sub
    charts/CalibrationChart.js
    charts/MonthlyAccuracyChart.js
    charts/BankrollChart.js
    format.js                 pct, money, signed helpers
public/index.html            title, description, Open Graph tags, fonts
```

Deleted: `FightPredictor.js`, `Testing.js`, `About.js`, `constants/about.md`,
`constants/predictions.txt`, `constants/README.md`, `assets/2021_to_2024.png`,
`App.css` (unused CRA boilerplate). `nameOptions` fetch in `App.js` goes away
with the predictor.

### Design system

Tailwind theme extension in `tailwind.config.js`:

- colors: `ink` #f4f3ef, `ink-2` #b8b6ae, `muted` #7c7a72, `ground` #0b0b0c,
  `surface` #151517, `hairline` rgba(255,255,255,.10), `accent` #e8362b,
  `up` #3ccb7f, `down` #ef6b62.
- fonts: `display` Barlow Condensed, `body` Barlow.

Single dark theme, painted explicitly. Max content width 1040px. Charts use
recharts with the same tokens: `up`/`down` for P&L, `accent` for the model
series, `ink-2` for the market series, hairline grid.

### Page content

**Home (`/`)**

1. Hero. Eyebrow "Out-of-sample, walk-forward, closing odds". Headline: "A UFC
   model that knows when it's right." Dek pulls `metrics.n`, `metrics.accuracy`,
   and the 70%+ band hit rate. Two buttons: "Get this week's picks" to
   `MEMBERSHIP_URL`, "See the results" to `/results`.
2. Four stat tiles: accuracy (n), 70%+ band hit rate (n), model-pick flat return
   per bet vs market-favorite flat return, Kelly return with bets and drawdown.
3. "How it works" in three steps: data, model, bets. Two sentences each.
4. Proof section: `CalibrationChart` with a two-sentence explanation of why
   calibration is what makes Kelly work.
5. Market section: the agree/disagree numbers in one short paragraph plus a
   three-row table.
6. Membership CTA band: what members get, one button.
7. Honest caveats, three bullets: sample size, coverage limits, paper bankroll.

**Results (`/results`)**

Sections in order: headline tiles; method (walk-forward description, retrain
dates from the cache, coverage numbers); calibration chart with band table;
monthly accuracy chart; vs-market table and agreement paragraph; betting
summary tiles, bankroll chart, flat-stake comparison; analysis bullets (edge is
price selection, disagreement is a warning sign, calibration is the asset,
error bars, coverage ceiling). Every number interpolated from `backtest.json`.

**Bets (`/bets`)**

Segmented control: Backtest / Live, defaulting to Backtest. Summary tiles
follow the selected segment. Backtest tiles: bets, hit rate, final paper
bankroll, return %, max drawdown. Live tiles: picks posted, graded, hit rate,
net % of bankroll (sum of `pnl_per_unit × stake_pct` over graded entries).
Table columns:
date, event, pick, opponent, odds, model %, market %, edge, stake, result,
P&L. Live rows show `stake_pct` as the stake and `pnl_per_unit × stake_pct` as
P&L. Pending live rows show "pending". Bankroll chart above the table for the
backtest segment. Empty-state copy when the live ledger has no graded entries
yet.

**Methodology (`/methodology`)**

Rewrite of `about.md` for the current pipeline: ufcstats scraping, cleaning,
180+ engineered features with recency weighting and ELO, five LightGBM members
with Optuna-tuned hyperparameters averaged at inference, Red/Blue mirroring,
correlation prune, walk-forward evaluation with no lookahead, twice-weekly
retrain, and what the model cannot cover (women's bouts, debutants, fighters
with fewer than two UFC fights). Link to the GitHub repo.

**Join (`/join`)**

What members get: every pick for the upcoming card with model probability,
market probability, edge, and Kelly stake; posted before the card; graded
publicly on `/bets` afterwards. One button to `MEMBERSHIP_URL`. Age and
responsible-gambling line repeated.

**Footer**

"UFC Alpha publishes model output for informational purposes. Nothing here is
betting advice. Past performance does not guarantee future results. You must be
of legal gambling age in your jurisdiction." Link to a responsible-gambling
resource and to GitHub.

### Claims policy

- Lead with accuracy, calibration bands, and market-beat hit rate.
- ROI never appears without bet count and max drawdown beside it.
- Every bankroll figure is labeled as a $1,000 paper bankroll at closing odds.
- No forward-looking return claims anywhere.

### Frontend tests

- `CI=true npm run build` passes with zero warnings treated as errors.
- One render test per page using a small fixture JSON that mirrors the payload
  shape, asserting the headline number and the CTA link render.

## Part D: refresh workflow

Documented in `CLAUDE.md` under Key Commands:

```
python testing/export_site_data.py     # rebuild frontend/src/data/*.json
git add frontend/src/data && git commit -m "Refresh site data" && git push
```

Cloudflare Pages rebuilds on push. `auto_retrain.py` grades the ledger but does
not run the export or push.

## Verification checklist

- Golden test passes against the tier-0 cache.
- Ledger tests pass.
- `pytest tests/` still passes (`test_no_data_leakage.py` untouched).
- `CI=true npm run build` passes.
- Each page renders against the real `backtest.json` in the dev server with no
  console errors.
- Every number quoted in copy traces to a field in `backtest.json`.
