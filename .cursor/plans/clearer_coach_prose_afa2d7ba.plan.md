---
name: Clearer coach prose
overview: Rewrite Why? template and prompt voice into short coach sentences—Throw X, improving-tile contrasts, fits yaku gloss—so Sensei explanations read like the plain-English rewrite instead of jargon semicolon soup.
todos:
  - id: wall-note-voice
    content: Rewrite wall_note contrast + shape phrase to improving-tiles / fits
    status: completed
  - id: template-coach
    content: Rebuild template_explain as Throw X sentences; skip duplicate acceptances on contrast; tanyao causal clause
    status: completed
  - id: prompt-align
    content: Update SYSTEM_PROMPT + substance anchors for new phrasing
    status: completed
  - id: tests
    content: Update string assertions; add West/tanyao/ukeire_alt golden test
    status: completed
isProject: false
---

# Clearer coach prose for Why?

## Goal

Make Why? text sound like:

> Throw West. That leaves about 55 tiles that can improve your hand, vs about 41 if you throw 7-sou. That fits tanyao (2–8 only; no 1/9, winds, or dragons)—West can’t stay in that hand.

Not:

> Mortal recommends West; … about 55 acceptances …; shape leans tanyao …; keeps more live acceptances (~55 vs ~41 …).

## Locked voice rules

- Lead with **Throw X** / **Throw X, not Y** (human tile labels already from `human_action_label`).
- Prefer **improving tiles** over **live acceptances** / stacked **acceptances** gloss when a contrast exists.
- Prefer **fits {goal}** over **shape leans**.
- Use **period-separated sentences**, not `; `.join` soup.
- When an ukeire contrast note exists, **do not** also emit the absolute “about N acceptances” line (avoid saying 55 twice). Still mention shanten when present.
- If `tanyao` is in `shape_goals` and Mortal’s cut is a terminal/honor, append a short causal clause: e.g. `West can’t stay in that hand`.

No separate post-pass normalizer—fix wording at the template/`wall_note`/prompt source.

## Code changes ([`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py))

### 1. `wall_note`

Change the contrast branch from:

```python
f"keeps more live acceptances (~{ukeire.count} vs ~{alt.count} after cutting {alt_label})"
```

to:

```python
f"about {ukeire.count} improving tiles left vs about {alt.count} if you throw {alt_label}"
```

Keep thinning / “already out” branches as-is (already plain).

### 2. `_shape_goal_phrase`

- `shape leans …` → `fits …`
- Dora-only stays `keeping dora (bonus tile) …`

### 3. `template_explain`

Rebuild as 2–3 short sentences:

1. **Action:** `Throw {best}` or `Throw {best}, not {other}` (diverge player or next-best).
2. **Efficiency:** wait shape if present; else if contrast `wall_note`, emit shanten (if any) + that note as its own sentence(s); else existing glossed shanten + acceptances phrase.
3. **Shape:** `That fits {glossed goals}…` (+ dora); if tanyao + cut is terminal/honor, append `—{tile} can’t stay in that hand`.
4. Defense bits (genbutsu) stay as an extra short sentence when relevant.

Detect contrast vs thin notes by checking whether `ukeire_alt` triggered the contrast branch (e.g. helper returns `(kind, text)` or `wall_note_contrast(turn)` bool) so absolute acceptances are skipped only for contrast, not for “already out”.

Terminal/honor check: small local helper in `explain.py` (same rule as [`features._is_terminal_or_honor`](src/shanten_sensei/features.py)) to avoid export churn.

### 4. `SYSTEM_PROMPT`

Nudge the LLM to the same voice:

- Lead with Throw X / Throw X, not Y.
- Prefer `improving tiles` and `fits tanyao (…)`; avoid `live acceptances`, `shape leans`, `Mortal recommends/prefers` as openers.
- Prefer rephrasing `wall_note` facts; don’t paste jargon.
- Include one locked example matching the West/tanyao rewrite pattern.

### 5. Substance anchors

In `_feature_anchors_in_summary`, treat the new contrast phrasing as an ukeire anchor (e.g. `improving tiles` + `vs about`, keep existing `live acceptances` for older LLM strings). No change to thin-claim logic.

## Tests

Update string expectations in:

- [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py) — `live acceptances` → new contrast string; template samples; LLM-style sample can stay valid if it still has anchors (update to new voice as the golden example).
- [`tests/test_shape_goals.py`](tests/test_shape_goals.py) — `shape leans` → `fits`.

Add one golden case: tanyao goals + honor cut (e.g. West) + `ukeire_alt` contrast → summary contains `Throw`, `improving tiles`, `vs about`, `fits tanyao`, and `can’t stay`.

Keep existing validate/substance tests green; `test_template_explain_live_contrasts_next_best` / honor Hatsu display should still pass (label checks unchanged).

## Out of scope

- Overlay UI / Aiming-for strip copy
- Renaming shanten term itself (keep `N-shanten (N steps from ready)` when shown)
- Claiming Mortal’s internal yaku plan beyond heuristic `shape_goals`
