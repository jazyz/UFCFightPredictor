"""Export the public site's data file from a walk-forward prediction cache.

Replays data/fight_results_with_odds.csv over the per-retrain predictions that
testing_time_period.find_fights cached, scores every fight the model covered,
and sizes bets through betting_math.decide_bet at the production config.
Writes frontend/src/data/backtest.json and copies the live ledger to
frontend/src/data/ledger.json.

    python testing/export_site_data.py                       # defaults below
    python testing/export_site_data.py --cache DIR --start YYYY-MM-DD --end YYYY-MM-DD
"""
import argparse
import csv
import glob
import inspect
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import betting_math  # noqa: E402

# Production betting config, copied from betting_math.decide_bet's defaults.
_DECIDE_BET_DEFAULTS = {k: p.default for k, p in inspect.signature(betting_math.decide_bet).parameters.items()
                        if p.default is not inspect.Parameter.empty}
BLEND_W = _DECIDE_BET_DEFAULTS["blend_w"]
MIN_EDGE = _DECIDE_BET_DEFAULTS["min_edge"]
KELLY_FRACTION = _DECIDE_BET_DEFAULTS["fraction"]
KELLY_MAX = _DECIDE_BET_DEFAULTS["cap"]
MAX_DOG_ODDS = _DECIDE_BET_DEFAULTS["max_dog_odds"]
START_BANKROLL = 1000.0
FLAT_STAKE = 10.0
BANDS = [("50–55%", 0.50, 0.55), ("55–60%", 0.55, 0.60), ("60–65%", 0.60, 0.65),
         ("65–70%", 0.65, 0.70), ("70%+", 0.70, 1.01)]

DEFAULT_CACHE = os.path.join(ROOT, "test_results", ".tier2_full_cache")
DEFAULT_ODDS = os.path.join(ROOT, "data", "fight_results_with_odds.csv")
DEFAULT_OUT = os.path.join(ROOT, "frontend", "src", "data", "backtest.json")
DEFAULT_LEDGER = os.path.join(ROOT, "data", "bet_ledger.json")
DEFAULT_LEDGER_OUT = os.path.join(ROOT, "frontend", "src", "data", "ledger.json")
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2026-08-30"


# ----------------------------------------------------------------- payload types

@dataclass
class Window:
    start: str
    end: str
    retrains: List[str]


@dataclass
class Coverage:
    fights_in_window: int
    scored: int
    with_odds: int


@dataclass
class Metrics:
    accuracy: float
    auc: float
    log_loss: float
    brier: float
    n: int


@dataclass
class Band:
    label: str
    lo: float
    hi: float
    n: int
    stated: Optional[float]
    hit: Optional[float]


@dataclass
class MonthRow:
    month: str
    n: int
    hit: float


@dataclass
class MarketRow:
    name: str
    accuracy: float
    auc: float
    log_loss: float
    brier: float


@dataclass
class Agreement:
    n: int
    hit: Optional[float]


@dataclass
class Disagreement:
    n: int
    model_hit: Optional[float]


@dataclass
class MarketSection:
    rows: List[MarketRow]
    agree: Agreement
    disagree: Disagreement


@dataclass
class FlatSection:
    market_favorite_per_bet: float
    model_pick_per_bet: float
    stake: float


@dataclass
class SideRecord:
    won: int
    total: int


@dataclass
class BettingSummary:
    final: float
    return_pct: float
    bets: int
    hit: Optional[float]
    favorites: SideRecord
    underdogs: SideRecord
    max_drawdown_pct: float
    low: float


@dataclass
class BankrollPoint:
    date: str
    event: str
    bankroll: float


@dataclass
class BetRecord:
    date: str
    event: str
    fighter: str
    opponent: str
    odds: int
    model_prob: float
    market_prob: float
    edge: float
    stake: float
    result: str
    pnl: float
    bankroll_after: float
    source: str = "backtest"


@dataclass
class BacktestPayload:
    generated: str
    window: Window
    coverage: Coverage
    metrics: Metrics
    bands: List[Band]
    monthly: List[MonthRow]
    market: MarketSection
    flat: FlatSection
    betting: BettingSummary
    bankroll: List[BankrollPoint]
    bets: List[BetRecord]


@dataclass
class Range:
    start: str
    end: str
    retrains: List[str]


@dataclass
class Config:
    blend_w: float
    min_edge: float
    kelly_fraction: float
    kelly_cap: float
    max_dog_odds: Optional[int]
    start_bankroll: float
    flat_stake: float


