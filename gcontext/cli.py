"""gcontext CLI. One server you start, clients connect to its URL. State is files."""

import argparse
import json
import os
import re
import shutil
import socket
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import __version__
from . import commands as commands_mod
from . import exec as exec_mod
from . import ledger as ledger_mod
from . import secrets as secrets_mod
from . import server
from . import state

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

DEFAULT_PORT = 4242
PORT_LOCKFILE = ".gcontext-port"

# The reload rule from docs/setup-script.md: one wording, reused everywhere.
RESTART_RULE = ("Run `gcontext reload`, then reconnect in your client (`/mcp` in Claude Code) "
                "if it reports a reconnect is needed. If the server is stopped: `gcontext up`.")

STATUS_COLOR = {
    "loaded": GREEN,
    "on demand": DIM,
    "skipped": DIM,
    "uncontrolled": YELLOW,
}


def print_ledger(project_dir: Path):
    for i, pipe in enumerate(ledger_mod.build(project_dir), 1):
        color = STATUS_COLOR.get(pipe["status"], "")
        label = f"{pipe['label']} ".ljust(36, ".")
        status = pipe["status"].upper() if pipe["status"] == "uncontrolled" else pipe["status"]
        print(f"  {i}. [{pipe['id']}] {label} {color}{status}{RESET} {DIM}{pipe['detail']}{RESET}")


INIT_INSTRUCTIONS = """\
# Agent

Describe what this agent is for and how it should behave. This file is yours;
gcontext pushes it to every runtime that connects, right after its own fixed
framework instructions (which already cover the tools, connections,
modules, and agents).
"""

INIT_SECRETS = """\
# Secret VALUES live here and never leave this machine (this file is gitignored).
# EXAMPLE_API_KEY=...
"""

INIT_AGENT_GITIGNORE = """\
secrets.env
.venv/
.venv-sync.lock
"""

INIT_README = """\
# {name}

This folder is the state of a [gcontext](https://pypi.org/project/gcontext-ai/)
agent: everything it knows lives here as plain files.

Run it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # once: uv, which gcontext needs at runtime
uv tool install gcontext-ai                       # once
gcontext up .                 # from this folder (or: gcontext up <path> from anywhere)
```

The server prints a URL and the one-line command to connect your client
(Claude Code, Claude Desktop, Codex, Cursor). The client does the reasoning;
this folder is the memory.

Three ideas cover the folder:

- Memory: the agent's files. `agent.md` is its definition, pushed to every
  client at connect; `modules/` holds knowledge by topic; `archive/` holds
  retired state; installed agents live in `agents/` and bring their own
  commands.
- Reach: `connections/` holds the services the agent can use; `secrets.env`
  holds the secret values. It is gitignored and never leaves this machine.
- Steering: commands (slash commands in your client) and resources (state
  files you attach to a message).
"""

def cmd_init(args):
    target = Path(args.directory).resolve()
    if target.exists() and any(target.iterdir()):
        print(f"Error: {target} already exists and is not empty.", file=sys.stderr)
        sys.exit(1)

    name = target.name
    install_id = str(uuid.uuid4())
    files = {
        "README.md": INIT_README.format(name=name),
        "agent.md": INIT_INSTRUCTIONS,
        "secrets.env": INIT_SECRETS,
        ".gitignore": INIT_AGENT_GITIGNORE,
        "connections/.gitkeep": "",
        "modules/.gitkeep": "",
        "agents/.gitkeep": "",
        "archive/.gitkeep": "",
    }
    for rel, content in files.items():
        f = target / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

    (target / "secrets.env").chmod(0o600)

    from gcontext.telemetry import ping_install
    ping_install(install_id, __version__)

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} created {name}")
    print(f"{DIM}State: {target}{RESET}")
    print()
    print("The folder is the agent's Memory: plain files, version it with git, edit it freely.")
    print("Reach (connections plus secrets) and Steering (commands and resources) come next:")
    print("the setup command builds them with you.")
    if os.environ.get("GCONTEXT_TELEMETRY") != "0":
        print(f"{DIM}Sent anonymous install event. Disable with GCONTEXT_TELEMETRY=0{RESET}")
    print()
    pad = min(max(len(f"gcontext up {args.directory}"), len(f"/mcp__{name}__setup")) + 4, 44)
    print("Steps:")
    print(f"  1. {f'gcontext up {args.directory}':<{pad}}  start the server")
    print(f"  2. {'connect your client':<{pad}}  the up banner prints the exact command per client")
    print(f"  3. {f'run /mcp__{name}__setup':<{pad}}  in the client: describe what the agent should do, it builds the rest")


