"""Substance metric: thin efficiency claims vs anchored Why? text."""

import re

from shanten_sensei.explain import (
    _glossed_acceptances_phrase,
    build_detail_paragraph,
    build_user_payload,
    explain,
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


def _turn(
    *,
    shape_goals: list[str] | None = None,
    dora_in_hand: list[str] | None = None,
    wait_shape: str | None = None,
    danger: dict[str, str] | None = None,
    mortal_best: str = "dahai 3p",
    player_action: str = "dahai 5m",
    ukeire: UkeireInfo | None = None,
    ukeire_alt: UkeireInfo | None = None,
    diverge: bool = False,
) -> TurnExplainInput:
    return TurnExplainInput(
        game_state=GameState(
            hand=["2m", "3m", "5m", "7m", "3p", "6p", "7p", "1s", "3s", "8s", "8s", "S", "S"]
        ),
        mortal_output=MortalOutput(
            recommended=mortal_best,
            candidates=[
                MortalCandidate(action=mortal_best, prob=0.79),
                MortalCandidate(action=player_action, prob=0.11),
            ],
        ),
        features=DerivedFeatures(
            shanten=3,
            ukeire=ukeire
            or UkeireInfo(count=51, tiles=["2p", "4p", "5p"]),
            ukeire_alt=ukeire_alt,
            statuses=HandStatuses(
                shanten=3,
                wait_shape=wait_shape,  # type: ignore[arg-type]
                dora_in_hand=dora_in_hand or [],
            ),
            danger=danger or {},
            shape_goals=shape_goals or [],
        ),
        player_action=player_action,
        mortal_best=mortal_best,
        diverge=diverge,
    )


def test_screenshot_thin_higher_probability():
    turn = _turn(dora_in_hand=["3s"])
    summary = (
        "Your choice to discard 3-pin is solid as it maintains a higher probability "
        "of improving your hand compared to discarding 5-man, which has a much lower "
        "chance of helping you. Sticking with 3-pin keeps your options open for future draws."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is True
    assert score.anchors == []
    assert "thin_efficiency_claim" in score.issues
    errors = validate_explanation(
        turn,
        Explanation(
            summary=summary,
            focus="efficiency",
            pinned_action="dahai 3p",
            contrasted_action="dahai 5m",
        ),
    )
    assert "thin_efficiency_claim" in errors


def test_screenshot_thin_percent_efficiency():
    turn = _turn(mortal_best="dahai 6p", player_action="dahai 3p")
    summary = (
        "Your choice of discarding 6-pin is optimal as it maintains a higher efficiency "
        "with a 61.95% chance of improving your hand compared to the next-best option, "
        "3-pin, which has only a 33.12% chance. Sticking with 6-pin keeps your hand "
        "flexible for future draws."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is True
    assert validate_explanation(
        turn,
        Explanation(
            summary=summary,
            focus="efficiency",
            pinned_action="dahai 6p",
            contrasted_action="dahai 3p",
        ),
    ) == ["thin_efficiency_claim"]


def test_template_not_thin():
    turn = _turn(shape_goals=["tanyao"], dora_in_hand=["3s"])
    result = template_explain(turn)
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False
    assert "shanten" in score.anchors or "ukeire" in score.anchors
    assert "Throw" in result.summary
    assert "3-shanten (3 steps from ready)" in result.summary
    assert "acceptances (tiles that improve the hand)" in result.summary
    assert "fits tanyao" in result.summary
    assert validate_explanation(turn, result) == []


def test_anchored_llm_style_passes():
    turn = _turn(shape_goals=["tanyao"], dora_in_hand=["3s"])
    summary = (
        "Throw 3-pin, not 5-man. You’re 3-shanten (3 steps from ready) "
        "with about 51 acceptances (tiles that improve the hand). "
        "That fits tanyao (2–8 only; no 1/9, winds, or dragons) with "
        "dora (bonus tile) 3-sou."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is False
    assert "shanten" in score.anchors
    assert "ukeire" in score.anchors
    assert "shape_goal" in score.anchors
    assert "dora" in score.anchors
    assert validate_explanation(
        turn,
        Explanation(
            summary=summary,
            focus="value",
            pinned_action="dahai 3p",
            contrasted_action="dahai 5m",
        ),
    ) == []


def test_efficiency_with_anchor_not_thin():
    """Tautology language is OK when a hand fact is also cited."""
    turn = _turn()
    summary = (
        "Discarding 3-pin is more efficient than 5-man; you're 3-shanten "
        "(3 steps from ready) with about 51 acceptances "
        "(tiles that improve the hand)."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is False
    assert score.anchors


def test_glossed_shanten_singular_step():
    assert _glossed_shanten_phrase(1) == "1-shanten (1 step from ready)"
    assert _glossed_shanten_phrase(3) == "3-shanten (3 steps from ready)"
    assert _glossed_shanten_phrase(0) == "tenpai (ready)"
    assert _glossed_acceptances_phrase(55) == (
        "about 55 acceptances (tiles that improve the hand)"
    )


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
    assert "furiten on" in result.summary
    assert "7-sou" in result.summary
    assert "defense" in result.summary
    assert result.focus in ("defense", "mixed")
    payload = build_user_payload(turn)
    assert payload["wait_shape_glossary"]["ryanmen"] == "two-sided open"
    assert any("7-sou" in t for t in payload["furiten_blocking_tiles"])
    assert validate_explanation(turn, result) == []


def test_payload_includes_hand_metric_glossary():
    turn = _turn()
    payload = build_user_payload(turn)
    assert payload["hand_metric_glossary"]["shanten"] == "3 steps from ready"
    assert payload["hand_metric_glossary"]["acceptances"] == (
        "tiles that improve the hand"
    )


def test_wall_note_thin_remaining():
    turn = _turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s", "7s"],
            remaining_by_tile={"4s": 1, "7s": 3},
        ),
    )
    note = wall_note(turn)
    assert note is not None
    assert "already out" in note or "1×" in note or "1x" in note
    assert "4-sou" in note.lower() or "4s" in note


def test_wall_note_alt_improving_tiles_contrast():
    turn = _turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        ukeire=UkeireInfo(count=8, tiles=["2m"], remaining_by_tile={"2m": 3}),
        ukeire_alt=UkeireInfo(count=3, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    note = wall_note(turn)
    assert note is not None
    assert "improving tiles" in note
    assert "vs about" in note
    assert "8" in note and "3" in note


def test_template_tanyao_honor_ukeire_contrast():
    turn = _turn(
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
    assert "fits tanyao" in result.summary
    assert "floating honor" in result.summary
    assert "outside tanyao" in result.summary
    assert "acceptances (tiles that improve the hand)" not in result.summary
    assert "\n" in result.summary
    move_para, state_para = result.summary.split("\n", 1)
    assert "Throw" in move_para
    assert "improving tiles" in move_para
    assert "vs about" in move_para
    assert "3-shanten" in state_para or "fits tanyao" in state_para
    assert "fits tanyao" in state_para
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False
    assert "ukeire" in score.anchors
    assert "hand_shape_note" in score.anchors
    assert validate_explanation(turn, result) == []


def test_template_floating_terminal_and_isolated_kanchan():
    turn = _turn(
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

    turn2 = _turn(mortal_best="dahai 2m", player_action="dahai 5s", diverge=True)
    turn2.features.hand_shape_notes = [
        HandShapeNote(kind="isolated_kanchan", tile="2m")
    ]
    result2 = template_explain(turn2)
    assert "closed middle" in result2.summary
    assert "kanchan" in result2.summary


def test_template_dead_end_is_cut_reason_not_keep():
    turn = _turn(
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


def test_validate_rejects_maintains_dead_end_polarity():
    turn = _turn(mortal_best="dahai N", player_action="dahai 2m", diverge=True)
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="N")]
    bad = Explanation(
        summary=(
            "Throw North. This keeps your hand closed and maintains a dead-end "
            "tile, while discarding 2-man would not improve your hand."
        ),
        focus="efficiency",
        pinned_action="dahai N",
        contrasted_action="dahai 2m",
    )
    errors = validate_explanation(turn, bad)
    assert "dead_end_polarity_inverted" in errors


def test_payload_includes_hand_shape_notes():
    turn = _turn(shape_goals=["tanyao"], mortal_best="dahai 9p")
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_terminal", tile="9p")
    ]
    payload = build_user_payload(turn)
    assert payload["hand_shape_notes"][0]["kind"] == "floating_terminal"
    assert "lone 1/9" in payload["hand_shape_note_glossary"]["floating_terminal"]


def test_template_mentions_wall_depletion():
    turn = _turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s", "7s"],
            remaining_by_tile={"4s": 1, "7s": 0},
        ),
    )
    result = template_explain(turn)
    assert "already out" in result.summary or "1×" in result.summary
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False
    assert "ukeire" in score.anchors


def test_depletion_language_anchors_ukeire():
    turn = _turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s"],
            remaining_by_tile={"4s": 1},
        ),
    )
    summary = (
        "Throw 3-pin. Several improving tiles are already out "
        "(only 1× 4-sou left)."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is False
    assert "ukeire" in score.anchors


def test_payload_includes_ukeire_alt_and_wall_note():
    turn = _turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        ukeire=UkeireInfo(count=8, tiles=["2m"], remaining_by_tile={"2m": 2}),
        ukeire_alt=UkeireInfo(count=3, tiles=["2m"], remaining_by_tile={"2m": 2}),
    )
    payload = build_user_payload(turn)
    assert payload["ukeire_alt"]["count"] == 3
    assert payload["wall_note"] is not None
    assert "remaining_by_tile" in payload["ukeire"]


