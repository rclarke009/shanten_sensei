"""Grounded explain() — LLM translates Mortal; never evaluates the hand."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from collections.abc import Collection
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from shanten_sensei.features import danger_rank, genbutsu_discarders
from shanten_sensei.glosses import ACCEPTANCES_GLOSS as _ACCEPTANCES_GLOSS
from shanten_sensei.glosses import DANGER_GLOSS as _DANGER_GLOSS
from shanten_sensei.glosses import DORA_GLOSS as _DORA_GLOSS
from shanten_sensei.glosses import GOAL_GLOSS as _GOAL_GLOSS
from shanten_sensei.glosses import SHAPE_NOTE_GLOSS as _SHAPE_NOTE_GLOSS
from shanten_sensei.glosses import UKEIRE_GLOSS as _UKEIRE_GLOSS
from shanten_sensei.glosses import WAIT_GLOSS as _WAIT_GLOSS
from shanten_sensei.glosses import glossed_acceptances as _glossed_acceptances
from shanten_sensei.glosses import glossed_danger as _glossed_danger
from shanten_sensei.glosses import glossed_dora as _glossed_dora
from shanten_sensei.glosses import glossed_goal as _glossed_goal
from shanten_sensei.glosses import glossed_shanten as _glossed_shanten_phrase
from shanten_sensei.glosses import glossed_ukeire as _glossed_ukeire
from shanten_sensei.glosses import glossed_wait as _glossed_wait
from shanten_sensei.glosses import normalize_known_terms
from shanten_sensei.glosses import term_is_known
from shanten_sensei.glosses import using_known_terms
from shanten_sensei.live import (
    is_call_decision_turn,
    is_hora_decision_turn,
    is_riichi_decision_turn,
    next_best_action,
)
from shanten_sensei.schema import Explanation, Focus, TurnExplainInput
from shanten_sensei.tiles import (
    action_tile_arg,
    coach_action_label,
    deaka,
    human_action_label,
    human_tile_label,
    is_call_action,
    is_hora_decision_action,
    is_riichi_decision_action,
    normalize_tile,
    parse_action_kind,
)

ALLOWED_FOCUS = frozenset({"efficiency", "defense", "value", "tempo", "mixed"})
SUMMARY_WORD_LIMIT = 90

SYSTEM_PROMPT = """\
You are a beginner-friendly riichi mahjong coach. You explain Mortal’s \
recommendation using only the game state, Mortal scores, and derived features \
provided. You do not invent better moves. If the player’s move differs, say why \
Mortal’s choice is better in efficiency, safety, or point situation. If this is \
a live pre-decision turn (diverge is false / player_action equals mortal_best), \
explain why Mortal’s top pick beats the next-best candidate. Write two or three \
short sentences in plain English: (1) the action, (2) the main reason—efficiency, \
defense, or value, and (3) optional secondary grounded fact—shape, call \
tradeoff, wall contrast, point situation, or furiten when it justifies the pick. \
Never open with "Mortal recommends" or \
"Mortal prefers". Never use bare honor letters F/C/P or bare suit codes like \
5s when naming tiles for the player. Never recommend an action other than \
mortal_best. Never write \"Mortal’s cut is …\" or \"Target: …\". Do not restate \
bare shanten / improving-tile counts unless citing a contrast \
(\"about N … vs about M if you throw …\") or wall thinning.

For discard tips, lead with \"Throw X\" or \"Throw X, not Y\" using \
tile_glossary / coach_action labels (e.g. 🀅Hatsu, 🀔5-sou).

For call tips (mortal_best or contrast is none / pon / chi / kan — see \
call_tradeoff), lead with \"Skip\" / \"Skip the pon on …\" / \"Skip the chi on …\" / \
\"Call pon on …, don’t skip\" / \"Chi …, don’t skip\" — never \"Throw none\" or \
\"Throw pon\". The call verb must match mortal_best kind (pon vs chi vs kan). Cite \
call_tradeoff when present: opening loses riichi; open_shanten vs stay-closed \
shanten; open_ukeire_count vs stay_closed_ukeire when present; shape_goals \
(e.g. still aiming for tanyao while holding terminals). \
When recommending a call that opens the hand, do not say the hand is still \
aiming for closed-only yaku (pinfu, chiitoi / seven pairs)—cite tempo, \
shanten, or call_tradeoff instead.

Use \"open\" / \"closed\" only for called vs menzen (call tips / \
call_tradeoff)—e.g. \"Calling would open the hand\" or \"You’re still … \
closed\". Never write \"keeps your hand open\" / \"hand open with … improving \
tiles\" for discard ukeire; prefer \"That leaves about N tiles that can \
improve your hand\". Wait glosses like \"ryanmen (two-sided open)\" are fine.

For riichi tips (riichi_decision true — reach vs none), lead with \
\"Declare riichi\" / \"Stay silent\" — never \"Throw reach\" or \"Skip\". When \
reach_discard is present, name that cut in the lead (e.g. \"Declare riichi, \
discard red 5-sou\") — use \"discard\", not \"Throw\". Cite tenpai / wait \
shape, furiten_blocking_tiles, dora_in_hand, or score_situation.

For hora tips (hora_decision true — winning on tsumo/ron), lead with \
\"Take the win\" — never bare \"hora\" or \"Declare hora\". When shanten is -1, \
say the hand is complete / a winning hand, not tenpai (ready). Do not invent \
yaku aims for a finished hand. Never say \"Waiting on\" at hora — name the \
winning tile with \"Win on {tile}\" and wait_shape_glossary when known; omit \
the tile line on tsumo (14-tile hand).

When danger tags a safer cut (genbutsu / suji / one-chance with \
danger_glossary parentheticals), prefer one defense sentence about \
mortal_best only—never catalogue other hand tiles’ genbutsu / suji / \
one-chance tags. When danger is genbutsu, explain the rule: an opponent \
already discarded that tile, so they can't ron it from you — not jargon alone. \
For suji, explain that edge waits in that suit likely already discarded this \
tile. For one-chance, explain that the middle tile is nearly all out. You may \
say \"the riichi player\" only when danger_detail seats show a riichi opponent \
discarded it; otherwise say \"an opponent.\" Genbutsu / \"already discarded\" / \
\"already been played\" / \"can't ron\" must name the danger-tagged tile \
(usually mortal_best)—never the alternate cut unless that alternate is also \
tagged genbutsu. When score_situation is present, you may \
add one short point-situation line (opponent riichi, leading/trailing/even, late \
wall).

Do not justify Mortal by restating its probability percentages or by saying \
\"more efficient\" / \"higher chance\" alone. Prefer one concrete fact from the \
payload: shanten/acceptances (with hand_metric_glossary parentheticals), ukeire \
tiles / remaining_by_tile, ukeire_alt, wall_note, wait shape (with \
wait_shape_glossary parentheticals, e.g. \"ryanmen (two-sided open)\"), \
shape_goals (with glossary parentheticals), hand_shape_notes (floating \
terminal/honor, isolated kanchan/penchan, dead-end — these describe why the \
recommended cut is weak/useless and apply only to the recommended cut tile \
named in those notes, e.g. \"North is a dead-end tile\", \
\"9-pin is a floating terminal\", \"2-man clears a closed middle (kanchan) shape\" / \
\"8-man clears an edge (penchan) shape\"; never attach those notes to the \
alternate cut or another hand tile; never write \"kanchan/penchan/fragment on \
{tile}\" — that sounds like a wait; if naming both ends say \"6–8 kanchan\", never \
\"kanchan on 8-man\"; never say you keep / maintain / preserve a dead-end, \
floating, or isolated shape; never say \"better to keep it\" / \"keep it for \
now\" or that you should keep the recommended cut tile—cut notes justify \
throwing that tile), \
furiten_blocking_tiles, call_tradeoff, danger, score_situation, or dora. The \
chart already shows Mortal % — leave percentages out of the summary.

You may cite ukeire.remaining_by_tile or ukeire_alt for visible wall depletion \
or improving-tile contrast (e.g. tiles already out; about N improving tiles \
left vs about M if you throw the alternate). Prefer wall_note facts when \
present, rephrased in the same plain voice — do not paste jargon like \
\"live acceptances\". Wall thinning like \"only N× tile left\" / \"already out\" \
is about remaining copies of improving tiles, not the alternate cut’s \
acceptance count—never rewrite it as \"N improving tiles if you throw …\". \
Only invent an improving-tile vs/if-you-throw contrast when wall_note is already \
that contrast form (\"about N … vs about M if you throw …\"). Never invent \
unseen wall math, opponent-hand contents, or discard reasons not supported by \
those fields.

