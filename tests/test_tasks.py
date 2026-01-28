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
    append_task_to_note,
    contains_calendar_backlink,
    extract_backlinked_tasks,
    extract_overdue_tasks,
    extract_tasks_from_file,
    extract_tasks_from_today_note,
    filter_tasks_by_priority,
    filter_tasks_by_status,
    filter_tasks_by_statuses,
    filter_tasks_unscheduled,
    is_calendar_note_path,
    is_markdown_task_line,
    is_priority_task_line,
    resolve_calendar_daily_note_path,
    task_status_from_line,
)


def _run_cli(monkeypatch, argv: list[str], *, disable_dotenv: bool = True) -> int:
    """Run the CLI in tests with deterministic environment handling.

    By default we disable dotenv loading so the developer's repo `.env` doesn't
    affect test results.
    """

    if disable_dotenv:
        monkeypatch.setenv("OT_DISABLE_DOTENV", "1")
    else:
        monkeypatch.delenv("OT_DISABLE_DOTENV", raising=False)

    # Color behavior is controlled explicitly inside each test via OT_USE_COLORS
    # or the -c/--color flag.
    return main(argv)


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


def test_task_status_from_line() -> None:
    assert task_status_from_line("- [ ] open") == "open"
    assert task_status_from_line("- [x] done") == "done"
    assert task_status_from_line("- [X] done") == "done"
    assert task_status_from_line("- [-] cancelled") == "cancelled"
    assert task_status_from_line("- [>] scheduled") == "scheduled"

    # Not a task line
    assert task_status_from_line("hello") is None
    # Unrecognized checkbox token
    assert task_status_from_line("- [?] maybe") is None


def test_is_priority_task_line_strict_marker() -> None:
    assert is_priority_task_line("- [ ] ! important")
    assert is_priority_task_line("    - [x] ! done but important")

    # Strict: must be space + exclamation + space directly after ']'
    assert not is_priority_task_line("- [ ]! no-space")
    assert not is_priority_task_line("- [ ] !! double")
    assert not is_priority_task_line("- [ ]  ! two-spaces-before")
    assert not is_priority_task_line("- [ ] !")

    # Not a task
    assert not is_priority_task_line("hello !")


