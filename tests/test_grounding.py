"""Grounding validator property tests."""

from conftest import false_safer_tip_turn, make_turn, yakuhai_haku_pair_turn

import re

import pytest

from shanten_sensei.explain import template_explain, validate_explanation
from shanten_sensei.grounding import GROUNDING_RULES
from shanten_sensei.schema import Explanation, HandShapeNote, MortalCandidate, ScoreSituation, TurnExplainInput, UkeireInfo

def test_validate_rejects_kanchan_on_cut_phrasing():
    turn = make_turn(mortal_best="dahai 8m", player_action="dahai 2s", diverge=True)
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="isolated_kanchan", tile="8m")
    ]
    bad = Explanation(
        summary=(
            "Throw 8-man. That keeps your hand intact with about 19 tiles that "
            "can improve it, while throwing 2-sou would not change your current "
            "situation.\nYou're 2-shanten (2 steps from ready) and aiming for "
            "pinfu (closed all-sequences; no value pair) with an isolated "
            "kanchan (closed middle fragment) on 8-man."
        ),
        focus="efficiency",
        pinned_action="dahai 8m",
        contrasted_action="dahai 2s",
    )
    errors = validate_explanation(turn, bad)
    assert "isolated_shape_on_cut_phrasing" in errors


def test_validate_rejects_maintains_dead_end_polarity():
    turn = make_turn(mortal_best="dahai N", player_action="dahai 2m", diverge=True)
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
    assert "cut_note_polarity_inverted" in errors


def test_validate_rejects_figurative_hand_open():
    """ukeire flexibility must not be phrased as an open (called) hand."""
    turn = make_turn(
        mortal_best="dahai 8s",
        player_action="dahai 8s",
        diverge=False,
        ukeire=UkeireInfo(
            count=8, tiles=["4p", "7p", "7m"], remaining_by_tile={"4p": 3, "7p": 3, "7m": 2}
        ),
        shape_goals=["yakuhai", "chiitoi"],
    )
    bad = Explanation(
        summary=(
            "Throw 8-sou. That keeps your hand open with about 8 tiles that can "
            "improve it. You're 1-shanten (1 step from ready) and aiming for "
            "yakuhai (triplet of dragon or your seat/round wind) with a pair of Chun."
        ),
        focus="efficiency",
        pinned_action="dahai 8s",
        contrasted_action=None,
    )
    errors = validate_explanation(turn, bad)
    assert "figurative_hand_open" in errors


def test_validate_rejects_keeps_floating_terminal_polarity():
    turn = make_turn(
        shape_goals=["pinfu"],
        mortal_best="dahai 9p",
        player_action="dahai 3s",
        diverge=True,
        ukeire=UkeireInfo(
            count=10, tiles=["5m", "8m"], remaining_by_tile={"5m": 4, "8m": 4}
        ),
    )
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_terminal", tile="9p")
    ]
    bad = Explanation(
        summary=(
            "Throw 9-pin. That keeps a floating terminal, which can connect to "
            "8-pin or 6-pin for improvement.\nYou're 1-shanten (1 step from ready) "
            "with about 10 tiles that can improve your hand, fitting pinfu "
            "(closed all-sequences; no value pair)."
        ),
        focus="efficiency",
        pinned_action="dahai 9p",
        contrasted_action="dahai 3s",
    )
    errors = validate_explanation(turn, bad)
    assert "cut_note_polarity_inverted" in errors


def test_validate_allows_keeps_ryanmen_wait():
    turn = make_turn(
        mortal_best="dahai 4m",
        player_action="dahai 6m",
        diverge=True,
        ukeire=UkeireInfo(count=6, tiles=["4s", "7s"]),
        wait_shape="ryanmen",
    )
    good = Explanation(
        summary=(
            "Throw 4-man, not 6-man. That keeps a ryanmen (two-sided open) wait. "
            "You're tenpai with about 6 tiles that can improve your hand."
        ),
        focus="efficiency",
        pinned_action="dahai 4m",
        contrasted_action="dahai 6m",
    )
    assert "cut_note_polarity_inverted" not in validate_explanation(turn, good)
    assert validate_explanation(turn, good) == []