def test_explain_substance_only_repair_omits_suffix(monkeypatch):
    turn = _turn()
    thin_summary = (
        "Discarding 3-pin maintains a higher probability of improving your hand "
        "than 5-man and keeps your options open."
    )

    def fake_llm(t, *, model=None):
        return Explanation(
            summary=thin_summary,
            focus="efficiency",
            pinned_action=t.mortal_best,
            contrasted_action="dahai 5m",
        )

    monkeypatch.setattr("shanten_sensei.explain._llm_explain", fake_llm)
    result = explain(turn, use_llm=True)
    assert "grounding repair" not in result.summary
    assert "acceptances" in result.summary or "shanten" in result.summary.lower()


def test_explain_hard_grounding_omits_suffix(monkeypatch, caplog):
    turn = _turn(shape_goals=["tanyao"])

    def fake_llm(t, *, model=None):
        return Explanation(
            summary="Mortal prefers 3-pin; keep pinfu shape.",
            focus="efficiency",
            pinned_action=t.mortal_best,
            contrasted_action="dahai 5m",
        )

    monkeypatch.setattr("shanten_sensei.explain._llm_explain", fake_llm)
    with caplog.at_level("INFO", logger="shanten_sensei.explain"):
        result = explain(turn, use_llm=True)
    assert "grounding repair" not in result.summary
    assert "pinfu" not in result.summary.lower()
    assert any("grounding repair" in r.message for r in caplog.records)


