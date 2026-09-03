"""Is the backtest edge distinguishable from variance?

Pure replay over cached walk-forward predictions (same engine the cap experiment
validated to the cent against testing_time_period.py). For each bet set:
  - flat ROI/bet with t-test, iid bootstrap CI and cluster-by-card bootstrap CI
  - Monte Carlo under the null "de-vigged market prob is the truth"
  - z-test on picks beating the market probability (hit-rate signal, payout-free)
  - model-claimed EV vs realized
  - n needed to detect the observed effect at 80% power
"""
import os, sys, math
import numpy as np
from scipy import stats

ROOT = '/Users/alex.xu/Desktop/UFCFightPredictor'
WT = os.path.join(ROOT, '.claude/worktrees/tier2-model-upgrades')
os.chdir(ROOT)
sys.path.insert(0, ROOT)
import betting_math                      # main's copy (identical to worktree's)
sys.path.insert(0, os.path.join(WT, 'testing'))
import devig_cap_experiment as dce       # replay engine; reads data/ relative to cwd

rng = np.random.default_rng(0)
NSIM = 20000

def payout(odds):
    return 100 / -odds if odds < 0 else odds / 100

def analyse(label, res, flag=''):
    bets = res['bets']
    n = len(bets)
    if n == 0:
        print(f'{label}: no bets'); return
    r = np.array([b['ret'] / b['stake'] for b in bets])          # return per $1 staked
    f = np.array([b['stake'] / b['bank_before'] for b in bets])  # stake fraction
    win = np.array([b['win'] for b in bets], dtype=float)
    mkt = np.array([b['market'] for b in bets])
    mod = np.array([b['prob'] for b in bets])
    odds = np.array([b['odds'] for b in bets])
    pay = np.array([payout(o) for o in odds])
    dates = np.array([b['date'] for b in bets])

    mean, sd = r.mean(), r.std(ddof=1)
    se = sd / math.sqrt(n)
    t = mean / se
    p_t = 1 - stats.t.cdf(t, n - 1)

    # iid bootstrap on mean ROI/bet
    idx = rng.integers(0, n, size=(NSIM, n))
    boot = r[idx].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
    p_boot = (boot <= 0).mean()

    # cluster bootstrap by card (event date)
    udates = np.unique(dates)
    groups = [np.where(dates == d)[0] for d in udates]
    cl = np.empty(NSIM)
    for s in range(NSIM):
        pick = rng.integers(0, len(groups), size=len(groups))
        sel = np.concatenate([groups[g] for g in pick])
        cl[s] = r[sel].mean()
    cl_lo, cl_hi = np.percentile(cl, [2.5, 97.5])
    p_cl = (cl <= 0).mean()

    # null MC: market de-vigged prob is truth (same bets, same stakes, resimulated outcomes)
    u = rng.random((NSIM, n))
    sim_win = u < mkt
    sim_r = np.where(sim_win, pay, -1.0)
    null_roi = sim_r.mean(axis=1)
    null_final = 1000 * np.prod(1 + f * sim_r, axis=1)
    p_null_roi = (null_roi >= mean).mean()
    p_null_final = (null_final >= res['final']).mean()
    null_ev = (mkt * pay - (1 - mkt)).mean()

    # model-claimed EV per bet
    model_ev = (mod * pay - (1 - mod)).mean()

    # market-beat z-test: did picks win more often than the market said?
    z = (win - mkt).sum() / math.sqrt((mkt * (1 - mkt)).sum())
    p_z = 1 - stats.norm.cdf(z)

    # power: n needed to detect observed mean at alpha .05 one-sided, 80% power
    n_req = ((1.645 + 0.842) * sd / mean) ** 2 if mean > 0 else float('inf')

    dd = dce.max_dd(res['banks'])
    hit = win.mean() * 100
    print(f'\n=== {label} {flag}')
    print(f'  n={n}  hit={hit:.1f}%  final=${res["final"]:.2f}  maxDD={dd:.1f}%  '
          f'avg odds={odds.mean():+.0f}  dogs={int((odds>0).sum())}')
    print(f'  ROI/bet {mean*100:+.2f}%  sd {sd*100:.1f}%  SE {se*100:.1f}%  '
          f't={t:.2f}  p(one-sided)={p_t:.3f}')
    print(f'  95% CI ROI/bet  iid [{ci_lo*100:+.1f}%, {ci_hi*100:+.1f}%]  '
          f'by-card [{cl_lo*100:+.1f}%, {cl_hi*100:+.1f}%]   P(ROI<=0) iid {p_boot:.3f} / by-card {p_cl:.3f}')
    print(f'  null (market true): mean ROI {null_ev*100:+.2f}%  P(ROI>=obs)={p_null_roi:.3f}  '
          f'P(final>=obs)={p_null_final:.3f}  null final 95% [{np.percentile(null_final,2.5):.0f}, {np.percentile(null_final,97.5):.0f}]')
    print(f'  model-claimed EV/bet {model_ev*100:+.2f}%  vs realized {mean*100:+.2f}%   '
          f'market-beat z={z:.2f} p={p_z:.3f}  (wins {win.sum():.0f} vs market-expected {mkt.sum():.1f})')
    print(f'  n needed for 80% power at this effect size: {n_req:,.0f}')
    return dict(label=label, n=n, roi=mean, p_t=p_t, p_null=p_null_roi, p_z=p_z, ci=(cl_lo, cl_hi), n_req=n_req)

