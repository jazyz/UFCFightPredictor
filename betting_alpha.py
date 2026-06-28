"""Generate live betting suggestions for the next fight card."""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from utils.name_matching import canonical_name


PREDICTIONS_PATH = os.path.join("data", "betting_predictions.csv")
PREDICTIONS_METADATA_PATH = os.path.join("data", "betting_predictions_metadata.json")
POLICY_PATH = os.path.join("test_results", "frozen_forward_policy", "frozen_forward_policy.json")
OUTPUT_PATH = os.path.join("data", "betting_results.txt")
FORWARD_LEDGER_DIR = os.path.join("test_results", "forward_paper_tracking")
FORWARD_LEDGER_CSV_PATH = os.path.join(FORWARD_LEDGER_DIR, "latest_forward_paper_bets.csv")
FORWARD_LEDGER_JSON_PATH = os.path.join(FORWARD_LEDGER_DIR, "latest_forward_paper_bets.json")

# Paste the UFC.com card link to price here.
FIGHT_CARD_LINK = "https://www.ufc.com/event/ufc-322"

BANKROLL = 100

LEDGER_COLUMNS = [
    "generated_at_utc",
    "fight_card_link",
    "event_key",
    "bankroll",
    "policy_path",
    "policy_as_of_date",
    "policy_selection_objective",
    "policy_dev_start",
    "policy_dev_end",
    "strategy_json",
    "prediction_source",
    "prediction_generated_at_utc",
    "model_train_through",
    "model_param_source",
    "fight_index",
    "fighter1",
    "fighter2",
    "fighter1_odds",
    "fighter2_odds",
    "fighter1_model_probability",
    "fighter2_model_probability",
    "fighter1_market_probability",
    "fighter2_market_probability",
    "selected_fighter",
    "selected_odds",
    "selected_model_probability",
    "selected_market_probability",
    "selected_policy_probability",
    "selected_edge",
    "selected_kelly",
    "stake",
    "potential_profit",
    "potential_return_with_stake",
    "bet_placed",
    "no_bet_reason",
]


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


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def run_metadata(policy, prediction_metadata, strategy, generated_at_utc):
    return {
        "generated_at_utc": generated_at_utc,
        "fight_card_link": FIGHT_CARD_LINK,
        "event_key": FIGHT_CARD_LINK,
        "bankroll": BANKROLL,
        "policy_path": POLICY_PATH,
        "policy_as_of_date": policy.get("as_of_date", ""),
        "policy_selection_objective": policy.get("selection_objective", ""),
        "policy_dev_start": policy.get("dev_start", ""),
        "policy_dev_end": policy.get("dev_end", ""),
        "strategy_json": json.dumps(strategy, sort_keys=True),
        "prediction_source": prediction_metadata.get("prediction_source", "unknown"),
        "prediction_generated_at_utc": prediction_metadata.get("generated_at_utc", ""),
        "model_train_through": prediction_metadata.get("model_train_through", "unknown"),
        "model_param_source": prediction_metadata.get("model_param_source", ""),
    }


def empty_scored_row(fight_index, fighter1, fighter2, odds1, odds2):
    return {
        "fight_index": fight_index,
        "fighter1": fighter1,
        "fighter2": fighter2,
        "fighter1_odds": odds1,
        "fighter2_odds": odds2,
        "fighter1_model_probability": "",
        "fighter2_model_probability": "",
        "fighter1_market_probability": "",
        "fighter2_market_probability": "",
        "selected_fighter": "",
        "selected_odds": "",
        "selected_model_probability": "",
        "selected_market_probability": "",
        "selected_policy_probability": "",
        "selected_edge": "",
        "selected_kelly": "",
        "stake": 0.0,
        "potential_profit": 0.0,
        "potential_return_with_stake": 0.0,
        "bet_placed": False,
        "no_bet_reason": "",
    }


