from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from obsidian_tasks.env import load_dotenv_if_present
from obsidian_tasks.tasks import extract_tasks


def resolve_inbox_path() -> Path:
    """Resolve inbox path from env (.env)."""

    vault = os.environ["OT_VAULT_PATH"]
    inbox_note = os.environ.get("OT_INBOX_NOTE", "Inbox")
    return Path(vault).expanduser() / inbox_note


def _cmd_inbox(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()

    tasks = extract_tasks(root)

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
        sys.stdout.write(f"{display_text(t.raw)}\n")

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
    inbox.set_defaults(func=_cmd_inbox)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
