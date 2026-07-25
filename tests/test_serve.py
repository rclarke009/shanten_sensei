import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from shanten_sensei.explain import template_explain
from shanten_sensei.serve import ReviewSession, make_handler, resolve_web_dir

REPORT = Path(__file__).resolve().parents[1] / "fixtures" / "review_mini" / "report.json"


@pytest.fixture
def session_and_server():
    calls = {"n": 0}

    def stub_explain(turn):
        calls["n"] += 1
        return template_explain(turn)

    session = ReviewSession.from_path(REPORT, explain_fn=stub_explain)
    handler = make_handler(session, web_dir=resolve_web_dir())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        yield session, base, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_resolve_web_dir_has_review_html():
    web = resolve_web_dir()
    assert (web / "review.html").is_file()


def test_api_review_list_no_explanations(session_and_server):
    _session, base, _calls = session_and_server
    resp = httpx.get(f"{base}/api/review", timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["log_id"] == "review_mini"
    assert data["diverge_count"] == 2
    assert len(data["diverges"]) == 2
    first = data["diverges"][0]
    assert first["index"] == 1
    assert first["mortal_best"] == "dahai 9p"
    assert first["player_action"] == "dahai 5s"
    assert "statuses" in first
    assert "menzen" in first["statuses"]
    assert isinstance(first["hand"], list) and len(first["hand"]) >= 13
    assert "9p" in first["hand"]
    assert isinstance(first["ukeire_tiles"], list)
    assert isinstance(first.get("ukeire_remaining"), dict)
    assert isinstance(first["calls"], list)
    assert first.get("wait_shape") is not None or first["statuses"].get("wait_shape") is not None
    assert "explanation" not in first
    for d in data["diverges"]:
        assert "explanation" not in d
        assert "hand" in d
        assert "ukeire_tiles" in d
        assert "calls" in d


def test_api_explain_caches_and_pins(session_and_server):
    session, base, calls = session_and_server
    resp1 = httpx.post(f"{base}/api/explain/1", timeout=5.0)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["index"] == 1
    assert data1["source"] == "llm"
    assert data1["explanation"]["pinned_action"] == "dahai 9p"
    assert data1["grounding_errors"] == []
    assert calls["n"] == 1
    assert session._explain_calls == 1

    resp2 = httpx.post(f"{base}/api/explain/1", timeout=5.0)
    assert resp2.status_code == 200
    assert resp2.json() == data1
    assert calls["n"] == 1
    assert session._explain_calls == 1


def test_api_explain_template_mode(session_and_server):
    session, base, calls = session_and_server
    resp = httpx.post(f"{base}/api/explain/1?mode=template", timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "template"
    assert data["explanation"]["pinned_action"] == "dahai 9p"
    assert data["grounding_errors"] == []
    # template path does not use the LLM stub
    assert calls["n"] == 0
    assert session._explain_calls == 0

    resp2 = httpx.post(f"{base}/api/explain/1?mode=template", timeout=5.0)
    assert resp2.json() == data


def test_api_explain_404(session_and_server):
    _session, base, _calls = session_and_server
    resp = httpx.post(f"{base}/api/explain/99", timeout=5.0)
    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]


def test_api_explain_missing_key_503():
    session = ReviewSession.from_path(REPORT)
    handler = make_handler(session, web_dir=resolve_web_dir())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("OPENAI_API_KEY", raising=False)
            mp.delenv("SENSEI_API_KEY", raising=False)
            resp = httpx.post(f"{base}/api/explain/1", timeout=5.0)
        assert resp.status_code == 503
        assert "API key" in resp.json()["error"]

        offline = httpx.post(f"{base}/api/explain/1?mode=template", timeout=5.0)
        assert offline.status_code == 200
        assert offline.json()["source"] == "template"
        assert offline.json()["explanation"]["pinned_action"] == "dahai 9p"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_get_index_serves_html(session_and_server):
    _session, base, _calls = session_and_server
    resp = httpx.get(f"{base}/", timeout=5.0)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Shanten Sensei" in resp.text
    assert "Why?" in resp.text
    assert "Offline explanation" in resp.text
