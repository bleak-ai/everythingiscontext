# gcontext

A folder standard that gives an AI agent a memory of your project.
Project knowledge lives in `context/`, organized by one rule: a path is a chain of common denominators.

## Install

```bash
uv tool install gcontext-ai
```

Also works with `pip install gcontext-ai`.

## Get started

```bash
gcontext init
```

This writes `context/` with the standard, the scripts, the git hook, and two Claude Code commands (`/save`, `/check-structure`). It appends two lines to CLAUDE.md so the agent reads project context at session start.

## The three moments

**Save.** When the agent learns a durable fact, it writes it into the file of its subject. Files and folders are created only when the tests in the standard say so. A Stop hook forces a save every five turns so nothing is lost.

**Track.** A statusline command shows how many facts and folders were added since the last structure check, colored green, amber, or red. Add it to your Claude Code statusline:

```bash
uv run --no-project python3 context/system/scripts/track-context-changes.py . --color
```

**Check.** When the count is high, run `/check-structure`. The agent proposes the smallest tree that passes the three tests. You approve, it applies, the counter resets.

## Commands

- `gcontext init [dir]` - write `context/` from the bundled standard.
- `gcontext install <package-folder> [dir]` - install a package into `context/packages/`.
- `gcontext serve [dir]` - start the MCP server.
- `gcontext check [dir]` - run the structure checks.

## Documentation

- [docs/standard.md](docs/standard.md) - the context standard, version 1.0.
- [docs/principles.md](docs/principles.md) - what gcontext is and why.
- [docs/cli.md](docs/cli.md) - commands, arguments, exit codes.
- [docs/mcp.md](docs/mcp.md) - how the MCP server works.

## License

MIT
