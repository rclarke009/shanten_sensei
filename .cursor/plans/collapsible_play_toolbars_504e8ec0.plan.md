---
name: Collapsible play toolbars
overview: Add a collapsible controls strip to the desktop overlay so the two toolbar rows (actions + Overlay/Autoplay/Auto Join/mode/timer) can hide during play while Aiming/Why coaching stays visible. Default to manual toggle via a thin header bar; optionally auto-collapse when a game is in progress.
todos: []
isProject: false
---

# Collapsible play toolbars

## Opinion (locked in)

Hide the **setup toolbars**, not the coaching surface. Those rows are lobby/setup chrome; Aiming / Why / reason log are what you want mid-hand. Work lives in the sibling overlay repo [`../shanten-sensei-overlay`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay), not in Sensei package code.

## UX choice

**Manual collapse via a thin header bar** at the top of the window:

- Label like `Controls ▾` / `Controls ▴` (or a chevron-only strip)
- Click toggles visibility of both [`self.toolbar`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/main_gui.py) and [`self.tb2`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/main_gui.py)
- Aiming, Why?, status, reason log stay packed/gridded as today
- Persist preference as `hide_toolbars: bool = False` in [`common/settings.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/settings.py) so it survives reload
- Shrink window height when collapsed (same spirit as compact `480×480` geometry in `_create_widgets` / `reload_gui`)

**Auto-collapse when in-game** (follow-up in same change if state is already easy to read): when bot reports an active kyoku / not-in-lobby, collapse; when back in lobby, expand — but only if the user has not manually forced the opposite this session. If game-state hooks are awkward, ship manual-only first and wire auto in a second pass.

## Implementation

### 1. Collapse chrome in main GUI
In [`gui/main_gui.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/main_gui.py) `_create_widgets`:

- Insert a small header row above the two toolbars (button or clickable label)
- Factor toolbar show/hide into `_set_toolbars_visible(visible: bool)` using `grid()` / `grid_remove()` on `toolbar` and `tb2`
- On toggle: flip setting, update chevron label, adjust `geometry` height (~toolbar row heights removed)
- Honor saved `hide_toolbars` on build and on `reload_gui`

### 2. Setting + strings
- [`common/settings.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/settings.py): `hide_toolbars: bool = False`
- [`common/lan_str.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/lan_str.py): short strings for the header (`CONTROLS_SHOW` / `CONTROLS_HIDE` or one `CONTROLS` + chevron in code)
- No Settings checkbox required if the header toggle is always visible; optional checkbox only if you want Settings parity with compact/dark

### 3. Optional auto-collapse
If `BotManager` / gameinfo already exposes “in game vs lobby” to the GUI update loop (same path that refreshes Aiming/Why):

- When entering gameplay → `_set_toolbars_visible(False)` unless user expanded manually this session
- When returning to lobby → restore visible unless user collapsed manually

Track a small `_toolbar_user_override: bool | None` on `MainGUI` so auto does not fight the user.

### 4. Manual check
- Collapse → toolbars gone, coaching panels remain, window shorter
- Expand → toolbars back, toggles still work
- Reload / settings save → collapse state preserved
- Overlay / Autoplay state unchanged while toolbars are hidden (only UI chrome hides)

## Out of scope
- Hiding the in-browser Majsoul HUD (already the Overlay toggle)
- Minimize-to-tray / global hotkey
- Sensei package / review HTML changes
