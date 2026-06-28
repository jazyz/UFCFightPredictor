#!/usr/bin/env python3
"""
Backfill missing fighter DOBs from UFCStats fighter pages.

The feature pipeline gets DOBs from instance/detailedfighters.db. When that DB
is stale, missing DOBs become impossible ages during feature generation. This
script scans feature rows for fighters with missing DOBs, finds their UFCStats
fighter pages, parses DOB, and upserts the DOB into the local fighter table.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRAPER_DIR = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, SCRAPER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scrape_incremental import fetch_url
from utils.name_matching import lookup_keys, normalize_name


UFCSTATS_BASE_URL = "http://ufcstats.com"
VALID_DOB_FORMATS = ("%b %d, %Y", "%B %d, %Y")


def valid_dob(value: object) -> bool:
    text = str(value).strip()
    if text in {"", "--", "nan", "None"}:
        return False
    for date_format in VALID_DOB_FORMATS:
        try:
            datetime.strptime(text, date_format)
            return True
        except ValueError:
            continue
    return False


def parse_date(value: object):
    return pd.to_datetime(value, format="mixed", errors="coerce")


def target_names_from_features(features_path: Path, start_date: str, end_date: str) -> list[str]:
    df = pd.read_csv(features_path)
    df["Date"] = parse_date(df["Date"])
    window = df[
        (df["Date"] >= pd.Timestamp(start_date))
        & (df["Date"] <= pd.Timestamp(end_date))
    ]

    missing = set()
    for side in ("Red", "Blue"):
        dob = pd.to_numeric(window.get(f"{side} dob"), errors="coerce")
        age = pd.to_numeric(window.get(f"{side} age"), errors="coerce")
        missing_mask = dob.isna() | (dob <= 1900) | age.isna() | (age < 12) | (age > 120)
        missing.update(window.loc[missing_mask, f"{side} Fighter"].dropna().astype(str))

    return sorted(missing)


def target_names_from_arg(names: str) -> list[str]:
    return sorted({name.strip() for name in names.split(",") if name.strip()})


def load_supplemental_dobs(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    required_columns = {"fighter_name", "dob"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"{path} is missing required columns: {sorted(missing_columns)}")

    indexed = {}
    for row in df.to_dict("records"):
        if not valid_dob(row.get("dob")):
            continue
        for key in lookup_keys(row["fighter_name"]):
            indexed[key] = row
    return indexed


def supplemental_row_for_name(name: str, supplemental: dict[str, dict]) -> dict | None:
    for key in lookup_keys(name):
        row = supplemental.get(key)
        if row:
            return row
    return None


def fighter_name_from_row(row) -> str:
    cols = row.find_all("td")
    if len(cols) >= 2:
        first = cols[0].get_text(" ", strip=True)
        last = cols[1].get_text(" ", strip=True)
        full_name = " ".join(part for part in (first, last) if part).strip()
        if full_name:
            return full_name

    link = row.find("a", href=lambda href: href and "fighter-details" in href)
    return "" if link is None else link.get_text(" ", strip=True)


def index_characters_for_targets(target_names: list[str]) -> list[str]:
    characters = set()
    for name in target_names:
        for key in lookup_keys(name):
            if key:
                characters.add(key[0])
    return sorted(character for character in characters if character.isalpha())


def build_fighter_link_index(characters: list[str], timeout: int, sleep: float) -> dict[str, str]:
    indexed = {}

    for character in characters:
        url = f"{UFCSTATS_BASE_URL}/statistics/fighters?char={character}&page=all"
        try:
            response = fetch_url(url, timeout=timeout)
        except Exception as exc:
            print(f"Failed to fetch fighter index for {character}: {exc}")
            continue

        if response.status_code != 200:
            print(f"Failed to fetch fighter index for {character}: {response.status_code}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("tr")
        for row in rows[1:]:
            link = row.find("a", href=lambda href: href and "fighter-details" in href)
            if link is None:
                continue

            fighter_url = urljoin(UFCSTATS_BASE_URL, link["href"])
            fighter_name = fighter_name_from_row(row)
            for key in lookup_keys(fighter_name):
                indexed.setdefault(key, fighter_url)

        time.sleep(sleep)

    return indexed


def matching_link_for_name(name: str, link_index: dict[str, str]) -> str | None:
    for key in lookup_keys(name):
        fighter_url = link_index.get(key)
        if fighter_url:
            return fighter_url
    return None


def parse_ufcstats_event_date(row) -> datetime | None:
    text = row.get_text(" ", strip=True)
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%B %d, %Y")
    except ValueError:
        return None


def build_event_fighter_link_index(
    target_names: list[str],
    start_date: str,
    end_date: str,
    timeout: int,
    sleep: float,
) -> dict[str, str]:
    if not target_names:
        return {}

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    indexed = {}
    remaining = set(target_names)
    target_by_key = {
        key: target_name
        for target_name in target_names
        for key in lookup_keys(target_name)
    }

    url = f"{UFCSTATS_BASE_URL}/statistics/events/completed?page=all"
    try:
        response = fetch_url(url, timeout=timeout)
    except Exception as exc:
        print(f"Failed to fetch UFCStats completed events: {exc}")
        return indexed

    if response.status_code != 200:
        print(f"Failed to fetch UFCStats completed events: {response.status_code}")
        return indexed

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr", class_="b-statistics__table-row")

    for row in rows:
        link = row.find("a", href=True)
        event_date = parse_ufcstats_event_date(row)
        if link is None or event_date is None:
            continue
        if not (start <= pd.Timestamp(event_date) <= end):
            continue

        event_url = urljoin(UFCSTATS_BASE_URL, link["href"])
        try:
            event_response = fetch_url(event_url, timeout=timeout)
        except Exception as exc:
            print(f"Failed to fetch event page {event_url}: {exc}")
            continue

        if event_response.status_code != 200:
            print(f"Failed to fetch event page {event_url}: {event_response.status_code}")
            continue

        event_soup = BeautifulSoup(event_response.text, "html.parser")
        event_text = normalize_name(event_soup.get_text(" ", strip=True))
        matching_targets = [
            target_name
            for target_name in sorted(remaining)
            if any(key in event_text for key in lookup_keys(target_name))
        ]
        if not matching_targets:
            continue

        fight_urls = {
            urljoin(UFCSTATS_BASE_URL, fight_link["href"])
            for fight_link in event_soup.find_all("a", href=lambda href: href and "fight-details" in href)
        }
        for fight_url in sorted(fight_urls):
            try:
                fight_response = fetch_url(fight_url, timeout=timeout)
            except Exception as exc:
                print(f"Failed to fetch fight page {fight_url}: {exc}")
                continue

            if fight_response.status_code != 200:
                print(f"Failed to fetch fight page {fight_url}: {fight_response.status_code}")
                continue

            fight_soup = BeautifulSoup(fight_response.text, "html.parser")
            fight_text = normalize_name(fight_soup.get_text(" ", strip=True))
            if not any(
                key in fight_text
                for target_name in matching_targets
                for key in lookup_keys(target_name)
            ):
                continue

            for person in fight_soup.find_all("div", class_="b-fight-details__person"):
                name_element = person.find("h3", class_="b-fight-details__person-name")
                link_element = person.find("a", href=lambda href: href and "fighter-details" in href)
                if name_element is None or link_element is None:
                    continue

                page_name = name_element.get_text(" ", strip=True)
                target_name = None
                for key in lookup_keys(page_name):
                    target_name = target_by_key.get(key)
                    if target_name:
                        break
                if not target_name:
                    continue

                fighter_url = urljoin(UFCSTATS_BASE_URL, link_element["href"])
                for key in lookup_keys(target_name) + lookup_keys(page_name):
                    indexed.setdefault(key, fighter_url)
                remaining.discard(target_name)
                print(f"{target_name} -> UFCStats fight-page profile: {fighter_url}")

            if not remaining:
                return indexed
            time.sleep(sleep)

        time.sleep(sleep)

    return indexed


def parse_fighter_page(url: str, timeout: int) -> tuple[str, str | None]:
    response = fetch_url(url, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"failed to fetch {url}: status {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("h2", class_="b-content__title")
    page_name = ""
    if title is not None:
        page_name = title.get_text(" ", strip=True).split("Record:")[0].strip()

    dob = None
    for item in soup.find_all("li", class_="b-list__box-list-item"):
        label = item.find("i", class_="b-list__box-item-title")
        if label is None:
            continue
        label_text = label.get_text(" ", strip=True).replace(":", "").strip()
        if label_text != "DOB":
            continue
        dob_text = item.get_text(" ", strip=True).replace(label.get_text(" ", strip=True), "", 1).strip()
        if valid_dob(dob_text):
            dob = dob_text
        break

    return page_name, dob


def load_fighter_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return list(connection.execute("select id, name, DOB from fighter"))


def find_existing_fighter_id(rows: list[sqlite3.Row], names: list[str]) -> int | None:
    wanted_keys = set()
    for name in names:
        wanted_keys.update(lookup_keys(name))

    for row in rows:
        row_keys = set(lookup_keys(row["name"]))
        if wanted_keys & row_keys:
            return int(row["id"])
    return None


def upsert_dob(
    connection: sqlite3.Connection,
    rows: list[sqlite3.Row],
    target_name: str,
    page_name: str,
    dob: str,
    replace_existing: bool,
) -> str:
    existing_id = find_existing_fighter_id(rows, [target_name, page_name])
    if existing_id is None:
        connection.execute(
            "insert into fighter (name, DOB) values (?, ?)",
            (page_name or target_name, dob),
        )
        return "inserted"

    current = connection.execute(
        "select DOB from fighter where id = ?",
        (existing_id,),
    ).fetchone()[0]
    if valid_dob(current) and not replace_existing:
        return "kept-existing"

    connection.execute(
        "update fighter set DOB = ? where id = ?",
        (dob, existing_id),
    )
    return "updated"


def run(args: argparse.Namespace) -> dict:
    if args.names:
        target_names = target_names_from_arg(args.names)
    else:
        target_names = target_names_from_features(
            Path(args.features),
            args.start_date,
            args.end_date,
        )
    if args.limit:
        target_names = target_names[: args.limit]

    print(f"Targets with missing/impossible DOBs: {len(target_names)}")
    supplemental = load_supplemental_dobs(Path(args.supplemental_dobs))
    print(f"Supplemental DOB entries: {len(supplemental)}")
    characters = (
        list("abcdefghijklmnopqrstuvwxyz")
        if args.index_all and target_names
        else index_characters_for_targets(target_names)
    )
    link_index = {}
    if characters:
        print(f"Indexing UFCStats fighter-list characters: {''.join(characters)}")
        link_index = build_fighter_link_index(characters, args.timeout, args.sleep)
    else:
        print("No UFCStats fighter-list indexing needed")
    print(f"Indexed UFCStats fighter links: {len(link_index)}")

    unresolved_after_index = [
        name for name in target_names
        if matching_link_for_name(name, link_index) is None
    ]
    if unresolved_after_index and not args.skip_event_page_fallback:
        print(f"Searching UFCStats event/fight pages for profile links: {len(unresolved_after_index)}")
        event_link_index = build_event_fighter_link_index(
            unresolved_after_index,
            args.start_date,
            args.end_date,
            args.timeout,
            args.sleep,
        )
        for key, fighter_url in event_link_index.items():
            link_index.setdefault(key, fighter_url)
        print(f"Indexed UFCStats event/fight-page links: {len(event_link_index)}")

    connection = sqlite3.connect(args.database)
    rows = load_fighter_rows(connection)

    found = []
    missing_link = []
    missing_dob = []
    errors = []

    for target_name in target_names:
        fighter_url = matching_link_for_name(target_name, link_index)

        if fighter_url is None:
            supplemental_row = supplemental_row_for_name(target_name, supplemental)
            if supplemental_row:
                dob = supplemental_row["dob"]
                action = "dry-run"
                if not args.dry_run:
                    action = upsert_dob(
                        connection,
                        rows,
                        target_name,
                        supplemental_row["fighter_name"],
                        dob,
                        args.replace_existing,
                    )
                    rows = load_fighter_rows(connection)

                found.append(
                    {
                        "target_name": target_name,
                        "page_name": supplemental_row["fighter_name"],
                        "dob": dob,
                        "url": supplemental_row.get("source_url", ""),
                        "source": supplemental_row.get("source_name", "supplemental"),
                        "action": action,
                    }
                )
                print(f"{target_name} -> {supplemental_row['fighter_name']}: {dob} ({action}, supplemental)")
                continue

            missing_link.append(target_name)
            continue

        try:
            page_name, dob = parse_fighter_page(fighter_url, args.timeout)
        except Exception as exc:
            errors.append({"target_name": target_name, "url": fighter_url, "error": str(exc)})
            continue

        if not dob:
            missing_dob.append({"target_name": target_name, "page_name": page_name, "url": fighter_url})
            continue

        action = "dry-run"
        if not args.dry_run:
            action = upsert_dob(
                connection,
                rows,
                target_name,
                page_name,
                dob,
                args.replace_existing,
            )
            rows = load_fighter_rows(connection)

        found.append(
            {
                "target_name": target_name,
                "page_name": page_name,
                "dob": dob,
                "url": fighter_url,
                "source": "UFCStats",
                "action": action,
            }
        )
        print(f"{target_name} -> {page_name or target_name}: {dob} ({action})")
        time.sleep(args.sleep)

    if not args.dry_run:
        connection.commit()
    connection.close()

    report = {
        "features": args.features,
        "database": args.database,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "dry_run": args.dry_run,
        "replace_existing": args.replace_existing,
        "supplemental_dobs": args.supplemental_dobs,
        "skip_event_page_fallback": args.skip_event_page_fallback,
        "targets": len(target_names),
        "found": found,
        "missing_link": missing_link,
        "missing_dob": missing_dob,
        "errors": errors,
    }

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as file:
            json.dump(report, file, indent=2)
        print(f"Wrote report: {report_path}")

    print("\n" + "=" * 70)
    print(f"Targets: {len(target_names)}")
    print(f"Found DOBs: {len(found)}")
    print(f"Missing links: {len(missing_link)}")
    print(f"Missing DOB on page: {len(missing_dob)}")
    print(f"Errors: {len(errors)}")
    print("=" * 70)
    return report


def parse_args() -> argparse.Namespace:
    today = datetime.now().date()
    start = today - timedelta(days=365)
    parser = argparse.ArgumentParser(description="Backfill missing fighter DOBs from UFCStats.")
    parser.add_argument("--features", default="data/detailed_fights.csv")
    parser.add_argument("--database", default="instance/detailedfighters.db")
    parser.add_argument("--report", default="data/fighter_dob_backfill_report.json")
    parser.add_argument("--supplemental-dobs", default="data/supplemental_fighter_dobs.csv")
    parser.add_argument("--names", default="", help="comma-separated fighter names to backfill instead of scanning features")
    parser.add_argument("--start-date", default=start.isoformat())
    parser.add_argument("--end-date", default=today.isoformat())
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=0, help="limit target names for smoke tests")
    parser.add_argument("--index-all", action="store_true", help="index all fighter-list letters")
    parser.add_argument("--skip-event-page-fallback", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
