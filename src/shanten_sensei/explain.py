"""Grounded explain() — LLM translates Mortal; never evaluates the hand."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from shanten_sensei.live import next_best_action
from shanten_sensei.schema import Explanation, Focus, TurnExplainInput
from shanten_sensei.tiles import (
    deaka,
    human_action_label,
    human_tile_label,
    normalize_tile,
)

ALLOWED_FOCUS = frozenset({"efficiency", "defense", "value", "tempo", "mixed"})

SYSTEM_PROMPT = """\
You are a beginner-friendly riichi mahjong coach. You explain Mortal’s \
recommendation using only the game state, Mortal scores, and derived features \
provided. You do not invent better moves. If the player’s move differs, say why \
Mortal’s choice is better in efficiency, safety, or point situation. If this is \
a live pre-decision turn (diverge is false / player_action equals mortal_best), \
explain why Mortal’s top pick beats the next-best candidate. One or two \
sentences. Plain English. Prefer concrete tile language from tile_glossary \
(e.g. 🀅Hatsu, 🀔5-sou, ryanmen wait). Never use bare honor letters F/C/P or \
bare suit codes like 5s when naming tiles for the player. \
Never recommend an action other than mortal_best.

Do not justify Mortal by restating its probability percentages or by saying \
\"more efficient\" / \"higher chance\" alone. Prefer one concrete fact from the \
payload: shanten/acceptances (with hand_metric_glossary parentheticals), ukeire \
tiles / remaining_by_tile, ukeire_alt, wall_note, wait shape, shape_goals \
(with glossary parentheticals), or dora. The chart already shows Mortal % — \
leave percentages out of the summary.

You may cite ukeire.remaining_by_tile or ukeire_alt for visible wall depletion \
or live-acceptance contrast (e.g. tiles already out; more live acceptances \
than the alternate cut). Prefer wall_note when present. Never invent unseen \
wall math, opponent-hand contents, or discard reasons not supported by those \
fields.

If shape_goals is non-empty, you may name only those goals as likely hand shape \
(not as Mortal’s internal plan). When you name a goal or dora, include the short \
parenthetical from shape_goal_glossary (e.g. \"tanyao (2–8 only; no 1/9, winds, \
or dragons)\", \"dora (bonus tile)\"). When you mention shanten or acceptances, \
include the short parenthetical from hand_metric_glossary (e.g. \"3-shanten \
(3 steps from ready)\", \"acceptances (tiles that improve the hand)\"). Never \
invent other yaku. You may mention dora only when statuses.dora_in_hand is \
non-empty.

Return JSON with exactly these keys:
- summary: string (1–2 sentences of coach text)
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
        r"\bhigher (?:probability|chance)\b",
        r"\bkeeps? (?:your )?(?:hand )?(?:flexible|options open)\b",
        r"\bimproving your hand\b",
        r"\bchance of (?:improving|helping)\b",
        r"\d+(?:\.\d+)?%\b",
    )
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

_GOAL_GLOSS: dict[str, str] = {
    "tanyao": "2–8 only; no 1/9, winds, or dragons",
    "yakuhai": "dragon or seat/round wind",
    "honitsu": "one suit + winds/dragons OK",
    "chinitsu": "one suit only",
    "toitoi": "all triplets",
    "chiitoi": "seven pairs",
}
_DORA_GLOSS = "bonus tile"
_ACCEPTANCES_GLOSS = "tiles that improve the hand"


def _glossed_goal(tag: str) -> str:
    gloss = _GOAL_GLOSS.get(tag)
    return f"{tag} ({gloss})" if gloss else tag


def _glossed_dora_phrase(tile_label: str) -> str:
    return f"dora ({_DORA_GLOSS}) {tile_label}"


def _glossed_shanten_phrase(shanten: int) -> str:
    if shanten <= 0:
        return "tenpai (ready)"
    step = "step" if shanten == 1 else "steps"
    return f"{shanten}-shanten ({shanten} {step} from ready)"


