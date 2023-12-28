# automated testing file
# get all the fights from a certain date from ufc events website
# 

import requests
from bs4 import BeautifulSoup
import csv
import oldModel.update_stats
from datetime import datetime
import oldModel.ml_training_duplication
import oldModel.predict_fights_elo
import os

bankroll = 1000.00
# GOOD INFO TO KEEP TRACK OF AND RESEARCH
correct_predictions = 0
total_predictions = 0
correct_bets = 0
total_bets = 0
correct_underdogs = 0
total_underdogs = 0
correct_favourites = 0
total_favourites = 0
max_bankroll = 0
min_bankroll = 1000
# how much we lose from favourites/underdogs
favourite_loss = 0
underdog_loss = 0
# how much we gain from favourites/underdogs
favourite_gain = 0
underdog_gain = 0

# allow users to pass in variables for website
testFrom_card = "https://www.ufc.com/event/ufc-293" # default to end of somewhere in page 1
testTo_card = "https://www.ufc.com/event/ufc-296" # default to most recent card

def runTests(testFrom_card, testTo_card):
    global bankroll, correct_predictions, total_predictions, correct_bets, total_bets, correct_underdogs, total_underdogs, correct_favourites, total_favourites
    global max_bankroll, min_bankroll, favourite_loss, underdog_loss, favourite_gain, underdog_gain
    print(testFrom_card)
    print(testTo_card)

    # TODO: figure out how to do rematches (maybe just use a set)
    def ml_elo(p1, p2):
        input_txt_filename = os.path.join("oldModel", "ml_elo.txt")
        id = -1
        flag = False
        prob_win = 0

        with open(input_txt_filename, mode="r") as input_file:
            lines = input_file.readlines()
            for line in lines:
                if ("fighter_names" in line):
                    flag = True
                elif ("dtype:" in line):
                    flag = False
                # fields = line.strip().split(' ')
                # fields = list(filter(lambda a: a != '', fields))
                fields = line.strip().split('*')
                # print(fields)

                if (flag):
                    if (fields[0] != "fighter_names" and len(fields) > 1):
                        fighter_name = fields[0][3:].strip()
                        opponent_name = fields[1].strip()
                        # print(fighter_name + " " + opponent_name)
                        if (p1 == fighter_name and p2 == opponent_name):
                            id = fields[0][0:3].strip()
                            print(id)
                if (len(fields) > 0 and "probability_win" in line):
                        flag = True
                elif (id != -1 and flag and fields[0][0:3].strip() == id):
                    # print(fields[0] + " " + fields[1] + " " + id)
                    fields = line.strip().split(' ')
                    fields = list(filter(lambda a: a != '', fields))
                    prob_win = fields[-1]

        if id == -1:
            # test.write(f"Fighter {p1} has less than 5 fights.\n")
            return
        return prob_win

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

    # bet only on favourites which has higher odds than ufc

    # bet only on underdogs 

    # bet on fights where our odds are +/-10% of ufc odds

    # calculate potential return on bet
    def pt(odds, bet):
        if (odds < 0):
            return (bet * (100 / -odds))
        else:
            return (bet * (odds / 100))

    # check winner and update bankroll
    def check_winner(winner_name, fighter_name, potential_return, bet, fighter_odds):
        global bankroll, max_bankroll, min_bankroll, correct_bets, total_bets, correct_underdogs, total_underdogs, correct_favourites, total_favourites
        global favourite_loss, underdog_loss, favourite_gain, underdog_gain
        if (fighter_odds < 0):
            total_favourites += 1
        else:
            total_underdogs += 1
        if (winner_name == fighter_name):
            test.write(" (win)")
            bankroll += potential_return
            max_bankroll = max(max_bankroll, bankroll)
            correct_bets += 1
            total_bets += 1
            if (fighter_odds < 0):
                favourite_gain += potential_return
                correct_favourites += 1
            else:
                underdog_gain += potential_return
                correct_underdogs += 1
        elif (winner_name == "draw/no contest"):
            test.write(" (draw/no contest)")
        else:
            test.write(" (loss)")
            bankroll -= bet
            min_bankroll = min(min_bankroll, bankroll)
            total_bets += 1
            if (fighter_odds < 0):
                favourite_loss += bet
            else:
                underdog_loss += bet

    with open(os.path.join("oldModel", "testing.txt"), "w") as test:

        urls = []
        urls.append("https://www.ufc.com/events")
        # end of page 5 is 1 year ago, usman vs edwards
        # for i in range(1, 2):
        #     urls.append("https://www.ufc.com/events?page=" + str(i))    
        i = 1
        flag = 0
        all_fight_card_links = []
        for url in urls:
            print(url)
            if (flag == 2): 
                break
            # Send a GET request to the events page
            response = requests.get(url)
            # Check if the request was successful
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Find all the fight card links
                fight_card_links = []

                # Extract the links to individual fight card pages
                for card_div in soup.find_all("div", {"class": "c-card-event--result__logo"}):
                    card_link = card_div.find("a")
                    if card_link:
                        fight_card_links.append("https://www.ufc.com" + card_link.get("href"))
        
                for link in fight_card_links:
                    print(link)
                    print(flag)
                    if (link == testTo_card):
                        flag = 1
                    if (flag == 1):
                        all_fight_card_links.append(link)
                    if (link == testFrom_card):
                        flag = 2

                urls.append("https://www.ufc.com/events?page=" + str(i))
                i += 1
                    
        all_fight_card_links.reverse()
        # for links in all_fight_card_links:
        #     print(links)
            # Loop through each fight card link and scrape the odds
        
        cnt = 1
        # UPDATE FIGHTER STATS TO THE DATE OF THE STARTING TEST
        response = requests.get(testFrom_card)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_tag = soup.find('meta', attrs={'property': 'og:description'})
            content = meta_tag.get('content')
            date_str = content.split('On ')[-1]  
            date_str = date_str.split('on ')[-1]
            date_str = date_str.split('.')[0]
            date_obj = ""
            formatted_date = ""
            date_formats = ['%A, %B %d, %Y', '%B %d, %Y', '%A %B %d, %Y']
            for date_format in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, date_format)
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                    print("date obj: ", date_obj)
                    break  # Break out of the loop if parsing succeeds
                except ValueError:
                    pass  # Continue to the next format if parsing fails
            if (formatted_date == ""):
                print(date_str)
            oldModel.update_stats.event_to_drop = date_obj
            oldModel.update_stats.main()

            # UPDATE PREDICT_FIGHTS_ELO.CSV WITH NEW FIGHTER STATS
            oldModel.predict_fights_elo.main()

            #  UPDATE TRAINING AND GET NEW PREDICTIONS
            # formatted_date = date_obj.strftime('%Y-%m-%d')
            print(formatted_date)
            oldModel.ml_training_duplication.date_to_train = formatted_date
            oldModel.ml_training_duplication.main()
        
        for fight_card_link in all_fight_card_links:
            print(fight_card_link)
            print(bankroll)
            response = requests.get(fight_card_link)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find and extract the odds as shown in your original HTML
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

                # Find all elements with the class "c-listing-fight__corner-body--blue"
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
                        if (ml_elo(fighter1_name, fighter2_name) == None or ml_elo(fighter2_name, fighter1_name) == None
                            or fighter1_odds == "-" or fighter2_odds == "-"):
                            # test.write("Fighter not found in the text file.\n")
                            test.write("---\n")
                            continue
                        fighter1_odds = int(fighter1_odds)
                        fighter2_odds = int(fighter2_odds)
                        avb_win = float(ml_elo(fighter1_name, fighter2_name)) 
                        avb_lose = 1 - avb_win
                        bva_win = float(ml_elo(fighter2_name, fighter1_name))
                        bva_lose = 1 - bva_win 
                        
                        # average AvB and BvA
                        a_win_avg = avg_win(avb_win, bva_lose)
                        b_win_avg = avg_win(bva_win, avb_lose)

                        # choose AvB or BvA based on how close they are to odds
                        odds1_prob = 0
                        odds2_prob = 0
                        if (fighter1_odds != "-" and fighter2_odds != "-"):
                            odds1_prob = odds_to_prob(fighter1_odds)
                            odds2_prob = odds_to_prob(fighter2_odds)
                        a_win_avg=avb_win
                        b_win_avg=bva_win
                        if(abs(avb_win-odds1_prob) > abs(bva_lose-odds1_prob)):
                            a_win_avg=bva_lose
                        if(abs(bva_win-odds2_prob) > abs(avb_lose-odds2_prob)):
                            b_win_avg=avb_lose

                        kc_a = 0
                        kc_b = 0
                        if (fighter1_odds != "-" and fighter2_odds != "-"):
                            kc_a = kelly_criterion(fighter1_odds, a_win_avg)
                            kc_b = kelly_criterion(fighter2_odds, b_win_avg)
                        test.write(f"{fighter1_name}: {fighter1_odds} {a_win_avg:.2f} {kc_a:.2f}\n")
                        test.write(f"{fighter2_name}: {fighter2_odds} {b_win_avg:.2f} {kc_b:.2f}\n")
                        if a_win_avg > b_win_avg:
                            if (winner_name == fighter1_name and winner_name != "draw/no contest"):
                                correct_predictions += 1
                            total_predictions += 1
                            test.write(f"{fighter1_name} ")
                            # for underdogs (and fighter1_odds < fighter2_odds)
                            if (kc_a > 0): 
                                # bet = 0
                                # if (fighter1_odds < fighter2_odds):
                                #     bet = 25
                                # else:
                                bet = bankroll * (0.1) * kc_a
                                odds = fighter1_odds
                                potential_return = pt(odds, bet)
                                test.write(f"${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f}")
                                check_winner(winner_name, fighter1_name, potential_return, bet, fighter1_odds)
                            else:
                                test.write(f"(no bet)")
                            test.write("\n")
                        else:
                            if (winner_name == fighter2_name and winner_name != "draw/no contest"):
                                correct_predictions += 1
                            total_predictions += 1
                            test.write(f"{fighter2_name} ")
                            # for favourites (and fighter2_odds < fighter1_odds)
                            if (kc_b > 0):
                                # bet = 0
                                # if (fighter2_odds < fighter1_odds):
                                #     bet = 25
                                # else:
                                bet = bankroll * (0.1) * kc_b
                                odds = fighter2_odds
                                potential_return = pt(odds, bet)
                                test.write(f"${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f}")
                                check_winner(winner_name, fighter2_name, potential_return, bet, fighter2_odds)
                            else:
                                test.write(f"(no bet)")
                            test.write("\n")
                        test.write(f" *** {winner_name} *** \n")
                        

                        test.write("---\n")
            
                if cnt % 8 == 0:
                    #  UPDATE FIGHTER STATS AFTER EACH EVENT
                    meta_tag = soup.find('meta', attrs={'property': 'og:description'})
                    content = meta_tag.get('content')
                    date_str = content.split('On ')[-1]  
                    date_str = date_str.split('on ')[-1]
                    date_str = date_str.split('.')[0]
                    date_obj = ""
                    formatted_date = ""
                    date_formats = ['%A, %B %d, %Y', '%B %d, %Y', '%A %B %d, %Y']
                    for date_format in date_formats:
                        try:
                            date_obj = datetime.strptime(date_str, date_format)
                            formatted_date = date_obj.strftime('%Y-%m-%d')
                            print("date obj: ", date_obj)
                            break  # Break out of the loop if parsing succeeds
                        except ValueError:
                            pass  # Continue to the next format if parsing fails
                    if (formatted_date == ""):
                        print(date_str)
                    oldModel.update_stats.event_to_drop = date_obj
                    oldModel.update_stats.main()
                    test.write("---\n")
        
            if cnt % 10 == 0:
                #  UPDATE FIGHTER STATS AFTER EACH EVENT
                meta_tag = soup.find('meta', attrs={'property': 'og:description'})
                content = meta_tag.get('content')
                date_str = content.split('On ')[-1]  
                date_str = date_str.split('on ')[-1]
                date_str = date_str.split('.')[0]
                date_obj = ""
                formatted_date = ""
                date_formats = ['%A, %B %d, %Y', '%B %d, %Y', '%A %B %d, %Y']
                for date_format in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, date_format)
                        formatted_date = date_obj.strftime('%Y-%m-%d')
                        print("date obj: ", date_obj)
                        break  # Break out of the loop if parsing succeeds
                    except ValueError:
                        pass  # Continue to the next format if parsing fails
                if (formatted_date == ""):
                    print(date_str)
                oldModel.update_stats.event_to_drop = date_obj
                oldModel.update_stats.main()

                # UPDATE PREDICT_FIGHTS_ELO.CSV WITH NEW FIGHTER STATS
                oldModel.predict_fights_elo.main()

                #  UPDATE TRAINING AND GET NEW PREDICTIONS
                # formatted_date = date_obj.strftime('%Y-%m-%d')
                print(formatted_date)
                oldModel.ml_training_duplication.date_to_train = formatted_date
                oldModel.ml_training_duplication.main()
                    
                # # most recent fight
                if (fight_card_link == testTo_card):
                    break
                cnt += 1

            else:
                test.write(f"Failed to retrieve the fight card page. Status code: {response.status_code}\n")
        else:
            test.write(f"Failed to retrieve the events page. Status code: {response.status_code}\n")
        test.write(f"Bankroll: ${bankroll:.2f}\n")
        test.write(f"Max Bankroll: ${max_bankroll:.2f}\n")
        test.write(f"{correct_bets}/{total_bets} = {correct_bets/total_bets * 100}% correct bets\n")
        test.write(f"{correct_predictions}/{total_predictions} = {correct_predictions/total_predictions*100}% correct predictions\n")
        test.write(f"{total_underdogs}/{total_bets} {correct_underdogs}/{total_underdogs} = {correct_underdogs/total_underdogs*100}% correct underdog bets\n")
        test.write(f"Total underdog loss: ${underdog_loss:.2f}\n")
        test.write(f"Total underdog gain: ${underdog_gain:.2f}\n")
        test.write(f"{total_favourites}/{total_bets} {correct_favourites}/{total_favourites} = {correct_favourites/total_favourites*100}% correct favourite bets\n")
        test.write(f"Total favourite loss: ${favourite_loss:.2f}\n")
        test.write(f"Total favourite gain: ${favourite_gain:.2f}\n")

if __name__ == "__main__":
    runTests(testFrom_card, testTo_card)