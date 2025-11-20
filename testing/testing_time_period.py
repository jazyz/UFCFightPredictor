import csv
from datetime import datetime, timedelta
import os
import sys
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('agg')

# Add parent directory to path for proper imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the training function
try:
    from testing.ml_alpha_testing import main
except ImportError:
    try:
        from ml_alpha_testing import main
    except ImportError:
        # If both fail, try adding testing directory to path
        testing_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, testing_dir)
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
            # fighters2 = (row["Blue Fighter"], row["Red Fighter"])
            # probability = float(row["Probability Win"])
            if row["Predicted Result"] == "win":
                probability = float(row["Probability"])
            else: 
                probability = 1 - float(row["Probability"])
            ml_predictions[fighters] = probability
            # ml_predictions[fighters2] = 1-probability

def get_ml(p1, p2):
    global ml_predictions
    result = ml_predictions.get((p1, p2))
    return result

ev=0
underdogs=0
favourites=0
underdogsHit=0
favouritesHit=0
total_wagered=0
total_to_win=0
num_bets=0
def process_winner(winner_name, fighter_name, potential_return, bet, fighter_odds):
    global ev,underdogs,favourites,underdogsHit,favouritesHit
    betEV=0

    if(fighter_odds<0):
        favourites+=1
        betEV=0.7*(potential_return)-0.3*bet 
    else:
        underdogs+=1
        betEV=0.34*(potential_return)-0.66*bet 
    ev+=betEV
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        if (winner_name == fighter_name):
            test.write(" (win)")
            if(fighter_odds<0):
                favouritesHit+=1
            else:
                underdogsHit+=1
            return potential_return
        elif (winner_name == "draw/no contest"):
            test.write(" (draw/no contest)")
            return 0
        else:
            test.write(" (loss)")
            return -bet


def processBet(bet, fighter_name, fighter_odds, winner_name):
    global total_wagered, total_to_win, num_bets
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        test.write(fighter_name)
        potential_return = pt(fighter_odds, bet)   
        test.write(f" ${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f} ")
        test.flush()
        
        # Track totals
        total_wagered += bet
        total_to_win += (bet + potential_return)
        num_bets += 1
        
        return process_winner(winner_name, fighter_name, potential_return, bet, fighter_odds)

