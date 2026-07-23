# gcontext

**Your agent's state lives in a folder. It's served at a URL. Any runtime becomes your agent.**

Claude Code, Codex, Cursor, Claude Desktop: these are runtimes. They read, reason, and act, but they forget everything between sessions. gcontext is the part that persists: the context your agent has learned, the services it can operate, the secrets it can use, the multi-step work in progress. All of it in a plain directory you can version with git.

gcontext is not a runtime. It has no chat loop, no LLM client, no orchestration engine. It serves your agent's state over MCP, and any MCP client that attaches becomes your agent.

```bash
uv tool install gcontext-ai        # or: uv tool install git+https://github.com/bleak-ai/gcontext

gcontext init my-agent             # scaffold the state folder
gcontext up my-agent               # serve it at http://127.0.0.1:4242/mcp
```

Connect a harness by pasting the URL, once, from any directory:

```bash
claude mcp add --transport http my-agent http://127.0.0.1:4242/mcp
```

The server prints every harness as it attaches. `Ctrl+C` and every harness cleanly loses access. That's the whole model: a server running, and harnesses that connect to it.

## What's in the folder

```
my-agent/
  gcontext.yaml          # identity: name, description, optional port
  instructions.md        # standing instructions for whatever runtime attaches
  secrets.env            # secret VALUES, gitignored, never leave your machine

  connections/           # services the agent can operate
    stripe/
      connection.yaml    # declares secret NAMEs and Python deps
      index.md           # how to use the API, patterns that work

  modules/               # knowledge the agent accumulates
  flows/                 # multi-step work, tracked as files (see below)
  archive/               # anything moved here is out of context, still readable
```

Markdown is the context. YAML is the config. The folder is the agent.

## The three ideas

### 1. Nothing reaches the agent invisibly

The **context ledger** enumerates every pipe that inserts context into the agent, each marked `loaded`, `on demand`, `skipped`, or `UNCONTROLLED` (runtime-owned). See it anytime:

```bash
gcontext context my-agent
```

If gcontext feeds something to the agent, it's on that list. No hidden injection, ever.

### 2. Secrets: names visible, values never

The agent sees secret NAMEs only. Values live in `secrets.env`, get injected as environment variables when a script runs (`run_script` tool, deps preinstalled via uv), and are scrubbed from all output. This never changes.

### 3. Flows: workflows as files, not engines

A flow declares which files each step needs and produces:

```yaml
steps:
  - id: draft
    needs: [flows/brief/brief.md]
    produces: [flows/brief/draft.md]
    instructions: Read the brief, write the draft.
```

Step status is computed purely from the filesystem, make-style: `blocked` (a need is missing), `ready` (needs exist, produces don't), `stale` (a need changed after the produces), `done`. A runtime completes a step by writing the declared files. There is no executor, no checkpointer, no stored run state: change an upstream file and downstream steps light up as stale. Progress is git-diffable because progress is files.

```bash
gcontext flows my-agent            # the board, per step
```

Attached runtimes get the same board via the `flows()` tool, with step instructions surfacing only when a step is actionable.

## Commands

| Command | What it does |
|---|---|
| `gcontext init <dir>` | Scaffold a new agent state folder |
| `gcontext up [dir]` | Serve the folder over MCP at a local URL |
| `gcontext status [dir]` | Server up? Who is connected? State overview |
| `gcontext connect [client]` | Attach instructions for claude, desktop, codex, cursor |
| `gcontext context [dir]` | The context ledger |
| `gcontext flows [dir]` | The flow boards |
| `gcontext chat [dir]` | A dedicated, fully controlled claude session |

The tools an attached runtime gets: `overview`, `read_context`, `write_context`, `run_script`, `list_connections`, `flows`.

## Housekeeping without magic

When accumulated state starts polluting context, move folders into `archive/`:

```
mv my-agent/modules/old-onboarding my-agent/archive/modules/
```

Archived items are never scanned into overviews or counts, stay readable by path, and every summary reports that they exist. The folder move is the entire mechanism. gcontext never archives, deletes, or reorganizes anything by itself.

## Scope

Local-first, by design. The server binds `127.0.0.1` with no auth: everything on your machine, nothing exposed. A remote/deployed story (same shape, a URL with a token) is planned but deliberately not in this release.

## License

MIT
