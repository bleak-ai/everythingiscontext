# CLI reference

gcontext has four commands: `init`, `install`, `serve`, and `check`.

## gcontext init [dir]

Writes `context/` from the standard bundled in the package. The optional `dir` argument sets the project root (defaults to the current directory).

Files written:

- `context/index.md`
- `context/project/index.md`
- `context/journal/index.md`
- `context/system/index.md`
- `context/system/rules.md`
- `context/system/log.md`
- `context/system/scripts/sync-index-files.py`
- `context/system/scripts/rules_config.py`
- `context/system/scripts/track-context-changes.py`
- `context/system/scripts/journal-every-n-turns.py`
- `context/system/scripts/journal-review.py`
- `context/system/scripts/githooks/pre-commit`
- `.claude/commands/save.md`
- `.claude/commands/check-structure.md`
- `.claude/commands/add-to-context.md`

The command never overwrites an existing file. It reports each file as `wrote` or `kept`.

When the directory is a git repo, it runs `git config core.hooksPath context/system/scripts/githooks` and marks `pre-commit` executable.

It appends two lines to `CLAUDE.md` (creates the file when missing):

```
Read context/project/index.md at the start of every session.
Follow context/system/rules.md for saves and structure changes.
```

It merges a Stop hook entry into `.claude/settings.json`. It creates
the file when it is missing. It keeps other hooks. The hook runs
`journal-every-n-turns.py` after every assistant turn. It changes the
old hook command to the new name.

It prints instructions for the statusline setup (see below), then runs `gcontext check`.

Exit codes: 0 on success, 1 on error.

## gcontext install \<package-folder\> [dir]

Installs a package folder into `context/packages/`. The first argument is the path to the package folder. The optional `dir` argument sets the project root.

Exit codes: 0 on success, 1 on error.

## gcontext serve [dir]

Starts the MCP server for the project. The optional `dir` argument sets the project root.

The server exposes seven tools (`read_file`, `write_file`, `list_dir`, `grep`, `run_script`, `run_adhoc_script`, `agent`), resources for every state file at `gcontext://<path>`, and prompts as slash commands. See [mcp.md](mcp.md) and [tools.md](tools.md) for details.

Exit codes: 0 on clean shutdown, 1 on error.

## gcontext check [dir]

Runs `context/system/scripts/sync-index-files.py --check` in the project directory. The optional `dir` argument sets the project root.

Checks: every folder has an index.md, names are lowercase, every file has a purpose line, index entries match what is on disk, no TODO(describe) placeholders, no broken pointer targets.

Exit codes: 0 when all checks pass, 1 when any check fails.

## Statusline

The tracker script shows growth since the last structure check as one colored line. Add it to your Claude Code statusline command:

```bash
uv run --no-project python3 context/system/scripts/track-context-changes.py . --color
```

Example output:

```
context: +4 facts, +0 folders since the structure check (2026-09-06), structure ok
```

Thresholds: green when under 10 facts and 3 folders, amber when under 20 facts and 5 folders, red above that.

## Git hook

`gcontext init` sets `core.hooksPath` to `context/system/scripts/githooks`. The bundled `pre-commit` hook runs `sync-index-files.py --check` and blocks the commit when the structure is broken.

## Journal hook

A Claude Code Stop hook (`journal-every-n-turns.py`) requests a journal
entry every ten assistant turns. On every tenth turn, the hook returns
a block decision. The decision tells the agent to append durable facts
to one session file under `context/journal/`. The agent uses one Write
or Edit call. It gives no report. It does not sync indexes. When
`stop_hook_active` is true, the hook does not block. It cannot trigger
itself.

The interval defaults to 10. Set the `GCONTEXT_SAVE_EVERY` environment variable to override it.

`gcontext init` registers the hook in `.claude/settings.json` automatically.
