# Design

Why gcontext is built the way it is: the decisions, the alternatives that were rejected, and the principles that fall out. The README explains what gcontext does; this explains why.

## State manager, not runtime

Claude Code, Codex, Cursor: these are runtimes. They run the loop, stream tokens, manage sessions, dispatch tools. gcontext is the part they all lack: the state. The context an agent has accumulated, the services it can operate, the secrets it can use, the work in progress, all in a plain directory.

gcontext never competes with runtimes, it feeds them. Anything that looks like a message loop, a streaming handler, or a session manager belongs to the runtime. Runtimes are a competitive, fast-moving space owned by large companies; state is not. Runtimes are interchangeable; the state is not.

An earlier version shipped a ~230 line custom chat REPL wrapping `claude -p`. It was deleted: it reimplemented what the runtime ships for free, and a homemade REPL is a runtime. Its replacement, `gcontext chat`, is a small launcher that prints the context ledger and execs the real `claude` with the right flags. The launcher gives more control over context than the REPL ever did, because the runtime's own flags can close pipes the REPL couldn't.

## A folder is the agent's state

There is no database, no manifest system, no type registry. An agent is a directory: markdown for context, YAML for config, an env file for secret values. If you can create a folder and put a markdown file in it, you can extend the agent. The whole thing versions with git, which means agent state gets diffs, history, review, and rollback for free.

The predecessor of this design had typed modules (integration / task / workflow) with manifest files. It was rejected: the classification created decision paralysis ("is this a task or a workflow?") and the manifests had too many fields. A folder is a folder. Progressive complexity instead: start with markdown (knowledge), add a `connection.yaml` when you need secrets (integration), add a `flow.yaml` when work has steps (process).

## Config is YAML, content is markdown, behavior is scripts

Each concern has exactly one representation:

- **YAML** (`gcontext.yaml`, `connection.yaml`, `flow.yaml`) is data the framework reads. It is statically parseable: gcontext can list every connection, every required secret, and every flow step without executing anything, without deps installed, without secrets set.
- **Markdown** is context the agent reads. Free-form, no schema, grows however makes sense.
- **Python** exists only as scripts the agent writes and runs on demand.

Connection definitions were almost Python files with a `Connection()` object and a `verify()` hook. Rejected for concrete reasons: importing user Python to scan connections executes side effects (the exact problem Airflow spent years escaping before `provider.yaml`), metadata extraction would require every dep installed and every env var set, Python config files accumulate business logic until they become God files, and importing untrusted connection definitions is arbitrary code execution.

## No pre-built tools

gcontext does not have pre-defined callable tool functions per service. The agent reads a connection's markdown (how the API works, usage patterns), then writes a script for whatever the task actually is. The framework runs it with secrets injected and deps available.

This is the core difference from tool-centric frameworks: there, a developer pre-builds functions and the agent picks one; here, the developer writes documentation and the agent writes the code. The context is the tool instruction. If the markdown explains the API well, the agent can do anything with it, not just the operations someone anticipated. And writing markdown about an API is something anyone can do; writing tool schemas requires framework knowledge.

## The secrets model

Secret NAMES are declared in `connection.yaml`. Secret VALUES live in `secrets.env`, gitignored, never leaving the machine.

The agent knows `STRIPE_API_KEY` exists and writes `os.environ["STRIPE_API_KEY"]` in scripts, but can never read the value: values are injected as environment variables at execution time and scrubbed from the script's output before the agent sees it. The `write_context` tool refuses to touch `secrets.env`.

This is the invariant that never changes: secrets never enter the context window. Names are visible, values are local, injected at runtime, scrubbed from output.

## One server, one URL

`gcontext up` serves the folder at one local HTTP URL. Every harness connects to that URL. There is no stdio mode.

The first MCP version used stdio, and a day of real use produced a catalog of failures with one root cause: stdio inverts the mental model. There is no "server running"; every harness silently spawns its own private copy from a long registration command. Commands paste-truncate silently and fail minutes later as a bare "not connected". "Is it connected?" has no answer without scanning config files across harnesses and scopes. People run the server by hand, see it "hang", and assume it is broken.

With one server at a URL: connecting is pasting a URL, which cannot half-truncate into something that almost works. Up or down is observable; Ctrl+C revokes access everywhere at once. Because all harnesses share the server, the server knows who is connected (the MCP handshake carries `clientInfo`, and `gcontext status` shows it). And local vs deployed becomes "local URL vs remote URL", the same shape.

