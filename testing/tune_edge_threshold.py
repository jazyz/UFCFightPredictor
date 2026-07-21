# Tunes the minimum-edge betting threshold (strategy[3]) on a training window,
# then validates the chosen value on a held-out window.
# Trainings are cached per retrain-date so each threshold run reuses the same models.
import os
import shutil
import sys

sys.path.insert(0, 'testing')
import testing_time_period as ttp

CACHE_DIR = os.path.join('test_results', '.edge_tune_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

_orig_train = ttp.train_ml

def cached_train(date):
    cache_file = os.path.join(CACHE_DIR, f'predicted_{date}.csv')
    if os.path.exists(cache_file):
        shutil.copy(cache_file, os.path.join('data', 'predicted_results.csv'))
    else:
        _orig_train(date)
        shutil.copy(os.path.join('data', 'predicted_results.csv'), cache_file)

ttp.train_ml = cached_train

def run(start, end, edge):
    ttp.process_dates(start, end, strategy=[0.05, 0.05, 0.005, edge])
    bets = ttp.favourites + ttp.underdogs
    hits = ttp.favouritesHit + ttp.underdogsHit
    return ttp.bankroll, bets, hits

if __name__ == '__main__':
    print('=== TUNING on 2021-01-01 .. 2023-01-01 ===')
    print(f'{"edge":>6} {"bankroll":>10} {"bets":>6} {"hits":>6}')
    for edge in [0, 0.02, 0.04, 0.06, 0.08]:
        bankroll, bets, hits = run('2021-01-01', '2023-01-01', edge)
        print(f'{edge:>6.2f} {bankroll:>10.2f} {bets:>6} {hits:>6}', flush=True)

    print('=== VALIDATION on 2023-01-01 .. 2024-01-01 ===')
    print(f'{"edge":>6} {"bankroll":>10} {"bets":>6} {"hits":>6}')
    for edge in [0, 0.02, 0.04, 0.06, 0.08]:
        bankroll, bets, hits = run('2023-01-01', '2024-01-01', edge)
        print(f'{edge:>6.2f} {bankroll:>10.2f} {bets:>6} {hits:>6}', flush=True)
