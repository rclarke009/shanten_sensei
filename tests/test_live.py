"""Tests for live turn builder and non-diverge explanations."""

from shanten_sensei.explain import explain, template_explain, validate_explanation
from shanten_sensei.live import (
    candidate_label_from_code,
    candidates_from_meta_options,
    next_best_action,
    turn_from_live,
)
from shanten_sensei.schema import MortalCandidate


# Closed 14-tile hand: Mortal cuts 9p for ryanmen (same shape as diverge_001)
LIVE_HAND = [
    "1m",
    "2m",
    "3m",
    "4p",
    "5p",
    "6p",
    "7s",
    "8s",
    "9s",
    "1s",
    "2s",
    "3s",
    "5s",
    "9p",
]


def test_candidate_label_from_code():
    assert candidate_label_from_code("9p") == "dahai 9p"
    assert candidate_label_from_code("5mr") == "dahai 5mr"
    assert candidate_label_from_code("reach") == "reach"
    assert candidate_label_from_code("none") == "none"


def test_candidates_from_meta_options():
    cands = candidates_from_meta_options([("9p", 0.8), ("5s", 0.15), ("reach", 0.05)])
    assert cands[0].action == "dahai 9p"
    assert cands[0].prob == 0.8
    assert cands[2].action == "reach"


def test_turn_from_live_pending_is_non_diverge():
    turn = turn_from_live(
        hand=LIVE_HAND,
        recommended="dahai 9p",
        candidates=[
            MortalCandidate(action="dahai 9p", prob=0.7),
            MortalCandidate(action="dahai 5s", prob=0.3),
        ],
        turn=3,
        kyoku=0,
        honba=0,
    )
    assert turn.source == "live-copilot"
    assert turn.diverge is False
    assert turn.player_action == "dahai 9p"
    assert turn.mortal_best == "dahai 9p"
    assert next_best_action(turn) == "dahai 5s"
    assert turn.features.shanten >= 0


def test_turn_from_live_with_reaction_dict():
    turn = turn_from_live(
        hand=LIVE_HAND,
        recommended={"type": "dahai", "pai": "9p", "actor": 0},
        candidates=candidates_from_meta_options([("9p", 0.9), ("5s", 0.1)]),
    )
    assert turn.mortal_best == "dahai 9p"
    assert turn.mortal_output.raw_expected is not None


def test_turn_from_live_post_action_diverge():
    turn = turn_from_live(
        hand=LIVE_HAND,
        recommended="dahai 9p",
        candidates=[
            MortalCandidate(action="dahai 9p", prob=0.7),
            MortalCandidate(action="dahai 5s", prob=0.3),
        ],
        player_action="dahai 5s",
    )
    assert turn.diverge is True
    assert turn.player_action == "dahai 5s"


def test_template_explain_live_contrasts_next_best():
    turn = turn_from_live(
        hand=LIVE_HAND,
        recommended="dahai 9p",
        candidates=[
            MortalCandidate(action="dahai 9p", prob=0.7),
            MortalCandidate(action="dahai 5s", prob=0.3),
        ],
    )
    result = template_explain(turn)
    assert result.pinned_action == "dahai 9p"
    assert result.contrasted_action == "dahai 5s"
    assert "9p" in result.summary or "9-pin" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_explain_offline_live():
    turn = turn_from_live(
        hand=LIVE_HAND,
        recommended="dahai 9p",
        candidates=[
            MortalCandidate(action="dahai 9p", prob=0.7),
            MortalCandidate(action="dahai 5s", prob=0.3),
        ],
    )
    result = explain(turn, use_llm=False)
    assert result.pinned_action == turn.mortal_best
    assert validate_explanation(turn, result) == []
