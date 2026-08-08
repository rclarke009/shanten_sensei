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

## Running tests

```bash
uv run pytest              # unit + ingest (default CI)
uv run pytest -m eval      # copy-sensitive regressions only
uv run pytest tests/test_grounding_fuzz.py
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
