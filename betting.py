# scrape betting odds from ufc
import requests
from bs4 import BeautifulSoup

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
                    print(f"{fighter1_name}: {fighter1_odds}")
                    print(f"{fighter2_name}: {fighter2_odds}")
                    print("---")

        else:
            print(f"Failed to retrieve the fight card page. Status code: {response.status_code}")
else:
    print(f"Failed to retrieve the events page. Status code: {response.status_code}")




# calculate using fractional kelly crciterion

# odds = int(input())
# prob_win = int(input())/100

# if (odds < 0):
#     n = 100 / -odds
#     kc = (n * prob_win - (1 - prob_win)) / n
#     print(kc)
# else:
#     n = odds / 100  
#     kc = (n * prob_win - (1 - prob_win)) / n
#     print(kc)
