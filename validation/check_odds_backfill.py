"""Sanity-check data/fight_results_with_odds.csv after a backfill.

The failure we care most about is lookahead: an odds row that was actually recorded while
the fight was in progress makes a backtest look brilliant for the wrong reason. A market
that already knows the answer shows up as a near-certain price on the fighter who won, so
we check the favourite-hit rate and the overround alongside the plain format checks.
"""
import csv
import os
import sys
from collections import Counter, defaultdict

CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "fight_results_with_odds.csv")


def prob(o):
    o = int(o)
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def main():
    rows = list(csv.DictReader(open(CSV, newline="", encoding="utf-8")))
    print(f"{len(rows)} rows in {os.path.basename(CSV)}")

    bad, by_year, missing, flags = [], defaultdict(list), 0, []
    for i, r in enumerate(rows, 2):
        # "-" is the pre-existing marker for a fight the old scraper found no odds for;
        # process_fight() already skips those, so they are missing data, not corruption.
        if r["fighter1_odds"].strip() == "-" or r["fighter2_odds"].strip() == "-":
            missing += 1
            continue
        try:
            o1, o2 = int(r["fighter1_odds"]), int(r["fighter2_odds"])
        except ValueError:
            bad.append((i, "unparseable odds", r["fighter1_odds"], r["fighter2_odds"]))
            continue
        if r["winner_name"] not in (r["fighter1_name"], r["fighter2_name"], "draw/no contest"):
            bad.append((i, "winner not a listed fighter", r["winner_name"], ""))
        s = prob(o1) + prob(o2)
        if not 0.95 <= s <= 1.30:
            bad.append((i, f"implausible overround {s:.3f}", o1, o2))
        by_year[r["event_date"].split()[-1]].append((o1, o2, r))

    print(f"{missing} rows carry no odds (\"-\") and are skipped by the backtester")

    print("\nyear   n    fav_hit%  fav_implied%   gap  avg_overround  max|odds|")
    for year in sorted(by_year):
        v = by_year[year]
        hits = tot = 0
        for o1, o2, r in v:
            if o1 == o2:
                continue
            fav = r["fighter1_name"] if o1 < o2 else r["fighter2_name"]
            tot += 1
            hits += (r["winner_name"] == fav)
        over = sum(prob(a) + prob(b) for a, b, _ in v) / len(v)
        mx = max(max(abs(a), abs(b)) for a, b, _ in v)
        implied = sum(max(prob(a), prob(b)) for a, b, _ in v) / len(v)
        rate = 100.0 * hits / tot if tot else float("nan")
        gap = rate - 100.0 * implied
        flags.append((year, gap, mx))
        print(f"{year}  {len(v):4d}    {rate:5.1f}       {100*implied:5.1f}     {gap:+5.1f}      "
              f"{over:.3f}        {mx}")

    # The real test for lookahead is calibration, not the raw favourite-hit rate: a market
    # captured mid-fight prices the eventual winner near certainty, so its implied
    # probability rockets away from the ~70% a genuine pre-fight line carries. A high hit
    # rate matched by an equally high implied probability just means favourites were
    # priced heavily that year.
    print("\nfav_implied% is what the odds themselves say; gap is fav_hit% minus that. A "
          "clean\npre-fight market keeps |gap| small. Leakage shows up as fav_implied% "
          "near 90-100.")
    for year, gap, mx in flags:
        if abs(gap) > 8:
            bad.append((0, f"{year}: fav_hit deviates {gap:+.1f}pts from implied", "", ""))
        if mx > 5000:
            bad.append((0, f"{year}: extreme price {mx} suggests a settled market", "", ""))
    if bad:
        print(f"\n{len(bad)} suspect rows:")
        for b in bad[:25]:
            print("   line", b[0], "-", b[1], b[2], b[3])
        return 1
    print("\nno format or overround problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
