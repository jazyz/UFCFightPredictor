import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import betting_math  # noqa: E402


def bet(odds1, odds2, model_p1, **kw):
    return betting_math.decide_bet(model_p1, None, odds1, odds2, bankroll=1000.0, **kw)


def test_a_plus_200_pick_is_still_bet():
    # model 0.60 on a +200 dog: blend ~0.54 beats the de-vigged 0.32, Kelly positive
    result = bet(200, -250, 0.60)
    assert result is not None and result["side"] == 1


def test_a_pick_longer_than_plus_200_is_skipped():
    assert bet(201, -250, 0.60) is None


def test_the_cap_can_be_disabled():
    assert bet(201, -250, 0.60, max_dog_odds=None) is not None


def test_favorites_are_unaffected_by_the_cap():
    result = bet(-150, 130, 0.70)
    assert result is not None and result["side"] == 1


def test_default_cap_is_200():
    import inspect
    assert inspect.signature(betting_math.decide_bet).parameters["max_dog_odds"].default == 200
