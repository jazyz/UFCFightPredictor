"""Build or extend a walk-forward prediction cache for the site export.

Replays testing_time_period.process_dates over a window, training the backtest
twin (testing/ml_alpha_testing.py) once per retrain date and saving each
retrain's data/predicted_results.csv as <cache>/pred_<date>.csv. Existing files
are reused, so extending a window only trains the missing dates.

    python testing/build_walk_forward_cache.py --start 2024-01-01 --end 2026-08-30 \
        --cache test_results/.tier2_full_cache
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "testing"))
os.chdir(ROOT)  # process_dates and ml_alpha_testing use repo-relative paths

import testing_time_period as ttp  # noqa: E402
import ml_alpha_testing  # noqa: E402

# fraction, cap, (inert legacy slot), min edge, blend weight: the production config
PRODUCTION_STRATEGY = [0.05, 0.05, 0, 0.05, 0.8]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD, first training cutoff")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD, last fight date")
    ap.add_argument("--cache", required=True, help="directory of pred_<date>.csv files")
    args = ap.parse_args(argv)
    os.makedirs(args.cache, exist_ok=True)
    retrains = []

    def cached_train(date):
        target = os.path.join(args.cache, f"pred_{date}.csv")
        if os.path.exists(target):
            print(f"reusing {target}", flush=True)
        else:
            print(f"training walk-forward model for {date} ...", flush=True)
            ml_alpha_testing.main(date)
            shutil.copy(os.path.join("data", "predicted_results.csv"), target)
        shutil.copy(target, os.path.join("data", "predicted_results.csv"))
        retrains.append(date)

    ttp.train_ml = cached_train
    ttp.process_dates(args.start, args.end, PRODUCTION_STRATEGY)
    print("retrain dates:", ", ".join(retrains))
    print(f"final bankroll ${ttp.bankroll:,.2f} over {ttp.favourites + ttp.underdogs} bets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