def _glossed_acceptances_phrase(count: int) -> str:
    return f"about {count} acceptances ({_ACCEPTANCES_GLOSS})"


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
    if turn.features.statuses.dora_in_hand:
        return True
    if any(v == "genbutsu" for v in turn.features.danger.values()):
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
        or re.search(r"\b\d+\s*[×x]\b", summary_l)
    )
    if (
        re.search(r"\bacceptances?\b", summary_l)
        or re.search(r"\bukeire\b", summary_l)
        or (_wall_facts_available(turn) and wall_lang)
    ):
        anchors.append("ukeire")

    wait_shape = turn.features.statuses.wait_shape
    if wait_shape and wait_shape in summary_l:
        anchors.append("wait_shape")

    for goal in turn.features.shape_goals:
        if re.search(rf"\b{re.escape(goal)}\b", summary_l):
            anchors.append("shape_goal")
            break

    if turn.features.statuses.dora_in_hand and re.search(r"\bdora\b", summary_l):
        anchors.append("dora")

    if any(v == "genbutsu" for v in turn.features.danger.values()) and re.search(
        r"\bgenbutsu\b", summary_l
    ):
        anchors.append("danger")

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


def wall_note(turn: TurnExplainInput) -> str | None:
    """Short grounded wall-depletion / live-ukeire contrast, or None if not meaningful."""
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
            f"keeps more live acceptances (~{ukeire.count} vs ~{alt.count} "
            f"after cutting {alt_label})"
        )

    if thin:
        thin.sort(key=lambda x: (x[1], x[0]))
        tile, n = thin[0]
        label = human_tile_label(tile)
        detail = f"{label} already out" if n <= 0 else f"only {n}× {label} left"
        if len(thin) >= 2:
            return f"several improving tiles are already out ({detail})"
        return f"improving tiles are thinning ({detail})"

    return None


