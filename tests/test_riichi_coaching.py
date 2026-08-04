"""Riichi tip branch: Declare riichi / Stay silent voice."""

from shanten_sensei.explain import (
    build_user_payload,
    template_explain,
    validate_explanation,
)
from shanten_sensei.live import (
    candidates_from_meta_options,
    is_riichi_decision_turn,
    turn_from_live,
)
from shanten_sensei.schema import Explanation
from shanten_sensei.tiles import (
    coach_action_label,
    human_tile_label,
    is_riichi_decision_action,
)

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

# Same shape with red 5-sou as the riichi cut
RIICHI_HAND_RED_SOU = [
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
    "5sr",
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


def test_live_declare_riichi_mentions_furiten_tsumo_only():
    # Ryanmen tenpai after cutting 9p; 7s already in river → furiten.
    hand = [
        "1m", "2m", "3m", "4m", "5m", "6m",
        "1p", "2p", "3p", "9p",
        "4s", "5s", "6s", "7s",
    ]
    turn = turn_from_live(
        hand=hand,
        recommended={
            "type": "reach",
            "reach_dahai": {"type": "dahai", "pai": "9p"},
        },
        candidates=candidates_from_meta_options([("reach", 0.85), ("9p", 0.15)]),
        discards=["7s"],
    )
    assert is_riichi_decision_turn(turn)
    assert turn.features.context.get("reach_discard") == "9p"
    assert turn.features.statuses.furiten is True
    result = template_explain(turn)
    assert "Declare riichi" in result.summary
    assert "9-pin" in result.summary.lower()
    assert "furiten" in result.summary
    assert "tsumo" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_live_declare_riichi_names_reach_dahai():
    turn = turn_from_live(
        hand=RIICHI_HAND_RED_SOU,
        recommended={
            "type": "reach",
            "reach_dahai": {"type": "dahai", "pai": "5sr"},
        },
        candidates=candidates_from_meta_options([("reach", 0.85), ("none", 0.15)]),
        dora_indicators=["4m"],
    )
    assert turn.features.context.get("reach_discard") == "5sr"
    assert is_riichi_decision_turn(turn)
    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Declare riichi" in result.summary
    assert "discard" in result.summary.lower()
    assert "red 5-sou" in result.summary.lower()
    assert "Skip" not in result.summary
    assert validate_explanation(turn, result) == []

    payload = build_user_payload(turn)
    assert payload["reach_discard"] == "5sr"
    assert payload["reach_discard_display"] == human_tile_label("5sr")


def test_live_reach_discard_from_context():
    turn = turn_from_live(
        hand=RIICHI_HAND_RED_SOU,
        recommended="reach",
        candidates=candidates_from_meta_options([("reach", 0.9), ("none", 0.1)]),
        context={"reach_discard": "5sr"},
    )
    assert turn.features.context.get("reach_discard") == "5sr"
    result = template_explain(turn)
    assert "red 5-sou" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_riichi_summary_omitting_reach_discard_fails_grounding():
    turn = turn_from_live(
        hand=RIICHI_HAND_RED_SOU,
        recommended={
            "type": "reach",
            "reach_dahai": {"type": "dahai", "pai": "5sr"},
        },
        candidates=candidates_from_meta_options([("reach", 0.85), ("none", 0.15)]),
    )
    bad = Explanation(
        summary="Declare riichi. You’re tenpai (ready).",
        focus="tempo",
        pinned_action="reach",
        contrasted_action="none",
    )
    errors = validate_explanation(turn, bad)
    assert any("reach discard" in e for e in errors)


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
    assert "discard" not in result.summary.lower()
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
