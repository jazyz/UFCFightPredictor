import csv
import random

file_path = 'modified_fight_details.csv'

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

feature_list=["totalfights","elo"]

for column in headers:
    s1,s2=split_at_first_space(column)
    if(s1=="Red" and s2!="Fighter"):
        feature_list.append(s2)

for fighter in all_fighters:
    fighter_stats[fighter] = {}
    for feature in feature_list:
        fighter_stats[fighter][feature]=0
    fighter_stats[fighter]["elo"]=1000

processed_fights=[]
count=0

def processFight(fight, Red, Blue):
    if fighter_stats[Red]["totalfights"]>=0 and fighter_stats[Blue]["totalfights"]>=0:
        winner = fight['Winner']
        Result='draw'
        if winner == Red:
            Result = 'win'
        elif winner == Blue:
            Result = 'loss'

        switch = random.choice([True, False])
        if switch:
            Red, Blue = Blue, Red 
            if Result == 'win':
                Result = 'loss'
            elif Result == 'loss':
                Result = 'win'

        processed_fight = {"Result": Result}
        if fighter_stats[Red]["totalfights"] >= 3 and fighter_stats[Blue]["totalfights"] >= 3:
            for feature in feature_list:
                if feature in fighter_stats[Red] and feature in fighter_stats[Blue]:
                    processed_fight[f'Red {feature}'] = fighter_stats[Red][feature]
                    processed_fight[f'Blue {feature}'] = fighter_stats[Blue][feature]
                    if feature != "elo" and feature != "totalfights":
                        processed_fight[f'Red {feature}'] /= fighter_stats[Red]["totalfights"]
                        processed_fight[f'Blue {feature}'] /= fighter_stats[Blue]["totalfights"]
            processed_fight['Red Fighter'] = Red
            processed_fight['Blue Fighter'] = Blue
            processed_fight['Title'] = fight['Title']
            processed_fights.append(processed_fight)

        rating_a = fighter_stats[Red]["elo"]
        rating_b = fighter_stats[Blue]["elo"]
        new_rating_a, new_rating_b = update_elo_ratings(rating_a, rating_b, Result)
        fighter_stats[Red]["elo"]=new_rating_a
        fighter_stats[Blue]["elo"]=new_rating_b

for fight in fights:
    count+=1
    Red = fight['Red Fighter']
    Blue = fight['Blue Fighter']

    
    processFight(fight, Red, Blue)
        # update more features
    for feature in feature_list:
        if feature=="elo" or feature=="totalfights":
            continue
        red_feature_key = "Red " + feature
        blue_feature_key = "Blue " + feature
        try:
            red_value = float(fight[red_feature_key])
            blue_value = float(fight[blue_feature_key])
            fighter_stats[Red][feature] += (red_value - blue_value)
            #fighter_stats[Red][feature] *= fighter_stats[Blue]["elo"]
            fighter_stats[Blue][feature] += (blue_value - red_value)
            #fighter_stats[Blue][feature] *= fighter_stats[Red]["elo"]
        except:
            pass

    fighter_stats[Red]["totalfights"] += 1
    fighter_stats[Blue]["totalfights"] += 1

def export_processed_fights(processed_fights, filename='detailed_fights.csv'):
    with open(filename, mode='w', newline='') as file:
        if processed_fights:  # check if the list is not empty
            headers = processed_fights[0].keys()  # Get the keys from the first dictionary as headers
            print(headers)
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            for fight in processed_fights:
                writer.writerow(fight)

def export_fighter_stats(fighter_stats, filename='detailed_fighter_stats.csv'):
    with open(filename, mode='w', newline='') as file:
        if fighter_stats:  # check if the dictionary is not empty
            example_fighter = next(iter(fighter_stats.values()))  # Get an example of the inner dictionary
            headers = ['Fighter'] + list(example_fighter.keys())  # 'Fighter' column plus each stat
            print(headers)
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()

            for fighter, stats in fighter_stats.items():
                row = {'Fighter': fighter}  # Start with fighter name
                row.update(stats)  # Add the stats
                writer.writerow(row)

# Assuming your processed_fights and fighter_stats are ready
export_processed_fights(processed_fights)
export_fighter_stats(fighter_stats)
