---
name: Grounding test hygiene
overview: Refactor coaching tests and validators so new bugs add one grounding rule + one property test; split eval from unit; align serve with explain() repair; template-first by default with explicit LLM opt-in (SENSEI_USE_LLM=1).
todos:
  - id: split-tests
    content: Extract conftest _turn(); split test_explanation_substance into test_grounding, eval/template_goldens, eval/screenshot_regressions; add pytest eval marker
    status: completed
  - id: grounding-module
    content: Create grounding.py with GroundingRule registry; move _xxx_error fns from explain.py; re-export validate_explanation
    status: completed
  - id: parametrize-rules
    content: Refactor test_grounding.py to parametrized RULE_CASES per rule id; document workflow in docs/testing-coaching.md
    status: completed
  - id: serve-repair
    content: serve ReviewSession uses explain(use_llm=True) with repair instead of bare explain_llm
    status: completed
  - id: template-first-default
    content: "Locked: template by default; LLM only when SENSEI_USE_LLM=1, --llm, or ?mode=llm; update .env.example and docs"
    status: completed
  - id: fuzz-property
    content: Add test_grounding_fuzz.py with seeded random_turn builder; assert template always validates
    status: completed
isProject: false
---

# Grounding architecture and test hygiene

## Locked decision: template-first (Option A)

**API key alone no longer enables the LLM.** Template is the default everywhere.

| Surface | Default | Opt-in LLM |
|---------|---------|------------|
| `explain()` | `template_explain` | `SENSEI_USE_LLM=1` or `use_llm=True` |
| CLI `sensei explain` | template | `--llm` |
| Review `POST /api/explain/{n}` | template | `?mode=llm` |
| Overlay Why? | template | `SENSEI_USE_LLM=1` in overlay `.env` |

Rationale: facts and phrasing live in deterministic code; LLM is optional polish with validator + repair, not the primary author.

---

## What’s appropriate now

| Phase | Effort | Value | Risk |
|-------|--------|-------|------|
| 1. Split eval vs unit | Medium | High | Low |
| 2. Consolidate validators | Medium | High | Low |
| 3. Template-first + serve repair | Small | High | Low (decision locked) |
| 4. Lightweight fuzz | Small | Medium | Low |

**Skip for now:** LangGraph/agents, Hypothesis, LLM paraphrase-only pass.

## Current pain (baseline)

- [`tests/test_explanation_substance.py`](tests/test_explanation_substance.py) (~1,700 lines) mixes validators, template goldens, screenshot regressions, payload tests.
- [`explain.py`](src/shanten_sensei/explain.py) (~2,850 lines) holds ~10 `_xxx_error` validators inline.
- [`serve.py`](src/shanten_sensei/serve.py) defaults to `explain_llm` — no repair on validation failure.
- [`explain()`](src/shanten_sensei/explain.py) today: `use_llm = bool(API_KEY)` when `use_llm is None` — **changing to `SENSEI_USE_LLM` gate.**

---

## Phase 1 — Split eval from unit

### Target layout

```
tests/
  conftest.py              # shared _turn() builder
  test_grounding.py        # validate_explanation property tests
  test_explanation_substance.py  # substance, payload, merge, emoji (slim)
  eval/
    test_template_goldens.py
    test_screenshot_regressions.py
  test_ingest_explain.py   # parametrized diverge_* (unchanged)
```

### Pytest marker ([`pyproject.toml`](pyproject.toml))

```toml
markers = ["eval: screenshot/template regression (copy-sensitive)"]
```

- CI default: `pytest`
- Optional: `pytest -m eval`

### Contributor rule ([`docs/testing-coaching.md`](docs/testing-coaching.md))

| Bug type | Add |
|----------|-----|
| Wrong fact / polarity | `test_grounding.py` — rule id + bad `Explanation` |
| Copy/layout screenshot | `eval/test_screenshot_regressions.py` |
| Template voice path | `eval/test_template_goldens.py` |
| Real log diverge | `fixtures/diverge_NNN/` + ingest parametrize |

No production code in Phase 1.

---

## Phase 2 — Consolidate validators

New [`src/shanten_sensei/grounding.py`](src/shanten_sensei/grounding.py):

```python
@dataclass(frozen=True)
class GroundingRule:
    id: str
    check: Callable[[TurnExplainInput, str, Explanation], str | None]

GROUNDING_RULES: tuple[GroundingRule, ...] = (...)

def validate_explanation(turn, explanation) -> list[str]:
    ...
    for rule in GROUNDING_RULES:
        msg = rule.check(turn, summary_l, explanation)
        if msg:
            errors.append(f"{rule.id}: {msg}")
```

Move all `_xxx_error` fns and regex constants from `explain.py`. Re-export `validate_explanation` from `explain.py`.

`test_grounding.py`: parametrized `RULE_CASES` — new bug = one rule + one row.

---

## Phase 3 — Template-first + serve repair (locked)

### 3a. `explain()` default gate

In [`explain.py`](src/shanten_sensei/explain.py):

```python
if use_llm is None:
    use_llm = os.environ.get("SENSEI_USE_LLM", "").lower() in ("1", "true", "yes")
```

Remove: `use_llm = bool(OPENAI_API_KEY or SENSEI_API_KEY)`.

### 3b. Serve uses repair path

Replace default `explain_fn=explain_llm` with wrapper calling `explain(turn, use_llm=True, ...)` so validation failure repairs to template (same as overlay).

- `mode=template` → unchanged
- `mode=llm` → `explain(use_llm=True)` with repair
- API still returns `grounding_errors` for debugging

### 3c. Docs and env

Update:
- [`.env.example`](.env.example) — document `SENSEI_USE_LLM=1` (key alone is not enough)
- [`docs/live-setup.md`](docs/live-setup.md) — overlay users must set both key and `SENSEI_USE_LLM=1` for LLM Why?
- [`docs/phase1-contract.md`](docs/phase1-contract.md) — review default is template; `?mode=llm` for LLM
- [`docs/phase2-kickoff.md`](docs/phase2-kickoff.md) — same for overlay

### 3d. Tests

- Any test that relied on implicit `use_llm=True` when key present: pass `use_llm=True` explicitly or set `SENSEI_USE_LLM=1` in test env.
- Add test: `explain(turn)` with only API key set (no `SENSEI_USE_LLM`) → template path.
- Add test: `SENSEI_USE_LLM=1` + mocked `_llm_explain` → LLM path.

---

## Phase 4 — Lightweight fuzz

[`tests/test_grounding_fuzz.py`](tests/test_grounding_fuzz.py):

- `random_turn` fixture, seeded `Random(0)`, 200–500 iterations
- Property: `validate_explanation(turn, template_explain(turn)) == []`
- No Hypothesis dependency

---

## Out of scope

- LangGraph / agents
- LLM paraphrase-only pass over template
- Splitting template code out of `explain.py` (beyond grounding extract)

## Verification

- `pytest` — all unit + ingest green
- `pytest -m eval` — copy regressions green
- `pytest tests/test_grounding_fuzz.py` — passes
- Manual: key in `.env` but no `SENSEI_USE_LLM` → template tips; with both → LLM + repair on drift
