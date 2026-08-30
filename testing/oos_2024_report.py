# Out-of-sample betting backtest on 2024-01-01 .. 2026-07-19: a window that
# influenced no tuning or feature selection. Walk-forward retraining, caches
# each retrain so the three configs share models.
import os
import shutil
import sys

sys.path.insert(0, 'testing')
import testing_time_period as ttp
import ml_alpha_testing

CACHE = os.path.join('test_results', '.oos2024_cache')
os.makedirs(CACHE, exist_ok=True)

def cached_train(date):
    cf = os.path.join(CACHE, f'pred_{date}.csv')
    if os.path.exists(cf):
        shutil.copy(cf, os.path.join('data', 'predicted_results.csv'))
    else:
        ml_alpha_testing.main(date)
        shutil.copy(os.path.join('data', 'predicted_results.csv'), cf)

ttp.train_ml = cached_train

def max_dd(series):
    peak, worst = (series[0] if series else 0), 0.0
    for x in series:
        peak = max(peak, x); worst = max(worst, (peak - x) / peak if peak else 0)
    return worst

CONFIGS = [
    ('legacy (devig only)', [0.05, 0.05, 0.005]),
    ('blend w=0.8',         [0.05, 0.05, 0.005, 0, 0.8]),
    ('blend + edge 0.04',   [0.05, 0.05, 0.005, 0.04, 0.8]),
]
START, END = '2024-01-01', '2026-07-19'

if __name__ == '__main__':
    print(f'{"config":>20} {"final$":>9} {"profit%":>8} {"bets":>5} {"hit%":>6} {"maxDD%":>7} {"min$":>8}')
    for label, strat in CONFIGS:
        ttp.process_dates(START, END, strategy=strat)
        bets = ttp.favourites + ttp.underdogs
        hits = ttp.favouritesHit + ttp.underdogsHit
        hit = hits / bets * 100 if bets else 0
        dd = max_dd(ttp.bankrolls) * 100
        mn = min(ttp.bankrolls) if ttp.bankrolls else 1000
        print(f'{label:>20} {ttp.bankroll:>9.2f} {(ttp.bankroll-1000)/10:>8.1f} {bets:>5} {hit:>6.1f} {dd:>7.1f} {mn:>8.2f}', flush=True)
