# Which then gets read by ml alpha
# Which outputs predicted results

import requests
from bs4 import BeautifulSoup
import csv
import os

# ****** HELPER FUNCTIONS ******
def get_csv_headers(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        return headers
def split_at_first_space(text):
    # Split the text by the first space
    parts = text.split(" ", 1)
    # Return both parts, before and after the first space
    return parts[0], parts[1] if len(parts) > 1 else ""

def sqrSum(n):
    x = float(n)
    return x*(x+1)*(2*x+1)//6

# ****** CONSTANTS ******
input_csv_filename = os.path.join("data", "detailed_fighter_stats.csv")
output_csv_filename = "predict_fights_alpha.csv"

end_fight_card = "http://www.ufcstats.com/event-details/13a0fb8fbdafb54f"

fieldnames = [
    "Result",
    "Red Fighter",
    "Blue Fighter",
    # "Title",
    "Red dob",
    "Blue dob",
    "Red totalfights",
    "Blue totalfights",
    "Red elo",
    "Blue elo",
    "Red losestreak",
    "Blue losestreak",
    "Red winstreak",
    "Blue winstreak",
    "Red titlewins",
    "Blue titlewins",
    "Red oppelo",
    "Blue oppelo",
    "Red wins",
    "Blue wins",
    "Red losses",
    "Blue losses",
    "Red KD",
    "Blue KD",
    "Red KD differential",
    "Blue KD differential",
    "Red Sig. str.",
    "Blue Sig. str.",
    "Red Sig. str. differential",
    "Blue Sig. str. differential",
    "Red Total str.",
    "Blue Total str.",
    "Red Total str. differential",
    "Blue Total str. differential",
    "Red Td",
    "Blue Td",
    "Red Td differential",
    "Blue Td differential",
    "Red Sub. att",
    "Blue Sub. att",
    "Red Sub. att differential",
    "Blue Sub. att differential",
    "Red Rev.",
    "Blue Rev.",
    "Red Rev. differential",
    "Blue Rev. differential",
    "Red Ctrl",
    "Blue Ctrl",
    "Red Ctrl differential",
    "Blue Ctrl differential",
    "Red Head",
    "Blue Head",
    "Red Head differential",
    "Blue Head differential",
    "Red Body",
    "Blue Body",
    "Red Body differential",
    "Blue Body differential",
    "Red Leg",
    "Blue Leg",
    "Red Leg differential",
    "Blue Leg differential",
    "Red Distance",
    "Blue Distance",
    "Red Distance differential",
    "Blue Distance differential",
    "Red Clinch",
    "Blue Clinch",
    "Red Clinch differential",
    "Blue Clinch differential",
    "Red Ground",
    "Blue Ground",
    "Red Ground differential",
    "Blue Ground differential",
    "Red Sig. str.%",
    "Blue Sig. str.%",
    "Red Sig. str.% differential",
    "Blue Sig. str.% differential",
    "Red Sig. str.% defense",
    "Blue Sig. str.% defense",
    "Red Total str.%",
    "Blue Total str.%",
    "Red Total str.% differential",
    "Blue Total str.% differential",
    "Red Total str.% defense",
    "Blue Total str.% defense",
    "Red Td%",
    "Blue Td%",
    "Red Td% differential",
    "Blue Td% differential",
    "Red Td% defense",
    "Blue Td% defense",
    "Red Head%",
    "Blue Head%",
    "Red Head% differential",
    "Blue Head% differential",
    "Red Head% defense",
    "Blue Head% defense",
    "Red Body%",
    "Blue Body%",
    "Red Body% differential",
    "Blue Body% differential",
    "Red Body% defense",
    "Blue Body% defense",
    "Red Leg%",
    "Blue Leg%",
    "Red Leg% differential",
    "Blue Leg% differential",
    "Red Leg% defense",
    "Blue Leg% defense",
    "Red Distance%",
    "Blue Distance%",
    "Red Distance% differential",
    "Blue Distance% differential",
    "Red Distance% defense",
    "Blue Distance% defense",
    "Red Clinch%",
    "Blue Clinch%",
    "Red Clinch% differential",
    "Blue Clinch% differential",
    "Red Clinch% defense",
    "Blue Clinch% defense",
    "Red Ground%",
    "Blue Ground%",
    "Red Ground% differential",
    "Blue Ground% differential",
    "Red Ground% defense",
    "Blue Ground% defense",
    "dob oppdiff",
    "totalfights oppdiff",
    "elo oppdiff",
    "losestreak oppdiff",
    "winstreak oppdiff",
    "titlewins oppdiff",
    "oppelo oppdiff",
    "wins oppdiff",
    "losses oppdiff",
    "KD oppdiff",
    "KD differential oppdiff",
    "Sig. str. oppdiff",
    "Sig. str. differential oppdiff",
    "Total str. oppdiff",
    "Total str. differential oppdiff",
    "Td oppdiff",
    "Td differential oppdiff",
    "Sub. att oppdiff",
    "Sub. att differential oppdiff",
    "Rev. oppdiff",
    "Rev. differential oppdiff",
    "Ctrl oppdiff",
    "Ctrl differential oppdiff",
    "Head oppdiff",
    "Head differential oppdiff",
    "Body oppdiff",
    "Body differential oppdiff",
    "Leg oppdiff",
    "Leg differential oppdiff",
    "Distance oppdiff",
    "Distance differential oppdiff",
    "Clinch oppdiff",
    "Clinch differential oppdiff",
    "Ground oppdiff",
    "Ground differential oppdiff",
    "Sig. str.% oppdiff",
    "Sig. str.% differential oppdiff",
    "Sig. str.% defense oppdiff",
    "Total str.% oppdiff",
    "Total str.% differential oppdiff",
    "Total str.% defense oppdiff",
    "Td% oppdiff",
    "Td% differential oppdiff",
    "Td% defense oppdiff",
    "Head% oppdiff",
    "Head% differential oppdiff",
    "Head% defense oppdiff",
    "Body% oppdiff",
    "Body% differential oppdiff",
    "Body% defense oppdiff",
    "Leg% oppdiff",
    "Leg% differential oppdiff",
    "Leg% defense oppdiff",
    "Distance% oppdiff",
    "Distance% differential oppdiff",
    "Distance% defense oppdiff",
    "Clinch% oppdiff",
    "Clinch% differential oppdiff",
    "Clinch% defense oppdiff",
    "Ground% oppdiff",
    "Ground% differential oppdiff",
    "Ground% defense oppdiff",
]

file_path = os.path.join('data', 'modified_fight_details.csv')


# retrieve all total strike numbers from head, body, leg, distance, clinch, ground, sig.str
# store it back into the dicts
headers=get_csv_headers(file_path)

hardcoded_features = ["dob","totalfights","elo","losestreak","winstreak","titlewins",]
hardcoded_features_divide = ["oppelo","wins","losses"]

feature_list=[]
feature_list.extend(hardcoded_features)
feature_list.extend(hardcoded_features_divide)

header_features = []
for column in headers:
    s1,s2=split_at_first_space(column)
    if(s1=="Red" and s2!="Fighter"):
        header_features.append(s2)

feature_list.extend(header_features)

# extract and process fights, return them into the csv
def extract_fighter_stats(fighter_name, opponent_name):
    fighter_stats = None
    opponent_stats = None

    with open(input_csv_filename, mode="r", newline="") as input_file:
        csv_reader = csv.DictReader(input_file)
        for row in csv_reader:
            if row["Fighter"] == fighter_name:
                fighter_stats = row
            elif row["Fighter"] == opponent_name:
                opponent_stats = row

    if fighter_stats is None or opponent_stats is None:
        print(f"{fighter_name} or {opponent_name} not found in the CSV.")
        return

    if int(fighter_stats["totalfights"]) <= 1 or int(opponent_stats["totalfights"]) <= 1:
        return
    combined_stats = {}
    combined_stats = process_fight(fighter_stats, opponent_stats, combined_stats)
    # print(combined_stats)
    with open(output_csv_filename, mode="a", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writerow(combined_stats)

def process_fight(fighter_stats, opponent_stats, processed_fight):
    if int(fighter_stats["totalfights"]) >= 2 and int(opponent_stats["totalfights"]) >= 2:
        processed_fight["Result"] = "unknown"
        processed_fight["Red Fighter"] = fighter_stats["Fighter"]
        processed_fight["Blue Fighter"] = opponent_stats["Fighter"]
        # print(f"Processing {fighter_stats['Fighter']} vs {opponent_stats['Fighter']}")
        for feature in feature_list:
            # print(feature)
            if feature in fighter_stats and feature in opponent_stats:
                processed_fight[f'Red {feature}'] = fighter_stats[feature]
                processed_fight[f'Blue {feature}'] = opponent_stats[feature]
                if feature in header_features:
                    processed_fight[f'Red {feature} differential'] = fighter_stats[f'{feature} differential']
                    processed_fight[f'Blue {feature} differential'] = opponent_stats[f'{feature} differential']
                    processed_fight[f'Red {feature}'] = float(fighter_stats[feature]) / sqrSum(fighter_stats["totalfights"])
                    processed_fight[f'Blue {feature}'] = float(opponent_stats[feature]) / sqrSum(opponent_stats["totalfights"])
                    processed_fight[f'Red {feature} differential'] = float(fighter_stats[feature]) / sqrSum(fighter_stats["totalfights"])
                    processed_fight[f'Blue {feature} differential'] = float(opponent_stats[feature]) / sqrSum(opponent_stats["totalfights"])
                    if "%" in feature:
                        processed_fight[f'Red {feature} defense'] = sqrSum(float(fighter_stats[f"{feature} defense"]) / float(fighter_stats["totalfights"]))
                        processed_fight[f'Blue {feature} defense'] = sqrSum(float(opponent_stats[f"{feature} defense"]) / float(opponent_stats["totalfights"]))
        for feature in feature_list:
            # Basic feature difference
            red_key = f'Red {feature}'
            blue_key = f'Blue {feature}'
            if red_key in processed_fight and blue_key in processed_fight:
                processed_fight[f'{feature} oppdiff'] = float(processed_fight[red_key]) - float(processed_fight[blue_key])

            # Differential feature difference
            red_diff_key = f'Red {feature} differential'
            blue_diff_key = f'Blue {feature} differential'
            if red_diff_key in processed_fight and blue_diff_key in processed_fight:
                processed_fight[f'{feature} differential oppdiff'] = float(processed_fight[red_diff_key]) - float(processed_fight[blue_diff_key])

            # Defense feature difference
            red_defense_key = f'Red {feature} defense'
            blue_defense_key = f'Blue {feature} defense'
            if red_defense_key in processed_fight and blue_defense_key in processed_fight:
                processed_fight[f'{feature} defense oppdiff'] = float(processed_fight[red_defense_key]) - float(processed_fight[blue_defense_key])

        return processed_fight

def predict_fight(fighter1_name, fighter2_name):
    # print(f"Processing {fighter1_name} vs {fighter2_name}")
    with open(output_csv_filename, mode="w", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writeheader()
    extract_fighter_stats(fighter1_name, fighter2_name)
    extract_fighter_stats(fighter2_name, fighter1_name)

def main():
    # GET LIST OF EVENTS URLS
    url = "http://www.ufcstats.com/statistics/events/completed?page=all"
    response = requests.get(url)

    # to get one event, paste the url in event_urls and comment out the part below
    event_urls = []

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr', class_='b-statistics__table-row')
        for row in rows:
            link = row.find('a', class_='b-link b-link_style_black')
            if link:
                event_url = link.get('href')
                event_urls.append(event_url)
                # event that your testing until
                # print(event_url)
                if (event_url == end_fight_card):
                    break
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")

    with open(output_csv_filename, mode="w", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writeheader()
    
    for url in event_urls:
        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            fight_table = soup.find("tbody", class_="b-fight-details__table-body")

            fight_rows = fight_table.find_all("tr", class_="b-fight-details__table-row")
            fights=[]
            for fight_row in fight_rows:
                fighter_names = fight_row.find_all("a", class_="b-link_style_black")
                fighter1_name = fighter_names[0].text.strip()
                fighter2_name = fighter_names[1].text.strip()
                fights.append([fighter1_name,fighter2_name])
        else:
            print("Failed to retrieve the web page.")
        
        for fight in fights:
            fighter_name = fight[0]
            opponent_name = fight[1]
            extract_fighter_stats(fighter_name, opponent_name)
            extract_fighter_stats(opponent_name, fighter_name)

if __name__ == "__main__":
    main()