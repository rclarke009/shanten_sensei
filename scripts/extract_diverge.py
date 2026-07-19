#!/usr/bin/env python3
"""Extract one diverge Entry from a full mjai-reviewer report into a fixture wrapper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running without install when PYTHONPATH includes src/
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from shanten_sensei.ingest import kyokus_from_report, load_json  # noqa: E402
from shanten_sensei.tiles import action_to_label  # noqa: E402


def find_diverge(
    blob: dict,
    *,
    kyoku: int,
    honba: int,
    junme: int,
    mortal: str | None = None,
    player: str | None = None,
) -> tuple[dict, dict]:
    """Return (kyoku_meta_slice, entry) for the matching diverge."""
    matches: list[tuple[dict, dict]] = []
    for k in kyokus_from_report(blob):
        if k.get("kyoku") != kyoku or k.get("honba") != honba:
            continue
        for entry in k.get("entries") or []:
            if entry.get("is_equal", False):
                continue
            if entry.get("junme") != junme:
                continue
            if mortal is not None and action_to_label(entry["expected"]) != mortal:
                continue
            if player is not None and action_to_label(entry["actual"]) != player:
                continue
            matches.append((k, entry))
    loc = f"kyoku={kyoku} honba={honba} junme={junme}"
    if mortal is not None:
        loc += f" mortal={mortal!r}"
    if player is not None:
        loc += f" player={player!r}"
    if not matches:
        raise SystemExit(f"no diverge found for {loc}")
    if len(matches) > 1:
        labels = [
            f"M={action_to_label(e['expected'])} P={action_to_label(e['actual'])}"
            for _, e in matches
        ]
        raise SystemExit(
            f"ambiguous: {len(matches)} diverges for {loc}: {labels}. "
            "Pass --mortal / --player to disambiguate."
        )
    return matches[0]


def build_wrapper(
    blob: dict,
    kyoku_row: dict,
    entry: dict,
) -> dict:
    log_id = blob.get("log_id") or "unknown"
    player_id = blob.get("player_id")
    seat = f"seat {player_id}" if player_id is not None else "seat ?"
    kyoku = kyoku_row.get("kyoku")
    honba = kyoku_row.get("honba")
    junme = entry.get("junme")
    mortal = action_to_label(entry["expected"])
    player = action_to_label(entry["actual"])
    shanten = entry.get("shanten")
    shanten_bit = f" at shanten {shanten}" if shanten is not None else ""

    note = (
        f"Real game {log_id}, player {seat}, "
        f"kyoku {kyoku} honba {honba}, junme {junme}. "
        f"Mortal wanted {mortal}, player chose {player}{shanten_bit}."
    )
    kyoku_meta = {
        "kyoku": kyoku,
        "honba": honba,
        "relative_scores": kyoku_row.get("relative_scores"),
    }
    if "end_status" in kyoku_row:
        kyoku_meta["end_status"] = kyoku_row["end_status"]

    return {"note": note, "kyoku": kyoku_meta, "entry": entry}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cut one diverge Entry from an mjai-reviewer JSON report."
    )
    parser.add_argument("report", type=Path, help="Path to full review JSON")
    parser.add_argument("--kyoku", type=int, required=True)
    parser.add_argument("--honba", type=int, required=True)
    parser.add_argument("--junme", type=int, required=True)
    parser.add_argument(
        "--mortal",
        help="Disambiguate by Mortal action label (e.g. 'pon W')",
    )
    parser.add_argument(
        "--player",
        help="Disambiguate by player action label (e.g. 'none')",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output fixture path (e.g. fixtures/diverge_003/entry.json)",
    )
    args = parser.parse_args(argv)

    blob = load_json(args.report)
    kyoku_row, entry = find_diverge(
        blob,
        kyoku=args.kyoku,
        honba=args.honba,
        junme=args.junme,
        mortal=args.mortal,
        player=args.player,
    )
    wrapper = build_wrapper(blob, kyoku_row, entry)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(wrapper, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
