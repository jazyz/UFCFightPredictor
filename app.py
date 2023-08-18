from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fighters.db"
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
    fighter_id = db.Column(db.Integer, db.ForeignKey("fighter.id"))
    result = db.Column(db.String)
    opponent = db.Column(db.String)
    KD = db.Column(db.String)
    STR = db.Column(db.String)
    TD = db.Column(db.String)
    SUB = db.Column(db.String)
    event = db.Column(db.String)
    date = db.Column(db.String)
    method = db.Column(db.String)
    round = db.Column(db.String)
    time = db.Column(db.String)

    fighter = db.relationship("Fighter", back_populates="fights")


def remove_after_first_space(input_string):
    parts = input_string.split(" ", 1)
    if len(parts) > 1:
        return parts[0]
    else:
        return input_string


def clean_and_convert(value):
    try:
        if value == None:
            return 0.0

        if isinstance(value, str):
            value = remove_after_first_space(value)
        if isinstance(value, str) and "%" in value:
            return float(value.strip("%")) / 100.0
        return float(value)
    except ValueError:
        return 0.0


def calculate_power_rating_with_history(fighter_stats, attribute_weights):
    power_rating = 0

    with app.app_context():
        session = db.session
        fighter_with_fights = (
            session.query(Fighter)
            .filter_by(id=fighter_stats.id)
            .options(db.joinedload(Fighter.fights))
            .first()
        )

        for attribute, weight in attribute_weights.items():
            if hasattr(fighter_with_fights, attribute):
                value = getattr(fighter_with_fights, attribute)
                value = clean_and_convert(value)
                power_rating += weight * value

        past_fights = fighter_with_fights.fights[-5:]

        for idx, fight in enumerate(past_fights):
            fight_impact = (1 if fight.result == "win" else -1) * (1 * (5 - idx))

            if fight.time and ":" in fight.time and fight.round:
                minutes, seconds = fight.time.split(":")
                time_in_seconds = int(minutes) * 60 + int(seconds)
                time_impact = (1 / (time_in_seconds + 1)) * 0.2

                round_number = int(fight.round)
                round_impact = (1 - round_number / 5) * 0.1

                fight_impact *= time_impact + round_impact

            power_rating += fight_impact

    return power_rating


attribute_weights = {
    "SLpM": 0.2,
    "Str_Acc": 0.1,
    "SApM": 0.1,
    "Str_Def": 0.15,
    "TD_Avg": 0.1,
    "TD_Acc": 0.05,
    "TD_Def": 0.05,
    "Sub_Avg": 0.15,
    "Weight": 0.2,
}


def predictOutcome(fighter1, fighter2):
    power1 = calculate_power_rating_with_history(fighter1, attribute_weights)
    power2 = calculate_power_rating_with_history(fighter2, attribute_weights)
    if power1 > power2:
        return fighter1.name
    else:
        return fighter2.name


def get_fighter_by_name(fighter_name):
    with app.app_context():
        fighter = Fighter.query.filter_by(name=fighter_name).first()
        return fighter


def main():
    fighter1 = get_fighter_by_name("Aljamain Sterling")
    fighter2 = get_fighter_by_name("Sean O'Malley")
    print(predictOutcome(fighter1, fighter2))


if __name__ == "__main__":
    main()
