# Phase 2 kickoff — live overlay

Practice / friend / vs-AI only. Not for ranked ladder assistance.

## Two-repo layout

| Repo | Role | License |
|------|------|---------|
| [shanten_sensei](../README.md) (this repo) | Explainer library: `turn_from_live` → `explain()` | Apache-2.0 |
| [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay) | Fork of [MahjongCopilot](https://github.com/latorc/MahjongCopilot): Majsoul MITM → mjai → Mortal → HUD + **Why?** | GPL-3.0 |

Do not merge the GPL overlay into this monorepo. The overlay depends on Sensei via `pip install 'shanten-sensei>=0.1.0'` (PyPI) or editable `pip install -e ../shanten_sensei` for development.

**Mac players:** [`install-mac.md`](install-mac.md) — no sibling clone required.

## Live turn contract

```python
from shanten_sensei.live import turn_from_live, candidates_from_meta_options
from shanten_sensei.explain import explain

turn = turn_from_live(
    hand=[...],                    # 13 or 14 mjai tiles
    recommended=reaction,          # mjai action dict or "dahai 9p"
    candidates=candidates_from_meta_options(reaction["meta_options"]),
    # omit player_action → pre-decision coaching (diverge=False)
)
explanation = explain(turn)        # LLM if key set, else template
```

- **Pre-decision:** `player_action == mortal_best`, contrast vs next-best Mortal candidate.
- **Post-action diverge:** pass `player_action` when it differs (same grounding as Phase 1).
- Tile / action labels match Phase 1 (`dahai 5s`, `pon W`, aka `5mr`, …).

## Overlay integration

Hook points in the fork:

- `sensei_adapter.py` — map pending Mortal reaction + hand → `explain()`
- `sensei_mode.py` — mode gate (`category` 1 friend / 2 ranked; `roomId > 0` → friend)
- GUI **Why?** button + status strip; overlay bottom-left shows banner + last explanation

## Mode policy

| Signal | Why? |
|--------|------|
| `meta.category == 1` or `roomId > 0` | Allowed |
| `meta.category == 2` (段位戦) | Disabled |
| Unknown / missing | Restricted (fail closed) |

Always show: *Practice / vs-AI / friend only — not for ranked*.

## Local setup (overlay)

Player-facing steps (install, model, How to play a game): **[`install-mac.md`](install-mac.md)** (Mac) or **[`live-setup.md`](live-setup.md)** (developers).

```bash
cd ../shanten-sensei-overlay
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install 'shanten-sensei>=0.1.0'
# Dev: pip install -e ../shanten_sensei
PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium   # optional if using Safari companion only
python main.py
```

Set `OPENAI_API_KEY` or `SENSEI_API_KEY` **and** `SENSEI_USE_LLM=1` for LLM Why? (overlay `.env`, `~/Library/Application Support/ShantenSensei/.env`, or export); otherwise template fallback. Overlay `main.py` loads these at startup.

## Non-goals (kickoff)

- Ranked / ladder assistance
- Akagi v3 / other platforms
- Shipping autoplay as a Sensei feature
- Replacing Mortal with LLM evaluation
