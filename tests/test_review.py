from pathlib import Path

from shanten_sensei.cli import main
from shanten_sensei.explain import explain, validate_explanation
from shanten_sensei.ingest import diverge_turns_from_path, iter_diverge_turns, load_json

REPORT = Path(__file__).resolve().parents[1] / "fixtures" / "review_mini" / "report.json"


def test_iter_diverge_turns_skips_matches():
    blob = load_json(REPORT)
    diverges = list(iter_diverge_turns(blob))
    assert len(diverges) == 2
    assert diverges[0].index == 1
    assert diverges[0].kyoku == 0
    assert diverges[0].honba == 0
    assert diverges[0].junme == 8
    assert diverges[0].turn.diverge is True
    assert diverges[0].turn.mortal_best == "dahai 9p"
    assert diverges[0].turn.player_action == "dahai 5s"
    assert diverges[1].kyoku == 1
    assert diverges[1].honba == 1
    assert diverges[1].junme == 4
    assert diverges[1].turn.player_action == "dahai 4s"


def test_iter_diverge_turns_limit():
    blob = load_json(REPORT)
    diverges = list(iter_diverge_turns(blob, limit=1))
    assert len(diverges) == 1
    assert diverges[0].index == 1


def test_diverge_turns_offline_explain_pins_mortal():
    for d in diverge_turns_from_path(REPORT):
        result = explain(d.turn, use_llm=False)
        assert result.pinned_action == d.turn.mortal_best
        assert validate_explanation(d.turn, result) == []


def test_cli_review_smoke(capsys):
    code = main(["review", str(REPORT)])
    captured = capsys.readouterr()
    assert code == 0
    assert "--- E1 / kyoku 0 honba 0 / junme 8 ---" in captured.out
    assert "--- E2 / kyoku 1 honba 1 / junme 4 ---" in captured.out
    assert "2 diverges, 0 warnings" in captured.out


def test_cli_review_json(capsys):
    code = main(["review", str(REPORT), "--json", "--limit", "1"])
    captured = capsys.readouterr()
    assert code == 0
    data = __import__("json").loads(captured.out)
    assert data["diverge_count"] == 1
    assert data["warning_count"] == 0
    assert data["diverges"][0]["explanation"]["pinned_action"] == "dahai 9p"
