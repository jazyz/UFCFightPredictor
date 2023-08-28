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
app2.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///dynamicfightstats.db"
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


def drop_tables():
    with app2.app_context():
        db2.drop_all()

def create_tables():
    fighter_stats = dict()
    fighter_ids = dict()
    fightdict = dict()
    with app.app_context():
        fighters=Fighter.query.all()
        for fighter in fighters:
            fighter_stats[fighter.name] = {
                "kd_differential": 0,
                "str_differential": 0,
                "td_differential": 0,
                "sub_differential": 0,
                "winrate": 0,
                "winstreak": 0,
                "totalwins": 0,
                "totalfights": 0,
                "titlefights": 0
            }
            fighter_ids[fighter.name] = fighter.id
    with app2.app_context():
        db2.create_all()
    with app.app_context():
        fighters=Fighter.query.all()
        for fighter in fighters:
            fights = fighter.fights
            fights = list(reversed(fights))
            first_fight=True
            cnt=0
            for fight in fights:
                opponent = Fighter.query.get(fighter_ids[fight.opponent])
                cnt+=1
                # Check if the processed fight already exists in db2
                fight_in_db=False
                with app2.app_context():
                    existingfight=None
                    if not first_fight:
                        existingfight = FightStats.query.filter_by(event=fight.event,date=fight.date,fighter_name=opponent.name,opponent_name=fighter.name,).first()
                    if existingfight:
                        existingfight.opponent_weight=fighter.Weight
                        existingfight.opponent_height=fighter.Height
                        existingfight.opponent_reach=fighter.Reach
                        existingfight.opponent_dob=fighter.DOB
                        existingfight.opponent_kd_differential = fighter_stats[fighter.name]["kd_differential"]/fighter_stats[fighter.name]["totalfights"]
                        existingfight.opponent_str_differential = fighter_stats[fighter.name]["str_differential"]/fighter_stats[fighter.name]["totalfights"]
                        existingfight.opponent_td_differential = fighter_stats[fighter.name]["td_differential"]/fighter_stats[fighter.name]["totalfights"]
                        existingfight.opponent_sub_differential = fighter_stats[fighter.name]["sub_differential"]/fighter_stats[fighter.name]["totalfights"]
                        existingfight.opponent_winrate = fighter_stats[fighter.name]["totalwins"]/fighter_stats[fighter.name]["totalfights"]
                        existingfight.opponent_winstreak = fighter_stats[fighter.name]["winstreak"]
                        existingfight.opponent_totalfights = fighter_stats[fighter.name]["totalfights"]
                        existingfight.opponent_totalwins = fighter_stats[fighter.name]["totalwins"]
                        existingfight.opponent_record = fighter.record
                        existingfight.opponent_titlefights = fighter_stats[fighter.name]["titlefights"]
                        fight_in_db=True
                        db2.session.commit()
                
                if fight.fighterKD =="--" or fight.fighterSTR =="--" or fight.fighterTD =="--" or fight.fighterSUB =="--":
                    continue
                processed_fight = FightStats()
                if not first_fight and not fight_in_db:
                    processed_fight = FightStats(
                        event=fight.event,
                        date=fight.date,
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
                        result=fight.result,
                        method=fight.method,
                        round=fight.round,
                        time=fight.time,
                    )

                with app2.app_context():
                    if not first_fight and not fight_in_db:
                        db2.session.add(processed_fight)
                        db2.session.commit()

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
                if cnt>=1:
                    first_fight=False

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


def main():
    drop_tables()
    create_tables()
    export_to_csv("dynamicfightstats.csv")
    # clean_data()
    return
    


if __name__ == "__main__":
    main()



