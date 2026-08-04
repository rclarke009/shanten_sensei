"""Beginner-friendly glosses for yaku/shape tags shown in coaching UI."""

from __future__ import annotations

GOAL_GLOSS: dict[str, str] = {
    "tanyao": "2–8 only; no 1/9, winds, or dragons",
    "yakuhai": "triplet of dragon or your seat/round wind",
    "honitsu": "one suit + winds/dragons OK",
    "chinitsu": "one suit only",
    "toitoi": "all triplets",
    "chiitoi": "seven pairs",
    "pinfu": "closed all-sequences; no value pair",
    "ittsu": "1–9 straight in one suit",
}

WAIT_GLOSS: dict[str, str] = {
    "ryanmen": "two-sided open",
    "kanchan": "closed middle",
    "penchan": "edge",
    "tanki": "pair",
    "shanpon": "two-pair",
    "complex": "multiple wait types",
}

DANGER_GLOSS: dict[str, str] = {
    "genbutsu": "safe — already discarded",
    "suji": "interval-safe vs a common wait",
    "one-chance": "middle tile almost all out",
}

SHAPE_NOTE_GLOSS: dict[str, str] = {
    "floating_terminal": "lone 1/9 with no connector",
    "floating_honor": "lone wind or dragon",
    "isolated_kanchan": "closed middle fragment",
    "isolated_penchan": "edge wait fragment",
    "dead_end": "connects to nothing useful",
}

NO_CLEAR_SHAPE = "no clear yaku shape yet"

YAKU_REFERENCE_URL = "https://www.mahjongmaster.co/learn/riichi/yaku/"
YAKU_REFERENCE_LABEL = "Yaku list"


def glossed_goal(tag: str) -> str:
    gloss = GOAL_GLOSS.get(tag)
    return f"{tag} ({gloss})" if gloss else tag


def glossed_wait(wait_shape: str | None) -> str | None:
    """e.g. ryanmen → 'ryanmen (two-sided open)'."""
    if not wait_shape:
        return None
    gloss = WAIT_GLOSS.get(wait_shape)
    return f"{wait_shape} ({gloss})" if gloss else wait_shape


def glossed_danger(tag: str | None) -> str | None:
    """e.g. suji → 'suji (interval-safe vs a common wait)'."""
    if not tag:
        return None
    gloss = DANGER_GLOSS.get(tag)
    return f"{tag} ({gloss})" if gloss else tag


def glossed_furiten(*, furiten: bool = False, temporary: bool = False) -> str:
    """Chip / status label for furiten (tsumo-only when permanent)."""
    if temporary:
        return "temp furiten (passed a win this turn)"
    if furiten:
        return "furiten (can’t win on discard — tsumo only)"
    return "not furiten"


def glossed_shanten(shanten: int) -> str:
    """e.g. 3 → '3-shanten (3 steps from ready)'; 0 → 'tenpai (ready)'."""
    if shanten == -1:
        return "complete (winning hand)"
    if shanten <= 0:
        return "tenpai (ready)"
    # features._shanten_with_melds sentinel when closed+melds ≠ 13/14
    if shanten == 8:
        return "hand sync unavailable"
    step = "step" if shanten == 1 else "steps"
    return f"{shanten}-shanten ({shanten} {step} from ready)"


def format_aiming_for(shape_goals: list[str] | None) -> str:
    """Human line for the Aiming-for strip (without the 'Aiming for:' prefix)."""
    goals = [g for g in (shape_goals or []) if g]
    if not goals:
        return NO_CLEAR_SHAPE
    return " / ".join(glossed_goal(g) for g in goals)
