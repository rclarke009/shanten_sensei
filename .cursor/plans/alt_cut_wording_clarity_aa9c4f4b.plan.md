---
name: Alt cut wording clarity
overview: Reword the ukeire-contrast alternate-discard sentence so it reads as a hypothetical counterfactual (“if you threw X instead…”) rather than a second recommendation, updating the template, LLM prompt example, and tests.
todos:
  - id: reword-alt-sentence
    content: Change alternate line in _named_improving_tiles_sentences to "If you threw {alt} instead, you'd mostly improve via {tiles}"
    status: completed
  - id: prompt-example
    content: Add SYSTEM_PROMPT ukeire-contrast example + rule forbidding bare "Throwing {alternate}…" for alt improving tiles
    status: completed
  - id: update-tests
    content: Update contrast assertions in test_explanation_substance.py and test_template_goldens.py
    status: completed
isProject: false
---

# Clearer alternate-cut wording in ukeire contrast tips

## Problem

In ukeire-contrast tips, the fourth move sentence currently reads:

> Throwing 2-pin mostly improves via 1-man, 2-man, 3-man, and 4-man.

After “Throw Hatsu, not 2-pin” and the ukeire gap line, this sounds like 2-pin is another viable pick. It is not — it is the **runner-up cut** being compared against the recommendation.

## Target copy

Keep the recommended-cut line unchanged. Reword only the alternate line in [`_named_improving_tiles_sentences`](src/shanten_sensei/explain.py):

| Line | Before | After |
|------|--------|-------|
| Recommended | `Throwing {best} keeps draws like {tiles}` | *(unchanged)* |
| Alternate | `Throwing {alt} mostly improves via {tiles}` | `If you threw {alt} instead, you'd mostly improve via {tiles}` |

**Example block** (your screenshot shape):

```
Throw Hatsu, not 2-pin.
That leaves about 82 improving tiles left vs about 73 if you throw 2-pin.
Throwing Hatsu keeps draws like 1-man, 2-man, 3-man, and 4-man.
If you threw 2-pin instead, you'd mostly improve via 1-man, 2-man, 3-man, and 4-man.

You're 4-shanten.
An opponent already discarded Hatsu, so they can't ron it from you.
```

“Instead” ties explicitly to the “not 2-pin” lead; “If you threw…” makes the hypothetical framing obvious.

## Code change (single string)

In [`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py) ~644–646:

```python
sentences.append(
    f"If you threw {alt_label} instead, you'd mostly improve via {alt_named}"
)
```

No API or layout changes — still one sentence appended to `move_sents`, still newline-joined on contrast path.

## LLM prompt alignment

Add one **ukeire-contrast example** to `SYSTEM_PROMPT` in the same file (the contrast line-break example from [contrast_tip_line_breaks plan](.cursor/plans/contrast_tip_line_breaks_d13e85f7.plan.md) was layout-only and never added with named-tile lines). Mirror the template voice:

```
Throw 4-man, not 2-sou. That leaves about 47 improving tiles left vs about 42 if you throw 2-sou.
Throwing 4-man keeps draws like 6-man, 7-man, 8-man, and 9-man.
If you threw 2-sou instead, you'd mostly improve via 4-man, 6-man, 7-man, and 8-man.
You're 3-shanten.
```

Also add a one-line rule near the ukeire-contrast guidance (~169): when naming alternate improving tiles, use **“If you threw {alternate} instead…”** — never bare “Throwing {alternate}…” which reads like a second recommendation.

## Tests

| File | Update |
|------|--------|
| [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py) `test_named_improving_tiles_on_ukeire_contrast` | Assert `if you threw` and `instead` in summary; drop or relax `mostly improves via` substring assert (phrase still present inside new sentence) |
| [`tests/eval/test_template_goldens.py`](tests/eval/test_template_goldens.py) `test_template_tanyao_honor_ukeire_contrast` | Same: alternate move line matches `if you threw` + `instead` |

Run: `pytest tests/test_explanation_substance.py tests/eval/test_template_goldens.py -k contrast`

## Out of scope

- Rewording the recommended line (“keeps draws like”) — already reads as advice for the chosen cut
- Grounding validator changes — [`grounding.py`](src/shanten_sensei/grounding.py) rich-marker check already passes via `keeps draws like` / `vs about`; no new anchors needed
- Narrow-contrast path (ukeire gap 1–2) — does not emit named-tile sentences today; unchanged
