# Install Shanten Sensei on Mac

**Audience:** players who want live coaching — not developers.

Practice / friend / vs-AI only — **not for ranked**.

## Quick start

| Method | When to use |
|--------|-------------|
| **[Download .dmg](https://github.com/rclarke009/shanten-sensei-overlay/releases)** | Easiest — no Terminal |
| **[One-click installer](https://github.com/rclarke009/shanten-sensei-overlay/blob/main/scripts/install-macos.command)** | From a cloned overlay repo before a Release exists |
| **[Developer setup](live-setup.md)** | Contributing or Chromium / from-source |

### Download path (recommended)

1. Get **ShantenSensei-macOS.dmg** from [overlay Releases](https://github.com/rclarke009/shanten-sensei-overlay/releases).
2. Drag **Shanten Sensei** to Applications and open it (right-click → **Open** if macOS warns about an unsigned build).
3. Complete the **first-run wizard**: practice acknowledgment, Mortal model file, Safari companion, optional API key.
4. Play Majsoul in **Safari**, join friend / practice / vs-AI, press **Why?** in the coach window.

Full troubleshooting and proxy/cert notes: [overlay INSTALL.md](https://github.com/rclarke009/shanten-sensei-overlay/blob/main/INSTALL.md) and [proxy-trust-precautions.md](proxy-trust-precautions.md).

### One-click installer path

1. Install [Python 3.11](https://www.python.org/downloads/).
2. Clone [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay).
3. Double-click `scripts/install-macos.command`.
4. Open **Shanten Sensei** from `~/Applications/`.

The installer installs `shanten-sensei` from PyPI (or git) — you do **not** need a sibling `shanten_sensei` clone.

## Mortal model

Download an [Akagi](https://github.com/shinkuan/Akagi)-compatible Mortal `.pth`. The app does not redistribute weights.

## Optional LLM Why?

Works offline with template text. For LLM wording, set an API key in the first-run wizard or in:

`~/Library/Application Support/ShantenSensei/.env`

```env
OPENAI_API_KEY=sk-...
SENSEI_USE_LLM=1
```

## Post-game review (no overlay)

Install the explainer package only:

```bash
pip install shanten-sensei
sensei serve path/to/review.json
```

See [phase1-contract.md](phase1-contract.md).

## Developers

Terminal setup, Chromium browser path, tests, and two-repo layout: [live-setup.md](live-setup.md).
