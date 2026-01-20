from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, TypeAlias

TaskStatus: TypeAlias = str  # Literal would be nicer, but keep deps minimal.


def resolve_note_path(*, vault_root: str | Path, note_name: str) -> Path:
    """Resolve a note path from a note name (filename stem).

    If the note exists somewhere in the vault (any folder), we pick the first
    match in sorted order.

    If it doesn't exist yet, we default to creating it at the vault root as
    `<note_name>.md`.
    """

    vault = Path(vault_root).expanduser()
    wanted = note_name.strip()
    if not wanted:
        raise ValueError("note name is required")

    matches = find_notes_by_name(vault_root=vault, note_name=wanted)
    if matches:
        return matches[0]

    return vault / f"{wanted}.md"


def normalize_task_text(text: str) -> str:
    """Normalize free-form text into a markdown task line.

    Rules:
    - If the user already passed a markdown task line (e.g. "- [ ] ..."), keep it.
    - Otherwise, prefix with "- [ ] ".
    - Strip surrounding whitespace and ensure it's non-empty.
    """

    s = str(text).strip()
    if not s:
        raise ValueError("task text is required")

    if is_markdown_task_line(s):
        return s
    return f"- [ ] {s}"


def append_task_to_note(*, vault_root: str | Path, note_name: str, text: str) -> Path:
    """Append a task line to a note in the vault.

    Creates the note if needed.

    Returns:
        Path to the note written.
    """

    note_path = resolve_note_path(vault_root=vault_root, note_name=note_name)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    task_line = normalize_task_text(text)

    existing = ""
    if note_path.exists():
        try:
            existing = note_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            existing = note_path.read_text(encoding="utf-8", errors="replace")

    # Ensure we always append on a fresh line.
    if existing and not existing.endswith("\n"):
        existing += "\n"

    note_path.write_text(existing + task_line + "\n", encoding="utf-8")
    return note_path


def task_status_from_line(line: str) -> TaskStatus | None:
    """Return the status encoded in a markdown checkbox.

    Recognized:
    - open: "- [ ] ..."
    - done: "- [x] ..." (case-insensitive)
    - cancelled: "- [-] ..."

    Returns None if the line is not a markdown task or if the checkbox token is
    not one of the recognized statuses.
    """

    if not is_markdown_task_line(line):
        return None

    s = line.lstrip()
    token = s[2:5]  # e.g. "[ ]", "[x]", "[-]" (after leading "- ")

    if token == "[ ]":
        return "open"
    if token.lower() == "[x]":
        return "done"
    if token == "[-]":
        return "cancelled"
    return None


def filter_tasks_by_status(tasks: Iterable[Task], *, status: TaskStatus | None) -> list[Task]:
    """Filter tasks by checkbox status.

    If status is None, returns all tasks.
    """

    if status is None:
        return list(tasks)

    return [t for t in tasks if task_status_from_line(t.raw) == status]


def filter_tasks_by_statuses(
    tasks: Iterable[Task], *, statuses: Iterable[TaskStatus] | None
) -> list[Task]:
    """Filter tasks by multiple checkbox statuses.

    If statuses is None, returns all tasks.
    """

    if statuses is None:
        return list(tasks)

    wanted = {s for s in statuses if s}
    if not wanted:
        return []

    return [t for t in tasks if (st := task_status_from_line(t.raw)) is not None and st in wanted]


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


def extract_backlinked_tasks(
    *,
    vault_root: str | Path,
    note_path: str | Path,
    include_note_tasks: bool = True,
) -> list[Task]:
    """Extract tasks that reference a given note via an Obsidian wikilink.

    A backlink task is any markdown task line that contains
    `[[<note_stem>]]`, where `note_stem` is the filename of the note without
    the `.md` extension.

    Args:
        vault_root: The Obsidian vault root directory to search.
        note_path: The note file path (usually inside the vault). Only its stem
            is used for matching.
        include_note_tasks: If False, tasks in `note_path` itself are excluded.

    Returns:
        A list of tasks (deduplicated by file+line).
    """

    vault = Path(vault_root).expanduser()
    note = Path(note_path).expanduser()
    needle = f"[[{note.stem}]]"

    out: list[Task] = []
    seen: set[tuple[Path, int]] = set()

    for md in iter_markdown_files(vault):
        if not include_note_tasks and md.resolve() == note.resolve():
            continue

        try:
            content = md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = md.read_text(encoding="utf-8", errors="replace")

        for idx, line in enumerate(content.splitlines(), start=1):
            if needle not in line:
                continue
            if not is_markdown_task_line(line):
                continue
            key = (md, idx)
            if key in seen:
                continue
            seen.add(key)
            out.append(Task(file=md, line_no=idx, raw=line.rstrip("\n")))

    return out


def find_notes_by_name(*, vault_root: str | Path, note_name: str) -> list[Path]:
    """Find notes named `<note_name>.md` anywhere in the vault.

    Args:
        vault_root: The Obsidian vault root directory to search.
        note_name: Filename stem to search for (without `.md`).

    Returns:
        A list of matching paths (sorted). Empty if none.
    """

    vault = Path(vault_root).expanduser()
    if not vault.exists() or not vault.is_dir():
        return []

    wanted = note_name.strip()
    if not wanted:
        return []

    matches = [p for p in vault.rglob("*.md") if p.is_file() and p.stem == wanted]
    return sorted(matches)


def extract_tasks_from_note_name(*, vault_root: str | Path, note_name: str) -> list[Task]:
    """Extract tasks from notes matching a given note name.

    If multiple notes match (same filename stem in different folders), tasks are
    extracted from all of them.
    """

    out: list[Task] = []
    for p in find_notes_by_name(vault_root=vault_root, note_name=note_name):
        out.extend(extract_tasks_from_file(p))
    return out
