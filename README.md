# gcontext

The framework for building stateful agents.

An agent built with gcontext is a folder: instructions, service connections, secrets, knowledge, and multi-step work, all as plain files you can version with git. gcontext serves that folder over MCP from a local HTTP server, and you use the agent from the tools you already work in: Claude Code, Claude Desktop, Codex, or Cursor.

Runtimes forget everything between sessions; the folder doesn't. Because the state is separate from the runtime, the same agent works from any client and survives every session. gcontext ships no chat loop and no LLM client: the runtime you attach does the reasoning, gcontext keeps the state.

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
  agent.md               # your agent's definition, pushed to every agent at connect
  secrets.env            # secret values, gitignored

  connections/           # services the agent can use
    stripe/
      connection.yaml    # secret names + Python deps
      index.md           # API notes, usage patterns

  modules/               # accumulated knowledge
  archive/               # excluded from scanning, still readable
```

Markdown holds the context, YAML holds the config. Edit any of it with a text editor; the server reads the files on demand, so changes apply immediately. Two exceptions load at server start and need a restart to pick up edits: `agent.md` (pushed in the MCP handshake) and command files. The server warns when these files change: in the `write_file` result, and with a line on the server terminal.

At connect, every agent receives two layers of instructions through the handshake: first gcontext's own fixed instructions (shipped with the package, they explain the tools and the folder conventions), then your `agent.md` (what this particular agent is). You only ever write the second layer.

Connected clients get six tools: `read_file`, `write_file`, `list_dir`, `grep`, `run_script`, `run_adhoc_script`. Every state file is also exposed as an MCP resource at `gcontext://<path>` (a folder URI returns its listing), so runtimes that support resource mentions can attach a file directly, e.g. `@my-agent:gcontext://modules/topic/index.md`. The dashboard's copy buttons copy exactly these references.

`run_script` runs a saved script by path (`scripts/` folders hold proven procedures, so they are reused instead of rewritten); `run_adhoc_script` runs ad-hoc code, which keeps a script call short and readable in the runtime's tool display. Both return readable text: a status line (exit code, duration, timed out / truncated flags), then stdout and stderr. Files under `connections/*/commands/` and `modules/*/commands/` register as MCP prompts, which Claude Code shows as slash commands; see "Commands" below.

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

The full reference (manifest fields, index.md guidance, smoke tests, auth patterns, starter manifests) is in [docs/connections.md](docs/connections.md).

## Context ledger

