#!/usr/bin/env python3
"""Refresh the public site's data after a retrain and push it so Cloudflare rebuilds.

Run by run_scheduled.sh right after auto_retrain.py succeeds. Re-exports
frontend/src/data from the committed walk-forward cache, commits only the site
data if its content changed (the export's timestamp alone never triggers a
commit) and pushes main. Any step that fails exits non-zero.

    python publish_site.py            export, commit, push
    python publish_site.py --roll     also scrape new odds, extend the walk-forward
                                      cache to the latest priced fight and commit it
    python publish_site.py --no-push  commit locally only (for checking a run)
"""
import argparse
import csv
import datetime
import glob
import json
import logging
import os
import subprocess
import sys
from typing import List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs")

BRANCH = "main"
SITE_DATA = "frontend/src/data"
BACKTEST = f"{SITE_DATA}/backtest.json"
LEDGER = f"{SITE_DATA}/ledger.json"
CACHE = "test_results/.tier2_full_cache"
ODDS = "data/fight_results_with_odds.csv"
WINDOW_START = "2024-01-01"      # first walk-forward retrain; the cache is built from here

log = logging.getLogger("publish_site")


# ---------------------------------------------------------------- infrastructure

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"publish_site_{datetime.datetime.now():%Y%m%d_%H%M%S}.log")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    log.setLevel(logging.INFO)
    for handler in (logging.FileHandler(path), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return path


def banner(title):
    log.info("=" * 70)
    log.info(title)
    log.info("=" * 70)


def run_script(args: List[str]) -> str:
    """Run a repo script in a subprocess; raise if it fails."""
    env = dict(os.environ, MPLBACKEND="Agg", PYTHONPATH=ROOT)
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        for line in (proc.stderr or proc.stdout or "").strip().splitlines()[-15:]:
            log.error(f"  {line}")
        raise RuntimeError(f"{args[0]} exited {proc.returncode}")
    return proc.stdout


def git(root: str, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


# ---------------------------------------------------------------- odds & cache

def latest_odds_date(odds_csv: str) -> str:
    """ISO date of the newest priced fight; the window can end no later than this."""
    with open(odds_csv, newline="", encoding="utf-8") as fh:
        dates = [datetime.datetime.strptime(row["event_date"], "%b %d %Y") for row in csv.DictReader(fh)]
    return max(dates).strftime("%Y-%m-%d")


def sort_odds_csv(path: str) -> None:
    """Stable sort oldest-first. scrape_new_odds.py appends newest event first and the
    backtests walk the file in order, so every append must be followed by a re-sort."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    rows.sort(key=lambda r: datetime.datetime.strptime(r["event_date"], "%b %d %Y"))
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def newest_pred(cache_dir: str) -> Optional[str]:
    """The most recent pred_<date>.csv. It only covers fights that existed when it was
    built, so extending the window means deleting it and letting the builder redo it."""
    files = sorted(glob.glob(os.path.join(cache_dir, "pred_*.csv")))
    return files[-1] if files else None


# ----------------------------------------------------------------------- git

def backtest_changed(old_json: str, new_json: str) -> bool:
    """Content comparison of two exports, ignoring the run timestamp."""
    old, new = json.loads(old_json), json.loads(new_json)
    old.pop("generated", None)
    new.pop("generated", None)
    return old != new


def publishable_changes(root: str, paths: List[str]) -> List[str]:
    """The given repo-relative paths whose content differs from HEAD. A backtest.json
    that differs only in its timestamp is restored from HEAD and not reported."""
    changed = []
    for path in paths:
        if not git(root, "status", "--porcelain", "--", path).strip():
            continue
        if os.path.basename(path) == "backtest.json":
            try:
                head = git(root, "show", f"HEAD:{path}")
            except subprocess.CalledProcessError:
                head = None
            if head is not None:
                with open(os.path.join(root, path)) as fh:
                    if not backtest_changed(head, fh.read()):
                        git(root, "checkout", "--", path)
                        continue
        changed.append(path)
    return changed


def commit_and_push(root: str, paths: List[str], message: str, push: bool) -> None:
    """Commit only these paths (other dirty files stay untouched), then push main."""
    git(root, "add", "--", *paths)
    git(root, "commit", "-q", "-m", message, "--", *paths)
    if push:
        git(root, "push", "-q", "origin", BRANCH)


# ---------------------------------------------------------------------- main

def current_window_end() -> str:
    with open(os.path.join(ROOT, BACKTEST)) as fh:
        return json.load(fh)["default_window"]["end"]


def step_roll() -> Optional[str]:
    """Scrape new odds and extend the cache. Returns the new window end, or None if no
    newer priced fight appeared (a rebuild would only reshuffle numbers without data)."""
    banner("STEP 1: ROLLING THE WINDOW")
    run_script(["scrapers/scrape_new_odds.py"])
    sort_odds_csv(os.path.join(ROOT, ODDS))
    end, current = latest_odds_date(os.path.join(ROOT, ODDS)), current_window_end()
    if end <= current:
        log.info(f"↷ Newest priced fight is {end}; window already ends {current}. Nothing to roll.")
        return None
    stale = newest_pred(os.path.join(ROOT, CACHE))
    if stale:
        os.remove(stale)
        log.info(f"Removed {os.path.relpath(stale, ROOT)} so the builder re-predicts through {end}")
    out = run_script(["testing/build_walk_forward_cache.py", "--start", WINDOW_START, "--end", end,
                      "--cache", CACHE])
    for line in out.strip().splitlines()[-2:]:
        log.info(f"  {line}")
    log.info(f"✓ Cache extended to {end}")
    return end


def step_export(end: Optional[str]) -> None:
    banner("STEP 2: EXPORTING SITE DATA")
    args = ["testing/export_site_data.py"]
    if end:
        args += ["--cache", CACHE, "--start", WINDOW_START, "--end", end]
    for line in run_script(args).strip().splitlines():
        log.info(f"  {line}")
    log.info("✓ Export written")


def step_publish(paths: List[str], message: str, push: bool) -> bool:
    banner("STEP 3: PUBLISHING")
    changed = publishable_changes(ROOT, paths)
    if not changed:
        log.info("↷ Site data unchanged; nothing to publish")
        return False
    commit_and_push(ROOT, changed, message, push)
    log.info(f"✓ Committed {', '.join(changed)}" + ("" if push else " (not pushed)"))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roll", action="store_true", help="scrape odds and extend the walk-forward window")
    ap.add_argument("--no-push", action="store_true", help="commit locally, do not push")
    args = ap.parse_args()

    log_path = setup_logging()
    log.info(f"Started: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    try:
        branch = git(ROOT, "rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch != BRANCH:
            raise RuntimeError(f"the site publishes from {BRANCH}; {branch!r} is checked out")

        end = step_roll() if args.roll else None
        step_export(end)
        paths = [BACKTEST, LEDGER] + ([CACHE, ODDS] if end else [])
        message = f"Roll site window to {end}" if end else "Refresh site data"
        step_publish(paths, message, push=not args.no_push)
        log.info(f"Log file: {os.path.relpath(log_path, ROOT)}")
        return 0
    except Exception as exc:
        log.error(f"✗ Publish FAILED: {type(exc).__name__}: {exc}")
        log.error(f"Log file: {os.path.relpath(log_path, ROOT)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
