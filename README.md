# gcontext

gcontext is a standard for a `context/` folder in your repo, plus a small CLI. The standard keeps project knowledge in typed files with automated checks. The CLI installs reusable packages.

## Install

```bash
uv tool install gcontext-ai
```

## CLI commands

- `gcontext install <package>` installs a reusable package into `context/packages/`.
- `gcontext serve [project]` (alias `up`) starts the MCP server for a project.
- `gcontext check [project]` runs the context/ standard checks.
- `gcontext status [project]` shows server and project status.
- `gcontext reload [project]` applies file changes to the running server.
- `gcontext statusline [project]` prints a one-line server state for status display.

## The context standard

The standard defines the structure and rules for a `context/` folder. Read `context/_system/act.system.md` in an installed project for the full standard.

## Zero-install use

Copy `_system/` into your repo's `context/` folder. You do not need the CLI.
