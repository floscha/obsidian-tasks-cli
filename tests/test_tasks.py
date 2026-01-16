from datetime import date
from pathlib import Path

from obsidian_tasks.cli import (
    ANSI_GREEN,
    ANSI_GREY,
    ANSI_RED,
    ANSI_RESET,
    colorize_checkbox_prefix,
)
from obsidian_tasks.tasks import (
    extract_tasks_from_file,
    extract_tasks_from_today_note,
    is_markdown_task_line,
    resolve_calendar_daily_note_path,
)


def _display_text(raw: str) -> str:
    s = raw.lstrip()
    i = s.find("[")
    return s[i:].strip() if i != -1 else s.strip()


def test_is_markdown_task_line_variants() -> None:
    assert is_markdown_task_line("- [ ] hello")
    assert is_markdown_task_line("- [x] done")
    assert is_markdown_task_line("* [ ] star")
    assert is_markdown_task_line("    - [ ] indented")

    assert not is_markdown_task_line("- [] nope")
    assert not is_markdown_task_line("[ ] nope")
    assert not is_markdown_task_line("- [ ]")


def test_extract_tasks_from_file(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        """# Title

- [ ] first
not a task
    - [x] second

- [] broken
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(f)
    assert [t.text for t in tasks] == ["- [ ] first", "- [x] second"]
    assert [t.line_no for t in tasks] == [3, 5]


def test_display_text_strips_prefix() -> None:
    assert _display_text("- [ ] hello") == "[ ] hello"
    assert _display_text("    * [x] done") == "[x] done"


def test_resolve_calendar_daily_note_path_default_calendar_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    p = resolve_calendar_daily_note_path(for_date=date(2026, 1, 16))
    assert p == tmp_path / "2026-01-16.md"


def test_resolve_calendar_daily_note_path_custom_calendar_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "Calendar")
    p = resolve_calendar_daily_note_path(for_date=date(2026, 1, 16))
    assert p == tmp_path / "Calendar" / "2026-01-16.md"


def test_extract_tasks_from_today_note_reads_tasks(tmp_path: Path) -> None:
    note = tmp_path / "2026-01-16.md"
    note.write_text(
        """# 2026-01-16

- [ ] task one
not a task
    - [x] task two
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_today_note(
        vault_path=tmp_path, for_date=date(2026, 1, 16)
    )
    assert [t.text for t in tasks] == ["- [ ] task one", "- [x] task two"]


def test_colorize_checkbox_prefix() -> None:
    assert (
        colorize_checkbox_prefix("[ ] hello")
        == f"{ANSI_RED}[ ]{ANSI_RESET} hello"
    )
    assert (
        colorize_checkbox_prefix("[x] done")
        == f"{ANSI_GREEN}[x]{ANSI_RESET} done"
    )
    assert (
        colorize_checkbox_prefix("[X] done")
        == f"{ANSI_GREEN}[X]{ANSI_RESET} done"
    )
    assert (
        colorize_checkbox_prefix("[-] cancelled")
        == f"{ANSI_GREY}[-]{ANSI_RESET} cancelled"
    )

    # Unrecognized token stays unchanged
    assert colorize_checkbox_prefix("[?] maybe") == "[?] maybe"
    # Not a bracket token stays unchanged
    assert colorize_checkbox_prefix("hello") == "hello"
