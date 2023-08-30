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
                "titlefights": 0,
                "opponentexp": 0
            }
            fighter_ids[fighter.name] = fighter.id
    with app.app_context():
        fighters=Fighter.query.all()
        for fighter in fighters:
            fights = fighter.fights
            fights = list(reversed(fights))
            first_fight=True
            cnt=0
            for fight in fights:
                opponent = db.session.get(Fighter, fighter_ids[fight.opponent])
                if fight.fighterKD =="--" or fight.fighterSTR =="--" or fight.fighterTD =="--" or fight.fighterSUB =="--":
                    continue
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
                
                opponent_fights = list(reversed(opponent.fights))
                opp_wins = 0
                opp_total_fights = 0
                for opp_fight in opponent_fights:
                    if opp_fight.event == fight.event:
                        break
                    if opp_fight.result == "win":
                        opp_wins += 1
                    opp_total_fights += 1
                if opp_total_fights==0:
                    fighter_stats[fighter.name]["opponentexp"] += 0
                else:
                    opp_avg_winrate = opp_wins / opp_total_fights
                    fighter_stats[fighter.name]["opponentexp"] += opp_avg_winrate
                
                if cnt>=1:
                    first_fight=False


def main():
    create_tables()
    # clean_data()
    return
    


if __name__ == "__main__":
    main()