def test_filter_tasks_by_priority(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        """- [ ] ! one
- [ ] two
- [x] ! three
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(f)
    kept = filter_tasks_by_priority(tasks, priority_only=True)
    assert [t.text for t in kept] == ["- [ ] ! one", "- [x] ! three"]


def test_filter_tasks_by_status(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        """- [ ] one
- [x] two
- [-] three
 - [>] four
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(f)
    assert [t.text for t in filter_tasks_by_status(tasks, status=None)] == [
        "- [ ] one",
        "- [x] two",
        "- [-] three",
        "- [>] four",
    ]
    assert [t.text for t in filter_tasks_by_status(tasks, status="open")] == [
        "- [ ] one"
    ]
    assert [t.text for t in filter_tasks_by_status(tasks, status="done")] == [
        "- [x] two"
    ]
    assert [t.text for t in filter_tasks_by_status(tasks, status="cancelled")] == [
        "- [-] three"
    ]
    assert [t.text for t in filter_tasks_by_status(tasks, status="scheduled")] == [
        "- [>] four"
    ]


def test_filter_tasks_by_statuses_multiple(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        """- [ ] one
- [x] two
- [-] three
 - [>] four
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(f)
    kept = filter_tasks_by_statuses(tasks, statuses=["done", "cancelled", "scheduled"])
    assert [t.text for t in kept] == ["- [x] two", "- [-] three", "- [>] four"]


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


def test_is_calendar_note_path_year_and_daily() -> None:
    assert is_calendar_note_path(Path("/vault/2025.md"))
    assert is_calendar_note_path(Path("/vault/2025-01-01.md"))
    assert not is_calendar_note_path(Path("/vault/Project 2025.md"))
    assert not is_calendar_note_path(Path("/vault/notes.md"))


def test_contains_calendar_backlink_year_and_daily() -> None:
    assert contains_calendar_backlink("- [ ] do thing [[2025]]")
    assert contains_calendar_backlink("- [ ] do thing [[2025-01-01]]")
    assert not contains_calendar_backlink("- [ ] do thing [[Project 2025]]")
    assert not contains_calendar_backlink("- [ ] do thing [[2025-1-1]]")


def test_filter_tasks_unscheduled_filters_calendar_and_backlink(tmp_path: Path) -> None:
    (tmp_path / "2025-01-01.md").write_text("- [ ] in daily\n", encoding="utf-8")
    (tmp_path / "note.md").write_text(
        """- [ ] linked [[2025-01-01]]
- [ ] just a task
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(tmp_path / "2025-01-01.md") + extract_tasks_from_file(
        tmp_path / "note.md"
    )
    kept = filter_tasks_unscheduled(tasks, unscheduled_only=True)
    assert [t.text for t in kept] == ["- [ ] just a task"]


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


def test_append_task_to_note_creates_note_and_normalizes(tmp_path: Path) -> None:
    note_path = append_task_to_note(vault_root=tmp_path, note_name="Inbox", text="hello")
    assert note_path == tmp_path / "Inbox.md"
    assert note_path.read_text(encoding="utf-8") == "- [ ] hello\n"


def test_append_task_to_note_preserves_existing_and_appends_newline(tmp_path: Path) -> None:
    f = tmp_path / "Inbox.md"
    f.write_text("# Inbox", encoding="utf-8")  # no trailing newline

    append_task_to_note(vault_root=tmp_path, note_name="Inbox", text="- [ ] second")
    assert f.read_text(encoding="utf-8") == "# Inbox\n- [ ] second\n"


def test_cli_add_uses_default_add_note_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_DEFAULT_ADD_NOTE", "Inbox")

    code = _run_cli(monkeypatch, ["add", "hello from cli"])
    assert code == 0
    assert (tmp_path / "Inbox.md").read_text(encoding="utf-8") == "- [ ] hello from cli\n"


def test_cli_all_path_single_file_limits_scope(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    (tmp_path / "a.md").write_text("- [ ] from a\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("- [ ] from b\n", encoding="utf-8")

    # Only include tasks from a.md
    from io import StringIO

    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = _run_cli(monkeypatch, ["all", "--path", str(tmp_path / "a.md")])
    assert code == 0
    assert buf.getvalue().strip().splitlines() == ["[ ] from a"]


def test_cli_all_path_glob_supports_wildcards(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "one.md").write_text("- [ ] one\n", encoding="utf-8")
    (notes / "two.md").write_text("- [ ] two\n", encoding="utf-8")
    (tmp_path / "other.md").write_text("- [ ] other\n", encoding="utf-8")

    from io import StringIO

    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = _run_cli(monkeypatch, ["all", "--path", str(notes / "*.md")])
    assert code == 0

    out_lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert sorted(out_lines) == ["[ ] one", "[ ] two"]


def test_cli_all_path_multiple_values_union(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    (tmp_path / "a.md").write_text("- [ ] a\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("- [ ] b\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("- [ ] c\n", encoding="utf-8")

    from io import StringIO

    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = _run_cli(
        monkeypatch,
        [
            "all",
            "--path",
            str(tmp_path / "a.md"),
            "--path",
            str(tmp_path / "b.md"),
        ],
    )
    assert code == 0

    out_lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert sorted(out_lines) == ["[ ] a", "[ ] b"]


def test_cli_all_path_relative_is_relative_to_vault_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    # Create a subfolder inside the vault.
    projects = tmp_path / "1_Projects"
    projects.mkdir()
    (projects / "p.md").write_text("- [ ] project task\n", encoding="utf-8")

    # Change CWD to something else to ensure we don't resolve relative to CWD.
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    from io import StringIO

    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)

    code = _run_cli(monkeypatch, ["all", "--path", "1_Projects/p.md"])
    assert code == 0
    assert buf.getvalue().strip().splitlines() == ["[ ] project task"]


def test_cli_all_path_relative_glob_is_relative_to_vault_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    projects = tmp_path / "1_Projects"
    projects.mkdir()
    (projects / "a.md").write_text("- [ ] a\n", encoding="utf-8")
    (projects / "b.md").write_text("- [ ] b\n", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    from io import StringIO

    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)

    code = _run_cli(monkeypatch, ["all", "--path", "1_Projects/*.md"])
    assert code == 0

    out_lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert sorted(out_lines) == ["[ ] a", "[ ] b"]


def test_cli_add_note_flag_overrides_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_DEFAULT_ADD_NOTE", "Inbox")

    code = _run_cli(monkeypatch, ["add", "--note", "Work", "do it"])
    assert code == 0
    assert not (tmp_path / "Inbox.md").exists()
    assert (tmp_path / "Work.md").read_text(encoding="utf-8") == "- [ ] do it\n"


def test_cli_all_priority_only_filters(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    (tmp_path / "a.md").write_text(
        """- [ ] ! prio
- [ ] normal
""",
        encoding="utf-8",
    )

    code = _run_cli(monkeypatch, ["all", "--priority-only"])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["[ ] ! prio"]


def test_cli_all_unscheduled_filters(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    (tmp_path / "2025-01-01.md").write_text("- [ ] in daily\n", encoding="utf-8")
    (tmp_path / "a.md").write_text(
        """- [ ] linked [[2025-01-01]]
- [ ] normal
""",
        encoding="utf-8",
    )

    code = _run_cli(monkeypatch, ["all", "--unscheduled"])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["[ ] normal"]


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
    assert (
        colorize_checkbox_prefix("[>] scheduled")
        == f"{ANSI_GREY}[>]{ANSI_RESET} scheduled"
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
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text("# Today\n\n- [ ] local\n", encoding="utf-8")


def test_cli_note_prints_tasks_from_named_note(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    note = tmp_path / "Project X.md"
    note.write_text(
        """# Project X

- [ ] first
not a task
    - [x] second
""",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["note", "Project X"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.splitlines() == ["[ ] first", "[x] second"]


def test_cli_note_errors_when_note_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))

    rc = _run_cli(monkeypatch, ["note", "Does Not Exist"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no note found" in err


def test_cli_note_aggregates_tasks_when_multiple_notes_match(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    (a_dir / "Shared.md").write_text("- [ ] from a\n", encoding="utf-8")
    (b_dir / "Shared.md").write_text("- [x] from b\n", encoding="utf-8")

    rc = _run_cli(monkeypatch, ["note", "Shared"])
    assert rc == 0
    out = capsys.readouterr().out
    assert sorted(out.splitlines()) == sorted(["[ ] from a", "[x] from b"])


def test_cli_today_status_filter_open(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text(
        """# Today

- [ ] open one
- [x] done one
- [-] cancelled one
""",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["today", "--status", "open"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["[ ] open one"]


def test_cli_today_status_filter_multiple(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text(
        """# Today

- [ ] open one
- [x] done one
- [-] cancelled one
""",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["today", "--status", "done,cancelled"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["[x] done one", "[-] cancelled one"]


def test_cli_yesterday_includes_backlinked_tasks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    yesterday = date.today() - timedelta(days=1)

    note = tmp_path / f"{yesterday:%Y-%m-%d}.md"
    note.write_text("# Yesterday\n\n- [ ] local\n", encoding="utf-8")

    other = tmp_path / "Work.md"
    other.write_text(
        f"- [ ] follow up [[{yesterday:%Y-%m-%d}]]\n",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["yesterday"])
    assert rc == 0

    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(["[ ] local", "[ ] follow up"])


def test_cli_tomorrow_includes_backlinked_tasks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    tomorrow = date.today() + timedelta(days=1)

    note = tmp_path / f"{tomorrow:%Y-%m-%d}.md"
    note.write_text("# Tomorrow\n\n- [ ] local\n", encoding="utf-8")

    other = tmp_path / "Work.md"
    other.write_text(
        f"- [ ] follow up [[{tomorrow:%Y-%m-%d}]]\n",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["tomorrow"])
    assert rc == 0

    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(["[ ] local", "[ ] follow up"])


def test_cli_today_no_color_by_default(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text("# Today\n\n- [ ] local\n", encoding="utf-8")

    rc = _run_cli(monkeypatch, ["today"])
    assert rc == 0

    out = capsys.readouterr().out
    assert out == "[ ] local\n"


def test_cli_today_uses_colors_from_env(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.setenv("OT_USE_COLORS", "1")

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text("# Today\n\n- [ ] local\n", encoding="utf-8")

    rc = _run_cli(monkeypatch, ["today"])
    assert rc == 0

    out = capsys.readouterr().out
    assert out == f"{ANSI_RED}[ ]{ANSI_RESET} local\n"


def test_cli_today_uses_colors_from_ot_env(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.setenv("OT_USE_COLORS", "true")

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text("# Today\n\n- [ ] local\n", encoding="utf-8")

    rc = _run_cli(monkeypatch, ["today"])
    assert rc == 0

    out = capsys.readouterr().out
    assert out == f"{ANSI_RED}[ ]{ANSI_RESET} local\n"


def test_cli_today_uses_colors_from_dotenv(tmp_path: Path, monkeypatch, capsys) -> None:
    # Simulate running from a directory containing a .env file.
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        'OT_VAULT_PATH="{vault}"\nOT_CALENDAR_DIR=""\nOT_USE_COLORS=1\n'.format(
            vault=str(tmp_path)
        ),
        encoding="utf-8",
    )

    today = date.today()
    note = tmp_path / f"{today:%Y-%m-%d}.md"
    note.write_text("# Today\n\n- [ ] local\n", encoding="utf-8")

    rc = _run_cli(monkeypatch, ["today"], disable_dotenv=False)
    assert rc == 0

    out = capsys.readouterr().out
    assert out == f"{ANSI_RED}[ ]{ANSI_RESET} local\n"


def test_cli_all_lists_tasks_across_vault(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    (tmp_path / "A.md").write_text(
        """# A

- [ ] a1
not a task
    - [x] a2
""",
        encoding="utf-8",
    )
    (tmp_path / "B.md").write_text(
        """# B

* [ ] b1 [[Some Note]]
""",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["all"])
    assert rc == 0

    # We don't assert ordering, just presence; wikilinks are stripped.
    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(["[ ] a1", "[x] a2", "[ ] b1"])


def test_cli_all_json_includes_file_text_and_line_number(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import json

    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    (tmp_path / "A.md").write_text("- [ ] a1\n", encoding="utf-8")
    (tmp_path / "B.md").write_text("- [x] b1\n", encoding="utf-8")

    rc = _run_cli(monkeypatch, ["all", "--json"])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert {p["text"] for p in payload} == {"[ ] a1", "[x] b1"}
    assert all("file" in p for p in payload)
    assert all("line_number" in p for p in payload)
    assert {p["line_number"] for p in payload} == {1}


def test_extract_overdue_tasks_includes_past_daily_notes_and_past_backlinks(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Past daily note (overdue)
    (tmp_path / f"{yesterday:%Y-%m-%d}.md").write_text(
        "# Yesterday\n\n- [ ] overdue from daily\n",
        encoding="utf-8",
    )
    # Today's note (not overdue)
    (tmp_path / f"{today:%Y-%m-%d}.md").write_text(
        "# Today\n\n- [ ] today local\n",
        encoding="utf-8",
    )
    # Future note (not overdue)
    (tmp_path / f"{tomorrow:%Y-%m-%d}.md").write_text(
        "# Tomorrow\n\n- [ ] future local\n",
        encoding="utf-8",
    )

    # Backlink in some other note
    (tmp_path / "Work.md").write_text(
        "\n".join(
            [
                f"- [ ] follow up [[{yesterday:%Y-%m-%d}]]",
                f"- [ ] scheduled [[{tomorrow:%Y-%m-%d}]]",
                "- [ ] invalid backlink [[2026-99-99]]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    tasks = extract_overdue_tasks(
        vault_root=tmp_path,
        calendar_dir="",
        today=today,
    )

    texts = sorted(t.text for t in tasks)
    assert "- [ ] overdue from daily" in texts
    assert f"- [ ] follow up [[{yesterday:%Y-%m-%d}]]" in texts

    # Not overdue
    assert "- [ ] today local" not in texts
    assert "- [ ] future local" not in texts
    assert f"- [ ] scheduled [[{tomorrow:%Y-%m-%d}]]" not in texts
    assert "- [ ] invalid backlink [[2026-99-99]]" not in texts


def test_cli_overdue_lists_overdue_tasks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    yesterday = today - timedelta(days=1)

    (tmp_path / f"{yesterday:%Y-%m-%d}.md").write_text(
        "# Yesterday\n\n- [ ] overdue from daily\n- [x] done from daily\n",
        encoding="utf-8",
    )
    (tmp_path / "Work.md").write_text(
        f"- [ ] follow up [[{yesterday:%Y-%m-%d}]]\n",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["overdue"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    # We don't require exact ordering, just presence. Wikilinks are stripped.
    assert "[ ] overdue from daily" in out
    assert "[ ] follow up" in out
    assert "[x] done from daily" not in out


def test_cli_overdue_status_filter_open(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    yesterday = today - timedelta(days=1)

    (tmp_path / f"{yesterday:%Y-%m-%d}.md").write_text(
        "# Yesterday\n\n- [ ] open one\n- [x] done one\n- [-] cancelled one\n",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["overdue", "--status", "open"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["[ ] open one"]


def test_cli_overdue_status_filter_can_include_done(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OT_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OT_CALENDAR_DIR", "")
    monkeypatch.delenv("OT_USE_COLORS", raising=False)

    today = date.today()
    yesterday = today - timedelta(days=1)

    (tmp_path / f"{yesterday:%Y-%m-%d}.md").write_text(
        "# Yesterday\n\n- [ ] open one\n- [x] done one\n",
        encoding="utf-8",
    )

    rc = _run_cli(monkeypatch, ["overdue", "--status", "open,done"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert sorted(out) == sorted(["[ ] open one", "[x] done one"])
