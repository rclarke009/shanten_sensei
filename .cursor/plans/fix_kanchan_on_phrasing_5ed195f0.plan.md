---
name: Fix kanchan on phrasing
overview: "\"Isolated kanchan on 8-man\" is ambiguous jargon — most players won't parse \"on 8-man\" correctly, and Sensei's own voice already uses \"on TILE\" to mean waits. Steer mid-hand shape notes to the clearer cut-subject phrasing the template already uses."
todos:
  - id: prompt-ban-on
    content: "Update SYSTEM_PROMPT: ban 'kanchan/penchan/fragment on TILE'; require cut-clears voice"
    status: completed
  - id: grounding-reject-on
    content: Reject isolated_kanchan/penchan summaries matching '… on {cut}'
    status: completed
  - id: regression-test
    content: Add substance/grounding test for 'kanchan on 8-man' style drift
    status: completed
isProject: false
---

# Fix ambiguous "kanchan on 8-man" phrasing

## Verdict

**No.** Most players would not clearly know what "on 8-man" means here.

- In mahjong English (and in Sensei itself: "Waiting on …", "furiten on …"), **on TILE = the wait tile**.
- Here the shape is a **6–8 kanchan** (missing 7). The note is attached to the cut end `8m`, not a wait for 8-man.
- So "isolated kanchan … on 8-man" reads like "waiting on 8-man" or "the kanchan *is* 8-man" — both wrong.

The offline template already says it clearly:

```819:822:src/shanten_sensei/explain.py
    if note.kind == "isolated_kanchan":
        return f"{cut_label} clears a closed middle (kanchan) shape"
    if note.kind == "isolated_penchan":
        return f"{cut_label} clears an edge (penchan) shape"
```

The screenshot text is LLM drift from that pattern.

## Locked approach

Ban "shape-note on TILE" voice; require cut-as-subject voice matching the template / existing prompt examples (`"2-man clears a closed middle"`).

### 1. Prompt ([`explain.py`](src/shanten_sensei/explain.py) `SYSTEM_PROMPT`)

In the `hand_shape_notes` rules, add explicitly:

- Never write `kanchan` / `penchan` / `fragment` **on** `{tile}` (that sounds like a wait).
- Prefer: `{cut} clears a closed middle (kanchan) shape` / `{cut} clears an edge (penchan) shape`.
- Optional: if naming both ends helps, say `6–8 kanchan` — never `kanchan on 8-man`.

### 2. Grounding ([`validate_explanation`](src/shanten_sensei/explain.py))

When `hand_shape_notes` includes `isolated_kanchan` or `isolated_penchan`, reject summaries matching roughly:

`\b(kanchan|penchan|fragment)\s+on\s+{cut}`

→ repair to template (same path as dead-end polarity).

### 3. Test ([`tests/test_explanation_substance.py`](tests/test_explanation_substance.py))

- Assert template still says `2-man clears a closed middle`.
- Assert `validate_explanation` rejects `… isolated kanchan … on 2-man` (or 8-man) while that note is present.

## Out of scope

- Renaming the feature tag or detecting both kanchan ends in the UI.
- Changing when `_is_isolated_kanchan_cut` fires (5-6-8 still tags 8m as kanchan end; phrasing fix is enough for this bug).
