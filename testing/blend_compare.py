# Grids the model/market blend weight (strategy[4]) against the minimum-edge
# threshold (strategy[3]). Replays cached trainings, so no model refits.
import os
import shutil
import sys

sys.path.insert(0, 'testing')
import testing_time_period as ttp
import ml_alpha_testing

CACHE_DIR = os.path.join('test_results', '.edge_tune_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def cached_train(date):
    cache_file = os.path.join(CACHE_DIR, f'predicted_{date}.csv')
    if os.path.exists(cache_file):
        shutil.copy(cache_file, os.path.join('data', 'predicted_results.csv'))
    else:
        ml_alpha_testing.main(date)
        shutil.copy(os.path.join('data', 'predicted_results.csv'), cache_file)

ttp.train_ml = cached_train

if __name__ == '__main__':
    print(f'{"blend_w":>8} {"edge":>5} {"tune$":>9} {"bets":>5} {"val$":>9} {"bets":>5}')
    for w in [None, 1.0, 0.8, 0.6, 0.4, 0.2]:
        for edge in [0, 0.01, 0.02, 0.04]:
            results = []
            for start, end in [('2021-01-01', '2023-01-01'), ('2023-01-01', '2024-01-01')]:
                ttp.process_dates(start, end, strategy=[0.05, 0.05, 0.005, edge, w])
                results.append((ttp.bankroll, ttp.favourites + ttp.underdogs))
            (t_bank, t_bets), (v_bank, v_bets) = results
            label = 'legacy' if w is None else f'{w:.1f}'
            print(f'{label:>8} {edge:>5.2f} {t_bank:>9.2f} {t_bets:>5} {v_bank:>9.2f} {v_bets:>5}', flush=True)
