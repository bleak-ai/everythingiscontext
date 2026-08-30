# gcontext

gcontext is a standard for a `context/` folder in your repo, plus a small CLI. The standard keeps project knowledge in typed files with automated checks. The CLI installs reusable packages.

## Install

```bash
uv tool install gcontext-ai
```

## CLI commands

- `gcontext install <package>` installs a reusable package into `context/packages/`.
- `gcontext serve [project]` starts the optional MCP server for a project.
- `gcontext check [project]` checks the project's `context/` folder.

## The context standard

The standard defines the structure and rules for a `context/` folder. Read `context/_system/act.system.md` in an installed project for the full standard.

## Zero-install use

Copy `_system/` into your repo's `context/` folder. You do not need the CLI.
