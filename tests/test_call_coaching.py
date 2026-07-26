"""Call coaching: Skip/Call voice, label unification, open-vs-closed tradeoffs."""

from pathlib import Path

from shanten_sensei.explain import explain, template_explain, validate_explanation
from shanten_sensei.features import build_call_tradeoff, simulate_shanten_after_call
from shanten_sensei.ingest import turn_from_path
from shanten_sensei.live import (
    candidates_from_meta_options,
    next_best_action,
    turn_from_live,
    unify_call_candidates,
)
from shanten_sensei.schema import MortalCandidate
from shanten_sensei.tiles import coach_action_label

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"

# Screenshot-like closed hand: tanyao-ish but still holding terminals; pon on 3s available
SKIP_PON_HAND = [
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
]


def test_coach_action_label_skip_and_pon():
    assert coach_action_label("none") == "Skip"
    assert "pon" in coach_action_label("pon W").lower()
    assert "West" in coach_action_label("pon W")
    assert coach_action_label("chi_mid") == "Chi"
    assert "5-man" in coach_action_label("chi 5mr").lower() or "red" in coach_action_label(
        "chi 5mr"
    ).lower()


def test_unify_pon_w_with_bare_pon_meta():
    cands = unify_call_candidates(
        [
            MortalCandidate(action="pon W", prob=0.9),
            MortalCandidate(action="pon", prob=0.05),
            MortalCandidate(action="none", prob=0.05),
        ],
        "pon W",
        call_tile="W",
    )
    actions = [c.action for c in cands]
    assert actions.count("pon W") == 1
    assert "pon" not in actions
    assert "none" in actions


def test_live_pon_w_plus_bare_pon_contrasts_skip():
    turn = turn_from_live(
        hand=["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "W", "W", "N", "P"],
        recommended={"type": "pon", "pai": "W", "consumed": ["W", "W"]},
        candidates=candidates_from_meta_options([("pon", 0.9), ("none", 0.1)]),
        call_tile="W",
        call_consumed=["W", "W"],
    )
    assert turn.mortal_best == "pon W"
    assert next_best_action(turn) == "none"
    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Call pon" in result.summary
    assert "Skip" in result.summary or "skip" in result.summary
    assert validate_explanation(turn, result) == []


def test_template_skip_vs_pon_tanyao_voice():
    turn = turn_from_live(
        hand=SKIP_PON_HAND,
        recommended="none",
        candidates=candidates_from_meta_options([("none", 0.99), ("pon", 0.01)]),
        call_tile="3s",
        visible_discards={"2": ["3s"]},
        context={"bakaze": "E", "jikaze": "S"},
    )
    assert turn.features.call_tradeoff is not None
    assert turn.features.call_tradeoff.opens_hand is True
    assert turn.features.call_tradeoff.call_action.startswith("pon")
    # Heuristic may under-tag while terminals remain; pin aiming-for for this golden
    turn.features.shape_goals = ["tanyao"]

    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Skip" in result.summary
    assert "pon" in result.summary.lower()
    assert "riichi" in result.summary.lower() or "open" in result.summary.lower()
    assert "tanyao" in result.summary.lower()
    assert "terminal" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_pon_simulation_opens_hand():
    hand = ["1m", "3m", "5m", "6m", "6m", "8m", "4p", "8p", "9p", "W", "W", "N", "P"]
    open_sh = simulate_shanten_after_call(
        hand, "pon W", consumed=["W", "W"], call_tile="W"
    )
    assert open_sh is not None
    tradeoff = build_call_tradeoff(
        hand,
        stay_closed_shanten=3,
        stay_closed_ukeire=40,
        call_action="pon W",
        consumed=["W", "W"],
        call_tile="W",
    )
    assert tradeoff is not None
    assert tradeoff.opens_hand is True
    assert tradeoff.open_shanten == open_sh


def test_diverge_004_call_voice():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_004" / "entry.json")
    assert turn.mortal_best == "pon W"
    assert turn.player_action == "none"
    assert turn.features.call_tradeoff is not None
    assert turn.features.call_tradeoff.open_shanten is not None

    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Call pon" in result.summary
    assert "skip" in result.summary.lower()
    assert validate_explanation(turn, result) == []
    offline = explain(turn, use_llm=False)
    assert offline.pinned_action == "pon W"
    assert "Throw" not in offline.summary


def test_diverge_005_chi_voice():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_005" / "entry.json")
    assert turn.mortal_best.startswith("chi")
    assert turn.player_action == "none"
    assert turn.features.call_tradeoff is not None

    result = template_explain(turn)
    assert "Throw" not in result.summary
    assert "Chi" in result.summary or "chi" in result.summary.lower()
    assert "skip" in result.summary.lower()
    assert validate_explanation(turn, result) == []