def find_project_dir(path: str | None) -> Path:
    p = Path(path).resolve() if path else Path.cwd().resolve()
    if p.is_dir():
        return p
    print(f"Error: project folder does not exist: {p}", file=sys.stderr)
    sys.exit(1)


def resolve_port(args, project_dir: Path) -> int:
    if getattr(args, "port", None):
        return args.port
    env = os.environ.get("GCONTEXT_PORT")
    if env:
        try:
            return int(env)
        except ValueError:
            print(f"Error: GCONTEXT_PORT='{env}' is not a valid number.", file=sys.stderr)
            sys.exit(1)
    lockfile = project_dir / PORT_LOCKFILE
    if lockfile.exists():
        try:
            return int(lockfile.read_text().strip())
        except (ValueError, OSError):
            pass
    return DEFAULT_PORT


def write_port_lockfile(project_dir: Path, port: int) -> None:
    (project_dir / PORT_LOCKFILE).write_text(str(port))


def remove_port_lockfile(project_dir: Path) -> None:
    lockfile = project_dir / PORT_LOCKFILE
    if lockfile.exists():
        lockfile.unlink()


def server_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/mcp"


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_free_port(start: int, attempts: int = 50) -> int:
    for port in range(start, start + attempts):
        if port_is_free(port):
            return port
    print(f"Error: no free port found in {start}-{start + attempts - 1}.", file=sys.stderr)
    sys.exit(1)


def fetch_status(port: int) -> dict | None:
    """Query the running server. None means nothing is listening."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def post_reload(port: int) -> dict | None:
    """POST /api/reload on the running server. None means nothing is listening."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/reload", method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"error": f"server returned HTTP {e.code}"}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def format_reload_report(report: dict) -> list[str]:
    """Render the /api/reload report in the house style. Pure, for tests."""
    if report.get("error"):
        return [
            f"Error: {report['error']}",
            "The server kept its previous state. Fix the file and run gcontext reload again.",
        ]
    lines = [
        f"Reloaded: {report.get('framework_prompts', 0)} built-in + "
        f"{report.get('project_commands', 0)} project command(s) re-registered."
    ]
    if report.get("removed"):
        lines.append(f"Removed: {', '.join(report['removed'])}")
    if report.get("added"):
        lines.append(f"Added: {', '.join(report['added'])}")
    if report.get("agent_md_changed"):
        lines.append("agent.md: reloaded, delivered to clients at their next connect.")
    server_version = report.get("version")
    if server_version and server_version != __version__:
        lines.append(
            f"Warning: the server runs gcontext {server_version} but "
            f"{__version__} is installed. A full restart is required to run "
            "the installed version (stop, gcontext up)."
        )
    if report.get("client_reconnect_needed"):
        lines.append("Reconnect your client to pick this up (/mcp in Claude Code).")
    else:
        lines.append("Live now.")
    return lines


def cmd_reload(args):
    project_dir = find_project_dir(args.project)
    port = resolve_port(args, project_dir)
    live = fetch_status(port)
    if live is None:
        print(f"Server not running. Start it: gcontext up {args.project or '.'}", file=sys.stderr)
        sys.exit(1)
    if live.get("project_dir") != str(project_dir.resolve()):
        print(f"Error: port {port} is serving a different project "
              f"({live.get('name', '?')} at {live.get('project_dir', '?')}).", file=sys.stderr)
        sys.exit(1)
    report = post_reload(port)
    if report is None:
        print(f"Server not running. Start it: gcontext up {args.project or '.'}", file=sys.stderr)
        sys.exit(1)
    for line in format_reload_report(report):
        print(line)
    if report.get("error"):
        sys.exit(1)


