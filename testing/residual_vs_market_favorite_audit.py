#!/usr/bin/env python3
"""Compare frozen residual cap bets against market-only favorite benchmarks.

The frozen residual cap-3 ledger is almost entirely favorite exposure. This
diagnostic asks whether the residual ranking adds value beyond simple
market-only favorite selection on the same event dates and with the same
per-event bet counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.statistical_edge_audit import implied_prob, net_odds, parse_odds  # noqa: E402
from utils.name_matching import canonical_name  # noqa: E402


DEFAULT_LEDGER = "test_results/nested_edge_long/ledgers/regularized_lgbm_2022_2026/no_leakage_backtest.csv"
DEFAULT_RANKED_BETS = "test_results/residual_event_cap_ranking_audit/ranked_cap_bets.csv"


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark residual cap bets versus market favorites")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--ranked-bets", default=DEFAULT_RANKED_BETS)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--market-null-iterations", type=int, default=20000)
    parser.add_argument("--random-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--output-dir", default="test_results/residual_vs_market_favorite_audit")
    return parser.parse_args()


def fmt_units(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value, digits=2) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"{100.0 * float(value):.{digits}f}%"


def fmt_p(value) -> str:
    if value is None or not np.isfinite(value):
        return ""
    if float(value) < 0.001:
        return "<0.001"
    return f"{float(value):.3f}"


def win_profit_from_odds(odds: np.ndarray) -> np.ndarray:
    odds = np.asarray(odds, dtype=float)
    return np.where(odds > 0.0, odds / 100.0, 100.0 / np.abs(odds))


def flat_profit(odds: float, won: bool) -> float:
    return float(net_odds(odds) if won else -1.0)


def devig_pair(odds1, odds2) -> tuple[float, float] | None:
    raw1 = implied_prob(odds1)
    raw2 = implied_prob(odds2)
    total = raw1 + raw2 if np.isfinite(raw1) and np.isfinite(raw2) else np.nan
    if not np.isfinite(total) or total <= 0.0:
        return None
    return float(raw1 / total), float(raw2 / total)


def load_market_favorites(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    rows = []
    for _, row in df.iterrows():
        event_date = pd.to_datetime(row.get("event_date"), errors="coerce")
        if pd.isna(event_date):
            continue

        fighter1 = canonical_name(row.get("odds_fighter1_name", ""))
        fighter2 = canonical_name(row.get("odds_fighter2_name", ""))
        winner = canonical_name(row.get("winner_name", ""))
        if not fighter1 or not fighter2 or not winner:
            continue

        odds1 = parse_odds(row.get("fighter1_odds"))
        odds2 = parse_odds(row.get("fighter2_odds"))
        if odds1 is None or odds2 is None:
            continue
        devig = devig_pair(odds1, odds2)
        if devig is None:
            continue
        market1, market2 = devig

        if market1 >= market2:
            selected = {
                "selected_side": "fighter1",
                "selected_fighter": row.get("odds_fighter1_name", ""),
                "selected_fighter_key": fighter1,
                "selected_odds": float(odds1),
                "selected_market_probability": market1,
                "selected_won": winner == fighter1,
            }
        else:
            selected = {
                "selected_side": "fighter2",
                "selected_fighter": row.get("odds_fighter2_name", ""),
                "selected_fighter_key": fighter2,
                "selected_odds": float(odds2),
                "selected_market_probability": market2,
                "selected_won": winner == fighter2,
            }

        if selected["selected_market_probability"] < 0.5:
            continue

        selected["event_date"] = event_date.normalize()
        selected["event_year"] = int(event_date.year)
        selected["fight_key"] = "|".join(
            [
                event_date.date().isoformat(),
                "|".join(sorted([fighter1, fighter2])),
            ]
        )
        selected["title"] = row.get("title", "")
        selected["flat_profit"] = flat_profit(selected["selected_odds"], selected["selected_won"])
        rows.append(selected)

    if not rows:
        raise SystemExit(f"No market favorite rows loaded from {path}")
    return pd.DataFrame(rows)


def load_residual_bets(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_date"])
    required = {
        "event_date",
        "fight_key",
        "selected_odds",
        "selected_market_probability",
        "selected_won",
        "flat_profit",
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
        raise SystemExit("No frozen_residual_meta/top_edge bets found")
    bets["event_date"] = pd.to_datetime(bets["event_date"]).dt.normalize()
    bets["event_year"] = bets["event_date"].dt.year.astype(int)
    bets["benchmark"] = "residual_cap3"
    return bets


def summarize(df: pd.DataFrame, label: str, iterations: int, market_iterations: int, rng) -> dict:
    if df.empty:
        return {
            "benchmark": label,
            "bets": 0,
            "events": 0,
            "profit": 0.0,
            "roi": None,
            "actual_win_rate": None,
            "mean_market_probability": None,
            "actual_minus_market": None,
            "event_bootstrap_p_profit_le_zero": None,
            "event_bootstrap_profit_ci_95": [None, None],
            "market_null_p": None,
            "market_null_mean_profit": None,
            "market_null_profit_ci_95": [None, None],
        }

    profit = df["flat_profit"].astype(float)
    actual = df["selected_won"].astype(float)
    market = df["selected_market_probability"].astype(float)
    bootstrap = event_bootstrap_profit(df, iterations, rng)
    market_null = market_null_profit(df, market_iterations, rng)
    return {
        "benchmark": label,
        "bets": int(len(df)),
        "events": int(df["event_date"].nunique()),
        "profit": float(profit.sum()),
        "roi": float(profit.mean()),
        "actual_win_rate": float(actual.mean()),
        "mean_market_probability": float(market.mean()),
        "actual_minus_market": float(actual.mean() - market.mean()),
        "event_bootstrap_p_profit_le_zero": bootstrap["p_profit_le_zero"],
        "event_bootstrap_profit_ci_95": bootstrap["profit_ci_95"],
        "market_null_p": market_null["p_observed_or_better"],
        "market_null_mean_profit": market_null["mean_profit"],
        "market_null_profit_ci_95": market_null["profit_ci_95"],
    }


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


def market_null_profit(df: pd.DataFrame, iterations: int, rng) -> dict:
    if df.empty or iterations <= 0:
        return {"p_observed_or_better": None, "mean_profit": None, "profit_ci_95": [None, None]}
    market = df["selected_market_probability"].astype(float).to_numpy()
    odds = df["selected_odds"].astype(float).to_numpy()
    win_profit = win_profit_from_odds(odds)
    observed = float(df["flat_profit"].astype(float).sum())
    wins = rng.random((iterations, len(df))) < market
    profits = np.where(wins, win_profit, -1.0).sum(axis=1)
    return {
        "p_observed_or_better": float((np.sum(profits >= observed) + 1) / (iterations + 1)),
        "mean_profit": float(np.mean(profits)),
        "profit_ci_95": [float(value) for value in np.percentile(profits, [2.5, 97.5])],
    }


def apply_same_event_counts(
    market_favorites: pd.DataFrame,
    residual_bets: pd.DataFrame,
    mode: str,
) -> pd.DataFrame:
    event_counts = residual_bets.groupby("event_date").size().to_dict()
    rows = []
    for event_date, count in sorted(event_counts.items()):
        event_favorites = market_favorites[market_favorites["event_date"] == event_date].copy()
        if event_favorites.empty:
            continue
        if mode == "top_market":
            ordered = event_favorites.sort_values(
                ["selected_market_probability", "fight_key"],
                ascending=[False, True],
            )
        elif mode == "low_conf_market":
            ordered = event_favorites.sort_values(
                ["selected_market_probability", "fight_key"],
                ascending=[True, True],
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
        kept = ordered.head(int(count)).copy()
        kept["benchmark"] = mode
        rows.append(kept)
    if not rows:
        return pd.DataFrame(columns=market_favorites.columns)
    return pd.concat(rows, ignore_index=True)


def apply_cap_per_event(market_favorites: pd.DataFrame, cap: int, mode: str) -> pd.DataFrame:
    if mode == "top_market":
        ordered = market_favorites.sort_values(
            ["event_date", "selected_market_probability", "fight_key"],
            ascending=[True, False, True],
        )
    elif mode == "low_conf_market":
        ordered = market_favorites.sort_values(
            ["event_date", "selected_market_probability", "fight_key"],
            ascending=[True, True, True],
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")
    kept = ordered.groupby("event_date", sort=False).head(cap).copy()
    kept["benchmark"] = f"{mode}_cap{cap}"
    return kept


def random_same_event_distribution(
    market_favorites: pd.DataFrame,
    residual_bets: pd.DataFrame,
    iterations: int,
    rng,
) -> dict:
    event_counts = residual_bets.groupby("event_date").size().to_dict()
    event_groups = []
    for event_date, count in sorted(event_counts.items()):
        event_favorites = market_favorites[market_favorites["event_date"] == event_date].copy()
        if event_favorites.empty:
            continue
        profits = event_favorites["flat_profit"].astype(float).to_numpy()
        keep = min(int(count), len(profits))
        event_groups.append((event_date, profits, keep))

    if not event_groups:
        return {
            "iterations": iterations,
            "mean_profit": None,
            "profit_ci_95": [None, None],
            "prob_profit_positive": None,
            "p_random_profit_at_least_residual": None,
        }

    residual_profit = float(residual_bets["flat_profit"].astype(float).sum())
    samples = np.zeros(iterations, dtype=float)
    for index in range(iterations):
        profit = 0.0
        for _, profits, keep in event_groups:
            if keep >= len(profits):
                chosen = np.arange(len(profits))
            else:
                chosen = rng.choice(len(profits), size=keep, replace=False)
            profit += float(profits[chosen].sum())
        samples[index] = profit

    return {
        "iterations": int(iterations),
        "events": int(len(event_groups)),
        "mean_profit": float(np.mean(samples)),
        "profit_ci_95": [float(value) for value in np.percentile(samples, [2.5, 97.5])],
        "prob_profit_positive": float(np.mean(samples > 0.0)),
        "p_random_profit_at_least_residual": float(
            (np.sum(samples >= residual_profit) + 1) / (iterations + 1)
        ),
    }


def paired_event_bootstrap(residual: pd.DataFrame, benchmark: pd.DataFrame, iterations: int, rng) -> dict:
    residual_by_event = residual.groupby("event_date", sort=True)["flat_profit"].sum()
    benchmark_by_event = benchmark.groupby("event_date", sort=True)["flat_profit"].sum()
    events = sorted(set(residual_by_event.index) | set(benchmark_by_event.index))
    if not events:
        return {"diff_profit": None, "p_diff_le_zero": None, "diff_ci_95": [None, None]}
    residual_values = np.asarray([residual_by_event.get(event, 0.0) for event in events], dtype=float)
    benchmark_values = np.asarray([benchmark_by_event.get(event, 0.0) for event in events], dtype=float)
    diff_values = residual_values - benchmark_values
    observed = float(diff_values.sum())
    sampled = rng.integers(0, len(diff_values), size=(iterations, len(diff_values)))
    diffs = diff_values[sampled].sum(axis=1)
    return {
        "events": int(len(events)),
        "diff_profit": observed,
        "p_diff_le_zero": float((np.sum(diffs <= 0.0) + 1) / (iterations + 1)),
        "diff_ci_95": [float(value) for value in np.percentile(diffs, [2.5, 97.5])],
    }


def period_summaries(frames: dict[str, pd.DataFrame], iterations: int, market_iterations: int, rng) -> list[dict]:
    rows = []
    for label, frame in frames.items():
        for period_label, subset in [
            ("2024", frame[frame["event_year"] == 2024]),
            ("2025-2026", frame[frame["event_year"] >= 2025]),
            ("last_365d", frame[frame["event_date"] >= pd.Timestamp("2025-06-28")]),
        ]:
            summary = summarize(subset.copy(), label, iterations, market_iterations, rng)
            summary["period"] = period_label
            rows.append(summary)
    return rows


def audit(args) -> dict:
    rng = np.random.default_rng(args.seed)
    residual = load_residual_bets(args.ranked_bets)
    favorites = load_market_favorites(args.ledger)

    start = residual["event_date"].min()
    end = residual["event_date"].max()
    same_period = favorites[(favorites["event_date"] >= start) & (favorites["event_date"] <= end)].copy()
    same_events = same_period[same_period["event_date"].isin(set(residual["event_date"]))].copy()

    benchmarks = {
        "residual_cap3": residual.copy(),
        "market_top_same_count": apply_same_event_counts(same_events, residual, "top_market"),
        "market_low_conf_same_count": apply_same_event_counts(same_events, residual, "low_conf_market"),
        "market_top3_same_events": apply_cap_per_event(same_events, 3, "top_market"),
        "market_low_conf3_same_events": apply_cap_per_event(same_events, 3, "low_conf_market"),
        "all_market_favorites_same_events": same_events.assign(benchmark="all_market_favorites_same_events"),
        "all_market_favorites_same_period": same_period.assign(benchmark="all_market_favorites_same_period"),
    }

    summaries = [
        summarize(frame.copy(), label, args.bootstrap_iterations, args.market_null_iterations, rng)
        for label, frame in benchmarks.items()
    ]
    paired = {
        label: paired_event_bootstrap(residual, frame, args.bootstrap_iterations, rng)
        for label, frame in benchmarks.items()
        if label != "residual_cap3"
    }
    random_favorite = random_same_event_distribution(
        same_events,
        residual,
        args.random_iterations,
        rng,
    )

    return {
        "ledger_path": args.ledger,
        "ranked_bets_path": args.ranked_bets,
        "bootstrap_iterations": args.bootstrap_iterations,
        "market_null_iterations": args.market_null_iterations,
        "random_iterations": args.random_iterations,
        "seed": args.seed,
        "date_window": {
            "start": str(start.date()),
            "end": str(end.date()),
            "residual_events": int(residual["event_date"].nunique()),
            "same_event_market_favorite_rows": int(len(same_events)),
            "same_period_market_favorite_rows": int(len(same_period)),
        },
        "summaries": summaries,
        "period_summaries": period_summaries(
            {
                "residual_cap3": benchmarks["residual_cap3"],
                "market_top_same_count": benchmarks["market_top_same_count"],
                "market_low_conf_same_count": benchmarks["market_low_conf_same_count"],
            },
            args.bootstrap_iterations,
            args.market_null_iterations,
            rng,
        ),
        "paired_event_bootstrap_vs_residual": paired,
        "random_market_favorites_same_count": random_favorite,
    }


def summary_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Benchmark | Bets | Events | Profit | ROI | Actual | Market P | Actual - Market | Bootstrap P(profit <= 0) | Market-Null p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {label} | {bets} | {events} | {profit} | {roi} | {actual} | {market} | {actual_market} | {boot} | {null} |".format(
                label=row["benchmark"],
                bets=row["bets"],
                events=row["events"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual=fmt_pct(row["actual_win_rate"]),
                market=fmt_pct(row["mean_market_probability"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                boot=fmt_p(row["event_bootstrap_p_profit_le_zero"]),
                null=fmt_p(row["market_null_p"]),
            )
        )
    return lines


def period_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Period | Benchmark | Bets | Profit | ROI | Actual - Market | Market-Null p |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {period} | {label} | {bets} | {profit} | {roi} | {actual_market} | {null} |".format(
                period=row["period"],
                label=row["benchmark"],
                bets=row["bets"],
                profit=fmt_units(row["profit"]),
                roi=fmt_pct(row["roi"]),
                actual_market=fmt_pct(row["actual_minus_market"]),
                null=fmt_p(row["market_null_p"]),
            )
        )
    return lines


def paired_table(rows: dict[str, dict]) -> list[str]:
    lines = [
        "| Benchmark | Residual - Benchmark Profit | Bootstrap P(diff <= 0) | 95% Diff CI |",
        "| --- | ---: | ---: | --- |",
    ]
    for label, row in rows.items():
        ci = row["diff_ci_95"]
        ci_text = "" if ci[0] is None else f"{fmt_units(ci[0])} to {fmt_units(ci[1])}"
        lines.append(
            "| {label} | {diff} | {p_value} | {ci} |".format(
                label=label,
                diff=fmt_units(row["diff_profit"]),
                p_value=fmt_p(row["p_diff_le_zero"]),
                ci=ci_text,
            )
        )
    return lines


def markdown_report(result: dict) -> str:
    summaries = {row["benchmark"]: row for row in result["summaries"]}
    period = {
        (row["benchmark"], row["period"]): row
        for row in result["period_summaries"]
    }
    residual = summaries["residual_cap3"]
    top_same = summaries["market_top_same_count"]
    low_same = summaries["market_low_conf_same_count"]
    residual_last365 = period[("residual_cap3", "last_365d")]
    top_last365 = period[("market_top_same_count", "last_365d")]
    low_last365 = period[("market_low_conf_same_count", "last_365d")]
    random_summary = result["random_market_favorites_same_count"]
    paired_top = result["paired_event_bootstrap_vs_residual"]["market_top_same_count"]
    paired_low = result["paired_event_bootstrap_vs_residual"]["market_low_conf_same_count"]

    lines = [
        "# Residual Vs Market Favorite Audit",
        "",
        "This diagnostic compares the frozen residual-meta top-edge cap-3 ledger",
        "against market-only favorite benchmarks on the same historical event",
        "dates. It does not retrain the model or change any frozen policy.",
        "",
        "## Inputs",
        "",
        f"- market/source ledger: `{result['ledger_path']}`",
        f"- residual ranked bets: `{result['ranked_bets_path']}`",
        f"- residual window: `{result['date_window']['start']}` to `{result['date_window']['end']}`",
        f"- residual events: `{result['date_window']['residual_events']}`",
        f"- same-event market favorite rows: `{result['date_window']['same_event_market_favorite_rows']}`",
        f"- event-bootstrap iterations: `{result['bootstrap_iterations']}`",
        f"- market-null iterations: `{result['market_null_iterations']}`",
        f"- random favorite iterations: `{result['random_iterations']}`",
        "",
        "## Key Diagnostics",
        "",
        "- Residual cap-3 made {residual_profit} on {residual_bets} bets.".format(
            residual_profit=fmt_units(residual["profit"]),
            residual_bets=residual["bets"],
        ),
        "- Top market favorites with the same per-event bet counts made {top_profit}; paired event-bootstrap P(residual <= top-market) was `{top_p}`.".format(
            top_profit=fmt_units(top_same["profit"]),
            top_p=fmt_p(paired_top["p_diff_le_zero"]),
        ),
        "- Low-confidence market favorites with the same per-event bet counts made {low_profit}; paired event-bootstrap P(residual <= low-confidence) was `{low_p}`.".format(
            low_profit=fmt_units(low_same["profit"]),
            low_p=fmt_p(paired_low["p_diff_le_zero"]),
        ),
        "- Random same-event favorite selections averaged {random_mean}; P(random >= residual) was `{random_p}`.".format(
            random_mean=fmt_units(random_summary["mean_profit"]),
            random_p=fmt_p(random_summary["p_random_profit_at_least_residual"]),
        ),
        "- The recent caveat remains: over the last 365 days residual cap-3 made {residual_recent}, top-market same-count favorites made {top_recent}, and low-confidence same-count favorites made {low_recent}.".format(
            residual_recent=fmt_units(residual_last365["profit"]),
            top_recent=fmt_units(top_last365["profit"]),
            low_recent=fmt_units(low_last365["profit"]),
        ),
        "",
        "## Benchmark Summary",
        "",
        *summary_table(result["summaries"]),
        "",
        "## Same-Event Paired Bootstrap",
        "",
        *paired_table(result["paired_event_bootstrap_vs_residual"]),
        "",
        "## Random Same-Event Favorite Selection",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| iterations | {random_summary['iterations']} |",
        f"| events | {random_summary['events']} |",
        f"| mean profit | {fmt_units(random_summary['mean_profit'])} |",
        f"| 95% profit interval | {fmt_units(random_summary['profit_ci_95'][0])} to {fmt_units(random_summary['profit_ci_95'][1])} |",
        f"| probability random profit > 0 | {fmt_pct(random_summary['prob_profit_positive'])} |",
        f"| P(random >= residual) | {fmt_p(random_summary['p_random_profit_at_least_residual'])} |",
        "",
        "## Period Summary",
        "",
        *period_table(result["period_summaries"]),
        "",
        "## Interpretation",
        "",
        "- This is a benchmark diagnostic, not a policy change.",
        "- If residual cap-3 cannot beat same-event market-only favorite rules, the model-specific edge claim is weak.",
        "- Here residual cap-3 does beat top-market, low-confidence, all-favorite, and random same-event favorite exposure historically, which supports residual selection as more than generic favorite betting.",
        "- The support is still not a live-edge claim: the low-confidence paired interval crosses zero, and the last-365-day residual result remains only slightly positive.",
        "- Any such narrower hypothesis still needs future paper tracking before live staking escalation.",
        "",
    ]
    return "\n".join(lines)


def main():
    args = parse_args()
    result = audit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "residual_vs_market_favorite_audit.json"
    md_path = output_dir / "residual_vs_market_favorite_audit.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    summaries = {row["benchmark"]: row for row in result["summaries"]}
    print(
        "Residual cap3 {residual}; top-market same-count {top}; low-conf same-count {low}".format(
            residual=fmt_units(summaries["residual_cap3"]["profit"]),
            top=fmt_units(summaries["market_top_same_count"]["profit"]),
            low=fmt_units(summaries["market_low_conf_same_count"]["profit"]),
        )
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
