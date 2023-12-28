# Instead of recomputing stats every time, read the current stats from elofights.csv into fighter_stats dict. Then, update them from a certain start date to end date.
# Then also write the new fights into the db without overwriting the previous info.# process_fights_elo
# this file is used to process the fights and create features for the model
# during testing this file updates all fighter's stats after a certain period of time

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv
from models import db, Fighter, Fight
import sys

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///detailedfighters.db"
db.init_app(app)

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

fighter_stats = dict()
fighter_ids = dict()
ratings = dict()

def get_stats():
    with app.app_context():
        fighters = Fighter.query.all()
        for fighter in fighters:
            ratings[fighter.name]=1000
            fighter_stats[fighter.name] = {
                "kd_differential": 0,
                "str_differential": 0,
                "td_differential": 0,
                "sub_differential": 0,
                "winrate": 0,
                "winstreak": 0,
                "losestreak": 0,
                "totalwins": 0,
                "totalfights": 0,
                "titlefights": 0,
                "titlewins": 0,
                "age_deviation": 0,
                "opp_avg_elo": 0,
                "kowin": 0,
                "koloss": 0,
                "subwin": 0,
                "subloss": 0,
                "udecwin": 0,
                "udecloss": 0,
                "sdecwin": 0,
                "sdecloss": 0,
                "mdecwin": 0,
                "mdecloss": 0,
                "dob": fighter.DOB,
            }
            fighter_ids[fighter.name] = fighter.id
    fightset=set()
    with app.app_context():
        allfights = Fight.query.order_by(Fight.date).all()
        fights = []
        for fight in allfights:
            formatted_date = datetime.strptime(fight.date, "%b. %d, %Y")
            fights.append((formatted_date, fight))
        fights = sorted(fights, key=lambda x: x[0])
        for date, fight in fights:
            # if fight.event == event_to_drop:
            #     print("Dropping event", event_to_drop)
            #     break
            #print(date)
            if event_to_drop == date:
                print("Dropping event", event_to_drop)
                break
            fighter_a = fight.fighter
            fighter_b = db.session.get(Fighter, fighter_ids[fight.opponent])
            
            flag = False
            
            fighthash=fighter_b.name+fighter_a.name+fight.event
            if fighthash in fightset:
                flag = True
                continue
            
            if (not flag):
                rating_a = ratings[fighter_a.name]
                rating_b = ratings[fighter_b.name]
                result = fight.result.lower()
                
                new_rating_a, new_rating_b = update_elo_ratings(rating_a, rating_b, result)
                
                ratings[fighter_a.name] = new_rating_a
                ratings[fighter_b.name] = new_rating_b
    
                prime_age = 25 * 365
                fight_date_object = datetime.strptime(fight.date, "%b. %d, %Y")
                # Change fighter a's stats
                try:
                    a_date_object = datetime.strptime(fighter_a.DOB, "%b %d, %Y")
                    age_a = (fight_date_object - a_date_object).days
                    fighter_stats[fighter_a.name]["age_deviation"] = abs(age_a - prime_age)
                # If DOB is --
                except: 
                    fighter_stats[fighter_a.name]["age_deviation"] = 5*365

                if fight.fighterKD =="--" or fight.fighterSTR =="--" or fight.fighterTD =="--" or fight.fighterSUB =="--":
                    pass
                else:
                    fighter_stats[fighter_a.name]["kd_differential"] += int(fight.fighterKD) - int(fight.opponentKD)
                    fighter_stats[fighter_a.name]["str_differential"] += int(fight.fighterSTR) - int(fight.opponentSTR)
                    fighter_stats[fighter_a.name]["td_differential"] += int(fight.fighterTD) - int(fight.opponentTD)
                    fighter_stats[fighter_a.name]["sub_differential"] += int(fight.fighterSUB) - int(fight.opponentSUB)
                   
                fighter_stats[fighter_a.name]["totalfights"] += 1
                if fight.result=="win":
                    fighter_stats[fighter_a.name]["winstreak"] += 1
                    fighter_stats[fighter_a.name]["totalwins"] += 1
                    fighter_stats[fighter_a.name]["losestreak"] = 0
                    if fight.method == "KO/TKO":
                        fighter_stats[fighter_a.name]["kowin"] += 1
                    elif fight.method == "SUB":
                        fighter_stats[fighter_a.name]["subwin"] += 1
                    elif fight.method == "U-DEC":
                        fighter_stats[fighter_a.name]["udecwin"] += 1
                    elif fight.method == "S-DEC":
                        fighter_stats[fighter_a.name]["sdecwin"] += 1
                    elif fight.method == "M-DEC":
                        fighter_stats[fighter_a.name]["mdecwin"] += 1
                elif fight.result=="loss":
                    fighter_stats[fighter_a.name]["losestreak"] += 1
                    fighter_stats[fighter_a.name]["winstreak"] = 0
                    if fight.method == "KO/TKO":
                        fighter_stats[fighter_a.name]["koloss"] += 1
                    elif fight.method == "SUB":
                        fighter_stats[fighter_a.name]["subloss"] += 1
                    elif fight.method == "U-DEC":
                        fighter_stats[fighter_a.name]["udecloss"] += 1
                    elif fight.method == "S-DEC":
                        fighter_stats[fighter_a.name]["sdecloss"] += 1
                    elif fight.method == "M-DEC":
                        fighter_stats[fighter_a.name]["mdecloss"] += 1

                if fight.titlefight:
                    fighter_stats[fighter_a.name]["titlefights"] += 1
                    if fight.result=="win":
                        fighter_stats[fighter_a.name]["titlewins"] += 1

                fighter_stats[fighter_a.name]["opp_avg_elo"] += ratings[fighter_b.name]
                
                # Change fighter b's stats
                try:
                    b_date_object = datetime.strptime(fighter_b.DOB, "%b %d, %Y")
                    age_b = (fight_date_object - b_date_object).days
                    fighter_stats[fighter_b.name]["age_deviation"] = abs(age_b - prime_age)
                except:
                    fighter_stats[fighter_b.name]["age_deviation"] = 5*365

                if fight.opponentKD =="--" or fight.opponentSTR =="--" or fight.opponentTD =="--" or fight.opponentSUB =="--":
                    pass
                else:
                    fighter_stats[fighter_b.name]["kd_differential"] -= int(fight.fighterKD) - int(fight.opponentKD)
                    fighter_stats[fighter_b.name]["str_differential"] -= int(fight.fighterSTR) - int(fight.opponentSTR)
                    fighter_stats[fighter_b.name]["td_differential"] -= int(fight.fighterTD) - int(fight.opponentTD)
                    fighter_stats[fighter_b.name]["sub_differential"] -= int(fight.fighterSUB) - int(fight.opponentSUB)

                fighter_stats[fighter_b.name]["totalfights"] += 1
                if fight.result=="loss":
                    fighter_stats[fighter_b.name]["winstreak"] += 1
                    fighter_stats[fighter_b.name]["totalwins"] += 1
                    fighter_stats[fighter_b.name]["losestreak"] = 0
                    if fight.method == "KO/TKO":
                        fighter_stats[fighter_b.name]["koloss"] += 1
                    elif fight.method == "SUB":
                        fighter_stats[fighter_b.name]["subloss"] += 1
                    elif fight.method == "U-DEC":
                        fighter_stats[fighter_b.name]["udecloss"] += 1
                    elif fight.method == "S-DEC":
                        fighter_stats[fighter_b.name]["sdecloss"] += 1
                    elif fight.method == "M-DEC":
                        fighter_stats[fighter_b.name]["mdecloss"] += 1
                elif fight.result=="win":
                    fighter_stats[fighter_b.name]["losestreak"] += 1
                    fighter_stats[fighter_b.name]["winstreak"] = 0
                    if fight.method == "KO/TKO":
                        fighter_stats[fighter_b.name]["kowin"] += 1
                    elif fight.method == "SUB":
                        fighter_stats[fighter_b.name]["subwin"] += 1
                    elif fight.method == "U-DEC":
                        fighter_stats[fighter_b.name]["udecwin"] += 1
                    elif fight.method == "S-DEC":
                        fighter_stats[fighter_b.name]["sdecwin"] += 1
                    elif fight.method == "M-DEC":
                        fighter_stats[fighter_b.name]["mdecwin"] += 1
                if fight.titlefight:
                    fighter_stats[fighter_b.name]["titlefights"] += 1
                    if fight.result=="loss":
                        fighter_stats[fighter_b.name]["titlewins"] += 1
                
                fighter_stats[fighter_b.name]["opp_avg_elo"] += ratings[fighter_a.name]
            
