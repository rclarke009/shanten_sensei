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
| Scoped Safari proxy | Safari mode writes a PAC that proxies **Majsoul-related hosts only** (`sensei-majsoul.pac`), not all HTTPS. |
| Off when done | Overlay disables/restores auto-proxy on quit (`atexit` best-effort). Document manual disable if the app crashes. Never leave Auto Proxy on after coaching. |
| Companion for Safari | Coach UI stays in the tkinter companion window. No in-page Safari HUD / content script in v1 (limits page-world privilege). |
| Practice-only gate | Keep ranked Why? disabled (`sensei_mode`); do not market ladder assistance. |
| Known install source | Users should install only from the official overlay / Sensei repos or known releases. A fake “Sensei” that installs a CA is the realistic spyware vector. |

Code-signing / notarization may come in a later packaging pass; until then, prefer running from source you can inspect.

---

## Chromium vs Safari — risk comparison

| | Chromium path | Safari path (macOS) |
|--|---------------|---------------------|
| How traffic is proxied | Playwright sets a **browser-only** proxy on the app Chromium | macOS **Auto Proxy PAC** (Majsoul hosts → local mitm) |
| Typical blast radius | Mostly the app-owned browser session | Only Majsoul hosts matched by the PAC |
| In-page HUD | Optional Playwright canvas inject | **Not used** — companion window only |
| Cert trust | Still needed for MITM TLS | Same; prefers login keychain, System+sudo fallback |
| Leave-on risk | Lower (closing app browser ends that proxy use) | Cleared on quit; if crash, turn Auto Proxy off manually (below) |

Chromium stays the smaller everyday footprint. Safari is supported when you use the built-in companion mode (PAC + quit cleanup).

---

## User checklist

### Before / first run

1. Install overlay + Sensei from the **official** sibling repos (see [`live-setup.md`](live-setup.md)).
2. Start the overlay once so `mitm_config/` can create the local CA.
3. Install/trust the MITM cert when prompted (or follow overlay logs). On macOS you may get a Keychain prompt (login keychain) or an admin/`sudo` prompt for the System keychain.
4. Prefer understanding: the cert is for **local** coaching, not a random website.

### Each coaching session

1. Start the overlay helper.
2. **Chromium:** use **Start Browser** and play only in that window.  
   **Safari (macOS):** Settings → Safari companion mode → restart → open Majsoul in Safari (do not use Start Web Client).
3. Join **friend / practice / vs-AI** only.
4. Keep the companion window visible beside the game for status / Why?.
5. When finished: **quit the overlay** (Safari PAC is turned off / restored automatically).

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

Overlay prefers installing into the **login** keychain first:

```bash
security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain-db /path/to/mitmproxy-ca-cert.cer
```

If that fails, it falls back to System keychain (may prompt for admin):

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /path/to/mitmproxy-ca-cert.cer
```

To remove manually:

1. Open **Keychain Access**.
2. Check **login** and **System**.
3. Search for `mitmproxy` / the CA common name from your `mitm_config` cert.
4. Delete the certificate.

Also delete the overlay’s local `mitm_config/` directory if you no longer need it (contains private key material for that install).

### Safari Auto Proxy stuck after a crash

```bash
networksetup -listallnetworkservices
networksetup -setautoproxystate "Wi-Fi" off
# or Ethernet / your real service name
```

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
