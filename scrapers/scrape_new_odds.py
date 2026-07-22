# Incremental odds scraper. ufc.com event pages still expose betting odds but no
# longer expose winners, and their dates carry no year. So we take ONLY the odds
# (fighter pair + moneylines) from ufc.com and get the authoritative winner and
# date from the refreshed ufcstats data (fight_details_date.csv), matched by name.
# Upcoming fights and pre-2024 fights have no 2024+ ufcstats match and are skipped.
import os
import re
import csv
import time
import unicodedata

import requests
import pandas as pd
from bs4 import BeautifulSoup

ODDS_CSV = os.path.join('data', 'fight_results_with_odds.csv')
STATS_CSV = os.path.join('data', 'fight_details_date.csv')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'
REQUEST_DELAY = 1.1
LISTING_PAGES = 14  # covers ~2.5 years back at ~8-16 events/page
CUTOFF = pd.Timestamp('2024-01-01')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z ]', '', s.lower()).strip()


def pair_key(a, b):
    return frozenset((norm(a), norm(b)))


def build_stats_index():
    """unordered fighter-pair -> (winner, 'Mon DD YYYY'); 2024+ only, unique pairs."""
    df = pd.read_csv(STATS_CSV)
    df['d'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df[df['d'] >= CUTOFF]
    index, collisions = {}, 0
    for _, r in df.iterrows():
        k = pair_key(r['Red Fighter'], r['Blue Fighter'])
        if k in index:
            collisions += 1  # rematch within window; keep first, skip ambiguous
            continue
        winner = r['Winner'] if pd.notna(r['Winner']) and str(r['Winner']).strip() else 'draw/no contest'
        index[k] = (winner, r['d'].strftime('%b %d %Y'))
    print(f'stats index: {len(index)} unique 2024+ pairs ({collisions} rematch collisions skipped)')
    return index


def existing_keys():
    if not os.path.exists(ODDS_CSV):
        return set()
    df = pd.read_csv(ODDS_CSV)
    return {pair_key(r['fighter1_name'], r['fighter2_name']) for _, r in df.iterrows()}


def get(session, url):
    try:
        return session.get(url, timeout=30)
    except requests.RequestException:
        return None


def collect_event_slugs(session):
    slugs = []
    seen = set()
    for pg in range(LISTING_PAGES):
        r = get(session, f'https://www.ufc.com/events?page={pg}')
        time.sleep(REQUEST_DELAY)
        if r is None or r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, 'html.parser')
        for d in soup.find_all('div', class_='c-card-event--result__logo'):
            a = d.find('a')
            if a and a.get('href') and a['href'] not in seen:
                seen.add(a['href'])
                slugs.append(a['href'])
    return slugs


def scrape_event_fights(session, slug):
    """Return list of (name1, name2, odds1, odds2) from a ufc.com event page."""
    r = get(session, 'https://www.ufc.com' + slug)
    if r is None or r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, 'html.parser')

    names = []
    for nd in soup.find_all('div', {'class': 'c-listing-fight__corner-name'}):
        g = nd.find('span', class_='c-listing-fight__corner-given-name')
        f = nd.find('span', class_='c-listing-fight__corner-family-name')
        if g and f:
            names.append(f'{g.get_text(strip=True)} {f.get_text(strip=True)}')
        else:
            a = nd.find('a')
            names.append((a.get_text(strip=True) if a else nd.get_text(strip=True)) or '')

    wrappers = soup.find_all(class_='c-listing-fight__odds-wrapper')
    fights = []
    for i in range(0, len(names) - 1, 2):
        j = i // 2
        if j >= len(wrappers):
            break
        amounts = [e.get_text(strip=True).replace('−', '-')
                   for e in wrappers[j].find_all(class_='c-listing-fight__odds-amount')]
        if len(amounts) != 2:
            continue
        fights.append((names[i], names[i + 1], amounts[0], amounts[1]))
    return fights


def main():
    session = requests.Session()
    session.headers['User-Agent'] = UA

    index = build_stats_index()
    have = existing_keys()

    slugs = collect_event_slugs(session)
    print(f'collected {len(slugs)} event slugs from ufc.com')

    new_rows = []
    matched_pairs = set()
    for slug in slugs:
        time.sleep(REQUEST_DELAY)
        event = slug.rsplit('/', 1)[-1]
        for n1, n2, o1, o2 in scrape_event_fights(session, slug):
            k = pair_key(n1, n2)
            if k not in index or k in have or k in matched_pairs:
                continue
            winner, date_str = index[k]
            new_rows.append([event, date_str, n1, n2, winner, o1, o2])
            matched_pairs.add(k)
        print(f'  {event[:45]:45} matched so far: {len(new_rows)}', flush=True)

    with open(ODDS_CSV, 'a', newline='') as f:
        csv.writer(f).writerows(new_rows)
    print(f'appended {len(new_rows)} fights with odds to {ODDS_CSV}')


if __name__ == '__main__':
    main()
