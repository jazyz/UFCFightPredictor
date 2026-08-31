"""Backfill data/fight_results_with_odds.csv with Kalshi (fallback FanDuel) closing odds.

Source: fightodds.io's GraphQL API (https://api.fightodds.io/gql), the same backend the
site's React frontend calls. Using the API rather than clicking through the rendered
pages gives us the per-sportsbook odds *history* with timestamps, which the HTML does not
expose and which we need to avoid lookahead (see pick_quote).

Odds selection, per fight:
  1. Kalshi, if it quoted both sides before the event started.
  2. Otherwise FanDuel.
Kalshi has no UFC coverage before 2026, so FanDuel carries most of the backfill.
"""
import argparse
import csv
import datetime as dt
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

GQL = "https://api.fightodds.io/gql"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://fightodds.io",
    "Referer": "https://fightodds.io/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
BOOK_PRIORITY = ["kalshi", "fanduel"]

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ODDS_CSV = os.path.join(DATA, "fight_results_with_odds.csv")
META_CSV = os.path.join(DATA, "fight_results_with_odds_meta.csv")
FIGHTS_CSV = os.path.join(DATA, "modified_fight_details.csv")
FIELDS = ["event_name", "event_date", "fighter1_name", "fighter2_name",
          "winner_name", "fighter1_odds", "fighter2_odds"]


class ScrapeError(RuntimeError):
    pass


def gql(query, variables, tries=4):
    body = json.dumps({"query": query, "variables": variables}).encode()
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(GQL, data=body, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = json.load(r)
            if "errors" in payload:
                raise ScrapeError(f"GraphQL errors: {json.dumps(payload['errors'])[:400]}")
            return payload["data"]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 * (i + 1))
    raise ScrapeError(f"request failed after {tries} tries: {last}")


EVENTS_Q = """
query($p:String,$first:Int,$after:String,$orderBy:String,$dateGte:Date,$dateLt:Date){
  promotion:promotionBySlug(slug:$p){
    events(first:$first,after:$after,date_Gte:$dateGte,date_Lt:$dateLt,orderBy:$orderBy){
      pageInfo{hasNextPage endCursor}
      edges{node{name pk slug date startTime isCancelled}}}}}
"""

OFFERS_Q = """
query($pk:Int!){
  eventOfferTable(pk:$pk){
    name pk slug
    fightOffers{edges{node{
      slug isCancelled
      fighter1{firstName lastName}
      fighter2{firstName lastName}
      straightOffers{edges{node{
        sportsbook{slug shortName}
        outcome1{odds oddsOutcome{edges{node{odds timestamp}}}}
        outcome2{odds oddsOutcome{edges{node{odds timestamp}}}}
      }}}
    }}}
  }}
"""


def list_events(date_gte, date_lt):
    out, after = [], None
    while True:
        d = gql(EVENTS_Q, {"p": "ufc", "first": 100, "after": after,
                           "orderBy": "date", "dateGte": date_gte, "dateLt": date_lt})
        conn = d["promotion"]["events"]
        out += [e["node"] for e in conn["edges"]]
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    if not out:
        raise ScrapeError(f"no UFC events returned for {date_gte}..{date_lt}")
    return out


def parse_ts(s):
    return dt.datetime.fromisoformat(s)


def pick_quote(outcome, cutoff):
    """Last quoted price strictly before the event started.

    The API's `odds` field is the most recent price it ever stored, which for a completed
    event is an in-play or post-settlement price -- FanDuel runs live markets during the
    card and Kalshi keeps trading to settlement. Backtesting on those would be betting
    with the answer in hand, so we walk the timestamped history instead and take the last
    point before `cutoff`.
    """
    if not outcome:
        return None
    hist = [e["node"] for e in (outcome.get("oddsOutcome") or {}).get("edges", [])]
    pre = [h for h in hist if h.get("odds") is not None and parse_ts(h["timestamp"]) < cutoff]
    if not pre:
        return None
    best = max(pre, key=lambda h: parse_ts(h["timestamp"]))
    return int(best["odds"]), best["timestamp"]


