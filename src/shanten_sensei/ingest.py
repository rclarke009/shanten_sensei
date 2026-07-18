"""Normalize mjai-reviewer Mortal JSON entries into TurnExplainInput."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shanten_sensei.features import extract_features
from shanten_sensei.schema import (
    GameState,
    MortalCandidate,
    MortalOutput,
    TurnExplainInput,
)
from shanten_sensei.tiles import action_to_label, normalize_tile


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def entry_from_reviewer_blob(blob: dict[str, Any]) -> dict[str, Any]:
    """Accept a raw Entry, or a thin wrapper {entry, kyoku?, context?}."""
    if "entry" in blob:
        return blob["entry"]
    if "expected" in blob and "actual" in blob and "state" in blob:
        return blob
    raise ValueError(
        "expected an mjai-reviewer Entry or a wrapper with an 'entry' key"
    )


def turn_from_entry(
    entry: dict[str, Any],
    *,
    kyoku_meta: dict[str, Any] | None = None,
    extra_context: dict[str, Any] | None = None,
) -> TurnExplainInput:
    """Build a grounded TurnExplainInput from one Mortal review Entry."""
    state = entry.get("state") or {}
    hand = [normalize_tile(t) for t in state.get("tehai") or []]
    calls = list(state.get("fuuros") or [])

    expected = entry["expected"]
    actual = entry["actual"]
    mortal_best = action_to_label(expected)
    player_action = action_to_label(actual)

    details = entry.get("details") or []
    candidates = [
        MortalCandidate(
            action=action_to_label(d["action"]),
            q_value=d.get("q_value"),
            prob=d.get("prob"),
        )
        for d in details
    ]
    if candidates and candidates[0].action != mortal_best:
        # Prefer highest q_value ordering from reviewer; keep expected as pin.
        pass

    discard_tile = None
    if (expected.get("type") or expected.get("type_")) == "dahai":
        discard_tile = normalize_tile(expected["pai"])

    kyoku_meta = kyoku_meta or {}
    context = {
        "junme": entry.get("junme"),
        "tiles_left": entry.get("tiles_left"),
        "kyoku": kyoku_meta.get("kyoku"),
        "honba": kyoku_meta.get("honba", entry.get("honba")),
        "relative_scores": kyoku_meta.get("relative_scores"),
        "at_self_riichi": entry.get("at_self_riichi", False),
        **(extra_context or {}),
    }

    # Optional enrichment fields (not always in Entry; fixtures may supply them)
    discards = [
        normalize_tile(t) for t in (entry.get("player_discards") or [])
    ]
    dora_indicators = [
        normalize_tile(t) for t in (entry.get("dora_indicators") or [])
    ]
    visible_discards = {
        str(k): [normalize_tile(t) for t in v]
        for k, v in (entry.get("visible_discards") or {}).items()
    }
    genbutsu = [normalize_tile(t) for t in (entry.get("genbutsu") or [])]

    candidate_tiles = []
    for c in candidates:
        if c.action.startswith("dahai "):
            candidate_tiles.append(c.action.split(" ", 1)[1])

    features = extract_features(
        hand,
        calls=calls,
        discards=discards,
        dora_indicators=dora_indicators,
        riichi=bool(entry.get("at_self_riichi")),
        at_furiten_hint=entry.get("at_furiten"),
        candidate_tiles=candidate_tiles,
        visible_discards=visible_discards,
        genbutsu_tiles=genbutsu,
        context=context,
        ukeire_after_discard=discard_tile,
    )

    # Prefer Mortal's reported shanten when present
    if "shanten" in entry and entry["shanten"] is not None:
        features.shanten = int(entry["shanten"])
        features.statuses.shanten = int(entry["shanten"])
        features.statuses.tenpai = int(entry["shanten"]) == 0

    game_state = GameState(
        hand=hand,
        calls=calls,
        discards=discards,
        visible_discards=visible_discards,
        dora_indicators=dora_indicators,
        turn=entry.get("junme"),
        tiles_left=entry.get("tiles_left"),
        honba=kyoku_meta.get("honba"),
        scores=kyoku_meta.get("relative_scores"),
        kyoku=kyoku_meta.get("kyoku"),
    )

    mortal_output = MortalOutput(
        recommended=mortal_best,
        candidates=candidates,
        raw_expected=expected,
    )

    return TurnExplainInput(
        game_state=game_state,
        mortal_output=mortal_output,
        features=features,
        player_action=player_action,
        mortal_best=mortal_best,
        diverge=not bool(entry.get("is_equal", False)),
    )


def turn_from_path(path: str | Path) -> TurnExplainInput:
    blob = load_json(path)
    entry = entry_from_reviewer_blob(blob)
    return turn_from_entry(
        entry,
        kyoku_meta=blob.get("kyoku"),
        extra_context=blob.get("context"),
    )
