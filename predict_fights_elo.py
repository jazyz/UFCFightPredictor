import csv
import requests
from bs4 import BeautifulSoup

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


input_csv_filename = "fighter_stats.csv"
output_csv_filename = "predict_fights_elo.csv"

with open(output_csv_filename, mode="w", newline="") as output_file:
    fieldnames = [
        "fighter_name",
        "fighter_kd_differential",
        "fighter_str_differential",
        "fighter_td_differential",
        "fighter_sub_differential",
        "fighter_winrate",
        "fighter_winstreak",
        "fighter_losestreak",
        "fighter_totalwins",
        "fighter_totalfights",
        "fighter_titlefights",
        "fighter_titlewins",
        "fighter_age_deviation",
        "fighter_opp_avg_elo",
        "fighter_elo",
        "fighter_dob",
        "opponent_name",
        "opponent_kd_differential",
        "opponent_str_differential",
        "opponent_td_differential",
        "opponent_sub_differential",
        "opponent_winrate",
        "opponent_winstreak",
        "opponent_losestreak",
        "opponent_totalwins",
        "opponent_totalfights",
        "opponent_titlefights",
        "opponent_titlewins",
        "opponent_age_deviation",
        "opponent_opp_avg_elo",
        "opponent_elo",
        "opponent_dob",
        "result",
        "date",
    ]
    csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    csv_writer.writeheader()


# fights = [
#     ["Alexa Grasso", "Valentina Shevchenko"],
#     ["Jack Della Maddalena", "Kevin Holland"],
#     ["Daniel Zellhuber", "Christos Giagos"],
#     ["Loopy Godinez","Elise Reed"],
#     ["Roman Kopylov","Josh Fremd"],
#     ["Edgar Chairez","Daniel Lacerda"],
#     ["Tracy Cortez","Jasmine Jasudavicius"],
# ]

# replace with correct url
url = "http://ufcstats.com/event-details/c945adc22c2bfe8f"

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
