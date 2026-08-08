"""Grounding validators and substance scoring for Why? summaries."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from shanten_sensei.live import (
    is_call_decision_turn,
    is_hora_decision_turn,
    is_riichi_decision_turn,
    next_best_action,
)
from shanten_sensei.schema import Explanation, TurnExplainInput
from shanten_sensei.tiles import (
    action_tile_arg,
    deaka,
    human_tile_label,
    is_riichi_decision_action,
    normalize_tile,
    parse_action_kind,
)

SUMMARY_WORD_LIMIT = 90

_HONOR_ALIASES: dict[str, tuple[str, ...]] = {
    "e": ("east",),
    "s": ("south",),
    "w": ("west",),
    "n": ("north",),
    "p": ("haku",),
    "f": ("hatsu",),
    "c": ("chun",),
}
_HONOR_ORDER = ("E", "S", "W", "N", "P", "F", "C")
_DRAGONS = frozenset({"P", "F", "C"})
_WINDS = frozenset({"E", "S", "W", "N"})


def _action_tile_token(action: str) -> str | None:
    tile = action_tile_arg(action)
    return tile.lower() if tile else None


def _action_tile_token_raw(action: str | None) -> str | None:
    if not action:
        return None
    return action_tile_arg(action)


def _danger_key(tile: str | None) -> str | None:
    if not tile:
        return None
    return deaka(normalize_tile(tile))


def _yakuhai_value_tiles(context: dict | None) -> set[str]:
    tiles = set(_DRAGONS)
    for key in ("bakaze", "jikaze", "round_wind", "seat_wind"):
        val = (context or {}).get(key)
        if isinstance(val, str):
            wind = deaka(normalize_tile(val))
            if wind in _WINDS:
                tiles.add(wind)
    return tiles


def _hand_tile_counts(hand: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for tile in hand:
        counts[deaka(normalize_tile(tile))] += 1
    return counts


def _coaching_shape_goals(turn: TurnExplainInput) -> list[str]:
    from shanten_sensei.explain import coaching_shape_goals
    return coaching_shape_goals(turn)


def _wall_note_kind(turn: TurnExplainInput) -> str | None:
    from shanten_sensei.explain import _wall_note_detail
    kind, _ = _wall_note_detail(turn)
    return kind


def _contrast_alt_action(turn: TurnExplainInput) -> str | None:
    if turn.diverge and turn.player_action != turn.mortal_best:
        return turn.player_action
    return next_best_action(turn)

# Tautological efficiency / Mortal-% claims with no hand-fact anchors.
_THIN_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bmore efficient\b",
        r"\bhigher efficiency\b",
        r"\befficiency is worse\b",
        r"\bhigher (?:probability|chance)\b",
        r"\bkeeps? (?:your )?(?:hand )?(?:flexible|options open)\b",
        r"\bimproving your hand\b",
        r"\bchance of (?:improving|helping)\b",
        r"\d+(?:\.\d+)?%\b",
    )
)

# LLM inverted polarity: cut-shape notes are reasons to discard, not keep.
# Do not match wait phrasing like "That keeps a ryanmen wait".
_CUT_NOTE_POLARITY_PATTERN = re.compile(
    r"\b(?:maintain(?:s|ing)?|keep(?:s|ing)?|preserve(?:s|ing)?)\s+"
    r"(?:a\s+|an\s+)?"
    r"(?:dead[-\s]?end|floating|isolated|closed\s+middle|kanchan|penchan|edge)\b",
    re.IGNORECASE,
)

# Figurative "hand open" for ukeire — conflates with called (furo) hands.
# Do not match call copy ("open the hand") or wait glosses ("two-sided open").
_FIGURATIVE_HAND_OPEN_PATTERN = re.compile(
    r"(?:\bkeep(?:s|ing)? (?:your )?hand open\b|\bhand open with\b)",
    re.IGNORECASE,
)

# Throw X then "keep it" / "better to keep" — pronoun or vague keep of the cut.
_PINNED_CUT_KEEP_IT_PATTERN = re.compile(
    r"\b(?:(?:still\s+)?better\s+to\s+keep|keep(?:s|ing)?\s+it(?:\s+for\s+now)?)\b",
    re.IGNORECASE,
)


# Yaku / shape words the LLM might invent — only allowed if in shape_goals
# (plus "dora" when dora_in_hand is present).
_YAKU_MENTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tanyao", (r"\btanyao\b", r"\ball\s+simples\b")),
    ("yakuhai", (r"\byakuhai\b", r"\bvalue\s+honor")),
    ("honitsu", (r"\bhonitsu\b", r"\bhalf\s+flush\b")),
    ("chinitsu", (r"\bchinitsu\b", r"\bfull\s+flush\b")),
    ("toitoi", (r"\btoitoi\b", r"\ball\s+triplets\b", r"\ball\s+pons\b")),
    ("chiitoi", (r"\bchiitoitsu\b", r"\bchiitoi\b", r"\bseven\s+pairs\b")),
    ("ittsu", (r"\bittsu\b", r"\biitsu\b", r"\bpure\s+straight\b")),
    ("pinfu", (r"\bpinfu\b",)),
    ("iipeiko", (r"\biipeiko\b", r"\biipeikou\b")),
    ("sanshoku", (r"\bsanshoku\b",)),
    ("dora", (r"\bdora\b",)),
)

@dataclass(frozen=True)
class SubstanceScore:
    """Offline/runtime substance metric for Why? summaries."""

    thin: bool
    anchors: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _wall_facts_available(turn: TurnExplainInput) -> bool:
    ukeire = turn.features.ukeire
    remaining = ukeire.remaining_by_tile
    if remaining and any(remaining.get(t, 0) <= 1 for t in ukeire.tiles):
        return True
    alt = turn.features.ukeire_alt
    if alt is not None and turn.features.ukeire.count - alt.count >= 1:
        return True
    return False


def _cut_shape_notes_for_turn(turn: TurnExplainInput) -> list:
    """Mortal-cut notes plus alternate-cut shape note when contrasted."""
    from shanten_sensei.features import alternate_cut_shape_note

    notes = list(turn.features.hand_shape_notes)
    alt_action = _contrast_alt_action(turn)
    if alt_action and alt_action != turn.mortal_best:
        alt_raw = _action_tile_token_raw(alt_action)
        if alt_raw:
            alt_note = alternate_cut_shape_note(
                turn.game_state.hand,
                cut_tile=alt_raw,
                shape_goals=turn.features.shape_goals,
                shanten=turn.features.shanten,
            )
            if alt_note is not None:
                notes.append(alt_note)
    return notes


def _turn_has_usable_anchors(turn: TurnExplainInput) -> bool:
    """True when the turn has at least one citeable hand fact."""
    if turn.features.shanten is not None:
        return True
    if turn.features.statuses.wait_shape:
        return True
    if turn.features.shape_goals:
        return True
    if turn.features.hand_shape_notes:
        return True
    if turn.features.statuses.dora_in_hand:
        return True
    if turn.features.call_tradeoff is not None:
        return True
    if turn.features.danger:
        return True
    if turn.features.score_situation is not None:
        return True
    if _wall_facts_available(turn):
        return True
    return False


def _feature_anchors_in_summary(turn: TurnExplainInput, summary_l: str) -> list[str]:
    """Which citeable features the summary actually mentions."""
    anchors: list[str] = []

    if re.search(r"\b\d+-shanten\b", summary_l) or re.search(r"\bshanten\b", summary_l):
        anchors.append("shanten")
    wall_lang = bool(
        re.search(r"\balready out\b", summary_l)
        or re.search(r"\bstill unseen\b", summary_l)
        or re.search(r"\blive acceptances?\b", summary_l)
        or re.search(r"\bimproving tiles\b", summary_l)
        or re.search(r"\b\d+\s*[×x]\b", summary_l)
        or re.search(r"\bfew copies left of tiles you need\b", summary_l)
    )
    if (
        re.search(r"\bacceptances?\b", summary_l)
        or re.search(r"\bukeire\b", summary_l)
        or (
            re.search(r"\bimproving tiles\b", summary_l)
            and re.search(r"\bvs about\b", summary_l)
        )
        or (_wall_facts_available(turn) and wall_lang)
    ):
        anchors.append("ukeire")

    wait_shape = turn.features.statuses.wait_shape
    if wait_shape and wait_shape in summary_l:
        anchors.append("wait_shape")

    for goal in _coaching_shape_goals(turn):
        if re.search(rf"\b{re.escape(goal)}\b", summary_l):
            anchors.append("shape_goal")
            break

    if turn.features.hand_shape_notes and (
        re.search(r"\bfloating\b", summary_l)
        or re.search(r"\bdead-end\b", summary_l)
        or re.search(r"\bdead end\b", summary_l)
        or re.search(r"\bclosed middle\b", summary_l)
        or re.search(r"\bedge\b", summary_l)
        or re.search(r"\bkanchan\b", summary_l)
        or re.search(r"\bpenchan\b", summary_l)
    ):
        anchors.append("hand_shape_note")

    if turn.features.statuses.dora_in_hand and re.search(r"\bdora\b", summary_l):
        anchors.append("dora")

    if turn.features.danger and (
        re.search(r"\bgenbutsu\b", summary_l)
        or re.search(r"\bsuji\b", summary_l)
        or re.search(r"\bone-chance\b", summary_l)
        or re.search(r"\bone chance\b", summary_l)
        or re.search(r"\bcan'?t\s+ron\b", summary_l)
        or (
            re.search(r"\balready\s+discarded\b", summary_l)
            and not re.search(r"\bfuriten\b", summary_l)
        )
    ):
        anchors.append("danger")

    if turn.features.call_tradeoff is not None and (
        re.search(r"\bskip\b", summary_l)
        or re.search(r"\bcall\b", summary_l)
        or re.search(r"\bopen\b", summary_l)
        or re.search(r"\briichi\b", summary_l)
    ):
        anchors.append("call_tradeoff")

    sit = turn.features.score_situation
    if sit is not None and (
        re.search(r"\briichi\b", summary_l)
        or re.search(r"\bleading\b", summary_l)
        or re.search(r"\btrailing\b", summary_l)
        or re.search(r"\bahead\b", summary_l)
        or re.search(r"\bbehind\b", summary_l)
        or re.search(r"\bscores are close\b", summary_l)
        or re.search(r"\bsafety\b", summary_l)
        or re.search(r"\blate\b", summary_l)
        or re.search(r"\bwall\b", summary_l)
        or re.search(r"\bpoints?\b", summary_l)
    ):
        anchors.append("score_situation")

    if is_riichi_decision_turn(turn) and (
        re.search(r"\bdeclare riichi\b", summary_l)
        or re.search(r"\bstay silent\b", summary_l)
    ):
        anchors.append("riichi_decision")

    if is_hora_decision_turn(turn) and re.search(r"\btake the win\b", summary_l):
        anchors.append("hora_decision")

    return anchors


def _bare_contrasted_discard_summary(
    turn: TurnExplainInput, summary_l: str, anchors: list[str]
) -> bool:
    """True when a Throw X, not Y tip lacks any grounded why beyond metrics."""
    if parse_action_kind(turn.mortal_best) != "dahai":
        return False
    alt = next_best_action(turn)
    contrasted = (turn.diverge and turn.player_action != turn.mortal_best) or (
        alt is not None and alt != turn.mortal_best
    )
    if not contrasted:
        return False
    if not re.search(r"\bthrow\b.+\bnot\b", summary_l):
        return False
    rich_markers = (
        "vs about",
        "keeps draws like",
        "dead-end",
        "floating",
        "genbutsu",
        "already discarded",
        "can't ron",
        "cant ron",
        "suji",
        "one-chance",
        "ryanmen",
        "tanki",
        "still unseen",
        "already out",
        "closed middle",
        "penchan",
    )
    if any(marker in summary_l for marker in rich_markers):
        return False
    about_counts = [
        int(x) for x in re.findall(r"(?:about|only about)\s+(\d+)", summary_l)
    ]
    if len(set(about_counts)) >= 2:
        return False
    if any(g in summary_l for g in _coaching_shape_goals(turn)):
        return False
    return not anchors or all(a in ("shanten", "ukeire") for a in anchors)


def score_explanation_substance(turn: TurnExplainInput, summary: str) -> SubstanceScore:
    """Score whether a Why? summary cites hand facts or only tautological efficiency."""
    summary_l = summary.lower()
    anchors = _feature_anchors_in_summary(turn, summary_l)
    has_thin_claim = any(p.search(summary_l) for p in _THIN_CLAIM_PATTERNS)
    bare_contrasted = _bare_contrasted_discard_summary(turn, summary_l, anchors)
    thin = (
        _turn_has_usable_anchors(turn)
        and (
            (not anchors and has_thin_claim)
            or bare_contrasted
        )
    )
    issues = ["thin_efficiency_claim"] if thin else []
    return SubstanceScore(thin=thin, anchors=anchors, issues=issues)

def _genbutsu_tile_codes(turn: TurnExplainInput) -> set[str]:
    return {
        deaka(normalize_tile(t))
        for t, tag in turn.features.danger.items()
        if tag == "genbutsu"
    }


def _mentionable_tile_codes(turn: TurnExplainInput) -> list[str]:
    """Tiles likely named in discard tips (hand + candidates + danger keys)."""
    codes: set[str] = set()
    for tile in turn.game_state.hand:
        try:
            codes.add(deaka(normalize_tile(tile)))
        except ValueError:
            continue
    for action in (
        turn.mortal_best,
        turn.player_action,
        next_best_action(turn),
        *(c.action for c in turn.mortal_output.candidates[:8]),
    ):
        raw = _action_tile_token_raw(action) if action else None
        if raw:
            try:
                codes.add(deaka(normalize_tile(raw)))
            except ValueError:
                continue
    for tile in turn.features.danger:
        try:
            codes.add(deaka(normalize_tile(tile)))
        except ValueError:
            continue
    return sorted(codes)


def _tile_claim_label_pattern(tile: str) -> str:
    """Regex fragment matching human / code forms of a tile in lowered prose."""
    tile = deaka(normalize_tile(tile)).lower()
    if tile in _HONOR_ALIASES:
        # Word-bound each alias so bare "n" does not match inside "chun".
        names = "|".join(
            rf"(?:\b{re.escape(a)}\b)" for a in (tile, *_HONOR_ALIASES[tile])
        )
        return rf"(?:{names})"
    m = re.fullmatch(r"([1-9])([mps])", tile)
    if not m:
        return re.escape(tile)
    num, suit = m.group(1), m.group(2)
    suit_name = {"m": "man", "p": "pin", "s": "sou"}[suit]
    return (
        rf"(?:{re.escape(tile)}|{num}-{suit_name}|{num}\s*{suit_name}|"
        rf"{num}{suit_name})"
    )


def _tile_claimed_as_genbutsu_safe(summary_l: str, tile: str) -> bool:
    """True when prose attributes genbutsu / already-discarded safety to tile."""
    label = _tile_claim_label_pattern(tile)
    if re.search(
        rf"{label}\s+is\s+(?:also\s+)?genbutsu\b",
        summary_l,
    ):
        return True
    if re.search(
        rf"{label}\s+is\s+(?:also\s+)?(?:a\s+)?"
        rf"safer\b[^.]*\balready\s+(?:been\s+)?(?:played|discarded)\b",
        summary_l,
    ):
        return True
    if re.search(
        rf"{label}\s+is\s+[^.]*\balready\s+(?:been\s+)?(?:played|discarded)\b",
        summary_l,
    ) and not re.search(r"\bfuriten\b", summary_l):
        # Template: "2-man is genbutsu (safe — already discarded)"
        if re.search(
            rf"{label}\s+is\s+[^.]*\b(?:genbutsu|safe)\b",
            summary_l,
        ):
            return True
    # Teaching voice: "already discarded East" / "can't ron East"
    # (exclude furiten: "you already discarded 7-sou, so you can't win on…")
    if not re.search(r"\bfuriten\b", summary_l):
        if re.search(
            rf"\balready\s+(?:been\s+)?(?:played|discarded)\s+{label}\b",
            summary_l,
        ):
            return True
        if re.search(
            rf"\bcan'?t\s+(?:ron|win on)\s+{label}\b",
            summary_l,
        ):
            return True
    elif re.search(rf"\bcan'?t\s+ron\s+{label}\b", summary_l):
        return True
    if re.search(
        rf"if you throw\s+{label}\b[^.]{{0,60}}?"
        rf"(?:\bsafer\b|\bgenbutsu\b|\balready\s+(?:been\s+)?(?:played|discarded)\b"
        rf"|\bcan'?t\s+ron\b)",
        summary_l,
    ):
        return True
    return False


def _false_genbutsu_error(turn: TurnExplainInput, summary_l: str) -> str | None:
    """Reject genbutsu / already-played safety attached to the wrong tile."""
    gen = _genbutsu_tile_codes(turn)
    has_genbutsu_word = bool(re.search(r"\bgenbutsu\b", summary_l))
    has_safer_already = bool(
        re.search(
            r"\bsafer\b[^.]*\balready\s+(?:been\s+)?(?:played|discarded)\b",
            summary_l,
        )
    )
    has_already_played = bool(
        re.search(r"\balready\s+been\s+played\b", summary_l)
    )
    # Furiten tips also say "already discarded" / "can't win on" — ignore those.
    has_furiten = bool(re.search(r"\bfuriten\b", summary_l))
    has_already_discarded = bool(
        re.search(r"\balready\s+discarded\b", summary_l)
    ) and not has_furiten
    has_cant_ron = bool(re.search(r"\bcan'?t\s+ron\b", summary_l))
    has_cant_win_on = bool(
        re.search(r"\bcan'?t\s+win on\b", summary_l)
    ) and not has_furiten
    claims_genbutsu_safety = (
        has_genbutsu_word
        or has_safer_already
        or has_already_played
        or has_already_discarded
        or has_cant_ron
        or has_cant_win_on
    )
    if not claims_genbutsu_safety:
        return None

    for tile in _mentionable_tile_codes(turn):
        if tile in gen:
            continue
        if _tile_claimed_as_genbutsu_safe(summary_l, tile):
            return f"summary attributes genbutsu/already-discarded safety to {tile!r}"

    if has_genbutsu_word and gen:
        if not any(_mentions_tile(summary_l, t) for t in gen):
            return "summary mentions genbutsu without naming a genbutsu tile"
    needs_named_gen = (
        has_safer_already
        or has_already_played
        or has_already_discarded
        or has_cant_ron
        or has_cant_win_on
    )
    if needs_named_gen and not gen:
        return "summary claims already-discarded safety with no genbutsu tag"
    if needs_named_gen and gen:
        if not any(_mentions_tile(summary_l, t) for t in gen):
            return (
                "summary claims already-discarded safety "
                "without naming a genbutsu tile"
            )
    return None


# Count unit: "improving tiles" or prompt voice "tiles that can improve…"
_UKEIRE_COUNT_UNIT = (
    r"(?:improving tiles?(?:\s+available)?|"
    r"tiles that can improve(?:\s+(?:your\s+)?hand)?|"
    r"tiles that can help(?:\s+you)?)"
)

_UKEIRE_CONTRAST_PAIR_RE = re.compile(
    rf"(?P<best>\d+)\s+{_UKEIRE_COUNT_UNIT}"
    r".{0,120}?"
    r"(?:vs(?:\s+about)?|compared to(?:\s+only)?)\s+"
    rf"(?:about\s+)?(?P<alt>\d+)"
    rf"(?:\s+{_UKEIRE_COUNT_UNIT})?"
    r".{0,60}?"
    r"(?:if you throw|while throwing)\s+(?P<label>[^.]+?)(?:\.|,|$)",
    re.IGNORECASE | re.DOTALL,
)

# "31 tiles that can improve…, while throwing 9-sou … only 36 improving tiles"
_UKEIRE_WHILE_THROWING_RE = re.compile(
    rf"(?P<best>\d+)\s+{_UKEIRE_COUNT_UNIT}"
    r".{0,120}?"
    r"while\s+throwing\s+(?P<label>[^.]+?)"
    r".{0,80}?"
    rf"(?:only\s+)?(?:about\s+)?(?P<alt>\d+)\s+{_UKEIRE_COUNT_UNIT}",
    re.IGNORECASE | re.DOTALL,
)

# "37 … while 2-pin leaves you with only about 35"
_UKEIRE_WHILE_LEAVES_RE = re.compile(
    rf"(?P<best>\d+)\s+{_UKEIRE_COUNT_UNIT}"
    r".{0,120}?"
    r"while\s+(?P<label>[^.]+?)\s+leaves\s+you\s+with\s+"
    rf"(?:only\s+)?(?:about\s+)?(?P<alt>\d+)",
    re.IGNORECASE | re.DOTALL,
)

# Adjacent claim only — avoid matching best-count … vs about N if you throw
_UKEIRE_ALT_ONLY_RE = re.compile(
    rf"(?:compared to(?:\s+only)?|only)\s+"
    rf"(?:about\s+)?(?P<alt>\d+)\s+{_UKEIRE_COUNT_UNIT}\s+"
    r"(?:if you throw|while throwing)\s+(?P<label>[^.]+?)(?:\.|,|$)",
    re.IGNORECASE | re.DOTALL,
)


def _ukeire_contrast_match(
    summary_l: str,
) -> tuple[re.Match[str], int | None, int, str] | None:
    """Return (match, best_n|None, alt_n, label) for an improving-tile contrast."""
    pair = _UKEIRE_CONTRAST_PAIR_RE.search(summary_l)
    if pair:
        return pair, int(pair.group("best")), int(pair.group("alt")), pair.group("label")
    while_throw = _UKEIRE_WHILE_THROWING_RE.search(summary_l)
    if while_throw:
        return (
            while_throw,
            int(while_throw.group("best")),
            int(while_throw.group("alt")),
            while_throw.group("label"),
        )
    while_leaves = _UKEIRE_WHILE_LEAVES_RE.search(summary_l)
    if while_leaves:
        return (
            while_leaves,
            int(while_leaves.group("best")),
            int(while_leaves.group("alt")),
            while_leaves.group("label"),
        )
    alt_only = _UKEIRE_ALT_ONLY_RE.search(summary_l)
    if alt_only:
        return alt_only, None, int(alt_only.group("alt")), alt_only.group("label")
    return None


def _ukeire_only_on_larger_error(
    summary_l: str, best_n: int, alt_n: int
) -> str | None:
    """Reject 'only N' when N is the larger of the two cited contrast counts."""
    smaller = min(best_n, alt_n)
    for m in re.finditer(r"\bonly\s+(?:about\s+)?(\d+)\b", summary_l):
        n = int(m.group(1))
        if n in (best_n, alt_n) and n != smaller:
            return "summary uses 'only' on the larger improving-tile count"
    return None


def _false_ukeire_contrast_error(
    turn: TurnExplainInput, summary_l: str
) -> str | None:
    """Reject invented improving-tile vs / if-you-throw contrasts."""
    note_kind = _wall_note_kind(turn)
    alt_info = turn.features.ukeire_alt
    alt_action = _contrast_alt_action(turn)
    alt_raw = _action_tile_token_raw(alt_action) if alt_action else None
    alt_code = _danger_key(alt_raw) if alt_raw else None

    parsed = _ukeire_contrast_match(summary_l)
    if not parsed:
        return None
    match, best_n, alt_n, label = parsed

    if note_kind not in ("contrast", "narrow_contrast") or alt_info is None or alt_code is None:
        return "summary invents improving-tile contrast without wall_note contrast"

    if best_n is not None and best_n != turn.features.ukeire.count:
        return "summary improving-tile contrast counts do not match ukeire"
    if alt_n != alt_info.count:
        return "summary improving-tile contrast counts do not match ukeire"
    if best_n is not None:
        only_err = _ukeire_only_on_larger_error(summary_l, best_n, alt_n)
        if only_err:
            return only_err

    label = label.strip().lower()
    # Trim trailing relative clauses ("1-sou, which is…") / "would leave…"
    label = re.split(
        r"\s*,\s*|\s+which\b|\s+would\b|\s+leaves\b", label, maxsplit=1
    )[0].strip()
    if not _mentions_tile(label, alt_code) and not _mentions_tile(
        summary_l[match.start() : match.end()], alt_code
    ):
        return "summary improving-tile contrast names the wrong alternate cut"
    return None


_HONOR_NAME_TO_CODE: dict[str, str] = {
    "east": "E",
    "south": "S",
    "west": "W",
    "north": "N",
    "haku": "P",
    "white": "P",
    "hatsu": "F",
    "green": "F",
    "chun": "C",
}

_PAIR_OF_HONOR_RE = re.compile(
    r"\b(?:holding\s+)?(?:a\s+)?pair\s+of\s+"
    r"(?:[^\w\s]\s*)?"  # optional tile emoji before the name
    r"(?P<label>east|south|west|north|haku|hatsu|chun|white|green)\b",
    re.IGNORECASE,
)


def _yakuhai_pair_codes(
    hand: list[str], context: dict[str, Any] | None
) -> set[str]:
    """Yakuhai-capable honor codes held as a pair or triplet."""
    value = _yakuhai_value_tiles(context)
    counts = _hand_tile_counts(hand)
    return {
        tile
        for tile in _HONOR_ORDER
        if tile in value and counts.get(tile, 0) >= 2
    }


def _false_yakuhai_pair_error(
    turn: TurnExplainInput, summary_l: str
) -> str | None:
    """Reject 'pair of X' when X is not actually held as a yakuhai pair."""
    allowed = _yakuhai_pair_codes(
        turn.game_state.hand, turn.features.context
    )
    for m in _PAIR_OF_HONOR_RE.finditer(summary_l):
        code = _HONOR_NAME_TO_CODE.get(m.group("label").lower())
        if code is None:
            continue
        if code not in allowed:
            return f"summary claims pair of {code!r} not in yakuhai_pairs"

    # Template voice: "while Chun is already a pair"
    for tile in _HONOR_ORDER:
        label = _tile_claim_label_pattern(tile)
        if re.search(rf"{label}\s+is\s+already\s+a\s+pair\b", summary_l):
            if tile not in allowed:
                return f"summary claims pair of {tile!r} not in yakuhai_pairs"
    return None


# Cut-note kinds → prose patterns that attribute the note to a named tile.
_CUT_NOTE_TILE_CLAIM_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dead_end", (r"dead[-\s]?end",)),
    ("floating_honor", (r"floating\s+honor",)),
    ("floating_terminal", (r"floating\s+terminal",)),
    (
        "isolated_kanchan",
        (
            r"isolated\s+kanchan",
            r"closed\s+middle(?:\s*\([^)]*\))?",
        ),
    ),
    (
        "isolated_penchan",
        (
            r"isolated\s+penchan",
            r"(?:an?\s+)?edge(?:\s*\([^)]*\))?\s+shape",
        ),
    ),
)


def _tile_claimed_as_cut_note(
    summary_l: str, tile: str, kind_patterns: tuple[str, ...]
) -> bool:
    """True when prose attributes a cut-note kind to this tile."""
    label = _tile_claim_label_pattern(tile)
    kind_alt = "|".join(f"(?:{p})" for p in kind_patterns)
    if re.search(
        rf"{label}\s+is\s+(?:a\s+|an\s+)?(?:{kind_alt})\b",
        summary_l,
    ):
        return True
    if re.search(
        rf"{label}\s+breaks\s+up\s+(?:a\s+|an\s+)?(?:{kind_alt})\b",
        summary_l,
    ):
        return True
    if re.search(
        rf"while\s+{label}\s+is\s+(?:a\s+|an\s+)?(?:{kind_alt})\b",
        summary_l,
    ):
        return True
    return False


def _false_cut_note_tile_error(
    turn: TurnExplainInput, summary_l: str
) -> str | None:
    """Reject cut-note nouns attached to a tile that lacks that note."""
    notes_by_kind: dict[str, set[str]] = {}
    for note in _cut_shape_notes_for_turn(turn):
        try:
            code = deaka(normalize_tile(note.tile))
        except ValueError:
            continue
        notes_by_kind.setdefault(note.kind, set()).add(code)

    # Skip if summary has no cut-note vocabulary at all.
    if not re.search(
        r"\b(?:dead[-\s]?end|floating\s+honor|floating\s+terminal|"
        r"isolated\s+kanchan|isolated\s+penchan|closed\s+middle|"
        r"edge\s*\([^)]*\)\s+shape|edge\s+shape)\b",
        summary_l,
    ):
        return None

    for tile in _mentionable_tile_codes(turn):
        for kind, patterns in _CUT_NOTE_TILE_CLAIM_PATTERNS:
            if not _tile_claimed_as_cut_note(summary_l, tile, patterns):
                continue
            allowed = notes_by_kind.get(kind, set())
            if tile not in allowed:
                return f"summary attributes {kind} to {tile!r}"
    return None


def _pinned_discard_keep_error(
    turn: TurnExplainInput, summary_l: str
) -> str | None:
    """Reject Throw X tips that also advise keeping the pinned cut."""
    if parse_action_kind(turn.mortal_best) != "dahai":
        return None
    pin = _action_tile_token(turn.mortal_best)
    if not pin:
        return None

    if _PINNED_CUT_KEEP_IT_PATTERN.search(summary_l):
        return "pinned_cut_keep_contradiction"

    label = _tile_claim_label_pattern(pin)
    if re.search(
        rf"\b(?:keep(?:s|ing)?|preserve(?:s|ing)?|hold(?:s|ing)?\s+onto)\s+"
        rf"{label}\b",
        summary_l,
    ):
        return "pinned_cut_keep_contradiction"
    return None


def _negated_before(summary_l: str, start: int) -> bool:
    """True when match at start is preceded by don't / do not / not."""
    prefix = summary_l[max(0, start - 24) : start]
    return bool(re.search(r"(?:don['\u2019]t|do\s+not|not)\s+$", prefix))


