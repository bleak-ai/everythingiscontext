# Troubleshooting

One symptom per heading. Each entry quotes the exact text you see, explains the cause, and lists the fix.

## `gcontext up` reports the port is taken

Without a configured port, the server picks the next free one and tells you:

```
Port 4242 is taken (other-agent serving /path/to/other-agent).
Using port 4243 instead. Saved port: 4243 to gcontext.yaml so this URL stays stable.
```

This is not an error. But your URL changed, so a client added with the old port will not connect; use the URL from the banner.

When the port came from `--port` or from a `port:` line in `gcontext.yaml`, the server refuses instead of picking another, so a URL you chose stays yours:

```
Error: port 4242 (from gcontext.yaml) is already in use (other-agent serving /path/to/other-agent).
Free it, or pick another port with --port.
```

Cause: another process, often another gcontext server, is bound to the port.

1. Find out who has it: `gcontext status` in the other project, or `lsof -i :4242`.
2. Stop that process, or start this server with `gcontext up --port <other>`.
3. Reconnect clients if the URL changed.

## `command not found: gcontext` after install

```
zsh: command not found: gcontext
```

Cause: `uv tool install` places binaries in uv's tool bin directory (usually `~/.local/bin`), and that directory is not on your PATH, or the shell has not picked up the change yet.

1. Run `uv tool install gcontext-ai` if you have not installed it.
2. Run `uv tool update-shell` to add the tool bin directory to your PATH.
3. Open a new terminal (or `source` your shell rc file) and retry.

If `uv` itself is not found, install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.

## The client cannot connect to the URL

The client reports a connection failure for `http://127.0.0.1:<port>/mcp`.

Cause: the server is not running, or it is running on a different port than the client was configured with (see the port entry above: an auto-picked port is saved to `gcontext.yaml`, so the URL can differ from the default).

1. Run `gcontext status` in the project. If it prints `Server: not running (start it: gcontext up)`, start it: `gcontext up <dir>`.
2. Compare the URL in the up banner (`Serving at http://127.0.0.1:<port>/mcp`) with the URL your client uses.
3. If they differ, re-add the connection with the banner's URL. `gcontext connect <client>` prints the exact command.

Note the server binds `127.0.0.1`: it is reachable only from the same machine. That is by design.

## A script fails because a secret has no value

The script result shows the failure in its stderr block, for example:

```
[exit 1 | 42 ms]
[stderr]
...
KeyError: 'STRIPE_API_KEY'
```

Cause: the connection declares the secret name in `connection.yaml`, but `secrets.env` has no value for it. The server injects only names that have values; the script's `os.environ["NAME"]` lookup then fails.

1. Run `gcontext status`. A connection with unfilled secrets shows: `stripe: missing STRIPE_API_KEY`.
2. Add the value to `secrets.env` at the project root: `STRIPE_API_KEY=sk_...`.
3. Rerun the script. `secrets.env` is read per run, so nothing needs a reload or restart.

## A command does not appear in the slash command list

Three causes, in order of likelihood:

1. **The server has not registered it yet.** Command files load at server start; `gcontext status` tells you when they changed since:

   ```
   commands changed since server start; run gcontext reload to re-register them
   ```

   Run `gcontext reload`.

2. **The client has a stale prompt list.** After a reload that added or removed commands, the reload output ends with:

   ```
   Reconnect your client to pick this up (/mcp in Claude Code).
   ```

   Type `/mcp` in Claude Code and reconnect the server.

3. **The command is off in `controls.yaml`.** The up banner counts these: `2 off in controls.yaml`. Open `controls.yaml`, find the `<owner>/<stem>` line under `commands:`, set it to `on`, then `gcontext reload` and reconnect.

The full table of which change needs a reload or a reconnect is in [using.md](using.md#what-needs-a-reload-what-needs-a-reconnect).

Also check the server terminal: a malformed command file is skipped loudly, for example:

```
! skipping command <path>: missing frontmatter: file must start with ---
```

## The server refuses to start over `controls.yaml`

```
Error: controls.yaml is not valid YAML: ...
Fix controls.yaml and run gcontext up again.
```

Other variants of the first line, depending on the mistake: `controls.yaml must be a YAML mapping`, `'commands' must be a mapping of key: on|off`, `'commands' entry '<key>' must be on or off, got ...`, `'pinned' must be a list`.

Cause: `controls.yaml` is the on/off registry for everything the server exposes, and the server fails loud at startup rather than guessing. On an already running server the same problem is softer: the terminal prints `keeping the last good controls state` and `gcontext reload` reports the error and changes nothing.

1. Open `controls.yaml` and fix the reported line. Values are `on` or `off`.
2. Run `gcontext up` again (or `gcontext reload` if the server is running).

## Edits to `agent.md` do not reach the agent

You changed `agent.md` and the connected session still behaves like before.

Cause: `agent.md` is delivered inside the MCP connect handshake, so it takes both a reload and a reconnect. `gcontext status` reminds you:

```
agent.md changed since server start; run gcontext reload to push the new version
```

1. Run `gcontext reload`. It confirms: `agent.md: reloaded, delivered to clients at their next connect.`
2. Reconnect the client: `/mcp` in Claude Code.

The full table of which change needs which step is in [using.md](using.md#what-needs-a-reload-what-needs-a-reconnect).

## `gcontext reload` warns about a version mismatch

```
Warning: the server runs gcontext 0.12.0 but 0.12.1 is installed. A full restart is required to run the installed version (stop, gcontext up).
```

Cause: you updated the gcontext package while a server started by the older version was still running. Reload re-reads state files, but it cannot swap the running code.

1. Stop the server (Ctrl+C in its terminal).
2. Start it again: `gcontext up <dir>`.
3. Reconnect the client: `/mcp` in Claude Code.