def test_validate_rejects_better_to_keep_it_after_throw_west():
    """Screenshot: Throw West then 'better to keep it for now'."""
    turn = make_turn(
        mortal_best="dahai W",
        player_action="dahai E",
        diverge=False,
        ukeire=UkeireInfo(count=64, tiles=["6m", "9m", "1p"], remaining_by_tile={}),
        ukeire_alt=UkeireInfo(count=64, tiles=["6m", "9m", "1p"], remaining_by_tile={}),
    )
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="W")]
    turn.features.score_situation = ScoreSituation(score_diff="even")
    bad = Explanation(
        summary=(
            "Throw West. This keeps your hand efficient with about 64 tiles that "
            "can improve it, while throwing East would not change that count. "
            "You're 3-shanten (3 steps from ready) and holding a dead-end tile—"
            "West connects to nothing useful, but it's still better to keep it "
            "for now."
        ),
        focus="efficiency",
        pinned_action="dahai W",
        contrasted_action="dahai E",
    )
    errors = validate_explanation(turn, bad)
    assert "pinned_cut_keep_contradiction" in errors

    repaired = template_explain(turn)
    assert "Throw" in repaired.summary
    assert "West" in repaired.summary
    assert "is a dead-end tile" in repaired.summary
    assert not re.search(
        r"\bbetter to keep\b|\bkeep(?:s|ing)? it\b", repaired.summary, re.I
    )
    assert validate_explanation(turn, repaired) == []


def test_validate_rejects_keep_west_pinned_cut():
    turn = make_turn(mortal_best="dahai W", player_action="dahai E")
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="W")]
    bad = Explanation(
        summary=(
            "Throw West. You're 3-shanten (3 steps from ready) with about 51 "
            "tiles that can improve your hand. West is a dead-end tile, but "
            "keeping West is still fine for now."
        ),
        focus="efficiency",
        pinned_action="dahai W",
        contrasted_action="dahai E",
    )
    assert "pinned_cut_keep_contradiction" in validate_explanation(turn, bad)


def test_validate_allows_keeping_dora_while_throwing_west():
    turn = make_turn(
        mortal_best="dahai W",
        player_action="dahai E",
        dora_in_hand=["5mr"],
        ukeire=UkeireInfo(count=51, tiles=["6m"], remaining_by_tile={"6m": 3}),
    )
    good = Explanation(
        summary=(
            "Throw West, not East. You're 3-shanten (3 steps from ready) with "
            "about 51 tiles that can improve your hand.\nRed 5-man is dora "
            "(bonus tile), so keeping dora red 5-man boosts your score if you win."
        ),
        focus="value",
        pinned_action="dahai W",
        contrasted_action="dahai E",
    )
    errors = validate_explanation(turn, good)
    assert "pinned_cut_keep_contradiction" not in errors
    assert errors == []


def test_validate_rejects_skip_then_better_to_call():
    from shanten_sensei.live import (
        candidates_from_meta_options,
        turn_from_live,
    )

    turn = turn_from_live(
        hand=[
            "4m",
            "5m",
            "4p",
            "4p",
            "8p",
            "9p",
            "3s",
            "3s",
            "4s",
            "5s",
            "6s",
            "7s",
            "9s",
        ],
        recommended="none",
        candidates=candidates_from_meta_options([("none", 0.99), ("pon", 0.01)]),
        call_tile="3s",
        visible_discards={"2": ["3s"]},
    )
    bad = Explanation(
        summary=(
            "Skip the pon on 3-sou. You're 2-shanten (2 steps from ready) closed "
            "with about 20 improving tiles. Still, it's better to call."
        ),
        focus="efficiency",
        pinned_action="none",
        contrasted_action="pon 3s",
    )
    assert "action_lead_polarity_inverted" in validate_explanation(turn, bad)
    result = template_explain(turn)
    assert "Skip" in result.summary
    assert validate_explanation(turn, result) == []


