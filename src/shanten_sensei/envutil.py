"""Minimal .env loader (stdlib only — no python-dotenv)."""

from __future__ import annotations

import os
from pathlib import Path


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines; ignore blanks and # comments; strip optional quotes."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def find_dotenv(
    start: Path | None = None,
    *,
    max_parents: int = 6,
) -> Path | None:
    """Return the first .env found from start upward (cwd by default)."""
    cur = (start or Path.cwd()).resolve()
    for _ in range(max_parents + 1):
        candidate = cur / ".env"
        if candidate.is_file():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def load_dotenv(
    path: Path | str | None = None,
    *,
    override: bool = False,
) -> Path | None:
    """
    Load variables from a .env file into os.environ.

    By default does not override keys already set in the process environment.
    Returns the path loaded, or None if no file was found / used.
    """
    env_path = Path(path) if path is not None else find_dotenv()
    if env_path is None or not env_path.is_file():
        return None
    parsed = parse_dotenv(env_path.read_text(encoding="utf-8"))
    for key, value in parsed.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return env_path
