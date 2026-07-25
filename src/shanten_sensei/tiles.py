"""mjai tile string helpers (e.g. 5s, 5mr, E, C)."""

from __future__ import annotations

# 34-index order used by mahjong / Mortal: man, pin, sou, honors
_HONOR_TO_IDX = {
    "E": 27,
    "S": 28,
    "W": 29,
    "N": 30,
    "P": 31,  # haku (white)
    "F": 32,  # hatsu (green)
    "C": 33,  # chun (red)
    "1z": 27,
    "2z": 28,
    "3z": 29,
    "4z": 30,
    "5z": 31,
    "6z": 32,
    "7z": 33,
}

_IDX_TO_TILE = (
    [f"{i}m" for i in range(1, 10)]
    + [f"{i}p" for i in range(1, 10)]
    + [f"{i}s" for i in range(1, 10)]
    + ["E", "S", "W", "N", "P", "F", "C"]
)


def normalize_tile(tile: str) -> str:
    """Normalize aka / honor spellings to a canonical mjai-ish string."""
    t = tile.strip()
    if t in ("5mr", "0m"):
        return "5mr"
    if t in ("5pr", "0p"):
        return "5pr"
    if t in ("5sr", "0s"):
        return "5sr"
    if t in _HONOR_TO_IDX and len(t) <= 2 and not t[-1:].isdigit():
        return t
    if t.endswith("z") and t[:-1].isdigit():
        return ["E", "S", "W", "N", "P", "F", "C"][int(t[0]) - 1]
    return t


def tile_to_34(tile: str) -> int:
    """Map a tile string to a 0..33 index (aka reds → 5 of suit)."""
    t = normalize_tile(tile)
    if t in ("5mr", "5pr", "5sr"):
        suit = t[1]
        base = {"m": 0, "p": 9, "s": 18}[suit]
        return base + 4  # 5m/5p/5s
    if t in _HONOR_TO_IDX:
        return _HONOR_TO_IDX[t]
    if len(t) >= 2 and t[0].isdigit() and t[1] in "mps":
        num = int(t[0])
        suit = t[1]
        base = {"m": 0, "p": 9, "s": 18}[suit]
        return base + num - 1
    raise ValueError(f"unrecognized tile: {tile!r}")


def tile_from_34(index: int) -> str:
    if not 0 <= index < 34:
        raise ValueError(f"tile index out of range: {index}")
    return _IDX_TO_TILE[index]


def tiles_to_34_array(tiles: list[str]) -> list[int]:
    counts = [0] * 34
    for tile in tiles:
        counts[tile_to_34(tile)] += 1
    return counts


def deaka(tile: str) -> str:
    t = normalize_tile(tile)
    if t == "5mr":
        return "5m"
    if t == "5pr":
        return "5p"
    if t == "5sr":
        return "5s"
    return t


# Unicode mahjong tiles (same block as overlay MJAI_TILE_2_UNICODE)
_TILE_EMOJI: dict[str, str] = {
    **{f"{i}m": c for i, c in enumerate("🀇🀈🀉🀊🀋🀌🀍🀎🀏", 1)},
    **{f"{i}p": c for i, c in enumerate("🀙🀚🀛🀜🀝🀞🀟🀠🀡", 1)},
    **{f"{i}s": c for i, c in enumerate("🀐🀑🀒🀓🀔🀕🀖🀗🀘", 1)},
    "5mr": "🀋",
    "5pr": "🀝",
    "5sr": "🀔",
    "E": "🀀",
    "S": "🀁",
    "W": "🀂",
    "N": "🀃",
    "P": "🀆",
    "F": "🀅",
    "C": "🀄",
}

_HONOR_NAMES: dict[str, str] = {
    "E": "East",
    "S": "South",
    "W": "West",
    "N": "North",
    "P": "Haku",
    "F": "Hatsu",
    "C": "Chun",
}

_SUIT_NAMES = {"m": "man", "p": "pin", "s": "sou"}


def human_tile_label(tile: str) -> str:
    """Beginner-facing label: emoji + English name (e.g. 🀅Hatsu, 9-pin)."""
    try:
        t = tile_from_34(tile_to_34(tile))
        # Preserve aka reds (tile_to_34 collapses them to plain 5s)
        norm = normalize_tile(tile)
        if norm in ("5mr", "5pr", "5sr"):
            t = norm
    except ValueError:
        t = normalize_tile(tile)
        if len(t) == 1 and t.upper() in _HONOR_NAMES:
            t = t.upper()
    emoji = _TILE_EMOJI.get(t, "")
    if t in _HONOR_NAMES:
        return f"{emoji}{_HONOR_NAMES[t]}"
    if t in ("5mr", "5pr", "5sr"):
        suit = _SUIT_NAMES[t[1]]
        return f"{emoji}red 5-{suit}"
    if len(t) >= 2 and t[0].isdigit() and t[1] in _SUIT_NAMES:
        return f"{emoji}{t[0]}-{_SUIT_NAMES[t[1]]}"
    return tile


def human_action_label(action: str) -> str:
    """Humanize tile args in action labels; keep verbs (dahai → tile only for prose)."""
    if action.startswith("dahai "):
        return human_tile_label(action.split(" ", 1)[1])
    parts = action.split(" ", 1)
    if len(parts) == 2:
        return f"{parts[0]} {human_tile_label(parts[1])}"
    return action


def action_to_label(action: dict) -> str:
    """Compact label for prompts / pinning, e.g. 'dahai 5s'."""
    kind = action.get("type") or action.get("type_")
    if kind == "dahai":
        return f"dahai {normalize_tile(action['pai'])}"
    if kind == "reach":
        return "reach"
    if kind == "hora":
        return "hora"
    if kind == "none":
        return "none"
    if kind in ("chi", "pon", "daiminkan", "kakan", "ankan"):
        pai = action.get("pai") or (action.get("consumed") or ["?"])[0]
        return f"{kind} {normalize_tile(str(pai))}"
    if kind == "ryukyoku":
        return "ryukyoku"
    return str(kind)
