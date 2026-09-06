# Changelog

## 1.0.1 (2026-09-07)

- The bundled /save command follows the 1.0 Save steps instead of v5 wording.
- The bundled pre-commit hook message says how to log a structure change.

## 1.0.0 (2026-09-07)

### Added

- `gcontext init [dir]`: writes `context/` from the standard bundled in the package, sets the git hook, appends to CLAUDE.md, installs the `/save` and `/check-structure` commands.
- The context standard (version 1.0) ships inside the package. No separate copy step needed.
- `gcontext check [dir]`: runs `sync-index-files.py --check` from the installed standard.
- Statusline via `track-context-changes.py`: one colored line showing facts and folders added since the last structure check.
- Forced save via `save-every-n-turns.py` Stop hook: saves context every five turns (overridable with `GCONTEXT_SAVE_EVERY`). `gcontext init` registers the hook in `.claude/settings.json`.

### Changed

- CLI reduced to four commands: `init`, `install`, `serve`, `check`.
- Documentation rewritten for 1.0: new README.md, docs/standard.md, docs/principles.md, docs/cli.md; kept docs cleaned of removed features.

### Removed

- `gcontext status`, `gcontext reload`, `gcontext statusline`, `gcontext up`, `gcontext connect`, `gcontext context` commands.
- Dashboard and all dashboard endpoints.
- controls.yaml and the controls system.

## 0.16.0 (2026-08-30)

### Added

- `gcontext install <package>`: installs a package from the registry into `context/packages/`, adds deps to pyproject.toml, and runs `uv sync`.
- `gcontext check`: runs `context/_system/scripts/check.py --check`.
- `gcontext serve`: serves `context/` as an MCP server with no config file needed.

### Changed

- The CLI is now three commands: install, serve, check.
- The knowledge system is the context standard. gcontext is optional tooling.

### Removed

- Dashboard and all dashboard endpoints.
- controls.yaml and the controls system.
- connection.yaml format (replaced by package.yaml and known files).
- gcontext.yaml config file (serve reads `context/` directly).
- Agent registry website and marketplace API.
- `gcontext init`, `gcontext up`, `gcontext add`, `gcontext reload`, `gcontext share`, `gcontext statusline` commands.

## 0.15.0 (2026-08-24)

### Added

- `gcontext statusline` command: one line for your client statusline. Green "gcontext ok" when current, amber "RECONNECT NEEDED" when the client is behind, "STALE" for hand edits, "down" when the server is not running. `--color` flag for ANSI colors.
- Server self-reload: edits made through the MCP tools apply without running `gcontext reload`.
- `/status` reports `client_behind`: whether the connected client misses commands or an agent.md change, and which.
- Dashboard banner when the client needs a reconnect, with the exact items.
- `.gcontext-port` lockfile so CLI subcommands find the running server's port.

### Changed

- Dashboard copy buttons produce plain `gcontext://path` references.
- Console warnings for hand edits now say "changed outside tools; run gcontext reload".

## 0.14.0 (2026-08-23)

### Changed

- Controls tab redesigned: sticky header with server name and connected status, search with "/" shortcut, All/Listed/Hidden segmented filter, Resources/Commands type chips, Descriptions toggle, collapsible sections with white group cards, List all/Hide all bulk actions, inline copy and rename, fixed pending-changes bar with Discard/Reload, green reloaded toast.
- Commands tab removed (now redundant with Controls).
- Backend adds category field to command rows for grouped display.

### Fixed

- Pin POST validates that the target file exists on disk and rejects path traversal attempts.

## 0.13.1 (2026-08-22)

### Added

- `agents/` folder parity: MCP resource picker, root resource map, ask/explain/setup prompts, context ledger, dashboard, CLI banner, restart notes, and docs now treat `agents/` equal to `connections/` and `modules/`.
- controls.yaml as full on/off registry with one-time migration from the old auto values.
- Controls tab in dashboard: toggle, rename, bulk-toggle, flat layout with reload banner.
- File pinning in dashboard Files tab.
- `gcontext reload` replaces the three-step restart cycle in framework instructions.
- New docs: using.md, mcp.md, tools.md, troubleshooting.md.

### Changed

- `names:` section in controls.yaml renames commands and resource display titles.
- Legacy dual-scan removed: agents scan only `agents/`, no longer fall back to `modules/`.

### Removed

- Auto value in controls.yaml (migrated to explicit on/off).

## 0.13.0 (2026-08-20)

### Added

- controls.yaml: single file to control the MCP surface (replaces commands.yaml).
- `hidden_commands`: hide slash commands by stable key.
- `hidden_resources`: hide modules/connections from the resource picker (fnmatch globs supported).
- `pinned_resources`: surface specific files in the resource picker.

### Fixed

- Manifest loads before framework prompt registration so `hidden_commands` applies to built-in prompts.
