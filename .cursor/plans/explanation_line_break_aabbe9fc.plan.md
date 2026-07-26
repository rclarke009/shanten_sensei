---
name: Explanation line break
overview: Insert a paragraph break in Sensei `summary` between move/efficiency advice and hand-state/goal advice, and make the review UI honor that newline.
todos:
  - id: join-helper
    content: Add _join_summary_paragraphs and split discard/call/riichi template sentences; reorder contrast so ukeire precedes standalone shanten
    status: completed
  - id: prompt-css
    content: "Nudge SYSTEM_PROMPT examples for a paragraph break; add white-space: pre-line on .why-box .summary"
    status: completed
  - id: tests
    content: Assert newline between efficiency and state/goal chunks on a contrast golden
    status: completed
isProject: false
---

# Visual break between advice chunks

## Goal

Turn one blob:

> Throw 5-man. This keeps about 13 tiles… about 10. You're 1-shanten… aiming for pinfu…

into two paragraphs:

```
Throw 5-man. This keeps about 13 tiles… about 10.
You're 1-shanten… aiming for pinfu…
```

No new schema fields. Keep a single `Explanation.summary` string with an embedded `\n`.

## Split rule (locked)

| Paragraph | Contents |
|-----------|----------|
| 1 – move/efficiency | Lead action (Throw / Skip / Declare…) + wait shape + wall/ukeire notes |
| 2 – state/goals+ | Standalone shanten, shape goals / mid-hand, furiten, danger, score |

When shanten is already bundled with acceptances in one sentence (`You're N-shanten with about N acceptances`), that sentence stays in paragraph 1; paragraph 2 starts at goals/mid-hand/etc.

## Code changes

### 1. Template join in [`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py)

Add a small helper, e.g. `_join_summary_paragraphs(first, second) -> str`, that joins each list with `". "` and inserts `\n` between non-empty groups.

Use it in:
- `template_explain` (discard)
- `_template_explain_call`
- `_template_explain_riichi`

**Discard contrast path reorder** (needed so the break matches the screenshot): today contrast emits shanten *before* the ukeire note. Change to:

1. Throw…
2. That leaves {ukeire contrast}
3. `\n`
4. You're N-shanten
5. That fits / mid-hand / defense / score…

Track the split with two lists (or a split index) while appending—no second pass over prose.

### 2. LLM prompt nudge (same file)

In `SYSTEM_PROMPT`, tell the model to put a line break between the move/ukeire chunk and the shanten/aiming chunk, and update the discard examples to show two paragraphs (same voice, just `\n` between them). Overlay already renders newlines in its ScrolledText; no overlay code change required for the string itself.

### 3. Review UI in [`web/review.html`](web/review.html)

`.why-box .summary` currently has no `white-space` rule, so `\n` collapses. Add:

```css
.why-box .summary { font-size: 1.05rem; white-space: pre-line; }
```

`renderWhy` can keep using a single text node.

### 4. Tests

In an existing golden (e.g. ukeire-alt contrast in [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py) or shape-goal fixtures):

- Assert `summary` contains `\n`
- Assert throw/ukeire text is before the break and shanten or `fits` after it when both exist
- Keep substring asserts; they still pass with a newline in the middle

## Out of scope

- Splitting into two API fields or two DOM blocks
- Overlay GUI changes (newline already displays)
- Rewriting coach wording beyond the contrast-path sentence order tweak above