Rejected along the way: per-harness adapters that write each client's config (scope creep into files gcontext doesn't own), a machine-wide agent name registry (another layer of state; the URL already is the handle), and config-scanning diagnostics (detective work compensating for a transport that hides the truth).

The accepted tradeoff: something must be running.

## The context ledger: nothing is pushed invisibly

Every pipe that inserts context into the agent is enumerated in one ledger, computed live from the folder so it cannot go stale. Each pipe is marked `loaded` (pushed at start), `on demand` (agent pulls it via a visible tool call), `skipped` (closed by a launch flag), or `uncontrolled` (runtime-owned, outside gcontext's view). The ledger appears in `gcontext context`, at `chat` launch, in `overview()`, and after `connect`.

This section exists because of a reverted feature. instructions.md was once wired into the MCP handshake's `instructions` field, so any connecting client received it automatically. It worked, and it was reverted the same day. gcontext's entire promise is legibility of context: you look at the folder and you know what the agent knows. Content that teleports into the agent's head through a handshake side channel is invisible; a user debugging their agent cannot tell where an instruction came from or that it was loaded at all.

The invariant: a context management system must make context flow explicit and inspectable. Convenience never justifies a hidden push. Consequence: in attach mode, instructions.md is not auto-loaded; the ledger and `overview()` tell the agent to read it.

The ledger is also honest about its limits. When a runtime keeps pipes gcontext cannot close (its own system prompt, its config files, other MCP servers), the ledger marks them UNCONTROLLED instead of pretending the session is cleaner than it is.

## Flows: reactive state, not reactive execution

The tempting design was a workflow engine inside gcontext: watch state, fire LLM calls, run steps. That would make gcontext a runtime and an orchestrator, competing with graph frameworks and the harnesses themselves. Rejected.

Instead, flows are data. A step declares `needs` and `produces` (file paths), and status is a pure function of the filesystem, computed on read with make-style mtime staleness: `blocked`, `ready`, `stale`, `done`. No run state is stored anywhere.

Everything else falls out for free:

- Completing a step IS writing its declared files. There is no `complete_step` call, so there is no stored state to drift from reality.
- Reactivity with zero machinery: change an upstream file and downstream steps become stale on the next read.
- Progress is git-diffable and revertible, because progress is files.
- Any runtime, several at once, a script, or a human with a text editor can advance the same flow.

A graph engine keeps state in a checkpointer and drives execution; gcontext keeps state in files and drives nothing.

The `flows()` tool shows every step's status but includes instructions only for actionable (ready or stale) steps: the runtime receives exactly the work the current state unlocks. This stays inside the legibility invariant because it is a pull, and the deferral rule is itself declared in the ledger.

## Archive: a location, not metadata

State accumulates until it pollutes the context and the agent can't find the right thing. The rejected fix was a `surface: active | background | archived` field with agent-driven housekeeping and staleness hints: too much magic. gcontext must have no background or automatic behaviors; humans must always see how state is controlled.

So visibility is a function of file location, the same way flow status is a function of file existence. Move a folder into `archive/` and it stops being scanned, while staying readable by path, and every summary mentions what's archived so nothing disappears silently. A folder move is an action everyone understands, is visible in git, and cannot happen behind anyone's back. gcontext never moves, archives, or deletes anything on its own.

## Deferred, deliberately

- **Remote variant**: same model, URL plus token, for a served-anywhere agent. The URL transport is the bridge to it.
- **Triggers/watchers**: something that pokes a runtime when state changes. Even then, gcontext would trigger a runtime, never run the loop.
- **Multi-instance flow runs** (the same flow over many tickets): needs a parametrization story, waiting for a real need.
- **Non-file flow conditions** (a step gated on a secret being filled): plausible, waiting for a real need.

## Principles

1. **Feed runtimes, never be one.**
2. **A folder is a folder.** No types, no manifests, no classification.
3. **Config and content are separate concerns.** YAML is data, markdown is context, Python is behavior.
4. **Static metadata, dynamic execution.** Everything is inspectable without running anything; scripts run only when explicitly invoked.
5. **The agent is already smart, it just needs the right information.** Good context plus usable credentials beats pre-built tools.
6. **Secrets never enter the context window.**
7. **Nothing is pushed invisibly.** Every piece of context is a file in the folder, a visible tool result, or explicitly listed as runtime-owned.
8. **Status is a pure function of the filesystem.** Flow progress, archive visibility, connection readiness: all derived from files on read, never stored and synced.
9. **Honesty over the illusion of control.** Uncontrolled pipes are labeled uncontrolled.
