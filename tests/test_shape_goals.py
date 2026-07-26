"""Table-driven shape/yaku goal heuristics + explain grounding."""

from shanten_sensei.explain import template_explain, validate_explanation
from shanten_sensei.features import extract_features, infer_shape_goals
from shanten_sensei.schema import (
    DerivedFeatures,
    Explanation,
    GameState,
    HandStatuses,
    MortalCandidate,
    MortalOutput,
    TurnExplainInput,
    UkeireInfo,
)


def test_infer_tanyao_all_simples():
    hand = [
        "2m",
        "3m",
        "4m",
        "3p",
        "4p",
        "5p",
        "2s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "8s",
    ]
    assert infer_shape_goals(hand) == ["tanyao"]


def test_infer_not_tanyao_with_terminal():
    hand = [
        "1m",
        "2m",
        "3m",
        "3p",
        "4p",
        "5p",
        "2s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "8s",
    ]
    assert "tanyao" not in infer_shape_goals(hand)


def test_infer_yakuhai_dragon_pair():
    hand = [
        "2m",
        "3m",
        "4m",
        "5p",
        "6p",
        "7p",
        "2s",
        "3s",
        "4s",
        "C",
        "C",
        "1s",
        "9s",
    ]
    assert "yakuhai" in infer_shape_goals(hand)
    assert "tanyao" not in infer_shape_goals(hand)


def test_infer_yakuhai_seat_wind_from_context():
    hand = [
        "2m",
        "3m",
        "4m",
        "5p",
        "6p",
        "7p",
        "2s",
        "3s",
        "4s",
        "E",
        "E",
        "1s",
        "9s",
    ]
    assert "yakuhai" not in infer_shape_goals(hand)
    assert "yakuhai" in infer_shape_goals(hand, context={"jikaze": "E"})


def test_infer_chinitsu_not_honitsu():
    hand = [
        "1s",
        "2s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "8s",
        "9s",
        "2s",
        "3s",
        "5s",
        "6s",
    ]
    goals = infer_shape_goals(hand)
    assert goals[0] == "chinitsu"
    assert "honitsu" not in goals


def test_infer_honitsu_with_honors():
    hand = [
        "1s",
        "2s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "8s",
        "9s",
        "2s",
        "3s",
        "C",
        "C",
    ]
    goals = infer_shape_goals(hand)
    assert "honitsu" in goals
    assert "chinitsu" not in goals
    assert "yakuhai" in goals


def test_infer_not_chinitsu_mixed_suits():
    hand = [
        "1s",
        "2s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "8s",
        "1m",
        "2m",
        "3m",
        "4m",
        "5m",
    ]
    goals = infer_shape_goals(hand)
    assert "chinitsu" not in goals
    assert "honitsu" not in goals


def test_infer_chiitoi_competitive():
    # Six pairs + one singleton → chiitoi tenpai; regular usually worse
    hand = [
        "1m",
        "1m",
        "3m",
        "3m",
        "5p",
        "5p",
        "7p",
        "7p",
        "2s",
        "2s",
        "4s",
        "4s",
        "9s",
    ]
    assert "chiitoi" in infer_shape_goals(hand)


def test_infer_toitoi_strong_sets():
    hand = [
        "1m",
        "1m",
        "1m",
        "3p",
        "3p",
        "3p",
        "5s",
        "5s",
        "5s",
        "7m",
        "7m",
        "9p",
        "9p",
    ]
    assert "toitoi" in infer_shape_goals(hand)


def test_extract_features_shape_goals_after_discard():
    # 14 tiles: cut Chun → remaining all-simples tanyao
    hand = [
        "2m",
        "3m",
        "4m",
        "3p",
        "4p",
        "5p",
        "2s",
        "3s",
        "4s",
        "5s",
        "6s",
        "7s",
        "8s",
        "C",
    ]
    feats = extract_features(hand, ukeire_after_discard="C", dora_indicators=["2s"])
    assert feats.shape_goals == ["tanyao"]
    assert "3s" in feats.statuses.dora_in_hand


