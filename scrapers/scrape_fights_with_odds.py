# date
# fighters
# event name
# winner
# Odds
import requests
from bs4 import BeautifulSoup
import csv
import os
import pandas as pd
from datetime import datetime

def read_csv(file_path):
    data = []
    with open(file_path, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            data.append(row)
    return data

def get_existing_events():
    """Get set of event names that are already scraped"""
    odds_file = os.path.join('data', 'fight_results_with_odds.csv')
    
    if not os.path.exists(odds_file):
        return set()
    
    try:
        df = pd.read_csv(odds_file)
        if len(df) == 0:
            return set()
        return set(df['event_name'].unique())
    except Exception as e:
        print(f"Warning: Could not read existing odds file: {e}")
        return set()

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


# Get existing events to skip
existing_events = get_existing_events()
print(f"Found {len(existing_events)} events already in database\n")

# Determine mode: append if file exists and has data, write if new
odds_file = os.path.join("data", "fight_results_with_odds.csv")
file_exists = os.path.exists(odds_file) and os.path.getsize(odds_file) > 0
file_mode = 'a' if file_exists else 'w'

with open(odds_file, file_mode) as test:
    # Only write header if creating new file
    if not file_exists:
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
    
    events_processed = 0
    events_skipped = 0
    
    for fight_card_link in all_fight_card_links:
        event_name = fight_card_link.split("/")[-1]
        
        # Skip if already in database
        if event_name in existing_events:
            events_skipped += 1
            continue
        
        print(fight_card_link)
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
            
            # Check if event is in the future
            try:
                event_datetime = datetime.strptime(event_date, '%b %d %Y')
                if event_datetime > datetime.now():
                    print(f"Reached future event ({event_date}), stopping scraper.")
                    break
            except ValueError:
                print(f"Warning: Could not parse date '{event_date}' for {event_name}")

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
                # Check both uppercase and lowercase class names (UFC changed this over time)
                if (blue_corner_elements[i].find(class_='c-listing-fight__outcome--Win') 
                    or blue_corner_elements[i].find(class_='c-listing-fight__outcome--win')
                    or red_corner_elements[i].find(class_='c-listing-fight__outcome--Loss')
                    or red_corner_elements[i].find(class_='c-listing-fight__outcome--loss')):
                    winners.append("win")
                elif (blue_corner_elements[i].find(class_='c-listing-fight__outcome--Loss')
                      or blue_corner_elements[i].find(class_='c-listing-fight__outcome--loss')
                      or red_corner_elements[i].find(class_='c-listing-fight__outcome--Win')
                      or red_corner_elements[i].find(class_='c-listing-fight__outcome--win')):
                    winners.append("loss")
                elif (blue_corner_elements[i].find(class_='c-listing-fight__outcome--Draw')
                        or blue_corner_elements[i].find(class_='c-listing-fight__outcome--draw')
                        or red_corner_elements[i].find(class_='c-listing-fight__outcome--Draw')
                        or red_corner_elements[i].find(class_='c-listing-fight__outcome--draw')):
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
                    events_processed += 1

        else:
            print(f"Failed to retrieve the fight card page. Status code: {response.status_code}")
    else:
        print(f"Failed to retrieve the events page. Status code: {response.status_code}")

print("\n" + "="*60)
print(f"Scraping completed!")
print(f"Events processed: {events_processed}")
print(f"Events skipped (already in DB): {events_skipped}")
print("="*60)