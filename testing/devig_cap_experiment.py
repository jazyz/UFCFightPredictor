# Experiment for roadmap items #1 and #2, measured on the tier-2 walk-forward:
#   #1  +200 longshot screen: skip any pick whose American odds exceed +200
#   #2  Shin / power de-vig replacing proportional de-vig at the root
# Pure replay over the cached tier-2 retrain predictions — no training happens
# here; a retrain date missing from the cache is an error, never a retrain.
# Decisions route through the real betting_math.decide_bet with only the devig
# function swapped, so pick/gate/Kelly semantics are exactly production's.
import csv
import math
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import betting_math
from scipy.optimize import brentq

ODDS_CSV = os.path.join('data', 'fight_results_with_odds.csv')

WINDOWS = [
    ('OOS 2024-01 to 2026-07', '2024-01-01', '2026-07-19',
     os.path.join('test_results', '.tier2_oos2024_cache')),
    ('last-year 2025-08 to 2026-08', '2025-08-30', '2026-08-30',
     os.path.join('test_results', '.tier2_lastyear_cache')),
]

# ---------------------------------------------------------------- de-vig methods

_ORIG_DEVIG = betting_math.devig  # replay patches betting_math.devig; keep the real one

def devig_proportional(pi1, pi2):
    return _ORIG_DEVIG(pi1, pi2)

def devig_power(pi1, pi2):
    # p_i = pi_i^k with k solved so the probabilities sum to 1
    if pi1 + pi2 <= 1:
        return _ORIG_DEVIG(pi1, pi2)
    k = brentq(lambda k: pi1 ** k + pi2 ** k - 1, 1.0, 50.0, xtol=1e-13)
    return pi1 ** k, pi2 ** k

def devig_shin(pi1, pi2):
    # Shin (1992): insider-trading share z solved so the implied probs sum to 1
    B = pi1 + pi2
    if B <= 1:
        return _ORIG_DEVIG(pi1, pi2)
    def p(z, pi):
        return (math.sqrt(z * z + 4 * (1 - z) * pi * pi / B) - z) / (2 * (1 - z))
    f = lambda z: p(z, pi1) + p(z, pi2) - 1
    if f(0.9999) >= 0:                      # no root: degenerate line
        return _ORIG_DEVIG(pi1, pi2)
    z = brentq(f, 0.0, 0.9999, xtol=1e-14)
    return p(z, pi1), p(z, pi2)

DEVIGS = {'prop': devig_proportional, 'shin': devig_shin, 'power': devig_power}

# ---------------------------------------------------------------- replay engine

def load_preds(path):
    preds = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            prob = float(row['Probability'])
            if row['Predicted Result'] != 'win':
                prob = 1 - prob
            preds[(row['Red Fighter'], row['Blue Fighter'])] = prob
    return preds

