---
name: Yaku dora glosses
overview: Add short beginner parentheticals next to yaku tags and “dora” in Why? text (template + LLM glossary), using plain language (winds/dragons, not “honors”), without changing heuristic tagging.
todos:
  - id: gloss-dict
    content: Add goal/dora gloss map; format in _shape_goal_phrase
    status: completed
  - id: llm-glossary
    content: Expose glossary in payload + SYSTEM_PROMPT nudge
    status: completed
  - id: gloss-tests
    content: Update test_shape_goals for parenthetical definitions
    status: completed
isProject: false
---

# Parenthetical glosses for yaku and dora

## Goal

When Why? mentions a shape goal or dora, append a brief beginner definition in parentheses. Avoid jargon like “honors” / “simples” — say winds/dragons and 1/9 instead:

- `tanyao (2–8 only; no 1/9, winds, or dragons)`
- `yakuhai (dragon or seat/round wind)`
- `honitsu (one suit + winds/dragons OK)`
- `chinitsu (one suit only)`
- `toitoi (all triplets)`
- `chiitoi (seven pairs)`
- `dora (bonus tile)` — before the tile label

Example: `shape leans tanyao (2–8 only; no 1/9, winds, or dragons) with dora (bonus tile) 🀒3-sou.`

## Approach

Centralize gloss strings in [`explain.py`](src/shanten_sensei/explain.py) (next to `_shape_goal_phrase`):

```python
_GOAL_GLOSS = {
    "tanyao": "2–8 only; no 1/9, winds, or dragons",
    "yakuhai": "dragon or seat/round wind",
    "honitsu": "one suit + winds/dragons OK",
    "chinitsu": "one suit only",
    "toitoi": "all triplets",
    "chiitoi": "seven pairs",
}
_DORA_GLOSS = "bonus tile"
```

Update `_shape_goal_phrase` to format each goal as `{tag} ({gloss})` and dora as `dora (bonus tile) {label}`.

Also put the same map in `build_user_payload` as `shape_goal_glossary` / note in `SYSTEM_PROMPT`: when naming a goal or dora, include the short parenthetical from the glossary (keeps LLM path consistent).

Grounding stays tag-based (still matches `\btanyao\b` etc.); no change to `infer_shape_goals`.

## Tests

Update [`tests/test_shape_goals.py`](tests/test_shape_goals.py):

- Template with `tanyao` + dora asserts winds/dragons phrasing and `(bonus tile)`
- Multi-goal case asserts glosses on each tag
- Grounding allowlist tests still pass

## Out of scope

- Overlay UI glossary tooltips
- Longer encyclopedia definitions
- Changing which hands get tagged