def test_validate_rejects_declare_riichi_then_stay_silent():
    from shanten_sensei.live import (
        candidates_from_meta_options,
        turn_from_live,
    )

    turn = turn_from_live(
        hand=[
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
        ],
        recommended="reach",
        candidates=candidates_from_meta_options([("reach", 0.85), ("none", 0.15)]),
        dora_indicators=["4m"],
    )
    bad = Explanation(
        summary=(
            "Declare riichi. You're tenpai (ready) with a ryanmen (two-sided "
            "open) wait, but it's better to stay silent."
        ),
        focus="tempo",
        pinned_action="reach",
        contrasted_action="none",
    )
    assert "action_lead_polarity_inverted" in validate_explanation(turn, bad)
    result = template_explain(turn)
    assert "Declare riichi" in result.summary
    assert validate_explanation(turn, result) == []


def test_grounding_rejects_false_safer_improving_tile_tip():
    turn = false_safer_tip_turn()
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


def test_grounding_accepts_correct_genbutsu_on_best_cut():
    turn = false_safer_tip_turn()
    good = Explanation(
        summary=(
            "Throw 2-man, not 1-sou. You’re 2-shanten (2 steps from ready) with "
            "about 12 ukeire (tiles that improve the hand).\n"
            "Only 1 copy of 2-pin is still unseen. "
            "An opponent already discarded 2-man, so they can't ron it from you."
        ),
        focus="defense",
        pinned_action="dahai 2m",
        contrasted_action="dahai 1s",
    )
    assert validate_explanation(turn, good) == []


def test_validate_rejects_wall_jargon():
    turn = make_turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s"],
            remaining_by_tile={"4s": 1},
        ),
    )
    bad = Explanation(
        summary=(
            "Throw 3-pin. Calling would open the hand given the thinning wall "
            "(only 1 red 5-pin left)."
        ),
        focus="efficiency",
        pinned_action="dahai 3p",
        contrasted_action="dahai 5m",
    )
    errors = validate_explanation(turn, bad)
    assert any("ambiguous wall/thinning jargon" in e for e in errors)


