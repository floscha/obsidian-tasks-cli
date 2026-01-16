from __future__ import annotations

from dataclasses import dataclass
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