def _turn_with_goals(
    *,
    shape_goals: list[str],
    dora_in_hand: list[str] | None = None,
    mortal_best: str = "dahai 5s",
    player_action: str = "dahai 9p",
) -> TurnExplainInput:
    return TurnExplainInput(
        game_state=GameState(hand=["2m", "3m", "4m", "5s", "9p"] + ["2s"] * 8),
        mortal_output=MortalOutput(
            recommended=mortal_best,
            candidates=[
                MortalCandidate(action=mortal_best, prob=0.7),
                MortalCandidate(action=player_action, prob=0.3),
            ],
        ),
        features=DerivedFeatures(
            shanten=2,
            ukeire=UkeireInfo(count=20, tiles=["2m", "5m"]),
            statuses=HandStatuses(
                shanten=2,
                dora_in_hand=dora_in_hand or [],
            ),
            shape_goals=shape_goals,
        ),
        player_action=player_action,
        mortal_best=mortal_best,
        diverge=True,
    )


def test_template_includes_fits_goals():
    turn = _turn_with_goals(shape_goals=["tanyao"], dora_in_hand=["3s"])
    result = template_explain(turn)
    assert "Throw" in result.summary
    assert "2-shanten (2 steps from ready)" in result.summary
    assert "acceptances (tiles that improve the hand)" in result.summary
    assert "fits tanyao (2–8 only; no 1/9, winds, or dragons)" in result.summary
    assert "dora (bonus tile)" in result.summary
    assert "3-sou" in result.summary.lower() or "3s" in result.summary
    assert validate_explanation(turn, result) == []


def test_template_glosses_multiple_goals():
    turn = _turn_with_goals(shape_goals=["honitsu", "yakuhai"], dora_in_hand=["5m"])
    result = template_explain(turn)
    assert "honitsu (one suit + winds/dragons OK)" in result.summary
    assert "yakuhai (triplet of dragon or your seat/round wind)" in result.summary
    assert "dora (bonus tile)" in result.summary
    assert "fits" in result.summary
    assert validate_explanation(turn, result) == []


def test_template_yakuhai_because_east_pair_not_chun():
    """Screenshot-style: East pair yakuhai; cut 1m, keep singleton Chun."""
    hand = [
        "1m",
        "6m",
        "7m",
        "8m",
        "2p",
        "3p",
        "4p",
        "5p",
        "6p",
        "3s",
        "4s",
        "5s",
        "E",
        "E",
        "C",
    ]
    turn = TurnExplainInput(
        game_state=GameState(hand=hand),
        mortal_output=MortalOutput(
            recommended="dahai 1m",
            candidates=[
                MortalCandidate(action="dahai 1m", prob=0.55),
                MortalCandidate(action="dahai C", prob=0.2),
            ],
        ),
        features=DerivedFeatures(
            shanten=3,
            ukeire=UkeireInfo(count=54, tiles=["2m", "5m"]),
            ukeire_alt=UkeireInfo(count=40, tiles=["2m"]),
            statuses=HandStatuses(shanten=3),
            shape_goals=["yakuhai"],
            context={"jikaze": "E", "bakaze": "E"},
        ),
        player_action="dahai 1m",
        mortal_best="dahai 1m",
        diverge=False,
    )
    result = template_explain(turn)
    assert "Throw" in result.summary
    assert "1-man" in result.summary
    assert "Chun" in result.summary
    assert "fits yakuhai (triplet of dragon or your seat/round wind)" in result.summary
    assert "pair of" in result.summary and "East" in result.summary
    assert "isn’t a value tile" in result.summary or "isn't a value tile" in result.summary
    assert "can still pair" in result.summary
    assert "would not help" not in result.summary
    assert validate_explanation(turn, result) == []


def test_template_omits_goals_when_empty():
    turn = _turn_with_goals(shape_goals=[])
    result = template_explain(turn)
    assert "fits tanyao" not in result.summary
    assert "shape leans" not in result.summary
    assert validate_explanation(turn, result) == []


def test_grounding_rejects_unlisted_yaku():
    turn = _turn_with_goals(shape_goals=["tanyao"])
    bad = Explanation(
        summary="Throw 5-sou, not 9-pin. Keep pinfu.",
        focus="efficiency",
        pinned_action="dahai 5s",
        contrasted_action="dahai 9p",
    )
    errors = validate_explanation(turn, bad)
    assert any("pinfu" in e for e in errors)


def test_grounding_allows_listed_yaku_and_dora():
    turn = _turn_with_goals(shape_goals=["honitsu", "yakuhai"], dora_in_hand=["5m"])
    ok = Explanation(
        summary=(
            "Throw 5-sou. That fits "
            "honitsu (one suit + winds/dragons OK) / "
            "yakuhai (triplet of dragon or your seat/round wind) "
            "with dora (bonus tile) 5-man."
        ),
        focus="value",
        pinned_action="dahai 5s",
        contrasted_action="dahai 9p",
    )
    assert validate_explanation(turn, ok) == []