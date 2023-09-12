import csv


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
    combined_stats["result"]="unknown"
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
            'opponent_name',
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
            "result"
        ]
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerow(combined_stats)


input_csv_filename = "fighter_stats.csv"
output_csv_filename = "predict_fights_elo.csv"
fighter_name = "Sean Strickland"
opponent_name = "Israel Adesanya"

extract_fighter_stats(
    input_csv_filename, output_csv_filename, fighter_name, opponent_name
)
extract_fighter_stats(
    input_csv_filename, output_csv_filename, opponent_name, fighter_name
)