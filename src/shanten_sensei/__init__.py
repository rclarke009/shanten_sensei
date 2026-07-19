"""Shanten Sensei — grounded Mortal explanations for riichi learners."""

from shanten_sensei.schema import Explanation, TurnExplainInput

__all__ = ["Explanation", "TurnExplainInput", "explain", "turn_from_live"]
__version__ = "0.1.0"


def __getattr__(name: str):
    if name == "explain":
        from shanten_sensei.explain import explain

        return explain
    if name == "turn_from_live":
        from shanten_sensei.live import turn_from_live

        return turn_from_live
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
