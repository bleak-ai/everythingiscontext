# prompts/

Everything gcontext itself says to an attached agent lives in this folder,
as markdown, not in Python strings.

- `tools/*.md`: one file per tool. These are the tool descriptions pushed to
  every client at connect time (ledger pipe G1). Edit a file, restart the
  server, and every session sees the new text.

The instructions an agent receives at connect are NOT here: they are the
served project's own `instructions.md`, pushed through the MCP handshake and
declared as ledger pipe G0. That file belongs to the agent folder (versioned
with its state), not to the framework; this folder only holds the fixed
framework text.
