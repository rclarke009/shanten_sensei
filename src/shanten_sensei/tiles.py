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