If shape_goals is non-empty, you may name only those goals as likely hand shape \
(not as Mortal’s internal plan). Prefer \"fits tanyao (…)\" over \"shape leans\". \
When you name a goal or dora, include the short parenthetical ONLY when that \
term appears in shape_goal_glossary (e.g. \"tanyao (2–8 only; no 1/9, winds, or \
dragons)\", \"dora (bonus tile)\"). If a term is missing from the glossary maps, \
use the bare term with no parenthetical (the player already knows it). \
When you mention shanten, ukeire, or acceptances, include the short parenthetical \
from hand_metric_glossary when present (e.g. \"3-shanten (3 steps from ready)\", \
\"ukeire (tiles that improve the hand)\"). Prefer saying \"ukeire\" over \
\"acceptances\". If wall_note already contrasts improving-tile counts, do not \
also restate the absolute ukeire count. Never invent other yaku. You may mention \
dora only when statuses.dora_in_hand is non-empty.

When shape_goals includes yakuhai, always explain with a short because clause \
from yakuhai_pairs / yakuhai_singleton_value_tiles (e.g. you’re holding a pair \
of East for that; 1-man isn’t a value tile, while Chun can still pair). Only \
say \"pair of X\" / \"holding a pair of X\" when X is listed in yakuhai_pairs; \
singletons in yakuhai_singleton_value_tiles use \"can still pair\", never \
\"pair of\". Never say an alternate \"would not help … aiming for yakuhai\" \
without naming those tile facts.

Put a line break (\\n) in summary between the move/ukeire chunk and the \
hand-state / aiming chunk when both are present. Do not use a blank line.

Example discard voice: \"Throw 🀂West. That leaves about 55 tiles that can \
improve your hand, vs about 41 if you throw 🀖7-sou.\\nYou’re 1-shanten \
(1 step from ready). That fits tanyao (2–8 only; no 1/9, winds, or dragons)—🀂West \
is a floating honor outside tanyao.\"

Example mid-hand voice: \"Throw 🀡9-pin, not 🀔5-sou. You’re 2-shanten (2 steps \
from ready) with about 40 ukeire (tiles that improve the hand).\\n🀡9-pin is \
a floating terminal outside tanyao (2–8 only; no 1/9, winds, or dragons).\"

Example dead-end voice: \"Throw 🀃North.\\n🀃North is a dead-end tile—it connects \
to nothing useful.\"

Example yakuhai voice: \"Throw 🀇1-man, not 🀄Chun.\\nThat fits yakuhai (triplet of \
dragon or your seat/round wind)—you’re holding a pair of 🀀East for that; 🀇1-man \
isn’t a value tile, while 🀄Chun can still pair.\"

