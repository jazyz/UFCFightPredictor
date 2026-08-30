"""Add fighters referenced by fight data but missing from the fighter database.

process_fights_alpha.py reads Fighter.DOB for every fighter it encounters and
raises KeyError on anyone the database has never seen, so this has to run after
any scrape that introduces debutants.
"""
import argparse
import csv
import os
import re
import sqlite3
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ufcnet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "instance", "detailedfighters.db")
FIGHTS = os.path.join(ROOT, "data", "fight_details_date.csv")
INDEX = "http://ufcstats.com/statistics/fighters?char={c}&page=all"

KEYMAP = {"SLpM": "SLpM", "Str. Acc.": "Str_Acc", "SApM": "SApM",
          "Str. Def": "Str_Def", "TD Avg.": "TD_Avg", "TD Acc.": "TD_Acc",
          "TD Def.": "TD_Def", "Sub. Avg.": "Sub_Avg", "Height": "Height",
          "Weight": "Weight", "Reach": "Reach", "Stance": "Stance", "DOB": "DOB"}
FLOATS = {"SLpM", "SApM", "TD_Avg", "Sub_Avg"}
COLS = ["name", "record", "SLpM", "Str_Acc", "SApM", "Str_Def", "TD_Avg",
        "TD_Acc", "TD_Def", "Sub_Avg", "Height", "Weight", "Reach", "Stance", "DOB"]


def referenced_names(path=FIGHTS):
    names = set()
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            for key in ("Red Fighter", "Blue Fighter"):
                v = (row.get(key) or "").strip()
                if v:
                    names.add(v)
    return names


def missing_names(db=DB, path=FIGHTS):
    con = sqlite3.connect(db)
    try:
        have = {r[0].strip() for r in con.execute("SELECT name FROM fighter")}
    finally:
        con.close()
    return sorted(referenced_names(path) - have)


def _parse(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("h2", class_="b-content__title")
    if not title:
        return None
    txt = title.get_text()
    name = re.search(r"^([^\n]+)", txt.strip()).group(1).strip()
    rec = (re.search(r"Record: (\d+-\d+-\d+ \(.*\))", txt)
           or re.search(r"Record: (\d+-\d+-\d+)", txt))
    stats = {"name": name, "record": rec.group(1).strip() if rec else None}
    for item in soup.find_all("li", class_="b-list__box-list-item"):
        lab = item.find("i", class_="b-list__box-item-title")
        if not lab:
            continue
        label = lab.get_text().strip().rstrip(":")
        if label == "STANCE":
            label = "Stance"
        if label not in KEYMAP:
            continue
        sib = lab.next_sibling
        val = sib.text.strip() if hasattr(sib, "text") else (sib.strip() if sib else "")
        stats[KEYMAP[label]] = val
    return stats


def build_name_index(session, log=print):
    """Map "First Last" -> fighter-details URL across the a-z listing."""
    link_of = {}
    for c in "abcdefghijklmnopqrstuvwxyz":
        soup = BeautifulSoup(ufcnet.get(session, INDEX.format(c=c), delay=0.25), "html.parser")
        rows = soup.find_all("tr", class_="b-statistics__table-row")
        if not rows:
            raise ufcnet.ScrapeError(f"fighter index '{c}' parsed to zero rows")
        for row in rows:
            tds = row.find_all("td")
            links = [a for a in row.find_all("a", href=True) if "fighter-details" in a["href"]]
            if len(tds) < 2 or not links:
                continue
            full = (tds[0].get_text(strip=True) + " " + tds[1].get_text(strip=True)).strip()
            link_of.setdefault(full, links[0]["href"])
    log(f"fighter index built: {len(link_of)} names")
    return link_of


def run(dry_run=False, log=print):
    missing = missing_names()
    log(f"fighters missing from database: {len(missing)}")
    if not missing or dry_run:
        return 0

    session = ufcnet.new_session()
    link_of = build_name_index(session, log=log)

    con = sqlite3.connect(DB)
    next_id = con.execute("SELECT COALESCE(MAX(id),0) FROM fighter").fetchone()[0] + 1
    added, unmatched = 0, []
    try:
        for name in missing:
            url = link_of.get(name)
            if not url:
                unmatched.append(name)
                continue
            stats = _parse(ufcnet.get(session, url, delay=0.25))
            if not stats:
                unmatched.append(name)
                continue
            values = []
            for col in COLS:
                v = stats.get(col)
                if col in FLOATS:
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        v = None
                values.append(v)
            con.execute(
                f"INSERT INTO fighter (id,{','.join(COLS)}) "
                f"VALUES ({','.join(['?'] * (len(COLS) + 1))})",
                [next_id] + values)
            next_id += 1
            added += 1
            if added % 50 == 0:
                con.commit()
                log(f"  inserted {added}/{len(missing)}")
        con.commit()
    finally:
        con.close()

    log(f"inserted {added} fighters; {len(unmatched)} had no listing")
    if unmatched:
        log(f"  unmatched: {unmatched[:20]}")
    return added


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report what is missing, change nothing")
    a = ap.parse_args()
    run(dry_run=a.dry_run)