def _action_lead_polarity_error(
    turn: TurnExplainInput, summary_l: str
) -> str | None:
    """Reject Skip/Call or Declare/Stay-silent leads that flip advice mid-tip."""
    if is_call_decision_turn(turn):
        kind = parse_action_kind(turn.mortal_best)
        if kind == "none":
            if re.search(
                r"\b(?:better to call|should call|take the (?:pon|chi|kan))\b",
                summary_l,
            ):
                return "action_lead_polarity_inverted"
        elif kind in ("pon", "chi", "kan"):
            if re.search(
                r"\b(?:better to skip|should skip|stay closed instead)\b",
                summary_l,
            ):
                return "action_lead_polarity_inverted"
        return None

    if is_riichi_decision_turn(turn):
        kind = parse_action_kind(turn.mortal_best)
        if kind == "reach":
            for m in re.finditer(r"\bstay silent\b", summary_l):
                if not _negated_before(summary_l, m.start()):
                    return "action_lead_polarity_inverted"
            if re.search(r"\bbetter not to (?:riichi|reach)\b", summary_l):
                return "action_lead_polarity_inverted"
        elif kind == "none":
            for m in re.finditer(r"\bdeclare riichi\b", summary_l):
                if not _negated_before(summary_l, m.start()):
                    return "action_lead_polarity_inverted"
        return None

    return None


