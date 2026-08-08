"""Property: template_explain always passes grounding validators."""

from __future__ import annotations

from random import Random

import pytest

from conftest import make_turn
from shanten_sensei.explain import template_explain, validate_explanation
from shanten_sensei.schema import UkeireInfo

_SHAPES = ("pinfu", "tanyao", "yakuhai")
_ACTIONS = ("dahai 3p", "dahai 5m", "dahai 2s", "dahai W", "dahai 9p")
_TILES = ("2m", "4p", "7s", "3p", "9m")


def random_turn(rng: Random):
    mortal = rng.choice(_ACTIONS)
    ukeire_count = rng.randint(3, 80)
    tiles = rng.sample(_TILES, k=min(3, len(_TILES)))
    return make_turn(
        shape_goals=rng.sample(_SHAPES, k=rng.randint(0, 1)),
        mortal_best=mortal,
        player_action=mortal,
        diverge=False,
        ukeire=UkeireInfo(
            count=ukeire_count,
            tiles=tiles,
            remaining_by_tile={t: rng.randint(0, 4) for t in tiles},
        ),
    )


@pytest.fixture
def random_turns() -> list:
    rng = Random(0)
    return [random_turn(rng) for _ in range(300)]


def test_template_explain_always_grounded(random_turns) -> None:
    for turn in random_turns:
        explanation = template_explain(turn)
        errors = validate_explanation(turn, explanation)
        assert errors == [], f"turn={turn.mortal_best!r} errors={errors!r}"
