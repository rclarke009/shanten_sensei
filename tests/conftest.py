"""Shared test fixtures for coaching tests."""

BULLET_PREFIX = "• "


def strip_bullets(summary: str) -> str:
    """Remove bullet prefixes for prose assertions."""
    lines: list[str] = []
    for ln in summary.splitlines():
        ln = ln.strip()
        if ln.startswith(BULLET_PREFIX):
            ln = ln[len(BULLET_PREFIX) :].strip()
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def bullet_lines(summary: str) -> list[str]:
    """Non-empty lines that start with a bullet marker."""
    return [
        ln.strip()
        for ln in summary.splitlines()
        if ln.strip().startswith(BULLET_PREFIX)
    ]


def summary_blocks(summary: str) -> list[str]:
    """Blank-line-separated bullet groups."""
    return [block.strip() for block in summary.split("\n\n") if block.strip()]


from shanten_sensei.schema import (
    DerivedFeatures,
    GameState,
    HandStatuses,
    MortalCandidate,
    MortalOutput,
    TurnExplainInput,
    UkeireInfo,
)


def make_turn(
    *,
    shape_goals: list[str] | None = None,
    dora_in_hand: list[str] | None = None,
    wait_shape: str | None = None,
    danger: dict[str, str] | None = None,
    mortal_best: str = "dahai 3p",
    player_action: str = "dahai 5m",
    ukeire: UkeireInfo | None = None,
    ukeire_alt: UkeireInfo | None = None,
    diverge: bool = False,
) -> TurnExplainInput:
    return TurnExplainInput(
        game_state=GameState(
            hand=["2m", "3m", "5m", "7m", "3p", "6p", "7p", "1s", "3s", "8s", "8s", "S", "S"]
        ),
        mortal_output=MortalOutput(
            recommended=mortal_best,
            candidates=[
                MortalCandidate(action=mortal_best, prob=0.79),
                MortalCandidate(action=player_action, prob=0.11),
            ],
        ),
        features=DerivedFeatures(
            shanten=3,
            ukeire=ukeire
            or UkeireInfo(count=51, tiles=["2p", "4p", "5p"]),
            ukeire_alt=ukeire_alt,
            statuses=HandStatuses(
                shanten=3,
                wait_shape=wait_shape,  # type: ignore[arg-type]
                dora_in_hand=dora_in_hand or [],
            ),
            danger=danger or {},
            shape_goals=shape_goals or [],
        ),
        player_action=player_action,
        mortal_best=mortal_best,
        diverge=diverge,
    )


_turn = make_turn


def false_safer_tip_turn() -> TurnExplainInput:
    """Screenshot-shaped turn: 2m genbutsu, thin 2p wall, high ukeire_alt on 1s."""
    return make_turn(
        shape_goals=["pinfu"],
        mortal_best="dahai 2m",
        player_action="dahai 1s",
        danger={"2m": "genbutsu"},
        ukeire=UkeireInfo(
            count=12,
            tiles=["2p", "3p", "4p", "3s", "W"],
            remaining_by_tile={"2p": 1, "3p": 4, "4p": 2, "3s": 3, "W": 2},
        ),
        ukeire_alt=UkeireInfo(
            count=63,
            tiles=["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m"],
        ),
        diverge=False,
    )


def yakuhai_haku_pair_turn() -> TurnExplainInput:
    """Haku pair (correct yakuhai) + singleton East (not a pair)."""
    turn = make_turn(
        shape_goals=["yakuhai"],
        mortal_best="dahai 1m",
        player_action="dahai E",
        diverge=True,
        ukeire=UkeireInfo(count=40, tiles=["2m"], remaining_by_tile={"2m": 3}),
        ukeire_alt=UkeireInfo(count=35, tiles=["2m"], remaining_by_tile={"2m": 3}),
    )
    turn.game_state.hand = [
        "1m",
        "2m",
        "3m",
        "4p",
        "5p",
        "6p",
        "3s",
        "4s",
        "5s",
        "P",
        "P",
        "E",
        "C",
        "7m",
    ]
    turn.features.context = {"jikaze": "E", "bakaze": "E"}
    return turn


def summary_paragraphs(summary: str) -> list[str]:
    """Split formatted summary into paragraphs (blank-line separated)."""
    return [p.strip() for p in summary.split("\n\n") if p.strip()]


def summary_lines(paragraph: str) -> list[str]:
    """Non-empty lines in a paragraph, without bullet prefix."""
    return [
        ln.strip().removeprefix("• ").strip()
        for ln in paragraph.split("\n")
        if ln.strip()
    ]