`gcontext context` lists every channel through which context reaches the agent, marked as `loaded` (pushed at connect), `on demand` (agent pulls it via a visible tool call), `skipped` (nothing to push), or `uncontrolled` (owned by the runtime, outside gcontext's view). gcontext only inserts context through the channels on that list. If you want to know what the agent is seeing, this is the answer.

## Controlled session

The ledger marks runtime-owned pipes (the runtime's system prompt, its config files, its other MCP servers) as `uncontrolled`, because gcontext cannot close them. If you want a claude session with those pipes closed, launch claude yourself with its own flags; there is no gcontext command for this, since it is a runtime invocation, not framework behavior:

```bash
claude --mcp-config '{"mcpServers":{"gcontext":{"type":"http","url":"http://127.0.0.1:4242/mcp"}}}' \
       --strict-mcp-config \
       --setting-sources ""
```

`--strict-mcp-config` ignores every other configured MCP server, and `--setting-sources ""` skips CLAUDE.md files and user settings. Your `agent.md` still arrives through the MCP handshake, like in any session. Adjust the URL to your project's port.

## Secrets

`connection.yaml` declares secret names; `secrets.env` holds the values. When the agent calls `run_script` or `run_adhoc_script`, the values are injected as environment variables and scrubbed from the script's output. The agent can know that `STRIPE_API_KEY` exists and use it in a script, but never reads the value. `secrets.env` is gitignored by `init` and the `write_file` tool refuses to touch it.

One honest caveat: `secrets.env` is plain text on disk. gcontext never shows
values to the agent, but any other program with filesystem access, including
your AI client's own file tools, can read the file directly. `init` creates it
with mode 600 and gitignores it. If your client supports permission rules,
deny it read access to `secrets.env` as well.

Both tools execute Python in a per-project venv with each connection's declared deps preinstalled (via uv).

## Archiving

When old modules or connections start cluttering the context, move them:

```bash
mv my-agent/modules/old-onboarding my-agent/archive/modules/
```

Anything under `archive/` is skipped when scanning, but stays readable by path, and summaries mention what's archived so it doesn't silently vanish. That's the entire mechanism. gcontext never moves, archives, or deletes anything on its own.

## Commands

A command is a user-invokable entry point stored next to the knowledge it belongs to: a file under `connections/<name>/commands/` or `modules/<name>/commands/`. The server registers each one as an MCP prompt named `<owner>__<command>`; Claude Code shows it as a slash command (`/mcp__<server>__<owner>__<command>`). Prompts cost no tool-schema context: a command's text enters the conversation only when you invoke it.

Two file types:

- `.md`: YAML frontmatter (description, parameters), then the body that gets injected, with `$name` placeholders filled from the arguments.

  ```markdown
  ---
  description: Draft a refund reply
  parameters:
    - name: email
      required: true
  ---
  Draft a refund reply for $email and show it to the user.
  ```

- `.py`: a runnable script with the same frontmatter as a `# ---` comment block at the top. Invoking it instructs the agent to run the file through `run_script`, with the arguments passed as `params` (they reach the script as `PARAM_<NAME>` env vars).

Commands are discovered at server start; restart to pick up new files.

## Dashboard

`gcontext up` also serves a read-only dashboard at the server root, for example `http://127.0.0.1:4242/`. It shows the project overview and context ledger, connections with secret status (names only, never values), modules, commands, a file browser, and a live activity feed of every tool call agents make. The feed lives in server memory and empties on restart. The dashboard changes nothing; agents make the changes.

Developing the dashboard itself needs node: `make web-dev` runs a Vite dev server on `http://localhost:5179` that proxies to the gcontext server, and `make web-build` produces the static bundle that `gcontext up` serves.

## CLI

| Command | Description |
|---|---|
| `gcontext init <dir>` | Scaffold a new state folder |
| `gcontext up [dir]` | Serve the folder over MCP |
| `gcontext status [dir]` | Server state, connected clients, state overview |
| `gcontext connect [client]` | Connection steps for claude, desktop, codex, cursor |
| `gcontext add <id>` | Install a workflow from the registry repo ([github.com/bleak-ai/workflows](https://github.com/bleak-ai/workflows)) or from any public GitHub repo folder via `gcontext add <github-url>` |
| `gcontext update <id>` | Update an installed workflow from the registry (three-way merge: keeps your local changes, writes `.new` files on conflicts) |
| `gcontext search [query]` | Search the workflow registry by name, description, or tags |
| `gcontext share <path>` | Validate a workflow template folder and print the steps to submit it as a pull request to the registry |
| `gcontext context [dir]` | Print the context ledger |

## Going further

- [examples/ops-agent](examples/ops-agent): a complete agent folder with connections, modules, a command, and an archived module
- [docs/design.md](docs/design.md): why gcontext is built this way, decision by decision
- [docs/connections.md](docs/connections.md): the connection reference, from manifest fields to smoke tests
- [docs/modules.md](docs/modules.md): writing portable, shareable modules
- [docs/workflows.md](docs/workflows.md): the workflow template standard, the contract for distributable context-based workflows
- [docs/share-workflow.md](docs/share-workflow.md): instructions an author's agent follows to turn a lived workflow into a shareable template

## Scope

Local only. The server binds `127.0.0.1` without auth, so it is not reachable from outside your machine and should stay that way. A remote variant (same model, URL plus token) is planned but not part of this release.

## License

MIT
