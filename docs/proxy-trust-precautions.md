# Proxy and certificate trust — precautions

Plain-language rules for anyone who runs live Sensei coaching. Live capture uses a **local** MITM proxy (mitmproxy) so the overlay can read Majsoul WebSocket traffic. That requires trusting a certificate generated on your machine.

Architecture context: [`dual-client-architecture.md`](dual-client-architecture.md).

**Practice / friend / vs-AI only — not for ranked.**

---

## What trusting the MITM cert means

The overlay’s mitm CA (under the overlay’s `mitm_config/` folder, typically `mitmproxy-ca-cert.cer`) is a small “ID office” your OS or browser trusts. While traffic is sent through the local proxy, that proxy can decrypt HTTPS/WSS for sites it intercepts — including Majsoul login and game sessions that go through it.

**It does not mean** random people on the internet can suddenly read your browsing. A remote attacker still needs both:

1. Your traffic going through a proxy they control, and  
2. The private key for a CA you trust.

**The main trust decision** is: you trust **this overlay app** (and whoever built the binary you installed), not the open internet.

---

## Musts for Sensei (product / maintainer rules)

| Rule | Detail |
|------|--------|
| Per-machine cert | Let mitmproxy generate CA material in each install’s `mitm_config/`. **Never** ship one shared CA private key to all users. |
| Loopback only | mitm listens on `127.0.0.1` (or equivalent local-only bind). Do not expose the intercept on the LAN. |
| Scoped Safari proxy | When Safari path ships: proxy **Majsoul-related hosts only**, not “all HTTPS forever.” |
| Off when done | Tie proxy ON/OFF to overlay start/stop. Document manual disable if automation fails. Never tell users to leave a system-wide proxy on after coaching. |
| Companion for Safari | Coach UI stays in the tkinter companion window. No in-page Safari HUD / content script in v1 (limits page-world privilege). |
| Practice-only gate | Keep ranked Why? disabled (`sensei_mode`); do not market ladder assistance. |
| Known install source | Users should install only from the official overlay / Sensei repos or known releases. A fake “Sensei” that installs a CA is the realistic spyware vector. |

Code-signing / notarization may come in a later packaging pass; until then, prefer running from source you can inspect.

---

## Chromium vs Safari — risk comparison

| | Chromium path (today) | Safari path (designed) |
|--|------------------------|-------------------------|
| How traffic is proxied | Playwright sets a **browser-only** proxy on the app Chromium | OS/Safari **scoped** proxy to local mitm |
| Typical blast radius | Mostly the app-owned browser session | Only Majsoul hosts **if** scope is correct; wider if someone enables system-wide proxy |
| In-page HUD | Optional Playwright canvas inject | **Not used** — companion window only |
| Cert trust | Still needed for MITM TLS | Same class of trust; often System keychain on macOS |
| Leave-on risk | Lower (closing app browser ends that proxy use) | Higher if scoped/system proxy is left enabled after quit |

Chromium today is the smaller everyday footprint. Safari is fine if scope and OFF behavior are solid — that is a hard requirement before calling Safari “supported.”

---

## User checklist

### Before / first run

1. Install overlay + Sensei from the **official** sibling repos (see [`live-setup.md`](live-setup.md)).
2. Start the overlay once so `mitm_config/` can create the local CA.
3. Install/trust the MITM cert when prompted (or follow overlay logs). On macOS this may ask for admin via `security add-trusted-cert` — **verify on your machine**; Darwin helpers in the overlay are marked needs testing.
4. Prefer understanding: the cert is for **local** coaching, not a random website.

### Each coaching session

1. Start the overlay helper.
2. **Chromium (supported):** use **Start Browser** and play only in that window.  
   **Safari (when shipped):** enable the helper’s scoped proxy, then open Majsoul in Safari — do not use an unproxied window and expect tips.
3. Join **friend / practice / vs-AI** only.
4. Keep the companion window visible beside the game for status / Why?.
5. When finished: **quit the overlay**. Confirm proxy is off (especially after any Safari/system proxy session).

### After

- If anything looks wrong with HTTPS sites system-wide, check proxy settings first, then cert trust (below).
- Do not export or share files from `mitm_config/` that include private keys.

---

## Uninstall / remove trust

If you stop using live coaching, remove the trusted mitm CA so it cannot be reused by malware that later finds the key files.

### Windows

Overlay install path uses `certutil` against the **Root** store (`common/utils.py` in the overlay: `certutil -addstore Root …` / check via `certutil -store Root`).

To remove: open **Manage computer certificates** (or `certmgr.msc`) → **Trusted Root Certification Authorities** → find the mitmproxy / Sensei-related CA → Delete. Or use `certutil -delstore Root <serial>` with the serial from the `.cer` file.

### macOS

Overlay attempts install with:

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /path/to/mitmproxy-ca-cert.cer
```

**(Needs verification on real Macs** — marked TODO in overlay `common/utils.py`.)

To remove manually:

1. Open **Keychain Access**.
2. Check **System** (and **login** if you installed there instead).
3. Search for `mitmproxy` / the CA common name from your `mitm_config` cert.
4. Delete the certificate and set trust to absent, or use `security remove-trusted-cert` / delete from the keychain with admin rights.

Also delete the overlay’s local `mitm_config/` directory if you no longer need it (contains private key material for that install).

### Always

- Turn off any custom HTTP/HTTPS/SOCKS proxy or PAC that pointed at `127.0.0.1` mitm ports.
- Restart Safari/browser after proxy changes if settings seem sticky.

---

## If something feels wrong

| Symptom | First check |
|---------|-------------|
| Unrelated sites break or show cert warnings | Proxy still on? Wrong PAC? Remove proxy, then retest |
| No tips in companion window | Playing outside the proxied client; mitm/cert not trusted; not in a game lobby |
| Why? disabled | Ranked or unknown mode — switch to friend/practice |
| You did not install Sensei but a cert appeared | Treat as compromise; remove unknown roots; reinstall OS advice as needed |

---

## Related

- [`dual-client-architecture.md`](dual-client-architecture.md) — Chromium vs Safari design  
- [`live-setup.md`](live-setup.md) — supported Chromium play steps  
- Overlay: `mitm.py` (`install_mitm_cert`), `common/utils.py` (`install_root_cert`, `is_certificate_installed`)
