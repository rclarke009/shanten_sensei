"""Template voice regression tests (copy-sensitive)."""

from conftest import (
    bullet_lines,
    false_safer_tip_turn,
    make_turn,
    strip_bullets,
    summary_blocks,
    summary_lines,
    summary_paragraphs,
)

import re

import pytest

from shanten_sensei.explain import (
    build_detail_paragraph,
    build_user_payload,
    score_explanation_substance,
    template_explain,
    validate_explanation,
    wall_note,
)
from shanten_sensei.glosses import glossed_shanten as _glossed_shanten_phrase
from shanten_sensei.schema import (
    DerivedFeatures,
    Explanation,
    GameState,
    HandShapeNote,
    HandStatuses,
    MortalCandidate,
    MortalOutput,
    ScoreSituation,
    TurnExplainInput,
    UkeireInfo,
)
from shanten_sensei.tiles import human_tile_label

pytestmark = pytest.mark.eval

def test_template_not_thin():
    turn = make_turn(shape_goals=["tanyao"], dora_in_hand=["3s"])
    result = template_explain(turn)
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False
    assert "shanten" in score.anchors or "ukeire" in score.anchors
    assert "Throw" in result.summary
    assert "3-shanten (3 steps from ready)" in result.summary
    assert "ukeire (tiles that improve the hand)" in result.summary
    assert "builds toward tanyao" in result.summary
    assert validate_explanation(turn, result) == []


def test_template_wait_gloss_and_furiten_because():
    turn = TurnExplainInput(
        game_state=GameState(
            hand=[
                "1m",
                "2m",
                "3m",
                "4m",
                "5m",
                "6m",
                "1p",
                "2p",
                "3p",
                "4s",
                "5s",
                "6s",
                "7s",
                "9p",
            ],
            discards=["7s"],
        ),
        mortal_output=MortalOutput(
            recommended="dahai 4m",
            candidates=[
                MortalCandidate(action="dahai 4m", prob=0.6),
                MortalCandidate(action="dahai 6m", prob=0.3),
            ],
        ),
        features=DerivedFeatures(
            shanten=0,
            ukeire=UkeireInfo(count=6, tiles=["4s", "7s"]),
            statuses=HandStatuses(
                shanten=0,
                tenpai=True,
                wait_shape="ryanmen",
                furiten=True,
            ),
            shape_goals=[],
        ),
        player_action="dahai 6m",
        mortal_best="dahai 4m",
        diverge=True,
    )
    result = template_explain(turn)
    assert "Throw" in result.summary
    assert "ryanmen (two-sided open) wait" in result.summary
    assert "furiten" in result.summary
    assert "7-sou" in result.summary
    assert "any discard" in result.summary
    assert "tsumo" in result.summary.lower()
    assert result.focus in ("defense", "mixed")
    payload = build_user_payload(turn)
    assert payload["wait_shape_glossary"]["ryanmen"] == "two-sided open"
    assert any("7-sou" in t for t in payload["furiten_blocking_tiles"])
    assert validate_explanation(turn, result) == []


