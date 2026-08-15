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
- `setup.md`: the built-in `setup` prompt, registered as an MCP prompt in
  every instance (part of ledger pipe G6, `/mcp__<server>__setup` in Claude
  Code). Same frontmatter format as project commands, but framework-owned
  and shipped with the package. It follows the setup script standard
  (`docs/setup-script.md`): the code-built report opens the dialogue, then
  plan, questions one at a time, build progress, examples, one Next line.
  Its text enters context only when invoked.
- `explain.md`: the built-in `explain` prompt. Explains an installed agent:
  the code-built Does / Connects / Learns / Flow report, then the model
  walks the flow. Without an agent id it shows the agent list.
- `ask.md`: the built-in `ask` prompt. Loads the agent's context and
  answers a question using its state.
- `agents.md`: the built-in `agents` prompt. Browse, install, and update
  agents from the registry.

The wording of the code-built reports (the setup report and the explain
report) is not in this folder: it lives in `gcontext/report_strings.py`,
strings only, imported by `report.py`, which owns the computation and the
layout. Edit report wording there; everything conversational stays here.

The agent's own definition is NOT here: it is the served project's
`agent.md`, appended after the framework instructions in the same
handshake and declared as ledger pipe G1. That file belongs to the agent
folder (versioned with its state) and holds only the user's voice; `init`
seeds it with a three-line placeholder.

History: earlier versions deliberately had no server-side instructions file
and seeded all mechanics into each project's agent file. That mixed two
owners in one file and let framework text go stale per project, so the split
above replaced it (2026-08-01).
