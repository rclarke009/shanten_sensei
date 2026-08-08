"""Build TurnExplainInput from live mjai + Mortal state (overlay / Copilot)."""

from __future__ import annotations

from typing import Any

from shanten_sensei.features import (
    attach_score_situation,
    build_call_tradeoff,
    collect_visible_tiles,
    extract_features,
)
from shanten_sensei.schema import (
    GameState,
    MortalCandidate,
    MortalOutput,
    TurnExplainInput,
)
from shanten_sensei.tiles import (
    action_tile_arg,
    action_to_label,
    deaka,
    enrich_call_action_label,
    is_call_action,
    is_call_decision_action,
    is_hora_decision_action,
    is_riichi_decision_action,
    normalize_tile,
    parse_action_kind,
    same_call_family,
    tile_to_34,
    tiles_to_34_array,
)

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


def _reaction_call_tile(recommended: str | dict[str, Any] | None) -> str | None:
    if isinstance(recommended, dict):
        pai = recommended.get("pai")
        if pai:
            return normalize_tile(str(pai))
    return None


def _reaction_consumed(
    recommended: str | dict[str, Any] | None,
) -> list[str] | None:
    if isinstance(recommended, dict):
        consumed = recommended.get("consumed")
        if isinstance(consumed, list) and consumed:
            return [normalize_tile(str(t)) for t in consumed]
    return None


def _resolve_player_discards(
    discards: list[str] | None,
    visible_discards: dict[str, list[str]] | None,
    *,
    player_seat: int | str | None = None,
    context: dict[str, Any] | None = None,
) -> list[str]:
    """Prefer explicit river; else the player's seat river from visible_discards."""
    if discards:
        return [normalize_tile(t) for t in discards]
    seat = player_seat
    if seat is None and context:
        seat = context.get("self_seat")
    if seat is None:
        return []
    river = (visible_discards or {}).get(str(seat)) or []
    return [normalize_tile(t) for t in river]


def _reach_cut_tile(
    recommended: str | dict[str, Any],
    candidates: list[MortalCandidate],
    *,
    explicit_tile: str | None = None,
) -> str | None:
    """Tile discarded with riichi (nested reach_dahai, pai, or top dahai meta)."""
    if explicit_tile:
        return normalize_tile(explicit_tile)
    if isinstance(recommended, dict):
        nested = recommended.get("reach_dahai")
        if isinstance(nested, dict) and nested.get("pai"):
            return normalize_tile(str(nested["pai"]))
        if (recommended.get("type") or recommended.get("type_")) == "reach":
            pai = recommended.get("pai")
            if pai:
                return normalize_tile(str(pai))
    dahai = [c for c in candidates if c.action.startswith("dahai ")]
    if not dahai:
        return None

    def _prob(c: MortalCandidate) -> float:
        return float(c.prob) if c.prob is not None else -1.0

    best = max(dahai, key=_prob)
    return normalize_tile(best.action.split(" ", 1)[1])


def unify_call_candidates(
    candidates: list[MortalCandidate],
    mortal_best: str,
    *,
    call_tile: str | None = None,
) -> list[MortalCandidate]:
    """Enrich bare pon/chi meta codes with the known call tile; drop same-call dupes."""
    out: list[MortalCandidate] = []
    seen: set[str] = set()
    for c in candidates:
        action = enrich_call_action_label(
            c.action,
            call_tile=call_tile,
            preferred=mortal_best if is_call_action(mortal_best) else None,
        )
        # Bare call still same family as tile-bearing best → collapse to best
        if (
            is_call_action(mortal_best)
            and same_call_family(action, mortal_best)
            and action_tile_arg(action) == action_tile_arg(mortal_best)
        ):
            action = mortal_best
        if action in seen:
            continue
        seen.add(action)
        out.append(MortalCandidate(action=action, q_value=c.q_value, prob=c.prob))
    return out