_WALL_JARGON_RE = re.compile(
    r"\b(?:thinning wall|thin wall|improving tiles are thinning|left in the wall)\b",
    re.IGNORECASE,
)


def _wall_jargon_error(summary_l: str) -> str | None:
    """Reject ambiguous draw-pile / thinning jargon for unseen-copy facts."""
    if _WALL_JARGON_RE.search(summary_l):
        return "summary uses ambiguous wall/thinning jargon"
    if re.search(r"\bthinning\b", summary_l) and not (
        re.search(r"\bstill unseen\b", summary_l)
        or re.search(r"\balready out\b", summary_l)
    ):
        return "summary uses ambiguous wall/thinning jargon"
    return None



@dataclass(frozen=True)
class GroundingRule:
    id: str
    check: Callable[[TurnExplainInput, str, Explanation], str | None]


def _rule_false_genbutsu(turn, summary_l, explanation):
    return _false_genbutsu_error(turn, summary_l)


def _rule_false_ukeire(turn, summary_l, explanation):
    return _false_ukeire_contrast_error(turn, summary_l)


def _rule_false_yakuhai(turn, summary_l, explanation):
    return _false_yakuhai_pair_error(turn, summary_l)


def _rule_false_cut_note(turn, summary_l, explanation):
    return _false_cut_note_tile_error(turn, summary_l)


