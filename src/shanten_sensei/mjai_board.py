"""Replay mjai_log to recover rivers / dora for review entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shanten_sensei.tiles import normalize_tile


@dataclass(frozen=True)
class BoardSnapshot:
    """Board context immediately before a player decision."""

    player_discards: list[str]
    visible_discards: dict[str, list[str]]
    dora_indicators: list[str]


@dataclass
class EnrichmentIndex:
    """Snapshots keyed by kyoku ordinal (order of start_kyoku / review.kyokus)."""

    dahai_by_junme: dict[tuple[int, int], BoardSnapshot] = field(default_factory=dict)
    # (kyoku_ord, junme, tile, last_actor) → snapshot after that discard
    call_by_key: dict[tuple[int, int, str, int], BoardSnapshot] = field(
        default_factory=dict
    )

    def for_entry(
        self,
        *,
        kyoku_ord: int,
        entry: dict[str, Any],
    ) -> BoardSnapshot | None:
        junme = entry.get("junme")
        if junme is None:
            return None
        expected = entry.get("expected") or {}
        etype = expected.get("type") or expected.get("type_")
        if etype == "dahai":
            return self.dahai_by_junme.get((kyoku_ord, int(junme)))
        tile = entry.get("tile") or expected.get("pai")
        last_actor = entry.get("last_actor")
        if tile is None or last_actor is None:
            return None
        key = (kyoku_ord, int(junme), normalize_tile(tile), int(last_actor))
        return self.call_by_key.get(key)


def _copy_rivers(rivers: dict[int, list[str]]) -> dict[str, list[str]]:
    return {str(a): list(tiles) for a, tiles in rivers.items()}


def _snapshot(rivers: dict[int, list[str]], dora: list[str], player_id: int) -> BoardSnapshot:
    return BoardSnapshot(
        player_discards=list(rivers.get(player_id, [])),
        visible_discards=_copy_rivers(rivers),
        dora_indicators=list(dora),
    )


def build_enrichment_index(
    mjai_log: list[dict[str, Any]],
    player_id: int,
) -> EnrichmentIndex:
    """
    Replay mjai events and capture board snapshots for player decisions.

    Kyoku ordinal is the 0-based index of start_kyoku (matches review.kyokus order).
    Dahai snapshots are taken at each player tsumo (before the discard).
    Call snapshots are taken after each non-player dahai (tile available to call).
    """
    index = EnrichmentIndex()
    kyoku_ord = -1
    junme = 0
    rivers: dict[int, list[str]] = {0: [], 1: [], 2: [], 3: []}
    dora: list[str] = []

    for event in mjai_log:
        etype = event.get("type")
        if etype == "start_kyoku":
            kyoku_ord += 1
            junme = 0
            rivers = {0: [], 1: [], 2: [], 3: []}
            marker = event.get("dora_marker")
            dora = [normalize_tile(marker)] if marker else []
            continue
        if kyoku_ord < 0:
            continue
        if etype == "dora":
            marker = event.get("dora_marker") or event.get("pai")
            if marker:
                dora.append(normalize_tile(marker))
            continue
        if etype == "tsumo" and event.get("actor") == player_id:
            junme += 1
            index.dahai_by_junme[(kyoku_ord, junme)] = _snapshot(
                rivers, dora, player_id
            )
            continue
        if etype == "dahai":
            actor = int(event["actor"])
            pai = normalize_tile(event["pai"])
            rivers.setdefault(actor, []).append(pai)
            if actor != player_id:
                key = (kyoku_ord, junme, pai, actor)
                # First match at this junme/tile/actor wins (call before further play)
                if key not in index.call_by_key:
                    index.call_by_key[key] = _snapshot(rivers, dora, player_id)
            continue
    return index


def enrichment_fields(snapshot: BoardSnapshot) -> dict[str, Any]:
    """Fields mergeable into an entry for turn_from_entry (entry wins if set)."""
    return {
        "player_discards": snapshot.player_discards,
        "visible_discards": snapshot.visible_discards,
        "dora_indicators": snapshot.dora_indicators,
    }


def merge_entry_enrichment(
    entry: dict[str, Any],
    snapshot: BoardSnapshot | None,
) -> dict[str, Any]:
    """Return entry with missing river/dora fields filled from snapshot."""
    if snapshot is None:
        return entry
    merged = dict(entry)
    if not merged.get("player_discards"):
        merged["player_discards"] = list(snapshot.player_discards)
    if not merged.get("visible_discards"):
        merged["visible_discards"] = {
            k: list(v) for k, v in snapshot.visible_discards.items()
        }
    if not merged.get("dora_indicators"):
        merged["dora_indicators"] = list(snapshot.dora_indicators)
    return merged
