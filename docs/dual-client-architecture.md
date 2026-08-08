# Dual-client local install — architecture

One local Sensei + overlay install; two ways to play Majsoul next to the coach. This doc is the contract for maintainers and future implementers.

**Status today**

| Path | Status |
|------|--------|
| Chromium (Playwright) | Supported — see [`live-setup.md`](live-setup.md) |
| Safari + companion window | **Supported on macOS** — Settings → Safari companion mode |
| Mac Majsoul native app | **Out of scope** |
| Hosted live / zero-install proxy | **Out of scope** |

Security and trust rules: [`proxy-trust-precautions.md`](proxy-trust-precautions.md).

---

## Product model

Users install the overlay fork locally (sibling of this repo). They arrange **two windows side by side**:

- **Game** — Majsoul in Chromium (today) or Safari (future)
- **Coach** — the overlay’s tkinter companion window (`gui/main_gui.py`): status, Mortal tip, **Why?**, practice banner

Safari path does **not** inject an in-page HUD into Safari. Chromium may still use the optional Playwright canvas overlay; coaching truth lives in the companion window either way.

Practice / friend / vs-AI only. Ranked assistance is not a product goal; Why? stays gated when ranked is detected (`sensei_mode.py` in the overlay).

---

## Shared core (unchanged across clients)

Both paths feed the same pipeline. Only **how traffic reaches mitmproxy** differs.

```text
Majsoul WebSocket
      │
      ▼
mitmproxy (loopback)  →  liqi protobuf decode  →  mjai events
      │
      ▼
Mortal (local .pth)  →  recommended action + values
      │
      ▼
Sensei (this repo): live features + explain() / Why?
      │
      ▼
Companion window (and optional Chromium in-page HUD)
```

| Stage | Overlay / Sensei location |
|-------|---------------------------|
| MITM + WS queue | `shanten-sensei-overlay/mitm.py` |
| Protocol decode | `liqi.py` + proto assets |
| Game state / bot loop | `bot_manager.py`, `game/game_state.py` |
| Client kind | `GameClientType.PLAYWRIGHT` vs `PROXY` in `common/utils.py` |
| Mode gate | `sensei_mode.py` |
| Why? adapter | `sensei_adapter.py` → Sensei `live` / `explain` |
| Companion UI | `gui/main_gui.py` |

---

## Path A — Chromium (supported today)

1. Overlay starts mitmproxy on `127.0.0.1:{mitm_port}` (HTTP mode; config under `mitm_config/`).
2. User clicks **Start Browser** (or enables auto-launch). Playwright launches **Chromium** with a **browser-only** proxy pointing at that mitm URL (`game/browser.py`).
3. Traffic never needs OS-wide proxy settings; only the app-owned Chromium goes through MITM.
4. Optional in-page HUD: canvas injected via Playwright `page.evaluate` when Overlay is toggled on.
5. Companion GUI runs regardless; Why? and status are available there.

Docs for players: [`live-setup.md`](live-setup.md).

---

## Path B — Safari (macOS, shipped)

Goal: users who will not use Chromium play Majsoul in **Safari**, with the same companion coach beside it.

### UX (implemented)

1. Settings → **`safari_mode`** → restart overlay.
2. Overlay starts mitm; **does not** start Playwright Chromium.
3. [`common/macos_proxy.py`](file:///Users/rebeccaclarke/a_new_projects_folder/shanten-sensei-overlay/common/macos_proxy.py) writes `mitm_config/sensei-majsoul.pac` and enables auto-proxy via `networksetup` for Wi-Fi/Ethernet-like services (Majsoul hosts → `127.0.0.1:{mitm_port}`, else `DIRECT`).
4. Trust the local mitm CA (login keychain preferred; System + sudo fallback).
5. Open Majsoul in Safari; when lobby/game WS hits mitm, client type is `GameClientType.PROXY`.
6. Coach UI is **companion window only** — Start Browser / in-page Overlay disabled.
7. On quit (and `atexit`): restore previous auto-proxy / turn PAC off.

Player steps: [`live-setup.md`](live-setup.md#safari-companion-macos).

### Implementation map

| Piece | Location |
|-------|----------|
| PAC + networksetup | `shanten-sensei-overlay/common/macos_proxy.py` |
| Setting | `safari_mode` in `common/settings.py` |
| Lifecycle | `bot_manager.py` (`_enable_safari_proxy` / `_disable_safari_proxy`) |
| WS allowlist in Safari mode | `MitmController(allowed_domains=MAJSOUL_DOMAINS)` |
| Companion UI | `gui/main_gui.py`, `gui/settings_window.py`, `common/lan_str.py` |

---

## Window layout

Intended arrangement (user-managed; no forced tiling in v1):

```text
┌─────────────────────────────┐  ┌──────────────────────┐
│  Majsoul (Chromium or Safari)│  │  Sensei companion    │
│                             │  │  status / tip / Why? │
└─────────────────────────────┘  └──────────────────────┘
```

---

## Non-goals

- Mac Majsoul **native app** capture (no macOS proxinject; Windows inject stays Windows-only)
- Zero-install **hosted live** website that proxies Majsoul through our servers
- Safari **in-page** HUD / Web Extension coach in v1
- Ranked / ladder assistance
- Merging the GPL overlay into this repo

---

## Flow diagram

```mermaid
flowchart LR
  subgraph chromiumPath [ChromiumPath]
    OverlayA[OverlayApp] --> MitmA[mitmproxy]
    OverlayA --> Chromium[PlaywrightChromium]
    Chromium -->|browser proxy| MitmA
  end
  subgraph safariPath [SafariPath]
    OverlayB[OverlayApp] --> MitmB[mitmproxy]
    Safari[SafariMajsoul] -->|scoped proxy| MitmB
  end
  MitmA --> Core[liqi_mjai_Mortal_Sensei]
  MitmB --> Core
  Core --> Companion[CompanionWindow]
```

---

## Related docs

| Doc | Role |
|-----|------|
| [`live-setup.md`](live-setup.md) | How to play live today (Chromium) |
| [`proxy-trust-precautions.md`](proxy-trust-precautions.md) | Cert / proxy trust rules |
| [`phase2-kickoff.md`](phase2-kickoff.md) | Adapter + mode-gate kickoff |
| Overlay repo | Capture UI, mitm, Playwright |
