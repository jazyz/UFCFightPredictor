# Compares probability calibration methods (none / platt / isotonic) by backtest
# bankroll, across minimum-edge thresholds. Trainings cached per (method, date).
import os
import shutil
import sys

sys.path.insert(0, 'testing')
import testing_time_period as ttp
import ml_alpha_testing

CACHE_DIR = os.path.join('test_results', '.edge_tune_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

method = None

def cached_train(date):
    # raw runs keep the original cache-file names so earlier results are reused
    tag = f'{method}_' if method else ''
    cache_file = os.path.join(CACHE_DIR, f'predicted_{tag}{date}.csv')
    if os.path.exists(cache_file):
        shutil.copy(cache_file, os.path.join('data', 'predicted_results.csv'))
    else:
        ml_alpha_testing.main(date, calibration=method)
        shutil.copy(os.path.join('data', 'predicted_results.csv'), cache_file)

ttp.train_ml = cached_train

if __name__ == '__main__':
    print(f'{"method":>9} {"window":>6} {"edge":>5} {"bankroll":>10} {"bets":>5} {"hits":>5}')
    for m in [None, 'platt', 'isotonic']:
        method = m
        for start, end, label in [('2021-01-01', '2023-01-01', 'tune'),
                                  ('2023-01-01', '2024-01-01', 'val')]:
            for edge in [0, 0.02, 0.04]:
                ttp.process_dates(start, end, strategy=[0.05, 0.05, 0.005, edge])
                bets = ttp.favourites + ttp.underdogs
                hits = ttp.favouritesHit + ttp.underdogsHit
                print(f'{m or "raw":>9} {label:>6} {edge:>5.2f} {ttp.bankroll:>10.2f} {bets:>5} {hits:>5}', flush=True)
