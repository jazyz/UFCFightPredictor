import csv
import random
import unicodedata
import argparse
from collections import defaultdict
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models import db, Fighter, Fight
import os
import pandas as pd

from utils.feature_sanitization import sanitize_age_features
from utils.name_matching import lookup_keys, normalize_name as normalize_fighter_name

random.seed(42)


def parse_args():
    parser = argparse.ArgumentParser(description="Build chronological fight feature tables.")
    parser.add_argument("--input-fights", default=os.path.join("data", "modified_fight_details.csv"))
    parser.add_argument("--output-features", default=os.path.join("data", "detailed_fights.csv"))
    parser.add_argument("--output-fighter-stats", default=os.path.join("data", "detailed_fighter_stats.csv"))
    parser.add_argument("--output-processed-readable", default=os.path.join("data", "processed_fights_readable.txt"))
    parser.add_argument("--output-fighter-readable", default=os.path.join("data", "fighter_stats_readable.txt"))
    parser.add_argument(
        "--include-excluded-dobs",
        action="store_true",
        help="keep DOB/age values for fighters listed in data/excluded_fighter_dobs.csv",
    )
    return parser.parse_args()


ARGS = parse_args()

# retrieve data from Flask database
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///detailedfighters.db"
db.init_app(app)

# ********** HELPER FUNCTIONS **********
fighter_lookup = {}


def valid_dob(value):
    return bool(value and str(value).strip() not in {"", "--"})


def build_fighter_lookup():
    lookup = {}
    for fighter in Fighter.query.all():
        for key in lookup_keys(fighter.name):
            current = lookup.get(key)
            if current is None or (not valid_dob(current.DOB) and valid_dob(fighter.DOB)):
                lookup[key] = fighter
    return lookup


def query_fighter_by_name(name):
    for key in lookup_keys(name):
        fighter = fighter_lookup.get(key)
        if fighter:
            return fighter
    fighter = Fighter.query.filter_by(name=name).first() 
    return fighter


def canonical_fighter_key(name):
    keys = lookup_keys(name)
    return keys[-1] if keys else normalize_fighter_name(name)

file_path = ARGS.input_fights

