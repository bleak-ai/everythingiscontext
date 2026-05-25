# EIC Cloud

Give your agent a knowledge base it can navigate itself.

EIC Cloud is a context management platform for AI agents. Instead of re-explaining your stack every conversation, organize your knowledge as reusable **context modules** — plain markdown in Git that any AI agent can navigate independently.

![EIC Cloud demo](demo/eic-claude-demo.gif)

---

### Table of Contents

- [EIC Cloud](#eic-cloud)
    - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Supported Agents](#supported-agents)
  - [Self-host with Docker](#self-host-with-docker)
  - [Run Locally (Development)](#run-locally-development)
  - [Test with Claude Code](#test-with-claude-code)
  - [Architecture](#architecture)
  - [Contributing](#contributing)

---

## Features

**Three module types:**

- **Integrations** — Your external services: Stripe setup, database schema, CI pipeline, API docs
- **Workflows** — How you deploy, triage, onboard — agents follow your process step by step
- **Tasks** — Current work items; agents pick up where you left off

**Platform capabilities:**

- Visual module editor with live markdown preview
- Built-in AI chat with your full context loaded
- Modular context selection — enable only the modules each conversation needs
- Secret management via Varlock — secrets injected at runtime, never in files
- Git sync — modules live in a repo; pull, push, and review changes from the UI
- Session persistence across restarts
- Cron jobs for automated background tasks

## Supported Agents

EIC modules are plain markdown + YAML — they work with any agent that reads files:

- Claude Code
- Cursor
- Codex
- pi.dev

## Self-host with Docker

```bash
cp .env.example platform/.env   # fill in your credentials
docker compose up -d
```

Open http://localhost:9090

Update to latest version:

```bash
docker compose pull && docker compose up -d
```

The container includes Python 3.12, Node.js 22, Claude Code, Varlock, and Git. Modules are loaded from GitHub at runtime via the `GH_OWNER`/`GH_REPO`/`GH_TOKEN` env vars.

## Run Locally (Development)

```bash
cd platform
uv sync
uv run start
```

To build from source with Docker:

```bash
cd platform
docker build -t eic-cloud:local .
docker run --rm -p 9090:9090 --env-file .env.demo eic-cloud:local
```

## Test with Claude Code

1. Start the server (locally or with Docker)
2. Open http://localhost:9090 and select the modules you want to load
3. Open Claude Code from the context directory:
   ```bash
   cd platform/src/context
   claude
   ```
4. Claude will read the `CLAUDE.md` in that directory and work only with the loaded modules

## Architecture

```
├── core/            # Shared library — module specs, manifest parsing, templates
├── demo/            # CLI demo script + GIF
├── eic/             # CLI entry point
├── pyproject.toml   # Package definition
└── README.md
```

**Backend:** Python 3.12, FastAPI, SQLite, Varlock
**Frontend:** React 19, Vite, TanStack Router, Tailwind CSS, Radix UI

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request
