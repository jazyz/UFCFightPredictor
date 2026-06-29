#!/usr/bin/env python3
"""Regime diagnostics for the frozen residual event-cap policy.

This reads already-generated historical cap-3 paper bets. It does not retrain,
select thresholds, or alter the frozen policy. The goal is to see whether the
apparent edge is broad across price/rank regimes or concentrated in a few
post-hoc slices.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_RANKED_BETS = "test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv"


def parse_args():
    parser = argparse.ArgumentParser(description="Audit frozen residual cap-3 regimes")
    parser.add_argument("--ranked-bets", default=DEFAULT_RANKED_BETS)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_cap_regime_audit")
    return parser.parse_args()


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_float(value, digits=3) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def american_win_profit(odds: np.ndarray) -> np.ndarray:
    odds = np.asarray(odds, dtype=float)
    return np.where(odds > 0.0, odds / 100.0, 100.0 / np.abs(odds))


def event_bootstrap_profit(df: pd.DataFrame, iterations: int, rng) -> dict:
    if df.empty or iterations <= 0:
        return {"p_profit_le_zero": None, "profit_ci_95": [None, None]}

    event_profit = df.groupby("event_date", sort=True)["flat_profit"].sum().to_numpy(dtype=float)
    sampled = rng.integers(0, len(event_profit), size=(iterations, len(event_profit)))
    profits = event_profit[sampled].sum(axis=1)
    return {
        "p_profit_le_zero": float((np.sum(profits <= 0.0) + 1) / (iterations + 1)),
        "profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
    }


def market_null_profit_pvalue(df: pd.DataFrame, iterations: int, rng) -> float | None:
    if df.empty or iterations <= 0:
        return None
    market = df["selected_market_probability"].astype(float).to_numpy()
    odds = df["selected_odds"].astype(float).to_numpy()
    win_profit = american_win_profit(odds)
    observed = float(df["flat_profit"].astype(float).sum())
    wins = rng.random((iterations, len(df))) < market
    simulated = np.where(wins, win_profit, -1.0).sum(axis=1)
    return float((np.sum(simulated >= observed) + 1) / (iterations + 1))


def title_group(title: str) -> str:
    text = str(title)
    if "Heavyweight" in text or "Light Heavyweight" in text:
        return "heavy_or_lhw"
    if "Middleweight" in text or "Welterweight" in text:
        return "middle_or_welter"
    if "Lightweight" in text or "Featherweight" in text:
        return "light_or_feather"
    if "Bantamweight" in text or "Flyweight" in text:
        return "bantam_or_fly"
    if "Catch" in text or "Open" in text:
        return "catch_or_open"
    return "other"


def odds_band(odds: float) -> str:
    odds = float(odds)
    if odds <= -400:
        return "<= -400"
    if odds <= -250:
        return "-400 to -250"
    if odds <= -150:
        return "-250 to -150"
    if odds < 0:
        return "-150 to -100"
    return "plus money"


def bin_series(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(series.astype(float), bins=bins, labels=labels, include_lowest=True, right=False)


def load_cap_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "event_date",
        "fight_key",
        "title",
        "selected_odds",
        "selected_probability",
        "selected_market_probability",
        "selected_edge",
        "selected_won",
        "flat_profit",
        "fold",
        "probability_policy",
        "ranking_mode",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"{path} missing required columns: {missing}")

    bets = df[
        (df["probability_policy"] == "frozen_residual_meta")
        & (df["ranking_mode"] == "top_edge")
    ].copy()
    if bets.empty:
        raise SystemExit("No frozen_residual_meta top_edge rows found")

    bets = bets.sort_values(
        ["event_date", "selected_edge", "selected_probability", "fight_key"],
        ascending=[True, False, False, True],
    ).copy()
    bets["event_rank"] = bets.groupby("event_date", sort=False).cumcount() + 1
    bets["event_rank"] = bets["event_rank"].clip(upper=3).astype(str)
    bets["year"] = bets["event_date"].dt.year.astype(str)
    bets["period"] = np.where(bets["event_date"].dt.year == 2024, "2024", "2025-2026")
    bets["last_365d"] = np.where(bets["event_date"] >= pd.Timestamp("2025-06-28"), "last_365d", "older")
    bets["market_prob_bin"] = bin_series(
        bets["selected_market_probability"],
        [0.0, 0.60, 0.70, 0.80, 1.000001],
        ["<0.60", "0.60-0.70", "0.70-0.80", ">=0.80"],
    )
    bets["edge_bin"] = bin_series(
        bets["selected_edge"],
        [0.0, 0.03, 0.05, 0.08, 1.000001],
        ["<0.03", "0.03-0.05", "0.05-0.08", ">=0.08"],
    )
    bets["model_prob_bin"] = bin_series(
        bets["selected_probability"],
        [0.0, 0.65, 0.70, 0.80, 1.000001],
        ["<0.65", "0.65-0.70", "0.70-0.80", ">=0.80"],
    )
    bets["odds_band"] = bets["selected_odds"].map(odds_band)
    bets["title_group"] = bets["title"].map(title_group)
    bets["period_market_bin"] = bets["period"].astype(str) + " | " + bets["market_prob_bin"].astype(str)
    bets["period_rank"] = bets["period"].astype(str) + " | rank " + bets["event_rank"].astype(str)
    return bets


def summarize(df: pd.DataFrame, label: str, iterations: int, market_iterations: int, rng) -> dict:
    if df.empty:
        return {
            "slice": label,
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_market_probability": None,
            "actual_minus_market": None,
            "mean_model_probability": None,
            "mean_edge": None,
            "bootstrap_p_profit_le_zero": None,
            "bootstrap_profit_ci_95": [None, None],
            "market_null_p": None,
        }

    profit = df["flat_profit"].astype(float)
    actual = df["selected_won"].astype(float)
    market = df["selected_market_probability"].astype(float)
    bootstrap = event_bootstrap_profit(df, iterations, rng)
    return {
        "slice": str(label),
        "bets": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "profit": float(profit.sum()),
        "roi": float(profit.mean()),
        "actual_win_rate": float(actual.mean()),
        "mean_market_probability": float(market.mean()),
        "actual_minus_market": float(actual.mean() - market.mean()),
        "mean_model_probability": float(df["selected_probability"].astype(float).mean()),
        "mean_edge": float(df["selected_edge"].astype(float).mean()),
        "bootstrap_p_profit_le_zero": bootstrap["p_profit_le_zero"],
        "bootstrap_profit_ci_95": bootstrap["profit_ci_95"],
        "market_null_p": market_null_profit_pvalue(df, market_iterations, rng),
    }


def summarize_group(df: pd.DataFrame, column: str, iterations: int, market_iterations: int, rng) -> list[dict]:
    rows = []
    for value, subset in df.groupby(column, sort=True, observed=False, dropna=False):
        if subset.empty:
            continue
        rows.append(summarize(subset.copy(), str(value), iterations, market_iterations, rng))
    return rows


def event_concentration(df: pd.DataFrame) -> dict:
    event_profit = (
        df.groupby("event_date", sort=True)
        .agg(
            bets=("fight_key", "size"),
            profit=("flat_profit", "sum"),
            mean_edge=("selected_edge", "mean"),
        )
        .reset_index()
    )
    total_profit = float(event_profit["profit"].sum())
    ordered = event_profit.sort_values("profit", ascending=False).reset_index(drop=True)
    removal_rows = []
    for remove_count in [1, 3, 5, 10]:
        remaining = ordered.iloc[remove_count:]
        removal_rows.append(
            {
                "remove_top_events": int(remove_count),
                "remaining_events": int(len(remaining)),
                "remaining_profit": float(remaining["profit"].sum()),
            }
        )

    cumulative = 0.0
    events_to_erase = None
    for index, profit in enumerate(ordered["profit"].to_numpy(dtype=float), start=1):
        cumulative += profit
        if total_profit - cumulative <= 0.0:
            events_to_erase = index
            break

    top_events = []
    for row in ordered.head(10).to_dict("records"):
        top_events.append(
            {
                "event_date": str(pd.Timestamp(row["event_date"]).date()),
                "bets": int(row["bets"]),
                "profit": float(row["profit"]),
                "mean_edge": float(row["mean_edge"]),
            }
        )

    return {
        "events": int(len(event_profit)),
        "total_profit": total_profit,
        "events_to_erase_profit": events_to_erase,
        "removal_sensitivity": removal_rows,
        "top_events": top_events,
    }


def table(rows: list[dict]) -> list[str]:
    lines = [
        "| Slice | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Mean Edge | Bootstrap P(profit <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {slice} | {bets} | {events} | {profit} | {roi} | {actual} | {market} | {actual_market} | {edge} | {boot} | {null} |".format(
                slice=row["slice"],
                bets=row["bets"],
                events=row["events"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual=fmt_pct(row["actual_win_rate"]),
                market=fmt_pct(row["mean_market_probability"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                edge=fmt_pct(row["mean_edge"]),
                boot=fmt_p(row["bootstrap_p_profit_le_zero"]),
                null=fmt_p(row["market_null_p"]),
            )
        )
    return lines


def concentration_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Remove Top Events | Remaining Events | Remaining Profit |",
        "| ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['remove_top_events']} | {row['remaining_events']} | {fmt_units(row['remaining_profit'])} |"
        )
    return lines


def top_events_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Event Date | Bets | Profit | Mean Edge |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['event_date']} | {row['bets']} | {fmt_units(row['profit'])} | {fmt_pct(row['mean_edge'])} |"
        )
    return lines


def find_slice(rows: list[dict], label: str) -> dict | None:
    for row in rows:
        if row["slice"] == label:
            return row
    return None


def diagnostic_bullets(result: dict) -> list[str]:
    period_2024 = find_slice(result["by_period"], "2024")
    period_recent = find_slice(result["by_period"], "2025-2026")
    rank_1 = find_slice(result["by_event_rank"], "1")
    rank_2 = find_slice(result["by_event_rank"], "2")
    rank_3 = find_slice(result["by_event_rank"], "3")
    low_market = find_slice(result["by_market_prob_bin"], "<0.60")
    mid_edge = find_slice(result["by_edge_bin"], "0.03-0.05")
    high_edge = find_slice(result["by_edge_bin"], ">=0.08")
    middle = find_slice(result["by_title_group"], "middle_or_welter")
    light = find_slice(result["by_title_group"], "light_or_feather")
    recent_low_market = find_slice(result["by_period_market_bin"], "2025-2026 | <0.60")

    bullets = []
    if period_2024 and period_recent:
        bullets.append(
            "- Period stability is weak: 2024 produced {profit_2024}, while 2025-2026 produced {profit_recent} with market-null p `{p_recent}` and event-bootstrap P(profit <= 0) `{boot_recent}`.".format(
                profit_2024=fmt_units(period_2024["profit"]),
                profit_recent=fmt_units(period_recent["profit"]),
                p_recent=fmt_p(period_recent["market_null_p"]),
                boot_recent=fmt_p(period_recent["bootstrap_p_profit_le_zero"]),
            )
        )
    if rank_1 and rank_2 and rank_3:
        bullets.append(
            "- Residual-edge rank is not monotonic: rank 2 made {rank2}, rank 1 made {rank1}, and rank 3 was {rank3}. This argues against assuming every additional cap-3 slot carries the same edge.".format(
                rank2=fmt_units(rank_2["profit"]),
                rank1=fmt_units(rank_1["profit"]),
                rank3=fmt_units(rank_3["profit"]),
            )
        )
    if low_market and recent_low_market:
        bullets.append(
            "- The strongest price-regime result is lower-confidence favorites: market P `<0.60` made {low_profit} overall and {recent_low_profit} in 2025-2026, but this is only {recent_low_bets} recent bets and was identified after seeing the ledger.".format(
                low_profit=fmt_units(low_market["profit"]),
                recent_low_profit=fmt_units(recent_low_market["profit"]),
                recent_low_bets=recent_low_market["bets"],
            )
        )
    if mid_edge and high_edge:
        bullets.append(
            "- More residual edge was not automatically better: `0.03-0.05` edge made {mid_profit}, while `>=0.08` edge made {high_profit}.".format(
                mid_profit=fmt_units(mid_edge["profit"]),
                high_profit=fmt_units(high_edge["profit"]),
            )
        )
    if middle and light:
        bullets.append(
            "- Weight-class behavior is uneven: middle/welter made {middle_profit}, while light/feather made {light_profit}.".format(
                middle_profit=fmt_units(middle["profit"]),
                light_profit=fmt_units(light["profit"]),
            )
        )
    bullets.append(
        "- Event concentration is moderate: removing the top 10 events leaves {remaining}, and {events_to_erase} top events erase the aggregate profit.".format(
            remaining=fmt_units(result["event_concentration"]["removal_sensitivity"][3]["remaining_profit"]),
            events_to_erase=result["event_concentration"]["events_to_erase_profit"],
        )
    )
    return bullets


def markdown_report(result: dict) -> str:
    aggregate = result["aggregate"]
    concentration = result["event_concentration"]
    lines = [
        "# Residual Cap Regime Audit",
        "",
        "This diagnostic decomposes the frozen residual-meta top-edge cap-3",
        "historical paper ledger by market regime. It does not retrain the model,",
        "select new thresholds, or alter any frozen paper policy.",
        "",
        "## Inputs",
        "",
        f"- ranked cap bets: `{result['ranked_bets_path']}`",
        "- filter: `probability_policy == frozen_residual_meta` and `ranking_mode == top_edge`",
        f"- event-bootstrap iterations: `{result['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| bets | {aggregate['bets']} |",
        f"| events | {aggregate['events']} |",
        f"| profit | {fmt_units(aggregate['profit'])} |",
        f"| ROI | {fmt_pct(aggregate['roi'])} |",
        f"| actual - market | {fmt_pct(aggregate['actual_minus_market'])} |",
        f"| event-bootstrap P(profit <= 0) | {fmt_p(aggregate['bootstrap_p_profit_le_zero'])} |",
        f"| market-null p-value | {fmt_p(aggregate['market_null_p'])} |",
        "",
        "## Key Diagnostics",
        "",
        *diagnostic_bullets(result),
        "",
        "## By Period",
        "",
        *table(result["by_period"]),
        "",
        "## By Event Rank",
        "",
        "Rank is the residual-edge order within the event after applying cap `3`.",
        "",
        *table(result["by_event_rank"]),
        "",
        "## By Period And Rank",
        "",
        *table(result["by_period_rank"]),
        "",
        "## By Market Probability",
        "",
        *table(result["by_market_prob_bin"]),
        "",
        "## By Period And Market Probability",
        "",
        *table(result["by_period_market_bin"]),
        "",
        "## By Residual Edge",
        "",
        *table(result["by_edge_bin"]),
        "",
        "## By Model Probability",
        "",
        *table(result["by_model_prob_bin"]),
        "",
        "## By Odds Band",
        "",
        *table(result["by_odds_band"]),
        "",
        "## By Title Group",
        "",
        *table(result["by_title_group"]),
        "",
        "## Event Concentration",
        "",
        f"Events to erase aggregate profit: `{concentration['events_to_erase_profit']}`",
        "",
        *concentration_table(concentration["removal_sensitivity"]),
        "",
        "### Top Positive Events",
        "",
        *top_events_table(concentration["top_events"]),
        "",
        "## Interpretation",
        "",
        "- This is a diagnostic only; it is not permission to tune the frozen cap-3 policy after the fact.",
        "- The aggregate cap-3 result remains directionally interesting, but the regime tables weaken a broad live-edge claim.",
        "- A robust live edge claim would want positive results across recent periods, event ranks, and price bands; this ledger is too uneven for that.",
        "- The lower-confidence favorite pocket is worth watching in forward paper tracking, but should not be carved out as a new live policy from this same historical ledger.",
        "",
    ]
    return "\n".join(lines)


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    bets = load_cap_bets(args.ranked_bets)
    aggregate = summarize(
        bets,
        "aggregate",
        args.bootstrap_iterations,
        args.market_null_iterations,
        rng,
    )
    result = {
        "ranked_bets_path": args.ranked_bets,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "seed": args.seed,
        "aggregate": aggregate,
        "by_period": summarize_group(
            bets,
            "period",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_event_rank": summarize_group(
            bets,
            "event_rank",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_period_rank": summarize_group(
            bets,
            "period_rank",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_market_prob_bin": summarize_group(
            bets,
            "market_prob_bin",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_period_market_bin": summarize_group(
            bets,
            "period_market_bin",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_edge_bin": summarize_group(
            bets,
            "edge_bin",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_model_prob_bin": summarize_group(
            bets,
            "model_prob_bin",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_odds_band": summarize_group(
            bets,
            "odds_band",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "by_title_group": summarize_group(
            bets,
            "title_group",
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "event_concentration": event_concentration(bets),
    }
    return result


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_cap_regime_audit.json"
    md_path = output_dir / "residual_cap_regime_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    aggregate = result["aggregate"]
    print(
        "Frozen cap-3 aggregate: {profit}, market-null p={p_value}".format(
            profit=fmt_units(aggregate["profit"]),
            p_value=fmt_p(aggregate["market_null_p"]),
        )
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
