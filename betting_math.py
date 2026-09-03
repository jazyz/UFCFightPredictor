"""Single source of truth for bet-sizing math.

predict_event.py (live recommendations), betting_alpha.py (card betting) and
testing/testing_time_period.py (backtests) all route through here, so what the
backtests measure is exactly what production stakes. Pure functions, no I/O.

Doctrine: fractional Kelly (5% fraction, 5% cap, no floor), a minimum-edge
gate measured against DE-VIGGED market probabilities, and a betting
probability that blends model and market at w=0.8. Picks priced longer than +200 are skipped.
"""


def american_to_prob(odds):
    """Implied win probability of an American price (still includes the vig)."""
    if odds >= 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def devig(p1, p2):
    """Proportionally normalize two vigged implied probabilities to sum to 1."""
    total = p1 + p2
    if total <= 0:
        return p1, p2
    return p1 / total, p2 / total


def kelly(odds, prob):
    """Kelly criterion fraction for an American price and a win probability."""
    n = (100 / -odds) if odds < 0 else (odds / 100)
    return (n * prob - (1 - prob)) / n


def blend_prob(model_p, devig_p, w=0.8):
    """w*model + (1-w)*devigged market: the deployed betting probability.

    w=0.8 was tuned on 2021-2022 and validated on 2023 (testing/blend_compare.py).
    """
    return w * model_p + (1 - w) * devig_p


def size_bet(bankroll, kelly_frac, cap, kc):
    """Fractional-Kelly stake, capped. No floor: kc <= 0 stakes nothing."""
    if kc <= 0:
        return 0.0
    return min(bankroll * kelly_frac * kc, cap * bankroll)


def decide_bet(model_p1, model_p2, odds1, odds2, *, blend_w=0.8, min_edge=0.05,
               fraction=0.05, cap=0.05, dog_multiplier=1.0, max_dog_odds=200, bankroll):
    """Full decision for one bout; None when neither side clears the gates.

    model_p2 may be None when the model's probabilities are complementary.
    The chosen side is the PICK — the side with the higher betting
    probability — never the "value side" (the side where model most exceeds
    market): value-side selection concentrates bets on underdogs, the segment
    measured at flat-stake -3.5%/bet, and is exactly what the validated
    backtests did not do. The pick's edge is measured against its DE-VIGGED
    probability, and a bet requires edge >= min_edge and a positive Kelly.
    dog_multiplier scales the stake when the pick has positive odds
    (1.0 = no scaling; the half-stake-dogs experiment is a knob, not a
    default).
    max_dog_odds skips a pick priced strictly longer than +N (default +200, None
    disables it). The 2024-26 walk-forward study found picks beyond +200 lost at
    flat stakes (13 bets, 2-11); the cap removes the segment where the model is
    most often blind.
    """
    if model_p2 is None:
        model_p2 = 1.0 - model_p1
    market1, market2 = devig(american_to_prob(odds1), american_to_prob(odds2))
    p1 = blend_prob(model_p1, market1, blend_w)
    p2 = blend_prob(model_p2, market2, blend_w)
    side = 1 if p1 >= p2 else 2
    prob, market_prob, odds = (p1, market1, odds1) if side == 1 else (p2, market2, odds2)
    if max_dog_odds is not None and odds > max_dog_odds:
        return None
    edge = prob - market_prob
    kc = kelly(odds, prob)
    if edge < min_edge or kc <= 0:
        return None
    stake = size_bet(bankroll, fraction, cap, kc)
    if odds > 0:
        stake *= dog_multiplier
    return dict(side=side, name_index=side - 1, prob=prob, market_prob=market_prob,
                edge=edge, kc=kc, stake=stake)