def american_to_prob(odds):
    return (-odds) / ((-odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)


def plausible(o1, o2):
    """Reject in-play leakage that slipped past the cutoff.

    A genuine two-way pre-fight market prices to an overround of roughly 1.00-1.15. A
    price that has started tracking a fight in progress blows past that.
    """
    s = american_to_prob(o1) + american_to_prob(o2)
    return 0.95 <= s <= 1.25 and max(abs(o1), abs(o2)) <= 2000


def norm(name):
    s = unicodedata.normalize("NFKD", (name or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() or c.isspace() else " " for c in s).split())


def name_key(name):
    return frozenset(norm(name).split())


def load_our_fights():
    """(date -> list of fights) from our own ufcstats-derived data.

    We take fighter names and the winner from here rather than from fightodds.io so the
    backfilled rows use the exact spellings the model was trained on -- that is what
    testing_time_period.py's get_ml() looks up.
    """
    by_date = {}
    with open(FIGHTS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("Date") or "").strip()
            if not raw:
                continue
            try:
                d = dt.datetime.strptime(raw, "%B %d, %Y").date()
            except ValueError:
                continue
            red, blue = (row.get("Red Fighter") or "").strip(), (row.get("Blue Fighter") or "").strip()
            if not red or not blue:
                continue
            draw = str(row.get("Draw", "")).strip().lower() == "true"
            winner = "draw/no contest" if draw else (row.get("Winner") or "").strip()
            by_date.setdefault(d, []).append(
                {"red": red, "blue": blue, "winner": winner,
                 "keys": {name_key(red), name_key(blue)}})
    return by_date


def name_sim(a, b):
    """Similarity between two fighter names, tolerant of the ways the two sources differ.

    fightodds.io and ufcstats disagree on given names ("Joe"/"Joseph" Pyfer), on
    transliteration ("Ihor Potieria"/"Igor Poteria"), and on name order for some fighters
    ("Aoriqileng"/"Qileng Aori"). Comparing sorted characters of the whole name absorbs
    reordering, while a token-level pass catches a shared surname.
    """
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    whole = difflib.SequenceMatcher(None, "".join(sorted(na.replace(" ", ""))),
                                    "".join(sorted(nb.replace(" ", "")))).ratio()
    ta, tb = na.split(), nb.split()
    best = 0.0
    for x in ta:
        for y in tb:
            if len(x) > 3 and len(y) > 3:
                best = max(best, difflib.SequenceMatcher(None, x, y).ratio())
    return max(whole, 0.5 * whole + 0.5 * best)


def match_fight(f1, f2, candidates):
    """Match a fightodds pairing to one of our fights on the same date.

    Matching is done on the pair rather than on either name alone: a wrong name is far
    less likely to survive when both corners have to agree. We take the best-scoring
    candidate and require both a strong absolute score and a clear margin over the
    runner-up, so an ambiguous card never silently attaches odds to the wrong bout.
    """
    if not candidates:
        return None
    scored = []
    for c in candidates:
        direct = min(name_sim(f1, c["red"]), name_sim(f2, c["blue"]))
        swapped = min(name_sim(f1, c["blue"]), name_sim(f2, c["red"]))
        scored.append((max(direct, swapped), c))
    scored.sort(key=lambda t: t[0], reverse=True)
    best, runner = scored[0][0], (scored[1][0] if len(scored) > 1 else 0.0)
    if best >= 0.78 and best - runner >= 0.08:
        return scored[0][1]
    return None


def event_slug(name, date):
    """ufc.com-style slug, matching the convention already in the CSV.

    Only a number immediately after "UFC" is the event number: "UFC 297: ..." is ufc-297,
    but the trailing 2 in "UFC Fight Night: Ankalaev vs. Walker 2" marks a rematch, and a
    numbered Fight Night ("UFC Fight Night 285") is still slugged by date, the way the
    existing rows are.
    """
    low = (name or "").lower()
    m = re.match(r"ufc\s+(\d+)\b", low)
    if m and "fight night" not in low:
        return f"ufc-{m.group(1)}"
    return "ufc-fight-night-" + date.strftime("%B-%d-%Y").lower()


def collect_event(ev, our_fights, stats):
    date = dt.datetime.strptime(ev["date"], "%Y-%m-%d").date()
    cutoff = parse_ts(ev["startTime"]) if ev.get("startTime") else \
        dt.datetime.combine(date, dt.time(0, 0), dt.timezone.utc)

    table = gql(OFFERS_Q, {"pk": ev["pk"]})["eventOfferTable"]
    if not table:
        stats["events_no_table"] += 1
        return [], []

    candidates = our_fights.get(date, [])
    slug = event_slug(ev["name"], date)
    date_str = date.strftime("%b %d %Y")
    rows, meta = [], []

    for edge in table["fightOffers"]["edges"]:
        node = edge["node"]
        if node.get("isCancelled"):
            continue
        stats["fights_seen"] += 1
        f1 = f"{node['fighter1']['firstName']} {node['fighter1']['lastName']}".strip()
        f2 = f"{node['fighter2']['firstName']} {node['fighter2']['lastName']}".strip()

        books = {s["node"]["sportsbook"]["slug"]: s["node"]
                 for s in node["straightOffers"]["edges"]}

        chosen = None
        for book in BOOK_PRIORITY:
            off = books.get(book)
            if not off:
                continue
            q1 = pick_quote(off.get("outcome1"), cutoff)
            q2 = pick_quote(off.get("outcome2"), cutoff)
            if not q1 or not q2:
                stats[f"{book}_incomplete"] += 1
                continue
            if not plausible(q1[0], q2[0]):
                stats[f"{book}_implausible"] += 1
                continue
            chosen = (book, q1, q2)
            break

        if not chosen:
            stats["no_usable_odds"] += 1
            continue
        book, (o1, t1), (o2, t2) = chosen

        ours = match_fight(f1, f2, candidates)
        if not ours:
            stats["unmatched_fight"] += 1
            continue
        if ours["winner"] == "draw/no contest":
            stats["draw_or_nc"] += 1
            continue

        # Orient the row the way our own data does (red corner first) so the odds line up
        # with the fighter names the model is asked about.
        k1, red, blue = name_key(f1), name_key(ours["red"]), name_key(ours["blue"])
        f1_is_red = len(k1 & red) >= len(k1 & blue)
        n1, n2 = ours["red"], ours["blue"]
        a1, a2 = (o1, o2) if f1_is_red else (o2, o1)

        rows.append({"event_name": slug, "event_date": date_str,
                     "fighter1_name": n1, "fighter2_name": n2,
                     "winner_name": ours["winner"],
                     "fighter1_odds": f"{a1:+d}".replace("+-", "-"),
                     "fighter2_odds": f"{a2:+d}".replace("+-", "-")})
        meta.append({"event_name": slug, "event_date": date_str,
                     "fighter1_name": n1, "fighter2_name": n2,
                     "sportsbook": book, "cutoff_utc": cutoff.isoformat(),
                     "fighter1_quote_ts": t1, "fighter2_quote_ts": t2,
                     "kalshi_available": str("kalshi" in books).lower()})
        stats[f"used_{book}"] += 1

    stats["events_done"] += 1
    return rows, meta


def existing_keys():
    if not os.path.exists(ODDS_CSV):
        return set(), 0
    keys, n = set(), 0
    with open(ODDS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n += 1
            keys.add((row["event_date"], frozenset(
                (name_key(row["fighter1_name"]), name_key(row["fighter2_name"])))))
    return keys, n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-12-17", help="inclusive YYYY-MM-DD")
    ap.add_argument("--end", default=dt.date.today().isoformat(), help="inclusive YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    end_excl = (dt.date.fromisoformat(args.end) + dt.timedelta(days=1)).isoformat()
    print(f"Fetching UFC events {args.start} .. {args.end}")
    events = [e for e in list_events(args.start, end_excl) if not e.get("isCancelled")]
    print(f"  {len(events)} events")

    our_fights = load_our_fights()
    print(f"  {sum(len(v) for v in our_fights.values())} fights in our own data for matching")

    seen, before = existing_keys()
    stats = {k: 0 for k in ("events_done", "events_no_table", "fights_seen", "used_kalshi",
                            "used_fanduel", "kalshi_incomplete", "fanduel_incomplete",
                            "kalshi_implausible", "fanduel_implausible", "no_usable_odds",
                            "unmatched_fight", "draw_or_nc", "duplicate")}
    all_rows, all_meta = [], []
    for i, ev in enumerate(events, 1):
        rows, meta = collect_event(ev, our_fights, stats)
        kept_rows, kept_meta = [], []
        for r, m in zip(rows, meta):
            key = (r["event_date"], frozenset((name_key(r["fighter1_name"]),
                                               name_key(r["fighter2_name"]))))
            if key in seen:
                stats["duplicate"] += 1
                continue
            seen.add(key)
            kept_rows.append(r)
            kept_meta.append(m)
        all_rows += kept_rows
        all_meta += kept_meta
        print(f"  [{i:3d}/{len(events)}] {ev['date']} {ev['name'][:48]:50s} +{len(kept_rows)}")

    print("\n--- summary ---")
    for k, v in stats.items():
        print(f"  {k:22s} {v}")
    print(f"  new rows              {len(all_rows)}")

    if args.dry_run:
        print("\ndry run: nothing written")
        return 0
    if not all_rows:
        raise ScrapeError("parsed 0 new rows -- treating as a failure, not 'up to date'")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(ODDS_CSV, "rb") as src, open(f"{ODDS_CSV}.bak-{stamp}", "wb") as dst:
        dst.write(src.read())
    with open(ODDS_CSV, "a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n").writerows(all_rows)

    meta_new = not os.path.exists(META_CSV)
    with open(META_CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_meta[0].keys()), lineterminator="\n")
        if meta_new:
            w.writeheader()
        w.writerows(all_meta)

    print(f"\nwrote {len(all_rows)} rows to {ODDS_CSV} ({before} -> {before + len(all_rows)})")
    print(f"provenance -> {META_CSV}")
    print(f"backup     -> {ODDS_CSV}.bak-{stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
