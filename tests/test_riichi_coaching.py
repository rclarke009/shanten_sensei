"""Riichi tip branch: Declare riichi / Stay silent voice."""

from shanten_sensei.explain import template_explain, validate_explanation
from shanten_sensei.live import (
    candidates_from_meta_options,
    is_riichi_decision_turn,
    turn_from_live,
)
from shanten_sensei.tiles import coach_action_label, is_riichi_decision_action

# Closed tenpai-ish hand with dora path: 123m 123p 456s + pair + 9p
RIICHI_HAND = [
    "1m",
    "2m",
    "3m",
    "1p",
    "2p",
    "3p",
    "4s",
    "5s",
    "6s",
    "8s",
    "8s",
    "9p",
    "5m",
    "5m",
]


def test_coach_action_label_declare_riichi():
    assert coach_action_label("reach") == "Declare riichi"
    assert is_riichi_decision_action("reach")


def test_live_declare_riichi_voice():
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="reach",
        candidates=candidates_from_meta_options([("reach", 0.85), ("none", 0.15)]),
        dora_indicators=["4m"],
    )
    assert is_riichi_decision_turn(turn)
    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Declare riichi" in result.summary
    assert "Skip" not in result.summary
    assert "tenpai" in result.summary.lower() or "ready" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_live_stay_silent_vs_riichi():
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="none",
        candidates=candidates_from_meta_options([("none", 0.7), ("reach", 0.3)]),
        discards=["5m"],
    )
    assert is_riichi_decision_turn(turn)
    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Stay silent" in result.summary
    assert "Skip" not in result.summary
    assert validate_explanation(turn, result) == []


def test_dahai_with_low_prob_reach_stays_throw():
    """Reach as a third candidate must not steal discard coaching."""
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="dahai 9p",
        candidates=candidates_from_meta_options(
            [("9p", 0.8), ("5m", 0.15), ("reach", 0.05)]
        ),
    )
    assert not is_riichi_decision_turn(turn)
    result = template_explain(turn)
    assert "Throw" in result.summary
