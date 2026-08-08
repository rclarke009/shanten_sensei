"""Substance metric, payload, merge, and emoji helpers."""

from conftest import make_turn

import re

import pytest

from shanten_sensei.explain import (
    _ensure_tile_emojis,
    _finalize_explanation,
    _glossed_acceptances_phrase,
    _merge_detail_into_summary,
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
from shanten_sensei.tiles import human_tile_label

def test_anchored_llm_style_passes():
    turn = make_turn(shape_goals=["tanyao"], dora_in_hand=["3s"])
    summary = (
        "Throw 3-pin, not 5-man. You’re 3-shanten (3 steps from ready) "
        "with about 51 ukeire (tiles that improve the hand). "
        "Throwing 3-pin builds toward tanyao (2–8 only; no 1/9, winds, or dragons) with "
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
    turn = make_turn()
    summary = (
        "Discarding 3-pin is more efficient than 5-man; you're 3-shanten "
        "(3 steps from ready) with about 51 ukeire "
        "(tiles that improve the hand)."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is False
    assert score.anchors


def test_glossed_shanten_singular_step():
    assert _glossed_shanten_phrase(1) == "1-shanten (1 step from ready)"
    assert _glossed_shanten_phrase(3) == "3-shanten (3 steps from ready)"
    assert _glossed_shanten_phrase(-1) == "complete (winning hand)"
    assert _glossed_shanten_phrase(0) == "tenpai (ready)"
    assert _glossed_acceptances_phrase(55) == (
        "about 55 ukeire (tiles that improve the hand)"
    )
    assert _glossed_acceptances_phrase(0) == "no improving tiles"
    assert "about" not in _glossed_acceptances_phrase(0)


def test_payload_includes_hand_metric_glossary():
    turn = make_turn()
    payload = build_user_payload(turn)
    assert payload["hand_metric_glossary"]["shanten"] == "3 steps from ready"
    assert payload["hand_metric_glossary"]["ukeire"] == (
        "tiles that improve the hand"
    )
    assert payload["hand_metric_glossary"]["acceptances"] == (
        "tiles that improve the hand"
    )


def test_known_terms_strips_glosses_from_template_and_payload():
    turn = make_turn(shape_goals=["tanyao"])
    result = template_explain(turn, known_terms=["tanyao", "shanten", "ukeire"])
    assert "tanyao (" not in result.summary
    assert "builds toward tanyao" in result.summary or "tanyao" in result.summary
    assert "3-shanten (" not in result.summary
    assert "3-shanten" in result.summary
    assert "ukeire (" not in result.summary
    payload = build_user_payload(
        turn.model_copy(
            update={
                "features": turn.features.model_copy(
                    update={
                        "context": {
                            **turn.features.context,
                            "known_terms": ["tanyao", "shanten", "ukeire"],
                        }
                    }
                )
            }
        )
    )
    assert "tanyao" not in payload["shape_goal_glossary"]
    assert "ukeire" not in payload["hand_metric_glossary"]
    assert "acceptances" not in payload["hand_metric_glossary"]
    assert "shanten" not in payload["hand_metric_glossary"]


def test_wall_note_thin_remaining():
    turn = make_turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s", "7s"],
            remaining_by_tile={"4s": 1, "7s": 3},
        ),
    )
    note = wall_note(turn)
    assert note is not None
    assert "still unseen" in note or "already out" in note
    assert "4-sou" in note.lower() or "4s" in note


def test_wall_note_alt_improving_tiles_contrast():
    turn = make_turn(
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


def test_payload_includes_hand_shape_notes():
    turn = make_turn(shape_goals=["tanyao"], mortal_best="dahai 9p")
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_terminal", tile="9p")
    ]
    payload = build_user_payload(turn)
    assert payload["hand_shape_notes"][0]["kind"] == "floating_terminal"
    assert "lone 1/9" in payload["hand_shape_note_glossary"]["floating_terminal"]


def test_depletion_language_anchors_ukeire():
    turn = make_turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s"],
            remaining_by_tile={"4s": 1},
        ),
    )
    summary = (
        "Throw 3-pin. Few copies left of tiles you need "
        "(only 1 copy of 4-sou is still unseen)."
    )
    score = score_explanation_substance(turn, summary)
    assert score.thin is False
    assert "ukeire" in score.anchors


