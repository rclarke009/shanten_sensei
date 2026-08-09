# Shanten Sensei

**An AI coach that explains *why* a riichi mahjong move is good or bad — grounded in Mortal, not vibes.**

Shanten Sensei sits on top of existing open-source Mahjong Soul tooling. It does not reinvent board reading or AI evaluation. It adds the missing layer: plain-language coaching for beginners who learn best when someone is looking over their shoulder.

---

## Download for Mac (live coaching)

**Not a developer?** Start here:

- **[Install on Mac](docs/install-mac.md)** — download `Install-Shanten-Sensei.zip` from Releases; Safari companion is the default path.
- [Overlay Releases](https://github.com/rclarke009/shanten-sensei-overlay/releases) — macOS app bundle when published.

Practice / friend / vs-AI only — not for ranked. Developer setup (Terminal, Chromium, two-repo clone): [`docs/live-setup.md`](docs/live-setup.md).

---

## The problem

People learning riichi mahjong (e.g. on [Mahjong Soul](https://mahjongsoul.game.yo-star.com)) want live, over-the-shoulder feedback: *why* that discard was wrong, *why* keeping this tile opens a better wait, *why* defense matters on this turn.

Existing tools already solve the hard parts:

| Tool | Role |
|------|------|
| [Mortal](https://github.com/Equim-chan/Mortal) | Strongest open riichi AI — action values + recommendations |
| [mjai-reviewer](https://github.com/Equim-chan/mjai-reviewer) | Post-game log review via Mortal |
| [MahjongCopilot](https://github.com/latorc/MahjongCopilot) / [Akagi](https://github.com/shinkuan/Akagi) | Live Majsoul websocket → Mortal → overlay |

What they give you is the **what** (optimal discard, efficiency numbers). What beginners need is the **why** in one or two clear sentences. That “engine math → human explanation” layer is not really productized yet. That’s this project.

---

## Non-goals

- Building a stronger mahjong AI than Mortal
- Pixel/OCR vision of the board (Majsoul is WebGL; wrong approach)
- Ranked / live-ladder assistance against real players
- Letting an LLM invent its own discard opinions

---

## Core design rule

**The LLM translates Mortal. It never evaluates the hand itself.**

Language models are weak mahjong players and will confidently invent wrong advice. Mortal is near-superhuman. Every explanation must be pinned to:

1. Mortal’s recommended action  
2. Mortal’s values for alternatives  
3. Derived facts (shanten, ukeire, danger) from real libraries  

Get this wrong → confident liar. Get this right → the coach we actually want.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Existing plumbing (reuse)                    │
│                                                                  │
│  Majsoul WebSocket                                               │
│        │                                                         │
│        ▼                                                         │
│  protobuf decode (liqi.json)                                     │
│        │                                                         │
│        ▼                                                         │
│  mjai events  ──►  Mortal  ──►  recommended action + values      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Shanten Sensei (this project)                     │
│                                                                  │
│  On player turn (or post-game diverge):                          │
│                                                                  │
│  1. mjai game state  (hand, discards, dora, turn, scores)        │
│  2. Mortal output    (best action + alternative scores)          │
│  3. derived features (shanten, ukeire, suji / one-chance danger) │
│                                                                  │
│        │                                                         │
│        ▼                                                         │
│  explain(state, mortal, features)  ──►  1–2 sentence coach text  │
│                                                                  │
│  Shown in review UI or overlay ("Why?" button)                   │
└─────────────────────────────────────────────────────────────────┘
```

**Interface of record:** the [mjai protocol](https://mjai.app/) — a stream of JSON events (`tsumo`, `dahai`, `pon`, `reach`, etc.). Upstream tools already converge here; we consume that stream and Mortal’s outputs.

---

## Explainer module spec

### Function

```text
explain(game_state, mortal_output, features) → Explanation
```

### Inputs

| Input | Contents |
|-------|----------|
| `game_state` | Current hand, visible discards, dora indicators, turn/honba, scores, calls, riichi flags — from mjai |
| `mortal_output` | Recommended action; value / Q for each legal candidate; confidence if available |
| `features` | Shanten, ukeire (acceptance count), danger tags (suji, one-chance, genbutsu), point-situation hints, and **hand statuses** (see below) |

### Hand statuses (UI + features)

Surface these as a persistent status strip in the review UI / overlay (not only inside “Why?” text). Derive from mjai state + libraries — never invent via the LLM.

| Status | Meaning | Source |
|--------|---------|--------|
| Closed / open (menzen) | Hand has no calls vs has chi/pon/kan | Calls in `game_state` |
| Tenpai | Ready hand (`shanten == 0`) | Shanten library |
| Shanten | Distance to tenpai | Shanten library |
| Ukeire / waits | Acceptance count + waiting tiles | Ukeire library |
| Wait shape | e.g. ryanmen, kanchan, penchan, tanki, shanpon | Derived from wait set |
| Furiten | Permanent (discards ∩ waits) and/or temporary (this turn) | Discards + wait set |
| Riichi / ippatsu | Self declared riichi; ippatsu window if applicable | mjai `reach` + timing |
| Dora | Dora in hand; visible dora indicators | Hand + dora indicators |
| Danger tags | suji / one-chance / genbutsu on candidate discards | Danger heuristics |

### Output

```text
Explanation {
  summary: string   // 1–2 sentences, beginner-friendly
  focus: "efficiency" | "defense" | "value" | "tempo" | "mixed"
  pinned_action: string   // Mortal's recommended action (must match)
  contrasted_action?: string  // player's choice when it differed
}
```

### Constraints

- Never recommend an action Mortal did not rank highly (pin to Mortal’s top choice, or explain the gap vs. the player’s pick).
- Prefer concrete tile language (“5-sou”, “ryanmen wait”) over jargon dumps; introduce terms when used.
- Default length: one or two sentences. Optional `detail` paragraph behind a second-click “More” in review (grounded facts only).
- Trigger model: **on demand** (“Why?”) — not every tile — to control cost and attention.

### Suggested feature sources

Reuse existing Python mahjong libraries where possible for shanten / ukeire / danger rather than asking the LLM to invent them. Mortal remains the source of truth for *which* action; features only help the verbalization.

---

## Prompt design (v0)

System role (essence):

> You are a beginner-friendly riichi mahjong coach. You explain Mortal’s recommendation using only the game state, Mortal scores, and derived features provided. You do not invent better moves. If the player’s move differs, say why Mortal’s choice is better in efficiency, safety, or point situation. One or two sentences. Plain English.

User payload shape:

```json
{
  "player_action": "dahai 5s",
  "mortal_best": "dahai 9p",
  "mortal_scores": { "dahai 9p": 0.42, "dahai 5s": 0.11, "...": "..." },
  "hand": ["1m", "2m", "3m", "..."],
  "shanten": 0,
  "ukeire": { "count": 6, "tiles": ["4s", "7s"] },
  "statuses": {
    "menzen": true,
    "tenpai": true,
    "furiten": false,
    "temporary_furiten": false,
    "riichi": false,
    "ippatsu": false,
    "wait_shape": "ryanmen",
    "dora_in_hand": ["5m"],
    "visible_dora": ["4m"]
  },
  "danger": { "9p": "genbutsu" },
  "context": { "turn": 8, "riichi_opponents": 0, "score_diff": "even" }
}
```

Failure modes to guard in the prompt / post-checks:

1. **Contradiction** — summary must not recommend a different tile than `mortal_best`.
2. **Invented facts** — no claims about waits or danger not present in `features` / state.
3. **Wall of jargon** — reject / regenerate if over a short length budget.

---

## Build order

### Phase 1 — Post-game explainer (MVP)

**Goal:** After a finished Majsoul game, for every turn where the player differed from Mortal, generate a plain-English explanation.

**Why first:** Zero real-time complexity, no live client hook, no ToS risk from in-game assistance. Useful in a weekend if mjai-reviewer is already producing diverge turns.

**Deliverables:**

- CLI or small web UI: paste Majsoul replay / log → list of diverge turns → status strip + “Why?” text per turn  
- `explain()` module with grounded prompt  
- Fixture tests: sample mjai + Mortal JSON → explanation contains pinned action and does not invent alternatives  

**Phase 1 checklist**

- [x] Document how to obtain a Majsoul log / run mjai-reviewer locally (or use its web app output) — see `docs/phase1-contract.md`
- [x] Define a JSON schema for `(game_state, mortal_output, features)` per turn, including `statuses` — `schema.py`
- [x] Implement feature extraction (shanten, ukeire, basic danger) from libraries
- [x] Implement hand statuses: menzen, tenpai, furiten (permanent + temporary), riichi/ippatsu, wait shape, dora in hand / visible dora
- [x] Review UI: persistent status strip for the above (plus shanten / ukeire); “Why?” remains on demand — `sensei serve`
- [x] Implement `explain()` with an LLM API (env-based key; model configurable) + offline template fallback
- [x] Add contradiction check: explanation must mention / pin Mortal’s action
- [x] CLI: `sensei explain <entry.json>`, `sensei review <report.json>`, and `sensei serve <report.json>`
- [x] Golden fixtures: 5 diverge turns (1 synthetic + 4 real from a practice log); more via `scripts/extract_diverge.py`
- [x] README section: “Practice / review only — not for ranked assistance”

### Phase 2 — Live overlay (practice / vs-AI only)

**Goal:** Fork MahjongCopilot; wire Sensei `explain()` behind a **Why?** button on the existing overlay.

**How to play live:** step-by-step setup + in-game flow → **[`docs/live-setup.md`](docs/live-setup.md)**

**Dual clients (Chromium + Safari companion on macOS):** [`docs/dual-client-architecture.md`](docs/dual-client-architecture.md) · proxy/cert precautions: [`docs/proxy-trust-precautions.md`](docs/proxy-trust-precautions.md) · play steps: [`docs/live-setup.md`](docs/live-setup.md)

**Repos:**

| Piece | Location |
|-------|----------|
| Explainer (`turn_from_live` → `explain`) | This repo — [`docs/phase2-kickoff.md`](docs/phase2-kickoff.md) |
| Overlay fork (GPL-3.0) | [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay) |

**Constraints:**

- Practice / friend / vs-AI only — not ranked ladder against humans  
- On-demand LLM calls only  
- Same grounding rules as Phase 1  
- Sibling repos: do not merge the GPL fork into this tree  

**Deliverables (kickoff):**

- [x] Fork + Sensei adapter + mode gate  
- [x] Overlay UX: Mortal recommendation + status strip + **Why?**  
- [x] In-app practice-only banner; Why? disabled on ranked / unknown mode  

---

## How to play live (short)

**Mac users:** see **[`docs/install-mac.md`](docs/install-mac.md)** (download `Install-Shanten-Sensei.zip` from Releases).

**Developers / from source:**

1. Clone [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay) as a **sibling** of this repo, or install `shanten-sensei` from PyPI inside the overlay venv.
2. Install overlay deps; place an Akagi-compatible Mortal `.pth` in the overlay `models/` folder.
3. `python main.py` → **Start Browser** (Chromium) or enable Safari companion → Overlay on, Autoplay off.
4. Join a **friend / practice / vs-AI** game (not ranked).
5. On your turn, press **Why?** for a grounded explanation.

Full commands, API key, and troubleshooting: [`docs/live-setup.md`](docs/live-setup.md).

---

## What it takes

| Layer | Status |
|-------|--------|
| Majsoul protocol decode | Exists (`liqi.json`, upstream tools) |
| mjai event stream | Exists |
| Mortal evaluation | Exists |
| Overlay / review UI | Exists (fork) |
| **Explainer + prompt + grounding** | **This repo** |

Stack expectation: **Python**, comfort calling an LLM API. Protocol and engine work are reuse/fork, not greenfield.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Majsoul protocol changes break decoders | Depend on upstream `liqi.json` updates; Phase 1 can use offline logs |
| LLM cost | “Why?” on demand; short completions; cache identical states |
| Hallucination | Pin to Mortal; pass numeric features; post-validate pinned action |
| ToS / bans | No ranked live assist; document practice-only for Phase 2 |
| Scope creep into “better AI” | Refuse LLM-only evaluation paths |

---

## Ethical / ToS stance

Real-time client hooks for Majsoul assistance can violate the game’s terms of service and is bannable in ranked play if detected. This project’s learning stance:

1. **Phase 1** — post-game review only (safest, preferred default).  
2. **Phase 2** — practice / vs-AI only; never marketed as a ranked win tool.  
3. Prefer teaching understanding over automating optimal play for ladder climbing.

---

## Success criteria

A beginner can play a practice game, open a review (or press **Why?**), and get an explanation like:

> Keeping the 5-sou instead of the 9-pin preserves a two-sided wait and you’re still one away from riichi; the 9-pin is a dead end tile with far fewer acceptances.

…and that sentence matches Mortal’s numbers, not a chatbot’s guess.

---

## Related projects

- [Mortal](https://github.com/Equim-chan/Mortal) — riichi AI  
- [mjai-reviewer](https://github.com/Equim-chan/mjai-reviewer) — post-game Mortal review  
- [MahjongCopilot](https://github.com/latorc/MahjongCopilot) — live guidance + overlay (upstream of our fork)  
- [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay) — Sensei Why? on Copilot  
- [Akagi](https://github.com/shinkuan/Akagi) — live analysis, swappable models  
- [mjai](https://mjai.app/) — event protocol  

---

## Status

Phase 1 ready (post-game explainer + local review UI). Phase 2 live overlay is in the sibling fork.

- **Live play how-to:** [`docs/live-setup.md`](docs/live-setup.md)
- Contract: [`docs/phase1-contract.md`](docs/phase1-contract.md)
- Phase 2 live contract: [`docs/phase2-kickoff.md`](docs/phase2-kickoff.md)
- Schema / features / `explain()` / `live.py`: `src/shanten_sensei/`
- Golden fixtures: `fixtures/diverge_001/` … `diverge_005/` (cut more with `scripts/extract_diverge.py`)
- Full reports with `mjai_log` enrich rivers / dora / genbutsu for the status strip
- License: Apache-2.0 (this repo); overlay fork remains GPL-3.0
- Overlay: [shanten-sensei-overlay](https://github.com/rclarke009/shanten-sensei-overlay)

```bash
uv venv .venv
uv pip install -e ".[dev]" --python .venv/bin/python
# optional: put OPENAI_API_KEY or SENSEI_API_KEY in a repo-root .env (auto-loaded)
uv run --python .venv/bin/python sensei explain fixtures/diverge_002/entry.json
uv run --python .venv/bin/python sensei review fixtures/review_mini/report.json
# local review UI (Why? uses the API key; Offline explanation if unavailable):
uv run --python .venv/bin/python sensei serve fixtures/review_mini/report.json
# or a full mjai-reviewer export:
# uv run --python .venv/bin/python sensei review game_logs/review.json
# uv run --python .venv/bin/python sensei serve game_logs/review.json
# cut another fixture from a report:
# uv run --python .venv/bin/python scripts/extract_diverge.py game_logs/review.json \
#   --kyoku 0 --honba 0 --junme 3 -o fixtures/diverge_00N/entry.json
uv run --python .venv/bin/python pytest
```

Practice / review only — not for ranked assistance.
