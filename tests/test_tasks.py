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
    filter_tasks_by_status,
    filter_tasks_by_statuses,
    is_markdown_task_line,
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

    # Not a task line
    assert task_status_from_line("hello") is None
    # Unrecognized checkbox token
    assert task_status_from_line("- [?] maybe") is None


def test_filter_tasks_by_status(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        """- [ ] one
- [x] two
- [-] three
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(f)
    assert [t.text for t in filter_tasks_by_status(tasks, status=None)] == [
        "- [ ] one",
        "- [x] two",
        "- [-] three",
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


def test_filter_tasks_by_statuses_multiple(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        """- [ ] one
- [x] two
- [-] three
""",
        encoding="utf-8",
    )

    tasks = extract_tasks_from_file(f)
    kept = filter_tasks_by_statuses(tasks, statuses=["done", "cancelled"])
    assert [t.text for t in kept] == ["- [x] two", "- [-] three"]


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
