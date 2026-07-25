"""Pydantic models for one explain() turn — source of truth for Phase 1."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Focus = Literal["efficiency", "defense", "value", "tempo", "mixed"]
WaitShape = Literal["ryanmen", "kanchan", "penchan", "tanki", "shanpon", "complex", "unknown"]


class HandStatuses(BaseModel):
    menzen: bool = True
    tenpai: bool = False
    shanten: int = Field(..., description="Distance to tenpai; 0 = tenpai, -1 = agari")
    furiten: bool = False
    temporary_furiten: bool = False
    riichi: bool = False
    ippatsu: bool = False
    wait_shape: WaitShape | None = None
    dora_in_hand: list[str] = Field(default_factory=list)
    visible_dora: list[str] = Field(default_factory=list)


class UkeireInfo(BaseModel):
    count: int
    tiles: list[str] = Field(default_factory=list)
    remaining_by_tile: dict[str, int] = Field(
        default_factory=dict,
        description="Visible-adjusted copies left per improving tile",
    )


class GameState(BaseModel):
    hand: list[str]
    calls: list[dict[str, Any]] = Field(default_factory=list)
    discards: list[str] = Field(default_factory=list)
    visible_discards: dict[str, list[str]] = Field(default_factory=dict)
    dora_indicators: list[str] = Field(default_factory=list)
    turn: int | None = None
    tiles_left: int | None = None
    honba: int | None = None
    scores: list[int] | None = None
    riichi_flags: list[bool] = Field(default_factory=list)
    kyoku: int | None = None


class MortalCandidate(BaseModel):
    action: str
    q_value: float | None = None
    prob: float | None = None


class MortalOutput(BaseModel):
    recommended: str
    candidates: list[MortalCandidate] = Field(default_factory=list)
    raw_expected: dict[str, Any] | None = None


class DerivedFeatures(BaseModel):
    shanten: int
    ukeire: UkeireInfo
    ukeire_alt: UkeireInfo | None = Field(
        default=None,
        description="Ukeire after contrasted dahai (player / next-best), if different",
    )
    statuses: HandStatuses
    danger: dict[str, str] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    shape_goals: list[str] = Field(
        default_factory=list,
        description="Likely yaku/shape tags from heuristics (not Mortal intent)",
    )


class TurnExplainInput(BaseModel):
    """Full grounded payload for explain()."""

    game_state: GameState
    mortal_output: MortalOutput
    features: DerivedFeatures
    player_action: str
    mortal_best: str
    source: str = "mjai-reviewer"
    diverge: bool = True


class Explanation(BaseModel):
    summary: str
    focus: Focus = "mixed"
    pinned_action: str
    contrasted_action: str | None = None
