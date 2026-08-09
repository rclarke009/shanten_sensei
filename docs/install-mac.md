# Install Shanten Sensei on Mac

**Audience:** players who want live coaching — not developers.

Practice / friend / vs-AI only — **not for ranked**.

**Defaults:** English overlay UI and the English YoStar Majsoul client. Setup and updates re-apply these; change either in **Settings** if needed.

## Quick start

| Method | When to use |
|--------|-------------|
| **[Install-Shanten-Sensei.zip](https://github.com/rclarke009/shanten-sensei-overlay/releases/latest)** | **Easiest** — unzip, double-click the `.command` inside |
| **[Download .dmg](https://github.com/rclarke009/shanten-sensei-overlay/releases)** | Manual drag-to-Applications install |
| **[One-click installer](https://github.com/rclarke009/shanten-sensei-overlay/blob/main/scripts/install-macos.command)** | From a cloned overlay repo before a Release exists |
| **[Developer setup](live-setup.md)** | Contributing or Chromium / from-source |

### Download path (recommended)

1. Open [overlay Releases](https://github.com/rclarke009/shanten-sensei-overlay/releases/latest) and download **`Install-Shanten-Sensei.zip`**.
2. Unzip it, then double-click **`Install-Shanten-Sensei.command`** (right-click → **Open** if macOS blocks it).
3. It installs **Shanten Sensei** to Applications and opens the app. The installer checks GitHub for the latest release and re-downloads if your cached `.dmg` is older. Complete the **first-run wizard** (bundled Mortal model, Safari companion, optional API key).
4. Play Majsoul in **Safari**, join friend / practice / vs-AI, press **Why?** in the coach window.

**Or** use the `.dmg` manually: drag **Shanten Sensei** to Applications (right-click → **Open** if macOS warns about an unsigned build).

Full troubleshooting and proxy/cert notes: [overlay INSTALL.md](https://github.com/rclarke009/shanten-sensei-overlay/blob/main/INSTALL.md) and [proxy-trust-precautions.md](proxy-trust-precautions.md).

### One-click installer path

1. Install [Python 3.11](https://www.python.org/downloads/).
2. Clone [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay).
3. Double-click `scripts/install-macos.command`.
4. Open **Shanten Sensei** from `~/Applications/`.

The installer installs `shanten-sensei` from PyPI (or git) — you do **not** need a sibling `shanten_sensei` clone.

## Mortal model

**Release `.dmg` builds** include the [VoidShine/mortal-298k](https://huggingface.co/VoidShine/mortal-298k) checkpoint (AGPL-3.0). License text: [overlay MORTAL_MODEL_NOTICE.md](https://github.com/rclarke009/shanten-sensei-overlay/blob/main/licenses/MORTAL_MODEL_NOTICE.md).

**From-source installs** still need your own Akagi-compatible `.pth` ([Akagi](https://github.com/shinkuan/Akagi)).

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
