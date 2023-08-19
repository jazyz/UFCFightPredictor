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

        past_fights = fighter_with_fights.fights[0:5]

        for idx, fight in enumerate(past_fights):
            fight_impact = (1 if fight.result == "win" else -1) * (1 * (100 - idx))

            if fight.time and ":" in fight.time and fight.round:
                minutes, seconds = fight.time.split(":")
                time_in_seconds = int(minutes) * 60 + int(seconds)
                time_impact = (1 / (time_in_seconds + 1)) * 0.2

                round_number = int(fight.round)
                round_impact = (1 - round_number / 5) * 0.1

                fight_impact *= time_impact + round_impact

            opp = get_fighter_by_name(fight.opponent)
            opp_name=fight.opponent
            # make algo so that if you lose to a good fighter it doesn't affect that much
            # but if you lose to a bad fighter you lose a lot
            opp_record = opp.record.replace("(","-")
            opp_record = opp_record.split("-")
            opp_wins = float(opp_record[0])
            opp_losses = float(opp_record[1])
            opp_draws = float(opp_record[2])
            experience = opp_wins + opp_losses + opp_draws
            bias = opp_wins / experience
            if fight.result == "win":
                fight_impact *= bias
            else:
                fight_impact *= (1 - bias)

            power_rating += fight_impact

    return power_rating


attribute_weights = {
    "SLpM": 1,
    "Str_Acc": 3,
    "SApM": -1,
    "Str_Def": 3,
    "TD_Avg": 2,
    "TD_Acc": 3,
    "TD_Def": 3,  
    "Sub_Avg": 5,
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
    # fighter_name=fighter_name.title()
    with app.app_context():
        fighter = Fighter.query.filter_by(name=fighter_name).first()
        return fighter


def main():
    fighter1 = get_fighter_by_name("Karine Silva")
    fighter2 = get_fighter_by_name("Maryna Moroz")
    print(predictOutcome(fighter1, fighter2))


if __name__ == "__main__":
    main()

# UFC 292
# Sterling
# Weili
# Garry
# Bautista
# Vera
# Weidman (underdog)
# Rodrigues
# Hubbard
# Katona
# Petroski
# Silva
# Silva