def _rule_pinned_keep(turn, summary_l, explanation):
    return _pinned_discard_keep_error(turn, summary_l)


def _rule_action_lead(turn, summary_l, explanation):
    return _action_lead_polarity_error(turn, summary_l)


def _rule_wall_jargon(turn, summary_l, explanation):
    return _wall_jargon_error(summary_l)


def _rule_isolated_shape(turn, summary_l, explanation):
    return _isolated_shape_on_cut_error(turn, summary_l)


def _rule_call_kind(turn, summary_l, explanation):
    return _call_kind_mismatch_error(turn, summary_l)


GROUNDING_RULES: tuple[GroundingRule, ...] = (
    GroundingRule("false_genbutsu_on_alt", _rule_false_genbutsu),
    GroundingRule("false_ukeire_contrast", _rule_false_ukeire),
    GroundingRule("false_yakuhai_pair", _rule_false_yakuhai),
    GroundingRule("false_cut_note_tile", _rule_false_cut_note),
    GroundingRule("pinned_cut_keep_contradiction", _rule_pinned_keep),
    GroundingRule("action_lead_polarity_inverted", _rule_action_lead),
    GroundingRule("wall_jargon", _rule_wall_jargon),
    GroundingRule("isolated_shape_on_cut_phrasing", _rule_isolated_shape),
    GroundingRule("call_kind_mismatch", _rule_call_kind),
)