def test_template_tanyao_honor_ukeire_contrast():
    turn = make_turn(
        shape_goals=["tanyao"],
        mortal_best="dahai W",
        player_action="dahai 7s",
        diverge=True,
        ukeire=UkeireInfo(count=55, tiles=["2m"], remaining_by_tile={"2m": 3}),
        ukeire_alt=UkeireInfo(count=41, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_honor", tile="W")
    ]
    result = template_explain(turn)
    assert "Throw" in result.summary
    assert "improving tiles" in result.summary
    assert "vs about" in result.summary
    assert "builds toward tanyao" in result.summary
    assert "floating honor" in result.summary
    assert "outside tanyao" in result.summary
    assert "ukeire (tiles that improve the hand)" not in result.summary
    assert "\n" in result.summary
    move_lines = summary_lines(summary_paragraphs(result.summary)[0])
    state_lines = summary_lines(summary_paragraphs(result.summary)[1])
    assert move_lines[0].startswith("Throw")
    assert "floating honor" in move_lines[1].lower()
    assert "outside tanyao" in move_lines[1].lower()
    assert any("vs about" in line for line in move_lines)
    assert move_lines.index(next(l for l in move_lines if "vs about" in l)) > 1
    assert any("builds toward tanyao" in line for line in state_lines)
    assert "floating honor" not in " ".join(state_lines).lower()
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False
    assert "ukeire" in score.anchors
    assert "hand_shape_note" in score.anchors
    assert validate_explanation(turn, result) == []


def test_template_ukeire_contrast_move_lines_and_state_break():
    """Screenshot-shaped: 4m vs 2s ukeire contrast with named tiles on both cuts."""
    turn = make_turn(
        shape_goals=["pinfu"],
        mortal_best="dahai 4m",
        player_action="dahai 4m",
        danger={"4m": "genbutsu"},
        ukeire=UkeireInfo(
            count=47,
            tiles=["6m", "7m", "8m", "9m"],
            remaining_by_tile={"6m": 3, "7m": 3, "8m": 2, "9m": 4},
        ),
        ukeire_alt=UkeireInfo(
            count=42,
            tiles=["4m", "6m", "7m", "8m"],
            remaining_by_tile={"4m": 3, "6m": 3, "7m": 3, "8m": 2},
        ),
        diverge=False,
    )
    turn.mortal_output.candidates = [
        MortalCandidate(action="dahai 4m", prob=0.79),
        MortalCandidate(action="dahai 2s", prob=0.11),
    ]
    result = template_explain(turn)
    paras = summary_paragraphs(result.summary)
    move_lines = summary_lines(paras[0])
    state_lines = summary_lines(paras[1])
    assert len(move_lines) >= 4
    assert "4-man" in move_lines[0] and "2-sou" in move_lines[0]
    assert any("vs about" in line for line in move_lines)
    assert any("keeps draws like" in line for line in move_lines)
    assert any(
        "if you threw" in line.lower() and "instead" in line.lower()
        for line in move_lines
    )
    assert any("mostly improve via" in line for line in move_lines)
    assert "; throwing" not in result.summary.lower()
    assert any("3-shanten" in line for line in state_lines)
    assert any("already discarded" in line.lower() for line in state_lines)
    assert validate_explanation(turn, result) == []


def test_template_floating_terminal_and_isolated_kanchan():
    turn = make_turn(
        shape_goals=["tanyao"],
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        diverge=True,
        ukeire=UkeireInfo(count=40, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_terminal", tile="9p")
    ]
    result = template_explain(turn)
    assert "floating terminal" in result.summary
    assert "outside tanyao" in result.summary
    assert "hand_shape_note" in score_explanation_substance(
        turn, result.summary
    ).anchors

    turn2 = make_turn(mortal_best="dahai 2m", player_action="dahai 5s", diverge=True)
    turn2.features.hand_shape_notes = [
        HandShapeNote(kind="isolated_kanchan", tile="2m")
    ]
    result2 = template_explain(turn2)
    assert "2-man breaks up a closed middle" in result2.summary
    assert "kanchan" in result2.summary
    assert not re.search(
        r"\b(?:kanchan|penchan|fragment)\b(?:\s*\([^)]*\))?\s+on\s+2-man\b",
        result2.summary,
        re.I,
    )
    assert validate_explanation(turn2, result2) == []


def test_template_dead_end_is_cut_reason_not_keep():
    turn = make_turn(
        mortal_best="dahai N",
        player_action="dahai 2m",
        diverge=True,
        ukeire=UkeireInfo(count=15, tiles=["3m"], remaining_by_tile={"3m": 3}),
    )
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="N")]
    result = template_explain(turn)
    assert "is a dead-end tile" in result.summary
    assert "maintain" not in result.summary.lower()
    assert not re.search(r"\bkeeps?\s+(?:a\s+)?dead", result.summary, re.I)
    assert "hand_shape_note" in score_explanation_substance(
        turn, result.summary
    ).anchors
    assert validate_explanation(turn, result) == []


def test_template_dora_keep_separate_from_dead_end_cut():
    """Dora-keep and cut dead-end must not read as one dash-linked sentence."""
    turn = make_turn(
        mortal_best="dahai 9m",
        player_action="dahai N",
        diverge=True,
        dora_in_hand=["5pr"],
        ukeire=UkeireInfo(count=96, tiles=["2m", "3m"]),
    )
    turn.features.shanten = 5
    turn.features.statuses.shanten = 5
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="9m")]
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "keeping" in summary_l and "dora" in summary_l
    assert "is a dead-end tile" in result.summary
    assert not re.search(
        r"keeping dora[^.\n]*—[^.\n]*dead-end",
        result.summary,
        re.I,
    )