def cmd_up(args):
    project_dir = find_project_dir(args.project)
    server.PROJECT_DIR = project_dir
    name = project_dir.name
    port = resolve_port(args, project_dir)

    if not port_is_free(port):
        running = fetch_status(port)
        who = f" ({running.get('name', '?')} serving {running.get('project_dir', '?')})" if running else ""
        if getattr(args, "port", None):
            print(f"Error: port {port} (from --port) is already in use{who}.", file=sys.stderr)
            print("Free it, or pick another port with --port.", file=sys.stderr)
            sys.exit(1)
        chosen = find_free_port(port + 1)
        print(f"{YELLOW}{BOLD}Port {port} is taken{who}.{RESET}")
        print(f"{YELLOW}{BOLD}Using port {chosen} instead.{RESET}")
        print()
        port = chosen

    url = server_url(port)

    exec_mod.ensure_venv(project_dir)
    n_framework_prompts = server.register_framework_prompts()
    n_commands = server.register_commands()
    n_base_lines, n_instruction_lines = server.load_instructions()
    server.snapshot_startup_files()
    server.freeze_boot_prompts()

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} serving {name} {DIM}({__version__}){RESET}")
    print(f"{DIM}State: {project_dir}{RESET}")
    print()
    print(f"Serving at {BOLD}{url}{RESET}")
    print()
    env_file = project_dir / "secrets.env"
    if env_file.exists() and (env_file.stat().st_mode & 0o077):
        print(f"{DIM}note: secrets.env is readable by other users on this machine; consider: chmod 600 secrets.env{RESET}")
        print()

    print("Connect a client (once per client, works from any directory):")
    print(f"  Claude Code:     claude mcp add --transport http {name} {url}")
    print(f"  Claude Desktop:  Settings -> Connectors -> Add custom connector -> {url}")
    print(f'  Cursor:          "{name}": {{"url": "{url}"}} in ~/.cursor/mcp.json')
    print(f'  Codex:           [mcp_servers.{name}] url = "{url}" in ~/.codex/config.toml')
    print("  Details:         gcontext connect")
    print()
    if n_instruction_lines:
        print(f"Memory: framework instructions ({n_base_lines} lines) + agent.md ({n_instruction_lines} lines), pushed to every client at connect.")
    else:
        print(f"{YELLOW}Memory: no agent.md, clients receive only the framework instructions ({n_base_lines} lines) at connect.{RESET}")
    n_connections = len(state.load_connections(project_dir))
    if n_connections:
        print(f"Reach: {n_connections} connection(s); check their secrets with gcontext status.")
    else:
        print("Reach: no connections yet; the setup command adds them.")
    n_agents = len(state.discover_agents(project_dir))
    if n_agents:
        print(f"Agents: {n_agents} installed")
    builtin_names = ", ".join(p.stem for p in commands_mod.discover_framework_prompts())
    prompt_bits = [f"{n_framework_prompts} built-in commands ({builtin_names})"]
    if n_commands:
        prompt_bits.append(f"{n_commands} project command(s)")
    print(f"Steering: {' + '.join(prompt_bits)}, slash commands in your client.")
    print()
    print("Clients appear below as they connect. Ctrl+C stops the server,")
    print("and every client cleanly loses access.")
    print()
    print("Next: connect your client with the command above (already connected: /mcp to reconnect).")
    print()

    write_port_lockfile(project_dir, port)
    try:
        server.mcp.run(
            transport="http", host="127.0.0.1", port=port, path="/mcp",
            show_banner=False, log_level="warning", stateless_http=True,
        )
    finally:
        remove_port_lockfile(project_dir)


def cmd_status(args):
    project_dir = find_project_dir(args.project)

    connections = state.load_connections(project_dir)
    modules = state.discover_modules(project_dir)
    agents = state.discover_agents(project_dir)
    port = resolve_port(args, project_dir)

    name = project_dir.name
    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} status of {name}")
    print(f"{DIM}State: {project_dir}{RESET}")
    print()

    needs_restart = False
    live = fetch_status(port)
    if live is None:
        print(f"Server: {YELLOW}not running{RESET} {DIM}(start it: gcontext up){RESET}")
    elif live.get("project_dir") != str(project_dir.resolve()):
        print(f"Server: {YELLOW}port {port} is serving a different project{RESET}")
        print(f"  {DIM}{live.get('name', '?')} at {live.get('project_dir', '?')}{RESET}")
    else:
        print(f"Server: {GREEN}up{RESET} at {server_url(port)}")
        sessions = live.get("sessions", [])
        if not sessions:
            print(f"  {DIM}no client connected yet{RESET}")
        for s in sessions:
            print(f"  {GREEN}{s['client']}{RESET} {DIM}{s['version']}{RESET}  connected {s['connected']}  last activity {s['last_seen']}")
        stale = live.get("stale") or {}
        if stale.get("agent_md"):
            print(f"  {YELLOW}agent.md changed since server start; run gcontext reload to push the new version{RESET}")
        if stale.get("commands"):
            print(f"  {YELLOW}commands changed since server start; run gcontext reload to re-register them{RESET}")
        needs_restart = bool(stale.get("agent_md") or stale.get("commands"))
    print()

    instructions = project_dir / "agent.md"
    if instructions.exists():
        lines = len(instructions.read_text().splitlines())
        print(f"Instructions: agent.md ({lines} lines)")
        print()

    print("Connections:")
    if not connections:
        print(f"  {DIM}none defined{RESET}")
    for cname in connections:
        print(f"  {cname}")
    print()

    if modules:
        print("Modules:")
        for mname, mod in modules.items():
            suffix = f" {DIM}- {mod.description}{RESET}" if mod.description else ""
            print(f"  {mname}{suffix}")
        print()

    if agents:
        print("Agents:")
        for aname, agent in agents.items():
            suffix = f" {DIM}- {agent.description}{RESET}" if agent.description else ""
            print(f"  {aname}{suffix}")
        print()

    archived_line = state.archived_line(project_dir)
    if archived_line:
        print(f"{DIM}{archived_line}{RESET}")
        print()

    print(f"{DIM}No runtime included. Point any MCP client at the URL above.{RESET}")
    if needs_restart:
        print()
        print(f"Next: {RESTART_RULE}")


