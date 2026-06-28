"""Generate live betting suggestions for the next fight card."""

import csv
import json
import os

import requests
from bs4 import BeautifulSoup

from utils.name_matching import canonical_name


PREDICTIONS_PATH = os.path.join("data", "betting_predictions.csv")
PREDICTIONS_METADATA_PATH = os.path.join("data", "betting_predictions_metadata.json")
POLICY_PATH = os.path.join("test_results", "frozen_forward_policy", "frozen_forward_policy.json")
OUTPUT_PATH = os.path.join("data", "betting_results.txt")

# Paste the UFC.com card link to price here.
FIGHT_CARD_LINK = "https://www.ufc.com/event/ufc-322"

BANKROLL = 100


def parse_odds(value):
    cleaned = str(value).strip().replace("−", "-")
    if cleaned in {"", "-", "nan", "None"}:
        return None
    return int(cleaned)


def load_predictions(path=PREDICTIONS_PATH):
    predictions = {}
    with open(path, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            red = canonical_name(row["Red Fighter"])
            blue = canonical_name(row["Blue Fighter"])
            predictions[(red, blue)] = float(row["Probability Win"])
    return predictions


def load_prediction_metadata(path=PREDICTIONS_METADATA_PATH):
    if not os.path.exists(path):
        return {}
    with open(path) as file:
        return json.load(file)


def load_frozen_policy(path=POLICY_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing frozen policy artifact: {path}")
    with open(path) as file:
        policy = json.load(file)

    strategy = policy.get("selected_strategy")
    if not isinstance(strategy, dict):
        raise ValueError(f"{path} is missing selected_strategy")
    return policy


def get_ml(predictions, p1, p2):
    return predictions.get((canonical_name(p1), canonical_name(p2)))


def matchup_probability(predictions, fighter1, fighter2):
    """Average direct and mirrored predictions for fighter1 over fighter2."""
    direct = get_ml(predictions, fighter1, fighter2)
    mirrored = get_ml(predictions, fighter2, fighter1)
    if direct is None or mirrored is None:
        return None
    return (direct + (1 - mirrored)) / 2


def kelly_criterion(odds, prob_win):
    if odds < 0:
        net_odds = 100 / -odds
    else:
        net_odds = odds / 100
    return (net_odds * prob_win - (1 - prob_win)) / net_odds


def odds_to_prob(odds):
    if odds >= 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def devig_market_probabilities(odds1, odds2):
    raw1 = odds_to_prob(odds1)
    raw2 = odds_to_prob(odds2)
    total = raw1 + raw2
    if total <= 0:
        return None, None
    return raw1 / total, raw2 / total


def payout(odds, bet):
    if odds < 0:
        return bet * (100 / -odds)
    return bet * (odds / 100)


def score_side(fighter, odds, model_probability, market_probability, strategy):
    probability = (
        strategy["model_weight"] * model_probability
        + (1.0 - strategy["model_weight"]) * market_probability
    )
    edge = probability - market_probability
    kelly = kelly_criterion(odds, probability)
    reasons = []

    if probability < strategy["min_probability"]:
        reasons.append("probability below threshold")
    if edge < strategy["min_edge"]:
        reasons.append("edge below threshold")
    if kelly < strategy["min_kelly"]:
        reasons.append("kelly below threshold")
    max_underdog_odds = strategy.get("max_underdog_odds")
    if max_underdog_odds is not None and odds > max_underdog_odds:
        reasons.append("underdog odds above cap")

    return {
        "fighter": fighter,
        "odds": odds,
        "model_probability": model_probability,
        "market_probability": market_probability,
        "bet_probability": probability,
        "edge": edge,
        "kelly": kelly,
        "no_bet_reason": "; ".join(reasons),
        "passes_filters": not reasons,
    }


def candidate_sides(fighter1, fighter2, odds1, odds2, p1, strategy):
    p2 = 1 - p1
    market1, market2 = devig_market_probabilities(odds1, odds2)
    if market1 is None or market2 is None:
        return []

    side_policy = strategy["side_policy"]
    if side_policy == "predicted_winner":
        if p1 >= p2:
            sides = [(fighter1, odds1, p1, market1)]
        else:
            sides = [(fighter2, odds2, p2, market2)]
    elif side_policy == "best_edge":
        sides = [
            (fighter1, odds1, p1, market1),
            (fighter2, odds2, p2, market2),
        ]
    else:
        raise ValueError(f"unknown frozen side_policy: {side_policy}")

    return [
        score_side(fighter, odds, model_probability, market_probability, strategy)
        for fighter, odds, model_probability, market_probability in sides
    ]


def choose_bet(bankroll, fighter1, fighter2, odds1, odds2, p1, strategy):
    scored_sides = candidate_sides(fighter1, fighter2, odds1, odds2, p1, strategy)
    if not scored_sides:
        return None

    passing_sides = [side for side in scored_sides if side["passes_filters"]]
    chosen = max(
        passing_sides or scored_sides,
        key=lambda side: (side["edge"], side["kelly"]),
    )

    bet = 0.0
    no_bet_reason = chosen["no_bet_reason"]
    if chosen["passes_filters"] and chosen["kelly"] > 0:
        bet = bankroll * strategy["kelly_fraction"] * chosen["kelly"]
        bet = min(bet, strategy["max_fraction"] * bankroll)
    elif chosen["passes_filters"]:
        no_bet_reason = "zero stake"
    else:
        no_bet_reason = no_bet_reason or "strategy filter"

    return {
        **chosen,
        "bet": bet,
        "no_bet_reason": no_bet_reason,
    }


def write_bet(file, bet, fighter_name, fighter_odds):
    potential_return = payout(fighter_odds, bet)
    file.write(
        f"{fighter_name} ${bet:.2f} (bet) "
        f"pt: ${bet + potential_return:.2f} +${potential_return:.2f}"
    )


def scrape_card(link):
    response = requests.get(link, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    odds_wrappers = soup.find_all(class_="c-listing-fight__odds-wrapper")
    fighter_name_divs = soup.find_all("div", {"class": "c-listing-fight__corner-name"})

    fighter_names = []
    for name_div in fighter_name_divs:
        given_name_element = name_div.find("span", {"class": "c-listing-fight__corner-given-name"})
        family_name_element = name_div.find("span", {"class": "c-listing-fight__corner-family-name"})
        if given_name_element and family_name_element:
            given_name = given_name_element.text.strip()
            family_name = family_name_element.text.strip()
            fighter_names.append(f"{given_name} {family_name}")
            continue

        fighter_name_link = name_div.find("a")
        if fighter_name_link:
            fighter_names.append(fighter_name_link.text.strip())
        else:
            fighter_names.append("Fighter Name Not Found")

    fights = []
    for index in range(0, len(fighter_names) - 1, 2):
        odds_wrapper = odds_wrappers[index // 2] if index // 2 < len(odds_wrappers) else None
        if odds_wrapper is None:
            continue
        odds_elements = odds_wrapper.find_all(class_="c-listing-fight__odds-amount")
        odds_values = [element.get_text() for element in odds_elements]
        if len(odds_values) != 2:
            continue

        fights.append(
            (
                fighter_names[index],
                fighter_names[index + 1],
                parse_odds(odds_values[0]),
                parse_odds(odds_values[1]),
            )
        )

    return fights


def main():
    policy = load_frozen_policy()
    strategy = policy["selected_strategy"]
    prediction_metadata = load_prediction_metadata()
    predictions = load_predictions()
    fights = scrape_card(FIGHT_CARD_LINK)

    with open(OUTPUT_PATH, "w") as output:
        output.write(f"Bankroll: ${BANKROLL:.2f}\n")
        output.write(f"Fight Card: {FIGHT_CARD_LINK}\n")
        output.write(f"Frozen Policy As Of: {policy['as_of_date']}\n")
        output.write(f"Policy Source: {POLICY_PATH}\n")
        output.write(f"Prediction Source: {prediction_metadata.get('prediction_source', 'unknown')}\n")
        output.write(f"Model Train Through: {prediction_metadata.get('model_train_through', 'unknown')}\n")
        output.write(f"Strategy: {json.dumps(strategy, sort_keys=True)}\n")
        output.write("Mode: forward paper tracking; not proof of live edge\n")
        output.write("---\n")

        for fighter1, fighter2, odds1, odds2 in fights:
            if odds1 is None or odds2 is None:
                output.write(f"{fighter1} vs {fighter2}: missing odds\n---\n")
                continue

            p1 = matchup_probability(predictions, fighter1, fighter2)
            if p1 is None:
                output.write(f"{fighter1} vs {fighter2}: prediction not found\n---\n")
                continue

            p2 = 1 - p1
            selected = choose_bet(
                BANKROLL,
                fighter1,
                fighter2,
                odds1,
                odds2,
                p1,
                strategy,
            )
            if selected is None:
                output.write(f"{fighter1} vs {fighter2}: could not score market probabilities\n---\n")
                continue

            output.write(f"{fighter1}: {odds1} {p1:.3f}\n")
            output.write(f"{fighter2}: {odds2} {p2:.3f}\n")
            output.write(
                f"Candidate: {selected['fighter']} "
                f"model={selected['model_probability']:.3f} "
                f"market={selected['market_probability']:.3f} "
                f"policy_prob={selected['bet_probability']:.3f} "
                f"edge={selected['edge']:.3f} kelly={selected['kelly']:.3f}\n"
            )

            if selected["bet"] > 0:
                write_bet(output, selected["bet"], selected["fighter"], selected["odds"])
                output.write("\n")
            else:
                output.write(f"{selected['fighter']} (no bet: {selected['no_bet_reason']})\n")
            output.write("---\n")


if __name__ == "__main__":
    main()