def test_template_suji_defense_compare():
    turn = _turn(
        diverge=True,
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        danger={"4m": "suji"},
    )
    result = template_explain(turn)
    assert "suji" in result.summary
    assert "interval-safe" in result.summary
    assert "isn't" in result.summary.lower() or "4-man" in result.summary
    assert result.focus in ("defense", "mixed")
    score = score_explanation_substance(turn, result.summary)
    assert "danger" in score.anchors
    assert validate_explanation(turn, result) == []


def test_template_score_situation_opponent_riichi():
    turn = _turn(
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
    result = template_explain(turn)
    assert "opponent" in result.summary.lower()
    assert "riichi" in result.summary.lower()
    assert "safety" in result.summary.lower()
    score = score_explanation_substance(turn, result.summary)
    assert "score_situation" in score.anchors
    assert validate_explanation(turn, result) == []


def test_payload_includes_danger_glossary_and_score_situation():
    turn = _turn(danger={"9p": "genbutsu", "4m": "suji"})
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=0,
        score_diff="trailing",
        late_game=True,
    )
    payload = build_user_payload(turn)
    assert payload["danger_glossary"]["suji"] == "interval-safe vs a common wait"
    assert payload["score_situation"]["score_diff"] == "trailing"
    assert payload["score_situation"]["late_game"] is True


