from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

from obsidian_tasks import tasks as tasks_mod
from obsidian_tasks.env import load_dotenv_if_present

ANSI_RED = "\x1b[31m"
ANSI_GREEN = "\x1b[32m"
ANSI_GREY = "\x1b[90m"
ANSI_RESET = "\x1b[0m"


_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _strip_wikilinks(text: str) -> str:
    """Remove Obsidian wiki links from text.

    Example: "Do thing for [[2026-01-17]]" -> "Do thing for"
    """

    # Remove the whole wikilink token, then normalize whitespace.
    without = _WIKILINK_RE.sub("", text)
    return " ".join(without.split())


def colorize_checkbox_prefix(text: str) -> str:
    """Colorize the leading checkbox token in a normalized task string.

    Expects the string to start with a checkbox token like "[ ]" / "[x]" / "[-]".
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

    return text


def resolve_inbox_path() -> Path:
    """Resolve inbox path from env (.env)."""

    vault = os.environ["OT_VAULT_PATH"]
    inbox_note = os.environ.get("OT_INBOX_NOTE", "Inbox")
    return Path(vault).expanduser() / inbox_note


def _cmd_inbox(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()

    tasks = tasks_mod.extract_tasks(root)

    def display_text(raw: str) -> str:
        # Omit everything before the first '[' (e.g. '- ' or '* '), keep the checkbox.
        s = raw.lstrip()
        i = s.find("[")
        return s[i:].strip() if i != -1 else s.strip()

    if args.json:
        import json

        payload = [{"file": str(t.file), "text": display_text(t.raw)} for t in tasks]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    # Human output: one task per line
    for t in tasks:
        text = display_text(t.raw)
        if args.color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def _cmd_today(args: argparse.Namespace) -> int:
    # Today's note tasks + backlink tasks across the vault that reference today's note.
    vault_root = os.environ.get("OT_VAULT_PATH")
    calendar_dir = os.environ.get("OT_CALENDAR_DIR")

    today = date.today()

    note_path = tasks_mod.resolve_calendar_daily_note_path(
        vault_path=vault_root, calendar_dir=calendar_dir, for_date=today
    )

    tasks = tasks_mod.extract_tasks_from_today_note(
        vault_path=vault_root, calendar_dir=calendar_dir, for_date=today
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

    def display_text(raw: str) -> str:
        # Omit everything before the first '[' (e.g. '- ' or '* '), keep the checkbox.
        s = raw.lstrip()
        i = s.find("[")
        shown = s[i:].strip() if i != -1 else s.strip()
        return _strip_wikilinks(shown)

    if args.json:
        import json

        payload = [{"file": str(t.file), "text": display_text(t.raw)} for t in tasks]
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if not tasks:
        return 0

    for t in tasks:
        text = display_text(t.raw)
        if args.color:
            text = colorize_checkbox_prefix(text)
        sys.stdout.write(f"{text}\n")

    return 0


def build_parser() -> argparse.ArgumentParser:
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
    inbox.set_defaults(func=_cmd_inbox)

    today = sub.add_parser(
        "today",
        help="List Markdown tasks in today's daily note (Calendar folder, yyyy-mm-dd.md)",
    )
    today.add_argument("--json", action="store_true", help="Output JSON")
    today.add_argument("--color", "-c", action="store_true", help="Colorize checkbox")
    today.set_defaults(func=_cmd_today)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
