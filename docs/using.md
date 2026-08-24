# Using an agent day to day

You have a folder served by `gcontext up` and a client connected to its URL. This page covers the everyday moves: invoking commands, attaching files, knowing when a change needs a reload or a reconnect, template commands, and installing agents from the registry.

## Invoke a command

Commands are files under a `commands/` folder inside a connection, module, or installed agent. The server registers each one as an MCP prompt; Claude Code shows it as a slash command with the full form:

```
/mcp__<server>__<command>
```

`<server>` is the name you gave the server when you connected the client (usually the folder name). `<command>` is the file stem with hyphens turned into underscores. For a freshly scaffolded project named `my-agent`, the built-in setup command is:

```
/mcp__my-agent__setup
```

Naming rule: a command keeps its bare stem while that name is unique. When two owners ship the same stem, or the stem matches a framework prompt name (`setup`, `ask`, `explain`, `agents`), every collider registers as `<owner>__<command>` instead. That is why an installed agent's setup command is `/mcp__my-agent__<agent-id>__setup`: `setup` is reserved by the framework.

Invoking a command injects its rendered body into the conversation. Nothing runs in the background; the agent reads the injected text and acts on it.

## Attach a resource

Every state file is also an MCP resource. There are two ways content reaches the agent:

- **Attach**: you mention a resource in your message. Its content enters the context up front, before the agent does anything. Use this when you already know which file matters.
- **read_file**: the agent calls the tool itself, mid-task, when it decides it needs a file. Visible in the transcript as a tool call. Use nothing; this happens on its own.

The resource picker (the `@` menu in Claude Code) shows a curated list of `agent://` entries: the agent root (agent.md plus a map of modules and connections), one entry per module and connection (their index.md), and any files pinned in `controls.yaml`.

Any file can also be attached directly by path with the `gcontext://` form:

```
gcontext://modules/topic/index.md
```

In Claude Code the full mention syntax is `@<server>:<uri>`:

```
@my-agent:gcontext://modules/topic/index.md
```

The dashboard's copy buttons produce exactly this form, so you can browse a file in the dashboard and paste the mention into your client.

## What needs a reload, what needs a reconnect

Most edits are live immediately: the server reads state files on demand. The exceptions load at server start. When you make these edits through the MCP tools (`write_file`, `agent install`, `agent update`), the server reloads itself. You do not run `gcontext reload` for tool-driven edits.

For hand edits outside the tools (editing files with your editor), run `gcontext reload` to apply the changes.

Some changes also need a client reconnect (`/mcp` in Claude Code), because Claude Code reads the prompt list and instructions only at connect time.

| Change | Reload | Client reconnect (`/mcp`) |
|---|---|---|
| Edit `agent.md` | automatic (tool) or `gcontext reload` (hand) | yes (delivered in the MCP handshake) |
| Edit the body of an existing command file | automatic (tool) or `gcontext reload` (hand) | no (the client fetches the body at invocation) |
| Add or remove a command file | automatic (tool) or `gcontext reload` (hand) | yes (the prompt list changed) |
| New template entry created by a `write_file` | automatic | yes |
| Toggle a command in `controls.yaml` | automatic (tool) or `gcontext reload` (hand) | yes (the prompt list changed) |
| Toggle a resource in `controls.yaml` | no (re-read on every listing) | no |
| Change `pinned` in `controls.yaml` | no (re-read on every listing) | no |
| Edit `secrets.env` | no (read per script run) | no |
| Add a connection or module folder | no (scanned per tool call) | no |

### Knowing when to reconnect

The `gcontext statusline` command prints one line for use in Claude Code's statusline or claude-hud:

- `gcontext ok` when everything is current.
- `gcontext: RECONNECT NEEDED FOR <agent> --> /new_cmd , -removed_cmd` when the client is behind.
- `gcontext: STALE, run gcontext reload` when hand edits have not been reloaded.
- `gcontext down` when the server is not running.

Wire it into Claude Code's statusLine setting:

```json
{
  "statusLine": {
    "type": "command",
    "command": "gcontext statusline <project-dir>"
  }
}
```

Add `--color` to enable blue ANSI highlighting for the alert lines.

One case needs a full restart instead of a reload: when the running server was started by an older gcontext version than the one now installed. `gcontext reload` detects this and prints:

```
Warning: the server runs gcontext <old> but <new> is installed. A full restart is required to run the installed version (stop, gcontext up).
```

Stop the server (Ctrl+C), run `gcontext up`, and reconnect the client.

## Template commands

You need this when a folder keeps gaining entries and each entry should get its own slash command.

A `.md` command whose frontmatter declares `each: <glob>` is a template: it registers one command per state folder the glob matches inside its owner. Example: a module keeps writing profiles under `profiles/`, and you want one slash command per profile.

`modules/writer/commands/profile.md`:

```markdown
---
description: Write a post in one profile's voice
each: profiles/*
---
Read modules/writer/profiles/$each/index.md and write the post in that voice.
```

With `profiles/casual/` and `profiles/formal/` on disk, this registers `/mcp__my-agent__profile_casual` and `/mcp__my-agent__profile_formal`. `$each` is bound to the matched folder name; description and parameters can come from frontmatter in the matched folder's own index.md.

Templates re-expand automatically after every `write_file`, so when the agent creates `profiles/direct/`, no reload is needed. The new slash command still needs a client reconnect to show up, because Claude Code ignores the MCP prompt-list-changed notification.

## Install an agent from the registry

Pre-built agents live in the [registry](https://github.com/bleak-ai/agents). Find and install one:

```bash
gcontext search <query>
gcontext add <id>
```

`add` copies the agent's files into `agents/<id>/`, installs any agents it depends on, and reports the connections it needs (existing ones are reused, missing ones are named so you can set them up). It then prints the next steps:

```
Next steps:
  1. Apply it: gcontext reload (server not running: gcontext up .)
  2. Reconnect in your client: type /mcp in Claude Code.
  3. Run the setup: /mcp__<server>__<id>__setup
```

The agent's setup command carries the agent id in its name (`<id>__setup`) because every project also has the framework's own `/mcp__<server>__setup`; the id keeps the two apart. `<server>` is the name from `gcontext.yaml`, the one you gave `gcontext init`.

The setup command personalizes the agent by asking you what it should do. Everything the agent learns while working (runs, logs, harvested data) lands inside its own `agents/<id>/` folder; `gcontext remove <id>` offers to archive those files to `archive/agents/<id>/` before deleting the rest.

The seven tools the agent works with are described in [tools.md](tools.md).
