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
3. Find an entry with `"is_equal": false` under `review.kyokus[].entries[]`.
4. Save that single entry (plus optional kyoku context) under `fixtures/`.

Practice / review only — not for ranked live assistance.

## Fixture layout

```text
fixtures/diverge_001/
  entry.json          # one mjai-reviewer Mortal Entry (+ thin wrapper)
  turn_input.json     # optional: pre-normalized TurnExplainInput
```

## End-to-end check

```bash
uv run sensei explain fixtures/diverge_001/entry.json
uv run pytest
```

`explain()` must pin `mortal_best` and must not recommend a different discard.
