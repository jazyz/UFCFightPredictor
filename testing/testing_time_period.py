import csv
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('agg')

# Check if running in Flask context
try:
    from testing.ml_alpha_testing import main
except ImportError:
    from ml_alpha_testing import main


bankroll = 1000
bankrolls = []
def kelly_criterion(odds, prob_win):
        kc = 0
        if (odds < 0):
            n = 100 / -odds
            kc = (n * prob_win - (1 - prob_win)) / n
        else:
            n = odds / 100  
            kc = (n * prob_win - (1 - prob_win)) / n
        return kc

def odds_to_prob(odds):
    if odds >= 0:
        prob = 100 / (odds + 100)
    else:
        prob = -odds / (-odds + 100)
    return prob    

def avg_win(avb_win, bva_lose):
    avg_win = (float(avb_win) + float(bva_lose)) / 2
    return avg_win

def closerToOdds(avb_win, avb_lose, bva_win, bva_lose, odds1_prob, odds2_prob):
    a_win=avb_win
    b_win=bva_win
    if(abs(avb_win-odds1_prob) > abs(bva_lose-odds1_prob)):
        a_win=bva_lose
        b_win=1-a_win

    if(abs(bva_win-odds2_prob) > abs(avb_lose-odds2_prob)):
        b_win=avb_lose
        a_win=1-b_win

    if a_win + b_win != 1:
        a_win = avg_win(avb_win, bva_lose)
        b_win = 1-a_win
    return a_win, b_win

def pt(odds, bet):
    if (odds < 0):
        return (bet * (100 / -odds))
    else:
        return (bet * (odds / 100))


# Global dictionary to store all predictions
ml_predictions = {}

