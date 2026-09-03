# UFC Fight Predictor — Full Repo Review

Date: 2026-07-15
Scope: all active code (root `.py` files, `scrapers/`, `testing/`, `frontend/src/`, `app.py`), plus repo hygiene. Legacy folders (`oldModel/`, `oldStatic/`, `oldDynamic/`) were not deep-reviewed.

Findings are ordered by severity. File:line references point at the offending code.

---

## 🔴 Critical — production predictions are wrong or the app breaks

### 1. Training/serving skew: differential features are overwritten with base stats at prediction time
`predict_fights_alpha.py:114-119`

```python
processed_fight[f'Red {feature} differential'] = fighter_stats[f'{feature} differential']   # set correctly...
...
processed_fight[f'Red {feature} differential'] = float(fighter_stats[feature]) / sqrSum(...)  # ...then overwritten with the BASE stat
```

At training time (`process_fights_alpha.py:183-188`) `Red X differential` = accumulated *differential* ÷ sqrSum. At prediction time lines 118-119 divide the accumulated **base** stat instead of the differential, so every `* differential` feature fed to the model equals its base feature. The model was trained on real differentials but predicts on garbage. This silently degrades every live prediction (website + betting).

### 2. Training/serving skew: `oppelo`, `wins`, `avg age` are never divided by `totalfights` at prediction time
`predict_fights_alpha.py:108-122` vs `process_fights_alpha.py:192-194`

Training divides `hardcoded_features_divide` values by `totalfights`. The prediction-side `process_fight()` has no equivalent branch, so raw accumulated sums (e.g. `oppelo` ≈ 20,000 for a 20-fight veteran) are fed where the model expects averages (~1000). These are top features (`Red oppelo`, `Red wins` are in `saved_preprocessing/selected_columns.json`).

Related: `predict_fights_alpha.py:45` lists `"losses"` in `hardcoded_features_divide`, but `process_fights_alpha.py` never tracks a `losses` stat at all (only `wins` is incremented for either corner) — the feature is dead.

### 3. Starting the Flask app runs a full year-long backtest (with model training)
`testing/testing_time_period.py:270` + `app.py:5`

```python
process_dates('2023-01-01', '2024-01-01', strategy=[0.05,0.05,0.005])   # module level!
```

`app.py` does `from testing.testing_time_period import process_dates`, which executes this line at import. Every server start (and every `flask run` reload) kicks off LightGBM training plus a 12-month bet simulation before the app can serve a request. The call should be under `if __name__ == "__main__":`.

### 4. Hyperparameter CV validates on mirrored copies of the training data
`ml_ensemble.py:93-132`, `ml_alpha_date.py:76-114`, `ml_alpha_RL.py:210-247`

`X_train_extended = concat([X_train, X_train_swapped])` appends a red/blue-mirrored duplicate of every training fight, and then `lgb.cv(..., folds=TimeSeriesSplit(...))` is run on that concatenation. Later folds validate on swapped duplicates of fights already seen in training, so validation loss, early stopping, and Optuna's best score are all computed on leaked data. Augment *inside* each fold (or CV on the un-augmented set) instead.

### 5. RL hyperparameter search always returns the default hyperparameters
`ml_alpha_RL.py:132-150`

- `DummyVecEnv` auto-resets the wrapped env when `done=True`. By the time the loop reads `env.envs[0].hyperparams` (line 145), the env has already reset, so `best_hyperparams` is always the initial `{num_leaves: 50, lr: 0.1, min_child_samples: 30, subsample: 0.8}`. The entire RL search is a no-op.
- `current_log_loss = -total_reward` (line 142) is the **sum** of log losses over 20 steps, but it's printed and compared against single-model log loss (`ml_alpha_RL.py:307`) — an apples-to-oranges comparison off by ~20×.

(`tempCodeRunnerFile.py` is a byte-identical copy of this file — see Hygiene.)

### 6. Windows-only backslash paths break the data pipeline on macOS/Linux
- `modify_fights.py:4` — reads `r'data\fight_details_date.csv'`
- `modify_fights.py:55` — writes `'data\modified_fight_details.csv'`
- `scrapers/scrape_all_fights.py:127,162,169` — `r'data\fight_details_date.csv'`
- `scrapers/scrape_fights.py:77,109,115` — `r'data\fight_details.csv'`, `r'data\fight_details_date.csv'`