def validate_explanation(turn: TurnExplainInput, explanation: Explanation) -> list[str]:
    """Return list of grounding violations (empty = ok)."""
    errors: list[str] = []
    if explanation.pinned_action != turn.mortal_best:
        errors.append(
            f"pinned_action {explanation.pinned_action!r} != mortal_best {turn.mortal_best!r}"
        )

    pin_token = _action_tile_token(turn.mortal_best)
    summary_l = explanation.summary.lower()
    if pin_token and turn.mortal_best.lower() not in summary_l:
        # Allow readable forms like "5-sou" / "Hatsu" / emoji labels
        if not _mentions_tile(summary_l, pin_token):
            errors.append(
                f"summary does not mention pinned action/tile {turn.mortal_best!r}"
            )

    reach_discard = turn.features.context.get("reach_discard")
    if (
        is_riichi_decision_turn(turn)
        and is_riichi_decision_action(turn.mortal_best)
        and reach_discard
        and not _mentions_tile(summary_l, str(reach_discard))
    ):
        errors.append(
            f"summary does not mention reach discard tile {reach_discard!r}"
        )

    # Reject recommending a different dahai tile than mortal_best
    other = _action_tile_token(turn.player_action)
    if (
        other
        and other != pin_token
        and re.search(rf"\b(?:discard|throw|cut)\s+{re.escape(other)}\b", summary_l)
        and not re.search(
            rf"\b(?:instead of|rather than|over|not)\s+{re.escape(other)}\b",
            summary_l,
        )
        and not re.search(rf"\bif you throw\s+{re.escape(other)}\b", summary_l)
    ):
        errors.append("summary appears to recommend the player's tile over Mortal")

    if len(explanation.summary.split()) > SUMMARY_WORD_LIMIT:
        errors.append("summary exceeds length budget")

    allowed_yaku = set(_coaching_shape_goals(turn))
    if turn.features.statuses.dora_in_hand:
        allowed_yaku.add("dora")
    for tag, patterns in _YAKU_MENTION_PATTERNS:
        if tag in allowed_yaku:
            continue
        for pat in patterns:
            if re.search(pat, summary_l):
                errors.append(f"summary mentions yaku {tag!r} not in shape_goals")
                break

    if _CUT_NOTE_POLARITY_PATTERN.search(summary_l):
        errors.append("cut_note_polarity_inverted")

    if _FIGURATIVE_HAND_OPEN_PATTERN.search(summary_l):
        errors.append("figurative_hand_open")

    for rule in GROUNDING_RULES:
        msg = rule.check(turn, summary_l, explanation)
        if msg:
            errors.append(msg)

    substance = score_explanation_substance(turn, explanation.summary)
    if substance.thin:
        errors.append("thin_efficiency_claim")

    return errors


