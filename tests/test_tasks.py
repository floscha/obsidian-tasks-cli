from datetime import date, timedelta
from pathlib import Path

from obsidian_tasks.cli import (
    ANSI_GREEN,
    ANSI_GREY,
    ANSI_RED,
    ANSI_RESET,
    colorize_checkbox_prefix,
    main,
)
from obsidian_tasks.tasks import (
    extract_backlinked_tasks,
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


def test_extract_backlinked_tasks_finds_tasks_across_vault(tmp_path: Path) -> None:
    vault = tmp_path

    # The note we are linking to
    note = vault / "Project X.md"
    note.write_text("# Project X\n\n- [ ] local task\n", encoding="utf-8")

    other = vault / "Other.md"
    other.write_text(
        """# Other

- [ ] unrelated
- [ ] mentions [[Project X]]
not a task [[Project X]]
    - [x] indented task with [[Project X]]
""",
        encoding="utf-8",
    )

    nested_dir = vault / "Area"
    nested_dir.mkdir()
    nested = nested_dir / "Nested.md"
    nested.write_text(
        """# Nested

* [ ] bullet mentions [[Project X]]
""",
        encoding="utf-8",
    )

    tasks = extract_backlinked_tasks(vault_root=vault, note_path=note)
    assert sorted(t.text for t in tasks) == sorted(
        [
            "- [ ] mentions [[Project X]]",
            "- [x] indented task with [[Project X]]",
            "* [ ] bullet mentions [[Project X]]",
        ]
    )


def test_extract_backlinked_tasks_can_exclude_note_itself(tmp_path: Path) -> None:
    vault = tmp_path
    note = vault / "Note.md"
    note.write_text(
        """# Note

- [ ] self task mentions [[Note]]
""",
        encoding="utf-8",
    )
    other = vault / "Other.md"
    other.write_text("- [ ] other mentions [[Note]]\n", encoding="utf-8")

    tasks = extract_backlinked_tasks(
        vault_root=vault, note_path=note, include_note_tasks=False
    )
    assert [t.text for t in tasks] == ["- [ ] other mentions [[Note]]"]


def test_cli_today_includes_backlinked_tasks(tmp_path: Path, monkeypatch, capsys) -> None:
    # Arrange a minimal vault + today's note.
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    # Ensure the CLI looks in the vault root for the daily note.
    monkeypatch.setenv("OT_CALENDAR_DIR", "")

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text("# Today\n\n- [ ] local\n", encoding="utf-8")

    other = tmp_path / "Work.md"
    other.write_text(f"- [ ] follow up [[{today:%Y-%m-%d}]]\n", encoding="utf-8")

    # Act
    rc = main(["today"])
    assert rc == 0

    # Assert: output includes both tasks (order doesn't matter)
    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(
        ["[ ] local", "[ ] follow up"]
    )


def test_cli_yesterday_includes_backlinked_tasks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")

    yesterday = date.today() - timedelta(days=1)

    note = tmp_path / f"{yesterday:%Y-%m-%d}.md"
    note.write_text("# Yesterday\n\n- [ ] local\n", encoding="utf-8")

    other = tmp_path / "Work.md"
    other.write_text(
        f"- [ ] follow up [[{yesterday:%Y-%m-%d}]]\n",
        encoding="utf-8",
    )

    rc = main(["yesterday"])
    assert rc == 0

    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(["[ ] local", "[ ] follow up"])


def test_cli_tomorrow_includes_backlinked_tasks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")

    tomorrow = date.today() + timedelta(days=1)

    note = tmp_path / f"{tomorrow:%Y-%m-%d}.md"
    note.write_text("# Tomorrow\n\n- [ ] local\n", encoding="utf-8")

    other = tmp_path / "Work.md"
    other.write_text(
        f"- [ ] follow up [[{tomorrow:%Y-%m-%d}]]\n",
        encoding="utf-8",
    )

    rc = main(["tomorrow"])
    assert rc == 0

    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(["[ ] local", "[ ] follow up"])