# when looking at past events, drop the event
event_to_drop = ""
# find event names here: http://www.ufcstats.com/statistics/events/completed
def create_all_tables():
    get_stats()

def export_fighter_stats_to_csv(filename):
    with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "name",
            "kd_differential",
            "str_differential",
            "td_differential",
            "sub_differential",
            "winrate",
            "winstreak",
            "losestreak",
            "totalwins",
            "totalfights",
            "titlefights",
            "titlewins",
            "age_deviation",
            "opp_avg_elo",
            "elo",
            "dob",
            "kowin",
            "koloss",
            "subwin",
            "subloss",
            "udecwin",
            "udecloss",
            "mdecwin",
            "mdecloss",
            "sdecwin",
            "sdecloss",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for fighter_name, stats in fighter_stats.items():
            writer.writerow({
                "name": fighter_name,
                "kd_differential": stats["kd_differential"] / stats["totalfights"] if stats["totalfights"] > 0 else 0,
                "str_differential": stats["str_differential"] / stats["totalfights"] if stats["totalfights"] > 0 else 0,
                "td_differential": stats["td_differential"] / stats["totalfights"] if stats["totalfights"] > 0 else 0,
                "sub_differential": stats["sub_differential"] / stats["totalfights"] if stats["totalfights"] > 0 else 0,
                "winrate": stats["totalwins"] / stats["totalfights"] if stats["totalfights"] > 0 else 0,
                "winstreak": stats["winstreak"],
                "losestreak": stats["losestreak"],
                "totalwins": stats["totalwins"],
                "totalfights": stats["totalfights"],
                "titlefights": stats["titlefights"],
                "titlewins": stats["titlewins"],
                "age_deviation": stats["age_deviation"],
                "opp_avg_elo": stats["opp_avg_elo"] / stats["totalfights"] if stats["totalfights"] > 0 else 0,
                "elo": ratings.get(fighter_name, 0),
                "dob": stats["dob"],
                "kowin": stats.get("kowin", 0),
                "koloss": stats.get("koloss", 0),
                "subwin": stats.get("subwin", 0),
                "subloss": stats.get("subloss", 0),
                "udecwin": stats.get("udecwin", 0),
                "udecloss": stats.get("udecloss", 0),
                "mdecwin": stats.get("mdecwin", 0),
                "mdecloss": stats.get("mdecloss", 0),
                "sdecwin": stats.get("sdecwin", 0),
                "sdecloss": stats.get("sdecloss", 0),
            })

def main():
    create_all_tables()
    export_fighter_stats_to_csv(r"oldModel\fighter_stats.csv")
    sorted_ratings = sorted(ratings.items(), key=lambda x:x[1], reverse=True)
    cnt=0
    for name, rating in sorted_ratings:
        # print(name,rating)
        cnt+=1
        if(cnt==30):
            break
    return

if __name__ == "__main__":
    main()
