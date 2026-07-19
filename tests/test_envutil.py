"""Stdlib .env loader."""

from __future__ import annotations

from pathlib import Path

from shanten_sensei.envutil import load_dotenv, parse_dotenv


def test_parse_dotenv_basics():
    text = """
# comment
OPENAI_API_KEY=sk-test
SENSEI_MODEL="gpt-4o-mini"
export SENSEI_BASE_URL='https://example.com/v1'
EMPTY=
NOEQ
"""
    parsed = parse_dotenv(text)
    assert parsed["OPENAI_API_KEY"] == "sk-test"
    assert parsed["SENSEI_MODEL"] == "gpt-4o-mini"
    assert parsed["SENSEI_BASE_URL"] == "https://example.com/v1"
    assert parsed["EMPTY"] == ""
    assert "NOEQ" not in parsed


def test_load_dotenv_does_not_override(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SENSEI_TEST_KEY=from_file\nALREADY=from_file\n", encoding="utf-8")
    monkeypatch.setenv("ALREADY", "from_env")
    monkeypatch.delenv("SENSEI_TEST_KEY", raising=False)

    loaded = load_dotenv(env_file)
    assert loaded == env_file
    import os

    assert os.environ["SENSEI_TEST_KEY"] == "from_file"
    assert os.environ["ALREADY"] == "from_env"
