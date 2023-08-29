from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import csv
import re

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///detailedfighters.db"
db = SQLAlchemy(app)

class Fighter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
    id = db.Column(db.Integer, primary_key=True)
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

app2 = Flask("processfightsdynamic")
app2.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///predictfight.db"
db2 = SQLAlchemy(app2)

class FightStats(db2.Model):
    id = db2.Column(db2.Integer, primary_key=True)
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
    result = db2.Column(db2.String)
    method = db2.Column(db2.String)
    round = db2.Column(db2.String)
    time = db2.Column(db2.String)

# clean the database then get the stats of the fighters in the csv
# used to run predictions from the frontend
def process(fighter_name1, fighter_name2):
    with app2.app_context():
        db2.drop_all()
    fun(fighter_name1, fighter_name2)
    export_to_csv("predict_fights.csv")

# write stats of 2 fighters to a file, then send that file to the ml model
# predict the outcome of the fight
# .csv 
def fun(fighter_name1, fighter_name2):
    fighter_stats = dict()
    matchup=list()
    with app.app_context():
        fighter1 = Fighter.query.filter_by(name=fighter_name1).first()
        fighter2 = Fighter.query.filter_by(name=fighter_name2).first()
        if not fighter1 or not fighter2:
            return  # Handle case where one or both fighters are not found
        matchup.append(fighter1)
        matchup.append(fighter2)
        fighter_stats[fighter1.name] = {
            "kd_differential": 0,
            "str_differential": 0,
            "td_differential": 0,
            "sub_differential": 0,
            "winrate": 0,
            "winstreak": 0,
            "totalwins": 0,
            "totalfights": 0,
            "titlefights": 0,
            "opp_avg_winrate": 0
        }
        fighter_stats[fighter2.name] = {
            "kd_differential": 0,
            "str_differential": 0,
            "td_differential": 0,
            "sub_differential": 0,
            "winrate": 0,
            "winstreak": 0,
            "totalwins": 0,
            "totalfights": 0,
            "titlefights": 0,
            "opp_avg_winrate": 0
        }        
        with app2.app_context():
            db2.create_all()
        for fighter in matchup:
            fights = fighter.fights
            fights=list(reversed(fights))
            n=len(fights)
            cnt=0
            for fight in fights:
                opponent = Fighter.query.filter_by(name=fight.opponent).first()
                # if predicting the last fight of a fighter
                # if cnt==n-1:
                #     break
                if fight.fighterKD =="--" or fight.fighterSTR =="--" or fight.fighterTD =="--" or fight.fighterSUB =="--":
                    continue

                # calculate opponent record at the time of the fight
                opponent_fights = list(reversed(opponent.fights))
                opp_wins = 0
                opp_total_fights = 0
                for opp_fight in opponent_fights:
                    if opp_fight.fighterKD == "--" or opp_fight.fighterSTR == "--" or opp_fight.fighterTD == "--" or opp_fight.fighterSUB == "--":
                        continue
                    if opp_fight.result == "win":
                        opp_wins += 1
                    opp_total_fights += 1
                opp_avg_winrate = opp_wins / opp_total_fights
                fighter_stats[fighter.name]["opp_avg_winrate"] += opp_avg_winrate

                fighter_stats[fighter.name]["kd_differential"] += int(fight.fighterKD) - int(fight.opponentKD)
                fighter_stats[fighter.name]["str_differential"] += int(fight.fighterSTR) - int(fight.opponentSTR)
                fighter_stats[fighter.name]["td_differential"] += int(fight.fighterTD) - int(fight.opponentTD)
                fighter_stats[fighter.name]["sub_differential"] += int(fight.fighterSUB) - int(fight.opponentSUB)
                fighter_stats[fighter.name]["totalfights"] += 1
                if fight.result=="win":
                    fighter_stats[fighter.name]["winstreak"] += 1
                    fighter_stats[fighter.name]["totalwins"] += 1
                else:
                    fighter_stats[fighter.name]["winstreak"] = 0
                if fight.titlefight:
                    fighter_stats[fighter.name]["titlefights"] += 1
                cnt+=1

            fighter_stats[fighter.name]["opp_avg_winrate"] /= cnt

    
    # fighter1 = fighter, fighter2 = opponent
    with app.app_context():
        processed_fight = FightStats()
        fighter = Fighter.query.filter_by(name=fighter_name1).first()
        opponent = Fighter.query.filter_by(name=fighter_name2).first()
        processed_fight = FightStats(
            event="unknown",
            date="unknown",
            
            fighter_name=fighter.name,
            opponent_name=opponent.name,

            fighter_weight=fighter.Weight,
            fighter_height=fighter.Height,
            fighter_reach=fighter.Reach,
            fighter_dob=fighter.DOB,
            fighter_kd_differential = fighter_stats[fighter.name]["kd_differential"]/fighter_stats[fighter.name]["totalfights"],
            fighter_str_differential = fighter_stats[fighter.name]["str_differential"]/fighter_stats[fighter.name]["totalfights"],
            fighter_td_differential = fighter_stats[fighter.name]["td_differential"]/fighter_stats[fighter.name]["totalfights"],
            fighter_sub_differential = fighter_stats[fighter.name]["sub_differential"]/fighter_stats[fighter.name]["totalfights"],
            fighter_winrate = fighter_stats[fighter.name]["totalwins"]/fighter_stats[fighter.name]["totalfights"],
            fighter_winstreak = fighter_stats[fighter.name]["winstreak"],
            fighter_totalfights = fighter_stats[fighter.name]["totalfights"],
            fighter_totalwins = fighter_stats[fighter.name]["totalwins"],
            fighter_record = fighter.record,
            fighter_titlefights = fighter_stats[fighter.name]["titlefights"],
            
            opponent_weight=opponent.Weight,
            opponent_height=opponent.Height,
            opponent_reach=opponent.Reach,
            opponent_dob=opponent.DOB,
            opponent_kd_differential = fighter_stats[opponent.name]["kd_differential"]/fighter_stats[opponent.name]["totalfights"],
            opponent_str_differential = fighter_stats[opponent.name]["str_differential"]/fighter_stats[opponent.name]["totalfights"],
            opponent_td_differential = fighter_stats[opponent.name]["td_differential"]/fighter_stats[opponent.name]["totalfights"],
            opponent_sub_differential = fighter_stats[opponent.name]["sub_differential"]/fighter_stats[opponent.name]["totalfights"],
            opponent_winrate = fighter_stats[opponent.name]["totalwins"]/fighter_stats[opponent.name]["totalfights"],
            opponent_winstreak = fighter_stats[opponent.name]["winstreak"],
            opponent_totalfights = fighter_stats[opponent.name]["totalfights"],
            opponent_totalwins = fighter_stats[opponent.name]["totalwins"],
            opponent_record = opponent.record,
            opponent_titlefights = fighter_stats[opponent.name]["titlefights"],

            result="unknown",
            method="unknown",
            round="unknown",
            time="unknown",
        )
        with app2.app_context():
            db2.session.add(processed_fight)
            db2.session.commit()


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
                    "result": fight_stat.result,
                    "method": fight_stat.method,
                    "round": fight_stat.round,
                    "time": fight_stat.time,
                })

