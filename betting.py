# scrape betting odds from ufc and automatically calculate kelly criterion bet from ml_elo.txt

import requests
from bs4 import BeautifulSoup
import csv

input_csv_filename = "fighter_stats.csv"

def extract_fighter_stats(
    input_csv_filename, fighter_name
):
    fighter_stats = None

    with open(input_csv_filename, mode="r", newline="") as input_file:
        csv_reader = csv.DictReader(input_file)
        for row in csv_reader:
            if row["name"] == fighter_name:
                fighter_stats = row

    if fighter_stats is None:
        print("Fighter or opponent not found in the CSV.")
        return

    if int(fighter_stats["totalfights"]) <= 2:
        print("Fighter has less than 3 fights.")
        return
    print(fighter_stats["totalwins"])

# read from ml_elo.txt
def ml_elo(fighter_name):
    input_txt_filename = "ml_elo.txt"
    id = -1
    flag = False
    prob_win = 0

    with open(input_txt_filename, mode="r") as input_file:
        lines = input_file.readlines()
        for line in lines:
            if fighter_name in line:
                id = line[0] + line[1]
                id = id.strip()
            fields = line.strip().split(' ')
            
            # print(fields[0])
            if (fields[0] == "probability_win"):
                    flag = True
            elif (id != -1 and flag and fields[0] == id):
                # print(fields[0] + " " + fields[1] + " " + id)
                prob_win = fields[-1]
    
    if id == -1:
        print(f"Fighter {fighter_name} not found in the text file.")
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

# Send a GET request to the events page
url = "https://www.ufc.com/events#events-list-past"
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
        

    # Loop through each fight card link and scrape the odds
    for fight_card_link in fight_card_links:
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

            # print("Fight Card: ", fight_card_link)

            # Extract and print the odds for each fight on the current card
            for i in range(0, len(fighter_names), 2):
                fighter1_name = fighter_names[i]
                fighter2_name = fighter_names[i + 1]

                odds_wrapper = odds_wrappers[i // 2]
                odds_elements = odds_wrapper.find_all(class_='c-listing-fight__odds-amount')
                odds_values = [element.get_text() for element in odds_elements]

                if len(odds_values) == 2:
                    fighter1_odds = odds_values[0]
                    fighter2_odds = odds_values[1]
                    if (ml_elo(fighter1_name) == None or ml_elo(fighter2_name) == None):
                        print(f"Fighter not found in the text file.")
                        print("---")
                        continue
                    avb_win = ml_elo(fighter1_name)
                    avb_lose = 1 - float(avb_win)
                    bva_win = ml_elo(fighter2_name)
                    bva_lose = 1 - float(bva_win)
                    a_win_avg = (float(avb_win) + float(bva_lose)) / 2
                    b_win_avg = (float(bva_win) + float(avb_lose)) / 2
                    kc_a = kelly_criterion(int(fighter1_odds), a_win_avg)
                    kc_b = kelly_criterion(int(fighter2_odds), b_win_avg)
                    print(f"{fighter1_name}: {fighter1_odds} " + str(a_win_avg) + " " + str(kc_a))
                    print(f"{fighter2_name}: {fighter2_odds} " + str(b_win_avg) + " " + str(kc_b))
                    if a_win_avg > b_win_avg:
                        print(f"{fighter1_name}")
                    else:
                        print(f"{fighter2_name}")

                    print("---")

        else:
            print(f"Failed to retrieve the fight card page. Status code: {response.status_code}")
else:
    print(f"Failed to retrieve the events page. Status code: {response.status_code}")