def score_fights(fights, predictions, strategy, bankroll=BANKROLL):
    rows = []
    for fight_index, (fighter1, fighter2, odds1, odds2) in enumerate(fights, start=1):
        row = empty_scored_row(fight_index, fighter1, fighter2, odds1, odds2)
        if odds1 is None or odds2 is None:
            row["no_bet_reason"] = "missing odds"
            rows.append(row)
            continue

        p1 = matchup_probability(predictions, fighter1, fighter2)
        if p1 is None:
            row["no_bet_reason"] = "prediction not found"
            rows.append(row)
            continue

        p2 = 1 - p1
        market1, market2 = devig_market_probabilities(odds1, odds2)
        row.update(
            {
                "fighter1_model_probability": p1,
                "fighter2_model_probability": p2,
                "fighter1_market_probability": market1 if market1 is not None else "",
                "fighter2_market_probability": market2 if market2 is not None else "",
            }
        )

        selected = choose_bet(bankroll, fighter1, fighter2, odds1, odds2, p1, strategy)
        if selected is None:
            row["no_bet_reason"] = "could not score market probabilities"
            rows.append(row)
            continue

        potential_profit = payout(selected["odds"], selected["bet"]) if selected["bet"] > 0 else 0.0
        row.update(
            {
                "selected_fighter": selected["fighter"],
                "selected_odds": selected["odds"],
                "selected_model_probability": selected["model_probability"],
                "selected_market_probability": selected["market_probability"],
                "selected_policy_probability": selected["bet_probability"],
                "selected_edge": selected["edge"],
                "selected_kelly": selected["kelly"],
                "stake": selected["bet"],
                "potential_profit": potential_profit,
                "potential_return_with_stake": selected["bet"] + potential_profit,
                "bet_placed": selected["bet"] > 0,
                "no_bet_reason": selected["no_bet_reason"],
            }
        )
        rows.append(row)
    return rows


def serializable_value(value):
    if value is None:
        return ""
    return value


def rows_with_metadata(rows, metadata):
    return [
        {column: serializable_value({**metadata, **row}.get(column, "")) for column in LEDGER_COLUMNS}
        for row in rows
    ]


def write_machine_readable_ledger(rows, metadata, csv_path=FORWARD_LEDGER_CSV_PATH, json_path=FORWARD_LEDGER_JSON_PATH):
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    flat_rows = rows_with_metadata(rows, metadata)

    with open(csv_path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        writer.writerows(flat_rows)

    with open(json_path, "w") as file:
        json.dump(
            {
                "metadata": metadata,
                "rows": rows,
                "warning": (
                    "Forward paper-tracking recommendations only. Commit or archive "
                    "before outcomes are known if using this run as evidence."
                ),
            },
            file,
            indent=2,
        )

    return csv_path, json_path


def write_bet(file, bet, fighter_name, fighter_odds):
    potential_return = payout(fighter_odds, bet)
    file.write(
        f"{fighter_name} ${bet:.2f} (bet) "
        f"pt: ${bet + potential_return:.2f} +${potential_return:.2f}"
    )


def write_text_report(output_path, rows, metadata):
    with open(output_path, "w") as output:
        output.write(f"Bankroll: ${metadata['bankroll']:.2f}\n")
        output.write(f"Fight Card: {metadata['fight_card_link']}\n")
        output.write(f"Frozen Policy As Of: {metadata['policy_as_of_date']}\n")
        output.write(f"Policy Source: {metadata['policy_path']}\n")
        output.write(f"Prediction Source: {metadata['prediction_source']}\n")
        output.write(f"Model Train Through: {metadata['model_train_through']}\n")
        output.write(f"Strategy: {metadata['strategy_json']}\n")
        output.write("Mode: forward paper tracking; not proof of live edge\n")
        output.write("---\n")

        for row in rows:
            fighter1 = row["fighter1"]
            fighter2 = row["fighter2"]
            odds1 = row["fighter1_odds"]
            odds2 = row["fighter2_odds"]

            if row["no_bet_reason"] == "missing odds":
                output.write(f"{fighter1} vs {fighter2}: missing odds\n---\n")
                continue
            if row["no_bet_reason"] == "prediction not found":
                output.write(f"{fighter1} vs {fighter2}: prediction not found\n---\n")
                continue
            if row["no_bet_reason"] == "could not score market probabilities":
                output.write(f"{fighter1} vs {fighter2}: could not score market probabilities\n---\n")
                continue

            p1 = row["fighter1_model_probability"]
            p2 = row["fighter2_model_probability"]
            output.write(f"{fighter1}: {odds1} {p1:.3f}\n")
            output.write(f"{fighter2}: {odds2} {p2:.3f}\n")
            output.write(
                f"Candidate: {row['selected_fighter']} "
                f"model={row['selected_model_probability']:.3f} "
                f"market={row['selected_market_probability']:.3f} "
                f"policy_prob={row['selected_policy_probability']:.3f} "
                f"edge={row['selected_edge']:.3f} kelly={row['selected_kelly']:.3f}\n"
            )

            if row["stake"] > 0:
                write_bet(output, row["stake"], row["selected_fighter"], row["selected_odds"])
                output.write("\n")
            else:
                output.write(f"{row['selected_fighter']} (no bet: {row['no_bet_reason']})\n")
            output.write("---\n")


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
    metadata = run_metadata(policy, prediction_metadata, strategy, utc_now_iso())
    rows = score_fights(fights, predictions, strategy)
    write_text_report(OUTPUT_PATH, rows, metadata)
    csv_path, json_path = write_machine_readable_ledger(rows, metadata)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
