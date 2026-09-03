"""Unit tests for publish_site.py: the change detection, odds-file helpers and the
git step, run against a throwaway repository so no mocks are needed."""
import csv
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import publish_site  # noqa: E402

BACKTEST = "frontend/src/data/backtest.json"


def payload(generated, accuracy=0.66):
    return json.dumps({"generated": generated, "summary": {"metrics": {"accuracy": accuracy}}})


# ------------------------------------------------------------- pure helpers

def test_backtest_changed_ignores_generated_timestamp():
    assert not publish_site.backtest_changed(payload("2026-09-01T02:00:00"), payload("2026-09-04T02:00:00"))


def test_backtest_changed_detects_content_change():
    assert publish_site.backtest_changed(payload("2026-09-01T02:00:00"), payload("2026-09-01T02:00:00", 0.67))


def write_odds(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["event_name", "event_date", "fighter1_name", "fighter2_name", "winner_name",
                    "fighter1_odds", "fighter2_odds"])
        w.writerows(rows)


def read_dates(path):
    with open(path, newline="") as fh:
        return [row["event_date"] for row in csv.DictReader(fh)]


def test_latest_odds_date_returns_iso_of_newest_row(tmp_path):
    odds = tmp_path / "odds.csv"
    write_odds(odds, [("e1", "Aug 29 2026", "A", "B", "A", "-150", "+130"),
                      ("e2", "Sep 12 2026", "C", "D", "D", "+200", "-240"),
                      ("e3", "Sep 05 2026", "E", "F", "E", "-110", "-110")])
    assert publish_site.latest_odds_date(str(odds)) == "2026-09-12"


def test_sort_odds_csv_orders_rows_oldest_first_and_keeps_header(tmp_path):
    odds = tmp_path / "odds.csv"
    # scrape_new_odds.py appends newest event first; the backtests need file order = date order
    write_odds(odds, [("e1", "Aug 29 2026", "A", "B", "A", "-150", "+130"),
                      ("e3", "Sep 12 2026", "C", "D", "D", "+200", "-240"),
                      ("e3", "Sep 12 2026", "G", "H", "G", "-300", "+250"),
                      ("e2", "Sep 05 2026", "E", "F", "E", "-110", "-110")])
    publish_site.sort_odds_csv(str(odds))
    assert read_dates(odds) == ["Aug 29 2026", "Sep 05 2026", "Sep 12 2026", "Sep 12 2026"]
    with open(odds, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["fighter1_name"] for r in rows if r["event_date"] == "Sep 12 2026"] == ["C", "G"]  # stable


def test_newest_pred_returns_latest_file_or_none(tmp_path):
    assert publish_site.newest_pred(str(tmp_path)) is None
    for d in ("2026-01-24", "2024-07-13", "2026-07-25"):
        (tmp_path / f"pred_{d}.csv").write_text("Red Fighter,Blue Fighter,Predicted Result,Probability\n")
    assert publish_site.newest_pred(str(tmp_path)) == str(tmp_path / "pred_2026-07-25.csv")


# --------------------------------------------------------------- git steps

def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    os.makedirs(os.path.join(root, "frontend/src/data"))
    with open(os.path.join(root, BACKTEST), "w") as fh:
        fh.write(payload("2026-09-01T02:00:00"))
    with open(os.path.join(root, "other.txt"), "w") as fh:
        fh.write("untouched\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    return root


def rewrite(root, rel, text):
    with open(os.path.join(root, rel), "w") as fh:
        fh.write(text)


def test_publishable_changes_restores_a_timestamp_only_backtest(repo):
    rewrite(repo, BACKTEST, payload("2026-09-04T02:00:00"))
    assert publish_site.publishable_changes(repo, [BACKTEST]) == []
    assert git(repo, "status", "--porcelain") == ""          # restored from HEAD


def test_publishable_changes_reports_real_and_untracked_changes(repo):
    rewrite(repo, BACKTEST, payload("2026-09-04T02:00:00", 0.67))
    rewrite(repo, "frontend/src/data/ledger.json", "[]\n")   # untracked
    assert publish_site.publishable_changes(repo, [BACKTEST, "frontend/src/data/ledger.json", "other.txt"]) == [
        BACKTEST, "frontend/src/data/ledger.json"]


def test_commit_paths_commits_only_the_given_paths(repo):
    rewrite(repo, BACKTEST, payload("2026-09-04T02:00:00", 0.67))
    rewrite(repo, "other.txt", "dirty\n")
    publish_site.commit_and_push(repo, [BACKTEST], "Refresh site data", push=False)
    assert git(repo, "log", "-1", "--format=%s").strip() == "Refresh site data"
    assert git(repo, "status", "--porcelain").strip() == "M other.txt"
