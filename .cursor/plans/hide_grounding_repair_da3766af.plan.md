---
name: Hide grounding repair
overview: "Stop appending internal `(grounding repair: …)` text to live Sensei summaries so players only see the clean template fallback; keep the repair reason in logs for debugging."
todos:
  - id: omit-suffix
    content: Stop appending grounding repair to summary; log errors instead in explain()
    status: completed
  - id: update-tests
    content: Flip hard-grounding test to expect clean summary (+ optional caplog)
    status: completed
isProject: false
---

# Hide grounding-repair suffix from players

## Problem

When LLM output fails hard grounding checks (e.g. summary omitted pinned `dahai P`), [`explain()`](src/shanten_sensei/explain.py) correctly swaps in `template_explain`, then appends a debug suffix to `summary`. That leaked into the overlay as:

> … Haku is a dead-end tile. (grounding repair: summary does not mention pinned action/tile 'dahai P')

Substance-only repairs already omit the suffix; hard failures still append it.

## Fix (locked)

Never put `(grounding repair: …)` on `Explanation.summary`. Always return the clean repaired template for the overlay/API.

Log the repair reason instead (same module):

```python
import logging
logger = logging.getLogger(__name__)
# on repair:
logger.info("grounding repair: %s", "; ".join(errors))
```

Remove the `substance_only` special case for the suffix — both paths stay silent in the summary.

## Files

1. [`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py) — in `explain()`, drop the summary append; add `logging` + `logger.info` when `errors` is non-empty after LLM use (or whenever repair runs).
2. [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py) — rename/update `test_explain_hard_grounding_still_appends_suffix` to assert:
   - `"grounding repair" not in result.summary`
   - repaired text still grounded (template wins; e.g. no invented `pinfu` if goals are tanyao-only — keep existing invent-yaku coverage intent: hard fail → template, clean summary)
   - optionally `caplog` that an info log mentions `grounding repair` / the error string

## Out of scope

- Changing validation rules or `_mentions_tile` (why LLM failed on Haku/`P`)
- New API fields for repair metadata
- Overlay UI changes
