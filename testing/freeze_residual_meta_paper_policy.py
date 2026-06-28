#!/usr/bin/env python3
"""Freeze a residual-meta paper-betting policy for future tracking."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze residual-meta paper policy")
    parser.add_argument("--as-of-date", default=datetime.now().date().isoformat())
    parser.add_argument(
        "--transform",
        default="test_results/frozen_market_residual_meta/frozen_market_residual_meta.json",
        help="frozen residual probability transform JSON",
    )
    parser.add_argument(
        "--source-audit",
        default="test_results/residual_meta_pnl_audit/fixed_edge02_prob60/residual_meta_pnl_audit.json",
        help="fixed-policy historical diagnostic JSON",
    )
    parser.add_argument("--min-edge", type=float, default=0.02)
    parser.add_argument("--min-probability", type=float, default=0.60)
    parser.add_argument("--max-underdog-odds", type=float, default=300.0)
    parser.add_argument("--stake-units", type=float, default=1.0)
    parser.add_argument("--output-dir", default="test_results/frozen_residual_meta_paper_policy")
    return parser.parse_args()


def load_json(path: str) -> dict | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    with file_path.open() as file:
        return json.load(file)


def fmt_units(value) -> str:
    if value is None:
        return ""
    return f"{float(value):+.2f}u"


def fmt_pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2%}"


def fmt_p(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.3f}"


def markdown_report(result: dict) -> str:
    policy = result["policy"]
    transform = result["transform_summary"]
    diagnostics = result.get("historical_diagnostics") or {}
    aggregate = diagnostics.get("aggregate") or {}
    bootstrap = diagnostics.get("event_bootstrap") or {}
    market_null = diagnostics.get("market_null") or {}

    lines = [
        "# Frozen Residual Meta Paper Policy",
        "",
        f"As-of date: `{result['as_of_date']}`",
        f"Frozen transform: `{result['transform_path']}`",
        f"Historical diagnostic: `{result['source_audit']}`",
        "",
        "This is a paper-tracking contract only. It is intentionally separated",
        "from any live staking recommendation because the nested PnL evidence is",
        "weak and post-freeze outcomes have not accumulated.",
        "",
        "## Probability Transform",
        "",
        f"- base residual model: `{transform['model_label']}`",
        f"- transform training window: `{transform['dev_start']}` to `{transform['dev_end']}`",
        f"- logistic C: `{transform['c']}`",
        "",
        "| Term | Value |",
        "| --- | ---: |",
        f"| intercept | {transform['intercept']:.8f} |",
    ]
    for feature, coefficient in transform["coefficients"].items():
        lines.append(f"| `{feature}` | {coefficient:.8f} |")

    lines.extend(
        [
            "",
            "## Paper Betting Rule",
            "",
            "For each future fight with a regularized model probability and market odds:",
            "",
            "1. Compute de-vigged market probabilities for both fighters.",
            "2. Apply the frozen residual transform to the red-side probability.",
            "3. Set blue meta probability to `1 - red meta probability`.",
            "4. Compute `meta probability - market probability` for both sides.",
            "5. Paper bet the side with the largest positive residual edge only if all thresholds pass.",
            "",
            "| Rule | Value |",
            "| --- | ---: |",
            f"| minimum residual edge | {policy['min_edge']:.2%} |",
            f"| minimum meta probability | {policy['min_probability']:.2%} |",
            f"| maximum underdog odds | +{policy['max_underdog_odds']:.0f} |",
            f"| stake | {policy['stake_units']:.2f}u flat paper stake |",
            "",
            "## Historical Diagnostic",
            "",
            "This diagnostic uses the fixed policy historically. It is not post-freeze",
            "evidence and should not be treated as proof of a live edge.",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| folds | {aggregate.get('folds', '')} |",
            f"| holdout bets | {aggregate.get('bets', '')} |",
            f"| flat profit | {fmt_units(aggregate.get('profit'))} |",
            f"| flat ROI | {fmt_pct(aggregate.get('roi'))} |",
            f"| actual - market | {fmt_pct(aggregate.get('actual_minus_market'))} |",
            f"| positive folds | {aggregate.get('positive_folds', '')} / {aggregate.get('folds', '')} |",
            f"| event-bootstrap P(profit <= 0) | {fmt_p(bootstrap.get('prob_profit_le_zero'))} |",
            f"| market-null p-value | {fmt_p(market_null.get('p_value_observed_or_better'))} |",
            "",
            "## Frozen Rules",
            "",
            "- Do not alter the transform coefficients, thresholds, side-selection rule, or stake size after future outcomes are known.",
            "- Archive paper-bet ledgers before outcomes are known.",
            "- Score future paper bets against market-null and event-bootstrap tests before making any real edge claim.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    args = parse_args()
    transform = load_json(args.transform)
    if transform is None:
        raise SystemExit(f"Missing frozen transform: {args.transform}")
    source_audit = load_json(args.source_audit)

    transform_summary = {
        "model_label": transform["model_label"],
        "dev_start": transform["dev_start"],
        "dev_end": transform["dev_end"],
        "c": transform["c"],
        "intercept": transform["transform"]["intercept"],
        "coefficients": transform["transform"]["coefficients"],
    }
    result = {
        "as_of_date": args.as_of_date,
        "transform_path": args.transform,
        "source_audit": args.source_audit,
        "transform_summary": transform_summary,
        "policy": {
            "side_policy": "best_residual_edge",
            "min_edge": args.min_edge,
            "min_probability": args.min_probability,
            "max_underdog_odds": args.max_underdog_odds,
            "stake_units": args.stake_units,
            "settlement": "flat_units",
        },
        "historical_diagnostics": {
            "aggregate": (source_audit or {}).get("aggregate"),
            "event_bootstrap": (source_audit or {}).get("event_bootstrap"),
            "market_null": (source_audit or {}).get("market_null"),
        },
        "freeze_warning": (
            "This residual-meta paper policy is frozen for future paper tracking. "
            "Do not alter transform coefficients, thresholds, side-selection rule, "
            "or stake size after future outcomes are known."
        ),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "frozen_residual_meta_paper_policy.json"
    md_path = output_dir / "frozen_residual_meta_paper_policy.md"
    with json_path.open("w") as file:
        json.dump(result, file, indent=2)
    md_path.write_text(markdown_report(result))

    print(f"Frozen residual meta paper policy as of {args.as_of_date}")
    print(f"Min edge: {args.min_edge:.2%}")
    print(f"Min probability: {args.min_probability:.2%}")
    print(f"Max underdog odds: +{args.max_underdog_odds:.0f}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
