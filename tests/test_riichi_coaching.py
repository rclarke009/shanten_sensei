"""Riichi tip branch: Declare riichi / Stay silent voice."""

from shanten_sensei.explain import (
    build_user_payload,
    template_explain,
    validate_explanation,
)
from shanten_sensei.live import (
    candidates_from_meta_options,
    is_riichi_decision_turn,
    is_tenpai_dama_discard_turn,
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
    assert "already threw" in result.summary.lower()
    assert "can’t win from a discard" in result.summary.lower()
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
    assert "Stay silent" in result.summary
    assert "Declare riichi" not in result.summary
    assert validate_explanation(turn, result) == []


def test_tenpai_dahai_without_reach_candidate_still_stay_silent():
    """Closed tenpai + Throw: still name dama when Mortal only ranked tiles."""
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="dahai 9p",
        candidates=candidates_from_meta_options([("9p", 0.8), ("5m", 0.2)]),
    )
    assert not is_riichi_decision_turn(turn)
    result = template_explain(turn)
    assert "Throw" in result.summary
    assert "Stay silent" in result.summary
    assert validate_explanation(turn, result) == []
    payload = build_user_payload(turn)
    assert payload["dama_discard_tenpai"] is True


def test_already_riichi_dahai_skips_stay_silent():
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="dahai 9p",
        candidates=candidates_from_meta_options([("9p", 0.8), ("5m", 0.2)]),
        riichi=True,
    )
    result = template_explain(turn)
    assert "Stay silent" not in result.summary
    assert "Throw" in result.summary
    assert build_user_payload(turn)["dama_discard_tenpai"] is False


def test_dama_discard_rejects_declare_riichi_polarity():
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="dahai 9p",
        candidates=candidates_from_meta_options([("9p", 0.8), ("5m", 0.2)]),
    )
    bad = Explanation(
        summary="Throw 9-pin, not 5-man. Declare riichi.",
        focus="efficiency",
        pinned_action="dahai 9p",
        contrasted_action="dahai 5m",
    )
    assert "action_lead_polarity_inverted" in validate_explanation(turn, bad)


def test_dahai_with_reach_next_best_stays_dama():
    """Reach as 2nd candidate must not steal riichi template — Stay silent."""
    hand = [
        "1m",
        "1m",
        "5mr",
        "6m",
        "7m",
        "7m",
        "2p",
        "2p",
        "3p",
        "3p",
        "4s",
        "4s",
        "7s",
        "7s",
    ]
    turn = turn_from_live(
        hand=hand,
        recommended="dahai 6m",
        candidates=candidates_from_meta_options([("6m", 0.7), ("reach", 0.2)]),
    )
    assert not is_riichi_decision_turn(turn)
    assert is_tenpai_dama_discard_turn(turn)
    result = template_explain(turn)
    assert "Throw" in result.summary
    assert "Stay silent" in result.summary
    assert "Declare riichi" not in result.summary
    assert "not reach" not in result.summary.lower()
    move_lines = [
        ln.lstrip("• ").strip()
        for ln in result.summary.split("\n\n")[0].splitlines()
        if ln.strip()
    ]
    assert any(ln.startswith("Throw") for ln in move_lines)
    assert any(ln.startswith("Stay silent") for ln in move_lines)
    assert validate_explanation(turn, result) == []


def test_dama_throw_only_fails_grounding():
    hand = [
        "1m",
        "1m",
        "5mr",
        "6m",
        "7m",
        "7m",
        "2p",
        "2p",
        "3p",
        "3p",
        "4s",
        "4s",
        "7s",
        "7s",
    ]
    turn = turn_from_live(
        hand=hand,
        recommended="dahai 6m",
        candidates=candidates_from_meta_options([("6m", 0.7), ("reach", 0.2)]),
    )
    bad = Explanation(
        summary=(
            "Throw 6-man. You’re tenpai (ready) with a tanki (single-tile pair) wait."
        ),
        focus="efficiency",
        pinned_action="dahai 6m",
        contrasted_action="reach",
    )
    errors = validate_explanation(turn, bad)
    assert "dama_discard_missing_stay_silent" in errors


def test_table_tips_declare_riichi_cut_tile():
    turn = turn_from_live(
        hand=RIICHI_HAND_RED_SOU,
        recommended={
            "type": "reach",
            "reach_dahai": {"type": "dahai", "pai": "5sr"},
        },
        candidates=candidates_from_meta_options([("reach", 0.85), ("none", 0.15)]),
    )
    off = template_explain(turn)
    assert "at a real table" not in off.summary.lower()
    assert "table_procedure" not in build_user_payload(turn)
    on = template_explain(turn, include_table_tips=True)
    assert "at a real table" in on.summary.lower()
    assert "stick" in on.summary.lower()
    assert "sideways" in on.summary.lower()
    assert "red 5-sou" in on.summary.lower()
    assert validate_explanation(turn, on) == []
    stamped = turn.model_copy(
        update={
            "features": turn.features.model_copy(
                update={
                    "context": {**turn.features.context, "include_table_tips": True}
                }
            )
        }
    )
    proc = build_user_payload(stamped).get("table_procedure")
    assert isinstance(proc, str) and proc
    assert "stick" in proc.lower()
    assert "red 5-sou" in proc.lower()


def test_table_tips_stay_silent_omits_placement():
    turn = turn_from_live(
        hand=RIICHI_HAND,
        recommended="none",
        candidates=candidates_from_meta_options([("none", 0.7), ("reach", 0.3)]),
        discards=["5m"],
    )
    result = template_explain(turn, include_table_tips=True)
    assert "Stay silent" in result.summary
    assert "at a real table" not in result.summary.lower()
    stamped = turn.model_copy(
        update={
            "features": turn.features.model_copy(
                update={
                    "context": {**turn.features.context, "include_table_tips": True}
                }
            )
        }
    )
    assert "table_procedure" not in build_user_payload(stamped)


def test_riichi_tip_skips_tenpai_wait_when_not_tenpai():
    """Don't claim ryanmen/tenpai when the calculator says shanten > 0."""
    turn = turn_from_live(
        hand=[
            "4m", "5m", "4p", "4p", "8p", "9p",
            "3s", "3s", "4s", "5s", "6s", "7s", "9s", "1m",
        ],
        recommended="reach",
        candidates=candidates_from_meta_options([("reach", 0.85), ("none", 0.15)]),
    )
    assert is_riichi_decision_turn(turn)
    assert turn.features.shanten != 0
    result = template_explain(turn)
    assert "Declare riichi" in result.summary
    assert "tenpai" not in result.summary.lower()
    assert "ryanmen" not in result.summary.lower()
    assert validate_explanation(turn, result) == []
