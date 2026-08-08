"""Hora / agari tip branch: Take the win voice."""

from shanten_sensei.explain import (
    build_user_payload,
    coaching_shape_goals,
    template_explain,
    validate_explanation,
)
from shanten_sensei.glosses import NO_CLEAR_SHAPE, format_aiming_for
from shanten_sensei.live import (
    candidates_from_meta_options,
    is_hora_decision_turn,
    turn_from_live,
)
from shanten_sensei.schema import (
    DerivedFeatures,
    GameState,
    HandStatuses,
    MortalCandidate,
    MortalOutput,
    TurnExplainInput,
    UkeireInfo,
)
from shanten_sensei.tiles import coach_action_label, is_hora_decision_action

# Complete winning hand (shanten -1): 123m 567m 55p 888p 789s
HORA_HAND = [
    "1m",
    "2m",
    "3m",
    "5m",
    "6m",
    "7m",
    "5p",
    "5p",
    "8p",
    "8p",
    "8p",
    "7s",
    "8s",
    "9s",
]

# Ron prompt: 13-tile tenpai waiting on 2-sou (tanki)
RON_HAND = [
    "4m",
    "4m",
    "5m",
    "5m",
    "5m",
    "6p",
    "6p",
    "7p",
    "7p",
    "8p",
    "8p",
    "2s",
    "2s",
]


def _ron_hora_turn(
    *,
    raw_expected: dict | None = None,
    ukeire_tiles: list[str] | None = None,
) -> TurnExplainInput:
    tiles = ukeire_tiles or ["2s", "4m"]
    return TurnExplainInput(
        game_state=GameState(
            hand=list(RON_HAND),
            visible_discards={"1": ["2s"]},
        ),
        mortal_output=MortalOutput(
            recommended="hora",
            candidates=[
                MortalCandidate(action="hora", prob=0.95),
                MortalCandidate(action="none", prob=0.05),
            ],
            raw_expected=raw_expected,
        ),
        features=DerivedFeatures(
            shanten=0,
            ukeire=UkeireInfo(count=len(tiles), tiles=tiles),
            statuses=HandStatuses(
                shanten=0,
                tenpai=True,
                wait_shape="tanki",
                riichi=True,
            ),
        ),
        player_action="hora",
        mortal_best="hora",
        diverge=False,
    )


def test_coach_action_label_take_the_win():
    assert coach_action_label("hora") == "Take the win"
    assert is_hora_decision_action("hora")


def test_live_hora_voice():
    turn = turn_from_live(
        hand=HORA_HAND,
        recommended="hora",
        candidates=candidates_from_meta_options([("hora", 0.95), ("none", 0.05)]),
        dora_indicators=["4p"],
        riichi=True,
    )
    assert turn.features.shanten == -1
    assert is_hora_decision_turn(turn)
    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Take the win" in result.summary
    assert "hora" not in result.summary.lower()
    assert "tenpai" not in result.summary.lower()
    assert "complete" in result.summary.lower() or "winning" in result.summary.lower()
    assert "dora" in result.summary.lower()
    assert "waiting on" not in result.summary.lower()
    assert "win on" not in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_hora_ron_says_win_on_not_waiting():
    turn = _ron_hora_turn(
        raw_expected={"type": "hora", "pai": "2s"},
        ukeire_tiles=["2s", "4m"],
    )
    assert is_hora_decision_turn(turn)
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "take the win" in summary_l
    assert "win on" in summary_l
    assert "2-sou" in summary_l or "2s" in summary_l
    assert "waiting on" not in summary_l
    assert validate_explanation(turn, result) == []


def test_hora_ron_reaction_pai_picks_tile_among_shanpon_waits():
    turn = _ron_hora_turn(
        raw_expected={"type": "hora", "pai": "2s"},
        ukeire_tiles=["2s", "4m"],
    )
    result = template_explain(turn)
    assert result.summary.count("4-man") == 0
    assert "2-sou" in result.summary or "2s" in result.summary.lower()


def test_hora_suppresses_aiming_for_shape_goals():
    turn = turn_from_live(
        hand=HORA_HAND,
        recommended="hora",
        candidates=candidates_from_meta_options([("hora", 0.9), ("none", 0.1)]),
    )
    assert turn.features.shanten == -1
    assert coaching_shape_goals(turn) == []
    assert format_aiming_for(coaching_shape_goals(turn)) == NO_CLEAR_SHAPE
    payload = build_user_payload(turn)
    assert payload["hora_decision"] is True
    assert payload["shape_goals"] == []
    assert payload["hand_metric_glossary"]["shanten"] == "winning hand"
    assert payload["mortal_best_display"] == "Take the win"
