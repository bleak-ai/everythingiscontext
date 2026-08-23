[![PyPI](https://img.shields.io/pypi/v/gcontext-ai?style=for-the-badge)](https://pypi.org/project/gcontext-ai/)
[![License](https://img.shields.io/github/license/bleak-ai/gcontext?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/bleak-ai/gcontext?style=for-the-badge)](https://github.com/bleak-ai/gcontext/stargazers)

# gcontext

A framework for building stateful agents. An agent is a folder of plain files (instructions, connections, secrets, knowledge modules, scripts) served over [MCP](docs/mcp.md) by a local HTTP server. Runtimes (Claude Code, Desktop, Codex, Cursor) connect to the URL and do the reasoning; gcontext keeps the state.

## Table of Contents

- [Features](#features)
- [Install](#install)
- [Quickstart](#quickstart)
- [The folder](#the-folder)
- [Memory](#memory)
- [Reach](#reach)
- [Steering](#steering)
- [CLI](#cli)
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
- **Installable agents** - `gcontext add <id>` installs a pre-built agent from the [registry](https://github.com/bleak-ai/agents); browse them at [gcontext.ai/agents](https://gcontext.ai/agents/)

## Install

gcontext needs [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer; uv installs a suitable Python by itself when the machine has none. uv installs the tool and manages each agent's script environment at runtime. No uv yet? One line, no prerequisites:

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

The same server also hosts a read-only dashboard at `http://127.0.0.1:4242/`: file browser, connection status, live activity feed.

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
  agents/                # installed agents from the registry (gcontext add)
  archive/               # excluded from scanning, still readable
```

Markdown holds the context, YAML holds the config. Edit any of it with a text editor; the server reads the files on demand, so most changes apply immediately. The exceptions (`agent.md` and command files) are handled by `gcontext reload`; the full table of which change needs a reload or a client reconnect is in [docs/using.md](docs/using.md#what-needs-a-reload-what-needs-a-reconnect).

Three ideas cover everything in this folder: Memory (the agent's files), Reach (the services it can use), Steering (how you direct it from your client).

## Memory

Everything the agent knows is a plain file in this folder. `agent.md` is its definition, pushed to every client at connect: gcontext sends its own fixed instructions first (they explain the tools and folder conventions), then your `agent.md`; you only ever write the second layer. `modules/` holds accumulated knowledge, one folder per topic, growing as the agent works. `archive/` holds retired state: skipped when scanning, still readable. Installed agents (`gcontext add <id>`, from the [registry](https://github.com/bleak-ai/agents)) live in `agents/` as more files of the same kind, and bring their own commands.

Because memory is files, it persists across sessions and clients. Try it in Claude Code:

```
Remember that our API rate limit is 60 requests per minute.
```

The agent writes that into a module file. A new session, even in a different client, reads it back.

## Reach

A connection gives the agent a service it can use: a folder under `connections/` plus the secret names it needs. The values live in `secrets.env`, are injected into scripts at runtime, and are scrubbed from output; the agent uses the key but never sees it.

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

That's it. The server picks the connection up on the next tool call (no restart), `gcontext status` shows whether every declared secret has a value, and the agent can now use the service. In Claude Code:

```
List the last three Stripe test payments.
```

The full reference is in [docs/connections.md](docs/connections.md).

## Steering

Two ways to direct a connected agent, both typed in your client.

**Commands** are markdown or Python files under a `commands/` folder inside a connection, module, or installed agent. Each registers as a slash command in Claude Code. The one every new project has is setup:

```
/mcp__my-agent__setup
```

Installed agents bring their own commands; after `gcontext add <id>` they show up the same way.

**Resources** attach a state file to your message, so its content is in front of the agent before it starts. Every state file is one; in Claude Code the mention form is:

```
@my-agent:gcontext://modules/topic/index.md
```

The day-to-day details of both are in [docs/using.md](docs/using.md).

## CLI

| Command | Description |
|---|---|
| `gcontext init <dir>` | Scaffold a new state folder |
| `gcontext up [dir]` | Serve the folder over MCP |
| `gcontext status [dir]` | Server state, connected clients, state overview |
| `gcontext reload [dir]` | Apply agent.md, command, and controls.yaml edits to the running server |
| `gcontext connect [client]` | Connection steps for claude, desktop, codex, cursor |
| `gcontext add <id>` | Install an agent from the [registry](https://github.com/bleak-ai/agents) or from any public GitHub repo URL |
| `gcontext update <id>` | Update an installed agent (three-way merge, keeps your local changes) |
| `gcontext remove <id>` | Uninstall an agent, with optional archiving of its data |
| `gcontext search [query]` | Search the agent registry (no query lists every agent; also browsable at [gcontext.ai/agents](https://gcontext.ai/agents/)) |
| `gcontext share <path>` | Validate an agent folder and print the steps to submit it to the registry |
| `gcontext context [dir]` | Print the context ledger |

## Going further

- [docs/using.md](docs/using.md) - the day-to-day guide: invoking commands, attaching files, reload vs reconnect, template commands, installing agents
- [docs/mcp.md](docs/mcp.md) - the Model Context Protocol in one page
- [docs/connections.md](docs/connections.md) - the connection reference, from manifest fields to smoke tests
- [docs/troubleshooting.md](docs/troubleshooting.md) - symptoms, exact error texts, and fixes
- [examples/ops-agent](examples/ops-agent) - a complete agent folder with connections, modules, a command, and an archived module

### Advanced

Needed only in specific situations; each page or section opens with when.

- [docs/reference.md](docs/reference.md) - secrets handling, the command file format, dashboard, archiving
- [docs/reference.md#controls](docs/reference.md#controls) - controls.yaml, the on/off registry for commands and resources, plus pinned files
- [docs/reference.md#context-ledger](docs/reference.md#context-ledger) - list every channel through which context reaches the agent
- [docs/using.md#template-commands](docs/using.md#template-commands) - one command file that registers a slash command per matching folder
- [docs/reference.md#controlled-session](docs/reference.md#controlled-session) - a claude session with the runtime-owned context pipes closed
- [docs/tools.md](docs/tools.md) - the seven tools an attached agent works with, described one by one

### For agent authors

- [docs/modules.md](docs/modules.md) - writing portable, shareable modules
- [docs/agents.md](docs/agents.md) - the agent template standard for distributable agents
- [docs/setup-script.md](docs/setup-script.md) - the setup script standard, every text a user reads during install and setup
- [docs/design.md](docs/design.md) - why gcontext is built this way, decision by decision

## Scope

Local only. The server binds `127.0.0.1` without auth, so it is not reachable from outside your machine and should stay that way. A remote variant (same model, URL plus token) is planned but not part of this release.

## License

MIT
