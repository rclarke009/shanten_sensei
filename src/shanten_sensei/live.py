"""Build TurnExplainInput from live mjai + Mortal state (overlay / Copilot)."""

from __future__ import annotations

from typing import Any

from shanten_sensei.features import extract_features
from shanten_sensei.schema import (
    GameState,
    MortalCandidate,
    MortalOutput,
    TurnExplainInput,
)
from shanten_sensei.tiles import action_to_label, normalize_tile

# Mask codes from Mortal meta that are not tile dahai labels
_NON_DAHAI_CODES = frozenset(
    {
        "reach",
        "chi_low",
        "chi_mid",
        "chi_high",
        "pon",
        "kan_select",
        "hora",
        "ryukyoku",
        "none",
        "nukidora",
    }
)


def candidate_label_from_code(code: str) -> str:
    """Map a Mortal meta mask code to a Sensei action label."""
    c = code.strip()
    if c in _NON_DAHAI_CODES:
        return c
    # Tile codes → dahai label
    return f"dahai {normalize_tile(c)}"


def candidates_from_meta_options(
    meta_options: list[tuple[str, float]] | list[list[Any]] | None,
) -> list[MortalCandidate]:
    """Convert Copilot ``meta_options`` [(code, weight), ...] to candidates."""
    out: list[MortalCandidate] = []
    if not meta_options:
        return out
    for item in meta_options:
        if not item or len(item) < 1:
            continue
        code = str(item[0])
        weight = float(item[1]) if len(item) > 1 and item[1] is not None else None
        out.append(
            MortalCandidate(
                action=candidate_label_from_code(code),
                q_value=None,
                prob=weight,
            )
        )
    return out


def turn_from_live(
    *,
    hand: list[str],
    recommended: str | dict[str, Any],
    candidates: list[MortalCandidate] | list[dict[str, Any]] | None = None,
    player_action: str | None = None,
    calls: list[dict[str, Any]] | None = None,
    discards: list[str] | None = None,
    visible_discards: dict[str, list[str]] | None = None,
    dora_indicators: list[str] | None = None,
    turn: int | None = None,
    tiles_left: int | None = None,
    honba: int | None = None,
    scores: list[int] | None = None,
    kyoku: int | None = None,
    riichi: bool = False,
    riichi_flags: list[bool] | None = None,
    diverge: bool | None = None,
    source: str = "live-copilot",
    context: dict[str, Any] | None = None,
) -> TurnExplainInput:
    """Build a grounded turn for live coaching (pre-decision or post-action).

    When ``player_action`` is omitted, this is pre-decision coaching:
    ``player_action`` equals Mortal's recommendation and ``diverge`` is False.
    """
    if isinstance(recommended, dict):
        mortal_best = action_to_label(recommended)
    else:
        mortal_best = recommended.strip()

    cand_models: list[MortalCandidate] = []
    for c in candidates or []:
        if isinstance(c, MortalCandidate):
            cand_models.append(c)
        else:
            cand_models.append(
                MortalCandidate(
                    action=str(c["action"]),
                    q_value=c.get("q_value"),
                    prob=c.get("prob"),
                )
            )

    # Ensure recommended is first among candidates when missing
    if not any(c.action == mortal_best for c in cand_models):
        cand_models.insert(0, MortalCandidate(action=mortal_best, prob=1.0))

    pending = player_action is None
    if pending:
        player_action = mortal_best
    if diverge is None:
        diverge = (not pending) and (player_action != mortal_best)

    hand_n = [normalize_tile(t) for t in hand]
    discards_n = [normalize_tile(t) for t in (discards or [])]
    dora_n = [normalize_tile(t) for t in (dora_indicators or [])]
    visible_n = {
        str(k): [normalize_tile(t) for t in v]
        for k, v in (visible_discards or {}).items()
    }
    calls_n = list(calls or [])

    discard_tile = None
    if mortal_best.startswith("dahai "):
        discard_tile = mortal_best.split(" ", 1)[1]

    candidate_tiles = [
        c.action.split(" ", 1)[1]
        for c in cand_models
        if c.action.startswith("dahai ")
    ]

    feat_context = {
        "junme": turn,
        "tiles_left": tiles_left,
        "kyoku": kyoku,
        "honba": honba,
        "live": True,
        "diverge": diverge,
        **(context or {}),
    }

    features = extract_features(
        hand_n,
        calls=calls_n,
        discards=discards_n,
        dora_indicators=dora_n,
        riichi=riichi,
        candidate_tiles=candidate_tiles,
        visible_discards=visible_n,
        context=feat_context,
        ukeire_after_discard=discard_tile,
    )

    game_state = GameState(
        hand=hand_n,
        calls=calls_n,
        discards=discards_n,
        visible_discards=visible_n,
        dora_indicators=dora_n,
        turn=turn,
        tiles_left=tiles_left,
        honba=honba,
        scores=scores,
        riichi_flags=list(riichi_flags or []),
        kyoku=kyoku,
    )

    mortal_output = MortalOutput(
        recommended=mortal_best,
        candidates=cand_models,
        raw_expected=recommended if isinstance(recommended, dict) else None,
    )

    return TurnExplainInput(
        game_state=game_state,
        mortal_output=mortal_output,
        features=features,
        player_action=player_action,
        mortal_best=mortal_best,
        source=source,
        diverge=diverge,
    )


def next_best_action(turn: TurnExplainInput) -> str | None:
    """Second-ranked Mortal candidate, if any (for non-diverge contrast)."""
    best = turn.mortal_best
    for c in turn.mortal_output.candidates:
        if c.action != best:
            return c.action
    return None
