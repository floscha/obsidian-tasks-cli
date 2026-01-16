from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Task:
    file: Path
    line_no: int
    raw: str

    @property
    def text(self) -> str:
        return self.raw.strip()


def is_markdown_task_line(line: str) -> bool:
    """Return True if a line looks like an Obsidian/Markdown task.

    We treat common formats as tasks:
    - "- [ ] something"
    - "- [x] done"
    - "* [ ] something"

    Notes:
    - Leading whitespace is allowed.
    - Checkbox char can be space or any single char.
    """

    s = line.lstrip()
    if not (s.startswith("- [") or s.startswith("* [")):
        return False
    # minimal structure: "- [ ]"
    if len(s) < 6:
        return False
    return s[0] in {"-", "*"} and s[1:3] == " [" and s[4] == "]"


def iter_markdown_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix.lower() == ".md":
        yield root
        return

    if not root.exists():
        return

    if root.is_dir():
        yield from (p for p in sorted(root.rglob("*.md")) if p.is_file())


def extract_tasks_from_file(path: Path) -> list[Task]:
    tasks: list[Task] = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # fall back to a forgiving read
        content = path.read_text(encoding="utf-8", errors="replace")

    for idx, line in enumerate(content.splitlines(), start=1):
        if is_markdown_task_line(line):
            tasks.append(Task(file=path, line_no=idx, raw=line.rstrip("\n")))
    return tasks


def extract_tasks(root: Path) -> list[Task]:
    all_tasks: list[Task] = []
    for md in iter_markdown_files(root):
        all_tasks.extend(extract_tasks_from_file(md))
    return all_tasks


def resolve_calendar_daily_note_path(
    *,
    vault_path: str | Path | None = None,
    calendar_dir: str | None = None,
    for_date: date | None = None,
) -> Path:
    """Resolve the daily note path in the configured Calendar directory.

    Daily note format: yyyy-mm-dd.md
    Calendar directory is expected to be inside the vault.

    Configuration:
    - vault_path: defaults to OT_VAULT_PATH environment variable
    - calendar_dir: defaults to OT_CALENDAR_DIR environment variable, or the vault root
    - for_date: defaults to today
    """

    vault = Path(vault_path or os.environ["OT_VAULT_PATH"]).expanduser()
    cal = calendar_dir or os.environ.get("OT_CALENDAR_DIR", "")
    d = for_date or date.today()
    filename = f"{d:%Y-%m-%d}.md"
    return vault / cal / filename


def extract_tasks_from_today_note(
    *,
    vault_path: str | Path | None = None,
    calendar_dir: str | None = None,
    for_date: date | None = None,
) -> list[Task]:
    """Extract tasks from the daily note for the given date.

    Returns an empty list if the note does not exist.
    """

    note = resolve_calendar_daily_note_path(
        vault_path=vault_path, calendar_dir=calendar_dir, for_date=for_date
    )
    if not note.exists() or not note.is_file():
        return []
    return extract_tasks_from_file(note)
