"""Local review UI: diverge list + status strip + on-demand Why? (LLM)."""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import parse_qs, urlparse

from shanten_sensei.explain import (
    _furiten_blocking_tiles,
    coaching_shape_goals,
    explain_llm,
    template_explain,
    validate_explanation,
)
from shanten_sensei.glosses import (
    GLOSS_CHECKLIST,
    YAKU_REFERENCE_LABEL,
    YAKU_REFERENCE_URL,
    format_aiming_for,
    glossed_danger,
    glossed_furiten,
    glossed_shanten,
    glossed_ukeire_count,
    glossed_wait,
    normalize_known_terms,
    using_known_terms,
)
from shanten_sensei.ingest import DivergeTurn, diverge_turns_from_path, load_json
from shanten_sensei.schema import Explanation, TurnExplainInput
from shanten_sensei.tiles import coach_action_label

EXPLAIN_PATH_RE = re.compile(r"^/api/explain/(\d+)$")
ExplainSource = Literal["llm", "template"]


def _parse_known_terms(qs: dict[str, list[str]]) -> list[str]:
    """Accept known_terms=a,b,c or repeated known_terms=a&known_terms=b."""
    raw_list = qs.get("known_terms") or []
    out: list[str] = []
    for raw in raw_list:
        for part in raw.split(","):
            term = part.strip()
            if term:
                out.append(term)
    return out


def _parse_score_tips(qs: dict[str, list[str]], body: dict[str, Any] | None = None) -> bool:
    """Opt-in point tips via score_tips=1 / true (query or JSON body). Default off."""
    if body and "score_tips" in body:
        raw = body["score_tips"]
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    raw_list = qs.get("score_tips") or []
    if not raw_list:
        return False
    return str(raw_list[0]).strip().lower() in ("1", "true", "yes", "on")


