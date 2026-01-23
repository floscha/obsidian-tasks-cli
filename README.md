# Obsidian Tasks CLI

A CLI to manage tasks in your Obsidian vault.

## Install (editable)

This project is intended to be used with **uv**.

Create the environment and install dependencies:

```bash
uv sync --group dev
```

Run the CLI via uv:

```bash
uv run ot inbox
```

If you want a globally available `ot` command on your machine, you can additionally:

```bash
uv tool install -e .
```

Note: `.env` loading is intended for running from this repo (via `uv run ...`). If you install
`ot` globally, configure `OT_VAULT_PATH` / `OT_INBOX_NOTE` (or `OT_INBOX_PATH`) in your shell
environment instead.

## Usage

List tasks from the default inbox path:

```bash
uv run ot inbox
```

List tasks from today’s daily note (and tasks in the vault that backlink to it via `[[yyyy-mm-dd]]`):

```bash
uv run ot today
```

List **all** tasks across the whole vault:

```bash
uv run ot all
```

List overdue tasks (past daily notes + backlink-to-past-date):

```bash
uv run ot overdue
```

List tasks in a specific note by name (searches for `<name>.md` anywhere in the vault):

```bash
uv run ot note "My Project"
```

Add a task to a note (prints the written note path):

```bash
uv run ot add "buy milk" --note "Inbox"
```

JSON output:

```bash
uv run ot all --json
```

### Filtering

Filter by status (you can pass multiple, comma-separated):

```bash
uv run ot all --status open
uv run ot all --status "done,cancelled"
```

Only include “priority” tasks (strict marker: a literal ` ! ` right after the checkbox token):

```bash
uv run ot all --priority-only
```

Enable ANSI colors for checkbox tokens:

```bash
uv run ot inbox --color
```

### Output format

The default (human) output prints **one task per line**:

- no filename
- no line number
- everything before the first `[` is stripped
	- `- [ ] foo` prints as `[ ] foo`

### Configure via `.env`

When running the CLI from this repo, a local `.env` file is loaded automatically.

Set:

- `OT_VAULT_PATH` — path to your Obsidian vault
- `OT_INBOX_NOTE` — folder or note name inside the vault (default: `Inbox`)
- `OT_CALENDAR_DIR` — folder (inside the vault) that contains daily notes (defaults to the vault root)
- `OT_DEFAULT_ADD_NOTE` — default note name for `ot add` if `--note` is omitted
- `OT_USE_COLORS` — set to a truthy value (`1`, `true`, `yes`, `on`) to enable colors by default

Example:

```bash
OT_VAULT_PATH="/Users/florianfnschaefer/Library/Mobile Documents/iCloud~md~obsidian/Documents/Neo25"
OT_INBOX_NOTE="0_Inbox"  # or "Inbox"
```

Override the inbox path:

```bash
uv run ot inbox --path /path/to/folder-or-file
```

Or via env var:

```bash
export OT_INBOX_PATH="/path/to/folder-or-file"
uv run ot inbox
```

Precedence:

1. `--path`
2. `OT_INBOX_PATH`
3. `OT_VAULT_PATH` + `OT_INBOX_NOTE`

JSON output:

```bash
uv run ot inbox --json
```

JSON is a list of objects like:

- `file`: absolute path to the markdown file
- `line_number`: 1-based line number within that file
- `text`: normalized task text, starting at the first `[` (e.g. `[ ] something`)

## Tests

```bash
uv run pytest
```

## What counts as a task?

Currently, any line that starts with one of:

- `- [ ]`
- `- [x]` (or any other single char inside the brackets)
- `* [ ]`

Leading whitespace is allowed.
