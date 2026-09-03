"""Fee breakeven on Kalshi vs our realized edge, on the actual tier-2 OOS bet distribution.
Taker fee model: ceil_to_cent(COEF * p * (1-p)) per contract (COEF parameterized; verify 0.07).
Maker fee: MAKER_COEF (0 by default; some series charge 0.0175)."""
import os, sys, math
import numpy as np
ROOT='/Users/alex.xu/Desktop/UFCFightPredictor'; WT=os.path.join(ROOT,'.claude/worktrees/tier2-model-upgrades')
os.chdir(ROOT); sys.path.insert(0,ROOT); import betting_math
sys.path.insert(0, os.path.join(WT,'testing')); import devig_cap_experiment as dce
COEF=0.07; MAKER_COEF=0.0

def fee_cents(p, coef=COEF, n=1):
    # Kalshi rounds the fee up to the next cent (per order, on the total); for 1 contract that's per-contract
    return math.ceil(coef*n*p*(1-p)*100 - 1e-12)/n if coef>0 else 0.0

print("=== breakeven by price (buy YES at price p cents, hold to settlement) ===")
print(f"{'price':>5} {'takerfee¢':>9} {'fee%stake':>9} {'BE prob(take)':>13} {'edge needed(pts)':>16} {'+1¢ half-spread':>16} {'maker,0 fee,+1¢':>16}")
for p in [10,20,30,40,50,60,70,80,90]:
    pf=p/100; fee=fee_cents(pf)
    # taker: pay p + fee, win 100. breakeven prob q: q*100 = p+fee  -> q=(p+fee)/100
    be_take=(p+fee)/100
    be_take_spread=(p+1+fee)/100          # crossing a 2¢-wide book: fair mid is 1¢ below the ask you lift
    be_make=(p-1)/100                      # resting 1¢ below mid, filled, no fee
    print(f"{p:>5} {fee:>9.1f} {fee/p*100:>8.1f}% {be_take:>13.3f} {(be_take-pf)*100:>15.1f} {(be_take_spread-pf)*100:>15.1f} {(be_make-pf)*100:>15.1f}")

print("\n=== on our actual tier-2 OOS bets (price := de-vigged market prob of the pick, as a Kalshi-mid proxy) ===")
res=dce.replay('2024-01-01','2026-07-19', os.path.join(WT,'test_results/.tier2_oos2024_cache'),'prop',None,0.05)
bets=res['bets']; n=len(bets)
mkt=np.array([b['market'] for b in bets]); win=np.array([b['win'] for b in bets],float)
claimed=np.array([b['prob'] for b in bets]); odds=np.array([b['odds'] for b in bets])
fees=np.array([fee_cents(p) for p in mkt])      # cents per contract
price=mkt*100
print(f"n={n}  mean price {price.mean():.1f}¢  mean taker fee {fees.mean():.2f}¢ = {np.mean(fees/price)*100:.2f}% of stake, {fees.mean():.2f} prob-pts")
real_edge=(win.mean()-mkt.mean())*100
print(f"realized hit-rate edge {real_edge:.1f} pts vs claimed {((claimed-mkt).mean())*100:.1f} pts")
# ROI per $1 staked buying at mid vs at mid+1 vs at mid-1 with/without fee, using realized outcomes
def roi(px_cents, fee_c):
    cost=(px_cents+fee_c)/100                # $ per contract
    pay=win*1.0                              # $1 on win
    return ((pay-cost)/cost).mean()*100
for label,px,fc in [('take at mid, fee',price,fees),('take at mid+1¢ (lift ask), fee',price+1,fees),
                    ('take at mid+2¢, fee',price+2,fees),('make at mid-1¢, no fee',price-1,0*fees),
                    ('make at mid-1¢, maker fee 0.0175',price-1,np.array([fee_cents(p,0.0175) for p in mkt])),
                    ('make at mid, no fee',price,0*fees),('sportsbook (backtest, FanDuel-mix odds)',None,None)]:
    if px is None:
        r=np.array([b['ret']/b['stake'] for b in bets]).mean()*100
    else:
        r=roi(px,fc)
    print(f"  {label:40s} ROI/bet {r:+6.1f}%")
print("\nby price bucket (de-vigged pick prob):")
for lo,hi in [(0,0.4),(0.4,0.5),(0.5,0.6),(0.6,0.7),(0.7,1)]:
    m=(mkt>=lo)&(mkt<hi)
    if m.sum()==0: continue
    e=(win[m].mean()-mkt[m].mean())*100; f=fees[m].mean()
    print(f"  {lo:.1f}-{hi:.1f}: n={m.sum():3d}  realized edge {e:+5.1f} pts  taker fee {f:.2f}¢  fee+1¢ spread {f+1:.2f}  net(take) {e-f-1:+5.1f}  net(make -1¢) {e+1:+5.1f}")
# sportsbook hold in the odds file for comparison
holds=[]
for row in dce.ROWS:
    o1,o2=row['fighter1_odds'].replace('−','-'),row['fighter2_odds'].replace('−','-')
    if o1=='-' or o2=='-': continue
    holds.append(betting_math.american_to_prob(int(o1))+betting_math.american_to_prob(int(o2))-1)
holds=np.array(holds); print(f"\nodds-file two-sided hold: mean {holds.mean()*100:.2f}%  median {np.median(holds)*100:.2f}%  (per-side cost ≈ half)")
