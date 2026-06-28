"""Generate live betting suggestions for the next fight card."""

import csv
import os

import requests
from bs4 import BeautifulSoup

from utils.name_matching import canonical_name


PREDICTIONS_PATH = os.path.join("data", "betting_predictions.csv")
OUTPUT_PATH = os.path.join("data", "betting_results.txt")

# Paste the UFC.com card link to price here.
FIGHT_CARD_LINK = "https://www.ufc.com/event/ufc-322"

BANKROLL = 100
KELLY_FRACTION = 0.05
MAX_FRACTION = 0.05
POSITIVE_FLOOR_FRACTION = 0.0
NEGATIVE_FLAT_FRACTION = 0.0
MIN_EDGE = 0.02


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


def payout(odds, bet):
    if odds < 0:
        return bet * (100 / -odds)
    return bet * (odds / 100)


def choose_bet(bankroll, fighter1, fighter2, odds1, odds2, p1):
    p2 = 1 - p1
    if p1 >= p2:
        fighter, odds, probability = fighter1, odds1, p1
    else:
        fighter, odds, probability = fighter2, odds2, p2

    market_probability = odds_to_prob(odds)
    edge = probability - market_probability
    kelly = kelly_criterion(odds, probability)

    if edge < MIN_EDGE:
        return fighter, odds, probability, market_probability, edge, kelly, 0.0, "edge below threshold"

    if kelly > 0:
        bet = bankroll * KELLY_FRACTION * kelly
        bet = min(bet, MAX_FRACTION * bankroll)
        bet = max(bet, POSITIVE_FLOOR_FRACTION * bankroll)
    elif NEGATIVE_FLAT_FRACTION > 0 and kelly > -0.5:
        bet = bankroll * NEGATIVE_FLAT_FRACTION
    else:
        bet = 0.0
        return fighter, odds, probability, market_probability, edge, kelly, bet, "non-positive kelly"

    return fighter, odds, probability, market_probability, edge, kelly, bet, ""


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
    predictions = load_predictions()
    fights = scrape_card(FIGHT_CARD_LINK)

    with open(OUTPUT_PATH, "w") as output:
        output.write(f"Bankroll: ${BANKROLL:.2f}\n")
        output.write(f"Fight Card: {FIGHT_CARD_LINK}\n")
        output.write(f"Strategy: {KELLY_FRACTION} Kelly, {MAX_FRACTION} cap, {MIN_EDGE:.1%} min edge\n")
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
            bet_on, bet_odds, bet_probability, market_probability, edge, kelly, bet, no_bet_reason = choose_bet(
                BANKROLL,
                fighter1,
                fighter2,
                odds1,
                odds2,
                p1,
            )

            output.write(f"{fighter1}: {odds1} {p1:.3f}\n")
            output.write(f"{fighter2}: {odds2} {p2:.3f}\n")
            output.write(
                f"Candidate: {bet_on} model={bet_probability:.3f} "
                f"market={market_probability:.3f} edge={edge:.3f} kelly={kelly:.3f}\n"
            )

            if bet > 0:
                write_bet(output, bet, bet_on, bet_odds)
                output.write("\n")
            else:
                output.write(f"{bet_on} (no bet: {no_bet_reason})\n")
            output.write("---\n")


if __name__ == "__main__":
    main()
