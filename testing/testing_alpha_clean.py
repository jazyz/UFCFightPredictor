import matplotlib.pyplot as plt


import requests
from bs4 import BeautifulSoup
import csv
import os

# TODO: figure out how to do rematches (maybe just use a set)
def get_ml(p1, p2):
    with open(os.path.join("data", "predicted_results.csv"), mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if (row["Red Fighter"] == p1 and row["Blue Fighter"] == p2):
                # Check if p1 is the predicted winner and return the probability
                if row["Predicted Result"] == "win" and row["Red Fighter"] == p1:
                    return float(row["Probability"])
                elif row["Predicted Result"] == "loss" and row["Red Fighter"] == p1:
                    return 1 - float(row["Probability"])
                # elif row["Predicted Result"] == "loss" and row["Blue Fighter"] == p1:
                #     return float(row["Probability"])
                # elif row["Predicted Result"] == "win" and row["Blue Fighter"] == p1:
                #     return 1 - float(row["Probability"])
        # If no match found
        return None

bankroll = 1000.00
minBankroll = bankroll
maxBankroll = bankroll
maxCardBet = 0
correctBets = 0
totalBets = 0
totalBetAmount = 0 
favourite_gain = 0
favourite_loss = 0
underdog_gain = 0
underdog_loss = 0
correctPredictions = 0
totalPredictions = 0
averageBankroll = 0
cardNumber = 0
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

# choosing win/lose probability based on how close they are to odds
def odds_to_prob(odds):
    if odds >= 0:
        prob = 100 / (odds + 100)
    else:
        prob = -odds / (-odds + 100)
    return prob    

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

def closerToOdds(avb_win, avb_lose, bva_win, bva_lose, odds1_prob, odds2_prob):
    a_win=avb_win
    b_win=bva_win
    if(abs(avb_win-odds1_prob) > abs(bva_lose-odds1_prob)):
        a_win=bva_lose
    if(abs(bva_win-odds2_prob) > abs(avb_lose-odds2_prob)):
        b_win=avb_lose
    return a_win, b_win

def process_winner(winner_name, fighter_name, potential_return, bet, fighter_odds):
    global correctBets, favourite_gain, favourite_loss, underdog_gain, underdog_loss, totalBets, totalBetAmount
    totalBets+=1
    if (winner_name == fighter_name):
        correctBets+=1
        if fighter_odds<0:
            favourite_gain+=potential_return
        if fighter_odds>0:
            underdog_gain+=potential_return


        test.write(" (win)")
        return potential_return
    elif (winner_name == "draw/no contest"):
        test.write(" (draw/no contest)")
        return 0
    else:
        if fighter_odds<0:
            favourite_loss+=bet
        if fighter_odds>0:
            underdog_loss+=bet

        test.write(" (loss)")
        return -bet
    return 0

def processBet(bet, fighter_name, fighter_odds):
    test.write(fighter_name)
    potential_return = pt(fighter_odds, bet)    
    test.write(f" ${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f} ")
    return process_winner(winner_name, fighter_name, potential_return, bet, fighter_odds)

with open(r"test_results\testing_alpha_clean.txt", "w") as test:
    urls = []
    # urls.append("https://www.ufc.com/events")
    for i in range(5,10):
        urls.append("https://www.ufc.com/events?page=" + str(i))    
    all_fight_card_links = []
    for url in urls:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            fight_card_links = []
            for card_div in soup.find_all("div", {"class": "c-card-event--result__logo"}):
                card_link = card_div.find("a")
                if card_link:
                    fight_card_links.append("https://www.ufc.com" + card_link.get("href"))
            for link in fight_card_links:
                all_fight_card_links.append(link)
                

    all_fight_card_links.reverse()
    for fight_card_link in all_fight_card_links:
        print(fight_card_link)
        response = requests.get(fight_card_link)

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

            blue_corner_elements = soup.find_all(class_='c-listing-fight__corner-body--blue')
            red_corner_elements = soup.find_all(class_='c-listing-fight__corner-body--red')
            winners = []
            
            for i in range (0, len(blue_corner_elements)):
                if (blue_corner_elements[i].find(class_='c-listing-fight__outcome--Win') 
                    or red_corner_elements[i].find(class_='c-listing-fight__outcome--Loss')):
                    winners.append("win")
                elif (blue_corner_elements[i].find(class_='c-listing-fight__outcome--Loss')
                      or red_corner_elements[i].find(class_='c-listing-fight__outcome--Win')):
                    winners.append("loss")
                else:
                    winners.append("draw/no contest")
            
            if (len(winners) == 0):
                continue
            
            test.write(f"Bankroll: ${bankroll:.2f}\n")
            test.write(f"Fight Card: {fight_card_link}\n")
            test.write("---\n")

            # Extract and print the odds for each fight on the current card
            cardBet=0
            nextBankroll=bankroll
            for i in range(0, len(fighter_names), 2):
                fighter1_name = fighter_names[i]
                fighter2_name = fighter_names[i + 1]
                winner = winners[i // 2]
                winner_name = ""
                if winner == "win":
                    winner_name = fighter2_name
                elif winner == "loss":
                    winner_name = fighter1_name
                else:
                    winner_name = "draw/no contest"

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

                    # choose AvB or BvA based on how close they are to odds
                    odds1_prob = 0
                    odds2_prob = 0
                    if (fighter1_odds != "-" and fighter2_odds != "-"):
                        odds1_prob = odds_to_prob(fighter1_odds)
                        odds2_prob = odds_to_prob(fighter2_odds)

                    a_win, b_win = closerToOdds(avb_win,avb_lose, bva_win, bva_lose, odds1_prob, odds2_prob)

                    if (fighter1_odds != "-" and fighter2_odds != "-"):
                        kc_a = kelly_criterion(fighter1_odds, a_win)
                        kc_b = kelly_criterion(fighter2_odds, b_win)

                    test.write(f"{fighter1_name}: {fighter1_odds} {a_win:.2f} {kc_a:.2f}\n")
                    test.write(f"{fighter2_name}: {fighter2_odds} {b_win:.2f} {kc_b:.2f}\n")

                    fraction = 0.05
                    max_fraction = 0.05
                    flat = 0.000
                    totalPredictions += 1
                    if a_win > b_win:
                        if winner_name == fighter1_name:
                            correctPredictions+=1

                        if (kc_a > 0):
                            bet = bankroll * fraction * kc_a
                            bet = min(bet,max_fraction*bankroll)
                            bet=10
                            cardBet+=bet
                            nextBankroll+=processBet(bet, fighter1_name, fighter1_odds)
                        else:
                            # bet = bankroll * flat
                            # nextBankroll+=processBet(bet, fighter1_name, fighter1_odds)
                            test.write(f"(no bet)")
                        test.write("\n")
                    else:
                        if winner_name == fighter2_name:
                            correctPredictions+=1

                        if (kc_b > 0):
                            bet = bankroll * fraction * kc_b
                            bet = min(bet,max_fraction*bankroll)
                            bet=10
                            cardBet+=bet
                            nextBankroll+=processBet(bet, fighter2_name, fighter2_odds)
                        else:
                            # bet = bankroll * flat
                            # nextBankroll+=processBet(bet, fighter2_name, fighter2_odds)
                            test.write(f"(no bet)")
                            
                        test.write("\n")
                    test.write(f" *** {winner_name} *** \n")
                    

                    test.write("---\n")
                
            bankroll=nextBankroll
            averageBankroll+=bankroll
            cardNumber+=1
            bankrolls.append(bankroll)
            minBankroll=min(minBankroll,bankroll)
            maxBankroll=max(maxBankroll,bankroll)
            maxCardBet=max(maxCardBet,cardBet)
            if (fight_card_link == "https://www.ufc.com/event/ufc-296"):
                break

        else:
            test.write(f"Failed to retrieve the fight card page. Status code: {response.status_code}\n")
    else:
        test.write(f"Failed to retrieve the events page. Status code: {response.status_code}\n")
    with open(r"test_results\results.txt", "a") as file:
        file.write("------ RESULT ------\n")
        file.write(f"Bankroll: ${bankroll:.2f}\n")
        file.write(f"Min Bankroll: ${minBankroll:.2f}\n")
        file.write(f"Max Bankroll: ${maxBankroll:.2f}\n")
        file.write(f"Average Bankroll: ${averageBankroll/cardNumber:.2f}\n")
        file.write(f"Max Card Bet: ${maxCardBet:.2f}\n")
        # file.write(f"Correct Predictions: {correctPredictions/totalPredictions:.2f}\n")
        # file.write(f"Correct Bets: {correctBets/totalBets:.2f}\n")
        file.write(f"Favourite Gain: ${favourite_gain:.2f}\n")
        file.write(f"Favourite Loss: ${favourite_loss:.2f}\n")
        file.write(f"Underdog Gain: ${underdog_gain:.2f}\n")
        file.write(f"Underdog Loss: ${underdog_loss:.2f}\n")
        file.write("\n")

plt.figure(figsize=(10, 6))
plt.plot(bankrolls, marker='o')  # Plotting the bankrolls array
plt.title("Bankroll Over Time")
plt.xlabel("Time")
plt.ylabel("Bankroll")
plt.grid(True)
plt.show()
