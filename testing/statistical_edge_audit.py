#!/usr/bin/env python3
"""Statistical edge audit for leak-safe UFC backtest ledgers.

The tests are intentionally conditional on the existing rolling backtest CSVs:
they ask whether the saved predictions and bet decisions look better than
market-implied nulls, without retraining models.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.name_matching import canonical_name


EPS = 1e-12


def parse_odds(value):
    if value is None or pd.isna(value):
        return None
    cleaned = str(value).strip().replace("+", "").replace("−", "-")
    if cleaned in {"", "-", "nan", "None"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def implied_prob(american_odds):
    if american_odds is None:
        return np.nan
    if american_odds >= 0:
        return 100.0 / (american_odds + 100.0)
    return -american_odds / (-american_odds + 100.0)


def net_odds(american_odds):
    if american_odds is None:
        return np.nan
    if american_odds >= 0:
        return american_odds / 100.0
    return 100.0 / -american_odds


def binary_log_loss(y_true, p):
    y = np.asarray(y_true, dtype=float)
    prob = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    return float(np.mean(-(y * np.log(prob) + (1.0 - y) * np.log(1.0 - prob))))


def brier_score(y_true, p):
    y = np.asarray(y_true, dtype=float)
    prob = np.asarray(p, dtype=float)
    return float(np.mean((prob - y) ** 2))


def normal_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def binom_sf(k, n, p=0.5):
    if n <= 0:
        return None
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    logs = []
    log_p = math.log(p)
    log_q = math.log(1.0 - p)
    for i in range(k, n + 1):
        logs.append(
            math.lgamma(n + 1)
            - math.lgamma(i + 1)
            - math.lgamma(n - i + 1)
            + i * log_p
            + (n - i) * log_q
        )
    max_log = max(logs)
    return float(math.exp(max_log) * sum(math.exp(value - max_log) for value in logs))


def safe_float(value):
    if value is None or value == "" or pd.isna(value):
        return np.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def nanmean_or_none(values):
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return None
    return float(array.mean())


def load_summary(csv_path):
    summary_path = csv_path.with_name("no_leakage_backtest_summary.json")
    if summary_path.exists():
        with open(summary_path) as file:
            return json.load(file)
    return {}


def label_for_path(csv_path):
    if csv_path.parent.name == "test_results":
        return "test_results_current"
    return csv_path.parent.name


def discover_ledgers(paths):
    if paths:
        return [Path(path) for path in paths]

    found = sorted(Path("test_results").glob("**/no_leakage_backtest.csv"))
    return [path for path in found if path.is_file()]


def add_market_columns(df):
    market_rows = []
    for _, row in df.iterrows():
        fighter1 = canonical_name(row.get("odds_fighter1_name", ""))
        fighter2 = canonical_name(row.get("odds_fighter2_name", ""))
        red = canonical_name(row.get("red_fighter", ""))
        bet_on = canonical_name(row.get("bet_on", ""))

        odds1 = parse_odds(row.get("fighter1_odds"))
        odds2 = parse_odds(row.get("fighter2_odds"))
        p1_raw = implied_prob(odds1)
        p2_raw = implied_prob(odds2)
        vig_sum = p1_raw + p2_raw if np.isfinite(p1_raw) and np.isfinite(p2_raw) else np.nan

        p1_devig = p1_raw / vig_sum if np.isfinite(vig_sum) and vig_sum > 0 else np.nan
        p2_devig = p2_raw / vig_sum if np.isfinite(vig_sum) and vig_sum > 0 else np.nan

        red_market = np.nan
        if red and red == fighter1:
            red_market = p1_devig
        elif red and red == fighter2:
            red_market = p2_devig

        bet_market = np.nan
        bet_odds = np.nan
        if bet_on and bet_on == fighter1:
            bet_market = p1_devig
            bet_odds = odds1
        elif bet_on and bet_on == fighter2:
            bet_market = p2_devig
            bet_odds = odds2

        market_rows.append(
            {
                "red_market_probability": red_market,
                "bet_market_devig_probability": bet_market,
                "bet_odds": bet_odds,
                "market_overround": vig_sum - 1.0 if np.isfinite(vig_sum) else np.nan,
            }
        )

    market_df = pd.DataFrame(market_rows, index=df.index)
    return pd.concat([df, market_df], axis=1)


def calibration_stats(y_true, p, bins=10):
    y = np.asarray(y_true, dtype=float)
    prob = np.asarray(p, dtype=float)
    mask = np.isfinite(y) & np.isfinite(prob)
    y = y[mask]
    prob = prob[mask]
    if len(y) == 0:
        return {"ece": None, "mean_probability": None, "actual_rate": None, "bins": []}

    edges = np.linspace(0.0, 1.0, bins + 1)
    rows = []
    ece = 0.0
    for index in range(bins):
        lo = edges[index]
        hi = edges[index + 1]
        if index == bins - 1:
            in_bin = (prob >= lo) & (prob <= hi)
        else:
            in_bin = (prob >= lo) & (prob < hi)
        count = int(in_bin.sum())
        if count == 0:
            continue
        mean_prob = float(prob[in_bin].mean())
        actual = float(y[in_bin].mean())
        ece += (count / len(y)) * abs(actual - mean_prob)
        rows.append(
            {
                "bin": f"{lo:.1f}-{hi:.1f}",
                "n": count,
                "mean_probability": mean_prob,
                "actual_rate": actual,
                "gap": actual - mean_prob,
            }
        )

    return {
        "ece": float(ece),
        "mean_probability": float(prob.mean()),
        "actual_rate": float(y.mean()),
        "bins": rows,
    }


def event_bootstrap_profit(bets, iterations, rng):
    if bets.empty:
        return None

    grouped = bets.groupby("event_date", sort=True)[["profit", "bet"]].sum()
    grouped = grouped.rename(columns={"bet": "stake"})
    grouped["bets"] = bets.groupby("event_date", sort=True).size()
    group_profit = grouped["profit"].to_numpy(dtype=float)
    group_stake = grouped["stake"].to_numpy(dtype=float)
    group_count = len(grouped)
    if group_count == 0:
        return None

    sampled = rng.integers(0, group_count, size=(iterations, group_count))
    profits = group_profit[sampled].sum(axis=1)
    stakes = group_stake[sampled].sum(axis=1)
    roi = np.divide(profits, stakes, out=np.full_like(profits, np.nan), where=stakes > 0)

    return {
        "events": int(group_count),
        "profit_ci_95": [float(x) for x in np.percentile(profits, [2.5, 97.5])],
        "roi_ci_95": [float(x) for x in np.nanpercentile(roi, [2.5, 97.5])],
        "prob_profit_le_zero": float(np.mean(profits <= 0)),
    }


def event_bootstrap_logloss(df, iterations, rng):
    comparable = df.dropna(subset=["red_market_probability", "red_win_probability", "red_won"])
    if comparable.empty:
        return None

    y = comparable["red_won"].astype(float).to_numpy()
    model_p = np.clip(comparable["red_win_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    market_p = np.clip(comparable["red_market_probability"].astype(float).to_numpy(), EPS, 1.0 - EPS)
    comparable = comparable.assign(
        model_loss=-(y * np.log(model_p) + (1.0 - y) * np.log(1.0 - model_p)),
        market_loss=-(y * np.log(market_p) + (1.0 - y) * np.log(1.0 - market_p)),
    )

    grouped = comparable.groupby("event_date", sort=True)[["model_loss", "market_loss"]].sum()
    grouped["n"] = comparable.groupby("event_date", sort=True).size()
    if grouped.empty:
        return None

    model_loss = grouped["model_loss"].to_numpy(dtype=float)
    market_loss = grouped["market_loss"].to_numpy(dtype=float)
    counts = grouped["n"].to_numpy(dtype=float)
    group_count = len(grouped)

    sampled = rng.integers(0, group_count, size=(iterations, group_count))
    diffs = (
        market_loss[sampled].sum(axis=1) - model_loss[sampled].sum(axis=1)
    ) / counts[sampled].sum(axis=1)

    return {
        "events": int(group_count),
        "market_minus_model_logloss_ci_95": [float(x) for x in np.percentile(diffs, [2.5, 97.5])],
        "prob_model_not_better": float(np.mean(diffs <= 0)),
    }


def market_null_path_simulation(bets, starting_bankroll, observed_final_bankroll, iterations, rng):
    if bets.empty:
        return None

    required = bets.dropna(subset=["bet_market_devig_probability", "bet_odds", "bet", "profit", "bankroll_after"])
    if required.empty:
        return None

    if "bankroll_before" in required.columns:
        bankroll_before = required["bankroll_before"].astype(float)
    else:
        bankroll_before = required["bankroll_after"].astype(float) - required["profit"].astype(float)
    stake_fraction = required["bet"].astype(float).to_numpy() / bankroll_before.to_numpy()
    p_market = required["bet_market_devig_probability"].astype(float).to_numpy()
    odds_multiple = np.array([net_odds(value) for value in required["bet_odds"].to_numpy()], dtype=float)

    mask = (
        np.isfinite(stake_fraction)
        & np.isfinite(p_market)
        & np.isfinite(odds_multiple)
        & (stake_fraction > 0)
        & (stake_fraction < 1)
        & (p_market > 0)
        & (p_market < 1)
    )
    stake_fraction = stake_fraction[mask]
    p_market = p_market[mask]
    odds_multiple = odds_multiple[mask]
    if len(stake_fraction) == 0:
        return None

    finals = np.empty(iterations, dtype=float)
    cursor = 0
    chunk_size = 5000
    while cursor < iterations:
        chunk = min(chunk_size, iterations - cursor)
        bankroll = np.full(chunk, starting_bankroll, dtype=float)
        for fraction, probability, multiple in zip(stake_fraction, p_market, odds_multiple):
            stake = bankroll * fraction
            wins = rng.random(chunk) < probability
            bankroll += np.where(wins, stake * multiple, -stake)
        finals[cursor : cursor + chunk] = bankroll
        cursor += chunk

    return {
        "simulated_bets": int(len(stake_fraction)),
        "null_mean_final_bankroll": float(np.mean(finals)),
        "null_final_bankroll_ci_95": [float(x) for x in np.percentile(finals, [2.5, 97.5])],
        "p_value_observed_or_better": float((np.sum(finals >= observed_final_bankroll) + 1) / (iterations + 1)),
        "prob_null_profitable": float(np.mean(finals > starting_bankroll)),
    }


def mcnemar_against_market(df):
    comparable = df.dropna(subset=["red_market_probability", "red_win_probability", "red_won"])
    if comparable.empty:
        return None

    y = comparable["red_won"].astype(bool)
    model_correct = (comparable["red_win_probability"].astype(float) >= 0.5) == y
    market_correct = (comparable["red_market_probability"].astype(float) >= 0.5) == y
    model_only = int((model_correct & ~market_correct).sum())
    market_only = int((~model_correct & market_correct).sum())
    discordant = model_only + market_only
    p_value = binom_sf(model_only, discordant, 0.5) if discordant else None
    return {
        "model_only_correct": model_only,
        "market_only_correct": market_only,
        "discordant": discordant,
        "one_sided_p_model_better": p_value,
    }


def analyze_run(csv_path, iterations, rng):
    df = pd.read_csv(csv_path)
    if df.empty:
        return None

    for column in [
        "bet",
        "profit",
        "bankroll_after",
        "red_win_probability",
        "bet_probability",
        "bet_edge",
        "bet_on",
    ]:
        if column not in df.columns:
            df[column] = np.nan

    df = add_market_columns(df)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date.astype(str)
    df["red_won"] = [
        canonical_name(winner) == canonical_name(red)
        for winner, red in zip(df["winner_name"], df["red_fighter"])
    ]
    df["bet"] = df["bet"].map(safe_float)
    df["profit"] = df["profit"].map(safe_float)
    df["bankroll_after"] = df["bankroll_after"].map(safe_float)
    df["red_win_probability"] = df["red_win_probability"].map(safe_float)
    df["bet_probability"] = df["bet_probability"].map(safe_float)
    df["bet_edge"] = df["bet_edge"].map(safe_float)

    summary = load_summary(csv_path)
    starting_bankroll = float(summary.get("starting_bankroll", 1000.0))
    observed_final = float(summary.get("final_bankroll", starting_bankroll + df["profit"].sum()))
    total_profit = float(df["profit"].sum())

    model_y = df["red_won"].astype(float).to_numpy()
    model_p = df["red_win_probability"].astype(float).to_numpy()
    model_pred = model_p >= 0.5
    model_accuracy = float(np.mean(model_pred == df["red_won"].to_numpy()))
    model_wins = int((model_pred == df["red_won"].to_numpy()).sum())
    accuracy_p = binom_sf(model_wins, len(df), 0.5)

    comparable = df.dropna(subset=["red_market_probability"])
    prediction_stats = {
        "fights": int(len(df)),
        "model_accuracy": model_accuracy,
        "model_accuracy_p_vs_50": accuracy_p,
        "model_log_loss": binary_log_loss(model_y, model_p),
        "model_brier": brier_score(model_y, model_p),
        "model_calibration": calibration_stats(model_y, model_p),
    }
    if not comparable.empty:
        cy = comparable["red_won"].astype(float).to_numpy()
        cp_model = comparable["red_win_probability"].astype(float).to_numpy()
        cp_market = comparable["red_market_probability"].astype(float).to_numpy()
        market_pred = cp_market >= 0.5
        prediction_stats.update(
            {
                "market_comparable_fights": int(len(comparable)),
                "market_favorite_accuracy": float(np.mean(market_pred == comparable["red_won"].to_numpy())),
                "market_log_loss": binary_log_loss(cy, cp_market),
                "market_brier": brier_score(cy, cp_market),
                "market_minus_model_log_loss": binary_log_loss(cy, cp_market) - binary_log_loss(cy, cp_model),
                "market_minus_model_brier": brier_score(cy, cp_market) - brier_score(cy, cp_model),
                "mcnemar_vs_market": mcnemar_against_market(df),
                "logloss_event_bootstrap": event_bootstrap_logloss(df, iterations, rng),
            }
        )

    bets = df[df["bet"] > 0].copy()
    if bets.empty:
        betting_stats = {
            "bets": 0,
            "profit": 0.0,
            "profit_pct_bankroll": 0.0,
        }
    else:
        bet_won = np.array(
            [
                canonical_name(winner) == canonical_name(bet_on)
                for winner, bet_on in zip(bets["winner_name"], bets["bet_on"])
            ],
            dtype=float,
        )
        stake = bets["bet"].astype(float).to_numpy()
        bet_profit = bets["profit"].astype(float).to_numpy()
        roi = total_profit / stake.sum() if stake.sum() > 0 else np.nan
        per_bet_roi = bet_profit / stake
        avg_return = float(np.mean(per_bet_roi))
        std_return = float(np.std(per_bet_roi, ddof=1)) if len(per_bet_roi) > 1 else np.nan
        t_stat = avg_return / (std_return / math.sqrt(len(per_bet_roi))) if std_return and std_return > 0 else np.nan
        t_p = normal_sf(t_stat) if np.isfinite(t_stat) else None

        betting_stats = {
            "bets": int(len(bets)),
            "events_with_bets": int(bets["event_date"].nunique()),
            "wins": int(bet_won.sum()),
            "win_rate": float(bet_won.mean()),
            "mean_model_bet_probability": nanmean_or_none(bets["bet_probability"]),
            "mean_market_devig_bet_probability": nanmean_or_none(bets["bet_market_devig_probability"]),
            "mean_raw_edge_used_by_strategy": nanmean_or_none(bets["bet_edge"]),
            "mean_devig_edge": nanmean_or_none(
                bets["bet_probability"] - bets["bet_market_devig_probability"]
            ),
            "total_staked": float(stake.sum()),
            "profit": total_profit,
            "profit_pct_bankroll": float((observed_final - starting_bankroll) / starting_bankroll),
            "roi_on_staked": float(roi),
            "mean_profit_per_bet": float(np.mean(bet_profit)),
            "mean_return_per_bet": avg_return,
            "return_t_stat": float(t_stat) if np.isfinite(t_stat) else None,
            "return_t_p_one_sided": t_p,
            "bet_calibration": calibration_stats(bet_won, bets["bet_probability"]),
            "event_bootstrap": event_bootstrap_profit(bets, iterations, rng),
            "market_null_path": market_null_path_simulation(
                bets,
                starting_bankroll,
                observed_final,
                iterations,
                rng,
            ),
        }

    return {
        "label": label_for_path(csv_path),
        "csv_path": str(csv_path),
        "summary_path": str(csv_path.with_name("no_leakage_backtest_summary.json")),
        "start_date": summary.get("start_date", str(df["event_date"].min())),
        "end_date": summary.get("end_date", str(df["event_date"].max())),
        "strategy": summary.get("strategy"),
        "min_edge": summary.get("min_edge"),
        "starting_bankroll": starting_bankroll,
        "final_bankroll": observed_final,
        "summary_profit_pct": summary.get("profit_pct"),
        "prediction": prediction_stats,
        "betting": betting_stats,
    }


def fmt_pct(value, decimals=1):
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * value:.{decimals}f}%"


def fmt_money(value):
    if value is None or not np.isfinite(value):
        return ""
    return f"${value:,.2f}"


def fmt_float(value, decimals=3):
    if value is None or not np.isfinite(value):
        return ""
    return f"{value:.{decimals}f}"


def fmt_p(value):
    if value is None or not np.isfinite(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def markdown_report(results, iterations):
    valid = [result for result in results if result is not None]
    valid = sorted(valid, key=lambda item: (str(item.get("start_date")), item["label"]))
    p_values = [
        result["betting"].get("market_null_path", {}).get("p_value_observed_or_better")
        for result in valid
        if result["betting"].get("market_null_path")
    ]
    p_values = [p for p in p_values if p is not None and np.isfinite(p)]
    best_p = min(p_values) if p_values else None
    bonferroni = min(1.0, best_p * len(p_values)) if best_p is not None else None
    market_logloss_edges = [
        result["prediction"].get("market_minus_model_log_loss")
        for result in valid
        if result["prediction"].get("market_minus_model_log_loss") is not None
    ]
    model_beats_market_logloss = sum(value > 0 for value in market_logloss_edges)
    bootstrap_runs = [
        result["betting"].get("event_bootstrap", {}).get("profit_ci_95")
        for result in valid
        if result["betting"].get("event_bootstrap")
    ]
    bootstrap_positive = sum(ci and ci[0] > 0 for ci in bootstrap_runs)

    lines = [
        "# Statistical Edge Audit",
        "",
        f"Ledgers analyzed: {len(valid)}. Simulation/bootstrap iterations per run: {iterations:,}.",
        "",
        "## Bottom Line",
        "",
    ]

    if best_p is not None:
        lines.append(
            f"The best saved ledger has market-null p={fmt_p(best_p)}; Bonferroni across "
            f"{len(p_values)} saved ledgers gives p={fmt_p(bonferroni)}."
        )
    if market_logloss_edges:
        lines.append(
            f"Model probabilities beat de-vigged market log loss in "
            f"{model_beats_market_logloss}/{len(market_logloss_edges)} ledgers."
        )
    if bootstrap_runs:
        lines.append(
            f"Event-bootstrap profit CIs are strictly positive in "
            f"{bootstrap_positive}/{len(bootstrap_runs)} ledgers."
        )
    lines.append(
        "These p-values are conditional on the saved bet decisions and do not remove manual "
        "researcher degrees of freedom from feature fixes, DOB masking, strategy selection, "
        "or unrecorded failed experiments."
    )
    lines.append("")

    lines.extend(
        [
            "## Run Summary",
            "",
            "| Run | Window | Fights | Bets | Accuracy | Model LL | Market LL | Profit | ROI/Staked | Market-null p | Bootstrap profit CI |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for result in valid:
        prediction = result["prediction"]
        betting = result["betting"]
        market_null = betting.get("market_null_path") or {}
        event_boot = betting.get("event_bootstrap") or {}
        ci = event_boot.get("profit_ci_95")
        ci_text = ""
        if ci:
            ci_text = f"{fmt_money(ci[0])} to {fmt_money(ci[1])}"
        lines.append(
            "| {label} | {start} to {end} | {fights} | {bets} | {acc} | {model_ll} | {market_ll} | {profit} | {roi} | {p} | {ci} |".format(
                label=result["label"],
                start=result.get("start_date", ""),
                end=result.get("end_date", ""),
                fights=prediction.get("fights", ""),
                bets=betting.get("bets", ""),
                acc=fmt_pct(prediction.get("model_accuracy")),
                model_ll=fmt_float(prediction.get("model_log_loss")),
                market_ll=fmt_float(prediction.get("market_log_loss")),
                profit=fmt_money(betting.get("profit")),
                roi=fmt_pct(betting.get("roi_on_staked")),
                p=fmt_p(market_null.get("p_value_observed_or_better")),
                ci=ci_text,
            )
        )

    top = sorted(
        valid,
        key=lambda item: item["betting"].get("profit", float("-inf")),
        reverse=True,
    )[:5]
    lines.extend(
        [
            "",
            "## Highest PnL Runs",
            "",
            "| Run | Profit | Bets | Win Rate | Mean Model P | Actual Bet Win Rate | Devig Edge | Market-null p |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for result in top:
        betting = result["betting"]
        market_null = betting.get("market_null_path") or {}
        lines.append(
            "| {label} | {profit} | {bets} | {wr} | {mp} | {actual} | {edge} | {p} |".format(
                label=result["label"],
                profit=fmt_money(betting.get("profit")),
                bets=betting.get("bets", ""),
                wr=fmt_pct(betting.get("win_rate")),
                mp=fmt_pct(betting.get("mean_model_bet_probability")),
                actual=fmt_pct((betting.get("bet_calibration") or {}).get("actual_rate")),
                edge=fmt_pct(betting.get("mean_devig_edge")),
                p=fmt_p(market_null.get("p_value_observed_or_better")),
            )
        )

    lines.extend(
        [
            "",
            "## How To Read This",
            "",
            "- `Market LL` uses de-vigged American odds as the market probability.",
            "- `Market-null p` replays the same bet decisions and stake fractions with bankroll compounding, but makes winners random from de-vigged market probabilities.",
            "- `Bootstrap profit CI` resamples event dates from the realized ledger, so it captures schedule/event variance but not feature-selection or strategy-search bias.",
            "- Strong p-values here mean the saved ledger is hard to explain by market prices alone; they do not prove live edge after backtest fitting.",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Audit statistical edge in no-leakage backtest ledgers")
    parser.add_argument("ledgers", nargs="*", help="optional no_leakage_backtest.csv paths")
    parser.add_argument("--iterations", type=int, default=20000, help="bootstrap/simulation iterations per run")
    parser.add_argument("--seed", type=int, default=20260628)
    parser.add_argument("--output-dir", default="test_results/statistical_edge_audit")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    ledgers = discover_ledgers(args.ledgers)
    if not ledgers:
        raise SystemExit("No no_leakage_backtest.csv ledgers found")

    results = []
    for ledger in ledgers:
        results.append(analyze_run(ledger, args.iterations, rng))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "edge_audit_summary.json"
    md_path = output_dir / "edge_audit.md"

    with open(json_path, "w") as file:
        json.dump({"iterations": args.iterations, "seed": args.seed, "runs": results}, file, indent=2)

    with open(md_path, "w") as file:
        file.write(markdown_report(results, args.iterations))

    valid = [result for result in results if result is not None]
    print(f"Analyzed {len(valid)} ledgers")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    best = max(valid, key=lambda item: item["betting"].get("profit", float("-inf")))
    best_null = best["betting"].get("market_null_path") or {}
    print(
        "Top PnL: {label} profit={profit} market_null_p={p}".format(
            label=best["label"],
            profit=fmt_money(best["betting"].get("profit")),
            p=fmt_p(best_null.get("p_value_observed_or_better")),
        )
    )


if __name__ == "__main__":
    main()
