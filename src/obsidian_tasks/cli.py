from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from obsidian_tasks import tasks as tasks_mod
from obsidian_tasks.env import load_dotenv_if_present

ANSI_RED = "\x1b[31m"
ANSI_GREEN = "\x1b[32m"
ANSI_GREY = "\x1b[90m"
ANSI_RESET = "\x1b[0m"


_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _parse_statuses(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def _env_truthy(name: str) -> bool:
    """Interpret an environment variable as a boolean.

    Truthy values: 1, true, yes, on (case-insensitive)
    Falsy values: 0, false, no, off, empty/unset
    """

    v = os.environ.get(name)
    if v is None:
        return False
    v = v.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off", ""}:
        return False
    # Be conservative: unknown values are treated as False.
    return False


def _use_colors_from_env() -> bool:
    # Colors are opt-in only.
    return _env_truthy("OT_USE_COLORS")


def _use_colors(args: argparse.Namespace) -> bool:
    """Decide whether to emit ANSI colors.

    Colors are enabled only when explicitly requested via:
    - the command flag: --color / -c
    - environment variable: OT_USE_COLORS
    """

    return bool(getattr(args, "color", False)) or _use_colors_from_env()


def _strip_wikilinks(text: str) -> str:
    """Remove Obsidian wiki links from text.

    Example: "Do thing for [[2026-01-17]]" -> "Do thing for"
    """

    # Remove the whole wikilink token, then normalize whitespace.
    without = _WIKILINK_RE.sub("", text)
    return " ".join(without.split())


def colorize_checkbox_prefix(text: str) -> str:
    """Colorize the leading checkbox token in a normalized task string.

    Expects the string to start with a checkbox token like "[ ]" / "[x]" / "[-]" / "[>]".
    If the format doesn't match, returns the string unchanged.
    """

    if len(text) < 3 or text[0] != "[" or text[2] != "]":
        return text

    token = text[:3]
    rest = text[3:]

    if token == "[ ]":
        return f"{ANSI_RED}{token}{ANSI_RESET}{rest}"
    if token.lower() == "[x]":
        return f"{ANSI_GREEN}{token}{ANSI_RESET}{rest}"
    if token == "[-]":
        return f"{ANSI_GREY}{token}{ANSI_RESET}{rest}"
    if token == "[>]":
        return f"{ANSI_GREY}{token}{ANSI_RESET}{rest}"

    return text


def resolve_inbox_path() -> Path:
    """Resolve inbox path from env (.env)."""

    vault = os.environ["OT_VAULT_PATH"]
    inbox_note = os.environ.get("OT_INBOX_NOTE", "Inbox")
    return Path(vault).expanduser() / inbox_note


def _cmd_inbox(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()

    tasks = tasks_mod.extract_tasks(root)
    tasks = tasks_mod.filter_tasks_by_statuses(
        tasks, statuses=_parse_statuses(getattr(args, "status", None))
    )
    tasks = tasks_mod.filter_tasks_by_priority(
        tasks, priority_only=bool(getattr(args, "priority_only", False))
    )

    def display_text(raw: str) -> str:
        # Omit everything before the first '[' (e.g. '- ' or '* '), keep the checkbox.
        s = raw.lstrip()
        i = s.find("[")
        return s[i:].strip() if i != -1 else s.strip()

    if args.json:
        import json

        payload = [
            {
                "file": str(t.file),
                "line_number": t.line_no,
                "text": display_text(t.raw),
            }
            for t in tasks
        ]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    use_color = _use_colors(args)

    # Human output: one task per line
    for t in tasks:
        text = display_text(t.raw)
        if use_color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def _cmd_today(args: argparse.Namespace) -> int:
    return _cmd_day_offset(args, offset_days=0)


def _cmd_day_offset(args: argparse.Namespace, *, offset_days: int) -> int:
    """List tasks for a day relative to today.

    Includes:
    - tasks from the day's daily note
    - tasks across the vault that backlink to that note via [[yyyy-mm-dd]]
    """

    vault_root = os.environ.get("OT_VAULT_PATH")
    calendar_dir = os.environ.get("OT_CALENDAR_DIR")

    target = date.today() + timedelta(days=offset_days)

    note_path = tasks_mod.resolve_calendar_daily_note_path(
        vault_path=vault_root, calendar_dir=calendar_dir, for_date=target
    )

    tasks = tasks_mod.extract_tasks_from_today_note(
        vault_path=vault_root, calendar_dir=calendar_dir, for_date=target
    )
    if vault_root:
        tasks.extend(
            tasks_mod.extract_backlinked_tasks(
                vault_root=vault_root,
                note_path=note_path,
                include_note_tasks=False,
            )
        )

    # Deduplicate in case the same task line gets included twice.
    seen: set[tuple[str, int]] = set()
    deduped: list[tasks_mod.Task] = []
    for t in tasks:
        key = (str(t.file), t.line_no)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    tasks = deduped

    tasks = tasks_mod.filter_tasks_by_statuses(
        tasks, statuses=_parse_statuses(getattr(args, "status", None))
    )
    tasks = tasks_mod.filter_tasks_by_priority(
        tasks, priority_only=bool(getattr(args, "priority_only", False))
    )

    def display_text(raw: str) -> str:
        # Omit everything before the first '[' (e.g. '- ' or '* '), keep the checkbox.
        s = raw.lstrip()
        i = s.find("[")
        shown = s[i:].strip() if i != -1 else s.strip()
        return _strip_wikilinks(shown)

    if args.json:
        import json

        payload = [
            {
                "file": str(t.file),
                "line_number": t.line_no,
                "text": display_text(t.raw),
            }
            for t in tasks
        ]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    use_color = _use_colors(args)

    for t in tasks:
        text = display_text(t.raw)
        if use_color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def _cmd_yesterday(args: argparse.Namespace) -> int:
    return _cmd_day_offset(args, offset_days=-1)


def _cmd_tomorrow(args: argparse.Namespace) -> int:
    return _cmd_day_offset(args, offset_days=1)


def _cmd_all(args: argparse.Namespace) -> int:
    """List all Markdown tasks across the vault."""

    vault_root = os.environ.get("OT_VAULT_PATH")
    if not vault_root:
        raise KeyError(
            "OT_VAULT_PATH is required for the 'all' command (set it in your environment or .env)"
        )

    tasks = tasks_mod.extract_tasks(Path(vault_root).expanduser())
    tasks = tasks_mod.filter_tasks_by_statuses(
        tasks, statuses=_parse_statuses(getattr(args, "status", None))
    )
    tasks = tasks_mod.filter_tasks_by_priority(
        tasks, priority_only=bool(getattr(args, "priority_only", False))
    )

    def display_text(raw: str) -> str:
        # Omit everything before the first '[' (e.g. '- ' or '* '), keep the checkbox.
        s = raw.lstrip()
        i = s.find("[")
        shown = s[i:].strip() if i != -1 else s.strip()
        return _strip_wikilinks(shown)

    if args.json:
        import json

        payload = [
            {
                "file": str(t.file),
                "line_number": t.line_no,
                "text": display_text(t.raw),
            }
            for t in tasks
        ]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    use_color = _use_colors(args)

    for t in tasks:
        text = display_text(t.raw)
        if use_color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def _cmd_overdue(args: argparse.Namespace) -> int:
    """List tasks that are overdue.

    Overdue tasks are:
    - tasks found in any past daily note (yyyy-mm-dd.md with date < today)
    - tasks anywhere in the vault that contain a backlink [[yyyy-mm-dd]] to a past date
    """

    vault_root = os.environ.get("OT_VAULT_PATH")
    if not vault_root:
        raise KeyError(
            "OT_VAULT_PATH is required for the 'overdue' command "
            "(set it in your environment or .env)"
        )

    calendar_dir = os.environ.get("OT_CALENDAR_DIR")

    tasks = tasks_mod.extract_overdue_tasks(
        vault_root=vault_root,
        calendar_dir=calendar_dir,
        today=date.today(),
    )

    # Overdue is primarily meant for actionable items: default to open tasks.
    raw_statuses = getattr(args, "status", None)
    statuses = _parse_statuses(raw_statuses) if raw_statuses is not None else ["open"]
    tasks = tasks_mod.filter_tasks_by_statuses(
        tasks, statuses=statuses
    )
    tasks = tasks_mod.filter_tasks_by_priority(
        tasks, priority_only=bool(getattr(args, "priority_only", False))
    )

    # Keep output stable-ish: sort by file path then line.
    tasks = sorted(tasks, key=lambda t: (str(t.file), t.line_no))

    def display_text(raw: str) -> str:
        s = raw.lstrip()
        i = s.find("[")
        shown = s[i:].strip() if i != -1 else s.strip()
        return _strip_wikilinks(shown)

    if args.json:
        import json

        payload = [
            {
                "file": str(t.file),
                "line_number": t.line_no,
                "text": display_text(t.raw),
            }
            for t in tasks
        ]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    use_color = _use_colors(args)
    for t in tasks:
        text = display_text(t.raw)
        if use_color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def _cmd_note(args: argparse.Namespace) -> int:
    """List tasks contained in a specific note looked up by filename stem."""

    vault_root = os.environ.get("OT_VAULT_PATH")
    if not vault_root:
        raise KeyError(
            "OT_VAULT_PATH is required for the 'note' command (set it in your environment or .env)"
        )

    note_name = str(getattr(args, "name", "")).strip()
    if not note_name:
        sys.stderr.write("note name is required\n")
        return 2

    matches = tasks_mod.find_notes_by_name(vault_root=vault_root, note_name=note_name)
    if not matches:
        sys.stderr.write(f"no note found named '{note_name}.md' in vault\n")
        return 2

    tasks: list[tasks_mod.Task] = []
    for p in matches:
        tasks.extend(tasks_mod.extract_tasks_from_file(p))

    tasks = tasks_mod.filter_tasks_by_statuses(
        tasks, statuses=_parse_statuses(getattr(args, "status", None))
    )
    tasks = tasks_mod.filter_tasks_by_priority(
        tasks, priority_only=bool(getattr(args, "priority_only", False))
    )

    def display_text(raw: str) -> str:
        s = raw.lstrip()
        i = s.find("[")
        shown = s[i:].strip() if i != -1 else s.strip()
        return _strip_wikilinks(shown)

    if args.json:
        import json

        payload = [
            {
                "file": str(t.file),
                "line_number": t.line_no,
                "text": display_text(t.raw),
            }
            for t in tasks
        ]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    use_color = _use_colors(args)
    for t in tasks:
        text = display_text(t.raw)
        if use_color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    """Append a task to a chosen note."""

    vault_root = os.environ.get("OT_VAULT_PATH")
    if not vault_root:
        raise KeyError(
            "OT_VAULT_PATH is required for the 'add' command (set it in your environment or .env)"
        )

    text = str(getattr(args, "text", "")).strip()
    if not text:
        sys.stderr.write("task text is required\n")
        return 2

    note_name = getattr(args, "note", None) or os.environ.get("OT_DEFAULT_ADD_NOTE")
    note_name = str(note_name or "").strip()
    if not note_name:
        sys.stderr.write(
            "note name is required (use --note or set OT_DEFAULT_ADD_NOTE)\n"
        )
        return 2

    try:
        note_path = tasks_mod.append_task_to_note(
            vault_root=vault_root,
            note_name=note_name,
            text=text,
        )
    except ValueError as e:
        sys.stderr.write(f"{e}\n")
        return 2

    # Keep output minimal and script-friendly.
    sys.stdout.write(f"{note_path}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    # During test runs, avoid pulling local developer defaults from a repo .env.
    # Tests should control env vars explicitly via monkeypatch.
    if os.environ.get("OT_DISABLE_DOTENV") not in {"1", "true", "yes", "on"}:
        load_dotenv_if_present()
    parser = argparse.ArgumentParser(prog="ot", description="Obsidian tasks CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    inbox = sub.add_parser("inbox", help="List Markdown tasks in the inbox folder")
    inbox.add_argument(
        "--path",
        default=os.environ.get("OT_INBOX_PATH", str(resolve_inbox_path())),
        help=(
            "Inbox folder/file (default: OT_INBOX_PATH env var, or OT_VAULT_PATH/OT_INBOX_NOTE, "
            "or built-in path)"
        ),
    )
    inbox.add_argument("--json", action="store_true", help="Output JSON")
    inbox.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    inbox.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    inbox.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    inbox.set_defaults(func=_cmd_inbox)

    today = sub.add_parser(
        "today",
        help="List Markdown tasks in today's daily note (Calendar folder, yyyy-mm-dd.md)",
    )
    today.add_argument("--json", action="store_true", help="Output JSON")
    today.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    today.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    today.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    today.set_defaults(func=_cmd_today)

    yesterday = sub.add_parser(
        "yesterday",
        help="List Markdown tasks in yesterday's daily note (Calendar folder, yyyy-mm-dd.md)",
    )
    yesterday.add_argument("--json", action="store_true", help="Output JSON")
    yesterday.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    yesterday.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    yesterday.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    yesterday.set_defaults(func=_cmd_yesterday)

    tomorrow = sub.add_parser(
        "tomorrow",
        help="List Markdown tasks in tomorrow's daily note (Calendar folder, yyyy-mm-dd.md)",
    )
    tomorrow.add_argument("--json", action="store_true", help="Output JSON")
    tomorrow.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    tomorrow.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    tomorrow.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    tomorrow.set_defaults(func=_cmd_tomorrow)

    all_cmd = sub.add_parser(
        "all",
        help="List Markdown tasks across the whole vault (all notes)",
    )
    all_cmd.add_argument("--json", action="store_true", help="Output JSON")
    all_cmd.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    all_cmd.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    all_cmd.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    all_cmd.set_defaults(func=_cmd_all)

    overdue = sub.add_parser(
        "overdue",
        help=(
            "List overdue tasks: tasks in any past daily note and tasks with a "
            "[[yyyy-mm-dd]] backlink to a past date"
        ),
    )
    overdue.add_argument("--json", action="store_true", help="Output JSON")
    overdue.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    overdue.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    overdue.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    overdue.set_defaults(func=_cmd_overdue)

    note = sub.add_parser(
        "note",
        help=(
            "List Markdown tasks in a note by name (searches vault for <name>.md and prints tasks)"
        ),
    )
    note.add_argument(
        "name",
        help="Note name (filename without .md extension).",
    )
    note.add_argument("--json", action="store_true", help="Output JSON")
    note.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    note.add_argument(
        "--status",
        help=(
            'Filter tasks by status: "open" (- [ ]), "done" (- [x]), "cancelled" (- [-]), '
            '"scheduled" (- [>]). '
            'You can pass multiple, comma-separated (e.g. "done,cancelled").'
        ),
    )
    note.add_argument(
        "--priority-only",
        action="store_true",
        help=(
            'Only include tasks with a " ! " immediately after the checkbox token '
            '(e.g. "- [ ] ! foo")'
        ),
    )
    note.set_defaults(func=_cmd_note)

    add = sub.add_parser(
        "add",
        help="Add a task line to a note",
    )
    add.add_argument(
        "text",
        help='Task text. If it is not already a markdown task, it will be prefixed with "- [ ] ".',
    )
    add.add_argument(
        "--note",
        help=(
            "Target note name (filename without .md). If omitted, uses "
            "OT_DEFAULT_ADD_NOTE env var. "
            "The note is searched anywhere in the vault; if not found, a new note is created "
            "at the vault root."
        ),
    )
    add.set_defaults(func=_cmd_add)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