def test_payload_includes_ukeire_alt_and_wall_note():
    turn = make_turn(
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


def test_explain_defaults_to_template_when_only_api_key(monkeypatch):
    turn = make_turn()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("SENSEI_USE_LLM", raising=False)
    called = {"llm": False}

    def fake_llm(t, *, model=None):
        called["llm"] = True
        return Explanation(
            summary="LLM path",
            focus="efficiency",
            pinned_action=t.mortal_best,
            contrasted_action=None,
        )

    monkeypatch.setattr("shanten_sensei.explain._llm_explain", fake_llm)
    result = explain(turn)
    assert not called["llm"]
    assert "Throw" in result.summary


def test_explain_uses_llm_when_sensei_use_llm_set(monkeypatch):
    turn = make_turn()
    monkeypatch.setenv("SENSEI_USE_LLM", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    called = {"llm": False}

    def fake_llm(t, *, model=None):
        called["llm"] = True
        return Explanation(
            summary=(
                "Throw 3-pin, not 5-man. You're 3-shanten (3 steps from ready) "
                "with about 51 tiles that can improve your hand."
            ),
            focus="efficiency",
            pinned_action=t.mortal_best,
            contrasted_action="dahai 5m",
        )

    monkeypatch.setattr("shanten_sensei.explain._llm_explain", fake_llm)
    explain(turn)
    assert called["llm"]


def test_explain_substance_only_repair_omits_suffix(monkeypatch):
    turn = make_turn()
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
    turn = make_turn(shape_goals=["tanyao"])

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


def test_payload_includes_danger_glossary_and_score_situation():
    turn = make_turn(danger={"9p": "genbutsu", "4m": "suji"})
    turn.features.score_situation = ScoreSituation(
        riichi_opponents=0,
        score_diff="trailing",
        late_game=True,
    )
    payload_off = build_user_payload(turn)
    assert payload_off["score_situation"] is None
    assert "edge" in payload_off["danger_glossary"]["suji"]
    assert "already discarded" in payload_off["danger_glossary"]["genbutsu"]

    turn_on = turn.model_copy(
        update={
            "features": turn.features.model_copy(
                update={
                    "context": {
                        **turn.features.context,
                        "include_score_tips": True,
                    }
                }
            )
        }
    )
    payload = build_user_payload(turn_on)
    assert "danger_detail" in payload
    assert payload["score_situation"]["score_diff"] == "trailing"
    assert payload["score_situation"]["late_game"] is True


def test_build_detail_paragraph_ukeire_danger_score():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 9p",
        player_action="dahai 5s",
        danger={"9p": "suji", "5s": "one-chance", "2p": "genbutsu"},
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
    detail_off = build_detail_paragraph(turn)
    assert detail_off is not None
    assert "improving tiles" in detail_off
    assert "trailing" not in detail_off

    turn_on = turn.model_copy(
        update={
            "features": turn.features.model_copy(
                update={
                    "context": {
                        **turn.features.context,
                        "include_score_tips": True,
                    }
                }
            )
        }
    )
    detail = build_detail_paragraph(turn_on)
    assert detail is not None
    assert "improving tiles" in detail
    assert "vs about" in detail
    assert "suji" in detail
    # Cut-only: do not catalogue other danger tiles.
    assert "one-chance" not in detail
    assert "genbutsu" not in detail
    assert "floating terminal" in detail or "lone 1/9" in detail
    assert "riichi" in detail.lower()
    assert "trailing" in detail


def test_merge_skips_mortal_cut_ukeire_when_tiles_that_can_improve():
    """Preferred LLM voice already cites ukeire; don't echo Mortal's-cut contrast."""
    summary = (
        "Throw 9-sou. That leaves about 60 tiles that can improve your hand, "
        "vs about 57 if you throw 1-man. You're 3-shanten (3 steps from ready) "
        "and aiming for pinfu (closed all-sequences; no value pair) — "
        "9-sou is a floating terminal."
    )
    detail = (
        "Mortal's cut leaves about 60 improving tiles vs about 57 on the "
        "alternative. 9-sou — lone 1/9 with no connector. you're even on points."
    )
    merged = _merge_detail_into_summary(summary, detail)
    merged_l = merged.lower()
    assert "mortal" not in merged_l
    assert "leaves about 60 improving tiles" not in merged_l
    assert "tiles that can improve" in merged_l
    # Non-ukeire detail may still append.
    assert "even on points" in merged_l


def test_merge_skips_mortal_cut_ukeire_when_glossed_ukeire_phrase():
    """Glossed ukeire voice (tiles that improve the hand) also suppresses echo."""
    summary = (
        "Throw 1-pin, not 9-man. You're 4-shanten with about 58 ukeire "
        "(tiles that improve the hand).\n"
        "Keeping dora red 5-pin.\n"
        "1-pin is a dead-end tile."
    )
    detail = (
        "Mortal's cut leaves about 58 improving tiles vs about 56 on the "
        "alternative. 1-pin — connects to nothing useful."
    )
    merged = _merge_detail_into_summary(summary, detail)
    merged_l = merged.lower()
    assert "mortal" not in merged_l
    assert "leaves about 58 improving tiles" not in merged_l
    assert "connects to nothing useful" not in merged_l
    assert merged == summary


def test_defense_led_tip_omits_orphan_shape_gloss():
    """Genbutsu-led cut skips midhand shape prose; don't leak glossary stub."""
    turn = make_turn(
        shape_goals=["pinfu"],
        mortal_best="dahai C",
        player_action="dahai 9m",
        diverge=True,
        danger={"C": "genbutsu"},
        ukeire=UkeireInfo(
            count=45,
            tiles=["4m", "6m", "9m", "1p"],
            remaining_by_tile={"4m": 3, "6m": 3, "9m": 2, "1p": 3},
        ),
        ukeire_alt=UkeireInfo(
            count=41,
            tiles=["4m", "1p", "2p", "3p"],
            remaining_by_tile={"4m": 3, "1p": 3, "2p": 3, "3p": 3},
        ),
    )
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_honor", tile="C")
    ]
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "already discarded" in summary_l or "can't ron" in summary_l
    assert "lone wind or dragon" not in summary_l
    assert "floating_honor" not in summary_l
    assert "floating honor" not in summary_l

    detail = build_detail_paragraph(turn)
    if detail is not None:
        assert "lone wind or dragon" not in detail.lower()


def test_efficiency_led_tip_still_dedupes_shape_gloss():
    """When summary already teaches floating honor, omit redundant detail gloss."""
    summary = "Throw West, not red 5-sou. West is a floating honor."
    detail = f"{human_tile_label('W')} — lone wind or dragon."
    merged = _merge_detail_into_summary(summary, detail)
    assert "lone wind or dragon" not in merged.lower()
    assert merged == summary


def test_build_detail_paragraph_cut_only_danger():
    turn = make_turn(
        mortal_best="dahai 9s",
        danger={
            "9s": "genbutsu",
            "2p": "genbutsu",
            "9m": "suji",
        },
    )
    detail = build_detail_paragraph(turn)
    assert detail is not None
    assert "9-sou" in detail
    assert "genbutsu" in detail
    assert "2-pin" not in detail
    assert "9-man" not in detail
    assert "suji" not in detail


def test_named_improving_tiles_on_ukeire_contrast():
    turn = make_turn(
        diverge=False,
        mortal_best="dahai 3m",
        player_action="dahai 3m",
        ukeire=UkeireInfo(
            count=60,
            tiles=["2m", "4m", "5m", "6m"],
            remaining_by_tile={"2m": 4, "4m": 3, "5m": 3, "6m": 2},
        ),
        ukeire_alt=UkeireInfo(
            count=18,
            tiles=["9s", "8s"],
            remaining_by_tile={"9s": 3, "8s": 2},
        ),
    )
    turn.mortal_output.candidates = [
        MortalCandidate(action="dahai 3m", prob=0.79),
        MortalCandidate(action="dahai 9s", prob=0.11),
    ]
    result = template_explain(turn)
    assert "keeps draws like" in result.summary.lower()
    assert "if you threw" in result.summary.lower()
    assert "instead" in result.summary.lower()
    assert "mostly improve via" in result.summary.lower()
    assert "2-man" in result.summary
    assert result.summary.startswith("• ")
    assert "\n\n" in result.summary
    assert "; throwing" not in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_narrow_ukeire_contrast_gap_two():
    turn = make_turn(
        diverge=False,
        mortal_best="dahai 7s",
        player_action="dahai 7s",
        ukeire=UkeireInfo(
            count=33,
            tiles=["4m", "6m", "1p"],
            remaining_by_tile={"4m": 3, "6m": 3, "1p": 3},
        ),
        ukeire_alt=UkeireInfo(
            count=31,
            tiles=["4m", "1p", "2p"],
            remaining_by_tile={"4m": 3, "1p": 3, "2p": 3},
        ),
    )
    turn.mortal_output.candidates = [
        MortalCandidate(action="dahai 7s", prob=0.79),
        MortalCandidate(action="dahai C", prob=0.11),
    ]
    result = template_explain(turn)
    assert "vs about 31" in result.summary
    assert "keeps draws like" not in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_improving_tiles_preview_when_ukeire_gap_zero():
    turn = make_turn(
        diverge=False,
        mortal_best="dahai 7s",
        player_action="dahai 7s",
        ukeire=UkeireInfo(
            count=33,
            tiles=["4m", "6m", "1p", "2p"],
            remaining_by_tile={"4m": 3, "6m": 3, "1p": 3, "2p": 3},
        ),
        ukeire_alt=UkeireInfo(
            count=33,
            tiles=["4m", "1p", "2p", "3p"],
            remaining_by_tile={"4m": 3, "1p": 3, "2p": 3, "3p": 3},
        ),
    )
    turn.mortal_output.candidates = [
        MortalCandidate(action="dahai 7s", prob=0.79),
        MortalCandidate(action="dahai C", prob=0.11),
    ]
    turn.game_state.hand = [
        "4m",
        "7m",
        "8m",
        "9m",
        "9m",
        "7p",
        "8p",
        "9p",
        "7s",
        "8s",
        "9s",
        "W",
        "C",
    ]
    result = template_explain(turn)
    assert "keeps draws like" in result.summary.lower()
    assert "dead-end" in result.summary.lower()
    assert "chun" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_summary_word_limit_allows_longer_coaching():
    turn = make_turn(shape_goals=["tanyao"], dora_in_hand=["3s"])
    words = ["word"] * 85
    good = Explanation(
        summary="Throw 3-pin. " + " ".join(words),
        focus="efficiency",
        pinned_action="dahai 3p",
    )
    assert validate_explanation(turn, good) == []
    too_long = Explanation(
        summary="Throw 3-pin. " + " ".join(["word"] * 90),
        focus="efficiency",
        pinned_action="dahai 3p",
    )
    assert "summary exceeds length budget" in validate_explanation(turn, too_long)


def test_ensure_tile_emojis_rewrites_bare_suit_name():
    turn = make_turn(mortal_best="dahai 2m", player_action="dahai 1s")
    out = _ensure_tile_emojis(
        "Throw 2-man. That keeps your options open with about 9 tiles.",
        turn,
    )
    assert human_tile_label("2m") in out
    assert out.startswith(f"Throw {human_tile_label('2m')}")


def test_ensure_tile_emojis_idempotent_when_already_glyphed():
    turn = make_turn(mortal_best="dahai 2m", player_action="dahai 1s")
    label = human_tile_label("2m")
    already = f"Throw {label}. Keep options open."
    assert _ensure_tile_emojis(already, turn) == already
    assert _ensure_tile_emojis(already, turn).count(label) == 1


def test_ensure_tile_emojis_honor_and_aka():
    turn = TurnExplainInput(
        game_state=GameState(
            hand=[
                "5sr",
                "5s",
                "W",
                "2m",
                "3m",
                "7m",
                "3p",
                "6p",
                "7p",
                "1s",
                "3s",
                "8s",
                "8s",
            ]
        ),
        mortal_output=MortalOutput(
            recommended="dahai W",
            candidates=[
                MortalCandidate(action="dahai W", prob=0.7),
                MortalCandidate(action="dahai 5sr", prob=0.2),
            ],
        ),
        features=DerivedFeatures(
            shanten=2,
            ukeire=UkeireInfo(count=20, tiles=["2p", "5s"]),
            statuses=HandStatuses(shanten=2),
        ),
        player_action="dahai 5sr",
        mortal_best="dahai W",
        diverge=True,
    )
    out = _ensure_tile_emojis(
        "Throw West, not red 5-sou. West is a floating honor.",
        turn,
    )
    assert human_tile_label("W") in out
    assert human_tile_label("5sr") in out
    assert "🀔red 🀔5-sou" not in out
    assert "Throw West" not in out
    assert "not red 5-sou" not in out


def test_finalize_injects_glyphs_into_bare_llm_summary():
    turn = make_turn(mortal_best="dahai 2m", player_action="dahai 1s", diverge=False)
    result = _finalize_explanation(
        turn,
        Explanation(
            summary=(
                "Throw 2-man. That keeps your options open with about 9 tiles "
                "that can improve your hand."
            ),
            focus="efficiency",
            pinned_action="dahai 2m",
        ),
    )
    assert human_tile_label("2m") in result.summary
    assert result.summary.lstrip("• ").startswith(f"Throw {human_tile_label('2m')}")
