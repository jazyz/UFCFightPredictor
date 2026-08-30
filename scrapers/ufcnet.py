"""HTTP session for ufcstats.com.

The site fronts every page with a JavaScript proof-of-work interstitial: it
serves a stub page containing a nonce, the client must find n such that
sha256(f"{nonce}:{n}") starts with a run of zeros, POST that to /__c, and
retry. A plain requests.get() therefore returns a page with none of the
expected markup, which is how the old scraper silently reported "0 new fights"
for two and a half years.

Anything that parses a page fetched through here should still treat "zero rows
found" as an error, never as "nothing new" — see ScrapeError.
"""
import hashlib
import re
import time

import requests

BASE = "http://ufcstats.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CHALLENGE = re.compile(r'var nonce="([0-9a-f]+)",\s*target=new Array\((\d+)\+1\)')

DEFAULT_DELAY = 0.35


class ScrapeError(RuntimeError):
    """Raised when a page cannot be fetched, or parses to nothing unexpectedly."""


def _solve(nonce, zeros):
    target = "0" * zeros
    n = 0
    while not hashlib.sha256(f"{nonce}:{n}".encode()).hexdigest().startswith(target):
        n += 1
    return n


def new_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def get(session, url, delay=DEFAULT_DELAY, tries=4):
    """GET url, clearing the proof-of-work interstitial as needed.

    Returns the page HTML. Raises ScrapeError if it never gets a real page.
    """
    last = None
    for attempt in range(tries):
        time.sleep(delay)
        try:
            r = session.get(url, timeout=45)
        except requests.RequestException as exc:
            last = str(exc)
            time.sleep(2 * (attempt + 1))
            continue

        if r.status_code != 200:
            last = f"HTTP {r.status_code}"
            time.sleep(2 * (attempt + 1))
            continue

        m = CHALLENGE.search(r.text)
        if m is None:
            return r.text

        # Pay the toll, then loop round and re-request.
        nonce, zeros = m.group(1), int(m.group(2))
        session.post(f"{BASE}/__c",
                     data={"nonce": nonce, "n": _solve(nonce, zeros)},
                     headers={"Content-Type": "application/x-www-form-urlencoded",
                              "Referer": url},
                     timeout=45)
        last = "proof-of-work challenge"

    raise ScrapeError(f"could not fetch {url} after {tries} tries (last: {last})")
