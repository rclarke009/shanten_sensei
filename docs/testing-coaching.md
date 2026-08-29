# Testing coaching (Why? tips)

## Layout

| Path | Purpose |
|------|---------|
| `tests/conftest.py` | Shared `make_turn()` builder and screenshot-shaped turns |
| `tests/test_grounding.py` | Grounding validator property tests (`validate_explanation`) |
| `tests/test_explanation_substance.py` | Substance metric, payload, merge, emoji helpers |
| `tests/eval/test_template_goldens.py` | Template voice regressions (copy-sensitive) |
| `tests/eval/test_screenshot_regressions.py` | Screenshot-shaped copy regressions |
| `tests/test_grounding_fuzz.py` | Seeded fuzz: `template_explain` always validates |
| `tests/test_ingest_explain.py` | Real log diverges (`fixtures/diverge_NNN/`) |

## After a major change

From this repo, one command is enough. `uv run pytest` runs **everything** under `tests/` — unit, ingest fixtures (`diverge_001`–`005`), copy-sensitive eval goldens, and grounding fuzz. The `eval` marker is for targeting copy files, not for excluding them (pytest.ini has no `-m "not eval"`). There is no GitHub pytest CI today; this local run is the gate.

```bash
uv run pytest
```

When you only touched Why? copy / glosses:

```bash
uv run pytest -m eval
uv run pytest tests/test_explanation_substance.py tests/test_grounding.py \
  tests/test_riichi_coaching.py tests/test_call_coaching.py tests/test_serve.py \
  tests/test_glosses.py tests/test_features.py -q
```

When live discards, Why? cache, or score-tips wiring changed, also run the overlay adapter suite (sibling repo; uses this package):

```bash
cd ../shanten-sensei-overlay
# pytest on PATH, or the Sensei venv:
../shanten_sensei/.venv/bin/python -m pytest \
  tests/test_sensei_adapter.py tests/test_coach_journal.py -q
```

Coaching substance map:

| Slice | Tests |
|-------|--------|
| Wait gloss + furiten because | `tests/eval/test_template_goldens.py` (`test_template_wait_gloss_and_furiten_because`); `tests/test_glosses.py`; `tests/test_features.py` / `tests/test_live.py` river + reach-cut; overlay `test_build_turn_passes_player_river_for_furiten` |
| Defense / riichi / score | goldens `test_template_suji_*`, `test_template_genbutsu_*`, `test_template_score_situation_*`; `tests/test_riichi_coaching.py`; danger/score builders in `tests/test_features.py`. Score sentences only when `include_score_tips=True` (default off) |
| Review parity | `tests/test_serve.py` (`aiming_for`, `wait_shape_label`, `danger_labels`, `furiten_label`, `furiten_blocking_tiles`) |
| Real-log smoke | `tests/test_ingest_explain.py` over `fixtures/diverge_*/` — ingest + grounding, not copy pins |

```bash
uv run pytest tests/test_grounding_fuzz.py   # property: template always validates
```

## When a bug appears

| Bug type | Add |
|----------|-----|
| Wrong fact / polarity | `tests/test_grounding.py` — one row in `RULE_REJECT_CASES` (or a focused test) + rule in `src/shanten_sensei/grounding.py` |
| Copy/layout screenshot | `tests/eval/test_screenshot_regressions.py` |
| Template voice path | `tests/eval/test_template_goldens.py` |
| Real log diverge | `fixtures/diverge_NNN/` + parametrized row in `tests/test_ingest_explain.py` |

## Adding a grounding rule

1. Implement `_xxx_error(...)` in `grounding.py`.
2. Register it in `GROUNDING_RULES` with a stable `id` string.
3. Add one reject row to `RULE_REJECT_CASES` in `test_grounding.py` (or a dedicated test if setup is heavy).

New bugs should be **one rule + one test row**, not another 100-line monolith.

## LLM vs template in tests

- Default `explain()` uses the **template** unless `SENSEI_USE_LLM=1` or `use_llm=True`.
- Pass `use_llm=True` explicitly (or set env) when testing LLM repair paths.
- Review UI: `POST /api/explain/{n}` defaults to `?mode=template`; use `?mode=llm` for LLM + repair.
