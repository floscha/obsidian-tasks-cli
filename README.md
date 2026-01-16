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

### Output format

The default (human) output prints **one task per line**:

- no filename
- no line number
- everything before the first `[` is stripped
	- `- [ ] foo` prints as `[ ] foo`

### Configure via `.env`

This repo includes a `.env` file (loaded automatically when running the CLI from the repo).

Set:

- `OT_VAULT_PATH` — path to your Obsidian vault
- `OT_INBOX_NOTE` — folder or note name inside the vault (default: `Inbox`)

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