def load_rows():
    with open(ODDS_CSV, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row['_date'] = datetime.strptime(row['event_date'], '%b %d %Y')
    return rows

ROWS = load_rows()

def cache_file(cache_dir, date):
    path = os.path.join(cache_dir, f"pred_{date.strftime('%Y-%m-%d')}.csv")
    if not os.path.exists(path):
        raise RuntimeError(f'retrain {date:%Y-%m-%d} missing from {cache_dir}')
    return path

def replay(start, end, cache_dir, devig_name, max_dog_odds, min_edge,
           fraction=0.05, cap=0.05, blend_w=0.8):
    start_d = datetime.strptime(start, '%Y-%m-%d')
    end_d = datetime.strptime(end, '%Y-%m-%d')
    last_train = start_d
    preds = load_preds(cache_file(cache_dir, start_d))
    bankroll, bets, banks, capped = 1000.0, [], [1000.0], []
    orig_devig = betting_math.devig
    betting_math.devig = DEVIGS[devig_name]
    try:
        for row in ROWS:
            d = row['_date']
            if not (start_d <= d <= end_d):
                continue
            if d >= last_train + timedelta(days=182) and d < end_d:
                last_train = d
                preds = load_preds(cache_file(cache_dir, d))
            o1 = row['fighter1_odds'].replace('−', '-')
            o2 = row['fighter2_odds'].replace('−', '-')
            f1, f2 = row['fighter1_name'], row['fighter2_name']
            m1, m2 = preds.get((f1, f2)), preds.get((f2, f1))
            if m1 is None or m2 is None or o1 == '-' or o2 == '-':
                continue
            o1, o2 = int(o1), int(o2)
            model_a = (m1 + (1 - m2)) / 2
            # the experiment applies its own cap below; disable decide_bet's default so cap_odds=None is truly uncapped
            bet = betting_math.decide_bet(model_a, None, o1, o2, blend_w=blend_w,
                                          min_edge=min_edge, fraction=fraction,
                                          cap=cap, bankroll=bankroll, max_dog_odds=None)
            if bet is None:
                banks.append(bankroll)
                continue
            odds = o1 if bet['side'] == 1 else o2
            name = f1 if bet['side'] == 1 else f2
            if max_dog_odds is not None and odds > max_dog_odds:
                capped.append(dict(date=d, name=name, odds=odds, edge=bet['edge']))
                banks.append(bankroll)
                continue
            stake = bet['stake']
            winner = row['winner_name']
            if winner == name:
                ret = stake * (100 / -odds if odds < 0 else odds / 100)
            elif winner == 'draw/no contest':
                ret = 0.0
            else:
                ret = -stake
            bets.append(dict(date=d, name=name, odds=odds, prob=bet['prob'],
                             market=bet['market_prob'], edge=bet['edge'],
                             stake=stake, ret=ret, bank_before=bankroll,
                             win=winner == name))
            bankroll += ret
            banks.append(bankroll)
    finally:
        betting_math.devig = orig_devig
    return dict(final=bankroll, bets=bets, banks=banks, capped=capped,
                start=start_d, end=end_d)

# ---------------------------------------------------------------- metrics

def max_dd(banks):
    peak, worst = banks[0], 0.0
    for x in banks:
        peak = max(peak, x)
        worst = max(worst, (peak - x) / peak if peak else 0)
    return worst * 100

def compound(bets):
    m = 1.0
    for b in bets:
        m *= (b['bank_before'] + b['ret']) / b['bank_before']
    return (m - 1) * 100

def summary(res):
    bets = res['bets']
    n = len(bets)
    hit = 100 * sum(b['win'] for b in bets) / n if n else 0
    roi = 100 * sum(b['ret'] / b['stake'] for b in bets) / n if n else 0
    mid = res['start'] + (res['end'] - res['start']) / 2
    h1 = compound([b for b in bets if b['date'] < mid])
    h2 = compound([b for b in bets if b['date'] >= mid])
    return dict(final=res['final'], profit=(res['final'] - 1000) / 10, n=n,
                hit=hit, roi=roi, dd=max_dd(res['banks']), h1=h1, h2=h2,
                ncap=len(res['capped']))

def subset_line(bets, label):
    n = len(bets)
    if not n:
        return f'    {label:24s} 0 bets'
    hit = 100 * sum(b['win'] for b in bets) / n
    roi = 100 * sum(b['ret'] / b['stake'] for b in bets) / n
    pnl = sum(b['ret'] for b in bets)
    return (f'    {label:24s} {n:3d} bets  hit {hit:5.1f}%  ROI/bet {roi:+6.1f}%'
            f'  P&L ${pnl:+8.2f}')

# ---------------------------------------------------------------- validation

def validate_against_ttp():
    """The replay must reproduce testing_time_period.py to the cent."""
    import shutil
    sys.path.insert(0, 'testing')
    import testing_time_period as ttp

    def cached_train(date):
        src = os.path.join(WINDOWS[0][3], f'pred_{date}.csv')
        if not os.path.exists(src):
            raise RuntimeError(f'validation retrain {date} missing from cache')
        shutil.copy(src, os.path.join('data', 'predicted_results.csv'))

    ttp.train_ml = cached_train
    name, start, end, cache = WINDOWS[0]
    ttp.process_dates(start, end, strategy=[0.05, 0.05, 0, 0.05, 0.8])
    mine = replay(start, end, cache, 'prop', None, 0.05)
    n_mine = len(mine['bets'])
    n_ttp = ttp.favourites + ttp.underdogs
    assert abs(ttp.bankroll - mine['final']) < 1e-6, (ttp.bankroll, mine['final'])
    assert n_ttp == n_mine, (n_ttp, n_mine)
    print(f'validation vs testing_time_period.py: OK '
          f'(final ${mine["final"]:.2f}, {n_mine} bets)\n')

# ---------------------------------------------------------------- run

if __name__ == '__main__':
    # de-vig sanity: a lopsided -400/+300 line
    pi1, pi2 = betting_math.american_to_prob(-400), betting_math.american_to_prob(300)
    for nm, fn in DEVIGS.items():
        a, b = fn(pi1, pi2)
        assert abs(a + b - 1) < 1e-9
        print(f'devig sanity -400/+300  {nm:6s} fav {a:.4f}  dog {b:.4f}')
    print()

    validate_against_ttp()

    out = []
    for wname, start, end, cache in WINDOWS:
        for min_edge in (0.05, 0.04, 0.0):
            base_bets = None
            for devig_name in ('prop', 'shin', 'power'):
                for cap_odds in (None, 200):
                    res = replay(start, end, cache, devig_name, cap_odds, min_edge)
                    s = summary(res)
                    tag = f'{devig_name:5s} cap {"+200" if cap_odds else "none"}'
                    out.append((wname, min_edge, tag, s, res))
                    if devig_name == 'prop' and cap_odds is None:
                        base_bets = res['bets']
            # diagnostics: where the baseline's long-dog bets sit
            if base_bets is not None:
                dogs = [b for b in base_bets if b['odds'] > 0]
                d200 = [b for b in base_bets if b['odds'] >= 200]
                d200x = [b for b in base_bets if b['odds'] > 200]
                print(f'--- {wname}  edge {min_edge:.2f}  baseline segments ---')
                print(subset_line([b for b in base_bets if b['odds'] < 0], 'favourites'))
                print(subset_line(dogs, 'dogs (odds > 0)'))
                print(subset_line(d200, 'dogs >= +200'))
                print(subset_line(d200x, 'dogs > +200 (screened)'))
                print()

    hdr = (f'{"window":30s} {"edge":>4s} {"config":16s} {"final$":>8s} {"profit%":>8s}'
           f' {"bets":>5s} {"hit%":>6s} {"ROI/bet":>8s} {"maxDD%":>7s}'
           f' {"H1%":>7s} {"H2%":>7s} {"capped":>7s}')
    print(hdr)
    for wname, min_edge, tag, s, _ in out:
        print(f'{wname:30s} {min_edge:4.2f} {tag:16s} {s["final"]:8.2f} {s["profit"]:8.1f}'
              f' {s["n"]:5d} {s["hit"]:6.1f} {s["roi"]:+8.2f} {s["dd"]:7.1f}'
              f' {s["h1"]:+7.1f} {s["h2"]:+7.1f} {s["ncap"]:7d}')

    # decision-shift diagnostics: prop -> shin at the production edge
    print('\n--- decision shifts, prop -> shin, edge 0.05 ---')
    for wname, start, end, cache in WINDOWS:
        a = replay(start, end, cache, 'prop', None, 0.05)
        b = replay(start, end, cache, 'shin', None, 0.05)
        ka = {(x['date'], x['name']): x for x in a['bets']}
        kb = {(x['date'], x['name']): x for x in b['bets']}
        only_a, only_b = set(ka) - set(kb), set(kb) - set(ka)
        both = set(ka) & set(kb)
        d_edge = [kb[k]['edge'] - ka[k]['edge'] for k in both]
        print(f'{wname}: {len(only_a)} bets dropped, {len(only_b)} added, '
              f'{len(both)} shared (mean edge shift {sum(d_edge)/len(d_edge):+.4f})')
        for k in sorted(only_a):
            x = ka[k]
            print(f'  dropped: {x["date"]:%Y-%m-%d} {x["name"]:28s} {x["odds"]:+5d} '
                  f'edge {x["edge"]:.3f} {"WIN" if x["win"] else "loss"}')
        for k in sorted(only_b):
            x = kb[k]
            print(f'  added:   {x["date"]:%Y-%m-%d} {x["name"]:28s} {x["odds"]:+5d} '
                  f'edge {x["edge"]:.3f} {"WIN" if x["win"] else "loss"}')