def parse_date_for_sort(date_string):
    if not date_string:
        return datetime.max

    for date_format in ("%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_string, date_format)
        except ValueError:
            continue

    return datetime.max


def csv_to_chronological_dict(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        rows = list(csv_reader)

    def normalize_name(name):
        ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
        return " ".join(ascii_name.strip().lower().split())

    def normalized_date(date_string):
        parsed = parse_date_for_sort(date_string)
        if parsed == datetime.max:
            return str(date_string).strip()
        return parsed.date().isoformat()

    unique_rows = []
    seen = set()
    for row in rows:
        key = (
            normalized_date(row.get('Date', '')),
            row.get('Title', ''),
            frozenset({
                normalize_name(row.get('Red Fighter', '')),
                normalize_name(row.get('Blue Fighter', '')),
            }),
            normalize_name(row.get('Winner', '')),
            row.get('Method', ''),
            row.get('Round', ''),
            row.get('Time', ''),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    return sorted(unique_rows, key=lambda row: parse_date_for_sort(row.get('Date', '')))

def get_csv_headers(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        return headers
    
def calculate_k_factor(number_of_fights):
    # Adjust K-factor based on the number of fights
    if number_of_fights < 5:
        return 40
    elif 5 <= number_of_fights < 10:
        return 35
    elif 10 <= number_of_fights < 20:
        return 30
    else:
        return 25

def calculate_expected_win_probability(rating_a, rating_b):
    return 1 / (1 + pow(10, (rating_b - rating_a) / 400))

def update_elo_ratings(rating_a, rating_b, result, fights_a, fights_b):
    K_FACTOR_A = calculate_k_factor(fights_a)
    K_FACTOR_B = calculate_k_factor(fights_b)

    expected_win_probability = calculate_expected_win_probability(rating_a, rating_b)

    if result == "win":
        actual_score = 1
    elif result == "loss":
        actual_score = 0
    else:  # Draw
        actual_score = 0.5

    new_rating_a = rating_a + K_FACTOR_A * (actual_score - expected_win_probability)
    new_rating_b = rating_b + K_FACTOR_B * ((1 - actual_score) - (1 - expected_win_probability))

    return new_rating_a, new_rating_b

def split_at_first_space(text):
    # Split the text by the first space
    parts = text.split(" ", 1)
    # Return both parts, before and after the first space
    return parts[0], parts[1] if len(parts) > 1 else ""
    
fighter_stats = dict()
fighter_display_names = dict()

fights = csv_to_chronological_dict(file_path)

fighter_raw_names = defaultdict(set)
for fight in fights:
    for fighter in (fight['Red Fighter'], fight['Blue Fighter']):
        fighter_raw_names[canonical_fighter_key(fighter)].add(fighter)

# retrieve all total strike numbers from head, body, leg, distance, clinch, ground, sig.str
# store it back into the dicts
headers=get_csv_headers(file_path)

hardcoded_features = ["dob","totalfights","elo","losestreak","winstreak","titlewins"]
hardcoded_features_divide = ["oppelo","wins","avg age"]
feature_list=[]
feature_list.extend(hardcoded_features)
feature_list.extend(hardcoded_features_divide)

header_features = []
for column in headers:
    s1,s2=split_at_first_space(column)
    if(s1=="Red" and s2!="Fighter"):
        header_features.append(s2)

feature_list.extend(header_features)

with app.app_context():
    fighter_lookup = build_fighter_lookup()
    for fighter, raw_names in fighter_raw_names.items():
        fighter_stats[fighter] = {}
        for feature in feature_list:
            fighter_stats[fighter][feature]=0
            if feature in header_features:
                fighter_stats[fighter][f"{feature} differential"]=0
            if "%" in feature:
                fighter_stats[fighter][f"{feature} defense"]=0
        fighter_stats[fighter]["elo"]=1000
        # get DOB        
        fighter_object = None
        for raw_name in sorted(raw_names):
            fighter_object = query_fighter_by_name(raw_name)
            if fighter_object:
                break
        fighter_display_names[fighter] = fighter_object.name if fighter_object else sorted(raw_names)[0]
        if fighter_object:
            date_format = "%b %d, %Y"  # Format like "Oct 01, 1990"
            try:
                dob = datetime.strptime(fighter_object.DOB, date_format)
                fighter_stats[fighter]["dob"] = dob.year
            except ValueError:
                fighter_stats[fighter]["dob"] = 0
            #print(fighter_object.DOB)

processed_fights=[]
count=0

def C2(x):
    return (x*(x+1))//2

def sqr(n):
    return n*n

def sqrSum(n):
    return n*(n+1)*(2*n+1)//6

def getTime(fight):
    return (float(fight['Round'])-1)*5 + float(fight['Time'])

def getDate(date_string, date_format):
    """Parse date with fallback for multiple formats"""
    try:
        return datetime.strptime(date_string, date_format)
    except ValueError:
        # Try alternative formats if primary fails
        alternative_formats = [
            "%Y-%m-%d",      # ISO format: 2025-10-11
            "%m/%d/%Y",      # US format: 10/11/2025
            "%B %d, %Y",     # Full month: December 16, 2023
            "%b %d, %Y"      # Short month: Dec 16, 2023
        ]
        for fmt in alternative_formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        return None
    
# PROCESS FIGHTS TO RED AND BLUE 
def processFight(fight, Red, Blue):
    winner = fight['Winner']
    Result='draw'
    red_key = canonical_fighter_key(Red)
    blue_key = canonical_fighter_key(Blue)
    winner_key = canonical_fighter_key(winner)
    if winner_key == red_key:
        Result = 'win'
    elif winner_key == blue_key:
        Result = 'loss'
    if Result == 'draw':
        return
    switch = random.choice([True, False])
    if switch:
        Red, Blue = Blue, Red 
        red_key, blue_key = blue_key, red_key
        if Result == 'win':
            Result = 'loss'
        elif Result == 'loss':
            Result = 'win'

    processed_fight = {"Result": Result}
    if fighter_stats[red_key]["totalfights"] >= 2 and fighter_stats[blue_key]["totalfights"] >= 2:
        processed_fight['Red Fighter'] = Red
        processed_fight['Blue Fighter'] = Blue
        processed_fight['Title'] = fight['Title']
        processed_fight['Date'] = fight['Date']
        fight_date=getDate(fight['Date'], "%B %d, %Y")
        
        # Skip this fight if date parsing failed
        if not fight_date:
            print(f"Warning: Could not parse date '{fight['Date']}' for fight {Red} vs {Blue}")
            return
        
        processed_fight['Red age'] = fight_date.year - fighter_stats[red_key]['dob']
        processed_fight['Blue age'] = fight_date.year - fighter_stats[blue_key]['dob']
        processed_fight['age oppdiff'] = processed_fight['Red age'] - processed_fight['Blue age'] 
        processed_fight['Red last_fight'] = (fight_date-fighter_stats[red_key]["last_fight"]).days
        processed_fight['Blue last_fight'] = (fight_date-fighter_stats[blue_key]["last_fight"]).days
        processed_fight['last_fight oppdiff'] = processed_fight['Red last_fight'] - processed_fight['Blue last_fight']
        for feature in feature_list:
            if feature in fighter_stats[red_key] and feature in fighter_stats[blue_key]:
                processed_fight[f'Red {feature}'] = fighter_stats[red_key][feature]
                processed_fight[f'Blue {feature}'] = fighter_stats[blue_key][feature]
                if feature in header_features:
                    red_weight = sqrSum(fighter_stats[red_key]["totalfights"])
                    blue_weight = sqrSum(fighter_stats[blue_key]["totalfights"])
                    processed_fight[f'Red {feature} differential'] = fighter_stats[red_key][f'{feature} differential']
                    processed_fight[f'Blue {feature} differential'] = fighter_stats[blue_key][f'{feature} differential']
                    processed_fight[f'Red {feature}'] /= red_weight
                    processed_fight[f'Blue {feature}'] /= blue_weight
                    processed_fight[f'Red {feature} differential'] /= red_weight
                    processed_fight[f'Blue {feature} differential'] /= blue_weight
                    if "%" in feature:
                        processed_fight[f'Red {feature} defense'] = fighter_stats[red_key][f"{feature} defense"] / red_weight
                        processed_fight[f'Blue {feature} defense'] = fighter_stats[blue_key][f"{feature} defense"] / blue_weight
                if feature in hardcoded_features_divide:
                    processed_fight[f'Red {feature}'] /= fighter_stats[red_key]["totalfights"]
                    processed_fight[f'Blue {feature}'] /= fighter_stats[blue_key]["totalfights"]
        for feature in feature_list:
            # Basic feature difference
            red_column = f'Red {feature}'
            blue_column = f'Blue {feature}'
            if red_column in processed_fight and blue_column in processed_fight:
                processed_fight[f'{feature} oppdiff'] = processed_fight[red_column] - processed_fight[blue_column]

            # Differential feature difference
            red_diff_key = f'Red {feature} differential'
            blue_diff_key = f'Blue {feature} differential'
            if red_diff_key in processed_fight and blue_diff_key in processed_fight:
                processed_fight[f'{feature} differential oppdiff'] = processed_fight[red_diff_key] - processed_fight[blue_diff_key]

            # Defense feature difference
            red_defense_key = f'Red {feature} defense'
            blue_defense_key = f'Blue {feature} defense'
            if red_defense_key in processed_fight and blue_defense_key in processed_fight:
                processed_fight[f'{feature} defense oppdiff'] = processed_fight[red_defense_key] - processed_fight[blue_defense_key]

        processed_fights.append(processed_fight)

print(header_features)
for fight in fights:
    count+=1
    red_name = fight['Red Fighter']
    blue_name = fight['Blue Fighter']
    Red = canonical_fighter_key(red_name)
    Blue = canonical_fighter_key(blue_name)

    processFight(fight, red_name, blue_name)

    ### update stats
    fighter_stats[Red]["totalfights"] += 1
    fighter_stats[Blue]["totalfights"] += 1
    redfights = fighter_stats[Red]["totalfights"] 
    bluefights = fighter_stats[Blue]["totalfights"] 
    for feature in feature_list:
        if feature in hardcoded_features or feature in hardcoded_features_divide:
            continue
        red_feature_key = "Red " + feature
        blue_feature_key = "Blue " + feature
        try:
            red_value = float(fight[red_feature_key])
            blue_value = float(fight[blue_feature_key])
            
            if "%" in feature:
                fighter_stats[Red][f"{feature} differential"] += (red_value - blue_value) * sqr(redfights)
                fighter_stats[Blue][f"{feature} differential"] += (blue_value - red_value) * sqr(bluefights)
            else:
                fighter_stats[Red][f"{feature} differential"] += (red_value - blue_value) * sqr(redfights) 
                fighter_stats[Blue][f"{feature} differential"] += (blue_value - red_value) * sqr(bluefights) 
            
            fighter_stats[Red][f"{feature}"] += red_value * sqr(redfights) / getTime(fight)
            fighter_stats[Blue][f"{feature}"] += blue_value * sqr(bluefights) / getTime(fight)
            if "%" in feature:
                fighter_stats[Red][f"{feature} defense"] += (1 - blue_value) * sqr(redfights)
                fighter_stats[Blue][f"{feature} defense"] += (1 - red_value) * sqr(bluefights)
        except:
            pass
    winner = fight['Winner']
    winner_key = canonical_fighter_key(winner)
    Result='draw'
    if winner_key == Red:
        Result = 'win'
    elif winner_key == Blue:
        Result = 'loss'

    title=False
    if "Title" in fight['Title']:
        title=True
    rating_a = fighter_stats[Red]["elo"]
    rating_b = fighter_stats[Blue]["elo"]
    fighter_stats[Red]["oppelo"]+=rating_b
    fighter_stats[Blue]["oppelo"]+=rating_a
    fight_date=getDate(fight['Date'], "%B %d, %Y")
    
    # Skip updating date-dependent stats if date parsing failed
    if not fight_date:
        print(f"Warning: Could not parse date '{fight['Date']}' for ELO update {Red} vs {Blue}")
        # Still update ELO but skip date-dependent features
    else:
        fighter_stats[Red]["last_fight"]=fight_date
        fighter_stats[Blue]["last_fight"]=fight_date
        fighter_stats[Red]["avg age"]+=fight_date.year-fighter_stats[Red]["dob"]
        fighter_stats[Blue]["avg age"]+=fight_date.year-fighter_stats[Blue]["dob"]
    if Result=='win':
        fighter_stats[Blue]["losestreak"]+=1
        fighter_stats[Red]["losestreak"]=0
        fighter_stats[Red]["winstreak"]+=1
        fighter_stats[Blue]["winstreak"]=0
        fighter_stats[Red]["wins"]+=1 
        if title:
            fighter_stats[Red]["titlewins"]+=1
    if Result=='loss':
        fighter_stats[Red]["losestreak"]+=1
        fighter_stats[Blue]["losestreak"]=0
        fighter_stats[Blue]["winstreak"]+=1
        fighter_stats[Red]["winstreak"]=0
        fighter_stats[Blue]["wins"]+=1 
        if title:
            fighter_stats[Blue]["titlewins"]+=1

    new_rating_a, new_rating_b = update_elo_ratings(rating_a, rating_b, Result, redfights, bluefights)
    fighter_stats[Red]["elo"]=new_rating_a
    fighter_stats[Blue]["elo"]=new_rating_b
    

def export_processed_fights(processed_fights, filename=os.path.join('data', 'detailed_fights.csv')):
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, mode='w', newline='') as file:
        if processed_fights:  # check if the list is not empty
            headers = processed_fights[0].keys()  # Get the keys from the first dictionary as headers
            print(headers)
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            for fight in processed_fights:
                writer.writerow(fight)

def export_fighter_stats(fighter_stats, filename=os.path.join('data', 'detailed_fighter_stats.csv')):
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, mode='w', newline='') as file:
        if fighter_stats:  # check if the dictionary is not empty
            example_fighter = next(iter(fighter_stats.values()))  # Get an example of the inner dictionary
            headers = ['Fighter'] + list(example_fighter.keys())  # 'Fighter' column plus each stat
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()

            for fighter, stats in fighter_stats.items():
                row = {'Fighter': fighter_display_names.get(fighter, fighter)}  # Start with fighter name
                row.update(stats)  # Add the stats
                writer.writerow(row)

# Keep any still-missing DOBs from becoming impossible age outliers in exports.
if processed_fights:
    excluded_dob_names = set() if ARGS.include_excluded_dobs else None
    processed_fights = sanitize_age_features(
        pd.DataFrame(processed_fights),
        excluded_dob_names=excluded_dob_names,
    ).to_dict("records")

# Assuming your processed_fights and fighter_stats are ready
export_processed_fights(processed_fights, ARGS.output_features)
export_fighter_stats(fighter_stats, ARGS.output_fighter_stats)

def write_to_text_file(data, file_path, is_fighter_stats=False):
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, 'w') as file:
        if is_fighter_stats:
            for fighter, stats in data.items():
                file.write(f"Fighter: {fighter_display_names.get(fighter, fighter)}\n")
                for stat, value in stats.items():
                    file.write(f"  {stat}: {value}\n")
                file.write("\n")
        else:
            for fight in data:
                for key, value in fight.items():
                    file.write(f"{key}: {value}\n")
                file.write("\n")

# Paths for the output text files
processed_fights_txt_path = ARGS.output_processed_readable
fighter_stats_txt_path = ARGS.output_fighter_readable

# Write the processed fights and fighter stats to text files
write_to_text_file(processed_fights, processed_fights_txt_path)
write_to_text_file(fighter_stats, fighter_stats_txt_path, is_fighter_stats=True)

# Print paths to the generated files or handle further as needed
# print(f"Processed fights saved to {processed_fights_txt_path}")
# print(f"Fighter stats saved to {fighter_stats_txt_path}")

#TODO: STORE ALL THE PREVIOUS FIGHTS OF A FIGHTER. WHEN IT COMES TIME TO PROCESS, loop through the last 5 fights and compute the stats
