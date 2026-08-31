"""Run the Kelly betting strategy over the newly backfilled odds.

Joins the model's out-of-sample holdout predictions (data/predicted_results.csv, written
by ml_ensemble.py for the chronological last 5% of fights it never trained on) against the
odds backfilled from fightodds.io. Before the backfill those fights had no odds at all --
data/fight_results_with_odds.csv stopped at 2024-03-30 -- so this period could not be
bet-tested at any price.

Sizing follows the deployed defaults in CLAUDE.md: fractional Kelly at 5%, capped at 5% of
bankroll, and only where the model's edge over the market exceeds 5%.
"""
import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED = os.path.join(ROOT, "data", "predicted_results.csv")
ODDS = os.path.join(ROOT, "data", "fight_results_with_odds.csv")


def odds_to_prob(o):
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def kelly(odds, p):
    n = 100.0 / -odds if odds < 0 else odds / 100.0
    return (n * p - (1 - p)) / n


def payout(odds, bet):
    return bet * (100.0 / -odds) if odds < 0 else bet * (odds / 100.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--fraction", type=float, default=0.05)
    ap.add_argument("--cap", type=float, default=0.05)
    ap.add_argument("--min-edge", type=float, default=0.05)
    args = ap.parse_args()

    preds = {}
    for r in csv.DictReader(open(PRED, newline="", encoding="utf-8")):
        p = float(r["Probability"])
        # "Probability" is the confidence in the predicted label, so flip it when the
        # model picked the blue corner to get P(red wins).
        preds[(r["Red Fighter"], r["Blue Fighter"])] = p if r["Predicted Result"] == "win" else 1 - p

    # A rematch gives the same pair of names two rows years apart. The holdout is the
    # chronologically last slice of the data, so when a pair matches more than once we
    # keep the most recent bout rather than betting an old fight at the new fight's price.
    best = {}
    for r in csv.DictReader(open(ODDS, newline="", encoding="utf-8")):
        if r["fighter1_odds"].strip() == "-" or r["fighter2_odds"].strip() == "-":
            continue
        f1, f2 = r["fighter1_name"], r["fighter2_name"]
        if (f1, f2) in preds:
            p1 = preds[(f1, f2)]
        elif (f2, f1) in preds:
            p1 = 1 - preds[(f2, f1)]
        else:
            continue
        date = datetime.strptime(r["event_date"], "%b %d %Y")
        key = frozenset((f1, f2))
        if key not in best or date > best[key][0]:
            best[key] = (date, r, p1)
    joined = sorted(best.values(), key=lambda t: t[0])

    if not joined:
        print("no overlap between predicted_results.csv and the odds file")
        return 1

    bankroll = args.bankroll
    staked = returned = 0.0
    bets = wins = 0
    by_month = defaultdict(lambda: [0, 0.0])
    curve = []

    for date, r, p1 in joined:
        o1, o2 = int(r["fighter1_odds"]), int(r["fighter2_odds"])
        for name, odds, p in ((r["fighter1_name"], o1, p1), (r["fighter2_name"], o2, 1 - p1)):
            edge = p - odds_to_prob(odds)
            if edge <= args.min_edge:
                continue
            k = kelly(odds, p)
            if k <= 0:
                continue
            bet = min(bankroll * k * args.fraction, bankroll * args.cap)
            if bet <= 0:
                continue
            bets += 1
            staked += bet
            won = r["winner_name"] == name
            delta = payout(odds, bet) if won else -bet
            bankroll += delta
            returned += (bet + payout(odds, bet)) if won else 0.0
            wins += won
            m = date.strftime("%Y-%m")
            by_month[m][0] += 1
            by_month[m][1] += delta
        curve.append((date, bankroll))

    print(f"Fights with both a holdout prediction and odds: {len(joined)}")
    print(f"Period: {joined[0][0]:%Y-%m-%d} -> {joined[-1][0]:%Y-%m-%d}\n")
    print(f"Bets placed      {bets}")
    print(f"Bets won         {wins}" + (f"  ({100.0*wins/bets:.1f}%)" if bets else ""))
    print(f"Total staked     {staked:,.2f}")
    print(f"Net profit       {bankroll - args.bankroll:+,.2f}")
    if staked:
        print(f"ROI on stake     {100.0*(bankroll-args.bankroll)/staked:+.1f}%")
    print(f"Bankroll         {args.bankroll:,.2f} -> {bankroll:,.2f} "
          f"({100.0*(bankroll/args.bankroll-1):+.1f}%)")

    print("\nmonth      bets   P/L")
    for m in sorted(by_month):
        n, pl = by_month[m]
        print(f"{m}   {n:4d}   {pl:+9.2f}")
    peak = args.bankroll
    dd = 0.0
    for _, b in curve:
        peak = max(peak, b)
        dd = max(dd, (peak - b) / peak)
    print(f"\nMax drawdown     {100*dd:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
