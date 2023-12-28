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


def add_fight_history(fighter, past_fights):
    power_rating = 0
    for idx, fight in enumerate(past_fights):
        fight_impact = (1 if fight.result == "win" else -1) * (1 * (25 - 3 * idx))
        # probably replace fight time with decision method instead

        opp = get_fighter_by_name(fight.opponent)
        opp_name = fight.opponent
        # make algo so that if you lose to a good fighter it doesn't affect that much
        # but if you lose to a bad fighter you lose a lot
        opp_record = opp.record.replace("(", "-")
        opp_record = opp_record.split("-")
        opp_wins = float(opp_record[0])
        opp_losses = float(opp_record[1])
        opp_draws = float(opp_record[2])
        experience = opp_wins + opp_losses + opp_draws
        if experience == 0:
            continue
        bias = opp_wins / experience
        # calculate oppstrength based on stats
        # oppstats=calculate_power_with_stats(opp)
        # mystats=calculate_power_with_stats(fighter)
        # if oppstats==0:
        #     return 0
        # bias=mystats/(oppstats+mystats)
        if fight.result == "win":
            fight_impact *= bias
        else:
            fight_impact *= 1 - bias

        power_rating += fight_impact
    return power_rating


def calculate_power_with_stats(fighter):
    power_rating = 0
    for attribute, weight in attribute_weights.items():
        if hasattr(fighter, attribute):
            value = getattr(fighter, attribute)
            value = clean_and_convert(value)
            power_rating += weight * value
    return power_rating


def calculate_power_rating(fighter):
    power_rating = 0
    past_fights = fighter.fights[0:5]
    # if len(past_fights) < 5:
    #     return 0
    power_rating += calculate_power_with_stats(fighter)
    power_rating += add_fight_history(fighter, past_fights)

    return power_rating


attribute_weights = {
    "SLpM": 3,
    "Str_Acc": 3,
    "SApM": -3,
    "Str_Def": 5,
    "TD_Avg": 2,
    "TD_Acc": 2,
    "TD_Def": 5,
    "Sub_Avg": 3,
    # "Weight": 0.2,
}


def predictOutcome(fighter1, fighter2):
    power1 = calculate_power_rating(fighter1)
    power2 = calculate_power_rating(fighter2)
    if power1 > power2:
        return fighter1.name
    else:
        return fighter2.name


def get_fighter_by_name(fighter_name):
    # fighter_name=fighter_name.title()
    fighter = Fighter.query.filter_by(name=fighter_name).first()
    return fighter


def get_all_fighters():
    with app.app_context():
        fighters = Fighter.query.all()
        p4p = []
        fightcnt=0
        for fighter in fighters:
            power = calculate_power_rating(fighter)
            total_fights = len(fighter.fights)
            fightcnt+=total_fights
            p4p.append([power, fighter.name])
        p4p.sort(key=lambda x: (x[0], x[1]), reverse=True)
        print(fightcnt)
        for idx, (power, fighter_name) in enumerate(p4p[:10], start=1):
            print(f"{idx}. Power: {power:.2f}, Fighter: {fighter_name}")


def predict_event():
    fights = [["Max Holloway", "Chan Sung Jung"],["Anthony Smith", "Ryan Spann"],["Alex Caceres", "Giga Chikadze"],["Fernie Garcia", "Rinya Nakamura"],["Erin Blanchfield", "Taila Santos"],["Parker Porter", "Junior Tafa"],["Lukasz Brzeski", "Waldo Cortes-Acosta"],["Garrett Armfield", "Toshiomi Kazama"],["Michal Oleksiejczuk", "Chidi Njokuani"],["Rolando Bedoya", "Song Kenan"],["Billy Goff", "Yusaku Kinoshita"],["JJ Aldrich", "Liang Na"],["Jarno Errens", "SeungWoo Choi"]]
    for fight in fights:
        fighter1 = get_fighter_by_name(fight[0])
        fighter2 = get_fighter_by_name(fight[1])
        print(predictOutcome(fighter1,fighter2))


def main():
    with app.app_context():
        predict_event()
        # get_all_fighters()


if __name__ == "__main__":
    main()

# UFC 292
# Sterling wrong
# Weili correct
# Garry correct
# Bautista correct
# Vera correct
# Weidman (underdog) wrong
# Rodrigues correct
# Hubbard wrong
# Katona correct
# Petroski correct
# Silva correct
# Silva correct

# UFC Singapore
# Max Holloway correct
# Ryan Spann wrong
# Alex Caceres wrong 
# Rinya Nakamura correct 
# Erin Blanchfield correct
# Parker Porter wrong
# Waldo Cortes-Acosta correct
# Toshiomi Kazama wrong
# Michal Oleksiejczuk correct
# Song Kenan correct
# Billy Goff correct
# JJ Aldrich correct
# SeungWoo Choi correct