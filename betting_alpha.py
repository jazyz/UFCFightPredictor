# file used for betting on next fight card
import requests
from bs4 import BeautifulSoup
import csv
import os

# TODO: figure out how to do rematches 
def get_ml(p1, p2):
    with open("data/betting_predictions.csv", mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if (row["Red Fighter"] == p1 and row["Blue Fighter"] == p2):
                return row["Probability Win"]
        # If no match found
        return None

# ***** CONSTANTS *****
bankroll = 100

# ***** HELPER FUNCTIONS *****
# kelly criterion function, conservative betting strategy
def kelly_criterion(odds, prob_win):
        kc = 0
        if (odds < 0):
            n = 100 / -odds
            kc = (n * prob_win - (1 - prob_win)) / n
        else:
            n = odds / 100  
            kc = (n * prob_win - (1 - prob_win)) / n
        return kc

# convert odds to probability
def odds_to_prob(odds):
    if odds >= 0:
        prob = 100 / (odds + 100)
    else:
        prob = -odds / (-odds + 100)
    return prob

# bookmaker implied probabilities include the vig (they sum to >1);
# proportional normalization recovers the market's fair probabilities
def devig(prob1, prob2):
    total = prob1 + prob2
    if total <= 0:
        return prob1, prob2
    return prob1 / total, prob2 / total

# average win probability between AvB and BvA
def avg_win(avb_win, bva_lose):
    avg_win = (float(avb_win) + float(bva_lose)) / 2
    return avg_win

# bet on fights where our odds are +/-10% of ufc odds

# calculate potential return on bet
def pt(odds, bet):
    if (odds < 0):
        return (bet * (100 / -odds))
    else:
        return (bet * (odds / 100))

# weight on the model's estimate when blending with the devigged market probability;
# tuned on 2021-2022 and validated on 2023 (see testing/blend_compare.py)
BLEND_W = 0.8

# if we bet on a fight, write the bet to the file
def processBet(bet, fighter_name, fighter_odds):
    test.write(fighter_name)
    potential_return = pt(fighter_odds, bet)    
    test.write(f" ${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f} ")


# ***** MAIN *****
# write predictions and betting results to betting_results.txt
with open(os.path.join("data", "betting_results.txt"), "w") as test:
    
    # paste the link to the fight card you want to bet on here
    fight_card_link = "https://www.ufc.com/event/ufc-308"

    response = requests.get(fight_card_link)

    # get all the names of the fighters on the card and the odds 
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        odds_wrappers = soup.find_all(class_='c-listing-fight__odds-wrapper')

        fighter_name_divs = soup.find_all("div", {"class": "c-listing-fight__corner-name"})
        fighter_names = []

        for name_div in fighter_name_divs:
            given_name_element = name_div.find("span", {"class": "c-listing-fight__corner-given-name"})
            family_name_element = name_div.find("span", {"class": "c-listing-fight__corner-family-name"})
            if given_name_element and family_name_element:
                given_name = given_name_element.text.strip()
                family_name = family_name_element.text.strip()
                fighter_names.append(f"{given_name} {family_name}")
            else:
                fighter_name_link = name_div.find("a")
                if fighter_name_link:
                    fighter_name = fighter_name_link.text.strip()
                    fighter_names.append(fighter_name)
                else:
                    fighter_names.append("Fighter Name Not Found")
        
        test.write(f"Bankroll: ${bankroll:.2f}\n")
        test.write(f"Fight Card: {fight_card_link}\n")
        test.write("---\n")

        # Extract and print the odds for each fight on the current card
        for i in range(0, len(fighter_names) - 1, 2):
            # a cancelled bout can leave fewer odds blocks than name pairs
            if i // 2 >= len(odds_wrappers):
                break
            fighter1_name = fighter_names[i]
            fighter2_name = fighter_names[i + 1]
            winner_name = ""

            # extracting the odds
            odds_wrapper = odds_wrappers[i // 2]
            odds_elements = odds_wrapper.find_all(class_='c-listing-fight__odds-amount')
            odds_values = [element.get_text() for element in odds_elements]

            if len(odds_values) == 2:
                fighter1_odds = odds_values[0]
                fighter1_odds = fighter1_odds.replace('−', '-')
                fighter2_odds = odds_values[1]
                fighter2_odds = fighter2_odds.replace('−', '-')
                if (get_ml(fighter1_name, fighter2_name) == None or get_ml(fighter2_name, fighter1_name) == None
                    or fighter1_odds == "-" or fighter2_odds == "-"):
                    # test.write("Fighter not found in the text file.\n")
                    test.write("---\n")
                    continue
                fighter1_odds = int(fighter1_odds)
                fighter2_odds = int(fighter2_odds)
                avb_win = float(get_ml(fighter1_name, fighter2_name)) 
                avb_lose = 1 - avb_win
                bva_win = float(get_ml(fighter2_name, fighter1_name))
                bva_lose = 1 - bva_win 
                
                # average AvB and BvA
                # a_win = avg_win(avb_win, bva_lose)
                # b_win = avg_win(bva_win, avb_lose)

                # blend the model's symmetric estimate with the devigged market probability
                # (missing odds were already skipped above, so these are always ints here)
                odds1_prob, odds2_prob = devig(odds_to_prob(fighter1_odds), odds_to_prob(fighter2_odds))

                model_a = avg_win(avb_win, bva_lose)
                a_win = BLEND_W * model_a + (1 - BLEND_W) * odds1_prob
                b_win = 1 - a_win

                kc_a = kelly_criterion(fighter1_odds, a_win)
                kc_b = kelly_criterion(fighter2_odds, b_win)

                test.write(f"{fighter1_name}: {fighter1_odds} {a_win:.3f} {kc_a:.3f}\n")
                test.write(f"{fighter2_name}: {fighter2_odds} {b_win:.3f} {kc_b:.3f}\n")

                fraction = 0.05
                max_fraction = 0.05
                flat = 0.005
                if a_win > b_win:
                    if (kc_a > 0):
                        bet = bankroll * fraction * kc_a
                        bet = min(bet,max_fraction*bankroll)
                        bet = max(bet,flat*bankroll)
                        processBet(bet, fighter1_name, fighter1_odds)
                    else:
                        if (kc_a > -0.5):
                            bet = flat*bankroll
                            processBet(bet, fighter1_name, fighter1_odds)
                        else:
                            test.write(f"{fighter1_name} (no bet)")
                    test.write("\n")
                else:
                    if (kc_b > 0):
                        bet = bankroll * fraction * kc_b
                        bet = min(bet,max_fraction*bankroll)
                        bet = max(bet,flat*bankroll)
                        processBet(bet, fighter2_name, fighter2_odds)
                    else:
                        if (kc_b > -0.5):
                            bet = flat*bankroll
                            processBet(bet, fighter2_name, fighter2_odds)
                        else:
                            test.write(f"{fighter2_name} (no bet)")
                        
                    test.write("\n")
                test.write("---\n")

