# Reference

Details on secrets, commands, the dashboard, archiving, the context ledger, and controlled sessions.

## Secrets

`connection.yaml` declares secret names; `secrets.env` holds the values. When the agent calls `run_script` or `run_adhoc_script`, the values are injected as environment variables and scrubbed from the script's output. The agent can know that `STRIPE_API_KEY` exists and use it in a script, but never reads the value. `secrets.env` is gitignored by `init` and the `write_file` tool refuses to touch it.

One honest caveat: `secrets.env` is plain text on disk. gcontext never shows
values to the agent, but any other program with filesystem access, including
your AI client's own file tools, can read the file directly. `init` creates it
with mode 600 and gitignores it. If your client supports permission rules,
deny it read access to `secrets.env` as well.

Both tools execute Python in a per-project venv with each connection's declared deps preinstalled (via uv).

## Commands

A command is a user-invokable entry point stored next to the knowledge it belongs to: a file under `connections/<name>/commands/` or `modules/<name>/commands/`. The server registers each one as an MCP prompt named after the file stem (hyphens as underscores); Claude Code shows it as a slash command (`/mcp__<server>__<command>`). When two owners ship the same stem, or the stem matches a framework prompt name, the name becomes `<owner>__<command>` instead. Prompts cost no tool-schema context: a command's text enters the conversation only when you invoke it.

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

## Archiving

When old modules or connections start cluttering the context, move them:

```bash
mv my-agent/modules/old-onboarding my-agent/archive/modules/
```

Anything under `archive/` is skipped when scanning, but stays readable by path, and summaries mention what's archived so it doesn't silently vanish. That's the entire mechanism. gcontext never moves, archives, or deletes anything on its own.

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
