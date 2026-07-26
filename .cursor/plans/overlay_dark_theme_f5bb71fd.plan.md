---
name: Overlay dark theme
overview: Add a dark-theme setting to the live tkinter overlay (default on), matching the review page palette. Skip waiting for a custom Majsoul-side UI — none is planned, and the desktop coach window is the active teaching surface.
todos:
  - id: setting
    content: Add dark_theme setting (default True), lan strings, settings checkbox + reload on change
    status: completed
  - id: style-helper
    content: Extend GuiStyle with dark palette, clam theme, ttk + hover colors
    status: completed
  - id: apply-windows
    content: Paint main_gui sunken panels/frames/ScrolledText; theme settings/help/widgets
    status: completed
  - id: smoke-check
    content: "Manual: dark default + toggle to light via Settings reload"
    status: completed
isProject: false
---

# Overlay dark theme

## Decision

**Add dark mode on the tkinter overlay now.** Existing plans keep the desktop coach as the focus ([compact coaching overlay](.cursor/plans/compact_coaching_overlay_0b56cbf3.plan.md) explicitly defers a browser HUD). A custom alongside-Majsoul UI is not planned; theming is small and throwaway if that changes later.

Default **dark on** so it matches [`web/review.html`](web/review.html) (`#1a1f24` / `#242b33` / `#e8eef4`). Keep a Settings checkbox to switch back to light. Work lives entirely in the sibling overlay repo [`../shanten-sensei-overlay`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay).

## Approach

Centralize colors in [`gui/utils.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/utils.py) `GuiStyle`, apply at window build / reload.

**Palette (dark, aligned with review):**
- Window/frame bg: `#1a1f24`
- Sunken panels / text areas: `#242b33`
- Text: `#e8eef4`, muted: `#9aabba`
- Borders/highlights: `#3a4550`
- Accent button: keep green (`#4CAF50`) with light-on-dark text, or soft accent `#6eb5ff` for focus — keep green for familiarity
- Hover highlight: soften from `light blue` / `lightyellow` to darker blues (`#314052` / `#2c343d`)

**Light palette:** leave widgets at system defaults (current behavior) when the setting is off.

## Changes

### 1. Setting + strings
- [`common/settings.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/settings.py): `dark_theme: bool = True` (same `_get_value` pattern as `hide_ai_options`)
- [`common/lan_str.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/lan_str.py): `DARK_THEME = "Dark theme"` (+ Chinese mirror)
- [`gui/settings_window.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/settings_window.py): checkbox near compact/auto-why; on save set `gui_need_reload` when it changes (same as `hide_ai_options`)

### 2. Style helper
- Extend `GuiStyle` in [`gui/utils.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/utils.py):
  - `theme_use("clam")` when dark (needed so ttk bg/fg stick on macOS)
  - `configure` `TLabel`, `TButton`, `TCheckbutton`, `TCombobox`, `TFrame`, `TEntry` with dark colors
  - Expose panel colors for bare `tk.Label` / `tk.Frame` / `ScrolledText` (ttk does not cover those)
  - Dark-aware hover colors in `add_hover_text`

### 3. Apply on main + child windows
- [`gui/main_gui.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/main_gui.py): after style setup, if `st.dark_theme`, set root/`grid_frame`/`aim_header`/`ai_header` bg; paint sunken labels (`text_aiming`, `text_why`, `text_ai_guide`, `text_gameinfo`, `text_status_strip`) and `reason_log_text` with panel bg + light fg; pass theme into `reload_gui` path (already rebuilds widgets)
- [`gui/settings_window.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/settings_window.py) / [`gui/help_window.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/help_window.py): call the same style apply so dialogs match
- [`gui/widgets.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/widgets.py): `ToolBar` / `StatusBar` / `ToggleSwitch` frames and labels use theme bg when dark (toolbar buttons can stay image-based)

### 4. Manual check
- Launch overlay with default settings → dark main window + Aiming/Why/reason log readable
- Toggle off in Settings → Save → light again after reload
- No Sensei-package changes; review HTML already dark

## Out of scope
- Custom Majsoul browser HUD / in-game overlay
- Per-widget polish on Help HTML content colors (acceptable if chrome is dark)
- Automated GUI screenshot tests