def cmd_connect(args):
    project_dir = find_project_dir(args.project)
    name = project_dir.name
    port = resolve_port(args, project_dir)
    url = server_url(port)

    live = fetch_status(port)
    if live is None:
        print(f"{YELLOW}Server not running.{RESET} Start it first, in this or another terminal:")
        print()
        print(f"  gcontext up {project_dir}")
        print()

    client = args.client

    if client == "claude":
        print(f"{BOLD}Claude Code{RESET}")
        print()
        print("Run once, from the directory where you use claude (or add --scope user")
        print("to make it available everywhere):")
        print()
        print(f"  claude mcp add --transport http {name} {url}")

    elif client == "desktop":
        print(f"{BOLD}Claude Desktop{RESET}")
        print()
        print("Settings -> Connectors -> Add custom connector, then paste:")
        print()
        print(f"  {url}")

    elif client == "codex":
        print(f"{BOLD}Codex{RESET}")
        print()
        print("Add to ~/.codex/config.toml:")
        print()
        print(f"[mcp_servers.{name}]")
        print(f'url = "{url}"')

    elif client == "cursor":
        print(f"{BOLD}Cursor{RESET}")
        print()
        print("Add to .cursor/mcp.json (project) or ~/.cursor/mcp.json (global):")
        print()
        print(json.dumps({"mcpServers": {name: {"url": url}}}, indent=2))

    else:
        print(f"{BOLD}Any MCP client{RESET}")
        print()
        print("gcontext speaks MCP over streamable HTTP. Point your client at:")
        print()
        print(f"  {url}")

    print()
    print("Context this client will receive:")
    print_ledger(project_dir)
    print()
    print(f"{DIM}Verify anytime with: gcontext status{RESET}")


def cmd_context(args):
    project_dir = find_project_dir(args.project)
    name = project_dir.name

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} {name}")
    print(f"{DIM}Every pipe that inserts context into an attached agent.{RESET}")
    print()
    print_ledger(project_dir)


def cmd_statusline(args):
    project_dir = find_project_dir(args.project)
    port = resolve_port(args, project_dir)
    status = fetch_status(port)
    use_color = getattr(args, "color", False)
    print(server.format_statusline(status, color=use_color))


def main():
    parser = argparse.ArgumentParser(
        prog="gcontext",
        description="Agent state in a folder, served at a URL. Bring your own runtime.",
    )
    parser.add_argument("--version", action="version", version=f"gcontext {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Scaffold a new agent state folder")
    init_parser.add_argument("directory", help="Directory to create (its name becomes the agent name)")

    def add_common(p):
        p.add_argument("project", nargs="?", help="Path to gcontext project directory")
        p.add_argument("--port", type=int, help=f"Server port (default: {DEFAULT_PORT})")

    up_parser = subparsers.add_parser("up", help="Start the server. Clients connect to its URL")
    add_common(up_parser)

    status_parser = subparsers.add_parser("status", help="Server up? Who is connected? Plus connections, secrets, modules")
    add_common(status_parser)

    reload_parser = subparsers.add_parser("reload", help="Apply agent.md and command edits to the running server")
    add_common(reload_parser)

    connect_parser = subparsers.add_parser("connect", help="Show how to point a client at the server URL")
    connect_parser.add_argument(
        "client",
        nargs="?",
        default="generic",
        choices=["claude", "desktop", "codex", "cursor", "generic"],
        help="Which MCP client to show instructions for",
    )
    add_common(connect_parser)

    context_parser = subparsers.add_parser("context", help="Show the context ledger: every pipe into the agent, per mode")
    add_common(context_parser)

    statusline_parser = subparsers.add_parser("statusline", help="One-line server state for Claude Code statusline or claude-hud")
    add_common(statusline_parser)
    statusline_parser.add_argument("--color", action="store_true", help="Enable ANSI color codes in output")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "up": cmd_up,
        "status": cmd_status,
        "reload": cmd_reload,
        "connect": cmd_connect,
        "context": cmd_context,
        "statusline": cmd_statusline,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
