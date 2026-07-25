"""Deterministic feature extraction — never via the LLM."""

from __future__ import annotations

from collections import Counter

from mahjong.shanten import Shanten

from shanten_sensei.schema import (
    DerivedFeatures,
    HandStatuses,
    UkeireInfo,
    WaitShape,
)
from shanten_sensei.tiles import (
    deaka,
    normalize_tile,
    tile_from_34,
    tile_to_34,
    tiles_to_34_array,
)

_SHANTEN = Shanten()

# Dora indicator → next tile in suit / next honor
_DORA_NEXT = {
    **{f"{n}m": f"{n % 9 + 1}m" for n in range(1, 10)},
    **{f"{n}p": f"{n % 9 + 1}p" for n in range(1, 10)},
    **{f"{n}s": f"{n % 9 + 1}s" for n in range(1, 10)},
    "E": "S",
    "S": "W",
    "W": "N",
    "N": "E",
    "P": "F",
    "F": "C",
    "C": "P",
}


def calculate_shanten(hand: list[str], num_melds: int = 0) -> int:
    """Shanten for a 13- or 14-tile closed hand (+ optional open meld count)."""
    counts = tiles_to_34_array(hand)
    return _shanten_with_melds(counts, num_melds)


def hand_without_discard(hand: list[str], discard: str) -> list[str]:
    """Return hand with one copy of discard removed (aka-aware)."""
    target = normalize_tile(discard)
    out = list(hand)
    # Prefer exact aka match, then deaka equivalent
    for i, t in enumerate(out):
        if normalize_tile(t) == target:
            out.pop(i)
            return out
    target_base = deaka(target)
    for i, t in enumerate(out):
        if deaka(normalize_tile(t)) == target_base:
            out.pop(i)
            return out
    raise ValueError(f"discard {discard!r} not in hand {hand}")


def collect_visible_tiles(
    *,
    visible_discards: dict[str, list[str]] | None = None,
    discards: list[str] | None = None,
    calls: list[dict] | None = None,
    dora_indicators: list[str] | None = None,
) -> list[str]:
    """Tiles already visible outside the closed hand (rivers, calls, dora indicators)."""
    out: list[str] = []
    rivers: list[str] = []
    if visible_discards:
        for river in visible_discards.values():
            rivers.extend(river)
    if rivers:
        out.extend(rivers)
    elif discards:
        out.extend(discards)
    out.extend(_tiles_from_calls(calls or []))
    out.extend(dora_indicators or [])
    return out


def calculate_ukeire(
    hand: list[str],
    num_melds: int = 0,
    *,
    after_discard: str | None = None,
    visible_tiles: list[str] | None = None,
) -> UkeireInfo:
    """Tiles that strictly reduce shanten when drawn; count remaining copies (≤4).

    For a 14-tile hand, pass ``after_discard`` (usually Mortal's pick) so ukeire
    is computed on the resulting 13-tile shape.

    When ``visible_tiles`` is provided (rivers / calls / dora indicators), remaining
    copies subtract those as well as tiles already in the working hand.
    """
    working_tiles = (
        hand_without_discard(hand, after_discard) if after_discard else list(hand)
    )
    working = tiles_to_34_array(working_tiles)
    visible_outside = [0] * 34
    for tile in visible_tiles or []:
        try:
            visible_outside[tile_to_34(tile)] += 1
        except ValueError:
            continue
    current = _shanten_with_melds(working, num_melds)
    improving: list[str] = []
    remaining_by_tile: dict[str, int] = {}
    remaining = 0
    for idx in range(34):
        if working[idx] >= 4:
            continue
        working[idx] += 1
        new_sh = _shanten_with_melds(working, num_melds)
        working[idx] -= 1
        if new_sh < current:
            tile = tile_from_34(idx)
            left = max(0, 4 - working[idx] - visible_outside[idx])
            improving.append(tile)
            remaining_by_tile[tile] = left
            remaining += left
    return UkeireInfo(
        count=remaining,
        tiles=improving,
        remaining_by_tile=remaining_by_tile,
    )