@dataclass
class DefaultWindow:
    start: str
    end: str


@dataclass
class Bet:
    """The production decision for one fight, independent of bankroll: stake_frac is
    stake / bankroll and payout_mult is profit per $1 staked."""
    side: int
    odds: int
    prob: float
    market_prob: float
    edge: float
    kc: float
    stake_frac: float
    payout_mult: float


@dataclass
class FightRow:
    date: str
    event: str
    f1: str
    f2: str
    winner: str            # "f1" | "f2" | "push" | "unknown" (unknown only when unscored)
    model_p1: Optional[float]
    market_p1: Optional[float]
    odds1: Optional[int]
    odds2: Optional[int]
    bet: Optional[Bet]


@dataclass
class Summary:
    coverage: Coverage
    metrics: Metrics
    bands: List[Band]
    monthly: List[MonthRow]
    market: MarketSection
    flat: FlatSection
    betting: BettingSummary
    bankroll: List[BankrollPoint]
    bets: List[BetRecord]


@dataclass
class SitePayload:
    generated: str
    range: Range
    config: Config
    default_window: DefaultWindow
    summary: Summary
    fights: List[FightRow]


@dataclass
class Scored:
    """One fight the model covered, in the form every section needs."""
    date: str            # YYYY-MM-DD
    month: str           # YYYY-MM
    event: str
    f1: str
    f2: str
    winner: str          # f1, f2, or "draw/no contest"
    model_p1: float      # two-orientation average P(f1 wins)
    odds1: Optional[int]
    odds2: Optional[int]
    market_p1: Optional[float]   # de-vigged P(f1 wins); None without odds


# ------------------------------------------------------------------- inputs

def load_caches(cache_dir: str) -> Dict[str, Dict[Tuple[str, str], float]]:
    """{'YYYY-MM-DD': {(red, blue): P(red wins)}} for every pred_*.csv in the dir."""
    caches = {}
    for path in sorted(glob.glob(os.path.join(cache_dir, "pred_*.csv"))):
        date = os.path.basename(path)[len("pred_"):-len(".csv")]
        table = {}
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                p = float(row["Probability"])
                if row["Predicted Result"] != "win":
                    p = 1 - p
                table[(row["Red Fighter"], row["Blue Fighter"])] = p
        caches[date] = table
    if not caches:
        raise SystemExit(f"no pred_*.csv files in {cache_dir}")
    return caches


def cache_for(caches, date_iso: str):
    """The latest cache trained on or before this fight date (find_fights' retrain rule)."""
    eligible = [d for d in caches if d <= date_iso]
    if not eligible:
        raise ValueError(f"no cache trained on or before {date_iso}")
    return caches[max(eligible)]


