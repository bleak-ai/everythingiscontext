# Everything Is Context

An open-source, agent-agnostic context management system. Create, organize, and load context modules into a workspace that any coding agent can read and operate on.

## Quick start

```bash
# 1. Install dependencies
pip install .

# 2. Initialize the workspace
python eic.py init

# 3. Create a module
python eic.py new integration stripe

# 4. Edit the module files
# Fill in modules-repo/stripe/info.md with your Stripe docs, auth details, operations

# 5. Load it
python eic.py load stripe

# 6. Point your agent at context/
# Open Claude Code, Codex, Cursor, or any coding agent in the context/ directory
```

## How it works

Modules live in `modules-repo/`. Each module is a folder with:
- `module.yaml` — metadata (name, kind, secrets, dependencies)
- `llms.txt` — table of contents the agent reads first
- A starter file (`info.md`, `brief.md`, or `steps.md` depending on kind)

When you load a module, it gets symlinked into `context/` and the workspace files are regenerated:
- `context/system.md` — agent instructions + table of loaded modules
- `context/llms.txt` — index of loaded modules
- `context/structure.md` — module schema reference

The agent reads `system.md` -> `llms.txt` -> follows links into modules.

## Commands

| Command | Description |
|---------|-------------|
| `python eic.py init` | Initialize workspace |
| `python eic.py new <kind> <name>` | Create a module (kind: integration, task, workflow) |
| `python eic.py load <name> [...]` | Load modules into workspace |
| `python eic.py unload <name>` | Remove module from workspace |
| `python eic.py ls` | List all modules and status |
| `python eic.py env` | Check secret variable status |
| `python eic.py validate [name]` | Validate module structure |

## Module kinds

- **integration** — Reusable access to an external service, API, or database
- **task** — A bounded outcome needing progress tracking
- **workflow** — A repeatable procedure that improves across runs

## Secrets

Modules can declare required environment variables in `module.yaml`. Values go in `.env` (gitignored). See `context/secrets.md` for details.

## Platform compatibility

Module loading uses symlinks. On Windows, enable Developer Mode or run as admin. Alternatively, copy module directories into `context/` manually.

## Upgrading to Context Agora

For a full web UI with secrets management, cron jobs, benchmarks, and more — check out [Context Agora](https://contextagora.com).

---

Built by [Bleak AI](https://bleakai.com) | [everythingiscontext.com](https://everythingiscontext.com)