def wait_tiles_if_tenpai(hand: list[str], num_melds: int = 0) -> list[str]:
    counts = tiles_to_34_array(hand)
    if _shanten_with_melds(counts, num_melds) != 0:
        return []
    waits: list[str] = []
    for idx in range(34):
        if counts[idx] >= 4:
            continue
        counts[idx] += 1
        if _shanten_with_melds(counts, num_melds) == -1:
            waits.append(tile_from_34(idx))
        counts[idx] -= 1
    return waits


def classify_wait_shape(waits: list[str]) -> WaitShape | None:
    if not waits:
        return None
    if len(waits) == 1:
        return "tanki"
    idxs = sorted(tile_to_34(w) for w in waits)
    if len(idxs) == 2:
        a, b = idxs
        if a // 9 == b // 9 and a < 27:
            diff = b - a
            if diff == 3:
                return "ryanmen"
            if diff == 2:
                return "kanchan"
            if diff == 1:
                # could be shanpon of adjacents — treat adjacent honors/suits pair as shanpon
                return "penchan" if {a % 9, b % 9} & {0, 8} else "shanpon"
        return "shanpon"
    return "complex"


def dora_from_indicators(indicators: list[str]) -> list[str]:
    out: list[str] = []
    for ind in indicators:
        key = deaka(normalize_tile(ind))
        out.append(_DORA_NEXT.get(key, key))
    return out


def dora_in_hand(hand: list[str], indicators: list[str]) -> list[str]:
    dora_tiles = set(dora_from_indicators(indicators))
    found: list[str] = []
    for tile in hand:
        base = deaka(normalize_tile(tile))
        # aka 5 is always a dora
        norm = normalize_tile(tile)
        if norm in ("5mr", "5pr", "5sr") or base in dora_tiles:
            found.append(norm)
    return found


def is_furiten(waits: list[str], discards: list[str]) -> bool:
    wait_set = {deaka(normalize_tile(w)) for w in waits}
    discard_set = {deaka(normalize_tile(d)) for d in discards}
    return bool(wait_set & discard_set)


def basic_danger_tags(
    candidate_tiles: list[str],
    visible_discards: dict[str, list[str]] | None = None,
    genbutsu_tiles: list[str] | None = None,
) -> dict[str, str]:
    """Minimal danger labels for verbalization. Prefer caller-supplied genbutsu."""
    tags: dict[str, str] = {}
    gen = {deaka(normalize_tile(t)) for t in (genbutsu_tiles or [])}
    if visible_discards:
        for disc in visible_discards.values():
            gen.update(deaka(normalize_tile(t)) for t in disc)

    for tile in candidate_tiles:
        base = deaka(normalize_tile(tile))
        if base in gen:
            tags[base] = "genbutsu"
    return tags


# Deterministic shape/yaku tags — verbalize only; never claim Mortal "aims for" these.
SHAPE_GOAL_TAGS = frozenset(
    {"tanyao", "yakuhai", "honitsu", "chinitsu", "toitoi", "chiitoi"}
)
_DRAGONS = frozenset({"P", "F", "C"})
_WINDS = frozenset({"E", "S", "W", "N"})


def _is_terminal_or_honor(tile: str) -> bool:
    base = deaka(normalize_tile(tile))
    if base in _DRAGONS or base in _WINDS:
        return True
    return len(base) >= 2 and base[0] in "19" and base[1] in "mps"


def _suit_of(tile: str) -> str | None:
    base = deaka(normalize_tile(tile))
    if len(base) >= 2 and base[0].isdigit() and base[1] in "mps":
        return base[1]
    return None