On this machine (macOS) these are literal filenames containing `\`, so the scraper writes `data\fight_details_date.csv` into the CWD and `modify_fights.py` crashes with FileNotFoundError. Use `os.path.join("data", ...)` like the rest of the codebase.

### 7. Draw handling deletes the wrong row from the dataset
`modify_fights.py:36-46`

```python
if pd.isna(df.loc[i, 'Winner']) or df.loc[i, 'Winner'] == '':
    rows_to_delete.add(i + 1)   # deletes the NEXT fight, keeps the draw
    i += 2
```

When row `i` has no winner (draw/NC), the code deletes row `i+1` — a legitimate different fight — and keeps the draw row. Every draw in the raw data removes one valid fight from training and leaves the draw in. The last row is also never checked. (Downstream, `process_fights_alpha.py` skips draws for labels but still lets them mutate cumulative stats/Elo, which partially masks this.)

### 8. Running `scrapers/scrape_fights.py` truncates the main scraped dataset
`scrapers/scrape_fights.py:109-113,131-132`

Module-level code runs on import/run: `process_fight_urls(urls)` opens `data\fight_details_date.csv` in `'w'` mode (header row `i==0`) and replaces the whole dataset with one hardcoded test fight. On Windows (where the path resolves) this destroys the primary CSV. The write also omits the `Date` column that `scrape_all_fights.py` includes, so even appends would be misaligned.

### 9. Scraper writes misaligned CSV rows and crashes on error pages
`scrapers/scrape_all_fights.py:127-160`

- Headers are derived from the **first** fight's stat keys; every later row is written as `list(dict.values())` with no alignment to those headers. Any fight page with a different/missing stats table shifts values into the wrong columns silently.
- `get_fight_details()` returns `{"Error": ...}` on failure, but `process_fight_urls` passes it straight to `write_to_csv`, which does `fight_details['Fighter 1 Stats']` → `KeyError` crashes the multi-hour scrape.
- No rate limiting/retry on thousands of sequential requests to ufcstats.com.

---

## 🟠 High — backtest/results validity (the numbers in the README/website)

### 10. `row['Draw'] == True` is always False (CSV values are strings)
`scrapers/scrape_fights_with_odds.py:26,31`

`csv.DictReader` yields `"True"`/`"False"` strings, never the boolean `True`. Draws that fall through to `findWinner()` get `winner_name = row['Winner']` (empty for draws) instead of `"draw/no contest"`, and the backtest then scores the bet as a loss instead of a push.

### 11. Misplaced `for/else` writes a spurious failure line
`scrapers/scrape_fights_with_odds.py:152-153`

The final `else:` binds to the `for fight_card_link ...` loop (for/else), not to an `if`. If the loop finishes without hitting the `break` at ufc-296, it writes "Failed to retrieve the events page" with a stale `response.status_code` into the results CSV file.

### 12. Look-ahead bias in the backtest
- `testing/ml_alpha_testing.py:31-44` — correlation-based feature pruning is computed on the **full** dataset (including fights after `split_date`) before splitting. Same pattern in `ml_ensemble.py:36-45` and `ml_alpha_date.py:31-37`.
- `testing/ml_alpha_testing.py:90-95` — the backtest loads `data/best_params.json`, which was tuned (by `ml_alpha_date.py`) on data that includes the backtest period. Hyperparameters from the future leak into "past" retrains.
- Both inflate the simulated bankroll/accuracy numbers quoted in the README and Home page.

### 13. Backtest betting logic ≠ live betting logic
`testing/testing_time_period.py:38-52` and `betting_alpha.py:55-69` share `closerToOdds()` with a fallback `if a_win + b_win != 1:` — an exact float comparison that is almost always True unless a branch already normalized the pair, so the "pick the estimate closer to the odds" logic frequently collapses to plain averaging. Meanwhile `testing/test_from_site.py:199-204` uses the closer-to-odds picks **without** the sum-to-1 fallback. Three different bet-sizing behaviors are being compared as if they were one strategy.

### 14. Results parser cherry-picks trials before averaging
`test_results/parse_results.py:13-18`

`prune_bankrolls()` throws away every trial up to and including the last bankroll above $3000 before computing the "average bankroll" and above/below-1000 counts. Any aggregate stats produced by this script (and quoted in README §Results) are biased.

### 15. LabelEncoder is refit on the test slice and then saved for production
`ml_ensemble.py:219` refits the global `label_encoder` on the last-5% slice, and `ml_ensemble.py:262` then saves that refit encoder to `saved_preprocessing/label_encoder.joblib` for use by `ml_web.py`. If the slice ever contains a single class, the saved mapping breaks and every production prediction label is silently wrong. Use `.transform()` with the already-fit encoder. Same refit-on-test pattern at `ml_alpha_date.py:158` and `ml_alpha_RL.py:318`.

### 16. Swapped-row actual labels are not flipped
`testing/ml_alpha_testing.py:120-129` — `df_with_details_swapped` swaps fighter names but keeps `Result` unchanged, so `actual_labels` is wrong for the entire swapped half. Currently latent (the CSV only writes predicted labels), but any future use of `actual_labels` mis-scores 50% of rows. Similarly `ml_alpha_date.py`/`ml_alpha_RL.py` never negate `oppdiff` columns in their swapped training copies (they don't exclude them like `ml_ensemble.py:35` does), so their augmented rows carry contradictory oppdiff features with flipped labels.

### 17. Three different schemas for `data/predicted_results.csv`
- `ml_ensemble.py:225` writes `[Red, Blue, Predicted Result, Probability, Actual Result]`
- `testing/ml_alpha_testing.py:132` writes `[Red, Blue, Predicted Result, Probability]`
- `testing/ml_ensemble_testing.py:79` writes `[Red, Blue, Probability Win, Probability Lose, Probability]` — **no `Predicted Result` column**

Consumers (`testing_time_period.preload_ml_predictions`, `test_from_site.get_ml`) require `Predicted Result` + `Probability`, so running `ml_ensemble_testing.py` before a backtest crashes with `KeyError`.

### 18. Non-reproducible training data
`process_fights_alpha.py:154` — `random.choice([True, False])` (unseeded) randomly swaps corners while generating `detailed_fights.csv`. Every regeneration produces a different dataset, so accuracy numbers can't be reproduced and git diffs of the CSV are meaningless.

### 19. Bare `except: pass` silently corrupts cumulative stats
`process_fights_alpha.py:234-251` — the per-feature update does differential += … then base += … / getTime(fight) inside one `try`. A `ZeroDivisionError` (fight time 0:00) or `ValueError` (blank cell) after the differential update leaves that fighter's stats **partially** updated, and the error is swallowed. At minimum catch specific exceptions and log; ideally update atomically.

### 20. Missing DOB produces ages like 2023
`process_fights_alpha.py:104-120` — if a fighter isn't in the SQLite DB (or DOB fails to parse), `dob` stays `0`, so `Red age = fight_year - 0 ≈ 2023`. These rows are not filtered and poison the age features. Same at prediction time (`predict_fights_alpha.py:100-101`, age ≈ 2026).

### 21. Integer floor-division in `sqrSum` applied to floats
`process_fights_alpha.py:132-133` (`n*(n+1)*(2*n+1)//6`) is exact for the integer call sites, but line 190 calls it with a float (`defense/totalfights`) where `//6` silently floors the result. `predict_fights_alpha.py:19-21` has the same. Train and serve happen to match, but the transform is almost certainly meant to be `/6`.

