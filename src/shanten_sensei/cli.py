"""CLI: sensei explain / review / dump-turn / serve"""

from __future__ import annotations

import argparse
import json
import sys

from shanten_sensei.envutil import load_dotenv
from shanten_sensei.explain import explain, validate_explanation
from shanten_sensei.ingest import diverge_turns_from_path, turn_from_path
from shanten_sensei.schema import TurnExplainInput
from shanten_sensei.serve import serve_review


def _status_line(turn: TurnExplainInput) -> str:
    statuses = turn.features.statuses
    return (
        f"{'menzen' if statuses.menzen else 'open'} | "
        f"{'tenpai' if statuses.tenpai else f'{statuses.shanten}-shanten'} | "
        f"wait={statuses.wait_shape or '-'} | "
        f"furiten={statuses.furiten}"
    )


def _print_turn_human(turn: TurnExplainInput, summary: str) -> None:
    print(f"Mortal:  {turn.mortal_best}")
    print(f"Player:  {turn.player_action}")
    print(f"Shanten: {turn.features.shanten}  ukeire: {turn.features.ukeire.count}")
    print(f"Status:  {_status_line(turn)}")
    print()
    print(summary)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
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

    p_review = sub.add_parser(
        "review",
        help="Explain all diverge turns in a full mjai-reviewer report JSON",
    )
    p_review.add_argument("path", help="Path to mjai-reviewer --json report")
    p_review.add_argument(
        "--llm",
        action="store_true",
        help="Force LLM call for each diverge (requires API key)",
    )
    p_review.add_argument(
        "--json",
        action="store_true",
        help="Print list of turns + explanations as JSON",
    )
    p_review.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N diverge turns",
    )

    p_dump = sub.add_parser("dump-turn", help="Normalize entry → TurnExplainInput JSON")
    p_dump.add_argument("path")

    p_serve = sub.add_parser(
        "serve",
        help="Local review UI: diverge list + status strip + on-demand Why?",
    )
    p_serve.add_argument("path", help="Path to mjai-reviewer --json report")
    p_serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default 127.0.0.1)",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port (default 8765)",
    )
    p_serve.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Load only the first N diverge turns",
    )

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
            _print_turn_human(turn, result.summary)
            if errors:
                print("\nGrounding warnings:", "; ".join(errors), file=sys.stderr)
                return 2
        return 0

    if args.cmd == "review":
        diverges = diverge_turns_from_path(args.path, limit=args.limit)
        records: list[dict] = []
        warning_count = 0
        use_llm = True if args.llm else None

        for d in diverges:
            result = explain(d.turn, use_llm=use_llm)
            errors = validate_explanation(d.turn, result)
            if errors:
                warning_count += 1
            records.append(
                {
                    "index": d.index,
                    "kyoku": d.kyoku,
                    "honba": d.honba,
                    "junme": d.junme,
                    "turn": d.turn.model_dump(),
                    "explanation": result.model_dump(),
                    "grounding_errors": errors,
                }
            )
            if not args.json:
                print(
                    f"--- E{d.index} / kyoku {d.kyoku} honba {d.honba} "
                    f"/ junme {d.junme} ---"
                )
                _print_turn_human(d.turn, result.summary)
                if errors:
                    print(
                        "Grounding warnings:",
                        "; ".join(errors),
                        file=sys.stderr,
                    )
                print()

        if args.json:
            print(
                json.dumps(
                    {
                        "diverges": records,
                        "diverge_count": len(records),
                        "warning_count": warning_count,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(f"{len(records)} diverges, {warning_count} warnings")

        return 2 if warning_count else 0

    if args.cmd == "serve":
        serve_review(
            args.path,
            host=args.host,
            port=args.port,
            limit=args.limit,
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
