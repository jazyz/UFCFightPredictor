# get all the fighters from each card and put them in predict_fights_elo.csv 

import requests
from bs4 import BeautifulSoup
import csv

input_csv_filename = "fighter_stats.csv"
output_csv_filename = "predict_fights_elo.csv"

fieldnames = [
    "id",
    "event",
    "date",
    "fighter_name",
    "fighter_weight",
    "fighter_height",
    "fighter_reach",
    "fighter_dob",
    "fighter_kd_differential",
    "fighter_str_differential",
    "fighter_td_differential",
    "fighter_sub_differential",
    "fighter_winrate",
    "fighter_winstreak",
    "fighter_losestreak",
    "fighter_totalfights",
    "fighter_totalwins",
    "fighter_record",
    "fighter_titlefights",
    "fighter_titlewins",
    "fighter_age_deviation",
    "fighter_elo",
    "fighter_opp_avg_elo",
    
    "fighter_kowin",
    "fighter_koloss",
    "fighter_subwin",
    "fighter_subloss",
    "fighter_udecwin",
    "fighter_udecloss",
    "fighter_sdecwin",
    "fighter_sdecloss",
    "fighter_mdecwin",
    "fighter_mdecloss",

    "opponent_name",
    "opponent_weight",
    "opponent_height",
    "opponent_reach",
    "opponent_dob",
    "opponent_kd_differential",
    "opponent_str_differential",
    "opponent_td_differential",
    "opponent_sub_differential",
    "opponent_winrate",
    "opponent_winstreak",
    "opponent_losestreak",
    "opponent_totalfights",
    "opponent_totalwins",
    "opponent_record",
    "opponent_titlefights",
    "opponent_titlewins",
    "opponent_age_deviation",
    "opponent_elo",
    "opponent_opp_avg_elo",
    "opponent_kowin",
    "opponent_koloss",
    "opponent_subwin",
    "opponent_subloss",
    "opponent_udecwin",
    "opponent_udecloss",
    "opponent_sdecwin",
    "opponent_sdecloss",
    "opponent_mdecwin",
    "opponent_mdecloss",

    "result",
    "method",
    "round",
    "time",
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
            if row["name"] == fighter_name:
                fighter_stats = row
            elif row["name"] == opponent_name:
                opponent_stats = row

    if fighter_stats is None or opponent_stats is None:
        print("Fighter or opponent not found in the CSV.")
        return

    if int(fighter_stats["totalfights"]) <= 4 or int(opponent_stats["totalfights"]) <= 4:
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
    combined_stats["result"] = "unknown"
    combined_stats["date"] = "unknown"
    with open(output_csv_filename, mode="a", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writerow(combined_stats)

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
                if (event_url == "http://www.ufcstats.com/event-details/d2fa318f34d0aadc"):
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


def process(fighter1_name, fighter2_name):
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


if __name__ == "__main__":
    main()