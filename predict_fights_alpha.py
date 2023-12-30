# Which then gets read by ml alpha
# Which outputs predicted results

import requests
from bs4 import BeautifulSoup
import csv
import os

input_csv_filename = os.path.join("data", "detailed_fighter_stats.csv")
output_csv_filename = "predict_fights_alpha.csv"

fieldnames = [
    "fighter_Fighter",
    "fighter_dob",
    "fighter_totalfights",
    "fighter_elo",
    "fighter_losestreak",
    "fighter_winstreak",
    "fighter_titlewins",
    "fighter_oppelo",
    "fighter_wins",
    "fighter_losses",
    "fighter_KD",
    "fighter_KD differential",
    "fighter_Sig. str.",
    "fighter_Sig. str. differential",
    "fighter_Total str.",
    "fighter_Total str. differential",
    "fighter_Td",
    "fighter_Td differential",
    "fighter_Sub. att",
    "fighter_Sub. att differential",
    "fighter_Rev.",
    "fighter_Rev. differential",
    "fighter_Ctrl",
    "fighter_Ctrl differential",
    "fighter_Head",
    "fighter_Head differential",
    "fighter_Body",
    "fighter_Body differential",
    "fighter_Leg",
    "fighter_Leg differential",
    "fighter_Distance",
    "fighter_Distance differential",
    "fighter_Clinch",
    "fighter_Clinch differential",
    "fighter_Ground",
    "fighter_Ground differential",
    "fighter_Sig. str.%",
    "fighter_Sig. str.% differential",
    "fighter_Sig. str.% defense",
    "fighter_Total str.%",
    "fighter_Total str.% differential",
    "fighter_Total str.% defense",
    "fighter_Td%",
    "fighter_Td% differential",
    "fighter_Td% defense",
    "fighter_Head%",
    "fighter_Head% differential",
    "fighter_Head% defense",
    "fighter_Body%",
    "fighter_Body% differential",
    "fighter_Body% defense",
    "fighter_Leg%",
    "fighter_Leg% differential",
    "fighter_Leg% defense",
    "fighter_Distance%",
    "fighter_Distance% differential",
    "fighter_Distance% defense",
    "fighter_Clinch%",
    "fighter_Clinch% differential",
    "fighter_Clinch% defense",
    "fighter_Ground%",
    "fighter_Ground% differential",
    "fighter_Ground% defense",

    "opponent_Fighter",
    "opponent_dob",
    "opponent_totalfights",
    "opponent_elo",
    "opponent_losestreak",
    "opponent_winstreak",
    "opponent_titlewins",
    "opponent_oppelo",
    "opponent_wins",
    "opponent_losses",
    "opponent_KD",
    "opponent_KD differential",
    "opponent_Sig. str.",
    "opponent_Sig. str. differential",
    "opponent_Total str.",
    "opponent_Total str. differential",
    "opponent_Td",
    "opponent_Td differential",
    "opponent_Sub. att",
    "opponent_Sub. att differential",
    "opponent_Rev.",
    "opponent_Rev. differential",
    "opponent_Ctrl",
    "opponent_Ctrl differential",
    "opponent_Head",
    "opponent_Head differential",
    "opponent_Body",
    "opponent_Body differential",
    "opponent_Leg",
    "opponent_Leg differential",
    "opponent_Distance",
    "opponent_Distance differential",
    "opponent_Clinch",
    "opponent_Clinch differential",
    "opponent_Ground",
    "opponent_Ground differential",
    "opponent_Sig. str.%",
    "opponent_Sig. str.% differential",
    "opponent_Sig. str.% defense",
    "opponent_Total str.%",
    "opponent_Total str.% differential",
    "opponent_Total str.% defense",
    "opponent_Td%",
    "opponent_Td% differential",
    "opponent_Td% defense",
    "opponent_Head%",
    "opponent_Head% differential",
    "opponent_Head% defense",
    "opponent_Body%",
    "opponent_Body% differential",
    "opponent_Body% defense",
    "opponent_Leg%",
    "opponent_Leg% differential",
    "opponent_Leg% defense",
    "opponent_Distance%",
    "opponent_Distance% differential",
    "opponent_Distance% defense",
    "opponent_Clinch%",
    "opponent_Clinch% differential",
    "opponent_Clinch% defense",
    "opponent_Ground%",
    "opponent_Ground% differential",
    "opponent_Ground% defense",

    "Result",
    "date",
]

# GET ALL THE NAMES OF FIGHTERS ON EACH CARD
def extract_fighter_stats(
    input_csv_filename, output_csv_filename, fighter_name, opponent_name
):
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
    # else:
    #     print(f"Found {fighter_name} and {opponent_name}")

    if int(fighter_stats["totalfights"]) <= 1 or int(opponent_stats["totalfights"]) <= 1:
        return
    combined_stats = {}
    for key, value in fighter_stats.items():
        if key == "name":
            combined_stats["fighter_name"] = fighter_name
        else:
            combined_stats["fighter_" + key] = value


    for key, value in opponent_stats.items():
        if key == "name":
            combined_stats["opponent_name"] = opponent_name
        else:
            combined_stats["opponent_" + key] = value
        
    combined_stats["Result"] = "unknown"
    combined_stats["date"] = "unknown"

    # print(combined_stats)

    with open(output_csv_filename, mode="a", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writerow(combined_stats)

def predict_fight(fighter1_name, fighter2_name):
    print(f"Processing {fighter1_name} vs {fighter2_name}")
    with open(output_csv_filename, mode="w", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writeheader()
    extract_fighter_stats(
        input_csv_filename, output_csv_filename, fighter1_name, fighter2_name
    )
    extract_fighter_stats(
        input_csv_filename, output_csv_filename, fighter2_name, fighter1_name
    )

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
                if (event_url == "http://www.ufcstats.com/event-details/13a0fb8fbdafb54f"):
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
            extract_fighter_stats(
                input_csv_filename, output_csv_filename, fighter_name, opponent_name
            )
            extract_fighter_stats(
                input_csv_filename, output_csv_filename, opponent_name, fighter_name
            )

if __name__ == "__main__":
    main()