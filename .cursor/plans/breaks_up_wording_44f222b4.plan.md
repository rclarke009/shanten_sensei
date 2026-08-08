---
name: Breaks up wording
overview: Replace "clears" with "breaks up" in kanchan/penchan shape-note coaching text across templates, LLM prompt examples, grounding validation, and golden tests.
todos:
  - id: update-templates
    content: Change kanchan/penchan template strings and SYSTEM_PROMPT examples in explain.py
    status: completed
  - id: update-grounding
    content: Update _tile_claimed_as_cut_note regex in grounding.py to match breaks up
    status: completed
  - id: update-tests
    content: Fix golden assertion in test_template_goldens.py and run targeted pytest
    status: completed
isProject: false
---

# Replace "clears" with "breaks up" in shape notes

## Goal

Make kanchan/penchan mid-hand tips easier to parse for beginners:

- Before: `9-sou clears a closed middle (kanchan) shape`
- After: `9-sou breaks up a closed middle (kanchan) shape`

Same change for penchan: `breaks up an edge (penchan) shape`.

## Files to change

### 1. Template output — [`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py)

Update `_midhand_shape_clause_from_note` (lines ~1197–1200):

```python
return f"{cut_label} breaks up a closed middle (kanchan) shape"
return f"{cut_label} breaks up an edge (penchan) shape"
```

Update `SYSTEM_PROMPT` examples in the same file:

- Line ~92: `kanchan/penchan clear` → `kanchan/penchan break-up` (internal label only)
- Lines ~151–152: example sentences use `breaks up` instead of `clears`

### 2. Grounding regex — [`src/shanten_sensei/grounding.py`](src/shanten_sensei/grounding.py)

In `_tile_claimed_as_cut_note`, update the cut-note polarity matcher (~line 747):

```python
rf"{label}\s+breaks\s+up\s+(?:a\s+|an\s+)?(?:{kind_alt})\b"
```

This keeps validation working when the LLM paraphrases with the same verb as the template.

### 3. Golden test — [`tests/eval/test_template_goldens.py`](tests/eval/test_template_goldens.py)

Update assertion (~line 214):

```python
assert "2-man breaks up a closed middle" in result2.summary
```

## Verification

Run targeted tests:

```bash
pytest tests/eval/test_template_goldens.py::test_template_floating_terminal_and_isolated_kanchan -q
pytest tests/test_grounding.py -q
```

No changes needed in [`features.py`](src/shanten_sensei/features.py) — detection logic is unchanged; only the rendered phrase changes.

## Out of scope

- Historical `.cursor/plans/*.md` files (they reference old wording but are not user-facing)
- Unrelated uses of "clears" elsewhere (e.g. Why? box clearing in [`docs/live-setup.md`](docs/live-setup.md))
