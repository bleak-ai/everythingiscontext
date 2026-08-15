# Design

Why gcontext is built the way it is: the decisions, the alternatives that were rejected, and the principles that fall out. The README explains what gcontext does; this explains why.

## State manager, not runtime

Claude Code, Codex, Cursor: these are runtimes. They run the loop, stream tokens, manage sessions, dispatch tools. gcontext is the part they all lack: the state. The context an agent has accumulated, the services it can operate, the secrets it can use, the work in progress, all in a plain directory.

gcontext never competes with runtimes, it feeds them. Anything that looks like a message loop, a streaming handler, or a session manager belongs to the runtime. Runtimes are a competitive, fast-moving space owned by large companies; state is not. Runtimes are interchangeable; the state is not.

This principle removed two features in sequence. An early version shipped a ~230 line custom chat REPL wrapping `claude -p`; deleted, because a homemade REPL is a runtime. Its replacement, `gcontext chat`, was a launcher that execed the real `claude` with lockdown flags; also deleted, once the handshake started delivering the instructions to every client and the launcher's only remaining job was passing claude-specific flags gcontext has no business owning. What survives is a documented claude invocation in the README ("Controlled session") for anyone who wants those pipes closed. Each step moved the same direction: gcontext feeds runtimes and launches none.

## A folder is the agent's state

There is no database, no manifest system, no type registry. An agent is a directory: markdown for context, YAML for config, an env file for secret values. If you can create a folder and put a markdown file in it, you can extend the agent. The whole thing versions with git, which means agent state gets diffs, history, review, and rollback for free.

The predecessor of this design had typed modules (integration / task / workflow) with manifest files. It was rejected: the classification created decision paralysis ("is this a task or a workflow?") and the manifests had too many fields. A folder is a folder. Progressive complexity instead: start with markdown (knowledge), add a `connection.yaml` when you need secrets (integration), add scripts and commands when procedures prove themselves.

## Config is YAML, content is markdown, behavior is scripts

Each concern has exactly one representation:

- **YAML** (`gcontext.yaml`, `connection.yaml`) is data the framework reads. It is statically parseable: gcontext can list every connection and every required secret without executing anything, without deps installed, without secrets set.
- **Markdown** is context the agent reads. Free-form, no schema, grows however makes sense.
- **Python** exists only as scripts the agent writes and runs on demand.

Connection definitions were almost Python files with a `Connection()` object and a `verify()` hook. Rejected for concrete reasons: importing user Python to scan connections executes side effects (the exact problem Airflow spent years escaping before `provider.yaml`), metadata extraction would require every dep installed and every env var set, Python config files accumulate business logic until they become God files, and importing untrusted connection definitions is arbitrary code execution.

## No pre-built tools

gcontext does not have pre-defined callable tool functions per service. The agent reads a connection's markdown (how the API works, usage patterns), then writes a script for whatever the task actually is. The framework runs it with secrets injected and deps available.

This is the core difference from tool-centric frameworks: there, a developer pre-builds functions and the agent picks one; here, the developer writes documentation and the agent writes the code. The context is the tool instruction. If the markdown explains the API well, the agent can do anything with it, not just the operations someone anticipated. And writing markdown about an API is something anyone can do; writing tool schemas requires framework knowledge.

## The secrets model

Secret NAMES are declared in `connection.yaml`. Secret VALUES live in `secrets.env`, gitignored, never leaving the machine.

The agent knows `STRIPE_API_KEY` exists and writes `os.environ["STRIPE_API_KEY"]` in scripts, but can never read the value: values are injected as environment variables at execution time and scrubbed from the script's output before the agent sees it. The `write_file` tool refuses to touch `secrets.env`.

This is the invariant that never changes: secrets never enter the context window. Names are visible, values are local, injected at runtime, scrubbed from output.

## One server, one URL

`gcontext up` serves the folder at one local HTTP URL. Every client connects to that URL. There is no stdio mode.

The first MCP version used stdio, and a day of real use produced a catalog of failures with one root cause: stdio inverts the mental model. There is no "server running"; every client silently spawns its own private copy from a long registration command. Commands paste-truncate silently and fail minutes later as a bare "not connected". "Is it connected?" has no answer without scanning config files across clients and scopes. People run the server by hand, see it "hang", and assume it is broken.

With one server at a URL: connecting is pasting a URL, which cannot half-truncate into something that almost works. Up or down is observable; Ctrl+C revokes access everywhere at once. Because all clients share the server, the server knows who is connected (the MCP handshake carries `clientInfo`, and `gcontext status` shows it). And local vs deployed becomes "local URL vs remote URL", the same shape.

Rejected along the way: per-client adapters that write each client's config (scope creep into files gcontext doesn't own), a machine-wide agent name registry (another layer of state; the URL already is the handle), and config-scanning diagnostics (detective work compensating for a transport that hides the truth).

The accepted tradeoff: something must be running.

## The context ledger: everything pushed is declared

