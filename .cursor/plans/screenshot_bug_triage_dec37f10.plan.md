---
name: Screenshot bug triage
overview: "Triage of the six live screenshots: the dominant real bug is open-hand desync producing the `shanten 8 · ukeire 0` sentinel and stale/wrong discard tips; terminal `Route` errors and `Main Thread(404)` are not the cause."
todos:
  - id: ship-calls-plumbing
    content: Confirm overlay my_calls + turn_from_live(calls=) is committed/running in the build that produced the screenshots
    status: completed
  - id: ship-sentinel-hud
    content: Confirm status_line_from_features hides shanten==8 as hand-sync unavailable
    status: completed
  - id: ship-tip-guards
    content: Confirm zero-acceptances wording + dahai-not-in-hand Why skip are live
    status: completed
isProject: false
---

# Screenshot bug triage

## Verdict

Yes — there is one real systemic bug visible across nearly every frame, plus a few related tip/desync failures. Several things that look broken are not.

```mermaid
flowchart LR
  call["Chi/pon shortens tehai"]
  noCalls["Sensei gets calls=[]"]
  sentinel["shanten 8 / ukeire 0"]
  tips["Why? invents dead-end / genbutsu / wrong tiles"]
  call --> noCalls --> sentinel --> tips
```

---

## Real bugs

### 1. `shanten 8 · ukeire 0` on every tip (all 6 shots)

**Real.** `8` is a malformed-hand sentinel in [`features.py`](src/shanten_sensei/features.py) (`_shanten_with_melds`), not a mahjong distance. It fires when `len(closed) + 3×melds ∉ {13,14}`.

Live path was stripping meld tiles from the closed hand and not passing open melds into Sensei → after chi/pon, status sticks on `shanten 8 · ukeire 0`, and tips then riff on “0 acceptances / dead-end.”

Already planned/fixed in working trees via [fix_live_status_errors_4fe5d6f1.plan.md](.cursor/plans/fix_live_status_errors_4fe5d6f1.plan.md): overlay tracks `my_calls`, passes `calls=` into `turn_from_live`, and HUD shows `hand sync · status unavailable` instead of the sentinel.

### 2. Tips naming tiles not in the hand

**Real, related.** Examples:

- “Throw 3-pin” / “Throw 5-man” when the board has neither
- AI Guidance also saying “Discard 5 Man” (Mortal reaction desynced, not only LLM mash)
- “Throw 7-man, not 7-pin” when there is no 7-pin
- “8-sou does not help” while holding an 8-sou triplet

Causes: bad metrics from (1) + stale Mortal reaction vs current tehai. Overlay now skips Why when recommended dahai ∉ hand (`_dahai_reaction_missing_from_hand`); AI Guidance can still show Mortal’s bad `pai` until hand sync is fixed.

### 3. Wording: “about 0 acceptances”

**Real nit** (visible in the 1:27 shot). Exact zero should not say “about.” Covered in the same live-status plan (`_glossed_acceptances_phrase`).

### 4. Strategy nonsense fueled by bad metrics

**Real symptom, not a separate root cause.** Genbutsu claims that don’t match the pond, “no improving tiles,” tanyao-vs-cut contradictions — mostly LLM/template prose running on garbage shanten/ukeire from (1).

---

## Not bugs (or not the hand bug)

| Looks like | Actually |
| --- | --- |
| `Failed to parse … heartbeat` / `Error: 'Route'` | Liqi schema miss for `Route.heartbeat`; logged and ignored; does not mutate hand |
| `Main Thread(404)` / `Browser(404)` green | FPS counters (~400), not HTTP 404 |
| “Chi 5-pin” during a chii prompt | Often correct: `pai` is the opponent discard being called; consumed tiles come from your hand |
| Practice banner / ranked restriction text | As authored |

Emoji vs label mismatches (e.g. 1-man glyph next to “5-man”) are usually macOS mahjong-font fallback or tip naming a tile that isn’t on the board — not a swapped tile map in [`tiles.py`](src/shanten_sensei/tiles.py).

---

## Per-screenshot map

- **1:27** — Throw 5-man not in hand; AI Guidance agrees; `about 0 acceptances`; sentinel status
- **1:28** — Sentinel; “6-pin doesn’t connect” despite a quad; tip partly ok (1m exists) but metrics wrong
- **1:29** — Throw 7m not 7p (7p absent); dora chip says 7m; sentinel
- **1:29:56** — Throw 3p not in hand; genbutsu claim; sentinel
- **1:30** — Throw 6s while aiming tanyao with a 9s still held; “8s doesn’t help” with 8s set; sentinel
- **1:30:58** — Chi 5p tip may match the call UI; status still sentinel (open-hand path broken)

---

## What to do next (already chosen)

No new design needed — finish/ship the existing live-status fix:

1. Overlay: keep `my_calls` through chi/pon/kan; pass into `build_turn` / `refresh_board_features`
2. Sensei HUD: never show raw `shanten 8`
3. Drop “about” for 0 acceptances
4. Skip Why when dahai ∉ hand

Out of scope for this set: silencing `Route.heartbeat` parse spam; changing Mortal’s recommended discard beyond hand-sync correctness.