def test_template_dora_keep_and_dead_end_on_separate_lines():
    """Screenshot-shaped: dora-keep and cut reason on separate lines; no gloss echo."""
    turn = make_turn(
        mortal_best="dahai 1s",
        player_action="dahai S",
        diverge=True,
        dora_in_hand=["5pr"],
        ukeire=UkeireInfo(count=91, tiles=["2m", "3m"], remaining_by_tile={"7z": 1}),
    )
    turn.features.shanten = 5
    turn.features.statuses.shanten = 5
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="1s")]
    result = template_explain(turn)
    paras = summary_paragraphs(result.summary)
    assert len(paras) == 2
    move_text = " ".join(summary_lines(paras[0]))
    state_text = " ".join(summary_lines(paras[1]))
    assert move_text.startswith("Throw")
    assert "dead-end tile" in move_text
    assert "ukeire" in move_text.lower()
    assert state_text.startswith("Keeping dora")
    assert "red 5-pin" in state_text
    assert "1-sou" in move_text.lower() or "1s" in move_text.lower()
    assert "connects to nothing useful" not in result.summary.lower()
    assert result.detail and "connects to nothing useful" in result.detail.lower()


def test_template_chiitoi_dora_separate_from_floating_honor_cut():
    """Screenshot-shaped: fits-with-dora must not dash-glue floating-honor cut reason."""
    turn = make_turn(
        shape_goals=["chiitoi"],
        mortal_best="dahai W",
        player_action="dahai N",
        diverge=True,
        dora_in_hand=["1m"],
        ukeire=UkeireInfo(
            count=10,
            tiles=["4m", "6m", "8m"],
            remaining_by_tile={"4m": 2, "6m": 3, "8m": 2},
        ),
        ukeire_alt=UkeireInfo(
            count=9,
            tiles=["4m", "6m", "8m"],
            remaining_by_tile={"4m": 2, "6m": 3, "8m": 2},
        ),
    )
    turn.game_state.hand = [
        "1m",
        "1m",
        "4m",
        "4m",
        "6m",
        "8m",
        "8m",
        "8p",
        "8p",
        "F",
        "F",
        "W",
        "N",
    ]
    turn.features.shanten = 2
    turn.features.statuses.shanten = 2
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_honor", tile="W"),
    ]
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "builds toward chiitoi" in summary_l
    assert "with dora" in summary_l
    assert "floating honor" in summary_l
    assert "outside chiitoi" in summary_l
    assert not re.search(
        r"with dora[^.\n]*—[^.\n]*floating",
        result.summary,
        re.I,
    )
    lines = summary_lines(summary_paragraphs(result.summary)[0])
    state_lines = summary_lines(summary_paragraphs(result.summary)[1])
    assert len(lines) >= 2
    assert lines[0].startswith("Throw")
    assert "floating honor" in lines[1].lower()
    assert "West" in lines[1]
    assert any("vs about" in line for line in lines)
    assert any("builds toward chiitoi" in line for line in state_lines)
    assert any(
        "North" in line and "floating honor" in line.lower() for line in state_lines
    )
    assert validate_explanation(turn, result) == []


def test_template_pinfu_dora_floating_honor_teaching_first():
    """Screenshot-shaped: shape reason on recommended cut before ukeire contrast."""
    turn = make_turn(
        shape_goals=["pinfu"],
        mortal_best="dahai S",
        player_action="dahai S",
        diverge=False,
        dora_in_hand=["6m"],
        ukeire=UkeireInfo(
            count=23,
            tiles=["2p", "4p", "5p", "7p"],
            remaining_by_tile={"2p": 3, "4p": 3, "5p": 2, "7p": 3},
        ),
        ukeire_alt=UkeireInfo(
            count=20,
            tiles=["2p", "4p", "7p", "3s"],
            remaining_by_tile={"2p": 3, "4p": 3, "7p": 3, "3s": 2},
        ),
    )
    turn.mortal_output.candidates = [
        MortalCandidate(action="dahai S", prob=0.72),
        MortalCandidate(action="dahai 8p", prob=0.14),
    ]
    turn.features.shanten = 2
    turn.features.statuses.shanten = 2
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_honor", tile="S"),
        HandShapeNote(kind="isolated_kanchan", tile="8p"),
    ]
    result = template_explain(turn)
    move_lines = summary_lines(summary_paragraphs(result.summary)[0])
    state_lines = summary_lines(summary_paragraphs(result.summary)[1])
    assert move_lines[0].startswith("Throw")
    assert "South" in move_lines[1] and "floating honor" in move_lines[1].lower()
    assert any("vs about" in line for line in move_lines)
    assert move_lines.index(next(l for l in move_lines if "vs about" in l)) > 1
    assert any("builds toward pinfu" in line for line in state_lines)
    assert any("8-pin" in line for line in state_lines)
    assert validate_explanation(turn, result) == []