def _tiles_from_calls(calls: list[dict]) -> list[str]:
    """Best-effort tile extraction from mjai / reviewer fuuro dicts."""
    out: list[str] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        for key in ("pai", "tiles"):
            val = call.get(key)
            if isinstance(val, str):
                out.append(val)
            elif isinstance(val, list):
                out.extend(t for t in val if isinstance(t, str))
        consumed = call.get("consumed")
        if isinstance(consumed, list):
            out.extend(t for t in consumed if isinstance(t, str))
    return out


def infer_shape_goals(
    hand: list[str],
    *,
    calls: list[dict] | None = None,
    context: dict | None = None,
    max_goals: int = 3,
) -> list[str]:
    """Conservative mid-game yaku/shape tags from the closed hand (+ calls).

    Prefer under-tagging. Tags describe hand shape, not Mortal's internal plan.
    """
    calls = calls or []
    context = context or {}
    all_tiles = list(hand) + _tiles_from_calls(calls)
    if not all_tiles:
        return []

    counts = tiles_to_34_array(hand)
    menzen = len(calls) == 0
    goals: list[str] = []

    # Flush family
    suit_counts = {"m": 0, "p": 0, "s": 0}
    honor_count = 0
    for tile in all_tiles:
        suit = _suit_of(tile)
        if suit:
            suit_counts[suit] += 1
        else:
            honor_count += 1
    dominant_suit = max(suit_counts, key=suit_counts.get)  # type: ignore[arg-type]
    dominant_n = suit_counts[dominant_suit]
    other_suit_n = sum(n for s, n in suit_counts.items() if s != dominant_suit)
    if other_suit_n == 0 and honor_count == 0 and dominant_n >= 11:
        goals.append("chinitsu")
    elif other_suit_n == 0 and dominant_n >= 11:
        goals.append("honitsu")

    # Tanyao: no terminals/honors in hand or calls
    if all_tiles and not any(_is_terminal_or_honor(t) for t in all_tiles):
        goals.append("tanyao")

    # Yakuhai: pair/triplet of dragon, or seat/round wind when context provides them
    yakuhai_tiles = set(_DRAGONS)
    for key in ("bakaze", "jikaze", "round_wind", "seat_wind"):
        val = context.get(key)
        if isinstance(val, str):
            wind = deaka(normalize_tile(val))
            if wind in _WINDS:
                yakuhai_tiles.add(wind)
    for tile in yakuhai_tiles:
        if counts[tile_to_34(tile)] >= 2:
            goals.append("yakuhai")
            break

    # Chiitoi: only closed; strictly better than regular (under-tag)
    if menzen and sum(counts) in (13, 14):
        chiitoi_sh = _SHANTEN.calculate_shanten_for_chiitoitsu_hand(list(counts))
        regular_sh = _SHANTEN.calculate_shanten_for_regular_hand(list(counts))
        if chiitoi_sh < regular_sh and chiitoi_sh <= 3:
            goals.append("chiitoi")

    # Toitoi: strong pair/triplet density (conservative)
    pairish = sum(1 for c in counts if c >= 2)
    triplets = sum(1 for c in counts if c >= 3)
    if (triplets >= 2 and pairish >= 4) or (pairish >= 5 and triplets >= 1):
        goals.append("toitoi")

    # Prefer chinitsu over honitsu; cap length
    if "chinitsu" in goals and "honitsu" in goals:
        goals = [g for g in goals if g != "honitsu"]
    # Stable priority: flush → tanyao → yakuhai → chiitoi → toitoi
    priority = ["chinitsu", "honitsu", "tanyao", "yakuhai", "chiitoi", "toitoi"]
    ordered = [g for g in priority if g in goals]
    return ordered[:max_goals]