# used to run tests locally
def main():
    # clears the db
    with app2.app_context():
        db2.drop_all()
    fights = [
        ["Aljamain Sterling", "Sean O'Malley"],
        ["Zhang Weili", "Amanda Lemos"],
        ["Ian Garry", "Neil Magny"],
        ["Mario Bautista", "Da'Mon Blackshear"],
        ["Marlon Vera", "Pedro Munhoz"],
        ["Chris Weidman", "Brad Tavares"],
        ["Gregory Rodrigues", "Denis Tiuliulin"],
        ["Kurt Holobaugh", "Austin Hubbard"],
        ["Brad Katona", "Cody Gibson"],
        ["Gerald Meerschaert", "Andre Petroski"],
        ["Andrea Lee", "Natalia Silva"],
        ["Maryna Moroz", "Karine Silva"],
    ]
 
    for fight in fights:
        fun(fight[0],fight[1])
    export_to_csv("predict_fights.csv")
    # clean_data()
    return
    


if __name__ == "__main__":
    main()

# UFC Fight Night Holloway vs Zombie
# fights = [["Max Holloway", "Chan Sung Jung"],["Anthony Smith", "Ryan Spann"],["Alex Caceres", "Giga Chikadze"],["Fernie Garcia", "Rinya Nakamura"],["Erin Blanchfield", "Taila Santos"],["Parker Porter", "Junior Tafa"],["Lukasz Brzeski", "Waldo Cortes-Acosta"],["Garrett Armfield", "Toshiomi Kazama"],["Michal Oleksiejczuk", "Chidi Njokuani"],["Rolando Bedoya", "Song Kenan"],["Billy Goff", "Yusaku Kinoshita"],["JJ Aldrich", "Liang Na"],["Jarno Errens", "SeungWoo Choi"]]


# UFC 292
# fights = [["Aljamain Sterling", "Sean O'Malley"]]
