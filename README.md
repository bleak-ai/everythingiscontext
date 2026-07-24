# gcontext

gcontext stores an AI agent's state (instructions, service connections, secrets, knowledge, work in progress) in a plain directory and serves it over MCP from a local HTTP server. MCP clients like Claude Code, Codex, Cursor, or Claude Desktop connect to that server and work against the shared state.

The point: runtimes forget everything between sessions. If the state lives in a folder instead, it persists, you can version it with git, and you can switch runtimes without losing anything. gcontext only manages that state. It has no chat loop, no LLM client, and no orchestration; the runtime you attach does the actual work.

## Install

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
  instructions.md        # standing instructions for whatever runtime attaches
  secrets.env            # secret values, gitignored

  connections/           # services the agent can use
    stripe/
      connection.yaml    # secret names + Python deps
      index.md           # API notes, usage patterns

  modules/               # accumulated knowledge
  flows/                 # multi-step work, tracked as files (see below)
  archive/               # excluded from scanning, still readable
```

Markdown holds the context, YAML holds the config. Edit any of it with a text editor; the server reads the files on demand, so changes apply immediately.

Connected clients get six tools: `overview`, `read_context`, `write_context`, `run_script`, `list_connections`, `flows`.

## Context ledger

`gcontext context` lists every channel through which context reaches the agent, marked as `loaded` (pushed at start), `on demand` (agent pulls it via a visible tool call), `skipped` (closed by a launch flag), or `uncontrolled` (owned by the runtime, outside gcontext's view). gcontext only inserts context through the channels on that list. If you want to know what the agent is seeing, this is the answer.

## Secrets

`connection.yaml` declares secret names; `secrets.env` holds the values. When the agent calls `run_script`, the values are injected as environment variables and scrubbed from the script's output. The agent can know that `STRIPE_API_KEY` exists and use it in a script, but never reads the value. `secrets.env` is gitignored by `init` and the `write_context` tool refuses to touch it.

`run_script` executes Python in a per-project venv with each connection's declared deps preinstalled (via uv).

## Flows

A flow is a YAML file describing multi-step work as file dependencies:

```yaml
steps:
  - id: draft
    needs: [flows/brief/brief.md]
    produces: [flows/brief/draft.md]
    instructions: Read the brief, write the draft.
```

Step status is derived from the filesystem, like make targets:

- `blocked`: a needed file doesn't exist
- `ready`: needs exist, produces don't
- `stale`: a needed file was modified after the produced files
- `done`: everything exists and is up to date

There is no engine and no stored run state. A step is completed by writing the files it declares, whether that's done by an attached runtime, a script, or you in an editor. If an upstream file changes, downstream steps become stale on the next read. `gcontext flows` prints the board; attached clients get the same via the `flows()` tool, which includes step instructions only for steps that are currently actionable.

## Archiving

When old modules or connections start cluttering the context, move them:

```bash
mv my-agent/modules/old-onboarding my-agent/archive/modules/
```

Anything under `archive/` is skipped when scanning, but stays readable by path, and summaries mention what's archived so it doesn't silently vanish. That's the entire mechanism. gcontext never moves, archives, or deletes anything on its own.

## Commands

| Command | Description |
|---|---|
| `gcontext init <dir>` | Scaffold a new state folder |
| `gcontext up [dir]` | Serve the folder over MCP |
| `gcontext status [dir]` | Server state, connected clients, state overview |
| `gcontext connect [client]` | Connection steps for claude, desktop, codex, cursor |
| `gcontext context [dir]` | Print the context ledger |
| `gcontext flows [dir]` | Print the flow boards |
| `gcontext chat [dir]` | Launch a dedicated claude session against the folder |

## Scope

Local only. The server binds `127.0.0.1` without auth, so it is not reachable from outside your machine and should stay that way. A remote variant (same model, URL plus token) is planned but not part of this release.

## License

MIT
