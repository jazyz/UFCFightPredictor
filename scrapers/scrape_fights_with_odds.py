# date
# fighters
# event name
# winner
# Odds
import requests
from bs4 import BeautifulSoup
import csv
import os

def read_csv(file_path):
    data = []
    with open(file_path, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            data.append(row)
    return data

# TODO: handle rematches
def findWinner(fighter1_name, fighter2_name):
    csv_file_path = os.path.join('data', 'fight_details.csv')
    data = read_csv(csv_file_path)
    winner_name = ""
    for row in data:
        if row['Red Fighter'] == fighter1_name and row['Blue Fighter'] == fighter2_name:
            if (row['Draw'] == True):
                winner_name = "draw/no contest"
            else:
                winner_name = row['Winner']
        elif row['Red Fighter'] == fighter2_name and row['Blue Fighter'] == fighter1_name:
            if (row['Draw'] == True):
                winner_name = "draw/no contest"
            else:
                winner_name = row['Winner']
    return winner_name


with open(os.path.join("data", "fight_results_with_odds.csv"), "w") as test:
    test.write("event_name,event_date,fighter1_name,fighter2_name,winner_name,fighter1_odds,fighter2_odds\n")
    urls = []
    urls.append("https://www.ufc.com/events")
    for i in range(1,20):
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
                

    event_year = ""

    all_fight_card_links.reverse()
    for fight_card_link in all_fight_card_links:
        print(fight_card_link)

        event_name = fight_card_link.split("/")[-1]
        if event_name.startswith("ufc-fight-night"):
            event_year = event_name.split("-")[-1]

        response = requests.get(fight_card_link)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            event_date = ""
            element = soup.find('div', class_='c-hero__headline-suffix')
            if element:
                event_date = element.get_text(strip=True).split("/")[0].strip().split(",")[1].strip()
            
            event_date = event_date + " " + event_year

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
                elif (blue_corner_elements[i].find(class_='c-listing-fight__outcome--Draw')
                        or red_corner_elements[i].find(class_='c-listing-fight__outcome--Draw')):
                    winners.append("draw/no contest")
                else:
                    winners.append("Fighter Name Not Found")
            
            if (len(winners) == 0):
                continue
            
            for i in range(0, len(fighter_names), 2):
                fighter1_name = fighter_names[i]
                fighter2_name = fighter_names[i + 1]
                winner = winners[i // 2]
                winner_name = ""
                if winner == "win":
                    winner_name = fighter2_name
                elif winner == "loss":
                    winner_name = fighter1_name
                elif winner == "draw/no contest":
                    winner_name = "draw/no contest"
                else:
                    winner_name = findWinner(fighter1_name, fighter2_name)

                odds_wrapper = odds_wrappers[i // 2]
                odds_elements = odds_wrapper.find_all(class_='c-listing-fight__odds-amount')
                odds_values = [element.get_text() for element in odds_elements]

                if len(odds_values) == 2:
                    fighter1_odds = odds_values[0]
                    fighter1_odds = fighter1_odds.replace('−', '-')
                    fighter2_odds = odds_values[1]
                    fighter2_odds = fighter2_odds.replace('−', '-')

                    test.write(f"{event_name},{event_date},{fighter1_name},{fighter2_name},{winner_name},{fighter1_odds},{fighter2_odds}\n")
                    

            if (fight_card_link == "https://www.ufc.com/event/ufc-296"):
                break

        else:
            test.write(f"Failed to retrieve the fight card page. Status code: {response.status_code}\n")
    else:
        test.write(f"Failed to retrieve the events page. Status code: {response.status_code}\n")