def resolve_web_dir() -> Path:
    """Locate web/ for editable installs and cwd-relative runs."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "web",  # repo root: src/shanten_sensei/serve.py
        here.parent / "web",
        Path.cwd() / "web",
    ]
    for path in candidates:
        if (path / "review.html").is_file():
            return path
    raise FileNotFoundError(
        "web/review.html not found; expected next to the repo root or under cwd"
    )


class ReviewSession:
    """In-memory diverge turns for one loaded report."""

    def __init__(
        self,
        diverges: list[DivergeTurn],
        *,
        log_id: str | None = None,
        explain_fn: Callable[[TurnExplainInput], Explanation] | None = None,
    ) -> None:
        self.diverges = diverges
        self.log_id = log_id
        self._by_index = {d.index: d for d in diverges}
        self._cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._explain_fn = explain_fn or explain_llm
        self._explain_calls = 0

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        limit: int | None = None,
        explain_fn: Callable[[TurnExplainInput], Explanation] | None = None,
    ) -> ReviewSession:
        path = Path(path)
        blob = load_json(path)
        log_id = blob.get("log_id")
        if not isinstance(log_id, str):
            log_id = path.stem
        diverges = diverge_turns_from_path(path, limit=limit)
        return cls(diverges, log_id=log_id, explain_fn=explain_fn)

    def review_payload(
        self, *, known_terms: list[str] | None = None
    ) -> dict[str, Any]:
        known = normalize_known_terms(known_terms)
        return {
            "log_id": self.log_id,
            "diverge_count": len(self.diverges),
            "gloss_checklist": [
                {"id": item.id, "group": item.group, "gloss": item.gloss}
                for item in GLOSS_CHECKLIST
            ],
            "known_terms": sorted(known),
            "diverges": [
                self._diverge_summary(d, known_terms=known) for d in self.diverges
            ],
        }

    def explain_index(
        self,
        index: int,
        *,
        mode: ExplainSource = "llm",
        known_terms: list[str] | None = None,
        include_score_tips: bool = False,
    ) -> dict[str, Any]:
        known = normalize_known_terms(known_terms)
        known_key = tuple(sorted(known))
        score_tips = bool(include_score_tips)
        cache_key = (index, mode, known_key, score_tips)
        if cache_key in self._cache:
            return self._cache[cache_key]
        diverge = self._by_index.get(index)
        if diverge is None:
            raise KeyError(index)
        if mode == "template":
            explanation = template_explain(
                diverge.turn,
                known_terms=known,
                include_score_tips=score_tips,
            )
            source: ExplainSource = "template"
        else:
            self._explain_calls += 1
            # Prefer kwargs when the injected explain_fn supports them.
            try:
                explanation = self._explain_fn(  # type: ignore[call-arg]
                    diverge.turn,
                    known_terms=known,
                    include_score_tips=score_tips,
                )
            except TypeError:
                try:
                    explanation = self._explain_fn(  # type: ignore[call-arg]
                        diverge.turn, known_terms=known
                    )
                except TypeError:
                    explanation = self._explain_fn(diverge.turn)
            source = "llm"
        errors = validate_explanation(diverge.turn, explanation)
        payload = {
            "index": index,
            "source": source,
            "explanation": explanation.model_dump(),
            "grounding_errors": errors,
            "known_terms": sorted(known),
            "score_tips": score_tips,
        }
        self._cache[cache_key] = payload
        return payload

    @staticmethod
    def _diverge_summary(
        d: DivergeTurn, *, known_terms: frozenset[str] | None = None
    ) -> dict[str, Any]:
        turn = d.turn
        statuses = turn.features.statuses
        wait_shape = statuses.wait_shape
        shanten = turn.features.shanten
        blocking = _furiten_blocking_tiles(turn)
        known = known_terms or frozenset()
        with using_known_terms(known):
            return {
                "index": d.index,
                "kyoku": d.kyoku,
                "honba": d.honba,
                "junme": d.junme,
                "mortal_best": turn.mortal_best,
                "player_action": turn.player_action,
                "mortal_best_label": coach_action_label(turn.mortal_best),
                "player_action_label": coach_action_label(turn.player_action),
                "shanten": shanten,
                "shanten_label": glossed_shanten(shanten, known_terms=known),
                "ukeire": turn.features.ukeire.count,
                "ukeire_label": glossed_ukeire_count(
                    turn.features.ukeire.count, known_terms=known
                ),
                "ukeire_tiles": list(turn.features.ukeire.tiles),
                "ukeire_remaining": dict(turn.features.ukeire.remaining_by_tile),
                "hand": list(turn.game_state.hand),
                "calls": list(turn.game_state.calls),
                "wait_shape": wait_shape,
                "wait_shape_label": glossed_wait(wait_shape, known_terms=known),
                "shape_goals": coaching_shape_goals(turn),
                "aiming_for": format_aiming_for(
                    coaching_shape_goals(turn), known_terms=known
                ),
                "yaku_reference_url": YAKU_REFERENCE_URL,
                "yaku_reference_label": YAKU_REFERENCE_LABEL,
                "statuses": statuses.model_dump(),
                "furiten_label": glossed_furiten(
                    furiten=bool(statuses.furiten),
                    temporary=bool(statuses.temporary_furiten),
                    known_terms=known,
                ),
                "furiten_blocking_tiles": list(blocking),
                "danger": turn.features.danger,
                "danger_labels": {
                    tile: glossed_danger(tag, known_terms=known) or tag
                    for tile, tag in turn.features.danger.items()
                },
            }


def make_handler(
    session: ReviewSession,
    *,
    web_dir: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    web_root = web_dir or resolve_web_dir()

    class ReviewHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/review":
                known = _parse_known_terms(parse_qs(parsed.query))
                self._json(200, session.review_payload(known_terms=known))
                return
            if path in ("/", "/index.html"):
                self._file(web_root / "review.html", "text/html; charset=utf-8")
                return
            if path in ("/yakuman_idle.png", "/yakuman_talk.png"):
                name = path.lstrip("/")
                self._file(web_root / name, "image/png")
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            match = EXPLAIN_PATH_RE.match(parsed.path)
            if not match:
                self._json(404, {"error": "not found"})
                return
            index = int(match.group(1))
            qs = parse_qs(parsed.query)
            mode_raw = (qs.get("mode") or ["llm"])[0].strip().lower()
            if mode_raw not in ("llm", "template"):
                self._json(400, {"error": "mode must be 'llm' or 'template'"})
                return
            mode: ExplainSource = "template" if mode_raw == "template" else "llm"
            known = _parse_known_terms(qs)
            body: dict[str, Any] | None = None
            # Optional JSON body may also carry known_terms / score_tips.
            length = int(self.headers.get("Content-Length") or 0)
            if length > 0:
                try:
                    parsed_body = json.loads(
                        self.rfile.read(length).decode("utf-8") or "{}"
                    )
                except json.JSONDecodeError:
                    parsed_body = {}
                if isinstance(parsed_body, dict):
                    body = parsed_body
                    if body.get("known_terms") is not None:
                        raw = body["known_terms"]
                        if isinstance(raw, list):
                            known = [str(x) for x in raw]
                        elif isinstance(raw, str):
                            known = [
                                p.strip() for p in raw.split(",") if p.strip()
                            ]
            score_tips = _parse_score_tips(qs, body)
            try:
                payload = session.explain_index(
                    index,
                    mode=mode,
                    known_terms=known,
                    include_score_tips=score_tips,
                )
            except KeyError:
                self._json(404, {"error": f"diverge index {index} not found"})
                return
            except ValueError as exc:
                msg = str(exc)
                if "missing API key" in msg:
                    self._json(503, {"error": msg})
                else:
                    self._json(502, {"error": msg})
                return
            except Exception as exc:
                self._json(502, {"error": f"LLM explain failed: {exc}"})
                return
            self._json(200, payload)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: Path, content_type: str) -> None:
            if not path.is_file():
                self._json(404, {"error": f"missing {path.name}"})
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ReviewHandler


def serve_review(
    path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    limit: int | None = None,
) -> None:
    session = ReviewSession.from_path(path, limit=limit)
    handler = make_handler(session)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Shanten Sensei review UI — practice / review only")
    print(f"Loaded {session.review_payload()['diverge_count']} diverges from {path}")
    print(f"Open {url}")
    print("Why? uses OPENAI_API_KEY or SENSEI_API_KEY (from env or .env)")
    print("Offline explanation available in the UI if the LLM is unavailable")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
