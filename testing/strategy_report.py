# Runs the betting-strategy configurations across backtest windows and reports
# profit and risk metrics. Trainings cached per retrain date (shared with the
# other tuning drivers).
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

def max_drawdown(series):
    peak = series[0] if series else 0
    worst = 0.0
    for x in series:
        peak = max(peak, x)
        worst = max(worst, (peak - x) / peak)
    return worst

CONFIGS = [
    ('legacy (devig only)', [0.05, 0.05, 0.005]),
    ('blend w=0.8',         [0.05, 0.05, 0.005, 0, 0.8]),
    ('blend + edge 0.04',   [0.05, 0.05, 0.005, 0.04, 0.8]),
]

WINDOWS = [
    ('2021-2023 (tune)', '2021-01-01', '2023-01-01'),
    ('2023 (validation)', '2023-01-01', '2024-01-01'),
    ('2021-2024 (full)', '2021-01-01', '2024-01-01'),
]

if __name__ == '__main__':
    header = f'{"window":>18} {"config":>20} {"final$":>8} {"profit%":>8} {"bets":>5} {"hit%":>6} {"maxDD%":>7} {"min$":>8}'
    print(header)
    for wlabel, start, end in WINDOWS:
        for clabel, strat in CONFIGS:
            ttp.process_dates(start, end, strategy=strat)
            bets = ttp.favourites + ttp.underdogs
            hits = ttp.favouritesHit + ttp.underdogsHit
            hit_pct = hits / bets * 100 if bets else 0
            dd = max_drawdown(ttp.bankrolls) * 100
            min_bank = min(ttp.bankrolls) if ttp.bankrolls else 1000
            profit_pct = (ttp.bankroll - 1000) / 1000 * 100
            print(f'{wlabel:>18} {clabel:>20} {ttp.bankroll:>8.2f} {profit_pct:>8.1f} {bets:>5} {hit_pct:>6.1f} {dd:>7.1f} {min_bank:>8.2f}', flush=True)
