# prompts/

Everything gcontext itself says to an attached agent lives in this folder,
as markdown, not in Python strings.

- `framework-instructions.md`: the framework's own instructions, always pushed first in
  the MCP handshake (ledger pipe G0). What gcontext is, the tools, and how
  connections/modules/scripts/archive work. Framework-owned: users cannot
  edit it, and it updates with the package, so it never goes stale in old
  projects.
- `tools/*.md`: one file per tool. These are the tool descriptions pushed to
  every client at connect time (ledger pipe G2). Edit a file, restart the
  server, and every session sees the new text.
- `resources.md`: the description of the `gcontext://<path>` resource
  template, which exposes every state file as an MCP resource (ledger pipe
  G7).
- `setup.md`: the built-in `setup` prompt, registered as an MCP prompt in
  every instance (part of ledger pipe G6, `/mcp__<server>__setup` in Claude
  Code). Same frontmatter format as project commands, but framework-owned
  and shipped with the package. It guides the agent through adding a
  connection, adding a module, or health-checking the state, conversationally
  and through the normal tools. Its text enters context only when invoked.

The agent's own definition is NOT here: it is the served project's
`agent.md`, appended after the framework instructions in the same
handshake and declared as ledger pipe G1. That file belongs to the agent
folder (versioned with its state) and holds only the user's voice; `init`
seeds it with a three-line placeholder.

History: earlier versions deliberately had no server-side instructions file
and seeded all mechanics into each project's agent file. That mixed two
owners in one file and let framework text go stale per project, so the split
above replaced it (2026-08-01).