---

## 🟡 Medium — web app correctness/robustness

### 22. `/predict` can crash or serve stale predictions
`app.py:28-44`, `predict_fights_alpha.py:60-83`, `ml_web.py:34-42`
- If either fighter has ≤1 fights or isn't found, `extract_fighter_stats` just prints and returns; the output CSV may end up with 0 or 1 rows. `ml_web.main()` then either crashes on an empty frame (500 with debug traceback) or writes a 1-row `predicted_data.json`, and the frontend's `predictedData[1]["Probability Lose"]` (`FightPredictor.js:146,160`) throws. There's no error propagation to the user (`response = {"message": "Fighter stats processed"}` regardless).

### 23. Global file/state races
- All predictions flow through shared files (`data/predict_fights_alpha.csv`, `data/predicted_data.json`); two concurrent users overwrite each other's requests and can receive each other's results.
- `testing/testing_time_period.py:85-89` — `ev`, `underdogs`, `favourites`, `underdogsHit`, `favouritesHit` are module globals never reset in `process_dates()`; repeated `/test` calls accumulate stats across runs. `testing/test_from_site.py:25-32` has the same issue with `max_bankroll`/`min_bankroll` etc.

### 24. `app.run(debug=True)` and wide-open CORS
`app.py:15-16,146` — if this is the config behind betufc.ca, the Werkzeug debugger is remote-code-execution-as-a-service, and `CORS(app)` with no origin restriction lets any site drive the API (including the expensive `/test`). Use a production WSGI server, `debug=False`, and an explicit origin list.

