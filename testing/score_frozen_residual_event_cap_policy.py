#!/usr/bin/env python3
"""Generate pre-outcome paper bets for the frozen capped residual policy."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import net_odds, parse_odds  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_POLICY = "test_results/frozen_residual_event_cap_paper_policy/frozen_residual_event_cap_paper_policy.json"
DEFAULT_PREDICTIONS = "data/betting_predictions.csv"
DEFAULT_PREDICTION_METADATA = "data/betting_predictions_metadata.json"
DEFAULT_OUTPUT_CSV = "test_results/forward_paper_tracking/latest_residual_event_cap_paper_bets.csv"
DEFAULT_OUTPUT_JSON = "test_results/forward_paper_tracking/latest_residual_event_cap_paper_bets.json"

LEDGER_COLUMNS = [
    "generated_at_utc",
    "event_key",
    "fight_card_link",
    "policy_path",
    "policy_as_of_date",
    "policy_json",
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
    "fighter1_meta_probability",
    "fighter2_meta_probability",
    "fighter1_residual_edge",
    "fighter2_residual_edge",
    "selected_fighter",
    "selected_odds",
    "selected_model_probability",
    "selected_market_probability",
    "selected_policy_probability",
    "selected_edge",
    "stake",
    "potential_profit",
    "potential_return_with_stake",
    "bet_placed",
    "no_bet_reason",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Score frozen residual event-cap paper bets")
    parser.add_argument(
        "--fights",
        required=True,
        help=(
            "CSV with fighter1, fighter2, fighter1_odds, fighter2_odds. "
            "Optional columns: fight_index, event_key, fight_card_link."
        ),
    )
    parser.add_argument("--predictions", default=DEFAULT_PREDICTIONS)
    parser.add_argument("--prediction-metadata", default=DEFAULT_PREDICTION_METADATA)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--event-key", default="")
    parser.add_argument("--fight-card-link", default="")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def logit(probability: float) -> float:
    p = min(1.0 - 1e-6, max(1e-6, float(probability)))
    return float(np.log(p / (1.0 - p)))


def sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-float(value))))


def odds_to_prob(odds: float) -> float:
    if odds >= 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def devig_market_probabilities(odds1: float, odds2: float) -> tuple[float, float] | tuple[None, None]:
    raw1 = odds_to_prob(odds1)
    raw2 = odds_to_prob(odds2)
    total = raw1 + raw2
    if not np.isfinite(total) or total <= 0:
        return None, None
    return raw1 / total, raw2 / total


def load_json(path: str) -> dict:
    with Path(path).open() as file:
        return json.load(file)


def load_prediction_metadata(path: str) -> dict:
    metadata_path = Path(path)
    if not metadata_path.exists():
        return {}
    return load_json(path)


def load_predictions(path: str) -> dict[tuple[str, str], float]:
    predictions = {}
    with Path(path).open(newline="") as file:
        reader = csv.DictReader(file)
        required = {"Red Fighter", "Blue Fighter", "Probability Win"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{path} is missing prediction columns: {sorted(missing)}")
        for row in reader:
            red = canonical_name(row["Red Fighter"])
            blue = canonical_name(row["Blue Fighter"])
            predictions[(red, blue)] = float(row["Probability Win"])
    return predictions


def matchup_probability(predictions: dict[tuple[str, str], float], fighter1: str, fighter2: str) -> float | None:
    fighter1_key = canonical_name(fighter1)
    fighter2_key = canonical_name(fighter2)
    direct = predictions.get((fighter1_key, fighter2_key))
    mirrored = predictions.get((fighter2_key, fighter1_key))
    if direct is None or mirrored is None:
        return None
    return float((direct + (1.0 - mirrored)) / 2.0)


def residual_meta_probability(model_probability: float, market_probability: float, transform: dict) -> float:
    market_logit = logit(market_probability)
    model_delta = logit(model_probability) - market_logit
    value = float(transform["intercept"])
    value += float(transform["coefficients"]["market_logit"]) * market_logit
    value += float(transform["coefficients"]["regularized_lgbm_logit_delta"]) * model_delta
    return sigmoid(value)


def empty_row(fight_index, fighter1, fighter2, odds1, odds2, reason: str) -> dict:
    return {
        "fight_index": fight_index,
        "fighter1": fighter1,
        "fighter2": fighter2,
        "fighter1_odds": odds1 if odds1 is not None else "",
        "fighter2_odds": odds2 if odds2 is not None else "",
        "fighter1_model_probability": "",
        "fighter2_model_probability": "",
        "fighter1_market_probability": "",
        "fighter2_market_probability": "",
        "fighter1_meta_probability": "",
        "fighter2_meta_probability": "",
        "fighter1_residual_edge": "",
        "fighter2_residual_edge": "",
        "selected_fighter": "",
        "selected_odds": "",
        "selected_model_probability": "",
        "selected_market_probability": "",
        "selected_policy_probability": "",
        "selected_edge": "",
        "stake": 0.0,
        "potential_profit": 0.0,
        "potential_return_with_stake": 0.0,
        "bet_placed": False,
        "no_bet_reason": reason,
    }


def side_row(
    fighter: str,
    odds: float,
    model_probability: float,
    market_probability: float,
    meta_probability: float,
) -> dict:
    return {
        "fighter": fighter,
        "odds": odds,
        "model_probability": model_probability,
        "market_probability": market_probability,
        "meta_probability": meta_probability,
        "edge": meta_probability - market_probability,
    }


def choose_side(fighter1, fighter2, odds1, odds2, p1, market1, market2, meta1) -> dict:
    p2 = 1.0 - p1
    meta2 = 1.0 - meta1
    sides = [
        side_row(fighter1, odds1, p1, market1, meta1),
        side_row(fighter2, odds2, p2, market2, meta2),
    ]
    return max(sides, key=lambda side: (side["edge"], side["meta_probability"], canonical_name(side["fighter"])))


def score_fight(row: pd.Series, fight_index, predictions, transform, policy: dict) -> dict:
    fighter1 = str(row.get("fighter1", "")).strip()
    fighter2 = str(row.get("fighter2", "")).strip()
    odds1 = parse_odds(row.get("fighter1_odds"))
    odds2 = parse_odds(row.get("fighter2_odds"))
    if not fighter1 or not fighter2:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "missing fighter")
    if odds1 is None or odds2 is None:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "missing odds")

    p1 = matchup_probability(predictions, fighter1, fighter2)
    if p1 is None:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "prediction not found")
    p2 = 1.0 - p1
    market1, market2 = devig_market_probabilities(odds1, odds2)
    if market1 is None or market2 is None:
        return empty_row(fight_index, fighter1, fighter2, odds1, odds2, "could not score market probabilities")

    meta1 = residual_meta_probability(p1, market1, transform)
    meta2 = 1.0 - meta1
    selected = choose_side(fighter1, fighter2, odds1, odds2, p1, market1, market2, meta1)

    reasons = []
    if selected["edge"] < policy["min_edge"]:
        reasons.append("edge below threshold")
    if selected["meta_probability"] < policy["min_probability"]:
        reasons.append("probability below threshold")
    if (
        policy.get("max_underdog_odds") is not None
        and selected["odds"] > float(policy["max_underdog_odds"])
    ):
        reasons.append("underdog odds above cap")

    stake = float(policy["stake_units"]) if not reasons else 0.0
    potential_profit = stake * net_odds(selected["odds"]) if stake > 0 else 0.0
    return {
        "fight_index": fight_index,
        "fighter1": fighter1,
        "fighter2": fighter2,
        "fighter1_odds": odds1,
        "fighter2_odds": odds2,
        "fighter1_model_probability": p1,
        "fighter2_model_probability": p2,
        "fighter1_market_probability": market1,
        "fighter2_market_probability": market2,
        "fighter1_meta_probability": meta1,
        "fighter2_meta_probability": meta2,
        "fighter1_residual_edge": meta1 - market1,
        "fighter2_residual_edge": meta2 - market2,
        "selected_fighter": selected["fighter"],
        "selected_odds": selected["odds"],
        "selected_model_probability": selected["model_probability"],
        "selected_market_probability": selected["market_probability"],
        "selected_policy_probability": selected["meta_probability"],
        "selected_edge": selected["edge"],
        "stake": stake,
        "potential_profit": potential_profit,
        "potential_return_with_stake": stake + potential_profit,
        "bet_placed": stake > 0,
        "no_bet_reason": "; ".join(reasons),
    }


def apply_event_cap(scored: list[dict], policy: dict) -> list[dict]:
    max_bets = int(policy["max_bets_per_event"])
    passing_by_event: dict[str, list[int]] = {}
    for index, row in enumerate(scored):
        if row.get("bet_placed") and float(row.get("stake") or 0.0) > 0:
            passing_by_event.setdefault(str(row.get("_event_key", "")), []).append(index)

    kept = set()
    for indices in passing_by_event.values():
        ranked = sorted(
            indices,
            key=lambda index: (
                -float(scored[index].get("selected_edge") or -999.0),
                -float(scored[index].get("selected_policy_probability") or -999.0),
                "|".join(
                    sorted(
                        [
                            canonical_name(scored[index].get("fighter1", "")),
                            canonical_name(scored[index].get("fighter2", "")),
                        ]
                    )
                ),
            ),
        )
        kept.update(ranked[:max_bets])

    passing_indices = {index for indices in passing_by_event.values() for index in indices}
    capped = []
    for index, row in enumerate(scored):
        output = dict(row)
        if index in passing_indices and index not in kept:
            output["stake"] = 0.0
            output["potential_profit"] = 0.0
            output["potential_return_with_stake"] = 0.0
            output["bet_placed"] = False
            output["no_bet_reason"] = f"event cap {max_bets} reached"
        capped.append(output)
    return capped


def source_event_key(row: pd.Series, args) -> str:
    for column in ("event_key", "fight_card_link"):
        value = row.get(column)
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value).strip()
    return args.event_key or args.fight_card_link or "forward"


def optional_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def load_fights(path: str) -> pd.DataFrame:
    fights = pd.read_csv(path)
    required = {"fighter1", "fighter2", "fighter1_odds", "fighter2_odds"}
    missing = required - set(fights.columns)
    if missing:
        raise SystemExit(f"{path} is missing fight columns: {sorted(missing)}")
    return fights


def row_fight_index(row: pd.Series, fallback: int):
    value = row.get("fight_index")
    if value is None or pd.isna(value) or str(value).strip() == "":
        return fallback
    return value


def metadata(args, policy_artifact, prediction_metadata, generated_at_utc: str) -> dict:
    policy = policy_artifact["policy"]
    return {
        "generated_at_utc": generated_at_utc,
        "event_key": args.event_key or args.fight_card_link or generated_at_utc,
        "fight_card_link": args.fight_card_link,
        "policy_path": args.policy,
        "policy_as_of_date": policy_artifact.get("as_of_date", ""),
        "policy_json": json.dumps(policy, sort_keys=True),
        "prediction_source": prediction_metadata.get("prediction_source", args.predictions),
        "prediction_generated_at_utc": prediction_metadata.get("generated_at_utc", ""),
        "model_train_through": prediction_metadata.get("model_train_through", ""),
        "model_param_source": prediction_metadata.get("model_param_source", ""),
    }


def add_metadata(rows: list[dict], meta: dict, fights: pd.DataFrame) -> list[dict]:
    output = []
    for row, (_, source) in zip(rows, fights.iterrows()):
        row_meta = dict(meta)
        row_meta["event_key"] = (
            optional_text(source.get("event_key"))
            or optional_text(source.get("fight_card_link"))
            or meta["event_key"]
        )
        row_meta["fight_card_link"] = optional_text(source.get("fight_card_link")) or meta["fight_card_link"]
        output.append({column: {**row_meta, **row}.get(column, "") for column in LEDGER_COLUMNS})
    return output


def write_outputs(rows: list[dict], meta: dict, args, policy_artifact):
    csv_path = Path(args.output_csv)
    json_path = Path(args.output_json)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "metadata": meta,
        "policy": policy_artifact,
        "rows": rows,
        "warning": (
            "Frozen capped residual paper-tracking recommendations only. "
            "Archive before outcomes are known if this run will be used as evidence."
        ),
    }
    with json_path.open("w") as file:
        json.dump(payload, file, indent=2)
    return csv_path, json_path


def main():
    args = parse_args()
    policy_artifact = load_json(args.policy)
    policy = policy_artifact["policy"]
    transform = policy_artifact["transform_summary"]
    predictions = load_predictions(args.predictions)
    prediction_metadata = load_prediction_metadata(args.prediction_metadata)
    fights = load_fights(args.fights)

    scored = []
    for fallback_index, (_, row) in enumerate(fights.iterrows(), start=1):
        scored_row = score_fight(
            row,
            row_fight_index(row, fallback_index),
            predictions,
            transform,
            policy,
        )
        scored_row["_event_key"] = source_event_key(row, args)
        scored.append(scored_row)
    capped = apply_event_cap(scored, policy)
    generated_at_utc = utc_now_iso()
    meta = metadata(args, policy_artifact, prediction_metadata, generated_at_utc)
    flat_rows = add_metadata(capped, meta, fights)
    csv_path, json_path = write_outputs(flat_rows, meta, args, policy_artifact)

    bets = sum(1 for row in flat_rows if str(row.get("bet_placed")).lower() == "true")
    print(f"Scored fights: {len(flat_rows)}")
    print(f"Paper bets: {bets}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
