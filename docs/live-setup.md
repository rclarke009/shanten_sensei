# How to play live with Shanten Sensei

> **Mac players (no Terminal):** use **[`install-mac.md`](install-mac.md)** or the [overlay INSTALL.md](https://github.com/rclarke009/shanten-sensei-overlay/blob/main/INSTALL.md).  
> **This page** is the developer / from-source guide (clone repos, `pip`, Chromium, tests).

Live coaching uses the [overlay fork](https://github.com/rclarke009/shanten-sensei-overlay) (Mahjong Copilot + **Why?**) plus the `shanten-sensei` package (PyPI or sibling clone).

**Practice / friend / vs-AI only — not for ranked.** Why? is disabled when ranked (段位戦) is detected.

### Two client paths

| Path | Status |
|------|--------|
| **Chromium** — **Start Browser** in the overlay | Supported (steps below) |
| **Safari** — Majsoul in Safari + companion coach window | Supported on **macOS** (see [Safari companion](#safari-companion-macos)) |

Dual-window layout (game beside the Sensei companion UI) is the intended UX for both. Architecture: [`dual-client-architecture.md`](dual-client-architecture.md). Certificate / proxy trust: [`proxy-trust-precautions.md`](proxy-trust-precautions.md).

---

## What you get in-game

1. Mortal’s recommended action on the overlay (as with Copilot).
2. A status strip (shanten, ukeire, menzen/tenpai, etc.).
3. A **Why?** button — on demand — that asks Sensei to explain Mortal’s pick in 1–2 sentences.

The LLM never invents a better discard; it only verbalizes Mortal + derived features.

---

## One-time setup

Clone both repos as siblings (same parent folder):

```text
a_new_projects_folder/
  shanten_sensei/              ← this repo
  shanten-sensei-overlay/      ← Copilot fork with Why?
```

### 1. Install Sensei (this repo)

**Overlay users:** `pip install shanten-sensei` inside the overlay venv (see overlay `requirements.txt`) — no sibling clone required.

**Contributors** (editable install):

```bash
cd shanten_sensei
uv venv .venv
uv pip install -e ".[dev]" --python .venv/bin/python
```

Optional — for LLM explanations instead of the offline template:

```bash
# repo-root .env
OPENAI_API_KEY=sk-...
SENSEI_USE_LLM=1
# or
SENSEI_API_KEY=...
SENSEI_USE_LLM=1
```

An API key alone does **not** enable the LLM; you must set `SENSEI_USE_LLM=1` (or pass `--llm` / `?mode=llm` on supported surfaces).

### 2. Install the overlay

Python **3.11** recommended. On macOS use `python3.11` (there is often no bare `python`).

**macOS shortcut:** after cloning the overlay repo, double-click `scripts/install-macos.command` to create a venv, install packages, and add a launcher in `~/Applications/`. Skips Chromium by default (Safari path). For Playwright Chromium too: `INSTALL_CHROMIUM=1 ./scripts/install-macos.command`.

**Manual install:**

```bash
cd ../shanten-sensei-overlay
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
pip install 'shanten-sensei>=0.1.0'
# Or editable sibling for development: pip install -e ../shanten_sensei
# Compat pins (torch 2.2 + mitmproxy 10.2):
pip install 'numpy<2' 'httpx>=0.27,<0.28' 'httpcore>=1.0,<1.0.9' 'h11>=0.11,<0.15'
PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium
```

### 3. Place a Mortal model

The overlay’s **Local** model type expects an Akagi-compatible Mortal `.pth`.

- Put the file under `shanten-sensei-overlay/models/` (e.g. `mortal.pth`), **or**
- Symlink it, e.g. if you already have weights under Sensei’s `game_logs/mortal_model/`:

```bash
cd shanten-sensei-overlay/models
ln -sf ../../shanten_sensei/game_logs/mortal_model/mortal_298k.pth mortal.pth
```

Confirm **Settings → Model** is `Local` and points at that file. How to obtain models: [Akagi](https://github.com/shinkuan/Akagi).

---

## Play a live practice game

1. **Start the overlay**

   ```bash
   cd shanten-sensei-overlay
   source venv/bin/activate
   # Why? LLM: overlay loads .env from its cwd, or sibling ../shanten_sensei/.env
   # (or export OPENAI_API_KEY / SENSEI_API_KEY before launch)
   python main.py
   ```

2. **Open Majsoul through the app**  
   Click **Start Browser** in the toolbar. Use the Chromium window Copilot launches (MITM must see the game traffic). Do not play in a separate browser outside the proxy.

   Default URL is the English client: `https://mahjongsoul.game.yo-star.com/`.  
   If Chromium opens Chinese Majsoul (`game.maj-soul.com`), change **Settings → Majsoul URL** to the YoStar link above, save, then Start Browser again. (Browser auto-translate cannot fix Majsoul — the UI is canvas-drawn.)

3. **Turn on Overlay; leave Autoplay off**  
   Overlay = on so recommendations / status show in-game. Autoplay stays off — Sensei is a coach, not a bot.

4. **Join a safe mode**
   - Friend room, or
   - Practice / vs-AI  
   Avoid ranked ladder. The UI shows a practice-only banner; **Why?** is disabled on ranked / unknown mode.

5. **Play your turn**  
   When it’s your discard (or call decision), Mortal’s recommendation appears on the HUD.

6. **Press Why?**  
   In the desktop GUI (and reflected on the overlay strip), press **Why?**. Sensei returns a short explanation pinned to Mortal’s action.  
   - With an API key → LLM wording.  
   - Without → offline template text (still grounded in Mortal + features).

7. **When the tip changes**  
   Stale Why? text clears as soon as Mortal’s recommendation changes (or clears). Press **Why?** again for the new tip.  
   Optional: Settings → **Auto Why?** regenerates automatically on each new tip (uses the API when a key is set — cost per tip). Same tip is still cached if nothing changed.

---

## Safari companion (macOS)

Use this if you want Majsoul in **Safari** and the coach in the Sensei window beside it (no Chromium).

1. **Settings → enable “Safari companion mode (macOS; no Chromium)”** → Save. Restart the overlay when prompted (MITM / proxy settings need a restart).
2. **Start the overlay** (`python main.py`). It starts mitm, trusts/installs the local MITM cert if needed, serves a Majsoul-only PAC at `http://127.0.0.1:{mitm_port+1}/…`, and turns on Auto Proxy via `networksetup`. You may see a Keychain or admin prompt for the cert.
3. **Do not** click **Start Web Client**. Tips appear in the Sensei window, not inside Safari.
4. **Fully quit Safari** (`Cmd+Q`), then reopen → `https://mahjongsoul.game.yo-star.com/`.  
   If you opened Majsoul before starting the overlay, click **Quit Safari & reopen Majsoul** in the coach window instead (this closes all Safari tabs).
5. When the status shows **Proxy Client** (not “Safari — open Majsoul”), join friend / practice / vs-AI and use **Why?** in the companion window.
6. **Quit the overlay** when done — it turns Auto Proxy off. If browsing breaks after a crash, see [`proxy-trust-precautions.md`](proxy-trust-precautions.md).

**If status never becomes Proxy Client:** turn off **iCloud Private Relay** (System Settings → Apple ID → iCloud → Private Relay) and any VPN — they can bypass the PAC. Confirm System Settings → Network → Wi-Fi → Details → Proxies shows Automatic Proxy Configuration pointing at `http://127.0.0.1:…/sensei-majsoul.pac`.

Safari mode is **macOS only**. On other OSes, leave the setting off and use Chromium.

---

## Quick troubleshooting

| Symptom | Likely fix |
|---------|------------|
| No recommendations | Model not loaded — check Settings → Local `.pth`, restart after MITM/model changes |
| Overlay blank | Overlay toggle on; play inside the app’s browser (Chromium path) |
| Safari: no Proxy Client / no tips | Safari companion mode on + restart; cert trusted; Majsoul opened in Safari after overlay start; use **Quit Safari & reopen Majsoul** if you opened the game first (closes all Safari tabs); quit/restart if PAC failed |
| Browsing broken after Safari crash | `networksetup -setautoproxystate "Wi-Fi" off` (see precautions doc) |
| Why? greyed / “disabled” | You’re in ranked or mode is unknown — use friend / practice |
| `shanten_sensei` import errors | `pip install 'shanten-sensei>=0.1.0'` inside the overlay venv |
| Generic / template Why? text | Put `OPENAI_API_KEY` or `SENSEI_API_KEY` in overlay `.env`, sibling `../shanten_sensei/.env`, or export before `python main.py`. Restart the overlay after changing keys. |

---

## After the game (optional)

You can still use Phase 1 post-game review on a log:

```bash
cd shanten_sensei
uv run --python .venv/bin/python sensei serve path/to/review.json
```

See [`phase1-contract.md`](phase1-contract.md) for mjai-reviewer → report JSON.

---

## More detail

| Doc | Audience |
|-----|----------|
| This file | Playing live |
| [`phase2-kickoff.md`](phase2-kickoff.md) | Adapter contract, mode gate, two-repo layout |
| [Overlay readme](https://github.com/rclarke009/shanten-sensei-overlay) | Upstream Copilot install notes + screenshots |
