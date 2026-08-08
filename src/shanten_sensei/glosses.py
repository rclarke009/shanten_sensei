"""Beginner-friendly glosses for yaku/shape tags shown in coaching UI."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

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
    "genbutsu": "safe — opponent already discarded it, so they can't ron it",
    "suji": "interval-safe—if they waited on the edge, they'd likely discard this already",
    "one-chance": "middle tile nearly all out, so a closed middle wait is unlikely",
}

SHAPE_NOTE_GLOSS: dict[str, str] = {
    "floating_terminal": "lone 1/9 with no connector",
    "floating_honor": "lone wind or dragon",
    "isolated_kanchan": "closed middle fragment",
    "isolated_penchan": "edge wait fragment",
    "dead_end": "connects to nothing useful",
}

# Shared teaching gloss for ukeire / acceptances (same concept).
UKEIRE_GLOSS = "tiles that improve the hand"
ACCEPTANCES_GLOSS = UKEIRE_GLOSS
DORA_GLOSS = "bonus tile"

METRIC_GLOSS: dict[str, str] = {
    "shanten": "steps from ready",
    "tenpai": "ready",
    "ukeire": UKEIRE_GLOSS,
    "acceptances": ACCEPTANCES_GLOSS,
    "dora": DORA_GLOSS,
}

NO_CLEAR_SHAPE = "no clear yaku shape yet"

YAKU_REFERENCE_URL = "https://www.mahjongmaster.co/learn/riichi/yaku/"
YAKU_REFERENCE_LABEL = "Yaku list"

# Checking either synonym hides both parentheticals.
_TERM_ALIASES: dict[str, frozenset[str]] = {
    "ukeire": frozenset({"ukeire", "acceptances"}),
    "acceptances": frozenset({"ukeire", "acceptances"}),
}


@dataclass(frozen=True)
class GlossChecklistItem:
    """One row in the Terms I know checklist."""

    id: str
    group: str
    gloss: str


GLOSS_CHECKLIST: tuple[GlossChecklistItem, ...] = (
    *(GlossChecklistItem(k, "Yaku", v) for k, v in GOAL_GLOSS.items()),
    *(GlossChecklistItem(k, "Waits", v) for k, v in WAIT_GLOSS.items()),
    *(GlossChecklistItem(k, "Defense", v) for k, v in DANGER_GLOSS.items()),
    GlossChecklistItem("shanten", "Metrics", METRIC_GLOSS["shanten"]),
    GlossChecklistItem("tenpai", "Metrics", METRIC_GLOSS["tenpai"]),
    GlossChecklistItem("ukeire", "Metrics", METRIC_GLOSS["ukeire"]),
    GlossChecklistItem("acceptances", "Metrics", METRIC_GLOSS["acceptances"]),
    GlossChecklistItem("dora", "Metrics", METRIC_GLOSS["dora"]),
    GlossChecklistItem("furiten", "Status", "can’t win on discard — tsumo only"),
    GlossChecklistItem("temp_furiten", "Status", "passed a win this turn"),
    *(GlossChecklistItem(k, "Shape notes", v) for k, v in SHAPE_NOTE_GLOSS.items()),
)

GLOSS_TERM_IDS: frozenset[str] = frozenset(item.id for item in GLOSS_CHECKLIST)

_known_terms_var: ContextVar[frozenset[str]] = ContextVar(
    "shanten_sensei_known_terms", default=frozenset()
)


def normalize_known_terms(terms: Iterable[str] | None) -> frozenset[str]:
    """Keep only catalog ids; drop unknowns."""
    if not terms:
        return frozenset()
    return frozenset(t for t in terms if t in GLOSS_TERM_IDS)


@contextmanager
def using_known_terms(terms: Collection[str] | None) -> Iterator[None]:
    """Apply known-term set for gloss helpers in this scope."""
    token = _known_terms_var.set(normalize_known_terms(terms))
    try:
        yield
    finally:
        _known_terms_var.reset(token)


def _resolve_known(known_terms: Collection[str] | None) -> frozenset[str]:
    if known_terms is not None:
        return normalize_known_terms(known_terms)
    return _known_terms_var.get()


def term_is_known(term: str, known_terms: Collection[str] | None = None) -> bool:
    """True when the user marked this term (or an alias) as known."""
    known = _resolve_known(known_terms)
    if not known:
        return False
    aliases = _TERM_ALIASES.get(term, frozenset({term}))
    return bool(known & aliases)


def _with_gloss(term: str, gloss: str | None, known_terms: Collection[str] | None) -> str:
    if not gloss or term_is_known(term, known_terms):
        return term
    return f"{term} ({gloss})"


def glossed_goal(tag: str, *, known_terms: Collection[str] | None = None) -> str:
    gloss = GOAL_GLOSS.get(tag)
    return _with_gloss(tag, gloss, known_terms)


def glossed_wait(
    wait_shape: str | None, *, known_terms: Collection[str] | None = None
) -> str | None:
    """e.g. ryanmen → 'ryanmen (two-sided open)'."""
    if not wait_shape:
        return None
    gloss = WAIT_GLOSS.get(wait_shape)
    return _with_gloss(wait_shape, gloss, known_terms)


def glossed_danger(
    tag: str | None, *, known_terms: Collection[str] | None = None
) -> str | None:
    """e.g. suji → 'suji (interval-safe …)'."""
    if not tag:
        return None
    gloss = DANGER_GLOSS.get(tag)
    return _with_gloss(tag, gloss, known_terms)


def glossed_furiten(
    *,
    furiten: bool = False,
    temporary: bool = False,
    known_terms: Collection[str] | None = None,
) -> str:
    """Chip / status label for furiten (tsumo-only when permanent)."""
    if temporary:
        if term_is_known("temp_furiten", known_terms):
            return "temp furiten"
        return "temp furiten (passed a win this turn)"
    if furiten:
        if term_is_known("furiten", known_terms):
            return "furiten"
        return "furiten (can’t win on discard — tsumo only)"
    return "not furiten"


def glossed_shanten(
    shanten: int, *, known_terms: Collection[str] | None = None
) -> str:
    """e.g. 3 → '3-shanten (3 steps from ready)'; 0 → 'tenpai (ready)'."""
    if shanten == -1:
        return "complete (winning hand)"
    if shanten <= 0:
        if term_is_known("tenpai", known_terms):
            return "tenpai"
        return "tenpai (ready)"
    # features._shanten_with_melds sentinel when closed+melds ≠ 13/14
    if shanten == 8:
        return "hand sync unavailable"
    step = "step" if shanten == 1 else "steps"
    if term_is_known("shanten", known_terms):
        return f"{shanten}-shanten"
    return f"{shanten}-shanten ({shanten} {step} from ready)"


def glossed_ukeire(
    *, known_terms: Collection[str] | None = None
) -> str:
    """Bare 'ukeire' or 'ukeire (tiles that improve the hand)'."""
    return _with_gloss("ukeire", UKEIRE_GLOSS, known_terms)


def glossed_ukeire_count(
    count: int, *, known_terms: Collection[str] | None = None
) -> str:
    """Status-strip style: 'ukeire 51' or with parenthetical when unknown."""
    if term_is_known("ukeire", known_terms):
        return f"ukeire {count}"
    return f"ukeire ({UKEIRE_GLOSS}) {count}"


def glossed_dora(
    tile_label: str, *, known_terms: Collection[str] | None = None
) -> str:
    if term_is_known("dora", known_terms):
        return f"dora {tile_label}"
    return f"dora ({DORA_GLOSS}) {tile_label}"


def glossed_acceptances(
    count: int, *, known_terms: Collection[str] | None = None
) -> str:
    """Count of improving tiles; teaches ukeire when the user still needs it."""
    if count == 0:
        return "no improving tiles"
    if term_is_known("ukeire", known_terms):
        return f"about {count} ukeire"
    return f"about {count} ukeire ({UKEIRE_GLOSS})"


def format_aiming_for(
    shape_goals: list[str] | None,
    *,
    known_terms: Collection[str] | None = None,
) -> str:
    """Human line for the Aiming-for strip (without the 'Aiming for:' prefix)."""
    goals = [g for g in (shape_goals or []) if g]
    if not goals:
        return NO_CLEAR_SHAPE
    return " / ".join(glossed_goal(g, known_terms=known_terms) for g in goals)