def test_template_mentions_wall_depletion():
    turn = make_turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s", "7s"],
            remaining_by_tile={"4s": 1, "7s": 0},
        ),
    )
    result = template_explain(turn)
    assert "still unseen" in result.summary or "already out" in result.summary
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False
    assert "ukeire" in score.anchors


def test_template_suji_defense_compare():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        danger={"4m": "suji"},
    )
    result = template_explain(turn)
    assert "suji" in result.summary
    assert (
        "interval-safe" in result.summary
        or "edge tiles" in result.summary.lower()
        or "discarded" in result.summary.lower()
    )
    assert "isn't" in result.summary.lower() or "4-man" in result.summary
    assert result.focus in ("defense", "mixed")
    score = score_explanation_substance(turn, result.summary)
    assert "danger" in score.anchors
    assert validate_explanation(turn, result) == []


def test_template_score_situation_opponent_riichi():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        danger={"4m": "genbutsu"},
    )
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=1,
        score_diff="leading",
        late_game=False,
    )
    # Default: point tips off — tile/defense only.
    off = template_explain(turn)
    assert "ahead" not in off.summary.lower()
    assert "prefer the safer cut" not in off.summary.lower()
    assert "score_situation" not in score_explanation_substance(turn, off.summary).anchors

    result = template_explain(turn, include_score_tips=True)
    assert "opponent" in result.summary.lower()
    assert "riichi" in result.summary.lower()
    assert "safer cut" in result.summary.lower() or "ahead" in result.summary.lower()
    score = score_explanation_substance(turn, result.summary)
    assert "score_situation" in score.anchors
    assert validate_explanation(turn, result) == []


def test_template_score_situation_opponent_riichi_fold():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        danger={"4m": "genbutsu"},
    )
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=1,
        score_diff="even",
        late_game=False,
    )
    result = template_explain(turn, include_score_tips=True)
    assert "opponent is in riichi" in result.summary.lower()
    assert "safer" in result.summary.lower()
    assert "ukeire (tiles that improve the hand)" in result.summary
    assert "score_situation" in score_explanation_substance(turn, result.summary).anchors


def test_template_score_situation_trailing_late():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
    )
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=0,
        score_diff="trailing",
        late_game=True,
    )
    result = template_explain(turn, include_score_tips=True)
    assert "behind late" in result.summary.lower()
    assert "value" in result.summary.lower() or "speed" in result.summary.lower()
    assert result.focus in ("value", "mixed")
    assert "score_situation" in score_explanation_substance(turn, result.summary).anchors


def test_template_score_situation_even_late_safe():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        danger={"4m": "genbutsu"},
    )
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=0,
        score_diff="even",
        late_game=True,
    )
    result = template_explain(turn, include_score_tips=True)
    assert "scores are close" in result.summary.lower()
    assert "score_situation" in score_explanation_substance(turn, result.summary).anchors


def test_template_explain_merges_detail_into_summary():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        danger={"9p": "genbutsu"},
        ukeire=UkeireInfo(count=10, tiles=["2m", "3m"]),
        ukeire_alt=UkeireInfo(count=4, tiles=["2m"]),
    )
    result = template_explain(turn)
    assert result.summary
    assert result.detail is not None
    # Defense-led: tip stays short; do not re-inflate with Mortal's-cut metrics.
    assert "already discarded" in result.summary.lower()
    assert "mortal" not in result.summary.lower()
    assert "improving tiles" in result.detail
    assert validate_explanation(turn, result) == []


