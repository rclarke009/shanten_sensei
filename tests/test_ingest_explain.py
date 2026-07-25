from pathlib import Path

import pytest

from shanten_sensei.explain import (
    coerce_focus,
    explain,
    explanation_from_llm_data,
    template_explain,
    validate_explanation,
)
from shanten_sensei.ingest import turn_from_path

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
DIVERGE_001 = FIXTURES_ROOT / "diverge_001" / "entry.json"
DIVERGE_FIXTURES = sorted(FIXTURES_ROOT.glob("diverge_*/entry.json"))


@pytest.mark.parametrize(
    "path",
    DIVERGE_FIXTURES,
    ids=[p.parent.name for p in DIVERGE_FIXTURES],
)
def test_ingest_and_offline_explain_all_diverges(path: Path):
    turn = turn_from_path(path)
    assert turn.diverge is True
    assert turn.mortal_best
    assert turn.player_action
    assert turn.mortal_output.candidates
    result = explain(turn, use_llm=False)
    assert result.pinned_action == turn.mortal_best
    assert validate_explanation(turn, result) == []


def test_ingest_diverge_001_ryanmen():
    turn = turn_from_path(DIVERGE_001)
    assert turn.mortal_best == "dahai 9p"
    assert turn.player_action == "dahai 5s"
    assert turn.features.statuses.wait_shape == "ryanmen"
    assert turn.features.ukeire.count == 6
    assert turn.mortal_output.candidates[0].action == "dahai 9p"


def test_ingest_diverge_002_pins():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_002" / "entry.json")
    assert turn.mortal_best == "dahai 8s"
    assert turn.player_action == "dahai 6p"
    assert turn.features.shanten == 1


def test_ingest_diverge_003_pins():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_003" / "entry.json")
    assert turn.mortal_best == "dahai P"
    assert turn.player_action == "dahai 9p"


def test_ingest_diverge_004_pins():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_004" / "entry.json")
    assert turn.mortal_best == "pon W"
    assert turn.player_action == "none"


def test_ingest_diverge_005_pins():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_005" / "entry.json")
    assert turn.mortal_best.startswith("chi")
    assert "5m" in turn.mortal_best  # 5mr normalizes / appears as aka
    assert turn.player_action == "none"


def test_template_explain_pins_mortal():
    turn = turn_from_path(DIVERGE_001)
    result = template_explain(turn)
    assert result.pinned_action == "dahai 9p"
    assert result.contrasted_action == "dahai 5s"
    assert "9-pin" in result.summary.lower()
    assert "5-sou" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_template_explain_honor_haku_display():
    turn = turn_from_path(FIXTURES_ROOT / "diverge_003" / "entry.json")
    result = template_explain(turn)
    assert result.pinned_action == "dahai P"
    assert "Haku" in result.summary
    assert "🀆" in result.summary
    assert " F " not in f" {result.summary} "
    assert " P " not in f" {result.summary} "
    assert validate_explanation(turn, result) == []


def test_explain_offline_end_to_end():
    turn = turn_from_path(DIVERGE_001)
    result = explain(turn, use_llm=False)
    assert result.pinned_action == turn.mortal_best
    assert "9p" in result.summary or "9-pin" in result.summary.lower()
    assert validate_explanation(turn, result) == []


def test_coerce_focus_rejects_prose():
    assert coerce_focus("efficiency") == "efficiency"
    assert coerce_focus("By discarding 8s, you improve ukeire.") == "mixed"
    assert coerce_focus(None) == "mixed"


def test_explanation_from_llm_data_coerces_bad_focus():
    turn = turn_from_path(DIVERGE_001)
    result = explanation_from_llm_data(
        turn,
        {
            "summary": "Mortal prefers 9p over 5s to keep a ryanmen wait.",
            "focus": "By discarding 8s, you improve the current hand structure.",
            "pinned_action": "dahai 9p",
            "contrasted_action": "dahai 5s",
        },
    )
    assert result.focus == "mixed"
    assert result.pinned_action == "dahai 9p"
    assert validate_explanation(turn, result) == []


def test_explanation_from_llm_data_recovers_summary_in_focus():
    turn = turn_from_path(DIVERGE_001)
    result = explanation_from_llm_data(
        turn,
        {
            "focus": "Mortal prefers 9-pin over 5-sou to keep a ryanmen wait.",
            "pinned_action": "dahai 9p",
        },
    )
    assert "9-pin" in result.summary.lower() or "9p" in result.summary
    assert result.focus == "mixed"
