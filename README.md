# Everything Is Context

An open-source, agent-agnostic context management system. Create, organize, and load context modules into a workspace that any coding agent can read and operate on.

## Quick start

```bash
# Install
curl -LsSf https://everythingiscontext.com/eic/install.sh | sh

# Create a project
mkdir my-project && cd my-project
eic init

# Create a module
eic new integration stripe

# Edit the module files
# Fill in modules-repo/stripe/info.md with your Stripe docs, auth details, operations

# Load it
eic load stripe

# Point your agent at context/
# Open Claude Code, Codex, Cursor, or any coding agent in the context/ directory
```

**Alternative install methods:**

```bash
# Via uv (if already installed)
uv tool install everythingiscontext

# Via pip
pip install everythingiscontext
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
| `eic init` | Initialize workspace |
| `eic new <kind> <name>` | Create a module (kind: integration, task, workflow) |
| `eic load <name> [...]` | Load modules into workspace |
| `eic unload <name>` | Remove module from workspace |
| `eic ls` | List all modules and status |
| `eic env` | Check secret variable status |
| `eic validate [name]` | Validate module structure |

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
