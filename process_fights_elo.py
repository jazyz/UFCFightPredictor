from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///detailedfighters.db"
db = SQLAlchemy(app)

class Fighter(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String, nullable=False)
    record = db.Column(db.String)
    SLpM = db.Column(db.Float)
    Str_Acc = db.Column(db.String)
    SApM = db.Column(db.Float)
    Str_Def = db.Column(db.String)
    TD_Avg = db.Column(db.Float)
    TD_Acc = db.Column(db.String)
    TD_Def = db.Column(db.String)
    Sub_Avg = db.Column(db.Float)
    Height = db.Column(db.String)
    Weight = db.Column(db.String)
    Reach = db.Column(db.String)
    Stance = db.Column(db.String)
    DOB = db.Column(db.String)

    fights = db.relationship("Fight", back_populates="fighter")

class Fight(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    fighter_id = db.Column(db.Integer, db.ForeignKey('fighter.id'))
    result = db.Column(db.String)
    opponent = db.Column(db.String)
    fighterKD = db.Column(db.String)
    fighterSTR = db.Column(db.String)
    fighterTD = db.Column(db.String)
    fighterSUB = db.Column(db.String)
    opponentKD = db.Column(db.String)
    opponentSTR = db.Column(db.String)
    opponentTD = db.Column(db.String)
    opponentSUB = db.Column(db.String)
    titlefight = db.Column(db.Boolean)
    event = db.Column(db.String)
    date = db.Column(db.String)
    method = db.Column(db.String)
    round = db.Column(db.String)
    time = db.Column(db.String)

    fighter = db.relationship('Fighter', back_populates='fights')

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
    fighter_totalfights = db2.Column(db2.Integer)
    fighter_totalwins = db2.Column(db2.Integer)
    fighter_record = db2.Column(db2.String)
    fighter_titlefights = db2.Column(db2.Integer)
    fighter_titlewins = db2.Column(db2.Integer)
    fighter_elo = db2.Column(db2.Float)
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
    opponent_totalfights = db2.Column(db2.Integer)
    opponent_totalwins = db2.Column(db2.Integer)
    opponent_record = db2.Column(db2.String)    
    opponent_titlefights = db2.Column(db2.Integer)
    opponent_titlewins = db2.Column(db2.Integer)
    opponent_elo = db2.Column(db2.Float)
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
                "totalwins": 0,
                "totalfights": 0,
                "titlefights": 0,
                "titlewins": 0,
            }
            fighter_ids[fighter.name] = fighter.id

    with app.app_context():
        allfights = Fight.query.order_by(Fight.date).all()
        fights = []
        for fight in allfights:
            formatted_date = datetime.strptime(fight.date, "%b. %d, %Y")
            fights.append((formatted_date, fight))
        fights = sorted(fights, key=lambda x: x[0])
        for date, fight in fights:
            print(date)
            fighter_a = fight.fighter
            fighter_b = db.session.get(Fighter, fighter_ids[fight.opponent])
            
            flag = False
            with app2.app_context():
                # also chcek if fight already exists in db
                existing_fight = FightStats.query.filter_by(event=fight.event, fighter_name=fighter_b.name, opponent_name=fighter_a.name).first()
                if existing_fight:
                    flag = True
            # now add this fight stats to the database
            with app2.app_context():
                if fighter_stats[fighter_a.name]["totalfights"]>0 and fighter_stats[fighter_b.name]["totalfights"]>0:
                    processed_fight = FightStats(
                        event=fight.event,
                        date=fight.date,
                        fighter_name=fighter_a.name,
                        fighter_weight=fighter_a.Weight,
                        fighter_height=fighter_a.Height,
                        fighter_reach=fighter_a.Reach,
                        fighter_dob=fighter_a.DOB,
                        fighter_kd_differential = fighter_stats[fighter_a.name]["kd_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_str_differential = fighter_stats[fighter_a.name]["str_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_td_differential = fighter_stats[fighter_a.name]["td_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_sub_differential = fighter_stats[fighter_a.name]["sub_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_winrate = fighter_stats[fighter_a.name]["totalwins"]/fighter_stats[fighter_a.name]["totalfights"],
                        fighter_winstreak = fighter_stats[fighter_a.name]["winstreak"],
                        fighter_totalfights = fighter_stats[fighter_a.name]["totalfights"],
                        fighter_totalwins = fighter_stats[fighter_a.name]["totalwins"],
                        fighter_record = fighter_a.record,
                        fighter_titlefights = fighter_stats[fighter_a.name]["titlefights"],
                        fighter_titlewins = fighter_stats[fighter_a.name]["titlewins"],
                        fighter_elo = ratings[fighter_a.name],
                        opponent_name=fighter_b.name,
                        opponent_weight=fighter_b.Weight,
                        opponent_height=fighter_b.Height,
                        opponent_reach=fighter_b.Reach,
                        opponent_dob=fighter_b.DOB,
                        opponent_kd_differential = fighter_stats[fighter_b.name]["kd_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_str_differential = fighter_stats[fighter_b.name]["str_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_td_differential = fighter_stats[fighter_b.name]["td_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_sub_differential = fighter_stats[fighter_b.name]["sub_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_winrate = fighter_stats[fighter_b.name]["totalwins"]/fighter_stats[fighter_b.name]["totalfights"],
                        opponent_winstreak = fighter_stats[fighter_b.name]["winstreak"],
                        opponent_totalfights = fighter_stats[fighter_b.name]["totalfights"],
                        opponent_totalwins = fighter_stats[fighter_b.name]["totalwins"],
                        opponent_record = fighter_b.record,
                        opponent_titlefights = fighter_stats[fighter_b.name]["titlefights"],
                        opponent_titlewins = fighter_stats[fighter_b.name]["titlewins"],
                        opponent_elo = ratings[fighter_b.name],
                        result=fight.result,
                        method=fight.method,
                        round=fight.round,
                        time=fight.time,
                    )
                    db2.session.add(processed_fight)
                    db2.session.commit()
            if (not flag):
                rating_a = ratings[fighter_a.name]
                rating_b = ratings[fighter_b.name]
                result = fight.result.lower()
                
                new_rating_a, new_rating_b = update_elo_ratings(rating_a, rating_b, result)
                
                ratings[fighter_a.name] = new_rating_a
                ratings[fighter_b.name] = new_rating_b
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
                else:
                    fighter_stats[fighter_a.name]["winstreak"] = 0
                if fight.titlefight:
                    fighter_stats[fighter_a.name]["titlefights"] += 1
                    if fight.result=="win":
                        fighter_stats[fighter_a.name]["titlewins"] += 1
                
                if fight.opponentKD =="--" or fight.opponentSTR =="--" or fight.opponentTD =="--" or fight.opponentSUB =="--":
                    pass
                else:
                    fighter_stats[fighter_b.name]["kd_differential"] -= int(fight.fighterKD) - int(fight.opponentKD)
                    fighter_stats[fighter_b.name]["str_differential"] -= int(fight.fighterSTR) - int(fight.opponentSTR)
                    fighter_stats[fighter_b.name]["td_differential"] -= int(fight.fighterTD) - int(fight.opponentTD)
                    fighter_stats[fighter_b.name]["sub_differential"] -= int(fight.fighterSUB) - int(fight.opponentSUB)
                    fighter_stats[fighter_b.name]["totalfights"] += 1

                if fight.result=="lose":
                    fighter_stats[fighter_b.name]["winstreak"] += 1
                    fighter_stats[fighter_b.name]["totalwins"] += 1
                else:
                    fighter_stats[fighter_b.name]["winstreak"] = 0
                if fight.titlefight:
                    fighter_stats[fighter_b.name]["titlefights"] += 1
                    if fight.result=="lose":
                        fighter_stats[fighter_b.name]["titlewins"] += 1
            
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
                "fighter_totalfights",
                "fighter_totalwins",
                "fighter_record",
                "fighter_titlefights",
                "fighter_titlewins",
                "fighter_elo",
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
                "opponent_totalfights",
                "opponent_totalwins",
                "opponent_record",
                "opponent_titlefights",
                "opponent_titlewins",
                "opponent_elo",
                "result",
                "method",
                "round",
                "time",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for fight_stat in fight_stats:
                writer.writerow({
                    "id": fight_stat.id,
                    "event": fight_stat.event,
                    "date": fight_stat.date,
                    "fighter_name": fight_stat.fighter_name,
                    "fighter_weight": fight_stat.fighter_weight,
                    "fighter_height": fight_stat.fighter_height,
                    "fighter_reach": fight_stat.fighter_reach,
                    "fighter_dob": fight_stat.fighter_dob,
                    "fighter_kd_differential": fight_stat.fighter_kd_differential,
                    "fighter_str_differential": fight_stat.fighter_str_differential,
                    "fighter_td_differential": fight_stat.fighter_td_differential,
                    "fighter_sub_differential": fight_stat.fighter_sub_differential,
                    "fighter_winrate": fight_stat.fighter_winrate,
                    "fighter_winstreak": fight_stat.fighter_winstreak,
                    "fighter_totalfights": fight_stat.fighter_totalfights,
                    "fighter_totalwins": fight_stat.fighter_totalwins,
                    "fighter_record": fight_stat.fighter_record,
                    "fighter_titlefights": fight_stat.fighter_titlefights,
                    "fighter_titlewins": fight_stat.fighter_titlewins,
                    "fighter_elo": fight_stat.fighter_elo,
                    "opponent_name": fight_stat.opponent_name,
                    "opponent_weight": fight_stat.opponent_weight,
                    "opponent_height": fight_stat.opponent_height,
                    "opponent_reach": fight_stat.opponent_reach,
                    "opponent_dob": fight_stat.opponent_dob,
                    "opponent_kd_differential": fight_stat.opponent_kd_differential,
                    "opponent_str_differential": fight_stat.opponent_str_differential,
                    "opponent_td_differential": fight_stat.opponent_td_differential,
                    "opponent_sub_differential": fight_stat.opponent_sub_differential,
                    "opponent_winrate": fight_stat.opponent_winrate,
                    "opponent_winstreak": fight_stat.opponent_winstreak,
                    "opponent_totalfights": fight_stat.opponent_totalfights,
                    "opponent_totalwins": fight_stat.opponent_totalwins,
                    "opponent_record": fight_stat.opponent_record,
                    "opponent_titlefights": fight_stat.opponent_titlefights,
                    "opponent_titlewins": fight_stat.opponent_titlewins,
                    "opponent_elo": fight_stat.opponent_elo,
                    "result": fight_stat.result,
                    "method": fight_stat.method,
                    "round": fight_stat.round,
                    "time": fight_stat.time,
                })




































def predict_to_csv(filename):
    fights = [["Sean Strickland","Israel Adesanya"], ["Israel Adesanya", "Sean Strickland"], ["Dricus Du Plessis","Israel Adesanya"], ["Israel Adesanya", "Dricus Du Plessis"],]
    # fights = [["Michael Chandler", "Conor McGregor"], ["Conor McGregor", "Michael Chandler"]]
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
            "fighter_totalfights",
            "fighter_totalwins",
            "fighter_record",
            "fighter_titlefights",
            "fighter_titlewins",
            "fighter_elo",
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
            "opponent_totalfights",
            "opponent_totalwins",
            "opponent_record",
            "opponent_titlefights",
            "opponent_titlewins",
            "opponent_elo",
            "result",
            "method",
            "round",
            "time",
        ]
        with app.app_context():
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for fight in fights:
                fighter_a=Fighter.query.filter_by(name=fight[0]).first()
                fighter_b=Fighter.query.filter_by(name=fight[1]).first()
                fight_stat = FightStats(
                    event="unknown",
                    date="unknown",
                    fighter_name=fighter_a.name,
                    fighter_weight=fighter_a.Weight,
                    fighter_height=fighter_a.Height,
                    fighter_reach=fighter_a.Reach,
                    fighter_dob=fighter_a.DOB,
                    fighter_kd_differential = fighter_stats[fighter_a.name]["kd_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                    fighter_str_differential = fighter_stats[fighter_a.name]["str_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                    fighter_td_differential = fighter_stats[fighter_a.name]["td_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                    fighter_sub_differential = fighter_stats[fighter_a.name]["sub_differential"]/fighter_stats[fighter_a.name]["totalfights"],
                    fighter_winrate = fighter_stats[fighter_a.name]["totalwins"]/fighter_stats[fighter_a.name]["totalfights"],
                    fighter_winstreak = fighter_stats[fighter_a.name]["winstreak"],
                    fighter_totalfights = fighter_stats[fighter_a.name]["totalfights"],
                    fighter_totalwins = fighter_stats[fighter_a.name]["totalwins"],
                    fighter_record = fighter_a.record,
                    fighter_titlefights = fighter_stats[fighter_a.name]["titlefights"],
                    fighter_titlewins = fighter_stats[fighter_a.name]["titlewins"],
                    fighter_elo = ratings[fighter_a.name],
                    opponent_name=fighter_b.name,
                    opponent_weight=fighter_b.Weight,
                    opponent_height=fighter_b.Height,
                    opponent_reach=fighter_b.Reach,
                    opponent_dob=fighter_b.DOB,
                    opponent_kd_differential = fighter_stats[fighter_b.name]["kd_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                    opponent_str_differential = fighter_stats[fighter_b.name]["str_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                    opponent_td_differential = fighter_stats[fighter_b.name]["td_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                    opponent_sub_differential = fighter_stats[fighter_b.name]["sub_differential"]/fighter_stats[fighter_b.name]["totalfights"],
                    opponent_winrate = fighter_stats[fighter_b.name]["totalwins"]/fighter_stats[fighter_b.name]["totalfights"],
                    opponent_winstreak = fighter_stats[fighter_b.name]["winstreak"],
                    opponent_totalfights = fighter_stats[fighter_b.name]["totalfights"],
                    opponent_totalwins = fighter_stats[fighter_b.name]["totalwins"],
                    opponent_record = fighter_b.record,
                    opponent_titlefights = fighter_stats[fighter_b.name]["titlefights"],
                    opponent_titlewins = fighter_stats[fighter_b.name]["titlewins"],
                    opponent_elo = ratings[fighter_b.name],
                    result="unknown",
                    method="unknown",
                    round="unknown",
                    time="unknown",
                )

                writer.writerow({
                    "id": fight_stat.id,
                    "event": fight_stat.event,
                    "date": fight_stat.date,
                    "fighter_name": fight_stat.fighter_name,
                    "fighter_weight": fight_stat.fighter_weight,
                    "fighter_height": fight_stat.fighter_height,
                    "fighter_reach": fight_stat.fighter_reach,
                    "fighter_dob": fight_stat.fighter_dob,
                    "fighter_kd_differential": fight_stat.fighter_kd_differential,
                    "fighter_str_differential": fight_stat.fighter_str_differential,
                    "fighter_td_differential": fight_stat.fighter_td_differential,
                    "fighter_sub_differential": fight_stat.fighter_sub_differential,
                    "fighter_winrate": fight_stat.fighter_winrate,
                    "fighter_winstreak": fight_stat.fighter_winstreak,
                    "fighter_totalfights": fight_stat.fighter_totalfights,
                    "fighter_totalwins": fight_stat.fighter_totalwins,
                    "fighter_record": fight_stat.fighter_record,
                    "fighter_titlefights": fight_stat.fighter_titlefights,
                    "fighter_titlewins": fight_stat.fighter_titlewins,
                    "fighter_elo": fight_stat.fighter_elo,
                    "opponent_name": fight_stat.opponent_name,
                    "opponent_weight": fight_stat.opponent_weight,
                    "opponent_height": fight_stat.opponent_height,
                    "opponent_reach": fight_stat.opponent_reach,
                    "opponent_dob": fight_stat.opponent_dob,
                    "opponent_kd_differential": fight_stat.opponent_kd_differential,
                    "opponent_str_differential": fight_stat.opponent_str_differential,
                    "opponent_td_differential": fight_stat.opponent_td_differential,
                    "opponent_sub_differential": fight_stat.opponent_sub_differential,
                    "opponent_winrate": fight_stat.opponent_winrate,
                    "opponent_winstreak": fight_stat.opponent_winstreak,
                    "opponent_totalfights": fight_stat.opponent_totalfights,
                    "opponent_totalwins": fight_stat.opponent_totalwins,
                    "opponent_record": fight_stat.opponent_record,
                    "opponent_titlefights": fight_stat.opponent_titlefights,
                    "opponent_titlewins": fight_stat.opponent_titlewins,
                    "opponent_elo": fight_stat.opponent_elo,
                    "result": fight_stat.result,
                    "method": fight_stat.method,
                    "round": fight_stat.round,
                    "time": fight_stat.time,
                })

def main():
    with app2.app_context():
        db2.drop_all()
        db2.create_all()
    get_stats()
    export_to_csv("elofightstats.csv")
    predict_to_csv("predict_fights_elo.csv")
    return

if __name__ == "__main__":
    main()