def test_template_defense_multi_danger_cut_only():
    """Screenshot-shaped: teach only the cut, no other-tile catalogue / UI echoes."""
    turn = make_turn(
        shape_goals=["tanyao", "pinfu"],
        mortal_best="dahai 9s",
        player_action="dahai 9s",
        danger={
            "9s": "genbutsu",
            "2p": "genbutsu",
            "4p": "genbutsu",
            "9m": "suji",
            "6s": "suji",
        },
        ukeire=UkeireInfo(count=24, tiles=["2m", "3m", "5p"]),
        diverge=False,
    )
    turn.game_state.visible_discards = {"1": ["9s"]}
    turn.features.danger_detail = {"9s": {"tag": "genbutsu", "seats": ["1"]}}
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "9-sou" in summary_l
    assert summary_l.lstrip("• ").startswith("throw")
    assert "already discarded" in summary_l
    assert "can't ron" in summary_l or "cant ron" in summary_l
    # No multi-tile catalogue
    assert "2-pin" not in summary_l
    assert "4-pin" not in summary_l
    assert "9-man" not in summary_l
    assert "6-sou" not in summary_l
    assert "also genbutsu" not in summary_l
    assert "suji lines" not in summary_l
    # No UI echoes
    assert "mortal" not in summary_l
    assert "target:" not in summary_l
    assert "improving tiles" not in summary_l
    assert "acceptances" not in summary_l
    assert "shanten" not in summary_l
    assert "tanyao" not in summary_l
    assert "pinfu" not in summary_l
    assert result.focus in ("defense", "mixed")
    assert validate_explanation(turn, result) == []


def test_template_false_safer_tip_turn_stays_grounded():
    turn = false_safer_tip_turn()
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "2-pin" in summary_l or "2p" in summary_l
    assert "still unseen" in summary_l or "already out" in summary_l
    assert "already discarded" in summary_l
    assert "can't ron" in summary_l or "cant ron" in summary_l
    assert "2-man" in summary_l or "2m" in summary_l
    assert "already been played" not in summary_l
    # Must not claim 1-sou is the already-discarded safe cut
    assert not re.search(
        r"1-sou[^.]*already\s+(?:been\s+)?(?:played|discarded)",
        summary_l,
    )
    assert not re.search(
        r"already\s+(?:been\s+)?(?:played|discarded)\s+1-sou",
        summary_l,
    )
    assert "1 improving tile if you throw" not in summary_l
    assert validate_explanation(turn, result) == []


def test_template_omits_safer_alt_genbutsu_efficiency_worse():
    """Screenshot shape: Mortal picks efficiency over safer genbutsu alt.

    Do not teach genbutsu on the non-cut or say 'efficiency is worse'.
    """
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 3p",
        player_action="dahai P",
        danger={"P": "genbutsu"},
    )
    turn.game_state.visible_discards = {"1": ["P"]}
    turn.features.danger_detail = {"P": {"tag": "genbutsu", "seats": ["1"]}}
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "efficiency is worse" not in summary_l
    assert "already discarded" not in summary_l
    assert "can't ron" not in summary_l and "cant ron" not in summary_l
    assert summary_l.lstrip("• ").startswith("throw")
    assert "3-pin" in summary_l
    assert "haku" in summary_l
    assert validate_explanation(turn, result) == []


def test_template_genbutsu_teaching_voice():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 2m",
        player_action="dahai 1s",
        danger={"2m": "genbutsu"},
    )
    turn.game_state.visible_discards = {"1": ["2m"]}
    turn.features.danger_detail = {"2m": {"tag": "genbutsu", "seats": ["1"]}}
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "already discarded" in summary_l
    assert "can't ron" in summary_l or "cant ron" in summary_l
    assert "2-man" in summary_l
    assert "opponent" in summary_l
    assert "efficiency is worse" not in summary_l
    score = score_explanation_substance(turn, result.summary)
    assert "danger" in score.anchors
    assert validate_explanation(turn, result) == []


def test_template_genbutsu_names_riichi_player_when_grounded():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai E",
        player_action="dahai 1s",
        danger={"E": "genbutsu"},
    )
    turn.game_state.visible_discards = {"2": ["E"]}
    turn.game_state.riichi_flags = [False, False, True, False]
    turn.features.context = {"self_seat": 0}
    turn.features.danger_detail = {"E": {"tag": "genbutsu", "seats": ["2"]}}
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "riichi player" in summary_l
    assert "already discarded" in summary_l
    assert "east" in summary_l
    assert validate_explanation(turn, result) == []


def test_template_suji_teaching_voice():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        danger={"4m": "suji"},
    )
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "suji" in summary_l
    assert "edge" in summary_l or "waited" in summary_l
    assert validate_explanation(turn, result) == []