def test_build_detail_paragraph_ukeire_danger_score():
    turn = _turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        danger={"9p": "suji", "5s": "one-chance"},
        ukeire=UkeireInfo(count=8, tiles=["2m"], remaining_by_tile={"2m": 3}),
        ukeire_alt=UkeireInfo(count=3, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_terminal", tile="9p")
    ]
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=1,
        score_diff="trailing",
        late_game=True,
    )
    detail = build_detail_paragraph(turn)
    assert detail is not None
    assert "improving tiles" in detail
    assert "vs about" in detail
    assert "suji" in detail
    assert "floating terminal" in detail or "lone 1/9" in detail
    assert "riichi" in detail.lower()
    assert "trailing" in detail


def test_template_explain_attaches_detail_without_changing_summary():
    turn = _turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        danger={"9p": "genbutsu"},
        ukeire=UkeireInfo(count=10, tiles=["2m"]),
        ukeire_alt=UkeireInfo(count=4, tiles=["2m"]),
    )
    result = template_explain(turn)
    assert result.summary
    assert result.detail is not None
    assert "improving tiles" in result.detail
    assert result.detail not in result.summary
    assert validate_explanation(turn, result) == []


def _false_safer_tip_turn() -> TurnExplainInput:
    """Screenshot-shaped turn: 2m genbutsu, thin 2p wall, high ukeire_alt on 1s."""
    return _turn(
        shape_goals=["pinfu"],
        mortal_best="dahai 2m",
        player_action="dahai 1s",
        danger={"2m": "genbutsu"},
        ukeire=UkeireInfo(
            count=12,
            tiles=["2p", "3p", "4p", "3s", "W"],
            remaining_by_tile={"2p": 1, "3p": 4, "4p": 2, "3s": 3, "W": 2},
        ),
        ukeire_alt=UkeireInfo(
            count=63,
            tiles=["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m"],
        ),
        diverge=False,
    )


def test_grounding_rejects_false_safer_improving_tile_tip():
    turn = _false_safer_tip_turn()
    bad = Explanation(
        summary=(
            "Throw 2-man. This keeps your hand towards pinfu "
            "(closed all-sequences; no value pair) while maintaining 11 improving "
            "tiles, compared to only 1 improving tile if you throw 1-sou, which is "
            "also a safer discard since it's already been played."
        ),
        focus="efficiency",
        pinned_action="dahai 2m",
        contrasted_action="dahai 1s",
    )
    errors = validate_explanation(turn, bad)
    assert any("genbutsu" in e or "already-discarded" in e for e in errors)
    assert any("improving-tile contrast" in e for e in errors)


def test_template_false_safer_tip_turn_stays_grounded():
    turn = _false_safer_tip_turn()
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "2-pin" in summary_l or "2p" in summary_l
    assert "thinning" in summary_l or "only 1" in summary_l
    assert "genbutsu" in summary_l
    assert "2-man" in summary_l or "2m" in summary_l
    assert "already been played" not in summary_l
    # Must not claim 1-sou is the already-discarded safe cut
    assert not re.search(
        r"1-sou[^.]*already\s+(?:been\s+)?(?:played|discarded)",
        summary_l,
    )
    assert "1 improving tile if you throw" not in summary_l
    assert validate_explanation(turn, result) == []


def test_grounding_accepts_correct_genbutsu_on_best_cut():
    turn = _false_safer_tip_turn()
    good = Explanation(
        summary=(
            "Throw 2-man, not 1-sou. You’re 2-shanten (2 steps from ready) with "
            "about 12 acceptances (tiles that improve the hand).\n"
            "Improving tiles are thinning (only 1× 2-pin left). "
            "2-man is genbutsu (safe — already discarded). 1-sou isn't."
        ),
        focus="defense",
        pinned_action="dahai 2m",
        contrasted_action="dahai 1s",
    )
    assert validate_explanation(turn, good) == []


def test_grounding_accepts_real_ukeire_contrast():
    turn = _turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        ukeire=UkeireInfo(count=8, tiles=["2m"], remaining_by_tile={"2m": 2}),
        ukeire_alt=UkeireInfo(count=3, tiles=["2m"], remaining_by_tile={"2m": 2}),
    )
    good = Explanation(
        summary=(
            "Throw 9-pin, not 5-sou. That leaves about 8 improving tiles left "
            "vs about 3 if you throw 5-sou."
        ),
        focus="efficiency",
        pinned_action="dahai 9p",
        contrasted_action="dahai 5s",
    )
    assert validate_explanation(turn, good) == []
