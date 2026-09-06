# MCP in one page

MCP (Model Context Protocol) is an open standard for connecting AI clients to external systems. A program called an MCP server exposes capabilities over a simple protocol; clients like Claude Code, Claude Desktop, Codex, and Cursor speak it natively.

A server exposes three kinds of things:

- **Tools**: functions the model can call, with typed arguments and a result.
- **Resources**: pieces of content, each with a URI, that the user or client can attach to the conversation.
- **Prompts**: pre-written message templates the user invokes; Claude Code surfaces them as slash commands.

gcontext is one MCP server per project folder. It uses tools for state access (`read_file`, `write_file`, `list_dir`, `grep`, the script runners, `agent`), resources to make every state file attachable (`gcontext://<path>`), and prompts for commands. The server also pushes instructions to every client in the connect handshake.

Start the server with `gcontext serve [dir]`. See [tools.md](tools.md) for the full tool list.

The protocol itself, the spec, and the client list live at [modelcontextprotocol.io](https://modelcontextprotocol.io).
