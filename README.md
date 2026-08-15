[![PyPI](https://img.shields.io/pypi/v/gcontext-ai?style=for-the-badge)](https://pypi.org/project/gcontext-ai/)
[![License](https://img.shields.io/github/license/bleak-ai/gcontext?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/bleak-ai/gcontext?style=for-the-badge)](https://github.com/bleak-ai/gcontext/stargazers)

# gcontext

A framework for building stateful agents. An agent is a folder of plain files (instructions, connections, secrets, knowledge modules, scripts) served over MCP by a local HTTP server. Runtimes (Claude Code, Desktop, Codex, Cursor) connect to the URL and do the reasoning; gcontext keeps the state.

## Table of Contents

- [Features](#features)
- [Install](#install)
- [Quickstart](#quickstart)
- [The folder](#the-folder)
- [Your first connection](#your-first-connection)
- [CLI](#cli)
- [Agents](#agents)
- [Going further](#going-further)
- [Scope](#scope)
- [License](#license)

---

## Features

- **State that survives sessions** - the folder persists across runtimes and clients; nothing is lost between conversations
- **Any MCP client** - Claude Code, Claude Desktop, Codex, Cursor, or anything that speaks MCP
- **Connections** - declare service integrations with secret names and Python deps; values stay on your machine, injected at runtime, scrubbed from output
- **Modules** - accumulated knowledge on a topic, one folder per domain, growing over time
- **Scripts** - `run_script` for saved procedures, `run_adhoc_script` for one-off code, both with secret injection and output scrubbing
- **Commands** - markdown or Python files that register as slash commands in your client
- **Dashboard** - read-only web UI with file browser, connection status, and live activity feed
- **Context ledger** - `gcontext context` lists every channel through which context reaches the agent, so you always know what it sees
- **Installable agents** - `gcontext add <id>` installs a pre-built agent from the [registry](https://github.com/bleak-ai/agents)

## Install

gcontext needs [uv](https://docs.astral.sh/uv/): it installs the tool and manages each agent's script environment at runtime. No uv yet? One line, no prerequisites (it brings its own Python if needed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # or: brew install uv
```

Then:

```bash
uv tool install gcontext-ai
```

## Quickstart

```bash
gcontext init my-agent      # create the state folder
gcontext up my-agent        # serve it at http://127.0.0.1:4242/mcp
```

Then connect a client (once, from any directory):

```bash
claude mcp add --transport http my-agent http://127.0.0.1:4242/mcp
```

`gcontext connect claude|desktop|codex|cursor` prints the exact steps per client. The server logs each client as it connects. Stopping the server (Ctrl+C) disconnects everything; there is no other cleanup.

## The folder

```
my-agent/
  gcontext.yaml          # name, description, optional port
  agent.md               # your agent's definition, pushed to every client at connect
  secrets.env            # secret values, gitignored

  connections/           # services the agent can use
    stripe/
      connection.yaml    # secret names + Python deps
      index.md           # API notes, usage patterns

  modules/               # accumulated knowledge
  archive/               # excluded from scanning, still readable
```

Markdown holds the context, YAML holds the config. Edit any of it with a text editor; the server reads the files on demand, so changes apply immediately. Two exceptions load at server start and need a restart to pick up edits: `agent.md` and command files.

At connect, every agent receives two layers of instructions: gcontext's fixed instructions (shipped with the package, they explain the tools and folder conventions), then your `agent.md` (what this particular agent is). You only ever write the second layer.

Connected clients get seven tools: `read_file`, `write_file`, `list_dir`, `grep`, `run_script`, `run_adhoc_script`, `agent`. Every state file is also exposed as an MCP resource at `gcontext://<path>`, so runtimes that support resource mentions can attach a file directly, e.g. `@my-agent:gcontext://modules/topic/index.md`.

## Your first connection

`init` creates no connections: a connection is worth having when it points at a service you actually use. Adding one is three files, no command needed:

```bash
mkdir -p my-agent/connections/stripe
```

`connections/stripe/connection.yaml` declares what the connection needs, by name only:

```yaml
name: stripe
description: Payments, test mode.
secrets:
  - STRIPE_API_KEY
deps:
  - stripe
```

Put the value in `secrets.env` (gitignored, never leaves your machine):

```bash
echo 'STRIPE_API_KEY=sk_test_...' >> my-agent/secrets.env
```

And write `connections/stripe/index.md`: what the service is for, which endpoints matter, any usage patterns worth remembering. The agent reads this before writing scripts, and updates it as it learns.

That's it. The server picks the connection up on the next tool call (no restart), `gcontext status` shows whether every declared secret has a value, and the agent can now call the API through `run_adhoc_script` and `run_script` without ever seeing the key.

The full reference is in [docs/connections.md](docs/connections.md).

## CLI

| Command | Description |
|---|---|
| `gcontext init <dir>` | Scaffold a new state folder |
| `gcontext up [dir]` | Serve the folder over MCP |
| `gcontext status [dir]` | Server state, connected clients, state overview |
| `gcontext connect [client]` | Connection steps for claude, desktop, codex, cursor |
| `gcontext add <id>` | Install an agent from the [registry](https://github.com/bleak-ai/agents) or from any public GitHub repo URL |
| `gcontext update <id>` | Update an installed agent (three-way merge, keeps your local changes) |
| `gcontext search [query]` | Search the agent registry |
| `gcontext share <path>` | Validate an agent folder and print the steps to submit it to the registry |
| `gcontext context [dir]` | Print the context ledger |

## Agents

Pre-built agents live in the [bleak-ai/agents](https://github.com/bleak-ai/agents) registry. Install one with:

```bash
gcontext add <agent-id>
```

This copies the agent's modules, connections, and commands into your state folder. Agents that depend on other agents are resolved recursively. To create and share your own agent, see [docs/share-agent.md](docs/share-agent.md).

## Going further

- [examples/ops-agent](examples/ops-agent) - a complete agent folder with connections, modules, a command, and an archived module
- [docs/design.md](docs/design.md) - why gcontext is built this way, decision by decision
- [docs/connections.md](docs/connections.md) - the connection reference, from manifest fields to smoke tests
- [docs/modules.md](docs/modules.md) - writing portable, shareable modules
- [docs/agents.md](docs/agents.md) - the agent template standard for distributable agents
- [docs/setup-script.md](docs/setup-script.md) - the setup script standard, every text a user reads during install and setup
- [docs/share-agent.md](docs/share-agent.md) - turning a lived agent into a shareable template
- [docs/reference.md](docs/reference.md) - secrets, commands, dashboard, archiving, context ledger, controlled sessions

## Scope

Local only. The server binds `127.0.0.1` without auth, so it is not reachable from outside your machine and should stay that way. A remote variant (same model, URL plus token) is planned but not part of this release.

## License

MIT
