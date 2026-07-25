---
name: Shape yaku goals
overview: Add deterministic shape/yaku goal tags from the post-Mortal-discard hand, then have template and LLM Why? text only verbalize those tags — never invent yaku. Accuracy is verified with table-driven unit tests and grounding that rejects unlisted yaku names.
todos:
  - id: infer-shape-goals
    content: Add infer_shape_goals() + shape_goals on DerivedFeatures; call from extract_features on post-discard shape
    status: completed
  - id: wire-explain
    content: Template + payload + SYSTEM_PROMPT use shape_goals; grounding rejects unlisted yaku names
    status: completed
  - id: unit-tests
    content: Table-driven hand→tags tests + template/grounding explain tests
    status: completed
  - id: spot-check
    content: Spot-check a few golden/live turns; confirm phrasing is shape-leans not Mortal-intends
    status: completed
isProject: false
---

# Shape / yaku goals in Why?

## Can the AI handle it?

**Yes — if the LLM does not invent goals.** Mortal has no yaku field; asking ChatGPT to “guess the hand” will hallucinate. The reliable design matches existing Sensei rules (README: features are deterministic; LLM only translates):

1. **Python heuristics** tag likely goals from the hand after Mortal’s discard.
2. **Template + LLM** may only mention tags from that list (same pattern as `pinned_action`).
3. Phrase as **shape leans… / keeps … flex**, never “Mortal is going for tanyao.”

`mahjong.HandCalculator` scores **completed** winning hands, not mid-game shapes — skip it for v1. Use simple closed-hand heuristics (already have `mahjong.shanten` in [`features.py`](src/shanten_sensei/features.py)).

Skip Mortal % in Why text (chart already shows them).

```mermaid
flowchart LR
  Hand[Post-discard hand]
  Heur[infer_shape_goals]
  Feat[features.shape_goals]
  Why[template / LLM]
  Ground[validate: yaku only from list]

  Hand --> Heur --> Feat --> Why --> Ground
```

## v1 goal tags (allowlist)

Compute on **shape after Mortal discard** (same `shape_hand` path as ukeire in `extract_features`):

| Tag | Heuristic (conservative) |
|-----|--------------------------|
| `tanyao` | No terminals/honors in closed hand + calls (or only easy-to-cut ones already cut) |
| `yakuhai` | Pair or triplet of dragon / seat or round wind (winds from `context` when present; else dragons only) |
| `honitsu` | ≥11 tiles in one suit (closed + call suits), mixed honors OK |
| `chinitsu` | All tiles one suit, no honors |
| `toitoi` | ≥3 triplets/pairs-as-set-potential (count of tiles with ≥2 copies ≥4, few sequences) — only when strong |
| `chiitoi` | Standard 7-pairs shanten competitive vs regular (optional; only if chiitoi shanten ≤ regular) |
| `dora` | Reuse existing `dora_in_hand` (mention in prose, not a fake yaku) |

Emit at most **2–3** tags, highest confidence first. Prefer under-tagging over wrong tags.

Schema addition on [`DerivedFeatures`](src/shanten_sensei/schema.py) / context:

```python
shape_goals: list[str]  # e.g. ["tanyao", "yakuhai"]
```

Wire in [`extract_features`](src/shanten_sensei/features.py) → `build_user_payload` / `template_explain` in [`explain.py`](src/shanten_sensei/explain.py).

**Template example:**  
`Mortal prefers 🀄Chun over 🀘9-sou; shape leans tanyao with dora 3-sou.`

**LLM prompt nudge:** “If `shape_goals` is non-empty, you may name only those goals as likely shape (not Mortal’s plan). Never invent other yaku.”

**Grounding:** If summary mentions a known yaku word (`tanyao`, `yakuhai`, `honitsu`, `chinitsu`, `toitoi`, `chiitoitsu`/`chiitoi`, `ittsu`, `pinfu`, …) not in `shape_goals` (+ allow `dora` when `dora_in_hand`), fail → template repair (existing path).

## How we verify accuracy

| Layer | What |
|-------|------|
| **Unit tests** | Table of hands → expected `shape_goals` in [`tests/test_features.py`](tests/test_features.py) (and small `tests/test_shape_goals.py`). Include true positives and hard negatives (e.g. has 1m → not tanyao; mixed suits → not chinitsu). |
| **Explain tests** | Template includes goal phrase when tags present; omits when empty. Grounding rejects “pinfu” if not tagged. |
| **Fixture spot-check** | Run `sensei explain` / review on 5–10 golden diverge turns; manually confirm tags match beginner intuition. |
| **Live sanity** | One Why? on a clear tanyao-ish hand and one honor-heavy hand; confirm wording uses “shape leans,” not “Mortal is aiming for.” |

We are **not** verifying against Mortal’s internal intent (unavailable). We verify: heuristics match hand shape, and Why? never invents yaku outside the tag list.

## Out of scope (v1)

- Full EV / han–fu projections
- Mortal % in Why text
- HandCalculator scoring of imaginary agari
- Overlay UI changes (Why? already shows Sensei summary; [`why_panel_height`](.cursor/plans/why_panel_height_680882f8.plan.md) if lines clip)
- Seat/round wind yakuhai when bakaze/jikaze missing from live context (dragons-only until wired)