CFG = dict(devig_name='prop', min_edge=0.05)
T2_OOS = os.path.join(WT, 'test_results/.tier2_oos2024_cache')
T2_LY  = os.path.join(WT, 'test_results/.tier2_lastyear_cache')
T0_LY  = os.path.join(ROOT, 'test_results/.lastyear_tier0_cache')

runs = [
 ('tier-2 OOS 2024-01..2026-07, production cfg',      '2024-01-01','2026-07-19', T2_OOS, None, ''),
 ('tier-2 OOS 2024-01..2026-07, +200 cap',            '2024-01-01','2026-07-19', T2_OOS, 200,  '[cap chosen post-hoc on this data]'),
 ('tier-2 last-year 2025-08..2026-08, production cfg','2025-08-30','2026-08-30', T2_LY,  None, ''),
 ('tier-2 last-year 2025-08..2026-08, +200 cap',      '2025-08-30','2026-08-30', T2_LY,  200,  '[cap chosen post-hoc]'),
 ('tier-0 (main, deployed) last-year, production cfg','2025-08-30','2026-08-30', T0_LY,  None, ''),
]
out = []
for label, s, e, cache, cap, flag in runs:
    res = dce.replay(s, e, cache, 'prop', cap, 0.05)
    out.append(analyse(label, res, flag))

# favourites-only slice on the biggest sample
res = dce.replay('2024-01-01','2026-07-19', T2_OOS, 'prop', None, 0.05)
fav = dict(res); fav['bets'] = [b for b in res['bets'] if b['odds'] < 0]
fav['final'] = 1000 * np.prod([1 + b['stake']/b['bank_before'] * b['ret']/b['stake'] for b in fav['bets']])
fav['banks'] = [1000.0]
for b in fav['bets']:
    fav['banks'].append(fav['banks'][-1] * (1 + b['stake']/b['bank_before'] * b['ret']/b['stake']))
analyse('tier-2 OOS favourites only (odds<0)', fav, '[slice]')

# flat-stake random-pick benchmark: bet the market favourite in every odds-covered fight in window
print('\n=== reference: blindly backing the market favourite, flat stake, same window (tier-2 OOS coverage)')
rs = []
for row in dce.ROWS:
    d = row['_date']
    if not (res['start'] <= d <= res['end']): continue
    o1, o2 = row['fighter1_odds'].replace('−','-'), row['fighter2_odds'].replace('−','-')
    if o1 == '-' or o2 == '-': continue
    o1, o2 = int(o1), int(o2)
    side = 1 if o1 < o2 else 2
    name, o = (row['fighter1_name'], o1) if side == 1 else (row['fighter2_name'], o2)
    w = row['winner_name']
    if w == 'draw/no contest': continue
    rs.append(payout(o) if w == name else -1.0)
rs = np.array(rs)
print(f'  n={len(rs)}  ROI/bet {rs.mean()*100:+.2f}%  sd {rs.std(ddof=1)*100:.1f}%  hit {(rs>0).mean()*100:.1f}%')
