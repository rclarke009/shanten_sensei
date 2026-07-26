"""Deterministic feature extraction — never via the LLM."""

from __future__ import annotations

from collections import Counter

from mahjong.shanten import Shanten

from shanten_sensei.schema import (
    CallTradeoff,
    DerivedFeatures,
    GameState,
    HandShapeNote,
    HandStatuses,
    ScoreDiff,
    ScoreSituation,
    UkeireInfo,
    WaitShape,
)
from shanten_sensei.tiles import (
    action_tile_arg,
    deaka,
    is_call_action,
    normalize_tile,
    parse_action_kind,
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


def simulate_shanten_after_call(
    hand: list[str],
    call_action: str,
    *,
    num_melds: int = 0,
    consumed: list[str] | None = None,
    call_tile: str | None = None,
) -> int | None:
    """Shanten after pon/chi/kan when consumables are known; else None."""
    kind = parse_action_kind(call_action)
    if kind not in ("pon", "chi", "kan"):
        return None

    working = list(hand)
    tile = action_tile_arg(call_action) or (
        normalize_tile(call_tile) if call_tile else None
    )

    try:
        if kind == "pon":
            if not tile:
                return None
            to_remove = (
                [normalize_tile(t) for t in consumed[:2]]
                if consumed and len(consumed) >= 2
                else [tile, tile]
            )
            for t in to_remove:
                working = hand_without_discard(working, t)
            return calculate_shanten(working, num_melds + 1)

        if kind == "chi":
            if not consumed or len(consumed) < 2:
                return None
            for t in consumed[:2]:
                working = hand_without_discard(working, t)
            return calculate_shanten(working, num_melds + 1)

        # kan: remove 3 from hand (daiminkan) when we know the tile
        if not tile:
            return None
        to_remove = (
            [normalize_tile(t) for t in consumed[:3]]
            if consumed and len(consumed) >= 3
            else [tile, tile, tile]
        )
        for t in to_remove:
            working = hand_without_discard(working, t)
        return calculate_shanten(working, num_melds + 1)
    except ValueError:
        return None


def build_call_tradeoff(
    hand: list[str],
    *,
    calls: list[dict] | None = None,
    stay_closed_shanten: int,
    stay_closed_ukeire: int,
    call_action: str | None,
    consumed: list[str] | None = None,
    call_tile: str | None = None,
) -> CallTradeoff | None:
    """Build open-vs-closed tradeoff when a call action is in play."""
    if not call_action or not is_call_action(call_action):
        return None
    num_melds = len(calls or [])
    menzen = num_melds == 0
    open_shanten = simulate_shanten_after_call(
        hand,
        call_action,
        num_melds=num_melds,
        consumed=consumed,
        call_tile=call_tile,
    )
    return CallTradeoff(
        call_action=call_action,
        stay_closed_shanten=stay_closed_shanten,
        stay_closed_ukeire=stay_closed_ukeire,
        open_shanten=open_shanten,
        opens_hand=menzen,
    )


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


_DANGER_RANK = {"genbutsu": 3, "one-chance": 2, "suji": 1}


def _number_suit(tile: str) -> tuple[int, str] | None:
    base = deaka(normalize_tile(tile))
    if len(base) >= 2 and base[0].isdigit() and base[1] in "mps":
        return int(base[0]), base[1]
    return None


def _suji_mates(tile: str) -> list[str]:
    """Tiles that form classic 3-interval suji with a number discard."""
    parsed = _number_suit(tile)
    if parsed is None:
        return []
    n, suit = parsed
    mates: list[str] = []
    for m in (n - 3, n + 3):
        if 1 <= m <= 9:
            mates.append(f"{m}{suit}")
    return mates


def basic_danger_tags(
    candidate_tiles: list[str],
    visible_discards: dict[str, list[str]] | None = None,
    genbutsu_tiles: list[str] | None = None,
    visible_tiles: list[str] | None = None,
) -> dict[str, str]:
    """Danger labels for verbalization: genbutsu > one-chance > suji."""
    tags: dict[str, str] = {}
    gen = {deaka(normalize_tile(t)) for t in (genbutsu_tiles or [])}
    rivers: list[str] = []
    if visible_discards:
        for disc in visible_discards.values():
            rivers.extend(disc)
            gen.update(deaka(normalize_tile(t)) for t in disc)

    suji: set[str] = set()
    for disc in rivers:
        suji.update(_suji_mates(disc))

    visible = visible_tiles
    if visible is None:
        visible = collect_visible_tiles(visible_discards=visible_discards)
    counts = Counter(deaka(normalize_tile(t)) for t in visible)
    one_chance: set[str] = set()
    for tile, n in counts.items():
        if n < 3:
            continue
        parsed = _number_suit(tile)
        if parsed is None:
            continue
        mid, suit = parsed
        for adj in (mid - 1, mid + 1):
            if 1 <= adj <= 9:
                one_chance.add(f"{adj}{suit}")

    for tile in candidate_tiles:
        base = deaka(normalize_tile(tile))
        if base in gen:
            tags[base] = "genbutsu"
        elif base in one_chance:
            tags[base] = "one-chance"
        elif base in suji:
            tags[base] = "suji"
    return tags


def danger_rank(tag: str | None) -> int:
    """Higher = safer teaching tag (genbutsu > one-chance > suji)."""
    if not tag:
        return 0
    return _DANGER_RANK.get(tag, 0)


def build_score_situation(
    *,
    scores: list[int] | None = None,
    riichi_flags: list[bool] | None = None,
    tiles_left: int | None = None,
    kyoku: int | None = None,
) -> ScoreSituation | None:
    """Point-situation facts from scores / opponent riichi / late wall."""
    flags = list(riichi_flags or [])
    riichi_opponents = sum(1 for f in flags[1:] if f) if flags else 0

    score_diff: ScoreDiff | None = None
    if scores and len(scores) >= 2:
        player = scores[0]
        best_opp = max(scores[1:])
        delta = player - best_opp
        if abs(delta) <= 3000:
            score_diff = "even"
        elif delta > 0:
            score_diff = "leading"
        else:
            score_diff = "trailing"

    late_game = (tiles_left is not None and tiles_left <= 30) or (
        kyoku is not None and kyoku >= 7
    )

    if riichi_opponents == 0 and score_diff is None and not late_game:
        return None
    return ScoreSituation(
        riichi_opponents=riichi_opponents,
        score_diff=score_diff,
        late_game=late_game,
    )


def attach_score_situation(features: DerivedFeatures, state: GameState) -> None:
    """Fill features.score_situation from game_state fields."""
    features.score_situation = build_score_situation(
        scores=state.scores,
        riichi_flags=state.riichi_flags,
        tiles_left=state.tiles_left,
        kyoku=state.kyoku,
    )


# Deterministic shape/yaku tags — verbalize only; never claim Mortal "aims for" these.
SHAPE_GOAL_TAGS = frozenset(
    {
        "tanyao",
        "yakuhai",
        "honitsu",
        "chinitsu",
        "toitoi",
        "chiitoi",
        "pinfu",
        "ittsu",
    }
)
_DRAGONS = frozenset({"P", "F", "C"})
_WINDS = frozenset({"E", "S", "W", "N"})
_ITTSU_BLOCKS = ((1, 2, 3), (4, 5, 6), (7, 8, 9))


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


def _is_floating_terminal(counts: list[int], tile: str) -> bool:
    base = deaka(normalize_tile(tile))
    if not (len(base) >= 2 and base[0] in "19" and base[1] in "mps"):
        return False
    idx = tile_to_34(base)
    if counts[idx] != 1:
        return False
    suit = base[1]
    neighbor = f"2{suit}" if base[0] == "1" else f"8{suit}"
    return counts[tile_to_34(neighbor)] == 0


def _is_floating_honor(counts: list[int], tile: str) -> bool:
    base = deaka(normalize_tile(tile))
    if base not in _DRAGONS and base not in _WINDS:
        return False
    return counts[tile_to_34(base)] == 1


def _is_isolated_kanchan_cut(counts: list[int], tile: str) -> bool:
    """Cut is one end of an isolated kanchan taatsu (N + N+2, missing middle)."""
    base = deaka(normalize_tile(tile))
    if len(base) < 2 or not base[0].isdigit() or base[1] not in "mps":
        return False
    n = int(base[0])
    suit = base[1]
    if counts[tile_to_34(base)] != 1:
        return False
    for other_n, mid_n in ((n + 2, n + 1), (n - 2, n - 1)):
        if other_n < 1 or other_n > 9:
            continue
        other = f"{other_n}{suit}"
        mid = f"{mid_n}{suit}"
        if counts[tile_to_34(other)] == 1 and counts[tile_to_34(mid)] == 0:
            return True
    return False


def _is_isolated_penchan_cut(counts: list[int], tile: str) -> bool:
    """Cut is from a lone 12 / 89 edge fragment."""
    base = deaka(normalize_tile(tile))
    if len(base) < 2 or not base[0].isdigit() or base[1] not in "mps":
        return False
    n = int(base[0])
    suit = base[1]
    if counts[tile_to_34(base)] != 1:
        return False
    if n in (1, 2):
        has_1 = counts[tile_to_34(f"1{suit}")] >= 1
        has_2 = counts[tile_to_34(f"2{suit}")] >= 1
        has_3 = counts[tile_to_34(f"3{suit}")] >= 1
        return has_1 and has_2 and not has_3 and n in (1, 2)
    if n in (8, 9):
        has_7 = counts[tile_to_34(f"7{suit}")] >= 1
        has_8 = counts[tile_to_34(f"8{suit}")] >= 1
        has_9 = counts[tile_to_34(f"9{suit}")] >= 1
        return has_8 and has_9 and not has_7 and n in (8, 9)
    return False


def _value_tiles_from_context(context: dict | None) -> set[str]:
    """Dragons + seat/round wind when context provides them."""
    yakuhai_tiles = set(_DRAGONS)
    context = context or {}
    for key in ("bakaze", "jikaze", "round_wind", "seat_wind"):
        val = context.get(key)
        if isinstance(val, str):
            try:
                wind = deaka(normalize_tile(val))
            except ValueError:
                continue
            if wind in _WINDS:
                yakuhai_tiles.add(wind)
    return yakuhai_tiles


def _ittsu_blocks_present(counts: list[int], suit: str) -> int:
    """How many of the 123 / 456 / 789 blocks are fully represented in one suit."""
    present = 0
    for ranks in _ITTSU_BLOCKS:
        # Under-tag: require all three ranks present (not a loose stretch).
        if all(counts[tile_to_34(f"{n}{suit}")] >= 1 for n in ranks):
            present += 1
    return present


def _looks_like_ittsu(all_tiles: list[str]) -> bool:
    """True when one suit clearly covers two of the three 1–9 stretch blocks."""
    if not all_tiles:
        return False
    counts = tiles_to_34_array(all_tiles)
    for suit in "mps":
        if _ittsu_blocks_present(counts, suit) >= 2:
            return True
    return False


def _open_ended_sequence_density(counts: list[int]) -> tuple[int, int]:
    """Return (complete_sequences, ryanmen_taatsu) across suits (greedy, conservative)."""
    complete = 0
    ryanmen = 0
    work = list(counts)
    for suit_i, _suit in enumerate("mps"):
        base = suit_i * 9
        # Prefer complete sequences first so taatsu aren't double-counted away.
        for n in range(7):
            while (
                work[base + n] >= 1
                and work[base + n + 1] >= 1
                and work[base + n + 2] >= 1
            ):
                work[base + n] -= 1
                work[base + n + 1] -= 1
                work[base + n + 2] -= 1
                complete += 1
        # Open-ended taatsu: 23–78 adjacent pairs (not 12 / 89 edges).
        for n in range(1, 8):
            while work[base + n] >= 1 and work[base + n + 1] >= 1:
                work[base + n] -= 1
                work[base + n + 1] -= 1
                ryanmen += 1
    return complete, ryanmen


def _looks_like_pinfu(
    hand: list[str],
    *,
    menzen: bool,
    context: dict | None,
) -> bool:
    """Conservative closed-hand pinfu shape: sequences, no value pairs."""
    if not menzen or not hand:
        return False
    counts = tiles_to_34_array(hand)
    # Value pairs / triplets → yakuhai path, not pinfu.
    for tile in _value_tiles_from_context(context):
        if counts[tile_to_34(tile)] >= 2:
            return False
    # Dragons in hand (even singleton) rarely mean pinfu aiming.
    for tile in _DRAGONS:
        if counts[tile_to_34(tile)] >= 1:
            return False
    triplets = sum(1 for c in counts if c >= 3)
    if triplets >= 2:
        return False
    pairish = sum(1 for c in counts if c >= 2)
    if pairish >= 5:
        return False
    complete, ryanmen = _open_ended_sequence_density(counts)
    # Two+ sequences is enough; otherwise need open-ended taatsu density.
    if complete >= 2:
        return True
    if complete >= 1 and ryanmen >= 2:
        return True
    if ryanmen >= 3:
        return True
    return False


def infer_hand_shape_notes(
    hand: list[str],
    *,
    cut_tile: str | None,
    shape_goals: list[str] | None = None,
    shanten: int | None = None,
    max_notes: int = 2,
) -> list[HandShapeNote]:
    """Conservative mid-hand tags for why Mortal's cut is dead wood.

    Prefer under-tagging. Only fires before tenpai when a cut tile is known.
    """
    if not cut_tile:
        return []
    if shanten is not None and shanten <= 0:
        return []

    try:
        base = deaka(normalize_tile(cut_tile))
    except ValueError:
        return []

    counts = tiles_to_34_array(hand)
    try:
        if counts[tile_to_34(base)] < 1:
            return []
    except ValueError:
        return []

    goals = list(shape_goals or [])
    notes: list[HandShapeNote] = []

    if _is_isolated_kanchan_cut(counts, base):
        notes.append(HandShapeNote(kind="isolated_kanchan", tile=base))
    elif _is_isolated_penchan_cut(counts, base):
        notes.append(HandShapeNote(kind="isolated_penchan", tile=base))
    elif _is_floating_terminal(counts, base):
        if goals:
            notes.append(HandShapeNote(kind="floating_terminal", tile=base))
        else:
            notes.append(HandShapeNote(kind="dead_end", tile=base))
    elif _is_floating_honor(counts, base):
        if goals:
            notes.append(HandShapeNote(kind="floating_honor", tile=base))
        else:
            notes.append(HandShapeNote(kind="dead_end", tile=base))

    return notes[:max_notes]


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
    for tile in _value_tiles_from_context(context):
        if counts[tile_to_34(tile)] >= 2:
            goals.append("yakuhai")
            break

    # Ittsu: two of three 1–9 blocks in one suit (closed + calls)
    if _looks_like_ittsu(all_tiles):
        goals.append("ittsu")

    # Pinfu: closed, sequence-dense, no value pairs (under-tag)
    if _looks_like_pinfu(hand, menzen=menzen, context=context):
        goals.append("pinfu")

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
    # Stable priority: flush → ittsu → tanyao → pinfu → yakuhai → chiitoi → toitoi
    priority = [
        "chinitsu",
        "honitsu",
        "ittsu",
        "tanyao",
        "pinfu",
        "yakuhai",
        "chiitoi",
        "toitoi",
    ]
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
        visible_tiles=visible_tiles,
    )

    shape_goals = infer_shape_goals(
        shape_hand,
        calls=calls,
        context=context,
    )

    # Notes describe the cut tile in the pre-discard hand (14-tile when known).
    note_hand = hand if is_14 and mortal_discard is not None else shape_hand
    hand_shape_notes = infer_hand_shape_notes(
        note_hand,
        cut_tile=mortal_discard or ukeire_after_discard,
        shape_goals=shape_goals,
        shanten=statuses.shanten,
    )

    return DerivedFeatures(
        shanten=shanten,
        ukeire=ukeire,
        ukeire_alt=ukeire_alt,
        statuses=statuses,
        danger=danger,
        context=context or {},
        shape_goals=shape_goals,
        hand_shape_notes=hand_shape_notes,
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
