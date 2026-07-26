---
name: Settings window size
overview: Fix the Settings dialog so it always opens at its intended 700×710 size (with Save/Cancel visible), instead of collapsing to a tiny window when the parent coaching window is shrunk.
todos:
  - id: fix-geometry
    content: Combine size+position geometry in settings_window.py so 700x710 is not dropped
    status: completed
isProject: false
---

# Fix Settings window opening too small

## Cause

In [`shanten-sensei-overlay/gui/settings_window.py`](/Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/settings_window.py), size and position are applied in two separate `geometry()` calls, with **position last**:

```19:25:/Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/settings_window.py
        self.geometry('700x710')
        self.minsize(700, 710)        
        # set position: within main window
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        self.geometry(f'+{parent_x+10}+{parent_y+10}')
```

On macOS Tk, a position-only `geometry('+x+y')` can discard the earlier size, so the dialog falls back to a small default — especially noticeable when the parent coaching window is shrunk.

The Help dialog already avoids this by setting **size after** position in [`help_window.py`](/Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/gui/help_window.py).

## Fix

In `SettingsWindow.__init__`, set size and position in one call (and keep minsize):

```python
parent_x = parent.winfo_x()
parent_y = parent.winfo_y()
self.geometry(f'700x710+{parent_x + 10}+{parent_y + 10}')
self.minsize(700, 710)
```

No change to Save/Cancel layout, content packing, or parent `main_gui.py` open/modal flow — those already pack buttons at the bottom; they just need the window tall enough to show them.

## Verify

1. Shrink the main coaching window.
2. Click Settings.
3. Dialog should open at ~700×710 with Save and Cancel visible at the bottom.