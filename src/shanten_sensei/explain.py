"""Grounded explain() — LLM translates Mortal; never evaluates the hand."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from shanten_sensei.live import next_best_action
from shanten_sensei.schema import Explanation, Focus, TurnExplainInput

ALLOWED_FOCUS = frozenset({"efficiency", "defense", "value", "tempo", "mixed"})

SYSTEM_PROMPT = """\
You are a beginner-friendly riichi mahjong coach. You explain Mortal’s \
recommendation using only the game state, Mortal scores, and derived features \
provided. You do not invent better moves. If the player’s move differs, say why \
Mortal’s choice is better in efficiency, safety, or point situation. If this is \
a live pre-decision turn (diverge is false / player_action equals mortal_best), \
explain why Mortal’s top pick beats the next-best candidate. One or two \
sentences. Plain English. Prefer concrete tile language (e.g. 5-sou, ryanmen wait). \
Never recommend an action other than mortal_best.

Return JSON with exactly these keys:
- summary: string (1–2 sentences of coach text)
- focus: one of "efficiency", "defense", "value", "tempo", "mixed" (enum only, never prose)
- pinned_action: must equal mortal_best
- contrasted_action: player's action when it differs; else next-best candidate; else null
"""


def build_user_payload(turn: TurnExplainInput) -> dict[str, Any]:
    scores = {
        c.action: {"q_value": c.q_value, "prob": c.prob}
        for c in turn.mortal_output.candidates[:8]
    }
    return {
        "player_action": turn.player_action,
        "mortal_best": turn.mortal_best,
        "next_best": next_best_action(turn),
        "diverge": turn.diverge,
        "mortal_scores": scores,
        "hand": turn.game_state.hand,
        "shanten": turn.features.shanten,
        "ukeire": turn.features.ukeire.model_dump(),
        "statuses": turn.features.statuses.model_dump(),
        "danger": turn.features.danger,
        "context": turn.features.context,
    }


def _action_display(action: str) -> str:
    return action.split(" ", 1)[-1] if action.startswith("dahai ") else action


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
        bits.append(f"you’re {shanten}-shanten with about {ukeire.count} acceptances")

    player_danger = danger.get(player_tile)
    if player_danger == "genbutsu" and player != best:
        bits.append(f"{player_tile} is genbutsu-safe but efficiency is worse")
        focus = "mixed"
    elif best_tile in danger and danger[best_tile] == "genbutsu":
        bits.append(f"{best_tile} is also genbutsu")
        focus = "defense"

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
    if pin_token and pin_token not in summary_l and turn.mortal_best.lower() not in summary_l:
        # Allow readable forms like "5-sou" for "5s"
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
        repaired.summary = (
            f"{repaired.summary} (grounding repair: {'; '.join(errors)})"
            if use_llm
            else repaired.summary
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


def _mentions_tile(text: str, tile: str) -> bool:
    """Match 5s / 5-sou / 5 sou style mentions."""
    tile = tile.lower()
    if tile in text:
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