### 25. `/test` is an unbounded synchronous request
`app.py:113-126` triggers repeated model retraining inside one HTTP request (frontend allows 10 minutes, `Testing.js:79`). No queueing, no lock — two clicks run two trainings concurrently against the same output files.

### 26. Hardcoded retraining cutoff
`testing/testing_time_period.py:211` — `final_training_date = '2023-12-01'`: backtests covering 2024+ silently stop retraining, quietly changing the methodology for the "2024" option exposed in the UI.

### 27. `graph_predictions.py` reads a file that doesn't exist
`testing/graph_predictions.py:8` opens `'predictions.txt'` relative to CWD; no such file exists at the repo root (the real ones are `frontend/src/constants/predictions.txt` / `oldModel/predictions.txt`). The script crashes, and it's the only thing that regenerates `data/predictions_bankroll_plot.png` served by `/get_predictions_plot`.

### 28. Potential `ZeroDivisionError` in results summary
`testing/test_from_site.py:284-289` — divides by `total_bets`, `total_underdogs`, `total_favourites` without zero checks; a short test window with no qualifying bets crashes at the end after doing all the work.

### 29. IndexError risks in card parsing
`betting_alpha.py:115-121` and `scrapers/scrape_fights_with_odds.py:120-134` — `fighter_names[i+1]` and `odds_wrappers[i//2]` assume an even fighter count and one odds-wrapper per fight; a page with a cancelled bout or missing odds block crashes the run.

### 30. Dead odds checks / latent NameError
`betting_alpha.py:149-157`, `test_from_site.py:196-208` — `if (fighter1_odds != "-")` after `int(fighter1_odds)` is always True (dead). If those guards ever became effective, `kc_a`/`kc_b` would be referenced before assignment at the following `test.write` lines.

