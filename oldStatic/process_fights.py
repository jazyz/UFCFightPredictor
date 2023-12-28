from flask import Flask
from backend.models import Fighter, Fight, db
from flask_sqlalchemy import SQLAlchemy
import csv
import re

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fighters.db"
db.init_app(app)

app2 = Flask("processfights")
app2.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fightstats.db"
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
    opponent_name = db2.Column(db2.String)
    opponent_weight = db2.Column(db2.String)
    opponent_height = db2.Column(db2.String)
    opponent_reach = db2.Column(db2.String)
    opponent_dob = db2.Column(db2.String)
    result = db2.Column(db2.String)
    method = db2.Column(db2.String)
    round = db2.Column(db2.String)
    time = db2.Column(db2.String)


def drop_tables():
    with app2.app_context():
        db2.drop_all()

def create_tables():
    with app2.app_context():
        db2.create_all()
    with app.app_context():
        fights = Fight.query.all()
        for fight in fights:
            fighter = db.session.get(Fighter, fight.fighter_id)
            opponent = Fighter.query.filter_by(name=fight.opponent).first()

            # Check if the processed fight already exists in db2
            with app2.app_context():
                existing_processed_fight = FightStats.query.filter_by(event=fight.event,date=fight.date,fighter_name=opponent.name,opponent_name=fighter.name,).first()
                if existing_processed_fight:
                    continue

            processed_fight = FightStats(
                event=fight.event,
                date=fight.date,
                fighter_name=fighter.name,
                fighter_weight=fighter.Weight,
                fighter_height=fighter.Height,
                fighter_reach=fighter.Reach,
                fighter_dob=fighter.DOB,
                opponent_name=opponent.name,
                opponent_weight=opponent.Weight,
                opponent_height=opponent.Height,
                opponent_reach=opponent.Reach,
                opponent_dob=opponent.DOB,
                result=fight.result,
                method=fight.method,
                round=fight.round,
                time=fight.time,
            )

            with app2.app_context():
                db2.session.add(processed_fight)
                db2.session.commit()

def export_to_csv(filename):
    with app2.app_context():
        fight_stats = FightStats.query.all()

        with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "id", "event", "date", "fighter_name", "fighter_weight",
                "fighter_height", "fighter_reach", "fighter_dob",
                "opponent_name", "opponent_weight", "opponent_height",
                "opponent_reach", "opponent_dob", "result", "method",
                "round", "time"
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
                    "opponent_name": fight_stat.opponent_name,
                    "opponent_weight": fight_stat.opponent_weight,
                    "opponent_height": fight_stat.opponent_height,
                    "opponent_reach": fight_stat.opponent_reach,
                    "opponent_dob": fight_stat.opponent_dob,
                    "result": fight_stat.result,
                    "method": fight_stat.method,
                    "round": fight_stat.round,
                    "time": fight_stat.time,
                })

# clean scraped data in the database
def clean_data():
    with app2.app_context():
        fight_stats = FightStats.query.all()

        for fight_stat in fight_stats:
            if fight_stat.fighter_weight != "--":
                fight_stat.fighter_weight = int(re.search(r'\d+', fight_stat.fighter_weight).group())
            else:
                fight_stat.fighter_weight = None

            if fight_stat.opponent_weight != "--":
                fight_stat.opponent_weight = int(re.search(r'\d+', fight_stat.opponent_weight).group())
            else:
                fight_stat.opponent_weight = None

            if fight_stat.fighter_height != "--":
                height_parts = fight_stat.fighter_height.split("'")
                feet = int(height_parts[0])
                inches = 0
                if len(height_parts) > 1:
                    inches = int(height_parts[1].split('"')[0])
                total_inches = feet * 12 + inches
                fight_stat.fighter_height = total_inches
            else:
                fight_stat.fighter_height = None

            if fight_stat.opponent_height != "--":
                height_parts = fight_stat.opponent_height.split("'")
                feet = int(height_parts[0])
                inches = 0
                if len(height_parts) > 1:
                    inches = int(height_parts[1].split('"')[0])
                total_inches = feet * 12 + inches
                fight_stat.opponent_height = total_inches
            else:
                fight_stat.opponent_height = None

            if fight_stat.fighter_reach != "--":
                fight_stat.fighter_reach = int(re.search(r'\d+', fight_stat.fighter_reach).group())
            else:
                fight_stat.fighter_reach = None

            if fight_stat.opponent_reach != "--":
                fight_stat.opponent_reach = int(re.search(r'\d+', fight_stat.opponent_reach).group())
            else:
                fight_stat.opponent_reach = None

            if fight_stat.fighter_dob=="--":
                fight_stat.fighter_dob = None
            
            if fight_stat.opponent_dob=="--":
                fight_stat.opponent_dob = None
        db2.session.commit()

def main():
    # drop_tables()
    # create_tables()
    export_to_csv("fightstats.csv")
    # clean_data()
    return
    


if __name__ == "__main__":
    main()
