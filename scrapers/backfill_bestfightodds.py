#!/usr/bin/env python3
"""
Backfill missing UFC fight odds from BestFightOdds.

The existing UFC.com odds scraper often leaves recent completed fights with
dash-only odds or no row at all. This script repairs the local odds CSV by:

1. finding model-evaluable fights in a date window that lack usable odds
2. discovering the matching BestFightOdds event page from fighter history pages
3. parsing sportsbook moneylines from the event page
4. writing a merged `data/fight_results_with_odds.csv`

BestFightOdds pages expose many sportsbook columns. For one local odds number
per fighter, this script uses the median of sportsbook moneylines and ignores
prediction-market and props columns.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import statistics
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.bestfightodds.com"
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (compatible; UFCFightPredictor odds backfill)",
}

ODDS_COLUMNS = [
    "event_name",
    "event_date",
    "fighter1_name",
    "fighter2_name",
    "winner_name",
    "fighter1_odds",
    "fighter2_odds",
]

NAME_ALIASES = {
    "king green": "bobby green",
    "alatengheili alateng": "alatengheili",
    "jan bachowicz": "jan blachowicz",
    "jiri prochazka": "jiri prochazka",
    "asu almabayev": "asu almabaev",
    "beatriz mesquita": "bia mesquita",
    "carlos leal": "carlos leal miranda",
    "daria zheleznyakova": "daria zhelezniakova",
    "darya zheleznyakova": "daria zhelezniakova",
    "dennis buzukia": "dennis buzukja",
    "michael aswell jr": "michael aswell",
    "melissa dixon": "melissa mullins",
    "sean o malley": "sean omalley",
    "sergey spivak": "serghei spivac",
    "shara magomedov": "sharabutdin magomedov",
    "durko todorovir": "dusko todorovic",
    "ion curelaba": "ion cutelaba",
    "lupita godinez": "loopy godinez",
    "maheshate hayisaer": "maheshate",
    "montserrat rendon": "montse rendon",
    "patricio pitbull": "patricio freire",
    "ronaldo bedoya": "rolando bedoya",
    "rukasz brzeski": "lukasz brzeski",
    "stephen erceg": "steve erceg",
    "timothy cuamba": "timmy cuamba",
}

SKIP_BOOK_PATTERNS = (
    "props",
    "prop",
    "polymarket",
    "kalshi",
    "bonus",
    "free",
)


@dataclass(frozen=True)
class TargetFight:
    event_date: date
    red_fighter: str
    blue_fighter: str
    winner_name: str
    title: str
    source: str = "features"


@dataclass(frozen=True)
class BFOFight:
    event_date: date | None
    event_url: str
    event_name: str
    fighter1_name: str
    fighter2_name: str
    fighter1_odds: int | None
    fighter2_odds: int | None
    source: str


def normalize_name(name: object) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", str(name))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    lowered = ascii_name.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    parts = [
        part
        for part in cleaned.split()
        if part not in {"jr", "sr", "ii", "iii", "iv"}
    ]
    normalized = " ".join(parts)
    return NAME_ALIASES.get(normalized, normalized)


def ascii_text(value: object) -> str:
    return (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def suggest_query_variants(query: str) -> list[str]:
    variants = [
        str(query).strip(),
        ascii_text(query).strip(),
        normalize_name(query),
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        if not variant or variant in seen:
            continue
        unique.append(variant)
        seen.add(variant)
    return unique


def compact_name(name: object) -> str:
    return normalize_name(name).replace(" ", "")


def names_match(left: object, right: object) -> bool:
    left_norm = normalize_name(left)
    right_norm = normalize_name(right)
    if left_norm == right_norm:
        return True
    if compact_name(left_norm) == compact_name(right_norm):
        return True
    if difflib.SequenceMatcher(None, compact_name(left_norm), compact_name(right_norm)).ratio() >= 0.94:
        return True

    left_parts = left_norm.split()
    right_parts = right_norm.split()
    if len(left_parts) >= 2 and len(right_parts) >= 2:
        left_set = set(left_parts)
        right_set = set(right_parts)
        if left_set.issubset(right_set) or right_set.issubset(left_set):
            return True
        if left_parts[-1] == right_parts[-1]:
            return (
                left_parts[0].startswith(right_parts[0][:4])
                or right_parts[0].startswith(left_parts[0][:4])
            )

    return False


def pairs_match(left1: object, left2: object, right1: object, right2: object) -> bool:
    return (
        names_match(left1, right1)
        and names_match(left2, right2)
    ) or (
        names_match(left1, right2)
        and names_match(left2, right1)
    )


def parse_date(value: object) -> pd.Timestamp:
    return pd.to_datetime(value, format="mixed", errors="coerce")


def date_key(value: object) -> date | None:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return None
    return parsed.date()


def fight_key(event_date: date, fighter1: str, fighter2: str) -> tuple[date, frozenset[str]]:
    return event_date, frozenset({normalize_name(fighter1), normalize_name(fighter2)})


def parse_american_odds(value: object) -> int | None:
    cleaned = str(value).strip().replace("−", "-")
    if cleaned in {"", "-", "nan", "None", "n/a"}:
        return None
    match = re.search(r"(?<!\d)([+-]\d{2,5})(?!\d)", cleaned)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def has_usable_odds(row: pd.Series) -> bool:
    return (
        parse_american_odds(row.get("fighter1_odds")) is not None
        and parse_american_odds(row.get("fighter2_odds")) is not None
    )


def american_odds_text(value: int | None) -> str:
    if value is None:
        return "-"
    if value > 0:
        return f"+{value}"
    return str(value)


def output_date(value: date) -> str:
    return value.strftime("%b %d %Y").replace(" 0", " ")


def slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def event_query_from_slug(slug: object) -> str:
    text = str(slug).strip()
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def bfo_date_from_text(text: str) -> date | None:
    match = re.search(
        r"\b([A-Z][a-z]{2})\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})\b",
        text,
    )
    if not match:
        return None
    month, day, year = match.groups()
    try:
        return datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
    except ValueError:
        return None


def dates_close(left: date, right: date, tolerance_days: int) -> bool:
    return abs((left - right).days) <= tolerance_days


class BFOClient:
    def __init__(
        self,
        cache_dir: Path,
        refresh_cache: bool = False,
        sleep_seconds: float = 0.1,
        timeout: int = 30,
    ) -> None:
        self.cache_dir = cache_dir
        self.refresh_cache = refresh_cache
        self.sleep_seconds = sleep_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str, suffix: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}{suffix}"

    def get_text(self, url: str) -> str:
        absolute_url = urljoin(BASE_URL, url)
        path = self._cache_path(absolute_url, ".html")
        if path.exists() and not self.refresh_cache:
            return path.read_text(encoding="utf-8")

        try:
            response = self.session.get(absolute_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"  warning: could not fetch {absolute_url}: {exc}")
            return ""
        text = response.text
        path.write_text(text, encoding="utf-8")
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return text

    def get_json(self, url: str, params: dict[str, str]) -> object:
        absolute_url = urljoin(BASE_URL, url)
        cache_url = absolute_url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        path = self._cache_path(cache_url, ".json")
        if path.exists() and not self.refresh_cache:
            return json.loads(path.read_text(encoding="utf-8"))

        try:
            response = self.session.get(absolute_url, params=params, headers={"Accept": "application/json"}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  warning: could not fetch JSON {absolute_url} {params}: {exc}")
            return []
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return data

    def suggest_fighter_url(self, fighter_name: str) -> str | None:
        suggestions: list[object] = []
        for query in suggest_query_variants(fighter_name):
            query_suggestions = self.get_json("/api/suggest", {"q": query})
            if isinstance(query_suggestions, list):
                suggestions.extend(query_suggestions)

        normalized_target = normalize_name(fighter_name)
        fighter_suggestions = [
            item
            for item in suggestions
            if isinstance(item, dict) and str(item.get("type", "")).lower() == "fighter"
        ]

        for item in fighter_suggestions:
            if names_match(item.get("name", ""), normalized_target):
                return str(item.get("url"))

        target_tokens = set(normalized_target.split())
        for item in fighter_suggestions:
            item_tokens = set(normalize_name(item.get("name", "")).split())
            if target_tokens and target_tokens.issubset(item_tokens):
                return str(item.get("url"))

        if fighter_suggestions:
            return str(fighter_suggestions[0].get("url"))
        return None

    def suggest_event_urls(self, query: str) -> list[str]:
        urls = []
        seen: set[str] = set()
        for query_variant in suggest_query_variants(query):
            suggestions = self.get_json("/api/suggest", {"q": query_variant})
            if not isinstance(suggestions, list):
                continue
            for item in suggestions:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type", "")).lower() != "event":
                    continue
                url = str(item.get("url", ""))
                if not url.startswith("/events/"):
                    continue
                absolute_url = urljoin(BASE_URL, url)
                if absolute_url in seen:
                    continue
                urls.append(absolute_url)
                seen.add(absolute_url)
        return urls

    def fighter_history_matches(
        self,
        fighter_name: str,
        opponent_name: str,
        target_date: date,
        tolerance_days: int,
    ) -> list[BFOFight]:
        fighter_url = self.suggest_fighter_url(fighter_name)
        if not fighter_url:
            return []

        soup = BeautifulSoup(self.get_text(fighter_url), "html.parser")
        table = soup.find("table", class_="team-stats-table")
        if table is None:
            return []

        matches: list[BFOFight] = []
        current_event_url: str | None = None
        current_event_name = ""
        current_date: date | None = None
        pending_row: tuple[str, int | None] | None = None

        for row in table.find_all("tr"):
            row_classes = set(row.get("class") or [])
            if "event-header" in row_classes:
                current_date = bfo_date_from_text(row.get_text(" ", strip=True))
                event_link = row.find("a", href=re.compile(r"^/events/"))
                current_event_url = urljoin(BASE_URL, event_link["href"]) if event_link else None
                current_event_name = event_link.get_text(" ", strip=True) if event_link else ""
                pending_row = None
                continue

            if current_date is None or current_event_url is None:
                continue
            if not dates_close(current_date, target_date, tolerance_days):
                continue

            fighter_link = row.find("a", href=re.compile(r"^/fighters/"))
            if fighter_link is None:
                continue

            row_name = fighter_link.get_text(" ", strip=True)
            odds_values = [
                parse_american_odds(cell.get_text(" ", strip=True))
                for cell in row.find_all(class_="moneyline")
            ]
            odds_values = [value for value in odds_values if value is not None]
            closing_odds = odds_values[-1] if odds_values else None

            if pending_row is None:
                pending_row = (row_name, closing_odds)
                continue

            fighter1_name, fighter1_odds = pending_row
            fighter2_name, fighter2_odds = row_name, closing_odds
            pending_row = None
            if not pairs_match(fighter1_name, fighter2_name, fighter_name, opponent_name):
                continue

            matches.append(
                BFOFight(
                    event_date=current_date,
                    event_url=current_event_url,
                    event_name=current_event_name or slug_from_url(current_event_url),
                    fighter1_name=fighter1_name,
                    fighter2_name=fighter2_name,
                    fighter1_odds=fighter1_odds,
                    fighter2_odds=fighter2_odds,
                    source="bestfightodds_fighter_history_closing",
                )
            )

        return matches

    def parse_event(self, event_url: str, event_date_hint: date | None = None) -> list[BFOFight]:
        soup = BeautifulSoup(self.get_text(event_url), "html.parser")
        event_header = soup.find(class_="table-header")
        event_name = ""
        event_date = event_date_hint
        if event_header:
            event_text = event_header.get_text(" ", strip=True)
            event_name = re.sub(r"\s+[A-Z][a-z]{2}\s+\d{1,2}(?:st|nd|rd|th)?.*$", "", event_text).strip()
            event_date = event_date or bfo_date_from_text(event_text)

        fights: list[BFOFight] = []
        for table in soup.find_all("table", class_="odds-table"):
            classes = set(table.get("class") or [])
            if "odds-table-responsive-header" in classes:
                continue

            rows = table.find_all("tr")
            if not rows:
                continue

            header_cells = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
            allowed_indexes = allowed_moneyline_indexes(header_cells)
            pending: tuple[str, int | None] | None = None

            for row in rows[1:]:
                if "pr" in set(row.get("class") or []):
                    continue

                cells = row.find_all(["th", "td"])
                if not cells:
                    continue

                fighter_name = fighter_name_from_event_row(cells[0])
                if not fighter_name:
                    pending = None
                    continue

                odds_values = []
                for index, cell in enumerate(cells):
                    if index == 0 or index not in allowed_indexes:
                        continue
                    parsed = parse_american_odds(cell.get_text(" ", strip=True))
                    if parsed is not None:
                        odds_values.append(parsed)

                consensus_odds = median_american_odds(odds_values)
                if pending is None:
                    pending = (fighter_name, consensus_odds)
                    continue

                fighter1_name, fighter1_odds = pending
                fighter2_name, fighter2_odds = fighter_name, consensus_odds
                pending = None
                fights.append(
                    BFOFight(
                        event_date=event_date,
                        event_url=urljoin(BASE_URL, event_url),
                        event_name=event_name or slug_from_url(event_url),
                        fighter1_name=fighter1_name,
                        fighter2_name=fighter2_name,
                        fighter1_odds=fighter1_odds,
                        fighter2_odds=fighter2_odds,
                        source="bestfightodds_event_consensus",
                    )
                )

        return fights


def allowed_moneyline_indexes(header_cells: list[str]) -> set[int]:
    allowed = set()
    for index, header in enumerate(header_cells):
        if index == 0:
            continue
        normalized = header.lower()
        if any(pattern in normalized for pattern in SKIP_BOOK_PATTERNS):
            continue
        allowed.add(index)
    return allowed


def fighter_name_from_event_row(first_cell) -> str:
    fighter_link = first_cell.find("a", href=re.compile(r"^/fighters/"))
    if fighter_link is not None:
        return fighter_link.get_text(" ", strip=True)

    text = first_cell.get_text(" ", strip=True)
    text = re.sub(r"^\d+\s+", "", text)
    if not text:
        return ""
    return text


def median_american_odds(values: Iterable[int]) -> int | None:
    values = list(values)
    if not values:
        return None
    median_probability = statistics.median(american_to_probability(value) for value in values)
    return probability_to_american(median_probability)


def american_to_probability(odds: int) -> float:
    if odds >= 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def probability_to_american(probability: float) -> int:
    probability = max(0.001, min(0.999, probability))
    if probability >= 0.5:
        return -int(round((probability * 100) / (1 - probability)))
    return int(round(((1 - probability) * 100) / probability))


def load_targets(args) -> list[TargetFight]:
    features = pd.read_csv(args.features)
    features["Date"] = parse_date(features["Date"])
    features = features.dropna(subset=["Date", "Red Fighter", "Blue Fighter", "Result"])
    features = features[
        (features["Date"] >= pd.Timestamp(args.start_date))
        & (features["Date"] <= pd.Timestamp(args.end_date))
    ].copy()

    odds = load_existing_odds(args.odds)
    odds_index = build_existing_odds_index(odds)
    event_name_by_date: dict[date, str] = {}
    for _, row in odds.iterrows():
        existing_date = date_key(row.get("event_date"))
        event_name = str(row.get("event_name", "")).strip()
        if existing_date is not None and event_name:
            event_name_by_date.setdefault(existing_date, event_name)

    targets: list[TargetFight] = []
    seen: set[tuple[date, frozenset[str]]] = set()
    for _, row in features.sort_values("Date").iterrows():
        event_date = row["Date"].date()
        red_fighter = str(row["Red Fighter"])
        blue_fighter = str(row["Blue Fighter"])
        key = fight_key(event_date, red_fighter, blue_fighter)
        if key in seen:
            continue
        seen.add(key)

        existing = odds_index.get(key)
        if existing is not None and has_usable_odds(existing) and not args.replace_existing:
            continue

        result = str(row["Result"]).strip().lower()
        winner_name = red_fighter if result in {"win", "w"} else blue_fighter
        targets.append(
            TargetFight(
                event_date=event_date,
                red_fighter=red_fighter,
                blue_fighter=blue_fighter,
                winner_name=winner_name,
                title=event_name_by_date.get(event_date, str(row.get("Title", ""))),
                source="features",
            )
        )

    if not args.skip_odds_csv_targets:
        odds_window = odds.copy()
        odds_window["parsed_event_date"] = odds_window["event_date"].map(date_key)
        odds_window = odds_window.dropna(subset=["parsed_event_date"])
        odds_window = odds_window[
            (pd.to_datetime(odds_window["parsed_event_date"]) >= pd.Timestamp(args.start_date))
            & (pd.to_datetime(odds_window["parsed_event_date"]) <= pd.Timestamp(args.end_date))
        ]

        for _, row in odds_window.sort_values("parsed_event_date").iterrows():
            if has_usable_odds(row) and not args.replace_existing:
                continue

            event_date = row["parsed_event_date"]
            fighter1 = str(row.get("fighter1_name", ""))
            fighter2 = str(row.get("fighter2_name", ""))
            if not fighter1.strip() or not fighter2.strip():
                continue

            key = fight_key(event_date, fighter1, fighter2)
            if key in seen:
                continue
            seen.add(key)

            targets.append(
                TargetFight(
                    event_date=event_date,
                    red_fighter=fighter1,
                    blue_fighter=fighter2,
                    winner_name=str(row.get("winner_name", "")),
                    title=str(row.get("event_name", "")),
                    source="odds_csv",
                )
            )

    return targets


def load_existing_odds(path: str) -> pd.DataFrame:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=ODDS_COLUMNS)
    odds = pd.read_csv(path, dtype=str)
    for column in ODDS_COLUMNS:
        if column not in odds.columns:
            odds[column] = ""
    return odds[ODDS_COLUMNS].copy()


def build_existing_odds_index(odds: pd.DataFrame) -> dict[tuple[date, frozenset[str]], pd.Series]:
    indexed = {}
    for _, row in odds.iterrows():
        event_date = date_key(row.get("event_date"))
        if event_date is None:
            continue
        key = fight_key(event_date, row.get("fighter1_name", ""), row.get("fighter2_name", ""))
        indexed.setdefault(key, row)
    return indexed


def find_bfo_fight(
    client: BFOClient,
    target: TargetFight,
    event_cache: dict[str, list[BFOFight]],
    tolerance_days: int,
) -> BFOFight | None:
    cached_match = match_cached_event_fight(event_cache, target)
    if cached_match and cached_match.fighter1_odds is not None and cached_match.fighter2_odds is not None:
        return cached_match

    queries = [
        f"{target.red_fighter} {target.blue_fighter}",
        f"{target.blue_fighter} {target.red_fighter}",
    ]
    if target.title:
        queries.append(event_query_from_slug(target.title))

    seen_queries: set[str] = set()
    for query in queries:
        if not query or query in seen_queries:
            continue
        seen_queries.add(query)
        for event_url in client.suggest_event_urls(query):
            event_fights = event_cache.get(event_url)
            if event_fights is None:
                event_fights = client.parse_event(event_url, target.event_date)
                event_cache[event_url] = event_fights
            event_match = match_bfo_fight(event_fights, target)
            if event_match and event_match.fighter1_odds is not None and event_match.fighter2_odds is not None:
                return event_match

    history_matches: list[BFOFight] = []
    for fighter, opponent in [
        (target.red_fighter, target.blue_fighter),
        (target.blue_fighter, target.red_fighter),
    ]:
        history_matches.extend(
            client.fighter_history_matches(
                fighter,
                opponent,
                target.event_date,
                tolerance_days,
            )
        )
        if history_matches:
            break

    for history_match in history_matches:
        event_fights = event_cache.get(history_match.event_url)
        if event_fights is None:
            event_fights = client.parse_event(history_match.event_url, history_match.event_date)
            event_cache[history_match.event_url] = event_fights

        event_match = match_bfo_fight(event_fights, target)
        if event_match and event_match.fighter1_odds is not None and event_match.fighter2_odds is not None:
            return event_match

    for history_match in history_matches:
        if history_match.fighter1_odds is not None and history_match.fighter2_odds is not None:
            return history_match

    return None


def match_cached_event_fight(
    event_cache: dict[str, list[BFOFight]],
    target: TargetFight,
) -> BFOFight | None:
    for event_fights in event_cache.values():
        event_match = match_bfo_fight(event_fights, target)
        if event_match and (
            event_match.event_date is None
            or dates_close(event_match.event_date, target.event_date, tolerance_days=1)
        ):
            return event_match
    return None


def match_bfo_fight(fights: list[BFOFight], target: TargetFight) -> BFOFight | None:
    for fight in fights:
        if pairs_match(
            target.red_fighter,
            target.blue_fighter,
            fight.fighter1_name,
            fight.fighter2_name,
        ):
            return fight
    return None


def to_local_order(target: TargetFight, fight: BFOFight) -> tuple[int | None, int | None]:
    red = normalize_name(target.red_fighter)
    blue = normalize_name(target.blue_fighter)

    if names_match(red, fight.fighter1_name) and names_match(blue, fight.fighter2_name):
        return fight.fighter1_odds, fight.fighter2_odds
    if names_match(red, fight.fighter2_name) and names_match(blue, fight.fighter1_name):
        return fight.fighter2_odds, fight.fighter1_odds
    return None, None


def merge_odds(
    existing: pd.DataFrame,
    targets: list[TargetFight],
    found: dict[tuple[date, frozenset[str]], BFOFight],
    replace_existing: bool,
) -> pd.DataFrame:
    rows_by_key: dict[tuple[date, frozenset[str]], dict[str, object]] = {}
    order: list[tuple[date, frozenset[str]]] = []

    for _, row in existing.iterrows():
        event_date = date_key(row.get("event_date"))
        if event_date is None:
            continue
        key = fight_key(event_date, row.get("fighter1_name", ""), row.get("fighter2_name", ""))
        if key not in rows_by_key:
            order.append(key)
            rows_by_key[key] = {column: row.get(column, "") for column in ODDS_COLUMNS}

    target_by_key = {fight_key(t.event_date, t.red_fighter, t.blue_fighter): t for t in targets}
    for key, bfo_fight in found.items():
        target = target_by_key[key]
        red_odds, blue_odds = to_local_order(target, bfo_fight)
        if red_odds is None or blue_odds is None:
            continue

        current = rows_by_key.get(key)
        if current is not None and not replace_existing:
            current_row = pd.Series(current)
            if has_usable_odds(current_row):
                continue

        new_row = {
            "event_name": slug_from_url(bfo_fight.event_url),
            "event_date": output_date(target.event_date),
            "fighter1_name": target.red_fighter,
            "fighter2_name": target.blue_fighter,
            "winner_name": target.winner_name,
            "fighter1_odds": american_odds_text(red_odds),
            "fighter2_odds": american_odds_text(blue_odds),
        }
        if key not in rows_by_key:
            order.append(key)
        rows_by_key[key] = new_row

    merged = pd.DataFrame([rows_by_key[key] for key in order], columns=ODDS_COLUMNS)
    merged["_sort_date"] = pd.to_datetime(merged["event_date"], format="mixed", errors="coerce")
    merged["_sort_event"] = merged["event_name"].astype(str)
    merged["_sort_f1"] = merged["fighter1_name"].astype(str)
    merged = merged.sort_values(["_sort_date", "_sort_event", "_sort_f1"], kind="stable")
    return merged.drop(columns=["_sort_date", "_sort_event", "_sort_f1"]).reset_index(drop=True)


def load_supplemental_odds(path: str | None) -> pd.DataFrame:
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=ODDS_COLUMNS)

    supplemental = pd.read_csv(path, dtype=str)
    for column in ODDS_COLUMNS:
        if column not in supplemental.columns:
            supplemental[column] = ""
    supplemental = supplemental[ODDS_COLUMNS].copy()
    return supplemental[supplemental.apply(has_usable_odds, axis=1)].reset_index(drop=True)


def apply_supplemental_odds(
    odds: pd.DataFrame,
    supplemental: pd.DataFrame,
    replace_existing: bool,
) -> tuple[pd.DataFrame, int]:
    if supplemental.empty:
        return odds, 0

    rows_by_key: dict[tuple[date, frozenset[str]], dict[str, object]] = {}
    order: list[tuple[date, frozenset[str]]] = []

    for _, row in odds.iterrows():
        event_date = date_key(row.get("event_date"))
        if event_date is None:
            continue
        key = fight_key(event_date, row.get("fighter1_name", ""), row.get("fighter2_name", ""))
        if key not in rows_by_key:
            order.append(key)
        rows_by_key[key] = {column: row.get(column, "") for column in ODDS_COLUMNS}

    applied = 0
    for _, row in supplemental.iterrows():
        event_date = date_key(row.get("event_date"))
        if event_date is None:
            continue
        key = fight_key(event_date, row.get("fighter1_name", ""), row.get("fighter2_name", ""))
        current = rows_by_key.get(key)
        if current is not None and has_usable_odds(pd.Series(current)) and not replace_existing:
            continue

        if key not in rows_by_key:
            order.append(key)
        rows_by_key[key] = {column: row.get(column, "") for column in ODDS_COLUMNS}
        applied += 1

    merged = pd.DataFrame([rows_by_key[key] for key in order], columns=ODDS_COLUMNS)
    merged["_sort_date"] = pd.to_datetime(merged["event_date"], format="mixed", errors="coerce")
    merged["_sort_event"] = merged["event_name"].astype(str)
    merged["_sort_f1"] = merged["fighter1_name"].astype(str)
    merged = merged.sort_values(["_sort_date", "_sort_event", "_sort_f1"], kind="stable")
    return merged.drop(columns=["_sort_date", "_sort_event", "_sort_f1"]).reset_index(drop=True), applied


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")


def run(args) -> dict[str, object]:
    targets = load_targets(args)
    if args.limit:
        targets = targets[: args.limit]

    client = BFOClient(
        cache_dir=Path(args.cache_dir),
        refresh_cache=args.refresh_cache,
        sleep_seconds=args.sleep,
        timeout=args.timeout,
    )

    event_cache: dict[str, list[BFOFight]] = {}
    found: dict[tuple[date, frozenset[str]], BFOFight] = {}
    missed: list[dict[str, object]] = []

    for index, target in enumerate(targets, start=1):
        key = fight_key(target.event_date, target.red_fighter, target.blue_fighter)
        label = f"{target.event_date} {target.red_fighter} vs {target.blue_fighter}"
        print(f"[{index}/{len(targets)}] {label}")

        match = find_bfo_fight(
            client,
            target,
            event_cache=event_cache,
            tolerance_days=args.date_tolerance_days,
        )
        if match is None:
            print("  no BFO match")
            missed.append(
                {
                    "event_date": target.event_date.isoformat(),
                    "red_fighter": target.red_fighter,
                    "blue_fighter": target.blue_fighter,
                    "target_source": target.source,
                    "reason": "no BFO match",
                }
            )
            continue

        red_odds, blue_odds = to_local_order(target, match)
        if red_odds is None or blue_odds is None:
            print("  matched, but odds could not be aligned")
            missed.append(
                {
                    "event_date": target.event_date.isoformat(),
                    "red_fighter": target.red_fighter,
                    "blue_fighter": target.blue_fighter,
                    "target_source": target.source,
                    "reason": "matched odds could not be aligned",
                    "event_url": match.event_url,
                }
            )
            continue

        print(
            "  "
            f"{american_odds_text(red_odds)} / {american_odds_text(blue_odds)} "
            f"from {match.source} {match.event_url}"
        )
        found[key] = match

    if missed and event_cache:
        print("\nSecond pass: checking missed fights against already discovered event pages")
        still_missed: list[dict[str, object]] = []
        for item in missed:
            target = TargetFight(
                event_date=datetime.strptime(str(item["event_date"]), "%Y-%m-%d").date(),
                red_fighter=str(item["red_fighter"]),
                blue_fighter=str(item["blue_fighter"]),
                winner_name=next(
                    (
                        target.winner_name
                        for target in targets
                        if target.event_date.isoformat() == item["event_date"]
                        and target.red_fighter == item["red_fighter"]
                        and target.blue_fighter == item["blue_fighter"]
                    ),
                    "",
                ),
                title="",
                source=str(item.get("target_source", "unknown")),
            )
            key = fight_key(target.event_date, target.red_fighter, target.blue_fighter)
            match = match_cached_event_fight(event_cache, target)
            if match and match.fighter1_odds is not None and match.fighter2_odds is not None:
                red_odds, blue_odds = to_local_order(target, match)
                if red_odds is not None and blue_odds is not None:
                    print(
                        "  recovered "
                        f"{target.event_date} {target.red_fighter} vs {target.blue_fighter}: "
                        f"{american_odds_text(red_odds)} / {american_odds_text(blue_odds)}"
                    )
                    found[key] = match
                    continue
            still_missed.append(item)
        missed = still_missed

    existing = load_existing_odds(args.odds)
    merged = merge_odds(existing, targets, found, replace_existing=args.replace_existing)
    supplemental = load_supplemental_odds(args.supplemental_odds)
    merged, supplemental_applied = apply_supplemental_odds(
        merged,
        supplemental,
        replace_existing=args.replace_existing,
    )
    merged_index = build_existing_odds_index(merged)
    missed_after_supplemental = []
    for item in missed:
        event_date = datetime.strptime(str(item["event_date"]), "%Y-%m-%d").date()
        key = fight_key(event_date, str(item["red_fighter"]), str(item["blue_fighter"]))
        merged_row = merged_index.get(key)
        if merged_row is None or not has_usable_odds(merged_row):
            missed_after_supplemental.append(item)

    if not args.dry_run:
        output_path = Path(args.output or args.odds)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(output_path, index=False)

    report = {
        "features": args.features,
        "odds": args.odds,
        "output": args.output or args.odds,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "targets": len(targets),
        "target_sources": {
            source: sum(1 for target in targets if target.source == source)
            for source in sorted({target.source for target in targets})
        },
        "found": len(found),
        "bfo_missed": len(missed),
        "missed": len(missed_after_supplemental),
        "dry_run": args.dry_run,
        "replace_existing": args.replace_existing,
        "supplemental_odds": args.supplemental_odds,
        "supplemental_rows": len(supplemental),
        "supplemental_applied": supplemental_applied,
        "event_pages_parsed": len(event_cache),
        "bfo_missed_fights": missed,
        "missed_fights": missed_after_supplemental,
        "sources": sorted({fight.source for fight in found.values()}),
    }

    if args.report:
        write_report(Path(args.report), report)

    print("\n" + "=" * 70)
    print(f"Targets needing odds: {len(targets)}")
    print(f"Found odds: {len(found)}")
    print(f"Supplemental odds applied: {supplemental_applied}")
    print(f"Still missing: {len(missed_after_supplemental)}")
    if not args.dry_run:
        print(f"Wrote odds: {args.output or args.odds}")
    if args.report:
        print(f"Wrote report: {args.report}")
    print("=" * 70)

    return report


def parse_args() -> argparse.Namespace:
    today = datetime.now().date()
    start = today - timedelta(days=365)
    parser = argparse.ArgumentParser(description="Backfill missing fight odds from BestFightOdds.")
    parser.add_argument("--features", default=os.path.join("data", "detailed_fights.csv"))
    parser.add_argument("--odds", default=os.path.join("data", "fight_results_with_odds.csv"))
    parser.add_argument("--output", default=None, help="defaults to overwriting --odds")
    parser.add_argument("--report", default=os.path.join("data", "bestfightodds_backfill_report.json"))
    parser.add_argument("--supplemental-odds", default=os.path.join("data", "supplemental_fight_odds.csv"))
    parser.add_argument("--start-date", default=start.isoformat())
    parser.add_argument("--end-date", default=today.isoformat())
    parser.add_argument("--cache-dir", default=os.path.join(".cache", "bestfightodds"))
    parser.add_argument("--date-tolerance-days", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=0, help="limit targets for smoke tests")
    parser.add_argument(
        "--skip-odds-csv-targets",
        action="store_true",
        help="only backfill model feature rows; do not repair dash rows already in the odds CSV",
    )
    parser.add_argument("--replace-existing", action="store_true", help="replace usable existing odds too")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
