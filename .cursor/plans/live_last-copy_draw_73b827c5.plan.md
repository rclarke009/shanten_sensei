---
name: Live last-copy draw
overview: Yes — when one copy remains, the tip should say that tile can still be drawn, not only that it is scarce. Keep “already out” for zero copies, and do not claim the last copy is in the wall.
todos:
  - id: phrase-n1
    content: Append — you can still draw it to copies==1 in _unseen_copy_phrase + SYSTEM_PROMPT examples
    status: completed
  - id: tests-n1
    content: Assert draw clause on 1-copy wall_note / substance / call-skip goldens
    status: completed
isProject: false
---

# Say the last 9-pin can still be drawn

Tonight’s line is factually right and pedagogically half-wrong.

Three 9-pins are in the river, so [`_unseen_copy_phrase`](src/shanten_sensei/explain.py) correctly emits `only 1 copy of 9-pin is still unseen` (`remaining_by_tile == 1` and 9-pin is in ukeire after throwing 2-sou). That sentence was locked as a **scarcity** warning in [wall phrasing clarity](.cursor/plans/wall_phrasing_clarity_85ace442.plan.md). Sitting on `Throw 2-sou, not 5-pin`, it reads like “don’t bother with 9-pin.” For a beginner staring at three discarded 9-pins, the useful distinction is vs **zero**:

- **0 copies:** `{tile} is already out` — you cannot draw it
- **1 copy:** still live ukeire (it is in the 21) — you can still draw it, or it may be in someone’s hand

Do **not** say “left in the wall.” Unseen includes the draw pile **and** opponents’ hands; that jargon is already rejected in grounding.

## Target copy

Change only the `copies == 1` branch of `_unseen_copy_phrase` (shared by `wall_note` and `_thin_wall_sentence`):

```
only 1 copy of {tile} is still unseen — you can still draw it
```

Leave `only N× {tile} still unseen` and `{tile} is already out` as they are.

Screenshot would become:

> Throw 2-sou, not 5-pin. Only 1 copy of 9-pin is still unseen — you can still draw it. Throwing 2-sou keeps draws like …

## Code

[`src/shanten_sensei/explain.py`](src/shanten_sensei/explain.py)

- `_unseen_copy_phrase`: append ` — you can still draw it` when `copies == 1`
- `SYSTEM_PROMPT`: update the two locked examples (`only 1 copy of red 5-pin is still unseen`) to the new clause

No grounding rule change. Existing anchors already match `still unseen`. Do not add `left in the wall`.

## Tests

- [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py): `test_wall_note_thin_remaining` / depletion summary assert the draw clause
- Goldens / call-skip tests that already look for `still unseen` keep passing; add `you can still draw it` where the fixture is exactly 1 copy
- No new screenshot fixture required unless we want one later

Out of scope: moving the thin-copy sentence later in the throw paragraph; promising the tile is in the wall.