import csv
import random
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models import db, Fighter, Fight

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///detailedfighters.db"
db.init_app(app)

def query_fighter_by_name(name):
    fighter = Fighter.query.filter_by(name=name).first() 
    return fighter

file_path = 'data\modified_fight_details.csv'

def reverse_csv_to_dict(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        #return list(csv_reader)
        reversed_rows = list(csv_reader)[::-1]
        return reversed_rows

def get_csv_headers(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        return headers
    
# rating
K_FACTOR = 32

def calculate_expected_win_probability(rating_a, rating_b):
    return 1 / (1 + pow(10, (rating_b - rating_a) / 400))

def update_elo_ratings(rating_a, rating_b, result):
    expected_win_probability = calculate_expected_win_probability(rating_a, rating_b)

    if result == "win":
        actual_score = 1
    elif result == "loss":
        actual_score = 0
    else:  # Draw
        actual_score = 0.5

    new_rating_a = rating_a + K_FACTOR * (actual_score - expected_win_probability)
    new_rating_b = rating_b + K_FACTOR * ((1 - actual_score) - (1 - expected_win_probability))

    return new_rating_a, new_rating_b

def split_at_first_space(text):
    # Split the text by the first space
    parts = text.split(" ", 1)
    # Return both parts, before and after the first space
    return parts[0], parts[1] if len(parts) > 1 else ""
    
fighter_stats = dict()

fights = reverse_csv_to_dict(file_path)

all_fighters = set()
for fight in fights:
    Red = fight['Red Fighter']
    Blue = fight['Blue Fighter']
    all_fighters.add(Red)
    all_fighters.add(Blue)
    pass

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

with app.app_context():
    for fighter in all_fighters:
        fighter_stats[fighter] = {}
        for feature in feature_list:
            fighter_stats[fighter][feature]=0
            if feature in header_features:
                fighter_stats[fighter][f"{feature} differential"]=0
            if "%" in feature:
                fighter_stats[fighter][f"{feature} defense"]=0
        fighter_stats[fighter]["elo"]=1000
        # get DOB        
        fighter_object = query_fighter_by_name(fighter)
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

def processFight(fight, Red, Blue):
    winner = fight['Winner']
    Result='draw'
    if winner == Red:
        Result = 'win'
    elif winner == Blue:
        Result = 'loss'

    # switch = random.choice([True, False])
    # if switch:
    #     Red, Blue = Blue, Red 
    #     if Result == 'win':
    #         Result = 'loss'
    #     elif Result == 'loss':
    #         Result = 'win'

    processed_fight = {"Result": Result}
    if fighter_stats[Red]["totalfights"] >= 2 and fighter_stats[Blue]["totalfights"] >= 2:
        processed_fight['Red Fighter'] = Red
        processed_fight['Blue Fighter'] = Blue
        processed_fight['Title'] = fight['Title']
        for feature in feature_list:
            if feature in fighter_stats[Red] and feature in fighter_stats[Blue]:
                processed_fight[f'Red {feature}'] = fighter_stats[Red][feature]
                processed_fight[f'Blue {feature}'] = fighter_stats[Blue][feature]
                if feature in header_features:
                    processed_fight[f'Red {feature} differential'] = fighter_stats[Red][f'{feature} differential']
                    processed_fight[f'Blue {feature} differential'] = fighter_stats[Blue][f'{feature} differential']
                    processed_fight[f'Red {feature}'] /= sqrSum(fighter_stats[Red]["totalfights"])
                    processed_fight[f'Blue {feature}'] /= sqrSum(fighter_stats[Blue]["totalfights"])
                    processed_fight[f'Red {feature} differential'] /= sqrSum(fighter_stats[Red]["totalfights"])
                    processed_fight[f'Blue {feature} differential'] /= sqrSum(fighter_stats[Blue]["totalfights"])
                    if "%" in feature:
                        processed_fight[f'Red {feature} defense'] = sqrSum(fighter_stats[Red][f"{feature} defense"] / fighter_stats[Red]["totalfights"])
                        processed_fight[f'Blue {feature} defense'] = sqrSum(fighter_stats[Blue][f"{feature} defense"] / fighter_stats[Blue]["totalfights"])
                if feature in hardcoded_features_divide:
                    processed_fight[f'Red {feature}'] /= fighter_stats[Red]["totalfights"]
                    processed_fight[f'Blue {feature}'] /= fighter_stats[Blue]["totalfights"]
        for feature in feature_list:
            # Basic feature difference
            red_key = f'Red {feature}'
            blue_key = f'Blue {feature}'
            if red_key in processed_fight and blue_key in processed_fight:
                processed_fight[f'{feature} oppdiff'] = processed_fight[red_key] - processed_fight[blue_key]

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
    Red = fight['Red Fighter']
    Blue = fight['Blue Fighter']

    processFight(fight, Red, Blue)

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
    Result='draw'
    if winner == Red:
        Result = 'win'
    elif winner == Blue:
        Result = 'loss'

    title=False
    if "Title" in fight['Title']:
        title=True
    rating_a = fighter_stats[Red]["elo"]
    rating_b = fighter_stats[Blue]["elo"]
    fighter_stats[Red]["oppelo"]+=rating_b
    fighter_stats[Blue]["oppelo"]+=rating_a

    if Result=='win':
        fighter_stats[Blue]["losestreak"]+=1
        fighter_stats[Red]["losestreak"]=0
        fighter_stats[Red]["winstreak"]+=1
        fighter_stats[Blue]["winstreak"]=0
        fighter_stats[Red]["wins"]+=1 
        fighter_stats[Blue]["losses"]+=1
        if title:
            fighter_stats[Red]["titlewins"]+=1
    if Result=='loss':
        fighter_stats[Red]["losestreak"]+=1
        fighter_stats[Blue]["losestreak"]=0
        fighter_stats[Blue]["winstreak"]+=1
        fighter_stats[Red]["winstreak"]=0
        fighter_stats[Blue]["wins"]+=1 
        fighter_stats[Red]["losses"]+=1 
        if title:
            fighter_stats[Blue]["titlewins"]+=1

    new_rating_a, new_rating_b = update_elo_ratings(rating_a, rating_b, Result)
    fighter_stats[Red]["elo"]=new_rating_a
    fighter_stats[Blue]["elo"]=new_rating_b
    

def export_processed_fights(processed_fights, filename='data\detailed_fights.csv'):
    with open(filename, mode='w', newline='') as file:
        if processed_fights:  # check if the list is not empty
            headers = processed_fights[0].keys()  # Get the keys from the first dictionary as headers
            print(headers)
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            for fight in processed_fights:
                writer.writerow(fight)

def export_fighter_stats(fighter_stats, filename='data\detailed_fighter_stats.csv'):
    with open(filename, mode='w', newline='') as file:
        if fighter_stats:  # check if the dictionary is not empty
            example_fighter = next(iter(fighter_stats.values()))  # Get an example of the inner dictionary
            headers = ['Fighter'] + list(example_fighter.keys())  # 'Fighter' column plus each stat
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()

            for fighter, stats in fighter_stats.items():
                row = {'Fighter': fighter}  # Start with fighter name
                row.update(stats)  # Add the stats
                writer.writerow(row)

# Assuming your processed_fights and fighter_stats are ready
export_processed_fights(processed_fights)
export_fighter_stats(fighter_stats)

def write_to_text_file(data, file_path, is_fighter_stats=False):
    with open(file_path, 'w') as file:
        if is_fighter_stats:
            for fighter, stats in data.items():
                file.write(f"Fighter: {fighter}\n")
                for stat, value in stats.items():
                    file.write(f"  {stat}: {value}\n")
                file.write("\n")
        else:
            for fight in data:
                for key, value in fight.items():
                    file.write(f"{key}: {value}\n")
                file.write("\n")

# Paths for the output text files
processed_fights_txt_path = r'data\processed_fights_readable.txt'
fighter_stats_txt_path = r'data\fighter_stats_readable.txt'

# Write the processed fights and fighter stats to text files
write_to_text_file(processed_fights, processed_fights_txt_path)
write_to_text_file(fighter_stats, fighter_stats_txt_path, is_fighter_stats=True)

# Print paths to the generated files or handle further as needed
# print(f"Processed fights saved to {processed_fights_txt_path}")
# print(f"Fighter stats saved to {fighter_stats_txt_path}")

#TODO: STORE ALL THE PREVIOUS FIGHTS OF A FIGHTER. WHEN IT COMES TIME TO PROCESS, loop through the last 5 fights and compute the stats