def process_fight(fight, strategy=[0.05, 0.05, 0, 0.05]):
    global bankroll, bankrolls
    fighter1_name = fight['fighter1_name']
    fighter2_name = fight['fighter2_name']
    winner_name = fight['winner_name']
    fighter1_odds = fight['fighter1_odds']
    fighter2_odds = fight['fighter2_odds']
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        fighter1_odds = fighter1_odds.replace('−', '-')
        fighter2_odds = fighter2_odds.replace('−', '-')
        
        # Check if predictions are available
        avb_win = get_ml(fighter1_name, fighter2_name)
        bva_win = get_ml(fighter2_name, fighter1_name)
        
        if avb_win == None or bva_win == None:
            # No predictions available
            test.write("---\n")
            return
        
        # Have predictions but no odds
        if fighter1_odds == "-" or fighter2_odds == "-":
            avb_win = float(avb_win)
            avb_lose = 1 - avb_win
            bva_win = float(bva_win)
            bva_lose = 1 - bva_win
            a_win = avg_win(avb_win, bva_lose)
            b_win = 1 - a_win
            
            test.write(f"[NO ODDS AVAILABLE]\n")
            test.write(f"{fighter1_name}: prob={a_win:.3f} ({a_win:.1%})\n")
            test.write(f"{fighter2_name}: prob={b_win:.3f} ({b_win:.1%})\n")
            predicted_winner = fighter1_name if a_win > b_win else fighter2_name
            test.write(f"Predicted: {predicted_winner}\n")
            test.write(f" *** {winner_name} *** ")
            if winner_name == predicted_winner:
                test.write("✓ CORRECT\n")
            elif winner_name == "draw/no contest":
                test.write("(draw/no contest)\n")
            else:
                test.write("✗ WRONG\n")
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
        
        # Calculate edge (model probability - market implied probability)
        edge_a = a_win - odds1_prob
        edge_b = b_win - odds2_prob
        min_edge = strategy[3] if len(strategy) > 3 else 0.05  # 5% minimum edge threshold (default)
        
        test.write(f"Bankroll: {bankroll:.2f}\n")
        test.write(f"{fighter1_name}: {fighter1_odds} prob={a_win:.3f} edge={edge_a:.3f} kc={kc_a:.2f}\n")
        test.write(f"{fighter2_name}: {fighter2_odds} prob={b_win:.3f} edge={edge_b:.3f} kc={kc_b:.2f}\n")
        test.flush()
        # Strategy format: [kelly_fraction, max_fraction, flat_bet, min_edge]
        # conservative strategy: [0.025, 0.025, 0, 0.05]
        # normal strategy: [0.05, 0.05, 0, 0.05]
        # risky strategy: [0.1, 0.1, 0, 0.05]
        # no edge filter: [0.05, 0.05, 0, 0] - bet on any positive Kelly
        # flat: [0.01, 0.015, 0.02, 0.05] - if 3rd parameter > 0 then flat all predictions
        fraction = strategy[0]
        max_fraction = strategy[1]
        flat = strategy[2]
        if a_win > b_win:

            if (kc_a > 0 and edge_a > min_edge):
                bet = bankroll * fraction * kc_a
                bet = min(bet,max_fraction*bankroll)
                bet=max(bet,bankroll*flat)
                test.write(f"[EDGE {edge_a:.1%}] ")
                # if flat>0:
                #     bet = bankroll * flat
                bankroll+=processBet(bet, fighter1_name, fighter1_odds, winner_name)
            else:
                if (kc_a>-0.5 and flat > 0):
                    bet = bankroll * flat
                    test.write(f"[FLAT] ")
                    bankroll+=processBet(bet, fighter1_name, fighter1_odds, winner_name)
                else:
                    if edge_a <= min_edge:
                        test.write(f"(no bet - edge {edge_a:.1%} < {min_edge:.0%})")
                    else:
                        test.write(f"(no bet - kc {kc_a:.2f})")
            test.write("\n")
        else:

            if (kc_b > 0 and edge_b > min_edge):
                bet = bankroll * fraction * kc_b
                bet = min(bet,max_fraction*bankroll)
                bet=max(bet,bankroll*flat)
                test.write(f"[EDGE {edge_b:.1%}] ")
                # if flat>0:
                #     bet = bankroll * flat
                bankroll+=processBet(bet, fighter2_name, fighter2_odds, winner_name)
            else:
                if (kc_b>-0.5 and flat > 0):
                    bet = bankroll * flat
                    test.write(f"[FLAT] ")
                    bankroll+=processBet(bet, fighter2_name, fighter2_odds, winner_name)
                else:
                    if edge_b <= min_edge:
                        test.write(f"(no bet - edge {edge_b:.1%} < {min_edge:.0%})")
                    else:
                        test.write(f"(no bet - kc {kc_b:.2f})")
                
                
            test.write("\n")
        test.write(f" *** {winner_name} *** \n")
        test.write("---\n")
        bankrolls.append(bankroll)
    return
    
def find_fights(start_date, end_date, last_training_date, strategy):
    # Convert start_date and end_date from 'YYYY-MM-DD' to datetime objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    final_training_date = datetime.strptime(start_date.strftime('%Y-%m-%d'), '%Y-%m-%d')
    retrain_time = timedelta(days=182)  
    filepath = 'data/fight_results_with_odds.csv'
    
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        fight_reader = csv.DictReader(csvfile)
        for row in fight_reader:
            try:
                # Strip whitespace and parse date
                date_str = row['event_date'].strip()
                # Skip if date is malformed (missing year or incomplete)
                if not date_str or len(date_str.split()) < 3:
                    continue
                event_date = datetime.strptime(date_str, '%b %d %Y')
            except (ValueError, KeyError) as e:
                # Skip fights with malformed dates
                continue
            
            if start_date <= event_date <= end_date:
                if event_date >= (last_training_date + retrain_time) and event_date < final_training_date:
                    last_training_date = event_date
                    train_ml(last_training_date.strftime('%Y-%m-%d'))
                    preload_ml_predictions()
                process_fight(row, strategy)