def _isolated_shape_on_cut_error(
    turn: TurnExplainInput, summary_l: str
) -> str | None:
    """Reject 'kanchan/penchan/fragment on {cut}' — sounds like a wait tile."""
    for note in turn.features.hand_shape_notes:
        if note.kind not in ("isolated_kanchan", "isolated_penchan"):
            continue
        label = _tile_claim_label_pattern(note.tile)
        if re.search(
            rf"\b(?:(?:isolated\s+)?(?:kanchan|penchan)|fragment)\b"
            rf"(?:\s*\([^)]*\))?"
            rf"\s+on\s+{label}\b",
            summary_l,
        ):
            return "isolated_shape_on_cut_phrasing"
    return None


def _call_kind_mismatch_error(turn: TurnExplainInput, summary_l: str) -> str | None:
    """Reject summaries that recommend the wrong call family vs mortal_best."""
    kind = parse_action_kind(turn.mortal_best)
    if kind == "chi" and re.search(r"\bpon\b", summary_l):
        return "summary call kind pon mismatches mortal_best chi"
    if kind == "pon" and re.search(
        r"(?:^|[.!?]\s*)chi\b|\bchi\s+\d", summary_l
    ):
        return "summary call kind chi mismatches mortal_best pon"
    if kind == "kan" and (
        re.search(r"\bcall\s+pon\b", summary_l)
        or re.search(r"(?:^|[.!?]\s*)chi\b", summary_l)
    ):
        return "summary call kind mismatches mortal_best kan"
    return None
