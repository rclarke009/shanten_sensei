---
name: Why panel height
overview: Give the Sensei explanation box a bit more vertical room in the overlay desktop UI by raising its tkinter Label line height and slightly growing the window so the rest of the layout does not feel cramped.
todos: []
isProject: false
---

# More space for Why? answer

## Where it lives

The clipped “Sensei explanation” box is **not** in this repo. It is in the sibling overlay:

[`../shanten-sensei-overlay/gui/main_gui.py`](../shanten-sensei-overlay/gui/main_gui.py)

```171:177:../shanten-sensei-overlay/gui/main_gui.py
        self.text_why = tk.Label(
            self.grid_frame,
            textvariable=self.why_var,
            font=GUI_STYLE.font_normal("Segoe UI", 14),
            height=3, anchor=tk.NW, justify=tk.LEFT, wraplength=580,
            relief=tk.SUNKEN, padx=5, pady=5,
        )
```

`height=3` is a hard line-count cap on the `Label`, so wrapped LLM text gets cut off mid-line (as in your screenshot). Row `weight=1` does not help because grid sticky is `EW` only.

## Change

In [`gui/main_gui.py`](../shanten-sensei-overlay/gui/main_gui.py):

1. Bump `self.text_why` from `height=3` → `height=5` (same as AI Guidance above it — enough for a typical 1–2 sentence Why? with wrap).
2. Bump default/min window size from `(620, 540)` → `(620, 580)` so the extra two lines do not squeeze Game Info / status.

No scrollable `Text` widget, sticky/`NSEW` rewrite, or prompt changes — just a small layout tweak for the clipping you showed.

## Verify

Relaunch the overlay, click **Why?** on a turn with a multi-line explanation, and confirm the box shows ~5 lines without clipping the last line of a typical answer.