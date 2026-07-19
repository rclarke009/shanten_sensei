---
name: sensei review CLI
overview: Add `sensei review` to walk a full mjai-reviewer JSON report, explain every diverge turn via the existing ingest/explain pipeline, and print a readable turn list (template by default, LLM with `--llm`).
todos:
  - id: ingest-walk
    content: Add iter_diverge_turns() over review.kyokus[].entries (is_equal false) in ingest.py
    status: completed
  - id: cli-review
    content: Add sensei review subcommand with --llm/--json/--limit and human output
    status: completed
  - id: fixture-tests
    content: Add fixtures/review_mini/report.json + tests/test_review.py
    status: completed
  - id: docs
    content: Update README checklist and usage one-liner for sensei review
    status: completed
isProject: false
---

# Implement `sensei review` CLI

## Goal

Close the Phase 1 CLI gap: given a full mjai-reviewer report (e.g. [`game_logs/review.json`](game_logs/review.json)), list every diverge turn with status strip + coach text.

```text
sensei review <review.json> [--llm] [--json] [--limit N]
```

## Data shape (already confirmed)

Top-level report has `review.kyokus[]`; each kyoku has `kyoku`, `honba`, `relative_scores`, `entries[]`. Each entry has `is_equal`, `junme`, `expected`/`actual`, `state`, etc. Existing [`turn_from_entry`](src/shanten_sensei/ingest.py) already accepts `kyoku_meta`.

Your real log has **39 diverges / 59 entries** — default offline template so a full run stays free; `--llm` is opt-in.

## Implementation

### 1. Ingest: walk full reports

In [`src/shanten_sensei/ingest.py`](src/shanten_sensei/ingest.py):

- Add `iter_diverge_turns(blob) -> Iterator[tuple[dict, TurnExplainInput]]` (or a small named result) that:
  - Accepts a full report (`blob["review"]["kyokus"]`) **or** a bare `{ "kyokus": [...] }`
  - Yields only entries where `is_equal` is false
  - Calls existing `turn_from_entry(entry, kyoku_meta={kyoku, honba, relative_scores})`
- Keep `turn_from_path` / single-entry path unchanged for `explain` / fixtures

### 2. CLI: `review` subcommand

In [`src/shanten_sensei/cli.py`](src/shanten_sensei/cli.py):

- Add `sensei review <path>`
- Flags (mirror `explain`):
  - `--llm` — force LLM for each diverge
  - `--json` — dump list of `{kyoku, honba, junme, turn, explanation, grounding_errors}`
  - `--limit N` — stop after N diverges (smoke / cost control)
- Human output per diverge (reuse explain formatting):

```text
--- E1 / kyoku 0 honba 0 / junme 3 ---
Mortal:  dahai 9p
Player:  dahai 5s
Shanten: 0  ukeire: 6
Status:  menzen | tenpai | wait=ryanmen | furiten=False

<summary>
```

- Exit `2` if any turn has grounding errors (same spirit as `explain`); print a final count line (`39 diverges, 0 warnings`)

### 3. Tests + tiny fixture

- Add [`fixtures/review_mini/report.json`](fixtures/review_mini/report.json): minimal full-report shape with 2–3 kyoku entries (mix of `is_equal` true/false), enough `state`/`details` for ingest — do **not** check in the 39-diverge `game_logs/review.json`
- Add [`tests/test_review.py`](tests/test_review.py):
  - Walks mini report → only diverges
  - Offline `explain` pins Mortal on each
  - CLI smoke: `main(["review", str(path)])` returns 0 and prints headers

### 4. Docs touch

In [`README.md`](README.md) Phase 1 checklist: mark `sensei review` done; show the one-liner:

```bash
uv run --python .venv/bin/python sensei review game_logs/review.json
```

Optionally one sentence in [`docs/phase1-contract.md`](docs/phase1-contract.md) that full reports are accepted via `sensei review`.

## Out of scope

- Review UI / floating panel
- Live overlay (Phase 2)
- More golden fixtures (follow-up after this lands)