def preload_ml_predictions():
    global ml_predictions
    filepath = os.path.join("data", "predicted_results.csv")
    with open(filepath, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            fighters = (row["Red Fighter"], row["Blue Fighter"])
            fighters2 = (row["Blue Fighter"], row["Red Fighter"])
            if row["Predicted Result"] == "win":
                probability = float(row["Probability"])
            else:  # if the predicted result is "loss"
                probability = 1 - float(row["Probability"])
            ml_predictions[fighters] = probability
            # ml_predictions[fighters2] = 1-probability

def get_ml(p1, p2):
    global ml_predictions
    result = ml_predictions.get((p1, p2))
    return result

def process_winner(winner_name, fighter_name, potential_return, bet, fighter_odds):
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        if (winner_name == fighter_name):
            test.write(" (win)")
            return potential_return
        elif (winner_name == "draw/no contest"):
            test.write(" (draw/no contest)")
            return 0
        else:
            test.write(" (loss)")
            return -bet

def processBet(bet, fighter_name, fighter_odds, winner_name):
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        test.write(fighter_name)
        potential_return = pt(fighter_odds, bet)    
        test.write(f" ${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f} ")
        test.flush()
        return process_winner(winner_name, fighter_name, potential_return, bet, fighter_odds)

def process_fight(fight, strategy=[0.05, 0.05, 0]):
    global bankroll, bankrolls
    fighter1_name = fight['fighter1_name']
    fighter2_name = fight['fighter2_name']
    winner_name = fight['winner_name']
    fighter1_odds = fight['fighter1_odds']
    fighter2_odds = fight['fighter2_odds']
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        fighter1_odds = fighter1_odds.replace('−', '-')
        fighter2_odds = fighter2_odds.replace('−', '-')
        if (get_ml(fighter1_name, fighter2_name) == None or get_ml(fighter2_name, fighter1_name) == None
            or fighter1_odds == "-" or fighter2_odds == "-"):
            test.write("---\n")
            return
        fighter1_odds = int(fighter1_odds)
        fighter2_odds = int(fighter2_odds)
        avb_win = float(get_ml(fighter1_name, fighter2_name)) 
        avb_lose = 1 - avb_win
        bva_win = float(get_ml(fighter2_name, fighter1_name))
        bva_lose = 1 - bva_win 



        odds1_prob = odds_to_prob(fighter1_odds)
        odds2_prob = odds_to_prob(fighter2_odds)

        a_win, b_win = closerToOdds(avb_win,avb_lose, bva_win, bva_lose, odds1_prob, odds2_prob)
        # a_win = avg_win(avb_win, bva_lose)
        # b_win = avg_win(bva_win, avb_lose)
        kc_a = kelly_criterion(fighter1_odds, a_win)
        kc_b = kelly_criterion(fighter2_odds, b_win)
        test.write(f"Bankroll: {bankroll:.2f}\n")
        test.write(f"{fighter1_name}: {fighter1_odds} {a_win:.3f} {kc_a:.2f}\n")
        test.write(f"{fighter2_name}: {fighter2_odds} {b_win:.3f} {kc_b:.2f}\n")
        test.flush()
        # conservative strategy: 0.025, 0.025, 0
        # normal strategy: 0.05, 0.05, 0
        # risky strategy: 0.1, 0.1, 0
        # kc strategy: don't do anything
        # flat: 0.01, 0.015, 0.02 (if 3rd parameter > 0 then flat all predictions)
        fraction = strategy[0]
        max_fraction = strategy[1]
        flat = strategy[2]
        if a_win > b_win:

            if (kc_a > 0):
                bet = bankroll * fraction * kc_a
                bet = min(bet,max_fraction*bankroll)
                if flat>0:
                    bet = bankroll * flat
                bankroll+=processBet(bet, fighter1_name, fighter1_odds, winner_name)
            else:
                bet = bankroll * flat
                bankroll+=processBet(bet, fighter1_name, fighter1_odds, winner_name)
                # test.write(f"(no bet)")
            test.write("\n")
        else:

            if (kc_b > 0):
                bet = bankroll * fraction * kc_b
                bet = min(bet,max_fraction*bankroll)
                if flat>0:
                    bet = bankroll * flat
                bankroll+=processBet(bet, fighter2_name, fighter2_odds, winner_name)
            else:
                bet = bankroll * flat
                bankroll+=processBet(bet, fighter1_name, fighter1_odds, winner_name)
                # test.write(f"(no bet)")
                
            test.write("\n")
        test.write(f" *** {winner_name} *** \n")
        test.write("---\n")
        bankrolls.append(bankroll)
    return
    
def find_fights(start_date, end_date, last_training_date, strategy):
    # Convert start_date and end_date from 'YYYY-MM-DD' to datetime objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    final_training_date = datetime.strptime('2023-12-01', '%Y-%m-%d')
    retrain_time = timedelta(days=182)  
    filepath = 'data/fight_results_with_odds.csv'
    
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        fight_reader = csv.DictReader(csvfile)
        for row in fight_reader:
            event_date = datetime.strptime(row['event_date'], '%b %d %Y')
            if start_date <= event_date <= end_date:
                if event_date >= (last_training_date + retrain_time) and event_date < final_training_date:
                    last_training_date = event_date
                    train_ml(last_training_date.strftime('%Y-%m-%d'))
                    preload_ml_predictions()
                process_fight(row, strategy)

def train_ml(start_date):
    main(start_date)

def process_dates(start_date, end_date, strategy):
    print(strategy)
    global bankroll, bankrolls
    bankroll = 1000
    bankrolls = []
    with open(os.path.join("test_results", "testing_time_period.txt"), "w") as test:
        test.write(f"{start_date} to {end_date}\n")
    start_year = datetime.strptime(start_date, '%Y-%m-%d').year
    # split_date = f"{start_year}-01-01"
    split_date = start_date
    last_training_date = datetime.strptime(split_date, '%Y-%m-%d')  # Initialize last training date
    train_ml(split_date)
    preload_ml_predictions()
    
    find_fights(start_date, end_date, last_training_date, strategy)  # Pass the last training date
    
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        test.write(f"Bankroll: {bankroll:.2f}\n")
    with open(os.path.join("test_results", "testing_time_period_results.txt"), "a") as test:
        test.write("------ RESULT ------\n")
        test.write(f"Bankroll: {bankroll:.2f}\n")
    print(bankroll)
    plot_bankrolls()

def plot_bankrolls():
    plt.figure(figsize=(10, 6))
    plt.plot(bankrolls, marker='o')  # Plotting the bankrolls array
    plt.title("Bankroll Over Time")
    plt.xlabel("Bet Number")
    plt.ylabel("Bankroll")
    plt.grid(True)
    # plt.show()
    plt.savefig(os.path.join("data", "bankroll_plot.png"))  # Save the plot as an image file
    plt.close()  # Close the plot

process_dates('2023-01-01', '2024-01-01', strategy=[0.1,0.1,0.00])
