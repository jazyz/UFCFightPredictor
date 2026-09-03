"""Public bet ledger: record live picks, grade them once results land.

predict_event.py appends the picks it recommends; auto_retrain.py grades the
pending ones after each scrape. data/bet_ledger.json is a JSON list of
LedgerEntry dicts, and testing/export_site_data.py copies it into the site.
"""
import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER_PATH = os.path.join(ROOT, "data", "bet_ledger.json")
RESULTS_CSV = os.path.join(ROOT, "data", "fight_details_date.csv")
MATCH_WINDOW = timedelta(days=3)   # scraped Date may differ from the card date by a day or two


@dataclass
class LedgerEntry:
    event: str
    event_date: str            # YYYY-MM-DD
    generated: str             # ISO timestamp of the prediction run
    fighter: str
    opponent: str
    odds: int                  # American price at recommendation time
    model_prob: float          # blended betting probability
    market_prob: float         # de-vigged market probability
    edge: float
    kelly: float
    stake_pct: float           # percent of bankroll
    result: str = "pending"    # pending | win | loss | push
    pnl_per_unit: Optional[float] = None   # profit per $1 staked
    graded: Optional[str] = None           # ISO timestamp when settled


def load(path: str = LEDGER_PATH) -> List[LedgerEntry]:
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [LedgerEntry(**row) for row in json.load(fh)]


def save(entries: List[LedgerEntry], path: str = LEDGER_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump([asdict(e) for e in entries], fh, indent=1)
    os.replace(tmp, path)


def record(event: str, event_date: str, generated: str, bets: List[dict],
           path: str = LEDGER_PATH) -> int:
    """Append one pending entry per pick; (event, fighter) pairs already present are skipped."""
    entries = load(path)
    seen = {(e.event, e.fighter) for e in entries}
    added = 0
    for b in bets:
        if (event, b["fighter"]) in seen:
            continue
        entries.append(LedgerEntry(event=event, event_date=event_date, generated=generated,
                                   fighter=b["fighter"], opponent=b["opponent"], odds=int(b["odds"]),
                                   model_prob=b["model_prob"], market_prob=b["implied_prob"],
                                   edge=b["edge"], kelly=b["kelly"], stake_pct=b["stake_pct"]))
        seen.add((event, b["fighter"]))
        added += 1
    if added:
        save(entries, path)
    return added


def payout_per_unit(odds: int) -> float:
    """Profit on a $1 winning stake at an American price."""
    return 100 / -odds if odds < 0 else odds / 100


def _outcome(row: dict, entry: LedgerEntry):
    if row["Draw"] == "True" or not row["Winner"]:
        return "push", 0.0
    if row["Winner"] == entry.fighter:
        return "win", round(payout_per_unit(entry.odds), 4)
    return "loss", -1.0


def grade(results_csv: str = RESULTS_CSV, path: str = LEDGER_PATH, now=None) -> int:
    """Settle pending entries from scraped results. Returns how many were graded."""
    entries = load(path)
    pending = [e for e in entries if e.result == "pending"]
    if not pending:
        return 0
    with open(results_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    graded = 0
    for entry in pending:
        when = datetime.strptime(entry.event_date, "%Y-%m-%d")
        for row in rows:
            if {row["Red Fighter"], row["Blue Fighter"]} != {entry.fighter, entry.opponent}:
                continue
            if abs(datetime.strptime(row["Date"], "%B %d, %Y") - when) > MATCH_WINDOW:
                continue
            if row["Winner"] and row["Winner"] not in (entry.fighter, entry.opponent):
                continue  # malformed row: a named winner who is neither corner
            entry.result, entry.pnl_per_unit = _outcome(row, entry)
            entry.graded = stamp
            graded += 1
            break
    if graded:
        save(entries, path)
    return graded
