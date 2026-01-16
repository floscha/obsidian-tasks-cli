from __future__ import annotations

from pathlib import Path


def load_dotenv_if_present(dotenv_path: Path | None = None) -> None:
    """Best-effort loader for a local .env file.

    We intentionally avoid external dependencies (like python-dotenv).
    Only supports simple KEY=VALUE lines; ignores comments and blank lines.

    Values are only set if the variable is not already present in the process
    environment.
    """

    import os

    p = dotenv_path or (Path.cwd() / ".env")
    if not p.exists() or not p.is_file():
        return

    for raw_line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ.setdefault(key, value)