def _pick_call_action(
    mortal_best: str,
    player_action: str,
    candidates: list[MortalCandidate],
) -> str | None:
    """Call being debated (best, player, or next-best candidate)."""
    for action in (mortal_best, player_action):
        if is_call_action(action):
            return action
    for c in candidates:
        if is_call_action(c.action) and c.action != mortal_best:
            return c.action
    return None


def infer_call_tile(
    hand: list[str],
    candidates: list[MortalCandidate],
    *,
    visible_discards: dict[str, list[str]] | None = None,
) -> str | None:
    """Best-effort call tile when live meta only has bare pon/chi codes."""
    wants_pon = any(parse_action_kind(c.action) == "pon" for c in candidates)
    if not wants_pon:
        return None
    river_ends = [
        normalize_tile(river[-1])
        for river in (visible_discards or {}).values()
        if river
    ]
    if not river_ends:
        return None
    counts = tiles_to_34_array(hand)
    matches = [t for t in river_ends if counts[tile_to_34(t)] >= 2]
    bases = {deaka(t) for t in matches}
    if len(bases) == 1:
        return matches[0]
    return None


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
    call_tile: str | None = None,
    call_consumed: list[str] | None = None,
    player_seat: int | str | None = None,
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

    hand_n = [normalize_tile(t) for t in hand]
    dora_n = [normalize_tile(t) for t in (dora_indicators or [])]
    visible_n = {
        str(k): [normalize_tile(t) for t in v]
        for k, v in (visible_discards or {}).items()
    }
    discards_n = _resolve_player_discards(
        discards,
        visible_n,
        player_seat=player_seat,
        context=context,
    )
    calls_n = list(calls or [])

    resolved_tile = (
        call_tile
        or _reaction_call_tile(recommended if isinstance(recommended, dict) else None)
        or action_tile_arg(mortal_best)
        or (
            normalize_tile(str(context["call_tile"]))
            if context and context.get("call_tile")
            else None
        )
    )
    if resolved_tile is None:
        resolved_tile = infer_call_tile(
            hand_n, cand_models, visible_discards=visible_n
        )

    resolved_consumed = call_consumed or _reaction_consumed(
        recommended if isinstance(recommended, dict) else None
    )
    if context and not resolved_consumed and context.get("call_consumed"):
        resolved_consumed = [
            normalize_tile(str(t)) for t in context["call_consumed"]
        ]

    cand_models = unify_call_candidates(
        cand_models, mortal_best, call_tile=resolved_tile
    )

    # Ensure recommended is first among candidates when missing
    if not any(c.action == mortal_best for c in cand_models):
        cand_models.insert(0, MortalCandidate(action=mortal_best, prob=1.0))

    pending = player_action is None
    if pending:
        player_action = mortal_best
    else:
        player_action = enrich_call_action_label(
            player_action,
            call_tile=resolved_tile,
            preferred=mortal_best if is_call_action(mortal_best) else None,
        )
    if diverge is None:
        diverge = (not pending) and (player_action != mortal_best)

    discard_tile = None
    if mortal_best.startswith("dahai "):
        discard_tile = mortal_best.split(" ", 1)[1]
    elif is_riichi_decision_action(mortal_best):
        # Don't use call_tile here — for reach, pai often means the win tile.
        explicit = None
        if context and context.get("reach_discard"):
            explicit = str(context["reach_discard"])
        discard_tile = _reach_cut_tile(
            recommended, cand_models, explicit_tile=explicit
        )

    candidate_tiles = [
        c.action.split(" ", 1)[1]
        for c in cand_models
        if c.action.startswith("dahai ")
    ]
    alt_discard = contrasted_dahai_tile(
        mortal_best=mortal_best,
        player_action=player_action,
        candidates=cand_models,
        diverge=bool(diverge),
    )

    feat_context = {
        "junme": turn,
        "tiles_left": tiles_left,
        "kyoku": kyoku,
        "honba": honba,
        "live": True,
        "diverge": diverge,
        **(context or {}),
    }
    if resolved_tile:
        feat_context["call_tile"] = resolved_tile
    if discard_tile and is_riichi_decision_action(mortal_best):
        feat_context["reach_discard"] = discard_tile

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
        ukeire_alt_after_discard=alt_discard,
    )

    call_action = _pick_call_action(mortal_best, player_action, cand_models)
    if call_action and any(
        is_call_decision_action(a)
        for a in (mortal_best, player_action, *(c.action for c in cand_models))
    ):
        features.call_tradeoff = build_call_tradeoff(
            hand_n,
            calls=calls_n,
            stay_closed_shanten=features.shanten,
            stay_closed_ukeire=features.ukeire.count,
            call_action=call_action,
            consumed=resolved_consumed,
            call_tile=resolved_tile or action_tile_arg(call_action),
            visible_tiles=collect_visible_tiles(
                visible_discards=visible_n,
                discards=discards_n,
                calls=calls_n,
                dora_indicators=dora_n,
            ),
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
    attach_score_situation(features, game_state)

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
        if c.action == best:
            continue
        # Bare/enriched same call as best is not a real alternative
        if (
            is_call_action(best)
            and same_call_family(c.action, best)
            and (
                action_tile_arg(c.action) is None
                or action_tile_arg(c.action) == action_tile_arg(best)
            )
        ):
            continue
        return c.action
    return None


def contrasted_dahai_tile(
    *,
    mortal_best: str,
    player_action: str,
    candidates: list[MortalCandidate],
    diverge: bool,
) -> str | None:
    """Tile for ukeire_alt: player cut on diverge, else next-best dahai candidate."""
    if diverge and player_action.startswith("dahai ") and player_action != mortal_best:
        return normalize_tile(player_action.split(" ", 1)[1])
    for c in candidates:
        if c.action.startswith("dahai ") and c.action != mortal_best:
            return normalize_tile(c.action.split(" ", 1)[1])
    return None


def is_call_decision_turn(turn: TurnExplainInput) -> bool:
    """True when Why? should use Skip/Call voice instead of Throw.

    Requires a real call (pon/chi/kan) in the tip — bare ``none`` alone is
    not enough (that may be Stay silent vs riichi).
    """
    actions = [turn.mortal_best]
    if turn.diverge:
        actions.append(turn.player_action)
    alt = next_best_action(turn)
    if alt:
        actions.append(alt)
    actions.extend(c.action for c in turn.mortal_output.candidates)
    return any(is_call_action(a) for a in actions) and any(
        is_call_decision_action(a) for a in (turn.mortal_best, turn.player_action, alt)
        if a
    )


def is_riichi_decision_turn(turn: TurnExplainInput) -> bool:
    """True when Why? should use Declare riichi / Stay silent voice.

    Reach must be the top pick, the diverge contrast, or the next-best
    alternative — not merely a low-prob candidate on a discard tip.
    """
    if is_call_decision_turn(turn):
        return False
    if is_hora_decision_turn(turn):
        return False
    if is_riichi_decision_action(turn.mortal_best):
        return True
    if turn.diverge and is_riichi_decision_action(turn.player_action):
        return True
    alt = next_best_action(turn)
    if alt and is_riichi_decision_action(alt):
        return True
    # Stay silent: Mortal picked none while reach is among candidates
    if turn.mortal_best.strip() == "none" and any(
        is_riichi_decision_action(c.action) for c in turn.mortal_output.candidates
    ):
        return True
    return False


def is_hora_decision_turn(turn: TurnExplainInput) -> bool:
    """True when Why? should use Take the win voice (hora / agari)."""
    if is_call_decision_turn(turn):
        return False
    if is_hora_decision_action(turn.mortal_best):
        return True
    if turn.diverge and is_hora_decision_action(turn.player_action):
        return True
    alt = next_best_action(turn)
    if alt and is_hora_decision_action(alt):
        return True
    return False
