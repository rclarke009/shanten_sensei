"""Call coaching: Skip/Call voice, label unification, open-vs-closed tradeoffs."""

from pathlib import Path

from shanten_sensei.explain import (
    coaching_shape_goals,
    explain,
    template_explain,
    validate_explanation,
)
from shanten_sensei.features import (
    build_call_tradeoff,
    simulate_open_ukeire_after_call,
    simulate_shanten_after_call,
)
from shanten_sensei.ingest import turn_from_path
from shanten_sensei.live import (
    candidates_from_meta_options,
    next_best_action,
    turn_from_live,
    unify_call_candidates,
)
from shanten_sensei.schema import Explanation, MortalCandidate, UkeireInfo
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
    assert "open the hand" in result.summary.lower() or "closed with" in result.summary.lower()
    assert "tanyao" in result.summary.lower()
    assert "terminal" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_template_skip_includes_unseen_copy_note():
    turn = turn_from_live(
        hand=SKIP_PON_HAND,
        recommended="none",
        candidates=candidates_from_meta_options([("none", 0.99), ("pon", 0.01)]),
        call_tile="3s",
        visible_discards={"2": ["3s"]},
    )
    turn.features.shanten = 5
    turn.features.ukeire = UkeireInfo(
        count=91,
        tiles=["5pr", "5p"],
        remaining_by_tile={"5pr": 1, "5p": 3},
    )
    result = template_explain(turn)
    summary_l = result.summary.lower()
    assert "skip" in summary_l
    assert "still unseen" in summary_l or "already out" in summary_l
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
    assert tradeoff.open_ukeire_count is not None
    assert tradeoff.open_ukeire_count >= 0


def test_open_ukeire_simulation_after_pon():
    hand = ["1m", "3m", "5m", "6m", "6m", "8m", "4p", "8p", "9p", "W", "W", "N", "P"]
    open_ukeire = simulate_open_ukeire_after_call(
        hand, "pon W", consumed=["W", "W"], call_tile="W"
    )
    assert open_ukeire is not None
    assert open_ukeire >= 0


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


def test_template_call_does_not_claim_pinfu():
    hand = [
        "2m",
        "3m",
        "4m",
        "5m",
        "6m",
        "7m",
        "3p",
        "4p",
        "5p",
        "5s",
        "5s",
        "6s",
        "7s",
    ]
    turn = turn_from_live(
        hand=hand,
        recommended={"type": "pon", "pai": "5s", "consumed": ["5s", "5s"]},
        candidates=candidates_from_meta_options([("pon", 0.9), ("none", 0.1)]),
        call_tile="5s",
        call_consumed=["5s", "5s"],
    )
    turn.features.shape_goals = ["pinfu"]
    assert turn.features.call_tradeoff is not None
    assert turn.features.call_tradeoff.opens_hand is True
    assert "pinfu" not in coaching_shape_goals(turn)

    result = template_explain(turn)
    assert "Call" in result.summary or "pon" in result.summary.lower()
    assert "pinfu" not in result.summary.lower()
    assert "open" in result.summary.lower() or "riichi" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_grounding_rejects_pinfu_on_open_call():
    hand = [
        "2m",
        "3m",
        "4m",
        "5m",
        "6m",
        "7m",
        "3p",
        "4p",
        "5p",
        "5s",
        "5s",
        "6s",
        "7s",
    ]
    turn = turn_from_live(
        hand=hand,
        recommended={"type": "pon", "pai": "5s", "consumed": ["5s", "5s"]},
        candidates=candidates_from_meta_options([("pon", 0.9), ("none", 0.1)]),
        call_tile="5s",
        call_consumed=["5s", "5s"],
    )
    turn.features.shape_goals = ["pinfu"]
    bad = Explanation(
        summary=(
            "Call pon on 5-sou, don’t skip. This move opens your hand while still "
            "aiming for pinfu (closed all-sequences; no value pair)."
        ),
        focus="tempo",
        pinned_action="pon 5s",
        contrasted_action="none",
    )
    errors = validate_explanation(turn, bad)
    assert any("pinfu" in e for e in errors)


def test_grounding_rejects_pon_verb_when_chi_best():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_005" / "entry.json")
    assert turn.mortal_best.startswith("chi")
    bad = Explanation(
        summary=(
            "Call pon on 5-man, don’t skip. You’re 3-shanten (3 steps from ready) "
            "closed with about 40 improving tiles."
        ),
        focus="tempo",
        pinned_action=turn.mortal_best,
        contrasted_action="none",
    )
    errors = validate_explanation(turn, bad)
    assert any("call kind" in e for e in errors)
