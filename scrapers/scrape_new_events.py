# Incremental scraper: adds UFC events newer than what data/fight_details_date.csv
# already contains, matching that file's exact 45-column schema. ufcstats.com now
# gates pages behind a SHA-256 proof-of-work browser check; solve_challenge()
# performs the same computation a browser does, then the session cookie persists.
# Polite ~1 req/sec rate limiting throughout.
import os
import re
import csv
import time
import hashlib
from datetime import datetime

import requests
from bs4 import BeautifulSoup

CSV_PATH = os.path.join('data', 'fight_details_date.csv')
EVENTS_URL = 'http://ufcstats.com/statistics/events/completed?page=all'
REQUEST_DELAY = 1.1  # seconds between requests

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'


def new_session():
    s = requests.Session()
    s.headers['User-Agent'] = UA
    return s


def _solve(nonce, zeros):
    target = '0' * zeros
    n = 0
    while not hashlib.sha256(f'{nonce}:{n}'.encode()).hexdigest().startswith(target):
        n += 1
    return n


def fetch(session, url, tries=4):
    """GET url, transparently passing the proof-of-work challenge if present."""
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException:
            time.sleep(REQUEST_DELAY * (attempt + 1))
            continue
        m = re.search(r'nonce="([0-9a-f]+)"', r.text)
        if m and 'Checking your browser' in r.text:
            zeros = int(re.search(r'new Array\((\d+)\+1\)', r.text).group(1))
            n = _solve(m.group(1), zeros)
            session.post('http://ufcstats.com/__c', data={'nonce': m.group(1), 'n': n}, timeout=30)
            time.sleep(REQUEST_DELAY)
            continue  # retry the GET now that the cookie is set
        return r
    return None


def merge_dicts(d1, d2):
    result = d1.copy()
    for key, value in d2.items():
        if key not in result:
            result[key] = value
    return result


def get_fight_details(session, url):
    r = fetch(session, url)
    if r is None or r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    try:
        fight_info = {'Title': soup.find('i', class_='b-fight-details__fight-title').get_text(strip=True)}
        content = soup.find('div', class_='b-fight-details__content')
        for detail in content.find_all('p', class_='b-fight-details__text'):
            for item in detail.find_all('i'):
                label = item.find('i', class_='b-fight-details__label')
                if label:
                    label_text = label.get_text(strip=True).rstrip(':')
                    value = item.get_text(strip=True).replace(label_text + ':', '').strip()
                    fight_info[label_text] = value

        winner = loser = None
        draw = False
        for fighter in soup.find_all('div', class_='b-fight-details__person'):
            status = fighter.find('i', class_='b-fight-details__person-status').get_text().strip()
            name = fighter.find('h3', class_='b-fight-details__person-name').get_text().strip()
            if status == 'W':
                winner = name
            elif status == 'L':
                loser = name
            elif status == 'D':
                draw = True

        f1_stats, f2_stats = {}, {}
        for table_body in soup.find_all('tbody', class_='b-fight-details__table-body'):
            headers = [th.get_text(strip=True) for th in table_body.find_previous('thead').find_all('th')]
            f1_data, f2_data = [], []
            for row in table_body.find_all('tr', class_='b-fight-details__table-row'):
                for cell in row.find_all('td', class_='b-fight-details__table-col'):
                    ps = cell.find_all('p', class_='b-fight-details__table-text')
                    f1_data.append(ps[0].get_text(strip=True) if ps else '')
                    f2_data.append(ps[1].get_text(strip=True) if len(ps) > 1 else '')
            f1_stats = merge_dicts(f1_stats, dict(zip(headers, f1_data)))
            f2_stats = merge_dicts(f2_stats, dict(zip(headers, f2_data)))
    except AttributeError:
        return None  # unexpected page layout (e.g. event with no stats yet)

    return {'Winner': winner, 'Loser': loser, 'Draw': draw,
            'Fight Info': fight_info, 'Fighter 1 Stats': f1_stats, 'Fighter 2 Stats': f2_stats}


def get_event_fight_links(session, event_url):
    r = fetch(session, event_url)
    if r is None or r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, 'html.parser')
    seen, links = set(), []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'fight-details' in href and href not in seen:
            seen.add(href)
            links.append(href)
    return links


def build_row(fight_details, event_date, columns):
    fi = fight_details['Fight Info']
    row = {
        'Title': fi.get('Title', ''),
        'Winner': fight_details.get('Winner', ''),
        'Loser': fight_details.get('Loser', ''),
        'Draw': fight_details.get('Draw', ''),
        'Method': fi.get('Method', ''),
        'Round': fi.get('Round', ''),
        'Time': fi.get('Time', ''),
        'Time Format': fi.get('Time Format', ''),
        'Referee': fi.get('Referee', ''),
        'Details': fi.get('Details', ''),
        'Date': event_date,
    }
    for key, val in fight_details['Fighter 1 Stats'].items():
        row[f'Red {key}'] = val
    for key, val in fight_details['Fighter 2 Stats'].items():
        row[f'Blue {key}'] = val
    return {c: row.get(c, '') for c in columns}


def latest_existing_date():
    with open(CSV_PATH, newline='') as f:
        for row in csv.DictReader(f):
            return datetime.strptime(row['Date'], '%B %d, %Y')  # file is newest-first
    return None


def main():
    with open(CSV_PATH, newline='') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        existing_rows = list(reader)
    cutoff = datetime.strptime(existing_rows[0]['Date'], '%B %d, %Y')
    today = datetime.now()
    print(f'existing: {len(existing_rows)} fights, latest {cutoff.date()}')

    session = new_session()
    r = fetch(session, EVENTS_URL)
    soup = BeautifulSoup(r.text, 'html.parser')

    events = []  # (date, url, name), newest-first
    for tr in soup.find_all('tr', class_='b-statistics__table-row'):
        a = tr.find('a', href=True)
        span = tr.find('span', class_='b-statistics__date')
        if not a or not span:
            continue
        try:
            d = datetime.strptime(span.get_text(strip=True), '%B %d, %Y')
        except ValueError:
            continue
        if cutoff < d <= today:
            events.append((d, a['href'], a.get_text(strip=True)))

    print(f'new events to scrape: {len(events)}')
    new_rows = []
    for i, (d, url, name) in enumerate(events, 1):
        time.sleep(REQUEST_DELAY)
        fight_links = get_event_fight_links(session, url)
        date_str = d.strftime('%B %d, %Y')
        card_rows = 0
        for link in fight_links:
            time.sleep(REQUEST_DELAY)
            fd = get_fight_details(session, link)
            if fd is None:
                continue
            new_rows.append(build_row(fd, date_str, columns))
            card_rows += 1
        print(f'[{i}/{len(events)}] {d.date()} {name[:45]:45} +{card_rows} fights', flush=True)

    # file stays newest-first: new events (already newest-first) go on top
    with open(CSV_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(new_rows)
        writer.writerows(existing_rows)
    print(f'done: added {len(new_rows)} fights, total {len(new_rows) + len(existing_rows)}')


if __name__ == '__main__':
    main()