def extract_features(
    hand: list[str],
    *,
    calls: list[dict] | None = None,
    discards: list[str] | None = None,
    dora_indicators: list[str] | None = None,
    riichi: bool = False,
    ippatsu: bool = False,
    temporary_furiten: bool = False,
    at_furiten_hint: bool | None = None,
    candidate_tiles: list[str] | None = None,
    visible_discards: dict[str, list[str]] | None = None,
    genbutsu_tiles: list[str] | None = None,
    context: dict | None = None,
    ukeire_after_discard: str | None = None,
    ukeire_alt_after_discard: str | None = None,
) -> DerivedFeatures:
    calls = calls or []
    discards = discards or []
    dora_indicators = dora_indicators or []
    num_melds = len(calls)
    menzen = num_melds == 0
    hand_total = sum(tiles_to_34_array(hand)) + num_melds * 3
    is_14 = hand_total % 3 == 2

    visible_tiles = collect_visible_tiles(
        visible_discards=visible_discards,
        discards=discards,
        calls=calls,
        dora_indicators=dora_indicators,
    )

    shanten = calculate_shanten(hand, num_melds)
    # Prefer ukeire / waits on the post-discard shape when we have 14 tiles.
    shape_hand = hand
    mortal_discard = ukeire_after_discard if is_14 else None
    if mortal_discard is not None:
        shape_hand = hand_without_discard(hand, mortal_discard)
    shape_shanten = calculate_shanten(shape_hand, num_melds)
    ukeire = calculate_ukeire(
        hand,
        num_melds,
        after_discard=mortal_discard,
        visible_tiles=visible_tiles,
    )
    ukeire_alt: UkeireInfo | None = None
    alt_discard = ukeire_alt_after_discard
    if alt_discard is not None and is_14:
        same_cut = (
            mortal_discard is not None
            and deaka(normalize_tile(alt_discard))
            == deaka(normalize_tile(mortal_discard))
        )
        if not same_cut:
            try:
                ukeire_alt = calculate_ukeire(
                    hand,
                    num_melds,
                    after_discard=alt_discard,
                    visible_tiles=visible_tiles,
                )
            except ValueError:
                ukeire_alt = None
    waits = (
        wait_tiles_if_tenpai(shape_hand, num_melds) if shape_shanten == 0 else []
    )
    wait_shape = classify_wait_shape(waits)
    furiten = (
        bool(at_furiten_hint)
        if at_furiten_hint is not None
        else is_furiten(waits, discards)
    )

    statuses = HandStatuses(
        menzen=menzen,
        tenpai=shape_shanten == 0,
        shanten=shanten if ukeire_after_discard is None else shape_shanten,
        furiten=furiten,
        temporary_furiten=temporary_furiten,
        riichi=riichi,
        ippatsu=ippatsu,
        wait_shape=wait_shape,
        dora_in_hand=dora_in_hand(hand, dora_indicators),
        visible_dora=list(dora_indicators),
    )

    danger = basic_danger_tags(
        candidate_tiles or [],
        visible_discards=visible_discards,
        genbutsu_tiles=genbutsu_tiles,
    )

    shape_goals = infer_shape_goals(
        shape_hand,
        calls=calls,
        context=context,
    )

    return DerivedFeatures(
        shanten=shanten,
        ukeire=ukeire,
        ukeire_alt=ukeire_alt,
        statuses=statuses,
        danger=danger,
        context=context or {},
        shape_goals=shape_goals,
    )


def _shanten_with_melds(hand34: list[int], num_melds: int) -> int:
    """Pad open melds with ghost honor triplets so mahjong sees 13/14 tiles."""
    total_with_melds = sum(hand34) + num_melds * 3
    if total_with_melds not in (13, 14):
        # Malformed for standard calc — return a bad sentinel
        return 8
    if num_melds == 0:
        return _SHANTEN.calculate_shanten(list(hand34))

    padded = list(hand34)
    ghost_slots = [27, 28, 29, 30, 31, 32, 33]
    placed = 0
    for h in ghost_slots:
        if placed >= num_melds:
            break
        if padded[h] == 0:
            padded[h] = 3
            placed += 1
    if placed < num_melds:
        return 8
    return _SHANTEN.calculate_shanten(padded)


def visible_tile_counts(tiles: list[str]) -> Counter[str]:
    return Counter(deaka(normalize_tile(t)) for t in tiles)
