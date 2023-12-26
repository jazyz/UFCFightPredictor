# process_fights_elo
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

app2 = Flask("elo")
app2.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///elofightstats.db"
db2 = SQLAlchemy(app2)
class FightStats(db2.Model):
    id = db2.Column(db2.Integer, primary_key=True, index=True)
    event = db2.Column(db2.String)
    date = db2.Column(db2.String)
    fighter_name = db2.Column(db2.String)
    fighter_weight = db2.Column(db2.String)
    fighter_height = db2.Column(db2.String)
    fighter_reach = db2.Column(db2.String)
    fighter_dob = db2.Column(db2.String)
    fighter_kd_differential = db2.Column(db2.Integer)
    fighter_str_differential = db2.Column(db2.Integer)
    fighter_td_differential = db2.Column(db2.Integer)
    fighter_sub_differential = db2.Column(db2.Integer)
    fighter_winrate = db2.Column(db2.Float)
    fighter_winstreak = db2.Column(db2.Integer)
    fighter_losestreak = db2.Column(db2.Integer)
    fighter_totalfights = db2.Column(db2.Integer)
    fighter_totalwins = db2.Column(db2.Integer)
    fighter_record = db2.Column(db2.String)
    fighter_titlefights = db2.Column(db2.Integer)
    fighter_titlewins = db2.Column(db2.Integer)
    fighter_age_deviation = db2.Column(db2.Float)
    fighter_elo = db2.Column(db2.Float)
    fighter_opp_avg_elo = db2.Column(db2.Float)
    fighter_kowin = db2.Column(db2.Integer)
    fighter_koloss = db2.Column(db2.Integer)
    fighter_subwin = db2.Column(db2.Integer)
    fighter_subloss = db2.Column(db2.Integer)
    fighter_udecwin = db2.Column(db2.Integer)
    fighter_udecloss = db2.Column(db2.Integer)
    fighter_sdecwin = db2.Column(db2.Integer)
    fighter_sdecloss = db2.Column(db2.Integer)
    fighter_mdecwin = db2.Column(db2.Integer)
    fighter_mdecloss = db2.Column(db2.Integer)

    opponent_name = db2.Column(db2.String)
    opponent_weight = db2.Column(db2.String)
    opponent_height = db2.Column(db2.String)
    opponent_reach = db2.Column(db2.String)
    opponent_dob = db2.Column(db2.String)
    opponent_kd_differential = db2.Column(db2.Integer)
    opponent_str_differential = db2.Column(db2.Integer)
    opponent_td_differential = db2.Column(db2.Integer)
    opponent_sub_differential = db2.Column(db2.Integer)
    opponent_winrate = db2.Column(db2.Float)
    opponent_winstreak = db2.Column(db2.Integer)
    opponent_losestreak = db2.Column(db2.Integer)
    opponent_totalfights = db2.Column(db2.Integer)
    opponent_totalwins = db2.Column(db2.Integer)
    opponent_record = db2.Column(db2.String)    
    opponent_titlefights = db2.Column(db2.Integer)
    opponent_titlewins = db2.Column(db2.Integer)
    opponent_age_deviation = db2.Column(db2.Float)
    opponent_elo = db2.Column(db2.Float)
    opponent_opp_avg_elo = db2.Column(db2.Float)
    opponent_kowin = db2.Column(db2.Integer)
    opponent_koloss = db2.Column(db2.Integer)
    opponent_subwin = db2.Column(db2.Integer)
    opponent_subloss = db2.Column(db2.Integer)
    opponent_udecwin = db2.Column(db2.Integer)
    opponent_udecloss = db2.Column(db2.Integer)
    opponent_sdecwin = db2.Column(db2.Integer)
    opponent_sdecloss = db2.Column(db2.Integer)
    opponent_mdecwin = db2.Column(db2.Integer)
    opponent_mdecloss = db2.Column(db2.Integer)

    result = db2.Column(db2.String)
    method = db2.Column(db2.String)
    round = db2.Column(db2.String)
    time = db2.Column(db2.String)

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
            print(date)
            if event_to_drop == date:
                print("Dropping event", event_to_drop)
                break
            fighter_a = fight.fighter
            fighter_b = db.session.get(Fighter, fighter_ids[fight.opponent])
            
            flag = False
            with app2.app_context():
                # also chcek if fight already exists in db
                fighthash=fighter_b.name+fighter_a.name+fight.event
                if fighthash in fightset:
                    flag = True
                    continue
            # now add this fight stats to the database
            with app2.app_context():
                if fighter_stats[fighter_a.name]["totalfights"]>0 and fighter_stats[fighter_b.name]["totalfights"]>0 and not flag:
                    processed_fight = FightStats(
                        event=fight.event,
                        date=fight.date,
                        fighter_name=fighter_a.name,
                        fighter_weight=fighter_a.Weight,
                        fighter_height=fighter_a.Height,
                        fighter_reach=fighter_a.Reach,
                        fighter_dob=fighter_a.DOB,
                        fighter_kd_differential=fighter_stats[fighter_a.name]["kd_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_str_differential=fighter_stats[fighter_a.name]["str_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_td_differential=fighter_stats[fighter_a.name]["td_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_sub_differential=fighter_stats[fighter_a.name]["sub_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_winrate=fighter_stats[fighter_a.name]["totalwins"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_winstreak=fighter_stats[fighter_a.name]["winstreak"],
                        fighter_losestreak=fighter_stats[fighter_a.name]["losestreak"],
                        fighter_totalfights=fighter_stats[fighter_a.name]["totalfights"],
                        fighter_totalwins=fighter_stats[fighter_a.name]["totalwins"],
                        fighter_record=fighter_a.record,
                        fighter_titlefights=fighter_stats[fighter_a.name]["titlefights"],
                        fighter_titlewins=fighter_stats[fighter_a.name]["titlewins"],
                        fighter_age_deviation=fighter_stats[fighter_a.name]["age_deviation"],
                        fighter_elo=ratings[fighter_a.name],
                        fighter_opp_avg_elo=fighter_stats[fighter_a.name]["opp_avg_elo"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_kowin=fighter_stats[fighter_a.name].get("kowin", 0),
                        fighter_koloss=fighter_stats[fighter_a.name].get("koloss", 0),
                        fighter_subwin=fighter_stats[fighter_a.name].get("subwin", 0),
                        fighter_subloss=fighter_stats[fighter_a.name].get("subloss", 0),
                        fighter_udecwin=fighter_stats[fighter_a.name].get("udecwin", 0),
                        fighter_udecloss=fighter_stats[fighter_a.name].get("udecloss", 0),
                        fighter_sdecwin=fighter_stats[fighter_a.name].get("sdecwin", 0),
                        fighter_sdecloss=fighter_stats[fighter_a.name].get("sdecloss", 0),
                        fighter_mdecwin=fighter_stats[fighter_a.name].get("mdecwin", 0),
                        fighter_mdecloss=fighter_stats[fighter_a.name].get("mdecloss", 0),

                        opponent_name=fighter_b.name,
                        opponent_weight=fighter_b.Weight,
                        opponent_height=fighter_b.Height,
                        opponent_reach=fighter_b.Reach,
                        opponent_dob=fighter_b.DOB,
                        opponent_kd_differential=fighter_stats[fighter_b.name]["kd_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_str_differential=fighter_stats[fighter_b.name]["str_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_td_differential=fighter_stats[fighter_b.name]["td_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_sub_differential=fighter_stats[fighter_b.name]["sub_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_winrate=fighter_stats[fighter_b.name]["totalwins"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_winstreak=fighter_stats[fighter_b.name]["winstreak"],
                        opponent_losestreak=fighter_stats[fighter_b.name]["losestreak"],
                        opponent_totalfights=fighter_stats[fighter_b.name]["totalfights"],
                        opponent_totalwins=fighter_stats[fighter_b.name]["totalwins"],
                        opponent_record=fighter_b.record,
                        opponent_titlefights=fighter_stats[fighter_b.name]["titlefights"],
                        opponent_titlewins=fighter_stats[fighter_b.name]["titlewins"],
                        opponent_age_deviation=fighter_stats[fighter_b.name]["age_deviation"],
                        opponent_elo=ratings[fighter_b.name],
                        opponent_opp_avg_elo=fighter_stats[fighter_b.name]["opp_avg_elo"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_kowin=fighter_stats[fighter_b.name].get("kowin", 0),
                        opponent_koloss=fighter_stats[fighter_b.name].get("koloss", 0),
                        opponent_subwin=fighter_stats[fighter_b.name].get("subwin", 0),
                        opponent_subloss=fighter_stats[fighter_b.name].get("subloss", 0),
                        opponent_udecwin=fighter_stats[fighter_b.name].get("udecwin", 0),
                        opponent_udecloss=fighter_stats[fighter_b.name].get("udecloss", 0),
                        opponent_sdecwin=fighter_stats[fighter_b.name].get("sdecwin", 0),
                        opponent_sdecloss=fighter_stats[fighter_b.name].get("sdecloss", 0),
                        opponent_mdecwin=fighter_stats[fighter_b.name].get("mdecwin", 0),
                        opponent_mdecloss=fighter_stats[fighter_b.name].get("mdecloss", 0),

                        result=fight.result,
                        method=fight.method,
                        round=fight.round,
                        time=fight.time,
                    )

                    db2.session.add(processed_fight)
                    db2.session.commit()
                    fighthash=fighter_a.name+fighter_b.name+fight.event
                    fightset.add(fighthash)
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
    with app2.app_context():
        db2.drop_all()
        db2.create_all()
    get_stats()



def export_to_csv(filename):
    with app2.app_context():
        fight_stats = FightStats.query.all()

        with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
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
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for fight_stat in fight_stats:
                # Create a dictionary where each key is a fieldname and the value is the corresponding attribute from fight_stat
                row_data = {fieldname: getattr(fight_stat, fieldname, None) for fieldname in fieldnames}
                writer.writerow(row_data)

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
    export_to_csv("elofightstats.csv")
    export_fighter_stats_to_csv("fighter_stats.csv")
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