def read_window(odds_csv: str, start: datetime, end: datetime) -> List[dict]:
    rows = []
    with open(odds_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            date = datetime.strptime(row["event_date"], "%b %d %Y")
            if start <= date <= end:
                rows.append(row)
    return rows


def parse_odds(text: str) -> Optional[int]:
    text = text.replace("−", "-")
    return None if text == "-" else int(text)


def score_fights(rows: List[dict], caches) -> List[Scored]:
    scored = []
    for row in rows:
        iso = datetime.strptime(row["event_date"], "%b %d %Y").strftime("%Y-%m-%d")
        table = cache_for(caches, iso)
        f1, f2 = row["fighter1_name"], row["fighter2_name"]
        p_ab, p_ba = table.get((f1, f2)), table.get((f2, f1))
        if p_ab is None or p_ba is None:
            continue
        odds1, odds2 = parse_odds(row["fighter1_odds"]), parse_odds(row["fighter2_odds"])
        market_p1 = None
        if odds1 is not None and odds2 is not None:
            market_p1, _ = betting_math.devig(betting_math.american_to_prob(odds1),
                                              betting_math.american_to_prob(odds2))
        scored.append(Scored(date=iso, month=iso[:7], event=row["event_name"], f1=f1, f2=f2,
                             winner=row["winner_name"], model_p1=(p_ab + (1 - p_ba)) / 2,
                             odds1=odds1, odds2=odds2, market_p1=market_p1))
    return scored


# ------------------------------------------------------------------ sections

def decided(fights: List[Scored]) -> List[Scored]:
    return [s for s in fights if s.winner in (s.f1, s.f2)]


def pick_hit(s: Scored) -> Tuple[float, bool]:
    """(stated confidence of the model's pick, whether the pick won)."""
    if s.model_p1 >= 0.5:
        return s.model_p1, s.winner == s.f1
    return 1 - s.model_p1, s.winner == s.f2


def _metrics(ps: List[float], ys: List[int]) -> Tuple[float, float, float, float]:
    """accuracy, AUC, log loss, Brier for P(fighter 1 wins) against 1/0 outcomes."""
    clipped = [min(max(p, 1e-6), 1 - 1e-6) for p in ps]
    acc = sum((p >= 0.5) == (y == 1) for p, y in zip(ps, ys)) / len(ps)
    auc = roc_auc_score(ys, ps) if len(set(ys)) > 1 else float("nan")
    return (acc, float(auc), float(log_loss(ys, clipped, labels=[0, 1])),
            float(brier_score_loss(ys, clipped)))


def prediction_metrics(fights: List[Scored]) -> Metrics:
    ps = [s.model_p1 for s in fights]
    ys = [1 if s.winner == s.f1 else 0 for s in fights]
    acc, auc, ll, br = _metrics(ps, ys)
    return Metrics(accuracy=round(acc, 4), auc=round(auc, 4), log_loss=round(ll, 4),
                   brier=round(br, 4), n=len(fights))


def calibration_bands(fights: List[Scored]) -> List[Band]:
    out = []
    for label, lo, hi in BANDS:
        rows = [pick_hit(s) for s in fights if lo <= pick_hit(s)[0] < hi]
        n = len(rows)
        out.append(Band(label=label, lo=lo, hi=min(hi, 1.0), n=n,
                        stated=round(sum(c for c, _ in rows) / n, 4) if n else None,
                        hit=round(sum(h for _, h in rows) / n, 4) if n else None))
    return out


def monthly_accuracy(fights: List[Scored]) -> List[MonthRow]:
    by_month: Dict[str, List[bool]] = {}
    for s in fights:
        by_month.setdefault(s.month, []).append(pick_hit(s)[1])
    return [MonthRow(month=m, n=len(h), hit=round(sum(h) / len(h), 4))
            for m, h in sorted(by_month.items())]


def market_section(fights: List[Scored]) -> MarketSection:
    """fights: decided AND priced."""
    ys = [1 if s.winner == s.f1 else 0 for s in fights]
    rows = []
    series = [
        ("De-vigged market", [s.market_p1 for s in fights]),
        ("Model (ensemble)", [s.model_p1 for s in fights]),
        (f"Blend · {BLEND_W:g} model + {1 - BLEND_W:g} market",
         [betting_math.blend_prob(s.model_p1, s.market_p1, BLEND_W) for s in fights]),
    ]
    for name, ps in series:
        acc, auc, ll, br = _metrics(ps, ys)
        rows.append(MarketRow(name=name, accuracy=round(acc, 4), auc=round(auc, 4),
                              log_loss=round(ll, 4), brier=round(br, 4)))
    agree = [s for s in fights if (s.model_p1 >= 0.5) == (s.market_p1 >= 0.5)]
    disagree = [s for s in fights if (s.model_p1 >= 0.5) != (s.market_p1 >= 0.5)]

    def hit_rate(group):
        return round(sum(pick_hit(s)[1] for s in group) / len(group), 4) if group else None

    return MarketSection(rows=rows, agree=Agreement(n=len(agree), hit=hit_rate(agree)),
                         disagree=Disagreement(n=len(disagree), model_hit=hit_rate(disagree)))


def payout(odds: int, stake: float) -> float:
    """Profit on a winning stake at an American price."""
    return stake * (100 / -odds) if odds < 0 else stake * (odds / 100)


def settle(winner: str, name: str, odds: int, stake: float) -> Tuple[str, float]:
    if winner == name:
        return "win", payout(odds, stake)
    if winner == "draw/no contest":
        return "push", 0.0
    return "loss", -stake


def flat_section(fights: List[Scored]) -> FlatSection:
    """Return per $1 staked at a flat FLAT_STAKE on every decided, priced fight."""
    def per_bet(choose):
        total = sum(settle(s.winner, *choose(s), FLAT_STAKE)[1] for s in fights)
        return round(total / (FLAT_STAKE * len(fights)), 4) if fights else 0.0

    favorite = per_bet(lambda s: (s.f1, s.odds1) if s.market_p1 >= 0.5 else (s.f2, s.odds2))
    model = per_bet(lambda s: (s.f1, s.odds1) if s.model_p1 >= 0.5 else (s.f2, s.odds2))
    return FlatSection(market_favorite_per_bet=favorite, model_pick_per_bet=model, stake=FLAT_STAKE)


def max_drawdown(series: List[float]) -> float:
    peak, worst = series[0], 0.0
    for x in series:
        peak = max(peak, x)
        worst = max(worst, (peak - x) / peak if peak else 0.0)
    return worst


def replay_bets(fights: List[Scored]) -> Tuple[BettingSummary, List[BankrollPoint], List[BetRecord]]:
    """Compound a $1,000 bankroll over every priced fight in file order (pushes included,
    exactly as testing_time_period.process_fight does). Bankroll math stays unrounded."""
    bankroll = START_BANKROLL
    points: List[BankrollPoint] = []
    bets: List[BetRecord] = []
    won = {"fav": 0, "dog": 0}
    total = {"fav": 0, "dog": 0}
    for s in fights:
        bet = betting_math.decide_bet(s.model_p1, None, s.odds1, s.odds2, blend_w=BLEND_W,
                                      min_edge=MIN_EDGE, fraction=KELLY_FRACTION, cap=KELLY_MAX,
                                      bankroll=bankroll)
        if bet is not None:
            name, opponent, odds = ((s.f1, s.f2, s.odds1) if bet["name_index"] == 0
                                    else (s.f2, s.f1, s.odds2))
            result, pnl = settle(s.winner, name, odds, bet["stake"])
            bankroll += pnl
            side = "fav" if odds < 0 else "dog"
            total[side] += 1
            won[side] += result == "win"
            bets.append(BetRecord(date=s.date, event=s.event, fighter=name, opponent=opponent,
                                  odds=odds, model_prob=round(bet["prob"], 4),
                                  market_prob=round(bet["market_prob"], 4),
                                  edge=round(bet["edge"], 4), stake=round(bet["stake"], 2),
                                  result=result, pnl=round(pnl, 2),
                                  bankroll_after=round(bankroll, 2)))
        points.append(BankrollPoint(date=s.date, event=s.event, bankroll=round(bankroll, 2)))
    series = [START_BANKROLL] + [p.bankroll for p in points]
    n_bets = total["fav"] + total["dog"]
    n_won = won["fav"] + won["dog"]
    summary = BettingSummary(
        final=round(bankroll, 2),
        return_pct=round((bankroll - START_BANKROLL) / START_BANKROLL * 100, 1),
        bets=n_bets, hit=round(n_won / n_bets, 4) if n_bets else None,
        favorites=SideRecord(won=won["fav"], total=total["fav"]),
        underdogs=SideRecord(won=won["dog"], total=total["dog"]),
        max_drawdown_pct=round(max_drawdown(series) * 100, 1), low=round(min(series), 2))
    return summary, points, bets


def build_payload(caches, odds_csv: str, start: str, end: str) -> BacktestPayload:
    rows = read_window(odds_csv, datetime.strptime(start, "%Y-%m-%d"),
                       datetime.strptime(end, "%Y-%m-%d"))
    scored = score_fights(rows, caches)
    dec = decided(scored)
    priced = [s for s in scored if s.market_p1 is not None]
    dec_priced = [s for s in dec if s.market_p1 is not None]
    summary, points, bets = replay_bets(priced)
    return BacktestPayload(
        generated=datetime.now().isoformat(timespec="seconds"),
        window=Window(start=start, end=end, retrains=sorted(d for d in caches if start <= d <= end)),
        coverage=Coverage(fights_in_window=len(rows), scored=len(dec), with_odds=len(dec_priced)),
        metrics=prediction_metrics(dec),
        bands=calibration_bands(dec),
        monthly=monthly_accuracy(dec),
        market=market_section(dec_priced),
        flat=flat_section(dec_priced),
        betting=summary, bankroll=points, bets=bets)


def config_from_betting_math() -> Config:
    return Config(blend_w=BLEND_W, min_edge=MIN_EDGE, kelly_fraction=KELLY_FRACTION,
                  kelly_cap=KELLY_MAX, max_dog_odds=MAX_DOG_ODDS,
                  start_bankroll=START_BANKROLL, flat_stake=FLAT_STAKE)


def fight_rows(rows: List[dict], caches) -> List[FightRow]:
    """One row per odds-file fight; unscored and unpriced fights carry nulls."""
    out = []
    for row in rows:
        iso = datetime.strptime(row["event_date"], "%b %d %Y").strftime("%Y-%m-%d")
        table = cache_for(caches, iso)
        f1, f2 = row["fighter1_name"], row["fighter2_name"]
        p_ab, p_ba = table.get((f1, f2)), table.get((f2, f1))
        model_p1 = None if p_ab is None or p_ba is None else (p_ab + (1 - p_ba)) / 2
        odds1, odds2 = parse_odds(row["fighter1_odds"]), parse_odds(row["fighter2_odds"])
        market_p1 = None
        if odds1 is not None and odds2 is not None:
            market_p1, _ = betting_math.devig(betting_math.american_to_prob(odds1),
                                              betting_math.american_to_prob(odds2))
        name = row["winner_name"]
        winner = "f1" if name == f1 else "f2" if name == f2 else "push" if name == "draw/no contest" else "unknown"
        if winner == "unknown" and model_p1 is not None:
            raise SystemExit(f"scored fight {f1} vs {f2} on {iso} has an unrecognized winner {name!r}")
        bet = None
        if model_p1 is not None and market_p1 is not None:
            decision = betting_math.decide_bet(model_p1, None, odds1, odds2, blend_w=BLEND_W,
                                               min_edge=MIN_EDGE, fraction=KELLY_FRACTION,
                                               cap=KELLY_MAX, bankroll=1.0)
            if decision is not None:
                odds = odds1 if decision["side"] == 1 else odds2
                bet = Bet(side=decision["side"], odds=odds, prob=round(decision["prob"], 4),
                          market_prob=round(decision["market_prob"], 4), edge=round(decision["edge"], 4),
                          kc=round(decision["kc"], 4), stake_frac=decision["stake"],
                          payout_mult=payout(odds, 1.0))
        out.append(FightRow(date=iso, event=row["event_name"], f1=f1, f2=f2, winner=winner,
                            model_p1=model_p1, market_p1=market_p1, odds1=odds1, odds2=odds2, bet=bet))
    return out


def build_site_payload(caches, odds_csv: str, start: str, end: str) -> SitePayload:
    rows = read_window(odds_csv, datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d"))
    fights = fight_rows(rows, caches)  # validates winners before any aggregation
    v1 = build_payload(caches, odds_csv, start, end)
    summary = Summary(coverage=v1.coverage, metrics=v1.metrics, bands=v1.bands, monthly=v1.monthly,
                      market=v1.market, flat=v1.flat, betting=v1.betting, bankroll=v1.bankroll, bets=v1.bets)
    return SitePayload(generated=v1.generated,
                       range=Range(start=start, end=end, retrains=v1.window.retrains),
                       config=config_from_betting_math(),
                       default_window=DefaultWindow(start=start, end=end),
                       summary=summary, fights=fights)


# ---------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=DEFAULT_CACHE, help="dir of pred_YYYY-MM-DD.csv files")
    ap.add_argument("--odds", default=DEFAULT_ODDS)
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--ledger-out", default=DEFAULT_LEDGER_OUT)
    args = ap.parse_args(argv)

    payload = build_site_payload(load_caches(args.cache), args.odds, args.start, args.end)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(asdict(payload), fh, indent=1)
    os.makedirs(os.path.dirname(args.ledger_out), exist_ok=True)
    if os.path.exists(args.ledger):
        shutil.copy(args.ledger, args.ledger_out)
    else:
        with open(args.ledger_out, "w") as fh:
            fh.write("[]\n")

    m, b = payload.summary.metrics, payload.summary.betting
    print(f"{m.n} fights scored · accuracy {m.accuracy:.1%} · AUC {m.auc:.3f} · "
          f"log loss {m.log_loss:.3f} · Brier {m.brier:.3f}")
    print(f"{b.bets} bets · hit {(b.hit or 0):.1%} · final ${b.final:,.2f} ({b.return_pct:+.1f}%) · "
          f"max drawdown {b.max_drawdown_pct:.1f}%")
    print(f"{len(payload.fights)} fight rows · {payload.range.start} → {payload.range.end} · "
          f"retrains {', '.join(payload.range.retrains)}")
    print(f"wrote {os.path.relpath(args.out, ROOT)} and {os.path.relpath(args.ledger_out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
