"""Synthetic mjai_log enrichment: rivers, dora, genbutsu danger."""

from __future__ import annotations

from shanten_sensei.ingest import iter_diverge_turns
from shanten_sensei.mjai_board import build_enrichment_index


def _mini_log() -> list[dict]:
    """One East kyoku; player 0; a few tsumo/dahai; opponent river has 9p."""
    return [
        {"type": "start_game", "names": ["A", "B", "C", "D"]},
        {
            "type": "start_kyoku",
            "bakaze": "E",
            "dora_marker": "1m",
            "kyoku": 1,
            "honba": 0,
            "kyotaku": 0,
            "oya": 0,
            "scores": [25000, 25000, 25000, 25000],
            "tehais": [
                ["2m", "3m", "4m", "5m", "6m", "7m", "1p", "2p", "3p", "4p", "5p", "6p", "7p"],
                ["1s"] * 13,
                ["2s"] * 13,
                ["3s"] * 13,
            ],
        },
        # Others discard before player turn 1
        {"type": "tsumo", "actor": 1, "pai": "9s"},
        {"type": "dahai", "actor": 1, "pai": "9p", "tsumogiri": False},
        {"type": "tsumo", "actor": 2, "pai": "1s"},
        {"type": "dahai", "actor": 2, "pai": "1s", "tsumogiri": True},
        {"type": "tsumo", "actor": 3, "pai": "2s"},
        {"type": "dahai", "actor": 3, "pai": "2s", "tsumogiri": True},
        # Player junme 1
        {"type": "tsumo", "actor": 0, "pai": "8p"},
        {"type": "dahai", "actor": 0, "pai": "7p", "tsumogiri": False},
        # Opponent discard — call opportunity at junme 1
        {"type": "tsumo", "actor": 1, "pai": "E"},
        {"type": "dahai", "actor": 1, "pai": "W", "tsumogiri": False},
        # Player junme 2
        {"type": "tsumo", "actor": 2, "pai": "3s"},
        {"type": "dahai", "actor": 2, "pai": "3s", "tsumogiri": True},
        {"type": "tsumo", "actor": 3, "pai": "4s"},
        {"type": "dahai", "actor": 3, "pai": "4s", "tsumogiri": True},
        {"type": "tsumo", "actor": 0, "pai": "9s"},
        {"type": "dahai", "actor": 0, "pai": "8p", "tsumogiri": False},
        {"type": "end_kyoku"},
    ]


def test_dahai_snapshot_rivers_and_dora():
    idx = build_enrichment_index(_mini_log(), player_id=0)
    snap = idx.dahai_by_junme[(0, 1)]
    assert snap.dora_indicators == ["1m"]
    assert snap.player_discards == []
    assert snap.visible_discards["1"] == ["9p"]
    assert snap.visible_discards["2"] == ["1s"]

    snap2 = idx.dahai_by_junme[(0, 2)]
    assert snap2.player_discards == ["7p"]
    assert "W" in snap2.visible_discards["1"]


def test_call_snapshot_after_opponent_dahai():
    idx = build_enrichment_index(_mini_log(), player_id=0)
    entry = {
        "junme": 1,
        "tile": "W",
        "last_actor": 1,
        "expected": {"type": "pon", "actor": 0, "pai": "W"},
        "actual": {"type": "none"},
    }
    snap = idx.for_entry(kyoku_ord=0, entry=entry)
    assert snap is not None
    assert snap.player_discards == ["7p"]
    assert snap.visible_discards["1"][-1] == "W"
    assert snap.dora_indicators == ["1m"]


def test_iter_diverge_enriches_and_marks_genbutsu():
    """Candidate tile 9p is in opponent river → danger genbutsu."""
    hand = [
        "2m",
        "3m",
        "4m",
        "5m",
        "6m",
        "7m",
        "1p",
        "2p",
        "3p",
        "4p",
        "5p",
        "6p",
        "9p",
        "8p",
    ]
    report = {
        "log_id": "enrich_mini",
        "player_id": 0,
        "mjai_log": _mini_log(),
        "review": {
            "kyokus": [
                {
                    "kyoku": 0,
                    "honba": 0,
                    "relative_scores": [25000, 25000, 25000, 25000],
                    "entries": [
                        {
                            "junme": 1,
                            "tiles_left": 60,
                            "is_equal": False,
                            "state": {"tehai": hand, "fuuros": []},
                            "at_self_riichi": False,
                            "at_furiten": False,
                            "expected": {
                                "type": "dahai",
                                "actor": 0,
                                "pai": "8p",
                                "tsumogiri": True,
                            },
                            "actual": {
                                "type": "dahai",
                                "actor": 0,
                                "pai": "9p",
                                "tsumogiri": False,
                            },
                            "details": [
                                {
                                    "action": {
                                        "type": "dahai",
                                        "actor": 0,
                                        "pai": "8p",
                                        "tsumogiri": True,
                                    },
                                    "q_value": 1.0,
                                    "prob": 0.6,
                                },
                                {
                                    "action": {
                                        "type": "dahai",
                                        "actor": 0,
                                        "pai": "9p",
                                        "tsumogiri": False,
                                    },
                                    "q_value": 0.5,
                                    "prob": 0.4,
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    }
    diverges = list(iter_diverge_turns(report))
    assert len(diverges) == 1
    turn = diverges[0].turn
    assert turn.game_state.dora_indicators == ["1m"]
    assert turn.game_state.discards == []
    assert turn.game_state.visible_discards["1"] == ["9p"]
    assert turn.features.danger.get("9p") == "genbutsu"
    assert "1m" in turn.features.statuses.visible_dora


def test_no_mjai_log_skips_enrichment():
    report = {
        "review": {
            "kyokus": [
                {
                    "kyoku": 0,
                    "honba": 0,
                    "entries": [
                        {
                            "junme": 1,
                            "is_equal": False,
                            "state": {
                                "tehai": [
                                    "1m",
                                    "2m",
                                    "3m",
                                    "4m",
                                    "5m",
                                    "6m",
                                    "1p",
                                    "2p",
                                    "3p",
                                    "4p",
                                    "5p",
                                    "6p",
                                    "7p",
                                    "8p",
                                ],
                                "fuuros": [],
                            },
                            "expected": {
                                "type": "dahai",
                                "actor": 0,
                                "pai": "8p",
                                "tsumogiri": False,
                            },
                            "actual": {
                                "type": "dahai",
                                "actor": 0,
                                "pai": "7p",
                                "tsumogiri": False,
                            },
                            "details": [
                                {
                                    "action": {
                                        "type": "dahai",
                                        "actor": 0,
                                        "pai": "8p",
                                        "tsumogiri": False,
                                    },
                                    "q_value": 1.0,
                                    "prob": 1.0,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }
    turn = list(iter_diverge_turns(report))[0].turn
    assert turn.game_state.discards == []
    assert turn.game_state.dora_indicators == []
    assert turn.game_state.visible_discards == {}
