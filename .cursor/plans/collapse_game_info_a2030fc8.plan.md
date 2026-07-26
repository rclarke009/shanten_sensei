---
name: Collapse game info
overview: Make the overlay's Game Info hand strip collapsible via a clickable header (same UX as Reason log), starting collapsed so coaching panels get more vertical space by default.
todos:
  - id: gameinfo-header
    content: Replace Game Info label with clickable ▸/▾ header; default body hidden
    status: completed
  - id: layout-stage
    content: Wire _apply_layout_stage + reload_gui to respect _gameinfo_expanded
    status: completed
  - id: manual-verify
    content: Smoke-check collapse/expand and short-window sacrifice
    status: completed
isProject: false
---

# Collapsible Game Info (default collapsed)

Work lives in the sibling overlay repo [`../shanten-sensei-overlay`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay), not in the Sensei package.

## Approach

Mirror the existing **Reason log** pattern in [`gui/main_gui.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/main_gui.py): clickable header with `▸` / `▾`, body shown only when expanded. **Default collapsed** on launch and on `reload_gui`. No settings persistence (same as reason log).

```mermaid
flowchart TD
  header["Game Info header always visible when layout allows"]
  click["Click header"]
  body["text_gameinfo tile strip"]
  header --> click
  click -->|"expanded"| body
  click -->|"collapsed default"| hidden["body grid_remove"]
```

## Implementation

### 1. Clickable header + expand state

In `_create_widgets` (Game Info block ~lines 303–321):

- Replace the static `ttk.Label` header with a `tk.Frame` + clickable `ttk.Label` (copy the reason-log header wiring: `cursor="hand2"`, bind `<Button-1>`).
- Add `self._gameinfo_expanded = False` (init + after widget build).
- Build `text_gameinfo` but **do not** `grid` it initially (or `grid_remove` immediately).
- Call `_update_gameinfo_header()` so the label reads `▸ Game Info` / `▾ Game Info`.

Helpers (next to reason-log helpers ~505–528):

- `_update_gameinfo_header()` — chevron + `self.st.lan().GAME_INFO`
- `_toggle_gameinfo(_event=None)`
- `_set_gameinfo_expanded(expanded: bool)` — `grid` / `grid_remove` on `text_gameinfo`, reset `_layout_stage = -1`, `after_idle(self._adapt_layout_height)`

In `reload_gui`: reset `_gameinfo_expanded = False` alongside `_reason_log_expanded`.

### 2. Respect expand state in height-adaptive layout

`_apply_layout_stage` currently shows/hides Game Info purely by stage. Change so:

- **stage &lt; 2**: show header; show `text_gameinfo` **only if** `_gameinfo_expanded`
- **stage ≥ 2**: hide header and body (keep current “window too short” sacrifice)

That way auto-layout never forces the tile strip open when the user left it collapsed, and expanding still works when there is room.

### 3. Strings

Reuse existing [`GAME_INFO`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/lan_str.py) (`'Game Info'` / `'游戏信息'`). No new lan strings.

### 4. Manual check

- Fresh open: header shows `▸ Game Info`, no emoji hand strip
- Click: strip appears; click again: collapses
- Shorten window heavily: Game Info still sacrificed at stage 2; expand after resizing back works
- `reload_gui` / settings save that rebuilds UI: starts collapsed again
- Reason log / Controls collapse behavior unchanged