### 31. `scrape_fighters.py` robustness
- `scrapers/scrape_fighters.py:63-66` — `record_match.group(1)` raises `AttributeError` if neither record regex matches.
- Re-running `main()` inserts every fighter again (no uniqueness constraint or upsert) — duplicated fighters skew `query_fighter_by_name(...).first()`.
- `sqlite:///detailedfighters.db` is instance-relative: running the script from `scrapers/` creates a fresh empty DB there, and `process_fights_alpha.py` then silently resolves every DOB to 0 (see #20).

### 32. Duplicated model-inference code
`load_ensemble.py` is a near-copy of `ml_web.main()` (writing `betting_predictions.csv` instead of `fight_predictions.csv` + JSON). Two copies of preprocessing logic drift independently — the differential/divide bugs (#1/#2) already show how costly pipeline drift is. Both also trigger pandas `SettingWithCopyWarning` at `fighter_data['Probability Win'] = ...` (`ml_web.py:50`, `load_ensemble.py:53`) — use `.copy()`.

### 33. Ensemble label-order assumption
`ml_web.py:50-51`, `load_ensemble.py:53-54`, `ml_ensemble_testing.py:75-76` — `[:, 1]` is assumed to be "win". True today because `LabelEncoder` sorts `['loss','win']` alphabetically, but nothing enforces it; use `label_encoder.classes_` to index.

---

## 🔵 Frontend

### 34. Strategy values disagree with their documentation and `max_fraction` is never set
`frontend/src/components/Testing.js:17-48`
- Comments say conservative/normal/risky = 0.05/0.1/0.2; code uses `[0.025, 0.05, 0.1]` (line 31).
- `updatedStrategy[1]` (max bet fraction) is never updated — "Risky" raises the Kelly fraction to 0.1 but bets stay capped at 5% of bankroll, so Risky ≈ Normal.
- Flat-bet sizes computed as `0.005 * idx + 0.005` (0.5%/1%/1.5%) vs the documented 1%/1.5%/2%.

### 35. Missing-DOB ages render wrong
`frontend/src/components/FightPredictor.js:15-24` — the backend sends `dob` as a **year** string; `"0"` (missing DOB, see #20) becomes `new Date("0")` → year 2000 → a plausible-looking wrong age instead of "unknown".

### 36. Fragile prediction rendering
`FightPredictor.js:138-165` — `fighter1_stats.Fighter`, `predictedData[0]`, `predictedData[1]` are accessed without guarding for the partial-failure cases in #22; `fighter*_stats` can be `{}` (truthy) when a fighter isn't in the CSV.

### 37. Dead components with a broken import
`FightersPage.js` / `FightersDropdown.js` are not routed anywhere; `FightersDropdown.js:3` imports `./css/FightersDropdown.css`, which doesn't exist — wiring these up as-is breaks the build. `FightersPage.js:11` also hardcodes `http://127.0.0.1:5000` instead of `baseURL`.

### 38. Controlled inputs initialized to `null`
`Testing.js:6-7` — `useState(null)` for `value={startYear}` produces React controlled/uncontrolled warnings; use `""`.

### 39. Stale static content
`Bets.js` renders a bundled `constants/predictions.txt` (last predictions: UFC 308, Oct 2024) and Home's chart is a static PNG. Content, not code — but the site presents them as current.

---

## ⚪ Hygiene / repo health

40. **No root `.gitignore`.** Committed to git: `__pycache__/*.pyc` (root, `oldModel/`, `testing/`), `.DS_Store`, `.vscode/`, `instance/*.db`, `oldModel/instance/*.db`, `data/backup/`. Repo is 346 MB.
41. **`tempCodeRunnerFile.py`** (VS Code Code Runner artifact) is a committed byte-identical copy of `ml_alpha_RL.py` — delete it.
42. **`requirements.txt`**: `flask-sqlalchemy==3.0.5` is listed twice (lines 4 and 10; pip can reject the file with "Double requirement given"), and packages actually imported are missing: `numpy`, `joblib`, `shap` (`ml_ensemble.py:164`), `gym` and `stable-baselines3` (`ml_alpha_RL.py:15-18`). Note: modern `stable-baselines3` (≥2.0) requires `gymnasium`, not `gym`, and the old 4-tuple `step()` API used in `ml_alpha_RL.py` won't run against it — pin versions.
43. **README drift**: references `ml_alpha.py` (doesn't exist — closest are `ml_alpha_date.py`/`ml_ensemble.py`); says `modify_fights.py` reads `fight_details.csv` (code reads `fight_details_date.csv`); says `predicted_data.json` — the JSON is written by `ml_web.py`, not "ml_alpha". `betting_alpha.py:18` uses `bankroll = 100` vs README's $1000.
44. **CWD-relative paths everywhere** (`data/...`, `saved_models`, `sqlite:///detailedfighters.db`): every entry point only works when run from the repo root. Consider anchoring to `os.path.dirname(__file__)`.
45. **Optuna runs with `n_trials=1`** (`ml_ensemble.py:153`, `ml_alpha_date.py:118`, `ml_alpha_RL.py:251`) — each "tuned" model is a single random sample from the search space; the README's hyperparameter-tuning claims overstate what the code does.
46. **`num_class: 2` with `objective: multiclass`** instead of `binary` (all trainers) — works, but doubles output computation and diverges from LightGBM defaults for no benefit.
47. **SHAP API pinning** — `ml_ensemble.py:164-191` indexes `shap_values[class_index]`, which assumes the old list-based SHAP return for binary models; newer `shap` versions return a single array and this code breaks.
48. **Duplicate Elo/feature code paths** — `process_fights_alpha.py` and `predict_fights_alpha.py` reimplement the same transforms by hand (already inconsistent, see #1/#2). Extracting one shared function would eliminate the whole bug class.
49. **`for fight in fights: ... pass`** dead loop at `process_fights_alpha.py:77-82` and unused imports across most files (`subprocess`, `sys`, `time` in `app.py`; `GridSearchCV`, `cross_val_score`, `train_test_split` in trainers).

---

## Suggested priorities

1. Fix the two training/serving skews (#1, #2) — they affect every live prediction and bet.
2. Guard the module-level backtest (#3) so the app can start cleanly.
3. Fix data-pipeline destroyers (#6, #7, #8) before the next scrape/retrain.
4. Rerun backtests after removing leakage (#4, #12, #13, #14) to get honest performance numbers before trusting the betting output.
5. Add a root `.gitignore` and delete committed artifacts (#40-42).