def train_ml(start_date):
    main(start_date)
    pass

def process_dates(start_date, end_date, strategy):
    print(strategy)
    global bankroll, bankrolls, total_wagered, total_to_win, num_bets, ev, underdogs, favourites, underdogsHit, favouritesHit
    bankroll = 1000
    bankrolls = []
    total_wagered = 0
    total_to_win = 0
    num_bets = 0
    ev = 0
    underdogs = 0
    favourites = 0
    underdogsHit = 0
    favouritesHit = 0
    with open(os.path.join("test_results", "testing_time_period.txt"), "w") as test:
        test.write(f"{start_date} to {end_date}\n")
    start_year = datetime.strptime(start_date, '%Y-%m-%d').year
    # split_date = f"{start_year}-01-01"
    split_date = start_date
    last_training_date = datetime.strptime(split_date, '%Y-%m-%d')  # Initialize last training date
    train_ml(split_date)
    preload_ml_predictions()
    
    find_fights(start_date, end_date, last_training_date, strategy)  # Pass the last training date
    
    # Calculate profit/loss and ROI
    profit_loss = bankroll - 1000
    roi = (profit_loss / total_wagered * 100) if total_wagered > 0 else 0
    avg_bet = total_wagered / num_bets if num_bets > 0 else 0
    
    with open(os.path.join("test_results", "testing_time_period.txt"), "a") as test:
        test.write("\n" + "="*60 + "\n")
        test.write("BETTING SUMMARY\n")
        test.write("="*60 + "\n")
        test.write(f"Number of Bets: {num_bets}\n")
        test.write(f"Total Wagered: ${total_wagered:.2f}\n")
        test.write(f"Total To Win: ${total_to_win:.2f}\n")
        test.write(f"Average Bet Size: ${avg_bet:.2f}\n")
        test.write(f"\nStarting Bankroll: $1000.00\n")
        test.write(f"Final Bankroll: ${bankroll:.2f}\n")
        test.write(f"Profit/Loss: ${profit_loss:.2f}\n")
        test.write(f"ROI: {roi:.2f}%\n")
        test.write(f"\nFavourites: {favouritesHit}/{favourites} ({(favouritesHit/favourites*100 if favourites > 0 else 0):.1f}%)\n")
        test.write(f"Underdogs: {underdogsHit}/{underdogs} ({(underdogsHit/underdogs*100 if underdogs > 0 else 0):.1f}%)\n")
        test.write("="*60 + "\n")
        
    with open(os.path.join("test_results", "testing_time_period_results.txt"), "a") as test:
        test.write("------ RESULT ------\n")
        test.write(f"Bets: {num_bets} | Wagered: ${total_wagered:.2f} | To Win: ${total_to_win:.2f}\n")
        test.write(f"Final Bankroll: ${bankroll:.2f} | P/L: ${profit_loss:.2f} | ROI: {roi:.2f}%\n")
    
    print(f"\n{'='*60}")
    print(f"Bets: {num_bets} | Wagered: ${total_wagered:.2f} | To Win: ${total_to_win:.2f}")
    print(f"Final Bankroll: ${bankroll:.2f} | P/L: ${profit_loss:.2f} | ROI: {roi:.2f}%")
    print(f"{'='*60}\n")
    # Output final bankroll as plain number for auto_retrain parsing
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

if __name__ == "__main__":
    import sys
    from datetime import datetime, timedelta
    
    # Check if command line arguments provided
    if len(sys.argv) >= 3:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
    else:
        # Default: last 1 year
        end_date_dt = datetime.now()
        start_date_dt = end_date_dt - timedelta(days=365)
        start_date = start_date_dt.strftime('%Y-%m-%d')
        end_date = end_date_dt.strftime('%Y-%m-%d')
    
    print(f"Backtesting period: {start_date} to {end_date}")
    # Strategy: [kelly_fraction, max_fraction, flat_bet, min_edge]
    # With 5% edge filter (matching Event Predictor)
    process_dates(start_date, end_date, strategy=[0.05, 0.05, 0, 0.0])
