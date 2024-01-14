import requests
from bs4 import BeautifulSoup
import csv
import os
from datetime import datetime

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
# where to read stats from
input_csv_filename = os.path.join("data", "detailed_fighter_stats.csv")
# where to output processed stats to
output_csv_filename = os.path.join("data", "predict_fights_alpha.csv")

# starts from the most recent fight card and goes back in time, this is the last fight card to be processed
end_fight_card = "http://www.ufcstats.com/event-details/010986ee359fb863"
# end_fight_card = "http://www.ufcstats.com/event-details/5a558ba1ff5e9121"

# same fields used in ml_alpha, detailed_fights.csv
fieldnames = get_csv_headers(os.path.join("data", "detailed_fights.csv"))

# GETTING ALL REQUIRED STATS
# file path to the modified fight details csv, which contains the wanted headers
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

# process the 2 fighters stats into Red and Blue
# same process as process_fights_alpha
def process_fight(fighter_stats, opponent_stats, processed_fight):
    if int(fighter_stats["totalfights"]) >= 2 and int(opponent_stats["totalfights"]) >= 2:
        processed_fight["Result"] = "unknown"
        processed_fight["Red Fighter"] = fighter_stats["Fighter"]
        processed_fight["Blue Fighter"] = opponent_stats["Fighter"]
       
        current_year = datetime.now().year
        processed_fight['Red age'] = current_year - int(fighter_stats['dob'])
        processed_fight['Blue age'] = current_year - int(opponent_stats['dob'])
        processed_fight['age oppdiff'] = processed_fight['Red age'] - processed_fight['Blue age'] 
        
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


# Used to predict exactly 1 fight (erases all data in the output csv and writes the new fight)
def predict_fight(fighter1_name, fighter2_name):
    print(f"Processing {fighter1_name} vs {fighter2_name}")
    with open(output_csv_filename, mode="w", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writeheader()
    extract_fighter_stats(fighter1_name, fighter2_name)
    extract_fighter_stats(fighter2_name, fighter1_name)

# ***** MAIN *****
# get all the urls of the fight cards
# if you want a single fight card, paste the ufcstats.com url in event_urls and comment out the part below
# or if you just want the most recent fight card, change end_fight_card to the most recent
def main():
    # predict_fight("Alexander Volkanovski", "Ilia Topuria")
    # return
    # GET LIST OF EVENTS URLS
    # url = "http://www.ufcstats.com/statistics/events/completed?page=all"
    # response = requests.get(url)

    # to get one event, paste the url in event_urls and comment out the part below
    event_urls = ["http://ufcstats.com/event-details/bd85ca0bb4f26cfc"]

    # if response.status_code == 200:
    #     soup = BeautifulSoup(response.text, 'html.parser')
    #     rows = soup.find_all('tr', class_='b-statistics__table-row')
    #     for row in rows:
    #         link = row.find('a', class_='b-link b-link_style_black')
    #         if link:
    #             event_url = link.get('href')
    #             event_urls.append(event_url)
    #             # event that your testing until
    #             # print(event_url)
    #             if (event_url == end_fight_card):
    #                 break
    # else:
    #     print(f"Failed to retrieve the page. Status code: {response.status_code}")

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