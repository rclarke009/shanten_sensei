from pathlib import Path

from shanten_sensei.explain import explain, template_explain, validate_explanation
from shanten_sensei.ingest import turn_from_path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "diverge_001" / "entry.json"


def test_ingest_diverge_fixture():
    turn = turn_from_path(FIXTURE)
    assert turn.diverge is True
    assert turn.mortal_best == "dahai 9p"
    assert turn.player_action == "dahai 5s"
    assert turn.features.statuses.wait_shape == "ryanmen"
    assert turn.features.ukeire.count == 6
    assert turn.mortal_output.candidates[0].action == "dahai 9p"


def test_template_explain_pins_mortal():
    turn = turn_from_path(FIXTURE)
    result = template_explain(turn)
    assert result.pinned_action == "dahai 9p"
    assert result.contrasted_action == "dahai 5s"
    assert validate_explanation(turn, result) == []


def test_explain_offline_end_to_end():
    turn = turn_from_path(FIXTURE)
    result = explain(turn, use_llm=False)
    assert result.pinned_action == turn.mortal_best
    assert "9p" in result.summary or "9-pin" in result.summary.lower()
    assert validate_explanation(turn, result) == []
