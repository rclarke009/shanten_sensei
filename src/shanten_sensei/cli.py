"""CLI: sensei explain <entry.json>"""

from __future__ import annotations

import argparse
import json
import sys

from shanten_sensei.explain import explain, validate_explanation
from shanten_sensei.ingest import turn_from_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sensei",
        description="Shanten Sensei — grounded Mortal explanations (practice/review only)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_explain = sub.add_parser("explain", help="Explain one diverge entry JSON")
    p_explain.add_argument("path", help="Path to fixture / mjai-reviewer entry JSON")
    p_explain.add_argument(
        "--llm",
        action="store_true",
        help="Force LLM call (requires OPENAI_API_KEY or SENSEI_API_KEY)",
    )
    p_explain.add_argument(
        "--json",
        action="store_true",
        help="Print full TurnExplainInput + Explanation as JSON",
    )

    p_dump = sub.add_parser("dump-turn", help="Normalize entry → TurnExplainInput JSON")
    p_dump.add_argument("path")

    args = parser.parse_args(argv)

    if args.cmd == "dump-turn":
        turn = turn_from_path(args.path)
        print(turn.model_dump_json(indent=2))
        return 0

    if args.cmd == "explain":
        turn = turn_from_path(args.path)
        result = explain(turn, use_llm=True if args.llm else None)
        errors = validate_explanation(turn, result)
        if args.json:
            print(
                json.dumps(
                    {
                        "turn": turn.model_dump(),
                        "explanation": result.model_dump(),
                        "grounding_errors": errors,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(f"Mortal:  {turn.mortal_best}")
            print(f"Player:  {turn.player_action}")
            print(f"Shanten: {turn.features.shanten}  ukeire: {turn.features.ukeire.count}")
            statuses = turn.features.statuses
            print(
                "Status:  "
                f"{'menzen' if statuses.menzen else 'open'} | "
                f"{'tenpai' if statuses.tenpai else f'{statuses.shanten}-shanten'} | "
                f"wait={statuses.wait_shape or '-'} | "
                f"furiten={statuses.furiten}"
            )
            print()
            print(result.summary)
            if errors:
                print("\nGrounding warnings:", "; ".join(errors), file=sys.stderr)
                return 2
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