def test_grounding_accepts_real_ukeire_contrast():
    turn = make_turn(
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


def test_grounding_rejects_false_yakuhai_pair_of_singleton_east():
    turn = yakuhai_haku_pair_turn()
    bad = Explanation(
        summary=(
            "Throw 1-man, not East. You're 3-shanten (3 steps from ready) with "
            "about 40 tiles that can improve your hand.\nYou're aiming for "
            "yakuhai (triplet of dragon or your seat/round wind)—you have a "
            "pair of East for that, while 1-man is a floating terminal."
        ),
        focus="efficiency",
        pinned_action="dahai 1m",
        contrasted_action="dahai E",
    )
    errors = validate_explanation(turn, bad)
    assert any("yakuhai_pairs" in e or "pair of" in e for e in errors)


def test_grounding_rejects_pair_plus_floating_honor_contradiction():
    turn = make_turn(
        shape_goals=["yakuhai"],
        mortal_best="dahai S",
        player_action="dahai 9s",
        diverge=True,
        ukeire=UkeireInfo(count=31, tiles=["2m"], remaining_by_tile={"2m": 3}),
        ukeire_alt=UkeireInfo(count=36, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    # Singleton South — not a pair; floating honor on the cut.
    turn.game_state.hand = [
        "2p",
        "2p",
        "4p",
        "8p",
        "1s",
        "2s",
        "3s",
        "4s",
        "5s",
        "5sr",
        "7s",
        "8s",
        "9s",
        "S",
    ]
    turn.features.context = {"jikaze": "E", "bakaze": "E"}
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_honor", tile="S")
    ]
    # Yakuhai in goals without a real value pair (LLM/feature mismatch case):
    # still must not claim "pair of South".
    bad = Explanation(
        summary=(
            "Throw South. You have about 31 tiles that can improve your hand, "
            "while throwing 9-sou would leave you with only 36 improving tiles "
            "available.\nYou're aiming for yakuhai (triplet of dragon or your "
            "seat/round wind)—you have a pair of South for that, and the South "
            "tile is a floating honor."
        ),
        focus="efficiency",
        pinned_action="dahai S",
        contrasted_action="dahai 9s",
    )
    errors = validate_explanation(turn, bad)
    assert any("yakuhai_pairs" in e or "pair of" in e for e in errors)


def test_grounding_accepts_real_pair_of_haku():
    turn = yakuhai_haku_pair_turn()
    good = Explanation(
        summary=(
            "Throw 1-man, not East. You're 3-shanten (3 steps from ready) with "
            "about 40 improving tiles left vs about 35 if you throw East.\n"
            "Throwing 1-man builds toward yakuhai (triplet of dragon or your seat/round wind)—you're "
            "holding a pair of Haku for that; 1-man isn't a value tile, while "
            "East can still pair."
        ),
        focus="efficiency",
        pinned_action="dahai 1m",
        contrasted_action="dahai E",
    )
    assert validate_explanation(turn, good) == []


def test_grounding_rejects_tiles_that_can_improve_contrast_without_wall_note():
    """Screenshot: 65 vs 73 — alt has more ukeire; contrast not authorized."""
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 9m",
        player_action="dahai N",
        ukeire=UkeireInfo(count=65, tiles=["2m"], remaining_by_tile={"2m": 3}),
        ukeire_alt=UkeireInfo(count=73, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    bad = Explanation(
        summary=(
            "Throw 9-man, not North. You're 4-shanten (4 steps from ready) with "
            "about 65 tiles that can improve your hand, vs about 73 if you throw "
            "North."
        ),
        focus="efficiency",
        pinned_action="dahai 9m",
        contrasted_action="dahai N",
    )
    errors = validate_explanation(turn, bad)
    assert any("improving-tile contrast" in e for e in errors)


def test_grounding_rejects_only_on_larger_ukeire_count():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 2m",
        player_action="dahai 2p",
        ukeire=UkeireInfo(count=37, tiles=["3m"], remaining_by_tile={"3m": 3}),
        ukeire_alt=UkeireInfo(count=33, tiles=["3m"], remaining_by_tile={"3m": 3}),
    )
    bad_only = Explanation(
        summary=(
            "Throw 2-man, not 2-pin. You're 3-shanten (3 steps from ready) with "
            "only about 37 tiles that can improve your hand, while 2-pin leaves "
            "you with about 33."
        ),
        focus="efficiency",
        pinned_action="dahai 2m",
        contrasted_action="dahai 2p",
    )
    errors = validate_explanation(turn, bad_only)
    assert any("only" in e for e in errors)


def test_grounding_accepts_only_on_smaller_ukeire_contrast():
    turn = make_turn(
        diverge=True,
        mortal_best="dahai 2m",
        player_action="dahai 2p",
        ukeire=UkeireInfo(count=37, tiles=["3m"], remaining_by_tile={"3m": 3}),
        ukeire_alt=UkeireInfo(count=33, tiles=["3m"], remaining_by_tile={"3m": 3}),
    )
    good = Explanation(
        summary=(
            "Throw 2-man, not 2-pin. You're 3-shanten (3 steps from ready) with "
            "about 37 tiles that can improve your hand, while 2-pin leaves you "
            "with only about 33."
        ),
        focus="efficiency",
        pinned_action="dahai 2m",
        contrasted_action="dahai 2p",
    )
    assert validate_explanation(turn, good) == []


def test_grounding_accepts_narrow_ukeire_contrast():
    turn = make_turn(
        diverge=False,
        mortal_best="dahai 7s",
        player_action="dahai 7s",
        ukeire=UkeireInfo(count=33, tiles=["4m"], remaining_by_tile={"4m": 3}),
        ukeire_alt=UkeireInfo(count=31, tiles=["1p"], remaining_by_tile={"1p": 3}),
    )
    turn.mortal_output.candidates = [
        MortalCandidate(action="dahai 7s", prob=0.79),
        MortalCandidate(action="dahai C", prob=0.11),
    ]
    good = Explanation(
        summary=(
            "Throw 7-sou, not Chun. That leaves about 33 improving tiles left "
            "vs about 31 if you throw Chun."
        ),
        focus="efficiency",
        pinned_action="dahai 7s",
        contrasted_action="dahai C",
    )
    assert validate_explanation(turn, good) == []


def test_grounding_accepts_alternate_cut_dead_end():
    turn = make_turn(
        mortal_best="dahai 7s",
        player_action="dahai 7s",
        diverge=False,
        ukeire=UkeireInfo(count=33, tiles=["4m"], remaining_by_tile={"4m": 3}),
        ukeire_alt=UkeireInfo(count=33, tiles=["1p"], remaining_by_tile={"1p": 3}),
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
    good = Explanation(
        summary="Throw 7-sou, not Chun. Chun is a dead-end tile.",
        focus="efficiency",
        pinned_action="dahai 7s",
        contrasted_action="dahai C",
    )
    assert validate_explanation(turn, good) == []


def test_grounding_rejects_dead_end_on_alternate_tile():
    turn = make_turn(
        mortal_best="dahai C",
        player_action="dahai 3s",
        diverge=True,
        ukeire=UkeireInfo(count=30, tiles=["4s"], remaining_by_tile={"4s": 3}),
        ukeire_alt=UkeireInfo(count=11, tiles=["4s"], remaining_by_tile={"4s": 3}),
    )
    turn.game_state.hand = [
        "2p",
        "5p",
        "7p",
        "1s",
        "2s",
        "2s",
        "3s",
        "3s",
        "1m",
        "2m",
        "3m",
        "3m",
        "C",
        "4p",
    ]
    turn.features.hand_shape_notes = [
        HandShapeNote(kind="floating_honor", tile="C")
    ]
    bad = Explanation(
        summary=(
            "Throw Chun. That leaves about 30 tiles that can improve your hand, "
            "vs about 11 if you throw 3-sou. You're 2-shanten (2 steps from "
            "ready)—Chun is a floating honor, while 3-sou is a dead-end tile that "
            "connects to nothing useful."
        ),
        focus="efficiency",
        pinned_action="dahai C",
        contrasted_action="dahai 3s",
    )
    errors = validate_explanation(turn, bad)
    assert any("dead_end" in e and "3s" in e for e in errors)


def test_grounding_rejects_isolated_kanchan_on_wrong_tile():
    turn = make_turn(
        shape_goals=["yakuhai"],
        mortal_best="dahai 2p",
        player_action="dahai S",
        diverge=True,
        ukeire=UkeireInfo(count=12, tiles=["4p"], remaining_by_tile={"4p": 3}),
    )
    turn.game_state.hand = [
        "3p",
        "3p",
        "5p",
        "5p",
        "7p",
        "8p",
        "1s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "S",
        "2p",
    ]
    turn.features.context = {"jikaze": "E", "bakaze": "E"}
    # No isolated_kanchan note — claiming 2-pin is one must fail.
    bad = Explanation(
        summary=(
            "Throw 2-pin. That keeps your hand intact while maintaining a chance "
            "to improve with about 12 tiles that can help you.\nYou're 2-shanten "
            "(2 steps from ready) and aiming for yakuhai (triplet of dragon or "
            "your seat/round wind) with a pair of South, while 2-pin is an "
            "isolated kanchan (closed middle fragment)."
        ),
        focus="efficiency",
        pinned_action="dahai 2p",
        contrasted_action="dahai S",
    )
    errors = validate_explanation(turn, bad)
    assert any("isolated_kanchan" in e for e in errors)
    assert any("yakuhai_pairs" in e or "pair of" in e for e in errors)


def test_grounding_rules_registry_is_unique():
    rule_ids = [rule.id for rule in GROUNDING_RULES]
    assert len(rule_ids) == len(set(rule_ids))


def _kanchan_cut_turn() -> TurnExplainInput:
    turn = make_turn(mortal_best="dahai 8m", player_action="dahai 2s", diverge=True)
    turn.features.hand_shape_notes = [HandShapeNote(kind="isolated_kanchan", tile="8m")]
    return turn


def _wall_jargon_turn() -> TurnExplainInput:
    return make_turn(
        ukeire=UkeireInfo(
            count=4,
            tiles=["4s"],
            remaining_by_tile={"4s": 1},
        ),
    )


def _pinned_keep_west_turn() -> TurnExplainInput:
    turn = make_turn(mortal_best="dahai W", player_action="dahai E")
    turn.features.hand_shape_notes = [HandShapeNote(kind="dead_end", tile="W")]
    return turn


RULE_REJECT_CASES: list[tuple[str, TurnExplainInput, Explanation, str]] = [
    (
        "isolated_shape_on_cut_phrasing",
        _kanchan_cut_turn(),
        Explanation(
            summary=(
                "Throw 8-man. That keeps your hand intact with about 19 tiles that "
                "can improve it, while throwing 2-sou would not change your current "
                "situation.\nYou're 2-shanten (2 steps from ready) and aiming for "
                "pinfu (closed all-sequences; no value pair) with an isolated "
                "kanchan (closed middle fragment) on 8-man."
            ),
            focus="efficiency",
            pinned_action="dahai 8m",
            contrasted_action="dahai 2s",
        ),
        "isolated_shape_on_cut_phrasing",
    ),
    (
        "pinned_cut_keep_contradiction",
        _pinned_keep_west_turn(),
        Explanation(
            summary=(
                "Throw West. You're 3-shanten (3 steps from ready) with about 51 "
                "tiles that can improve your hand. West is a dead-end tile, but "
                "keeping West is still fine for now."
            ),
            focus="efficiency",
            pinned_action="dahai W",
            contrasted_action="dahai E",
        ),
        "pinned_cut_keep_contradiction",
    ),
    (
        "dora_keep_dead_end_clash",
        make_turn(
            mortal_best="dahai C",
            player_action="dahai C",
            dora_in_hand=["W"],
        ),
        Explanation(
            summary=(
                "Throw Chun, not West.\n"
                "Keeping dora (bonus tile) West.\n"
                "West is a dead-end tile."
            ),
            focus="value",
            pinned_action="dahai C",
            contrasted_action="dahai W",
        ),
        "dora_keep_dead_end_clash",
    ),
    (
        "wall_jargon",
        _wall_jargon_turn(),
        Explanation(
            summary=(
                "Throw 3-pin. Calling would open the hand given the thinning wall "
                "(only 1 red 5-pin left)."
            ),
            focus="efficiency",
            pinned_action="dahai 3p",
            contrasted_action="dahai 5m",
        ),
        "ambiguous wall/thinning jargon",
    ),
    (
        "false_yakuhai_pair",
        yakuhai_haku_pair_turn(),
        Explanation(
            summary=(
                "Throw 1-man, not East. You're 3-shanten (3 steps from ready) with "
                "about 40 tiles that can improve your hand.\nYou're aiming for "
                "yakuhai (triplet of dragon or your seat/round wind)—you have a "
                "pair of East for that, while 1-man is a floating terminal."
            ),
            focus="efficiency",
            pinned_action="dahai 1m",
            contrasted_action="dahai E",
        ),
        "yakuhai_pairs",
    ),
]


@pytest.mark.parametrize(
    ("rule_id", "turn", "explanation", "error_fragment"),
    RULE_REJECT_CASES,
    ids=[case[0] for case in RULE_REJECT_CASES],
)
def test_grounding_rule_rejects_bad_case(
    rule_id: str,
    turn: TurnExplainInput,
    explanation: Explanation,
    error_fragment: str,
) -> None:
    errors = validate_explanation(turn, explanation)
    assert any(error_fragment in err for err in errors), (
        f"expected {rule_id!r} violation, got {errors!r}"
    )

