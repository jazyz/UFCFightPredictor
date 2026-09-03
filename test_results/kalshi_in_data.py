import os, sys, math, numpy as np, pandas as pd
ROOT='/Users/alex.xu/Desktop/UFCFightPredictor'; WT=os.path.join(ROOT,'.claude/worktrees/tier2-model-upgrades')
os.chdir(ROOT); sys.path.insert(0,ROOT); import betting_math
sys.path.insert(0, os.path.join(WT,'testing')); import devig_cap_experiment as dce
m=pd.read_csv('data/fight_results_with_odds_meta.csv'); o=pd.read_csv('data/fight_results_with_odds.csv')
d=m.merge(o,on=['event_name','event_date','fighter1_name','fighter2_name'],how='inner'); print('merged',len(d))
def ap(x): x=int(str(x).replace('−','-')); return betting_math.american_to_prob(x)
d=d[(d.fighter1_odds!='-')&(d.fighter2_odds!='-')].copy()
d['p1']=d.fighter1_odds.map(ap); d['p2']=d.fighter2_odds.map(ap); d['hold']=(d.p1+d.p2-1)*100
d['fav']=d[['p1','p2']].max(axis=1)/(d.p1+d.p2)
d['dt']=pd.to_datetime(d.event_date,format='%b %d %Y')
for ts in ['fighter1_quote_ts','fighter2_quote_ts']: d[ts]=pd.to_datetime(d[ts],utc=True)
d['cut']=pd.to_datetime(d.cutoff_utc,utc=True)
d['stale_h']=((d.cut-d[['fighter1_quote_ts','fighter2_quote_ts']].min(axis=1)).dt.total_seconds()/3600)
print('\n=== hold (two-sided overround, %) by book — Kalshi quote spread proxy ===')
print(d.groupby('sportsbook').hold.describe()[['count','mean','25%','50%','75%']].round(2))
k=d[d.sportsbook=='kalshi']
print('\nKalshi rows by half-year:'); print(k.groupby(k.dt.dt.to_period('6M')).size())
print('kalshi_available flag by half-year (share of fights with a Kalshi quote):'); print(d.groupby(d.dt.dt.to_period('6M')).kalshi_available.mean().round(2))
print('\nKalshi hold by favourite-strength bucket:')
k=k.assign(b=pd.cut(k.fav,[0.5,0.6,0.7,0.8,1.0])); print(k.groupby('b',observed=True).hold.agg(['count','mean','median']).round(2))
print('\nquote staleness before cutoff (hours), by book:'); print(d.groupby('sportsbook').stale_h.describe()[['count','mean','50%','75%','max']].round(1))
# spread in cents implied by hold for a 2-outcome market ~ hold*100 split across both sides => each side ~hold/2 from mid
print(f"\nKalshi implied per-side distance from mid ≈ {k.hold.median()/2:.2f}¢ (median), i.e. a ~{k.hold.median():.1f}¢ wide book if quotes are the two asks")

print('\n=== exact (unrounded) taker fee 0.07·p(1−p), per contract, cents ===')
for p in [10,20,30,40,50,60,70,80,90]:
    f=7*p*(100-p)/10000; print(f"  {p:2d}¢ fee {f:.2f}¢ = {f/p*100:4.1f}% of stake; breakeven edge take-at-mid {f:.2f} pts, lift-ask(+1¢) {f+1:.2f} pts, maker(-1¢,0 fee) −1.00 pts")

print('\n=== how many of our 175 bets survive fees after shrinking claimed edge? ===')
res=dce.replay('2024-01-01','2026-07-19', os.path.join(WT,'test_results/.tier2_oos2024_cache'),'prop',None,0.05)
b=res['bets']; mkt=np.array([x['market'] for x in b]); cl=np.array([x['prob'] for x in b]); win=np.array([x['win'] for x in b],float)
fee=7*mkt*(1-mkt)   # exact per-contract fee in prob points (=cents)
for k_ in [1.0,0.6,0.5]:
    e=(cl-mkt)*k_*100
    for thr,label in [(fee+1,'take: fee + 1¢ half-spread'),(fee+0,'take at mid: fee only'),(-1+0*fee,'make −1¢: any positive shrunk edge')]:
        keep=e>=thr+0.0  # need shrunk edge >= cost
        # realized ROI of the kept set if executed at that cost
        cost=(mkt*100+(1 if 'half' in label else 0)+ (fee if 'take' in label else 0) - (1 if 'make' in label else 0))/100
        r=((win-cost)/cost)[keep].mean()*100 if keep.sum() else float('nan')
        print(f"  shrink k={k_:.1f}  {label:38s} kept {keep.sum():3d}/175  realized ROI on kept {r:+6.1f}%  hit {win[keep].mean()*100 if keep.sum() else 0:.0f}%")
