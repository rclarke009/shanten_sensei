# Phase 1 contract

The explainer never invents evaluation. Every turn is a structured payload; the LLM only verbalizes it.

## Turn payload (`TurnExplainInput`)

Built from one mjai-reviewer Mortal `Entry` (a diverge when `is_equal` is false) plus derived features.

| Field | Source |
|-------|--------|
| `game_state` | mjai / reviewer entry: hand, calls, discards, dora, turn, scores, riichi flags |
| `mortal_output` | `expected` + `details[]` (action, q_value, prob) |
| `features` | Libraries: shanten, ukeire, wait shape, furiten, danger tags, statuses |
| `player_action` | `actual` from the entry |
| `mortal_best` | `expected` from the entry (must match top of `details` by q_value) |

See `src/shanten_sensei/schema.py` for the Pydantic models (source of truth).

## Obtaining a diverge fixture

1. Install [mjai-reviewer](https://github.com/Equim-chan/mjai-reviewer) + Mortal locally, **or** use the [mjai.ekyu.moe](https://mjai.ekyu.moe) web app for a practice / friend / offline log.
2. Export JSON (`--json` locally, or save the report JSON from the web app).
3. Cut a single diverge with the helper (preferred):

```bash
uv run --python .venv/bin/python scripts/extract_diverge.py path/to/review.json \
  --kyoku 0 --honba 0 --junme 3 \
  -o fixtures/diverge_00N/entry.json
```

If the same junme has multiple diverges (e.g. a discarded-tile decision and a call decision), disambiguate with `--mortal` / `--player` labels (`pon W`, `none`, …).

Alternatively: find an entry with `"is_equal": false` under `review.kyokus[].entries[]` and save a thin wrapper `{note, kyoku, entry}` under `fixtures/`.

Practice / review only — not for ranked live assistance.

## Fixture layout

```text
fixtures/diverge_001/   # synthetic ryanmen baseline
fixtures/diverge_002/   # real: midgame dahai (8s vs 6p)
fixtures/diverge_003/   # real: early honor cut
fixtures/diverge_004/   # real: missed pon
fixtures/diverge_005/   # real: missed chi (aka)
  entry.json            # one mjai-reviewer Mortal Entry (+ thin wrapper)
```

## Full reports

`sensei review <report.json>` accepts a full mjai-reviewer export (`review.kyokus[].entries[]`) and explains every entry where `is_equal` is false.

When the report includes top-level `mjai_log` + `player_id`, ingest replays the log to fill player rivers, visible discards, and dora indicators (so furiten / genbutsu / visible dora work on real exports). Thin single-entry fixtures without `mjai_log` are unchanged.

`sensei serve <report.json>` opens a local review UI (diverge list + status strip). **Why?** defaults to the offline template (`POST /api/explain/{n}`). Use `POST /api/explain/{n}?mode=llm` for LLM tips when `OPENAI_API_KEY` or `SENSEI_API_KEY` is set; failed grounding repairs to the template (same as `explain(use_llm=True)`).

## End-to-end check

```bash
uv run sensei explain fixtures/diverge_001/entry.json
uv run sensei review fixtures/review_mini/report.json
uv run sensei serve fixtures/review_mini/report.json
uv run pytest
```

`explain()` must pin `mortal_best` and must not recommend a different discard.

Live overlay turns use the same models via `turn_from_live()` — see [`phase2-kickoff.md`](phase2-kickoff.md).
