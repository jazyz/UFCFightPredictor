"""Backfill the empty Stance column in instance/detailedfighters.db.

scrape_fighters.py retitled the "STANCE" label before its key_mapping lookup,
so every fighter row was stored with an empty stance (fixed in 54aa94c, but the
DB was never repopulated). Rather than re-scraping ~4,300 fighter detail pages,
this reads the 26 a-z fighter index pages — which carry a Stance column — and
fills Stance by full name, using Height to break ties between same-named
fighters (skipping any that stay ambiguous). Fighters whose stance the site
itself leaves blank stay empty. Only empty Stance values are written; nothing
else in the DB is touched.
"""
import os
import sqlite3
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ufcnet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "instance", "detailedfighters.db")
INDEX_URL = "http://ufcstats.com/statistics/fighters?char={char}&page=all"


def parse_index_page(html, char):
    """(full name, height, stance) for every fighter on one index page."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="b-statistics__table")
    if table is None:
        raise ufcnet.ScrapeError(f"no fighter table on index page {char!r}")

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    try:
        i_first, i_last = headers.index("First"), headers.index("Last")
        i_height, i_stance = headers.index("Ht."), headers.index("Stance")
    except ValueError:
        raise ufcnet.ScrapeError(
            f"index page {char!r} is missing expected columns; got {headers}")

    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) <= max(i_first, i_last, i_height, i_stance):
            continue
        name = f"{tds[i_first].get_text(strip=True)} {tds[i_last].get_text(strip=True)}".strip()
        if not name:
            continue
        rows.append((name, tds[i_height].get_text(strip=True),
                     tds[i_stance].get_text(strip=True)))

    if not rows:
        raise ufcnet.ScrapeError(f"index page {char!r} parsed to zero fighters")
    return rows


def main():
    session = ufcnet.new_session()
    by_name = {}
    total = 0
    for char in "abcdefghijklmnopqrstuvwxyz":
        rows = parse_index_page(ufcnet.get(session, INDEX_URL.format(char=char)), char)
        total += len(rows)
        for name, height, stance in rows:
            by_name.setdefault(name, []).append((height, stance))
        print(f"  {char}: {len(rows)} fighters")
    print(f"index pages parsed: {total} fighters, {len(by_name)} distinct names")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, Height FROM fighter "
                "WHERE Stance IS NULL OR TRIM(Stance) = ''")
    todo = cur.fetchall()

    updated = site_blank = ambiguous = unmatched = 0
    for fighter_id, name, height in todo:
        candidates = by_name.get(name)
        if not candidates:
            unmatched += 1
            continue
        if len(candidates) > 1:
            # Same-named fighters: prefer the height match; if that still
            # leaves several, only proceed when they agree on stance.
            matched = [c for c in candidates if c[0] == (height or "")]
            stances = {c[1] for c in (matched or candidates)}
            if len(stances) != 1:
                ambiguous += 1
                continue
            stance = stances.pop()
        else:
            stance = candidates[0][1]
        if not stance:
            site_blank += 1  # the site lists no stance for this fighter
            continue
        cur.execute("UPDATE fighter SET Stance = ? WHERE id = ?", (stance, fighter_id))
        updated += 1

    conn.commit()
    conn.close()

    print(f"rows missing stance: {len(todo)}")
    print(f"  updated:          {updated}")
    print(f"  blank on site:    {site_blank}")
    print(f"  ambiguous name:   {ambiguous}")
    print(f"  not in index:     {unmatched}")
    if updated == 0:
        raise ufcnet.ScrapeError("backfill wrote nothing — treat as failure, not 'no new data'")


if __name__ == "__main__":
    main()