def build_user_payload(turn: TurnExplainInput) -> dict[str, Any]:
    scores = {
        c.action: {"q_value": c.q_value, "prob": c.prob}
        for c in turn.mortal_output.candidates[:8]
    }
    next_best = next_best_action(turn)
    note = wall_note(turn)
    return {
        "player_action": turn.player_action,
        "mortal_best": turn.mortal_best,
        "next_best": next_best,
        "player_action_display": human_action_label(turn.player_action),
        "mortal_best_display": human_action_label(turn.mortal_best),
        "next_best_display": human_action_label(next_best) if next_best else None,
        "diverge": turn.diverge,
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
        "shape_goals": list(turn.features.shape_goals),
        "shape_goal_glossary": {
            **{g: _GOAL_GLOSS[g] for g in turn.features.shape_goals if g in _GOAL_GLOSS},
            "dora": _DORA_GLOSS,
        },
        "hand_metric_glossary": {
            "shanten": (
                "ready"
                if turn.features.shanten <= 0
                else (
                    f"{turn.features.shanten} "
                    f"{'step' if turn.features.shanten == 1 else 'steps'} from ready"
                )
            ),
            "acceptances": _ACCEPTANCES_GLOSS,
        },
        "danger": turn.features.danger,
        "context": turn.features.context,
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
    if not action or not action.startswith("dahai "):
        return None
    return action.split(" ", 1)[1]


def _danger_key(tile: str | None) -> str | None:
    if not tile:
        return None
    return deaka(normalize_tile(tile))


def _shape_goal_phrase(turn: TurnExplainInput) -> str | None:
    """Human phrase for heuristic shape goals (+ dora when present)."""
    goals = [g for g in turn.features.shape_goals if g]
    dora = turn.features.statuses.dora_in_hand
    if not goals and not dora:
        return None
    if goals:
        lean = " / ".join(_glossed_goal(g) for g in goals)
        if dora:
            return f"shape leans {lean} with {_glossed_dora_phrase(human_tile_label(dora[0]))}"
        return f"shape leans {lean}"
    # Dora only — still useful value signal
    return f"keeping {_glossed_dora_phrase(human_tile_label(dora[0]))}"


def template_explain(turn: TurnExplainInput) -> Explanation:
    """Deterministic offline explainer for tests / no API key."""
    best = turn.mortal_best
    player = turn.player_action
    shanten = turn.features.shanten
    ukeire = turn.features.ukeire
    danger = turn.features.danger
    wait_shape = turn.features.statuses.wait_shape

    best_tile = _action_display(best)
    player_tile = _action_display(player)
    best_code = _danger_key(_action_tile_token_raw(best))
    player_code = _danger_key(_action_tile_token_raw(player))
    alt = next_best_action(turn)
    alt_tile = _action_display(alt) if alt else None

    focus: Focus = "efficiency"
    bits: list[str] = []
    contrasted: str | None = None

    if turn.diverge and player != best:
        bits.append(f"Mortal prefers {best_tile} over {player_tile}")
        contrasted = player
    elif alt and alt != best:
        bits.append(f"Mortal prefers {best_tile} over {alt_tile}")
        contrasted = alt
    else:
        bits.append(f"Mortal recommends {best_tile}")

    if wait_shape:
        bits.append(f"keeping a {wait_shape} wait shape")
        focus = "efficiency"
    elif shanten is not None:
        bits.append(
            f"you’re {_glossed_shanten_phrase(shanten)} with "
            f"{_glossed_acceptances_phrase(ukeire.count)}"
        )

    goal_bit = _shape_goal_phrase(turn)
    if goal_bit:
        bits.append(goal_bit)
        if turn.features.shape_goals or turn.features.statuses.dora_in_hand:
            if focus == "efficiency" and (
                "yakuhai" in turn.features.shape_goals
                or turn.features.statuses.dora_in_hand
            ):
                focus = "value"

    player_danger = danger.get(player_code) if player_code else None
    if player_danger == "genbutsu" and player != best:
        bits.append(f"{player_tile} is genbutsu-safe but efficiency is worse")
        focus = "mixed"
    elif best_code and danger.get(best_code) == "genbutsu":
        bits.append(f"{best_tile} is also genbutsu")
        focus = "defense"

    note = wall_note(turn)
    if note:
        bits.append(note)

    summary = "; ".join(bits) + "."
    return Explanation(
        summary=summary,
        focus=focus,
        pinned_action=best,
        contrasted_action=contrasted,
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

    # Reject recommending a different dahai tile than mortal_best
    other = _action_tile_token(turn.player_action)
    if (
        other
        and other != pin_token
        and re.search(rf"\b(?:discard|throw|cut)\s+{re.escape(other)}\b", summary_l)
        and not re.search(
            rf"\b(?:instead of|rather than|over)\s+{re.escape(other)}\b", summary_l
        )
    ):
        errors.append("summary appears to recommend the player's tile over Mortal")

    if len(explanation.summary.split()) > 80:
        errors.append("summary exceeds length budget")

    allowed_yaku = set(turn.features.shape_goals)
    if turn.features.statuses.dora_in_hand:
        allowed_yaku.add("dora")
    for tag, patterns in _YAKU_MENTION_PATTERNS:
        if tag in allowed_yaku:
            continue
        for pat in patterns:
            if re.search(pat, summary_l):
                errors.append(f"summary mentions yaku {tag!r} not in shape_goals")
                break

    substance = score_explanation_substance(turn, explanation.summary)
    if substance.thin:
        errors.append("thin_efficiency_claim")

    return errors


def explain(
    turn: TurnExplainInput,
    *,
    use_llm: bool | None = None,
    model: str | None = None,
) -> Explanation:
    """Produce a grounded Explanation. Falls back to template without an API key."""
    if use_llm is None:
        use_llm = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("SENSEI_API_KEY"))

    if use_llm:
        try:
            explanation = _llm_explain(turn, model=model)
        except Exception:
            # Network / parse / schema failures → grounded template
            explanation = template_explain(turn)
    else:
        explanation = template_explain(turn)

    errors = validate_explanation(turn, explanation)
    if errors:
        # One repair pass: force template (always grounded)
        repaired = template_explain(turn)
        substance_only = errors == ["thin_efficiency_claim"]
        # Substance repair: show clean template (no debug suffix in overlay).
        if use_llm and not substance_only:
            repaired.summary = (
                f"{repaired.summary} (grounding repair: {'; '.join(errors)})"
            )
        return repaired
    return explanation


def explain_llm(
    turn: TurnExplainInput,
    *,
    model: str | None = None,
) -> Explanation:
    """LLM-only explain. Raises if no API key or the call fails — no template fallback."""
    return _llm_explain(turn, model=model)


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

    return Explanation(
        summary=summary.strip(),
        focus=coerce_focus(focus_raw),
        pinned_action=(
            data["pinned_action"]
            if isinstance(data.get("pinned_action"), str) and data["pinned_action"]
            else turn.mortal_best
        ),
        contrasted_action=contrasted,
    )


def _action_tile_token(action: str) -> str | None:
    if action.startswith("dahai "):
        return action.split(" ", 1)[1].lower()
    return None


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