When statuses.wait_shape is set, name it with the wait_shape_glossary \
parenthetical (e.g. \"ryanmen (two-sided open) wait\"). When statuses.furiten \
is true, name furiten_blocking_tiles if present (tiles you already discarded \
that are also waits) and explain that ron is blocked on every wait—you can \
only win by tsumo (self-draw).

Example tenpai voice: \"Throw 🀊4-man, not 🀌6-man. That keeps a ryanmen \
(two-sided open) wait.\\nYou’re furiten—you already discarded 🀖7-sou, so you \
can’t win on any discard (only tsumo).\"

Example call voice: \"Skip the pon on 🀒3-sou. You’re still 2-shanten (2 steps \
from ready) closed with about 55 improving tiles.\\nCalling would open the \
hand—no riichi—while you’re still aiming for tanyao (2–8 only; no 1/9, winds, \
or dragons) and holding terminals.\"

Example call (chi) voice: \"Chi 🀖7-sou, don’t skip. You’re 1-shanten (1 step \
from ready) closed with about 11 improving tiles.\\nThat gets you closer than \
staying closed. That opens the hand—no riichi.\"

Example defense voice: \"Throw 🀊4-man, not 🀌6-man. 🀊4-man is suji—if someone \
waited on the edge tiles in that suit, they'd likely have discarded 🀊4-man \
already.\\nAn opponent is in riichi—safety matters.\"

Example riichi voice: \"Declare riichi, discard 🀡9-pin. You’re tenpai (ready) \
with a ryanmen (two-sided open) wait.\\nYou have dora (bonus tile) in hand.\"

Example hora voice: \"Take the win. You’re complete (winning hand).\\nWin on \
🀛2-sou (tanki (pair)).\\nYou have dora (bonus tile) in hand.\"

Return JSON with exactly these keys:
- summary: string (two or three short sentences; use \\n between move and state when both appear)
- focus: one of "efficiency", "defense", "value", "tempo", "mixed" (enum only, never prose)
- pinned_action: must equal mortal_best
- contrasted_action: player's action when it differs; else next-best candidate; else null
"""

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

# Closed-hand-only yaku: drop from coaching when Mortal recommends an open call.
CLOSED_ONLY_GOALS = frozenset({"pinfu", "chiitoi"})


def recommending_open_call(turn: TurnExplainInput) -> bool:
    """True when mortal_best is a call that would break menzen."""
    if not is_call_action(turn.mortal_best):
        return False
    tradeoff = turn.features.call_tradeoff
    if tradeoff is not None:
        return tradeoff.opens_hand
    return len(turn.game_state.calls) == 0


def coaching_shape_goals(turn: TurnExplainInput) -> list[str]:
    """Shape goals safe to show/cite for this tip (filters closed-only on open calls)."""
    # Finished hand: don't keep "aiming for" mid-game shape tags.
    if turn.features.shanten == -1:
        return []
    goals = [g for g in turn.features.shape_goals if g]
    if recommending_open_call(turn):
        return [g for g in goals if g not in CLOSED_ONLY_GOALS]
    return goals


def _glossed_dora_phrase(tile_label: str) -> str:
    return _glossed_dora(tile_label)


def _glossed_acceptances_phrase(count: int) -> str:
    """Improving-tile count; teaches ukeire for beginners."""
    return _glossed_acceptances(count)


def _dora_in_hand_sentence() -> str:
    if term_is_known("dora"):
        return "You have dora in hand"
    return "You have dora (bonus tile) in hand"


@dataclass(frozen=True)
class SubstanceScore:
    """Offline/runtime substance metric for Why? summaries."""

    thin: bool
    anchors: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _wall_facts_available(turn: TurnExplainInput) -> bool:
    remaining = turn.features.ukeire.remaining_by_tile
    if remaining and any(n <= 1 for n in remaining.values()):
        return True
    alt = turn.features.ukeire_alt
    if alt is not None and turn.features.ukeire.count - alt.count >= 3:
        return True
    return False


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
        or re.search(r"\bleft in the wall\b", summary_l)
        or re.search(r"\blive acceptances?\b", summary_l)
        or re.search(r"\bimproving tiles\b", summary_l)
        or re.search(r"\b\d+\s*[×x]\b", summary_l)
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

    for goal in coaching_shape_goals(turn):
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


def score_explanation_substance(turn: TurnExplainInput, summary: str) -> SubstanceScore:
    """Score whether a Why? summary cites hand facts or only tautological efficiency."""
    summary_l = summary.lower()
    anchors = _feature_anchors_in_summary(turn, summary_l)
    has_thin_claim = any(p.search(summary_l) for p in _THIN_CLAIM_PATTERNS)
    thin = (
        _turn_has_usable_anchors(turn)
        and not anchors
        and has_thin_claim
    )
    issues = ["thin_efficiency_claim"] if thin else []
    return SubstanceScore(thin=thin, anchors=anchors, issues=issues)


def _wall_note_detail(turn: TurnExplainInput) -> tuple[str | None, str | None]:
    """Return (kind, text): kind is 'contrast' | 'thin', or (None, None)."""
    ukeire = turn.features.ukeire
    remaining = ukeire.remaining_by_tile
    thin = [(t, n) for t, n in remaining.items() if n <= 1]
    alt = turn.features.ukeire_alt

    if alt is not None and ukeire.count - alt.count >= 3:
        if turn.diverge and turn.player_action != turn.mortal_best:
            alt_action = turn.player_action
        else:
            alt_action = next_best_action(turn)
        alt_label = human_action_label(alt_action) if alt_action else "the alternate cut"
        return (
            "contrast",
            (
                f"about {ukeire.count} improving tiles left vs about {alt.count} "
                f"if you throw {alt_label}"
            ),
        )

    if thin:
        thin.sort(key=lambda x: (x[1], x[0]))
        tile, n = thin[0]
        label = human_tile_label(tile)
        detail = f"{label} already out" if n <= 0 else f"only {n}× {label} left"
        if len(thin) >= 2:
            return "thin", f"several improving tiles are already out ({detail})"
        return "thin", f"improving tiles are thinning ({detail})"

    return None, None


def wall_note(turn: TurnExplainInput) -> str | None:
    """Short grounded wall-depletion / improving-tile contrast, or None if not meaningful."""
    _kind, text = _wall_note_detail(turn)
    return text


def _score_tips_enabled(turn: TurnExplainInput) -> bool:
    """Opt-in point-situation tips (default off for beginners)."""
    return bool(turn.features.context.get("include_score_tips"))


def _known_terms_from_turn(turn: TurnExplainInput) -> frozenset[str]:
    raw = turn.features.context.get("known_terms")
    if isinstance(raw, (list, tuple, set, frozenset)):
        return normalize_known_terms(raw)
    return frozenset()


def _turn_with_coach_prefs(
    turn: TurnExplainInput,
    *,
    include_score_tips: bool,
    known_terms: Collection[str] | None,
) -> TurnExplainInput:
    """Stamp include_score_tips + known_terms onto features.context."""
    known = normalize_known_terms(known_terms)
    want_score = bool(include_score_tips)
    cur_score = bool(turn.features.context.get("include_score_tips"))
    cur_known = _known_terms_from_turn(turn)
    if cur_score is want_score and cur_known == known:
        return turn
    ctx = dict(turn.features.context)
    ctx["include_score_tips"] = want_score
    ctx["known_terms"] = sorted(known)
    return turn.model_copy(
        update={"features": turn.features.model_copy(update={"context": ctx})}
    )


def _filter_glossary(mapping: dict[str, str], known: frozenset[str]) -> dict[str, str]:
    """Drop glossary entries the player marked known (and ukeire/acceptances aliases)."""
    out: dict[str, str] = {}
    for key, gloss in mapping.items():
        if term_is_known(key, known):
            continue
        out[key] = gloss
    return out


def build_user_payload(turn: TurnExplainInput) -> dict[str, Any]:
    scores = {
        c.action: {"q_value": c.q_value, "prob": c.prob}
        for c in turn.mortal_output.candidates[:8]
    }
    next_best = next_best_action(turn)
    note = wall_note(turn)
    call_decision = is_call_decision_turn(turn)
    riichi_decision = is_riichi_decision_turn(turn)
    hora_decision = is_hora_decision_turn(turn)
    coach_labels = call_decision or riichi_decision or hora_decision
    known = _known_terms_from_turn(turn)

    def _display(action: str) -> str:
        if riichi_decision and action.strip() == "none":
            return "Stay silent"
        if coach_labels:
            return coach_action_label(action)
        return human_action_label(action)

    def _shanten_glossary() -> str:
        sh = turn.features.shanten
        if sh == -1:
            return "winning hand"
        if sh <= 0:
            return "ready"
        step = "step" if sh == 1 else "steps"
        return f"{sh} {step} from ready"

    reach_discard = turn.features.context.get("reach_discard")
    if reach_discard:
        reach_discard = normalize_tile(str(reach_discard))

    score_situation = None
    if _score_tips_enabled(turn) and turn.features.score_situation is not None:
        score_situation = turn.features.score_situation.model_dump()

    shape_goal_glossary = _filter_glossary(
        {
            **{
                g: _GOAL_GLOSS[g]
                for g in coaching_shape_goals(turn)
                if g in _GOAL_GLOSS
            },
            "dora": _DORA_GLOSS,
        },
        known,
    )
    wait_raw = (
        {turn.features.statuses.wait_shape: _WAIT_GLOSS[turn.features.statuses.wait_shape]}
        if turn.features.statuses.wait_shape in _WAIT_GLOSS
        else {}
    )
    hand_metric_glossary = _filter_glossary(
        {
            "shanten": _shanten_glossary(),
            "ukeire": _UKEIRE_GLOSS,
            "acceptances": _ACCEPTANCES_GLOSS,
        },
        known,
    )
    # Shanten / tenpai keys: drop shanten gloss text when shanten known; drop when tenpai known and ready.
    if term_is_known("shanten", known) and turn.features.shanten not in (-1, 0, None):
        hand_metric_glossary.pop("shanten", None)
    if term_is_known("tenpai", known) and (
        turn.features.shanten is not None and turn.features.shanten <= 0
    ):
        hand_metric_glossary.pop("shanten", None)

    return {
        "player_action": turn.player_action,
        "mortal_best": turn.mortal_best,
        "next_best": next_best,
        "player_action_display": _display(turn.player_action),
        "mortal_best_display": _display(turn.mortal_best),
        "next_best_display": _display(next_best) if next_best else None,
        "diverge": turn.diverge,
        "call_decision": call_decision,
        "riichi_decision": riichi_decision,
        "hora_decision": hora_decision,
        "reach_discard": reach_discard,
        "reach_discard_display": (
            human_tile_label(reach_discard) if reach_discard else None
        ),
        "mortal_scores": scores,
        "hand": turn.game_state.hand,
        "tile_glossary": _tile_glossary_for_turn(turn, next_best),
        "shanten": turn.features.shanten,
        "ukeire": turn.features.ukeire.model_dump(),
        "ukeire_alt": (
            turn.features.ukeire_alt.model_dump()
            if turn.features.ukeire_alt is not None
            else None
        ),
        "wall_note": note,
        "statuses": turn.features.statuses.model_dump(),
        "shape_goals": coaching_shape_goals(turn),
        "hand_shape_notes": [
            n.model_dump() for n in turn.features.hand_shape_notes
        ],
        "hand_shape_note_glossary": _filter_glossary(
            {
                n.kind: _SHAPE_NOTE_GLOSS[n.kind]
                for n in turn.features.hand_shape_notes
                if n.kind in _SHAPE_NOTE_GLOSS
            },
            known,
        ),
        "shape_goal_glossary": shape_goal_glossary,
        "wait_shape_glossary": _filter_glossary(wait_raw, known),
        "hand_metric_glossary": hand_metric_glossary,
        "call_tradeoff": (
            turn.features.call_tradeoff.model_dump()
            if turn.features.call_tradeoff is not None
            else None
        ),
        "score_situation": score_situation,
        "danger": turn.features.danger,
        "danger_detail": turn.features.danger_detail,
        "danger_glossary": _filter_glossary(
            {
                tag: _DANGER_GLOSS[tag]
                for tag in sorted(set(turn.features.danger.values()))
                if tag in _DANGER_GLOSS
            },
            known,
        ),
        "context": turn.features.context,
        "yakuhai_pairs": _yakuhai_pair_labels(
            turn.game_state.hand, turn.features.context
        ),
        "yakuhai_singleton_value_tiles": _yakuhai_singleton_value_labels(
            turn.game_state.hand, turn.features.context
        ),
        "furiten_blocking_tiles": [
            human_tile_label(t) for t in _furiten_blocking_tiles(turn)
        ],
    }


def _tile_glossary_for_turn(
    turn: TurnExplainInput, next_best: str | None
) -> dict[str, str]:
    """mjai code → human label for tiles relevant to this turn."""
    codes: set[str] = set()
    for tile in turn.game_state.hand:
        codes.add(normalize_tile(tile))
    for action in (turn.player_action, turn.mortal_best, next_best):
        token = _action_tile_token_raw(action) if action else None
        if token:
            codes.add(normalize_tile(token))
    for cand in turn.mortal_output.candidates[:8]:
        token = _action_tile_token_raw(cand.action)
        if token:
            codes.add(normalize_tile(token))
    return {code: human_tile_label(code) for code in sorted(codes)}


def _action_display(action: str) -> str:
    return human_action_label(action)


def _action_tile_token_raw(action: str | None) -> str | None:
    if not action:
        return None
    return action_tile_arg(action)


def _danger_key(tile: str | None) -> str | None:
    if not tile:
        return None
    return deaka(normalize_tile(tile))


_HONORS = frozenset({"E", "S", "W", "N", "P", "F", "C"})
_DRAGONS = frozenset({"P", "F", "C"})
_WINDS = frozenset({"E", "S", "W", "N"})
_HONOR_ORDER = ("E", "S", "W", "N", "P", "F", "C")


def _is_terminal_or_honor(tile: str) -> bool:
    base = deaka(normalize_tile(tile))
    if base in _HONORS:
        return True
    return len(base) >= 2 and base[0] in "19" and base[1] in "mps"


def _sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _join_sentence_list(sentences: list[str]) -> str:
    if not sentences:
        return ""
    return ". ".join(s.rstrip(".") for s in sentences) + "."


def _join_summary_paragraphs(first: list[str], second: list[str]) -> str:
    """Join two sentence groups; insert a newline between non-empty paragraphs."""
    a = _join_sentence_list(first)
    b = _join_sentence_list(second)
    if a and b:
        return f"{a}\n{b}"
    return a or b


def _format_tile_list(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _named_improving_tiles_sentence(turn: TurnExplainInput) -> str | None:
    """Name example improving tiles when ukeire contrast is large."""
    ukeire = turn.features.ukeire
    alt = turn.features.ukeire_alt
    if alt is None or ukeire.count - alt.count < 3:
        return None
    if len(ukeire.tiles) < 2:
        return None
    best_raw = _action_tile_token_raw(turn.mortal_best)
    alt_action = _contrast_alt_action(turn)
    alt_raw = _action_tile_token_raw(alt_action) if alt_action else None
    best_label = human_tile_label(best_raw) if best_raw else "this cut"
    alt_label = human_tile_label(alt_raw) if alt_raw else "the alternate"
    best_named = _format_tile_list(
        [human_tile_label(t) for t in ukeire.tiles[:4]]
    )
    lead = f"Throwing {best_label} keeps draws like {best_named}"
    if alt.tiles and len(alt.tiles) >= 2:
        alt_named = _format_tile_list(
            [human_tile_label(t) for t in alt.tiles[:4]]
        )
        return f"{lead}; throwing {alt_label} mostly improves via {alt_named}"
    return lead


def _thin_wall_sentence(turn: TurnExplainInput) -> str | None:
    """Thin-wall note when key improving tiles are nearly exhausted."""
    ukeire = turn.features.ukeire
    remaining = ukeire.remaining_by_tile
    thin_in_ukeire = [
        (t, n) for t, n in remaining.items() if n <= 1 and t in ukeire.tiles
    ]
    if not thin_in_ukeire:
        return None
    thin_in_ukeire.sort(key=lambda x: (x[1], x[0]))
    tile, n = thin_in_ukeire[0]
    label = human_tile_label(tile)
    detail = f"{label} already out" if n <= 0 else f"only {n}× {label} left"
    if len(thin_in_ukeire) >= 2:
        return f"Several improving tiles are already out ({detail})"
    return f"Improving tiles are thinning ({detail})"


_UKEIRE_CITED_IN_SUMMARY_RE = re.compile(
    r"\b(?:improving tiles?|acceptances?|ukeire|"
    r"tiles that can improve(?:\s+(?:your\s+)?hand)?|"
    r"tiles that improve(?:\s+(?:the|your)\s+hand)?)\b",
    re.IGNORECASE,
)


def _merge_detail_into_summary(summary: str, detail: str | None) -> str:
    """Append grounded detail sentences not already covered in summary."""
    if not detail:
        return summary
    summary_l = summary.lower()
    has_defense = bool(
        re.search(
            r"\b(?:genbutsu|suji|one-chance|already discarded|can't ron|cant ron)\b",
            summary_l,
        )
    )
    has_ukeire = bool(_UKEIRE_CITED_IN_SUMMARY_RE.search(summary_l))
    extras: list[str] = []
    for chunk in detail.rstrip(".").split(". "):
        chunk = chunk.strip()
        if not chunk:
            continue
        chunk_l = chunk.lower()
        if chunk_l in summary_l:
            continue
        probe = chunk[:40].lower()
        if probe in summary_l:
            continue
        # Don't restate Mortal's pick or echo Hand-stats metrics onto defense tips.
        if re.search(r"\bmortal['\u2019]?s cut\b", chunk_l) and (
            has_defense or has_ukeire
        ):
            continue
        if re.search(
            r"\bis (?:genbutsu|suji|one-chance)\b",
            chunk_l,
        ) and has_defense:
            continue
        if has_ukeire and re.search(r"\bimproving tiles?\b", chunk_l):
            continue
        # Skip goal/shape leftovers already named in summary.
        if chunk_l.startswith("target:"):
            continue
        goal_tokens = ("tanyao", "pinfu", "yakuhai", "chiitoi", "honitsu", "chinitsu")
        if any(g in chunk_l for g in goal_tokens) and any(
            g in summary_l for g in goal_tokens
        ):
            continue
        extras.append(chunk)
    if not extras:
        return summary
    merged = _join_sentence_list(extras)
    if "\n" in summary:
        return f"{summary}\n{merged}"
    return f"{summary}\n{merged}"


def _hora_winning_tile(turn: TurnExplainInput) -> str | None:
    """Tile to win on at a hora prompt (ron discard or sole wait)."""
    raw = turn.mortal_output.raw_expected
    if isinstance(raw, dict):
        pai = raw.get("pai")
        if pai:
            return normalize_tile(str(pai))

    waits = turn.features.ukeire.tiles
    if len(waits) == 1:
        return normalize_tile(waits[0])

    wait_set = {deaka(normalize_tile(w)) for w in waits}
    for river in turn.game_state.visible_discards.values():
        if not river:
            continue
        last = deaka(normalize_tile(river[-1]))
        if last in wait_set:
            return normalize_tile(river[-1])
    return None


def build_detail_paragraph(turn: TurnExplainInput) -> str | None:
    """One extra grounded paragraph for the second-click deeper Why? path."""
    bits: list[str] = []

    ukeire = turn.features.ukeire
    alt = turn.features.ukeire_alt
    if alt is not None and ukeire.count != alt.count:
        bits.append(
            f"Mortal’s cut leaves about {ukeire.count} improving tiles "
            f"vs about {alt.count} on the alternative"
        )

    statuses = turn.features.statuses
    if is_hora_decision_turn(turn):
        if len(turn.game_state.hand) < 14:
            tile = _hora_winning_tile(turn)
            if tile:
                labels = human_tile_label(tile)
            elif ukeire.tiles:
                labels = ", ".join(
                    human_tile_label(t) for t in ukeire.tiles[:6]
                )
            else:
                labels = None
            if labels:
                wait_label = _glossed_wait(statuses.wait_shape)
                if wait_label:
                    bits.append(f"Win on {labels} ({wait_label})")
                else:
                    bits.append(f"Win on {labels}")
    elif statuses.tenpai and ukeire.tiles:
        labels = ", ".join(human_tile_label(t) for t in ukeire.tiles[:6])
        wait_label = _glossed_wait(statuses.wait_shape)
        if wait_label:
            bits.append(f"Waiting on {labels} ({wait_label})")
        else:
            bits.append(f"Waiting on {labels}")

    # Cut-only danger — never catalogue other hand tiles' tags.
    best_code = _danger_key(_action_tile_token_raw(turn.mortal_best))
    danger = turn.features.danger
    if best_code and best_code in danger:
        tag = danger[best_code]
        glossed = _glossed_danger(tag) or tag
        bits.append(f"{human_tile_label(best_code)} is {glossed}")

    for note in turn.features.hand_shape_notes[:2]:
        gloss = _SHAPE_NOTE_GLOSS.get(note.kind)
        if not gloss:
            continue
        if term_is_known(note.kind):
            bits.append(f"{human_tile_label(note.tile)} — {note.kind}")
        else:
            bits.append(f"{human_tile_label(note.tile)} — {gloss}")

    if _score_tips_enabled(turn):
        ss = turn.features.score_situation
        if ss is not None:
            score_bits: list[str] = []
            if ss.riichi_opponents:
                n = ss.riichi_opponents
                score_bits.append(
                    f"{n} opponent{'s' if n != 1 else ''} in riichi"
                )
            if ss.score_diff:
                score_bits.append(f"you’re {ss.score_diff} on points")
            if ss.late_game:
                score_bits.append("late game / thin wall")
            if score_bits:
                bits.append("; ".join(score_bits))

    if not bits:
        return None
    return ". ".join(s.rstrip(".") for s in bits) + "."


def _finalize_explanation(
    turn: TurnExplainInput, explanation: Explanation
) -> Explanation:
    """Merge grounded detail into summary; keep detail for review API."""
    detail = build_detail_paragraph(turn)
    summary_l = explanation.summary.lower()
    # Omit cut danger from detail when the summary already teaches it.
    if detail and re.search(
        r"\b(?:genbutsu|suji|one-chance|already discarded|can't ron|cant ron)\b",
        summary_l,
    ):
        best_code = _danger_key(_action_tile_token_raw(turn.mortal_best))
        if best_code:
            cut_label = human_tile_label(best_code).lower()
            kept: list[str] = []
            for chunk in detail.rstrip(".").split(". "):
                chunk = chunk.strip()
                if not chunk:
                    continue
                chunk_l = chunk.lower()
                if cut_label and cut_label in chunk_l and re.search(
                    r"\bis (?:genbutsu|suji|one-chance)\b",
                    chunk_l,
                ):
                    continue
                kept.append(chunk)
            detail = (
                ". ".join(s.rstrip(".") for s in kept) + "." if kept else None
            )
    summary = _merge_detail_into_summary(explanation.summary, detail)
    summary = _ensure_tile_emojis(summary, turn)
    return explanation.model_copy(update={"summary": summary, "detail": detail})


def _tile_name_without_emoji(tile: str) -> str:
    """English name from human_tile_label, stripping the leading mahjong glyph."""
    label = human_tile_label(tile)
    if label and ord(label[0]) >= 0x1F000:
        return label[1:]
    return label


def _bare_tile_patterns(tile: str) -> list[str]:
    """Regexes matching bare (no-glyph) mentions of a tile, longest first."""
    code = normalize_tile(tile)
    name = _tile_name_without_emoji(code)
    patterns: list[str] = []
    if name:
        aka_m = re.fullmatch(r"red 5-(man|pin|sou)", name, flags=re.IGNORECASE)
        suit_m = re.fullmatch(r"([1-9])-(man|pin|sou)", name, flags=re.IGNORECASE)
        if aka_m:
            suit = aka_m.group(1).lower()
            patterns.append(rf"\bred\s+5-{suit}\b")
            patterns.append(rf"\bred\s+5\s+{suit}\b")
            patterns.append(rf"\bred\s+5{suit}\b")
        elif suit_m:
            num, suit = suit_m.group(1), suit_m.group(2).lower()
            # Don't rewrite the "5-sou" inside an aka "red 5-sou" label.
            red_guard = r"(?<!red )" if num == "5" else ""
            patterns.append(rf"{red_guard}\b{num}-{suit}\b")
            patterns.append(rf"{red_guard}\b{num}\s+{suit}\b")
            patterns.append(rf"{red_guard}\b{num}{suit}\b")
            patterns.append(rf"{red_guard}\b{num}{suit[0]}\b")
        else:
            patterns.append(rf"\b{re.escape(name)}\b")
    patterns.append(rf"\b{re.escape(code)}\b")
    # Dedupe while preserving order; longer aliases first.
    seen: set[str] = set()
    ordered: list[str] = []
    for pat in sorted(patterns, key=len, reverse=True):
        if pat not in seen:
            seen.add(pat)
            ordered.append(pat)
    return ordered


def _ensure_tile_emojis(text: str, turn: TurnExplainInput) -> str:
    """Rewrite bare tile names to emoji+name labels (e.g. 2-man → 🀈2-man)."""
    if not text:
        return text
    next_best = next_best_action(turn)
    codes = set(_tile_glossary_for_turn(turn, next_best))
    reach_discard = (turn.features.context or {}).get("reach_discard")
    if isinstance(reach_discard, str) and reach_discard.strip():
        codes.add(normalize_tile(reach_discard))
    ordered = sorted(
        codes,
        key=lambda c: len(human_tile_label(c)),
        reverse=True,
    )
    for code in ordered:
        label = human_tile_label(code)
        if not label or label == code:
            continue
        emoji = label[0] if ord(label[0]) >= 0x1F000 else ""
        if not emoji:
            continue
        for pat in _bare_tile_patterns(code):
            text = re.sub(
                rf"(?<!{re.escape(emoji)})(?:{pat})",
                label,
                text,
                flags=re.IGNORECASE,
            )
    return text


def _yakuhai_value_tiles(context: dict[str, Any] | None) -> set[str]:
    """Dragons plus seat/round winds when context provides them."""
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


def _yakuhai_pair_labels(
    hand: list[str], context: dict[str, Any] | None
) -> list[str]:
    """Human labels for yakuhai-capable tiles held as a pair or triplet."""
    value = _yakuhai_value_tiles(context)
    counts = _hand_tile_counts(hand)
    return [
        human_tile_label(tile)
        for tile in _HONOR_ORDER
        if tile in value and counts.get(tile, 0) >= 2
    ]


def _yakuhai_singleton_value_labels(
    hand: list[str], context: dict[str, Any] | None
) -> list[str]:
    """Human labels for yakuhai-capable tiles held as a singleton."""
    value = _yakuhai_value_tiles(context)
    counts = _hand_tile_counts(hand)
    return [
        human_tile_label(tile)
        for tile in _HONOR_ORDER
        if tile in value and counts.get(tile, 0) == 1
    ]


def _yakuhai_because_clause(
    turn: TurnExplainInput,
    best_raw: str | None,
    alt_raw: str | None,
) -> str | None:
    """Short em-dash clause naming which tiles support the yakuhai shape."""
    if "yakuhai" not in turn.features.shape_goals:
        return None
    hand = turn.game_state.hand
    context = turn.features.context
    value = _yakuhai_value_tiles(context)
    counts = _hand_tile_counts(hand)
    held: list[str] = []
    for tile in _HONOR_ORDER:
        if tile not in value:
            continue
        n = counts.get(tile, 0)
        if n >= 3:
            held.append(f"a triplet of {human_tile_label(tile)}")
        elif n >= 2:
            held.append(f"a pair of {human_tile_label(tile)}")
    if not held:
        return None
    if len(held) == 1:
        bits = [f"you’re holding {held[0]} for that"]
    else:
        bits = [f"you’re holding {' and '.join(held)} for that"]
    if best_raw:
        best_norm = deaka(normalize_tile(best_raw))
        if best_norm not in value:
            bits.append(f"{human_tile_label(best_raw)} isn’t a value tile")
    if alt_raw:
        alt_norm = deaka(normalize_tile(alt_raw))
        if alt_norm in value:
            label = human_tile_label(alt_raw)
            n = counts.get(alt_norm, 0)
            if n >= 2:
                bits.append(f"while {label} is already a pair")
            elif n >= 1:
                bits.append(f"while {label} can still pair")
    return "—" + "; ".join(bits)


def _furiten_blocking_tiles(turn: TurnExplainInput) -> list[str]:
    """Wait tiles already in the player's discard river (mjai codes)."""
    waits = {deaka(normalize_tile(w)) for w in turn.features.ukeire.tiles}
    if not waits:
        return []
    discards = {deaka(normalize_tile(d)) for d in turn.game_state.discards}
    return sorted(waits & discards)


def _furiten_because_sentence(turn: TurnExplainInput) -> str | None:
    """Name discarded wait tiles; ron blocked on every wait (tsumo only)."""
    statuses = turn.features.statuses
    if statuses.temporary_furiten and not statuses.furiten:
        return (
            "You’re temporarily furiten—you passed on a win this turn—so you "
            "can’t ron until after your next discard"
        )
    if not statuses.furiten:
        return None
    labels = [human_tile_label(t) for t in _furiten_blocking_tiles(turn)]
    if not labels:
        return (
            "You’re furiten—you already discarded a wait tile—so you can’t "
            "win on any discard (only tsumo)"
        )
    named = labels[0] if len(labels) == 1 else " and ".join(labels)
    return (
        f"You’re furiten—you already discarded {named}, so you can’t win "
        "on any discard (only tsumo)"
    )


def _note_for_cut(turn: TurnExplainInput, cut_raw: str | None):
    """Hand-shape note matching Mortal's cut tile, if any."""
    if not cut_raw or not turn.features.hand_shape_notes:
        return None
    try:
        cut = deaka(normalize_tile(cut_raw))
    except ValueError:
        return None
    for note in turn.features.hand_shape_notes:
        try:
            if deaka(normalize_tile(note.tile)) == cut:
                return note
        except ValueError:
            continue
    return turn.features.hand_shape_notes[0]


def _midhand_shape_clause(
    turn: TurnExplainInput,
    cut_raw: str | None,
    cut_label: str,
) -> str | None:
    """Short clause/sentence for floating / isolated / dead-end cuts."""
    note = _note_for_cut(turn, cut_raw)
    if note is None:
        return None
    goals = [g for g in turn.features.shape_goals if g]
    primary = goals[0] if goals else None
    if note.kind == "floating_terminal":
        if primary:
            return (
                f"{cut_label} is a floating terminal outside "
                f"{_glossed_goal(primary)}"
            )
        return f"{cut_label} is a floating terminal"
    if note.kind == "floating_honor":
        if primary:
            return (
                f"{cut_label} is a floating honor outside "
                f"{_glossed_goal(primary)}"
            )
        return f"{cut_label} is a floating honor"
    if note.kind == "isolated_kanchan":
        return f"{cut_label} clears a closed middle (kanchan) shape"
    if note.kind == "isolated_penchan":
        return f"{cut_label} clears an edge (penchan) shape"
    if note.kind == "dead_end":
        return f"{cut_label} is a dead-end tile"
    return None


def _shape_goal_phrase(turn: TurnExplainInput) -> str | None:
    """Human phrase for heuristic shape goals (+ dora when present)."""
    goals = coaching_shape_goals(turn)
    dora = turn.features.statuses.dora_in_hand
    if not goals and not dora:
        return None
    if goals:
        lean = " / ".join(_glossed_goal(g) for g in goals)
        if dora:
            return f"fits {lean} with {_glossed_dora_phrase(human_tile_label(dora[0]))}"
        return f"fits {lean}"
    # Dora only — still useful value signal
    return f"keeping {_glossed_dora_phrase(human_tile_label(dora[0]))}"


def _call_skip_lead(call_action: str | None) -> str:
    """Lead sentence when Mortal prefers Skip over a call."""
    if not call_action:
        return "Skip"
    kind = parse_action_kind(call_action)
    tile = action_tile_arg(call_action)
    if kind == "pon":
        if tile:
            return f"Skip the pon on {human_tile_label(tile)}"
        return "Skip the pon"
    if kind == "chi":
        if tile:
            return f"Skip the chi on {human_tile_label(tile)}"
        return "Skip the chi"
    if kind == "kan":
        if tile:
            return f"Skip the kan on {human_tile_label(tile)}"
        return "Skip the kan"
    return "Skip"


def _hand_has_terminals_or_honors(hand: list[str]) -> bool:
    return any(_is_terminal_or_honor(t) for t in hand)


def _score_situation_sentence(turn: TurnExplainInput) -> tuple[str | None, Focus | None]:
    """At most one point-situation sentence; optional focus nudge."""
    if not _score_tips_enabled(turn):
        return None, None
    sit = turn.features.score_situation
    if sit is None:
        return None, None

    best_code = _danger_key(_action_tile_token_raw(turn.mortal_best))
    best_tag = turn.features.danger.get(best_code) if best_code else None
    best_safe = danger_rank(best_tag) > 0

    if sit.riichi_opponents > 0:
        if sit.score_diff == "leading" and best_safe:
            return (
                "You’re ahead and an opponent is in riichi—"
                "prefer the safer cut over chasing efficiency",
                "defense",
            )
        return (
            "An opponent is in riichi—"
            f"fold toward safer tiles even if {_glossed_ukeire()} drops",
            "defense",
        )

    if sit.late_game and sit.score_diff == "trailing":
        if is_riichi_decision_action(turn.mortal_best):
            return (
                "You’re behind late—"
                "this riichi fights for points instead of playing safe",
                "value",
            )
        return (
            "You’re behind late—"
            "aim for value and speed over slow safe builds",
            "value",
        )

    if sit.late_game and sit.score_diff == "leading" and best_safe:
        return (
            "You’re ahead late—"
            "safer cuts protect the lead even if they leave fewer improving tiles",
            "defense",
        )

    if sit.late_game and sit.score_diff == "even" and best_safe:
        return (
            "Scores are close late—"
            "avoid needless deal-in risk when a safer cut exists",
            "defense",
        )

    return None, None


def _append_score_situation(
    sentences: list[str], focus: Focus, turn: TurnExplainInput
) -> Focus:
    bit, nudge = _score_situation_sentence(turn)
    if not bit:
        return focus
    sentences.append(bit)
    if nudge is None:
        return focus
    if focus == "efficiency":
        return nudge
    if nudge != focus:
        return "mixed"
    return focus


def _riichi_opponent_seats(turn: TurnExplainInput) -> set[str]:
    """Absolute seat ids in riichi, excluding self when self_seat is known."""
    flags = turn.game_state.riichi_flags
    if not flags:
        return set()
    self_seat = turn.features.context.get("self_seat")
    if self_seat is None:
        return set()
    self_s = str(self_seat)
    return {
        str(i)
        for i, reached in enumerate(flags)
        if reached and str(i) != self_s
    }


def _genbutsu_discarder_seats(
    turn: TurnExplainInput, tile_code: str
) -> list[str]:
    """Opponent seats that discarded tile (from danger_detail or rivers)."""
    detail = turn.features.danger_detail.get(tile_code) or {}
    seats = detail.get("seats")
    if isinstance(seats, list) and seats:
        return [str(s) for s in seats]
    # Also try deaka key
    base = deaka(normalize_tile(tile_code))
    detail = turn.features.danger_detail.get(base) or {}
    seats = detail.get("seats")
    if isinstance(seats, list) and seats:
        return [str(s) for s in seats]
    exclude = turn.features.context.get("self_seat")
    return genbutsu_discarders(
        tile_code,
        turn.game_state.visible_discards,
        exclude_seat=exclude,
    )


def _genbutsu_teaching_sentence(
    turn: TurnExplainInput,
    tile_code: str,
    tile_label: str,
) -> str:
    """Beginner teaching clause for a genbutsu cut."""
    discarders = set(_genbutsu_discarder_seats(turn, tile_code))
    riichi_opps = _riichi_opponent_seats(turn)
    if discarders and (discarders & riichi_opps):
        return (
            f"The riichi player already discarded {tile_label}, "
            f"so they can't ron it"
        )
    return (
        f"An opponent already discarded {tile_label}, "
        f"so they can't ron it from you"
    )


def _suji_teaching_sentence(tile_label: str) -> str:
    return (
        f"{tile_label} is suji—if someone waited on the edge tiles in that "
        f"suit, they'd likely have discarded {tile_label} already"
    )


def _one_chance_teaching_sentence(tile_label: str) -> str:
    return (
        f"{tile_label} is one-chance—the middle tile is nearly all out, "
        f"so a closed middle wait is unlikely"
    )


def _danger_teaching_sentence(
    turn: TurnExplainInput,
    tag: str,
    tile_code: str | None,
    tile_label: str,
) -> str:
    if tag == "genbutsu" and tile_code:
        return _genbutsu_teaching_sentence(turn, tile_code, tile_label)
    if tag == "suji":
        return _suji_teaching_sentence(tile_label)
    if tag == "one-chance":
        return _one_chance_teaching_sentence(tile_label)
    glossed = _glossed_danger(tag) or tag
    return f"{tile_label} is {glossed}"


def _danger_compare_sentences(
    turn: TurnExplainInput,
    *,
    best_tile: str,
    player_tile: str,
    best_code: str | None,
    player_code: str | None,
    player: str,
    best: str,
) -> tuple[list[str], Focus | None]:
    """Defense sentences from danger tag ranks; optional focus nudge."""
    danger = turn.features.danger
    best_tag = danger.get(best_code) if best_code else None
    player_tag = danger.get(player_code) if player_code else None
    best_r = danger_rank(best_tag)
    player_r = danger_rank(player_tag)
    out: list[str] = []
    nudge: Focus | None = None

    if best_r > player_r and best_tag:
        if best_tag in ("genbutsu", "suji", "one-chance") and best_code:
            out.append(
                _danger_teaching_sentence(
                    turn, best_tag, best_code, best_tile
                )
            )
        else:
            glossed = _glossed_danger(best_tag) or best_tag
            if player != best and player_code:
                out.append(f"{best_tile} is {glossed}. {player_tile} isn't")
            else:
                out.append(f"{best_tile} is {glossed}")
        nudge = "defense"
    elif player_tag and player != best and player_r >= best_r:
        # Safer alt than Mortal's cut: omit — don't teach genbutsu/suji on the
        # non-cut or say "efficiency is worse". Defense copy is cut-only;
        # efficiency/shape reasons lead once defense_led stays false.
        pass
    elif best_tag:
        if best_tag in ("genbutsu", "suji", "one-chance") and best_code:
            out.append(
                _danger_teaching_sentence(
                    turn, best_tag, best_code, best_tile
                )
            )
        else:
            glossed = _glossed_danger(best_tag) or best_tag
            out.append(f"{best_tile} is also {glossed}")
        nudge = "defense"

    return out, nudge


def _template_explain_call(turn: TurnExplainInput) -> Explanation:
    """Skip / Call coach voice with open-vs-closed tradeoffs."""
    best = turn.mortal_best
    player = turn.player_action
    shanten = turn.features.shanten
    ukeire = turn.features.ukeire
    tradeoff = turn.features.call_tradeoff
    alt = next_best_action(turn)

    focus: Focus = "efficiency"
    move_sents: list[str] = []
    state_sents: list[str] = []
    contrasted: str | None = None

    if turn.diverge and player != best:
        contrasted = player
    elif alt and alt != best:
        contrasted = alt

    best_kind = parse_action_kind(best)
    call_side = None
    if is_call_action(best):
        call_side = best
    elif contrasted and is_call_action(contrasted):
        call_side = contrasted
    elif tradeoff is not None:
        call_side = tradeoff.call_action

    if best_kind == "none":
        move_sents.append(_call_skip_lead(call_side))
    else:
        label = coach_action_label(best)
        if contrasted and parse_action_kind(contrasted) == "none":
            move_sents.append(f"{label}, don’t skip")
        else:
            move_sents.append(label)

    # Bundled shanten + improving-tile count stays with the move paragraph.
    if shanten is not None:
        move_sents.append(
            f"You’re {_glossed_shanten_phrase(shanten)} closed with "
            f"about {ukeire.count} improving tiles"
        )

    if best_kind == "none":
        if tradeoff is not None and tradeoff.opens_hand:
            open_note = "Calling would open the hand—no riichi"
            if (
                tradeoff.open_ukeire_count is not None
                and tradeoff.open_ukeire_count < tradeoff.stay_closed_ukeire
            ):
                open_note += (
                    f", and only about {tradeoff.open_ukeire_count} tiles would "
                    f"still improve it vs about {tradeoff.stay_closed_ukeire} closed"
                )
            elif (
                tradeoff.open_shanten is not None
                and tradeoff.open_shanten >= tradeoff.stay_closed_shanten
            ):
                open_note += ", and it doesn’t get you closer to ready"
            state_sents.append(open_note)
        if shanten is not None and shanten > 0:
            state_sents.append("You’re not in tenpai yet and can still improve closed")
        if "tanyao" in turn.features.shape_goals and _hand_has_terminals_or_honors(
            turn.game_state.hand
        ):
            state_sents.append(
                f"You’re still aiming for {_glossed_goal('tanyao')} and holding terminals"
            )
        else:
            goal_bit = _shape_goal_phrase(turn)
            if goal_bit:
                if goal_bit.startswith("fits"):
                    state_sents.append(f"That {goal_bit}")
                else:
                    state_sents.append(_sentence_case(goal_bit))
    else:
        tile = action_tile_arg(best)
        dragons = frozenset({"P", "F", "C"})
        coached_goals = coaching_shape_goals(turn)
        if parse_action_kind(best) == "pon" and tile and (
            "yakuhai" in coached_goals or tile in dragons
        ):
            state_sents.append(
                "That locks a yakuhai triplet for a guaranteed yaku when you win"
            )
            focus = "value"
        if parse_action_kind(best) == "chi" and (
            tradeoff is not None
            and tradeoff.open_shanten is not None
            and tradeoff.open_shanten < tradeoff.stay_closed_shanten
        ):
            state_sents.append("That completes a sequence and gets you closer open")
        if (
            tradeoff is not None
            and tradeoff.open_shanten is not None
            and tradeoff.open_shanten < tradeoff.stay_closed_shanten
        ):
            state_sents.append(
                f"That drops you to {_glossed_shanten_phrase(tradeoff.open_shanten)} open"
            )
            if focus == "efficiency":
                focus = "tempo"
        dropped_closed = recommending_open_call(turn) and any(
            g in CLOSED_ONLY_GOALS for g in turn.features.shape_goals
        )
        if dropped_closed and tradeoff is not None and tradeoff.opens_hand:
            if not any("open" in s.lower() for s in state_sents):
                state_sents.append("That opens the hand—no riichi")
        goal_bit = _shape_goal_phrase(turn)
        if goal_bit:
            if goal_bit.startswith("fits"):
                state_sents.append(f"That {goal_bit}")
            else:
                state_sents.append(_sentence_case(goal_bit))

    furiten_bit = _furiten_because_sentence(turn)
    if furiten_bit:
        state_sents.append(furiten_bit)
        focus = "defense" if focus == "efficiency" else "mixed"

    focus = _append_score_situation(state_sents, focus, turn)

    summary = _join_summary_paragraphs(move_sents, state_sents)
    return _finalize_explanation(
        turn,
        Explanation(
            summary=summary,
            focus=focus,
            pinned_action=best,
            contrasted_action=contrasted,
        ),
    )


def _template_explain_riichi(turn: TurnExplainInput) -> Explanation:
    """Declare riichi / Stay silent coach voice."""
    best = turn.mortal_best
    player = turn.player_action
    statuses = turn.features.statuses
    alt = next_best_action(turn)

    focus: Focus = "tempo"
    move_sents: list[str] = []
    state_sents: list[str] = []
    contrasted: str | None = None

    if turn.diverge and player != best:
        contrasted = player
    elif alt and alt != best:
        contrasted = alt

    best_kind = parse_action_kind(best)
    if best_kind == "none":
        move_sents.append("Stay silent")
        if contrasted and is_riichi_decision_action(contrasted):
            move_sents[-1] = "Stay silent—don’t declare riichi yet"
        focus = "defense"
    else:
        reach_discard = turn.features.context.get("reach_discard")
        if reach_discard:
            label = (
                f"Declare riichi, discard {human_tile_label(str(reach_discard))}"
            )
        else:
            label = coach_action_label(best)
        if contrasted and parse_action_kind(contrasted) == "none":
            move_sents.append(f"{label}, don’t stay silent")
        else:
            move_sents.append(label)

    # Tenpai + wait stays with the move paragraph; standalone shanten goes to state.
    if statuses.tenpai or turn.features.shanten == 0:
        wait = _glossed_wait(statuses.wait_shape)
        if wait:
            move_sents.append(
                f"You’re {_glossed_shanten_phrase(0)} with a {wait} wait"
            )
        else:
            move_sents.append(f"You’re {_glossed_shanten_phrase(0)}")
    elif turn.features.shanten is not None:
        state_sents.append(f"You’re {_glossed_shanten_phrase(turn.features.shanten)}")

    if statuses.dora_in_hand and best_kind == "reach":
        state_sents.append(_dora_in_hand_sentence())
        focus = "value"

    furiten_bit = _furiten_because_sentence(turn)
    if furiten_bit:
        state_sents.append(furiten_bit)
        focus = "defense" if focus in ("efficiency", "tempo") else "mixed"

    tiles_left = turn.game_state.tiles_left
    if (
        best_kind == "reach"
        and tiles_left is not None
        and tiles_left <= 30
        and not furiten_bit
    ):
        state_sents.append("The wall is getting thin")

    focus = _append_score_situation(state_sents, focus, turn)

    summary = _join_summary_paragraphs(move_sents, state_sents)
    return _finalize_explanation(
        turn,
        Explanation(
            summary=summary,
            focus=focus,
            pinned_action=best,
            contrasted_action=contrasted,
        ),
    )


def _template_explain_hora(turn: TurnExplainInput) -> Explanation:
    """Take the win coach voice for hora / agari."""
    best = turn.mortal_best
    player = turn.player_action
    statuses = turn.features.statuses
    alt = next_best_action(turn)

    focus: Focus = "value"
    move_sents: list[str] = []
    state_sents: list[str] = []
    contrasted: str | None = None

    if turn.diverge and player != best:
        contrasted = player
    elif alt and alt != best:
        contrasted = alt

    label = coach_action_label(best) if is_hora_decision_action(best) else "Take the win"
    if contrasted and contrasted.strip() == "none":
        move_sents.append(f"{label}, don’t skip")
    else:
        move_sents.append(label)

    shanten = turn.features.shanten
    if shanten == -1:
        move_sents.append(f"You’re {_glossed_shanten_phrase(-1)}")
    elif statuses.tenpai or shanten == 0:
        move_sents.append(
            f"You’re {_glossed_shanten_phrase(0)} with a winning hand"
        )
    elif shanten is not None:
        state_sents.append(f"You’re {_glossed_shanten_phrase(shanten)}")

    if statuses.dora_in_hand:
        state_sents.append(_dora_in_hand_sentence())
        focus = "value"

    focus = _append_score_situation(state_sents, focus, turn)

    summary = _join_summary_paragraphs(move_sents, state_sents)
    return _finalize_explanation(
        turn,
        Explanation(
            summary=summary,
            focus=focus,
            pinned_action=best,
            contrasted_action=contrasted,
        ),
    )


def template_explain(
    turn: TurnExplainInput,
    *,
    include_score_tips: bool = False,
    known_terms: Collection[str] | None = None,
) -> Explanation:
    """Deterministic offline explainer for tests / no API key."""
    turn = _turn_with_coach_prefs(
        turn,
        include_score_tips=include_score_tips,
        known_terms=known_terms,
    )
    with using_known_terms(_known_terms_from_turn(turn)):
        return _template_explain_body(turn)


def _template_explain_body(turn: TurnExplainInput) -> Explanation:
    if is_call_decision_turn(turn):
        return _template_explain_call(turn)
    if is_hora_decision_turn(turn):
        return _template_explain_hora(turn)
    if is_riichi_decision_turn(turn):
        return _template_explain_riichi(turn)

    best = turn.mortal_best
    player = turn.player_action
    shanten = turn.features.shanten
    ukeire = turn.features.ukeire
    wait_shape = turn.features.statuses.wait_shape

    best_tile = _action_display(best)
    player_tile = _action_display(player)
    best_raw = _action_tile_token_raw(best)
    best_code = _danger_key(best_raw)
    player_code = _danger_key(_action_tile_token_raw(player))
    alt = next_best_action(turn)
    alt_tile = _action_display(alt) if alt else None

    focus: Focus = "efficiency"
    move_sents: list[str] = []
    state_sents: list[str] = []
    contrasted: str | None = None

    if turn.diverge and player != best:
        move_sents.append(f"Throw {best_tile}, not {player_tile}")
        contrasted = player
    elif alt and alt != best:
        move_sents.append(f"Throw {best_tile}, not {alt_tile}")
        contrasted = alt
    else:
        move_sents.append(f"Throw {best_tile}")

    note_kind, note = _wall_note_detail(turn)

    if wait_shape:
        wait_label = _glossed_wait(wait_shape) or wait_shape
        move_sents.append(f"That keeps a {wait_label} wait")
        focus = "efficiency"

    if note_kind == "contrast" and note:
        move_sents.append(f"That leaves {note}")
        named = _named_improving_tiles_sentence(turn)
        if named:
            move_sents.append(named)
    elif note:
        move_sents.append(_sentence_case(note))

    thin_extra = _thin_wall_sentence(turn)
    if thin_extra and not any(
        "thinning" in s.lower() or "already out" in s.lower() for s in move_sents
    ):
        move_sents.append(thin_extra)

    contrast_tile = player_tile
    contrast_code = player_code
    contrast_action = player
    if contrasted and contrasted != player:
        contrast_tile = _action_display(contrasted)
        contrast_code = _danger_key(_action_tile_token_raw(contrasted))
        contrast_action = contrasted

    danger_bits, danger_nudge = _danger_compare_sentences(
        turn,
        best_tile=best_tile,
        player_tile=contrast_tile,
        best_code=best_code,
        player_code=contrast_code,
        player=contrast_action,
        best=best,
    )
    defense_led = bool(danger_bits)

    has_efficiency_lead = bool(wait_shape) or note_kind == "contrast"
    if shanten is not None:
        if has_efficiency_lead:
            state_sents.append(f"You’re {_glossed_shanten_phrase(shanten)}")
        elif not defense_led:
            # Skip bare Hand-stats echo when defense is the reason.
            move_sents.append(
                f"You’re {_glossed_shanten_phrase(shanten)} with "
                f"{_glossed_acceptances_phrase(ukeire.count)}"
            )

    goal_bit = _shape_goal_phrase(turn)
    midhand_bit = _midhand_shape_clause(turn, best_raw, best_tile)
    # Defense-led tips: cut teaching only — Aiming for covers yaku; Hand stats
    # covers metrics. Shape goals stay when they *are* the reason (no danger).
    if goal_bit and not defense_led:
        if goal_bit.startswith("fits"):
            shape_sentence = f"That {goal_bit}"
        else:
            shape_sentence = _sentence_case(goal_bit)
        if midhand_bit and (
            "floating" in midhand_bit or "dead-end" in midhand_bit
        ):
            shape_sentence += f"—{midhand_bit}"
            midhand_bit = None
        elif (
            "tanyao" in turn.features.shape_goals
            and best_raw
            and _is_terminal_or_honor(best_raw)
        ):
            shape_sentence += f"—{best_tile} can’t stay in that hand"
        else:
            alt_raw = _action_tile_token_raw(contrasted) if contrasted else None
            yakuhai_bit = _yakuhai_because_clause(turn, best_raw, alt_raw)
            if yakuhai_bit:
                shape_sentence += yakuhai_bit
        state_sents.append(shape_sentence)
        if turn.features.shape_goals or turn.features.statuses.dora_in_hand:
            if focus == "efficiency" and (
                "yakuhai" in turn.features.shape_goals
                or turn.features.statuses.dora_in_hand
            ):
                focus = "value"
    if midhand_bit and not defense_led:
        state_sents.append(_sentence_case(midhand_bit))

    furiten_bit = _furiten_because_sentence(turn)
    if furiten_bit:
        state_sents.append(furiten_bit)
        focus = "defense" if focus == "efficiency" else "mixed"

    state_sents.extend(danger_bits)
    if danger_nudge == "defense":
        focus = "defense" if focus == "efficiency" else (
            focus if focus == "defense" else "mixed"
        )
    elif danger_nudge == "mixed":
        focus = "mixed"

    focus = _append_score_situation(state_sents, focus, turn)

    summary = _join_summary_paragraphs(move_sents, state_sents)
    return _finalize_explanation(
        turn,
        Explanation(
            summary=summary,
            focus=focus,
            pinned_action=best,
            contrasted_action=contrasted,
        ),
    )


def _contrast_alt_action(turn: TurnExplainInput) -> str | None:
    """Action whose ukeire_alt / danger contrast the tip compares against."""
    if turn.diverge and turn.player_action != turn.mortal_best:
        return turn.player_action
    return next_best_action(turn)


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
    note_kind, _note = _wall_note_detail(turn)
    alt_info = turn.features.ukeire_alt
    alt_action = _contrast_alt_action(turn)
    alt_raw = _action_tile_token_raw(alt_action) if alt_action else None
    alt_code = _danger_key(alt_raw) if alt_raw else None

    parsed = _ukeire_contrast_match(summary_l)
    if not parsed:
        return None
    match, best_n, alt_n, label = parsed

    if note_kind != "contrast" or alt_info is None or alt_code is None:
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
        rf"{label}\s+clears\s+(?:a\s+|an\s+)?(?:{kind_alt})\b",
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
    for note in turn.features.hand_shape_notes:
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

    allowed_yaku = set(coaching_shape_goals(turn))
    if turn.features.statuses.dora_in_hand:
        allowed_yaku.add("dora")
    for tag, patterns in _YAKU_MENTION_PATTERNS:
        if tag in allowed_yaku:
            continue
        for pat in patterns:
            if re.search(pat, summary_l):
                errors.append(f"summary mentions yaku {tag!r} not in shape_goals")
                break

    kind_err = _call_kind_mismatch_error(turn, summary_l)
    if kind_err:
        errors.append(kind_err)

    if _CUT_NOTE_POLARITY_PATTERN.search(summary_l):
        errors.append("cut_note_polarity_inverted")

    if _FIGURATIVE_HAND_OPEN_PATTERN.search(summary_l):
        errors.append("figurative_hand_open")

    keep_err = _pinned_discard_keep_error(turn, summary_l)
    if keep_err:
        errors.append(keep_err)

    lead_err = _action_lead_polarity_error(turn, summary_l)
    if lead_err:
        errors.append(lead_err)

    shape_on_err = _isolated_shape_on_cut_error(turn, summary_l)
    if shape_on_err:
        errors.append(shape_on_err)

    cut_tile_err = _false_cut_note_tile_error(turn, summary_l)
    if cut_tile_err:
        errors.append(cut_tile_err)

    yakuhai_pair_err = _false_yakuhai_pair_error(turn, summary_l)
    if yakuhai_pair_err:
        errors.append(yakuhai_pair_err)

    gen_err = _false_genbutsu_error(turn, summary_l)
    if gen_err:
        errors.append(gen_err)

    ukeire_err = _false_ukeire_contrast_error(turn, summary_l)
    if ukeire_err:
        errors.append(ukeire_err)

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


def explain(
    turn: TurnExplainInput,
    *,
    use_llm: bool | None = None,
    model: str | None = None,
    include_score_tips: bool = False,
    known_terms: Collection[str] | None = None,
) -> Explanation:
    """Produce a grounded Explanation. Falls back to template without an API key."""
    turn = _turn_with_coach_prefs(
        turn,
        include_score_tips=include_score_tips,
        known_terms=known_terms,
    )
    known = _known_terms_from_turn(turn)
    with using_known_terms(known):
        if use_llm is None:
            use_llm = bool(
                os.environ.get("OPENAI_API_KEY") or os.environ.get("SENSEI_API_KEY")
            )

        if use_llm:
            try:
                explanation = _llm_explain(turn, model=model)
            except Exception:
                # Network / parse / schema failures → grounded template
                explanation = template_explain(
                    turn,
                    include_score_tips=include_score_tips,
                    known_terms=known,
                )
        else:
            explanation = template_explain(
                turn,
                include_score_tips=include_score_tips,
                known_terms=known,
            )

        errors = validate_explanation(turn, explanation)
        if errors:
            # One repair pass: force template (always grounded); keep summary clean for players.
            logger.info("grounding repair: %s", "; ".join(errors))
            return template_explain(
                turn,
                include_score_tips=include_score_tips,
                known_terms=known,
            )
        return _finalize_explanation(turn, explanation)


def explain_llm(
    turn: TurnExplainInput,
    *,
    model: str | None = None,
    include_score_tips: bool = False,
    known_terms: Collection[str] | None = None,
) -> Explanation:
    """LLM-only explain. Raises if no API key or the call fails — no template fallback."""
    turn = _turn_with_coach_prefs(
        turn,
        include_score_tips=include_score_tips,
        known_terms=known_terms,
    )
    with using_known_terms(_known_terms_from_turn(turn)):
        return _finalize_explanation(turn, _llm_explain(turn, model=model))


def _llm_explain(turn: TurnExplainInput, *, model: str | None) -> Explanation:
    api_key = os.environ.get("SENSEI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("missing API key: set OPENAI_API_KEY or SENSEI_API_KEY")

    base_url = os.environ.get("SENSEI_BASE_URL", "https://api.openai.com/v1")
    model = model or os.environ.get("SENSEI_MODEL", "gpt-4o-mini")
    payload = build_user_payload(turn)

    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    (
                        "Explain this live coaching turn. Return JSON only.\n"
                        if not turn.diverge
                        else "Explain this diverge turn. Return JSON only.\n"
                    )
                    + json.dumps(payload, ensure_ascii=False)
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    data = json.loads(content)
    return explanation_from_llm_data(turn, data)


def coerce_focus(value: Any) -> Focus:
    """Map LLM focus to a valid enum; invalid / prose → mixed."""
    if isinstance(value, str) and value in ALLOWED_FOCUS:
        return value  # type: ignore[return-value]
    return "mixed"


def explanation_from_llm_data(turn: TurnExplainInput, data: dict[str, Any]) -> Explanation:
    """Build Explanation from LLM JSON, coercing soft schema mistakes."""
    summary = data.get("summary")
    focus_raw = data.get("focus")

    # Recover if the model swapped summary into focus (common failure mode)
    if (not isinstance(summary, str) or not summary.strip()) and isinstance(focus_raw, str):
        if focus_raw not in ALLOWED_FOCUS and len(focus_raw.split()) > 2:
            summary = focus_raw

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("LLM response missing summary")

    contrasted = data.get("contrasted_action")
    if contrasted is not None and not isinstance(contrasted, str):
        contrasted = None

    return _finalize_explanation(
        turn,
        Explanation(
            summary=summary.strip(),
            focus=coerce_focus(focus_raw),
            pinned_action=(
                data["pinned_action"]
                if isinstance(data.get("pinned_action"), str) and data["pinned_action"]
                else turn.mortal_best
            ),
            contrasted_action=contrasted,
        ),
    )


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
