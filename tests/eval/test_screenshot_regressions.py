"""Screenshot-shaped regression tests (copy-sensitive)."""

from conftest import make_turn

import pytest

from shanten_sensei.explain import (
    explain,
    score_explanation_substance,
    template_explain,
    validate_explanation,
)
from shanten_sensei.schema import Explanation, MortalCandidate, UkeireInfo

pytestmark = pytest.mark.eval

def test_screenshot_thin_higher_probability():
    turn = make_turn(dora_in_hand=["3s"])
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
    turn = make_turn(mortal_best="dahai 6p", player_action="dahai 3p")
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


def test_screenshot_thin_efficiency_is_worse():
    """Vague 'efficiency is worse' with no anchors is a thin claim."""
    turn = make_turn(mortal_best="dahai 3p", player_action="dahai P")
    summary = "Throw 3-pin, not Haku, but efficiency is worse."
    score = score_explanation_substance(turn, summary)
    assert score.thin is True
    assert "thin_efficiency_claim" in score.issues
    assert "thin_efficiency_claim" in validate_explanation(
        turn,
        Explanation(
            summary=summary,
            focus="mixed",
            pinned_action="dahai 3p",
            contrasted_action="dahai P",
        ),
    )


def test_screenshot_7s_vs_chun_coaching_depth():
    """Screenshot-shaped: thin tip gets narrow contrast, preview, and alt shape."""
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
            count=31,
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
    summary_l = result.summary.lower()
    assert "throw" in summary_l and "not" in summary_l
    assert "vs about 31" in summary_l
    assert "dead-end" in summary_l
    assert validate_explanation(turn, result) == []
    score = score_explanation_substance(turn, result.summary)
    assert score.thin is False


