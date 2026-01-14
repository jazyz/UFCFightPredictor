"""
Process UFC event from ufcstats.com URL and generate predictions with betting recommendations
"""
import requests
from bs4 import BeautifulSoup
import csv
import os
import pandas as pd
import numpy as np
import joblib
import json

def get_csv_headers(file_path):
    with open(file_path, mode='r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        return headers

def split_at_first_space(text):
    parts = text.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""

def sqrSum(n):
    x = float(n)
    return x*(x+1)*(2*x+1)//6

# Constants
input_csv_filename = os.path.join("data", "detailed_fighter_stats.csv")
output_csv_filename = os.path.join("data", "event_predictions.csv")
fieldnames = get_csv_headers(os.path.join("data", "detailed_fights.csv"))

hardcoded_features = ["dob","totalfights","elo","losestreak","winstreak","titlewins"]
hardcoded_features_divide = ["oppelo","wins","losses", "avg age"]

feature_list = []
feature_list.extend(hardcoded_features)
feature_list.extend(hardcoded_features_divide)

file_path = os.path.join('data', 'modified_fight_details.csv')
headers = get_csv_headers(file_path)

header_features = []
for column in headers:
    s1, s2 = split_at_first_space(column)
    if s1 == "Red" and s2 != "Fighter":
        header_features.append(s2)

feature_list.extend(header_features)

def extract_fighter_stats(fighter_name, opponent_name):
    """Extract stats for both fighters"""
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
        return None

    if int(fighter_stats["totalfights"]) <= 1 or int(opponent_stats["totalfights"]) <= 1:
        return None

    return fighter_stats, opponent_stats

def process_fight(fighter_stats, opponent_stats):
    """Process fight data into model format"""
    from datetime import datetime
    
    processed_fight = {}
    processed_fight["Result"] = "unknown"
    processed_fight["Red Fighter"] = fighter_stats["Fighter"]
    processed_fight["Blue Fighter"] = opponent_stats["Fighter"]
    
    current_year = datetime.now().year
    current_date = datetime.now()
    date_format = "%Y-%m-%d %H:%M:%S"
    
    processed_fight['Red age'] = current_year - int(fighter_stats['dob'])
    processed_fight['Blue age'] = current_year - int(opponent_stats['dob'])
    processed_fight['age oppdiff'] = processed_fight['Red age'] - processed_fight['Blue age']
    
    processed_fight['Red last_fight'] = (current_date - datetime.strptime(fighter_stats["last_fight"], date_format)).days
    processed_fight['Blue last_fight'] = (current_date - datetime.strptime(opponent_stats["last_fight"], date_format)).days
    processed_fight['last_fight oppdiff'] = processed_fight['Red last_fight'] - processed_fight['Blue last_fight']
    
    for feature in feature_list:
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
        red_key = f'Red {feature}'
        blue_key = f'Blue {feature}'
        if red_key in processed_fight and blue_key in processed_fight:
            processed_fight[f'{feature} oppdiff'] = float(processed_fight[red_key]) - float(processed_fight[blue_key])

        red_diff_key = f'Red {feature} differential'
        blue_diff_key = f'Blue {feature} differential'
        if red_diff_key in processed_fight and blue_diff_key in processed_fight:
            processed_fight[f'{feature} differential oppdiff'] = float(processed_fight[red_diff_key]) - float(processed_fight[blue_diff_key])

        red_defense_key = f'Red {feature} defense'
        blue_defense_key = f'Blue {feature} defense'
        if red_defense_key in processed_fight and blue_defense_key in processed_fight:
            processed_fight[f'{feature} defense oppdiff'] = float(processed_fight[red_defense_key]) - float(processed_fight[blue_defense_key])

    return processed_fight

def scrape_event_fights(event_url):
    """Scrape fights from UFC stats event URL"""
    response = requests.get(event_url)
    
    if response.status_code != 200:
        return None, "Failed to retrieve the event page"
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Get event name
    event_name_tag = soup.find("h2", class_="b-content__title")
    event_name = event_name_tag.text.strip() if event_name_tag else "Unknown Event"
    
    fight_table = soup.find("tbody", class_="b-fight-details__table-body")
    
    if not fight_table:
        return None, "No fights found on this page"
    
    fight_rows = fight_table.find_all("tr", class_="b-fight-details__table-row")
    fights = []
    
    for fight_row in fight_rows:
        fighter_names = fight_row.find_all("a", class_="b-link_style_black")
        if len(fighter_names) >= 2:
            fighter1_name = fighter_names[0].text.strip()
            fighter2_name = fighter_names[1].text.strip()
            
            # Handle special cases
            if fighter1_name == "King Green":
                fighter1_name = "Bobby Green"
            if fighter2_name == "King Green":
                fighter2_name = "Bobby Green"
                
            fights.append([fighter1_name, fighter2_name])
    
    return fights, event_name

def predict_event(event_url):
    """
    Main function to predict all fights in an event
    Returns: dict with event info, predictions, and any errors
    """
    # Scrape fights from event
    result = scrape_event_fights(event_url)
    if result[0] is None:
        return {"error": result[1]}
    
    fights, event_name = result
    
    if len(fights) == 0:
        return {"error": "No fights found for this event"}
    
    # Prepare output CSV
    with open(output_csv_filename, mode="w", newline="") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        csv_writer.writeheader()
    
    # Process each fight
    processed_fights = []
    skipped_fights = []
    
    for fight in fights:
        fighter1_name = fight[0]
        fighter2_name = fight[1]
        
        # Process both permutations (Red vs Blue, Blue vs Red)
        stats1 = extract_fighter_stats(fighter1_name, fighter2_name)
        if stats1:
            processed = process_fight(stats1[0], stats1[1])
            with open(output_csv_filename, mode="a", newline="") as output_file:
                csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
                csv_writer.writerow(processed)
        else:
            if fighter1_name not in [s[0] for s in skipped_fights]:
                skipped_fights.append([fighter1_name, fighter2_name])
        
        stats2 = extract_fighter_stats(fighter2_name, fighter1_name)
        if stats2:
            processed = process_fight(stats2[0], stats2[1])
            with open(output_csv_filename, mode="a", newline="") as output_file:
                csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
                csv_writer.writerow(processed)
    
    # Load model and make predictions
    try:
        model = joblib.load(os.path.join("saved_models", "lgbm_single_model.joblib"))
        label_encoder = joblib.load(os.path.join("saved_preprocessing", "label_encoder_single.joblib"))
        with open(os.path.join("saved_preprocessing", "selected_columns_single.json"), "r") as f:
            selected_columns = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load model: {str(e)}"}
    
    # Make predictions
    new_data = pd.read_csv(output_csv_filename)
    X_new = new_data[selected_columns]
    X_new = X_new.drop(['Result', 'Date'], axis=1, errors='ignore')
    
    predicted_probabilities = model.predict_proba(X_new)
    predicted_classes = np.argmax(predicted_probabilities, axis=1)
    predicted_labels = label_encoder.inverse_transform(predicted_classes)
    
    new_data['Predicted Result'] = predicted_labels
    new_data['Red Fighter Win Probability'] = predicted_probabilities[:, 1]
    new_data['Blue Fighter Win Probability'] = predicted_probabilities[:, 0]
    
    # Format predictions
    predictions = []
    for idx, row in new_data.iterrows():
        predictions.append({
            "red_fighter": row['Red Fighter'],
            "blue_fighter": row['Blue Fighter'],
            "red_win_prob": float(row['Red Fighter Win Probability']),
            "blue_win_prob": float(row['Blue Fighter Win Probability']),
            "predicted_winner": row['Predicted Result']
        })
    
    # Try to get odds if available
    odds_data = get_event_odds(fights)
    
    return {
        "event_name": event_name,
        "event_url": event_url,
        "predictions": predictions,
        "odds": odds_data,
        "skipped_fights": skipped_fights
    }

def get_event_odds(fights):
    """
    Try to find odds for the event fights
    Returns dict of fighter pairs to odds
    """
    odds_file = os.path.join("data", "fight_results_with_odds.csv")
    
    if not os.path.exists(odds_file):
        return {}
    
    try:
        odds_df = pd.read_csv(odds_file)
        odds_dict = {}
        
        for fight in fights:
            fighter1 = fight[0]
            fighter2 = fight[1]
            
            # Try to find matching fights in odds file
            match = odds_df[
                ((odds_df['Red Fighter'] == fighter1) & (odds_df['Blue Fighter'] == fighter2)) |
                ((odds_df['Red Fighter'] == fighter2) & (odds_df['Blue Fighter'] == fighter1))
            ]
            
            if not match.empty:
                row = match.iloc[-1]  # Get most recent
                odds_dict[f"{fighter1} vs {fighter2}"] = {
                    "red_odds": float(row['Red Fighter Odds']) if pd.notna(row['Red Fighter Odds']) else None,
                    "blue_odds": float(row['Blue Fighter Odds']) if pd.notna(row['Blue Fighter Odds']) else None
                }
        
        return odds_dict
    except Exception as e:
        print(f"Error loading odds: {e}")
        return {}

if __name__ == "__main__":
    # Test with UFC 322
    test_url = "http://ufcstats.com/event-details/92c96df8bdab5fea"
    result = predict_event(test_url)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"\n{'='*70}")
        print(f"EVENT: {result['event_name']}")
        print(f"{'='*70}\n")
        
        for pred in result['predictions']:
            print(f"{pred['red_fighter']} vs {pred['blue_fighter']}")
            print(f"  → {pred['red_fighter']}: {pred['red_win_prob']:.2%}")
            print(f"  → {pred['blue_fighter']}: {pred['blue_win_prob']:.2%}")
            print(f"  → Predicted Winner: {pred['predicted_winner']}")
            print()
        
        if result['skipped_fights']:
            print(f"\nSkipped fights (insufficient data):")
            for fight in result['skipped_fights']:
                print(f"  - {fight[0]} vs {fight[1]}")