Every pipe that inserts context into the agent is enumerated in one ledger, computed live from the folder so it cannot go stale. Each pipe is marked `loaded` (pushed at connect), `on demand` (agent pulls it via a visible tool call), `skipped` (nothing to push), or `uncontrolled` (runtime-owned, outside gcontext's view). The ledger appears in `gcontext context`, after `connect`, and in the dashboard.

What gcontext pushes at connect, through the MCP handshake's `instructions` field, is two layers with two owners: the framework's own instructions (`prompts/framework-instructions.md` inside the package, ledger pipe G0) followed by the project's `agent.md` (ledger pipe G1). The framework layer explains gcontext itself: the tools, connections, modules, scripts, archive. It ships with the package, so users cannot edit it and it never goes stale in old projects. The project layer is the agent's definition, one file in the folder, versioned with git. Edit it and you have edited what every future session starts with.

This position was reached in three steps. The handshake push was first rejected outright, on the argument that content arriving through a side channel is invisible in the conversation. Living with the alternative showed the real cost: the agent started blind, had to be told to read its own instructions, and a runtime that never asked never saw them. The rejection was aimed at the wrong target. The problem was never pushing at connect; it was pushing without declaring. So the invariant is: everything pushed is declared in the ledger, and everything declared is enumerable. The third step separated the owners. Originally `init` seeded each project's instructions file with the framework mechanics, which mixed two voices in one user-editable file and froze framework text at whatever version `init` ran; splitting the layers keeps the user file pure agent definition (the seed is a three-line placeholder) and the framework text current with the installed package.

The ledger is also honest about its limits. When a runtime keeps pipes gcontext cannot close (its own system prompt, its config files, other MCP servers), the ledger marks them UNCONTROLLED instead of pretending the session is cleaner than it is.

## Archive: a location, not metadata

State accumulates until it pollutes the context and the agent can't find the right thing. The rejected fix was a `surface: active | background | archived` field with agent-driven housekeeping and staleness hints: too much magic. gcontext must have no background or automatic behaviors; humans must always see how state is controlled.

So visibility is a function of file location. Move a folder into `archive/` and it stops being scanned, while staying readable by path, and every summary mentions what's archived so nothing disappears silently. A folder move is an action everyone understands, is visible in git, and cannot happen behind anyone's back. gcontext never moves, archives, or deletes anything on its own.

## Scripts and commands: knowledge that graduated

Two features share one idea: when the agent produces something that works, keep it as a file next to the knowledge it belongs to, and reuse it instead of regenerating it.

A **saved script** is a proven procedure under a `scripts/` folder, run by path through `run_script` (with `args` and named `params` that arrive as `PARAM_<NAME>` env vars). Ad-hoc source goes through the separate `run_adhoc_script` tool; the split keeps a script invocation short and readable in the runtime's tool display, where inline source renders as an escaped blob. Both tools return readable text: a status line carrying the structured facts (exit code, duration, timed out / truncated), then stdout, stderr, and a hint on a missing import. Internally the execution layer produces a dict; the server renders it to text and deliberately does not declare it as MCP structured content, because runtimes that receive structured content display the JSON instead of the text block, and script output then renders with escaped newlines. Writing a script is an ordinary `write_file` call, visible like every other state change.

A **write** is always user-approved and auditable. The framework instructions require the agent to present every `write_file` call before making it (target path, one-line reason, the content or the changed lines), through the runtime's interactive question tool when it has one, otherwise as a plain-text approval frame. Updating an existing file returns a unified diff of the change (capped at 200 lines) so the write is auditable in the transcript afterwards; creating a file returns its size and line count. The approval lives in the instructions, not in the server: gcontext has no interaction channel of its own, so the server's contribution is the diff, and the asking is agent behavior.

A **command** is a user-invokable entry point under a `commands/` folder, registered as an MCP prompt and surfaced by Claude Code as a slash command. The prompt name is the file stem with hyphens as underscores when that short name is unique; it becomes `<owner>__<command>` when two owners collide (all colliders get the prefix) or when the stem matches a framework prompt name, because a short name is what keeps the command findable in the client's picker. Commands are prompts, not tools, on purpose: a tool's schema is pushed into context at connect time for every session, while a prompt is only listed, and its text enters the conversation exactly when the user invokes it. That keeps the tool list at six and honors the no-invisible-push rule: the injection is user-triggered and the ledger lists commands as their own pipe.

One command is framework-owned: `setup`, shipped in the package's `prompts/` and registered in every instance. Setup is a prompt rather than a CLI command because its work is a conversation, not a procedure: the agent inspects the state, asks the user what they want (a new connection, a new module, a health check), and does the work through the ordinary tools, where every write lands in the event feed. The CLI keeps lifecycle and inspection commands that work without an agent connected: `init`, `up`, `status`, `connect`, `context`, `add`, `share`, `update`, `search`.

## Deferred, deliberately

- **Remote variant**: same model, URL plus token, for a served-anywhere agent. The URL transport is the bridge to it.
- **Triggers/watchers**: something that pokes a runtime when state changes. Even then, gcontext would trigger a runtime, never run the loop.
- **Flows**: an earlier release shipped declarative multi-step work (steps declaring `needs`/`produces` files, status computed from the filesystem). It was removed because no real process ever needed it: a module with a steps file, entered through a command, covered every case that came up. The idea returns only if a real recurring process appears that modules plus commands cannot express, and it will be designed against that process.

## Principles

1. **Feed runtimes, never be one.**
2. **A folder is a folder.** No types, no manifests, no classification.
3. **Config and content are separate concerns.** YAML is data, markdown is context, Python is behavior.
4. **Static metadata, dynamic execution.** Everything is inspectable without running anything; scripts run only when explicitly invoked.
5. **The agent is already smart, it just needs the right information.** Good context plus usable credentials beats pre-built tools.
6. **Secrets never enter the context window.**
7. **Everything pushed is declared.** Every piece of context is a file in the folder reaching the agent through a ledger-declared pipe, a visible tool result, or explicitly listed as runtime-owned.
8. **Status is a pure function of the filesystem.** Flow progress, archive visibility, connection readiness: all derived from files on read, never stored and synced.
9. **Honesty over the illusion of control.** Uncontrolled pipes are labeled uncontrolled.