def _action_tile_token(action: str) -> str | None:
    tile = action_tile_arg(action)
    return tile.lower() if tile else None


_HONOR_ALIASES: dict[str, tuple[str, ...]] = {
    "e": ("east",),
    "s": ("south",),
    "w": ("west",),
    "n": ("north",),
    "p": ("haku",),
    "f": ("hatsu",),
    "c": ("chun",),
}


def _mentions_tile(text: str, tile: str) -> bool:
    """Match mjai codes, suit names (5-sou), honor names (Hatsu), and emoji labels."""
    tile = tile.lower()
    label = human_tile_label(tile).lower()
    if label and label in text:
        return True
    if tile in _HONOR_ALIASES:
        if re.search(rf"\b{re.escape(tile)}\b", text):
            return True
        return any(alias in text for alias in _HONOR_ALIASES[tile])
    if tile in text:
        return True
    if re.fullmatch(r"5[mps]r", tile) and "red" in text and _mentions_tile(text, tile[:2]):
        return True
    m = re.fullmatch(r"([1-9])([mps])", tile)
    if not m:
        return False
    num, suit = m.group(1), m.group(2)
    suit_name = {"m": "man", "p": "pin", "s": "sou"}[suit]
    patterns = [
        rf"{num}-{suit_name}",
        rf"{num}\s*{suit_name}",
        rf"{num}{suit_name}",
    ]
    return any(re.search(p, text) for p in patterns)
