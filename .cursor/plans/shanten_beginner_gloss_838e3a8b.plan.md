---
name: Shanten beginner gloss
overview: Add short parenthetical glosses for shanten (and paired “acceptances”) in Why? text, matching the existing yaku/dora glossary pattern so beginners understand “3-shanten” as distance from ready.
todos:
  - id: shanten-gloss-helpers
    content: Add _glossed_shanten_phrase / acceptances gloss helpers in explain.py
    status: completed
  - id: wire-template-llm
    content: Use glosses in template_explain + payload glossary + SYSTEM_PROMPT
    status: completed
  - id: gloss-tests
    content: Update substance/template tests; cover 1-shanten singular step
    status: completed
isProject: false
---

# Beginner glosses for shanten (and acceptances)

## Problem

Your screenshot’s Why? line is the template path:

> you’re **3-shanten** with about **55 acceptances**

`dora` already gets `(bonus tile)`, but `shanten` / `acceptances` stay unexplained jargon.

## Approach

Same pattern as [`yaku_dora_glosses`](.cursor/plans/yaku_dora_glosses_858462dd.plan.md): short parentheticals in Why? prose only. No overlay status-bar change (that strip lives in the sibling Copilot fork).

**Locked phrasing** (plain English; avoid unexplained “tenpai”):

| Term | Gloss |
|------|--------|
| `N-shanten` (N ≥ 1) | `N steps from ready` / `1 step from ready` when N=1 |
| `0` / tenpai (if mentioned) | `ready` |
| `acceptances` | `tiles that improve the hand` |

Template example after change:

> you’re 3-shanten (3 steps from ready) with about 55 acceptances (tiles that improve the hand)

## Code changes

In [`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py):

1. Add helpers next to `_GOAL_GLOSS` / `_glossed_dora_phrase`:

```python
_ACCEPTANCES_GLOSS = "tiles that improve the hand"

def _glossed_shanten_phrase(shanten: int) -> str:
    if shanten <= 0:
        return "tenpai (ready)"
    step = "step" if shanten == 1 else "steps"
    return f"{shanten}-shanten ({shanten} {step} from ready)"

def _glossed_acceptances_phrase(count: int) -> str:
    return f"about {count} acceptances ({_ACCEPTANCES_GLOSS})"
```

2. Update `template_explain` line (~284):

```python
bits.append(f"you’re {_glossed_shanten_phrase(shanten)} with {_glossed_acceptances_phrase(ukeire.count)}")
```

3. LLM consistency: put the same strings in `build_user_payload` (e.g. `hand_metric_glossary`) and nudge `SYSTEM_PROMPT` — when mentioning shanten/acceptances, include those parentheticals (parallel to `shape_goal_glossary`).

## Tests

Update assertions that expect the bare template string:

- [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py) — anchored/template samples should include `(… from ready)` and acceptances gloss
- Any shape-goal / ingest tests that substring-match the old `N-shanten with about X acceptances` form

Add a small unit check that `1-shanten` uses singular `step`.

## Out of scope

- Overlay status strip (`shanten 3 · ukeire 55`) — different repo
- Replacing “shanten” with only English (keep the term + gloss so players learn it)
- Longer encyclopedia definitions or tooltips
