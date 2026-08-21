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
from . import registry as registry_mod
from . import report_strings
from .kinds import CONNECTION_KINDS
from . import secrets as secrets_mod
from . import server
from . import state

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

DEFAULT_PORT = 4242

# The restart rule from docs/setup-script.md: one wording, reused everywhere.
RESTART_RULE = "Restart the server (stop, `gcontext up`), then reconnect in your client (`/mcp` in Claude Code)."

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


INIT_GCONTEXT_YAML = """\
name: {name}
description: Describe what this agent is for.
install_id: {install_id}
# port: 4242
"""

INIT_INSTRUCTIONS = """\
# Agent

Describe what this agent is for and how it should behave. This file is yours;
gcontext pushes it to every runtime that connects, right after its own fixed
framework instructions (which already cover the tools, connections, and
modules).
"""

INIT_SECRETS = """\
# Secret VALUES live here and never leave this machine (this file is gitignored).
# Each connection's connection.yaml declares which NAMEs it needs.
# EXAMPLE_API_KEY=...
"""

INIT_AGENT_GITIGNORE = """\
secrets.env
.venv/
.venv-sync.lock
.controls.lock
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

What's here: `agent.md` is the agent's definition, pushed to every client at
connect. `connections/` holds the services it can use, `agents/` the autonomous
actors installed from the registry, `modules/` accumulated knowledge by topic,
`archive/` retired state. `secrets.env` holds secret values; it is gitignored
and never leaves this machine, so after cloning, recreate it from the NAMEs
each connection.yaml declares.
"""

def cmd_init(args):
    target = Path(args.directory).resolve()
    if target.exists() and any(target.iterdir()):
        print(f"Error: {target} already exists and is not empty.", file=sys.stderr)
        sys.exit(1)

    name = target.name
    install_id = str(uuid.uuid4())
    files = {
        "gcontext.yaml": INIT_GCONTEXT_YAML.format(name=name, install_id=install_id),
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

    from gcontext import controls
    controls.heal(target)

    from gcontext.telemetry import ping_install
    ping_install(install_id, __version__)

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} created {name}")
    print(f"{DIM}State: {target}{RESET}")
    print()
    print("The folder IS your agent's state: version it with git, edit it freely.")
    if os.environ.get("GCONTEXT_TELEMETRY") != "0":
        print(f"{DIM}Sent anonymous install event. Disable with GCONTEXT_TELEMETRY=0{RESET}")
    print()
    pad = min(max(len(f"gcontext up {args.directory}"), len(f"/mcp__{name}__setup")) + 4, 44)
    print("Steps:")
    print(f"  1. {f'gcontext up {args.directory}':<{pad}}  start the server")
    print(f"  2. {'connect your client':<{pad}}  the up banner prints the exact command per client")
    print(f"  3. {f'run /mcp__{name}__setup':<{pad}}  in the client: describe what the agent should do, it builds the rest")
    print()
    print(f"{DIM}See what reaches the agent, anytime: gcontext context {args.directory}{RESET}")


def find_project_dir(path: str | None) -> Path:
    p = Path(path).resolve() if path else Path.cwd()
    if (p / "gcontext.yaml").exists():
        return p
    print(f"Error: no gcontext.yaml found in {p}", file=sys.stderr)
    print("Run from a gcontext project directory or pass the path as an argument.", file=sys.stderr)
    sys.exit(1)


def resolve_port(args, project_dir: Path) -> int:
    if getattr(args, "port", None):
        return args.port
    config = state.load_gcontext_yaml(project_dir)
    raw = config.get("port", DEFAULT_PORT)
    try:
        return int(raw)
    except (TypeError, ValueError):
        print(f"Error: port value '{raw}' in gcontext.yaml is not a valid number.", file=sys.stderr)
        sys.exit(1)


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


def persist_port(project_dir: Path, port: int):
    """Write port: into gcontext.yaml, replacing an existing (or commented) port line."""
    path = project_dir / "gcontext.yaml"
    lines = path.read_text().splitlines() if path.exists() else []
    out, replaced = [], False
    for line in lines:
        stripped = line.strip()
        if not replaced and (stripped.startswith("port:") or stripped.startswith("# port:")):
            out.append(f"port: {port}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"port: {port}")
    path.write_text("\n".join(out) + "\n")


def fetch_status(port: int) -> dict | None:
    """Query the running server. None means nothing is listening."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def cmd_up(args):
    project_dir = find_project_dir(args.project)
    server.PROJECT_DIR = project_dir
    config = state.load_gcontext_yaml(project_dir)
    name = config.get("name", project_dir.name)
    configured = config.get("port")
    port = resolve_port(args, project_dir)

    if not port_is_free(port):
        running = fetch_status(port)
        who = f" ({running.get('name', '?')} serving {running.get('project_dir', '?')})" if running else ""
        if getattr(args, "port", None) or configured:
            source = "--port" if getattr(args, "port", None) else "gcontext.yaml"
            print(f"Error: port {port} (from {source}) is already in use{who}.", file=sys.stderr)
            print("Free it, or pick another port with --port.", file=sys.stderr)
            sys.exit(1)
        chosen = find_free_port(port + 1)
        print(f"{YELLOW}{BOLD}Port {port} is taken{who}.{RESET}")
        print(f"{YELLOW}{BOLD}Using port {chosen} instead. Saved port: {chosen} to gcontext.yaml so this URL stays stable.{RESET}")
        print()
        port = chosen

    if port != int(configured or DEFAULT_PORT):
        persist_port(project_dir, port)

    url = server_url(port)

    exec_mod.ensure_venv(project_dir)
    from gcontext import controls
    try:
        n_off_cmds, n_off_res = server.load_controls()
    except controls.ControlsError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Fix controls.yaml and run gcontext up again.", file=sys.stderr)
        sys.exit(1)
    n_framework_prompts = server.register_framework_prompts()
    n_commands = server.register_commands()
    n_base_lines, n_instruction_lines = server.load_instructions()
    server.snapshot_startup_files()

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} serving {name} {DIM}({__version__}){RESET}")
    print(f"{DIM}State: {project_dir}{RESET}")
    print()
    print(f"Serving at {BOLD}{url}{RESET}")
    print(f"Dashboard:  http://127.0.0.1:{port}/")
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
        print(f"Instructions: framework ({n_base_lines} lines) + agent.md ({n_instruction_lines} lines), pushed to every agent at connect.")
    else:
        print(f"{YELLOW}Instructions: no agent.md, agents receive only the framework instructions ({n_base_lines} lines) at connect.{RESET}")
    builtin_names = ", ".join(p.stem for p in commands_mod.discover_framework_prompts())
    prompt_bits = [f"{n_framework_prompts} built-in ({builtin_names})"]
    if n_commands:
        prompt_bits.append(f"{n_commands} project command(s)")
    if n_off_cmds:
        prompt_bits.append(f"{n_off_cmds} off in controls.yaml")
    print(f"Prompts: {' + '.join(prompt_bits)} as MCP prompts (slash commands in Claude Code).")
    if n_off_res:
        print(f"Resources: {n_off_res} off in controls.yaml "
              "(unlisted, still readable via read_file).")
    print()
    print("Connections appear below as clients attach. Ctrl+C stops the server,")
    print("and every client cleanly loses access.")
    print()
    print("Next: connect your client with the command above (already connected: /mcp to reconnect).")
    print()

    server.mcp.run(
        transport="http", host="127.0.0.1", port=port, path="/mcp",
        show_banner=False, log_level="warning", stateless_http=True,
    )


def cmd_status(args):
    project_dir = find_project_dir(args.project)

    config = state.load_gcontext_yaml(project_dir)
    connections = state.load_connections(project_dir)
    secrets = secrets_mod.load(project_dir)
    modules = state.discover_modules(project_dir)
    agents = state.discover_agents(project_dir)
    port = resolve_port(args, project_dir)

    name = config.get("name", project_dir.name)
    desc = config.get("description", "")
    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} status of {name}")
    if desc:
        print(f"{DIM}{desc}{RESET}")
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
            print(f"  {YELLOW}agent.md changed since server start; restart to push the new version{RESET}")
        if stale.get("commands"):
            print(f"  {YELLOW}commands changed since server start; restart to re-register them{RESET}")
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
    for cname, conn in connections.items():
        missing = [s for s in conn.secrets if s not in secrets or not secrets[s]]
        if missing:
            print(f"  {cname}: {YELLOW}missing {', '.join(missing)}{RESET}")
        else:
            filled = len(conn.secrets)
            print(f"  {cname}: {GREEN}ready{RESET} {DIM}({filled}/{filled} secrets){RESET}")
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
    config = state.load_gcontext_yaml(project_dir)
    name = config.get("name", project_dir.name)
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
    config = state.load_gcontext_yaml(project_dir)
    name = config.get("name", project_dir.name)

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} {name}")
    print(f"{DIM}Every pipe that inserts context into an attached agent.{RESET}")
    print()
    print_ledger(project_dir)


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def cmd_add(args):
    project_dir = find_project_dir(args.project)
    source = args.source

    try:
        result = registry_mod.install_agent(project_dir, source)
    except (registry_mod.RegistryError, ValueError) as e:
        msg = str(e)
        print(f"Error: {msg}", file=sys.stderr)
        if msg.startswith("no agent '") or msg.startswith("no agent \""):
            print("Browse available agents:", file=sys.stderr)
            print("  https://github.com/bleak-ai/agents", file=sys.stderr)
            print("  https://gcontext.ai/agents/", file=sys.stderr)
        sys.exit(1)

    config = state.load_gcontext_yaml(project_dir)
    server_name = config.get("name", project_dir.name)
    rel = result["path"]
    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} installed {result['name']} ({result['count']} files) at {rel}/")
    for dep in result.get("dependencies", []):
        print(
            f"{BOLD}gcontext{RESET} {DIM}-{RESET} installed {dep['name']} "
            f"({dep['count']} files) at {dep['path']}/ (required by {dep['required_by']})"
        )
    for conn in result.get("connections", []):
        if conn["status"] == "missing":
            line = report_strings.CONNECTION_MISSING_LINE.format(kind=conn["kind"])
        else:
            line = report_strings.CONNECTION_EXISTS_LINE.format(kind=conn["kind"])
        print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} {line}")
    up_dir = args.project or "."
    print()
    print("Next steps:")
    print("  1. Stop the server (Ctrl-C).")
    print(f"  2. Start it again: gcontext up {up_dir}")
    print("  3. Reconnect in your client: type /mcp in Claude Code.")
    if (project_dir / rel / "commands" / "setup.md").exists():
        setup_cmd = commands_mod.installed_setup_prompt(server_name, result["id"])
        print(f"  4. Run the setup: {setup_cmd}")


def cmd_remove(args):
    project_dir = find_project_dir(args.project)
    agent_id = args.id
    from .commands import parse_command

    agent_dir = project_dir / "agents" / agent_id
    if not agent_dir.is_dir():
        agent_dir = project_dir / "modules" / agent_id
        if not agent_dir.is_dir():
            print(f"Error: agent '{agent_id}' not found in agents/ or modules/.", file=sys.stderr)
            sys.exit(1)

    manifest = registry_mod.read_manifest(agent_dir)
    if manifest is None:
        print(f"Error: {agent_dir / registry_mod.MANIFEST_NAME} not found. Cannot determine installed files.", file=sys.stderr)
        sys.exit(1)

    index_path = agent_dir / "index.md"
    learns = []
    configurable = []
    if index_path.exists():
        try:
            meta, _ = parse_command(index_path.read_text(encoding="utf-8"))
            learns = meta.get("learns") or []
            if isinstance(learns, str):
                learns = [learns]
            configurable = meta.get("configurable") or []
            if isinstance(configurable, str):
                configurable = [configurable]
        except (ValueError, OSError):
            pass

    print(f"Agent: {agent_id}")
    print(f"Location: {agent_dir.relative_to(project_dir)}/")

    if learns or configurable:
        print()
        if learns:
            print(f"Instance-owned folders: {', '.join(learns)}")
        if configurable:
            print(f"Configurable files: {', '.join(configurable)}")
        print()
        answer = input("Keep instance-owned files (runs, learned data)? [y/N] ").strip().lower()
        keep = answer in ("y", "yes")
    else:
        keep = False

    if keep:
        archive_dir = project_dir / "archive" / "agents" / agent_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        moved = []
        for folder_name in learns:
            src = agent_dir / folder_name
            if src.exists():
                dest = archive_dir / folder_name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(src), str(dest))
                moved.append(folder_name)
        manifest_hashes = manifest.get("files") or {}
        for conf_file in configurable:
            src = agent_dir / conf_file
            if not src.exists():
                continue
            local_hash = registry_mod.file_hash(src.read_text(encoding="utf-8"))
            installed_hash = manifest_hashes.get(conf_file)
            if installed_hash and local_hash != installed_hash:
                dest = archive_dir / conf_file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                moved.append(conf_file)

        shutil.rmtree(agent_dir)
        print()
        if moved:
            print(f"Archived to {archive_dir.relative_to(project_dir)}/: {', '.join(moved)}")
        print(f"Removed {agent_id}.")
    else:
        shutil.rmtree(agent_dir)
        print(f"Removed {agent_id}.")

    print()
    print(f"Commands from {agent_id} are gone after a server restart.")
    print(RESTART_RULE)


def validate_template(folder: Path) -> dict:
    """Validate a local template folder against the agent standard.

    Returns parsed frontmatter on success. Prints an error and exits on failure.
    """
    from .commands import parse_command

    index_path = folder / "index.md"
    if not index_path.exists():
        print(f"Error: {folder}/index.md not found.", file=sys.stderr)
        sys.exit(1)

    try:
        meta, _ = parse_command(index_path.read_text(encoding="utf-8"))
    except ValueError:
        print("Error: index.md has no YAML frontmatter.", file=sys.stderr)
        sys.exit(1)

    for field in ("id", "name", "description"):
        if not meta.get(field):
            print(f"Error: index.md frontmatter is missing '{field}'.", file=sys.stderr)
            sys.exit(1)

    tags = meta.get("tags")
    if not isinstance(tags, list) or len(tags) == 0:
        print("Error: index.md frontmatter is missing 'tags' (at least one tag required).", file=sys.stderr)
        sys.exit(1)

    agent_id = meta["id"]
    if not isinstance(agent_id, str) or not ID_RE.match(agent_id):
        print("Error: id must be lowercase letters, digits, and hyphens.", file=sys.stderr)
        sys.exit(1)

    valid_kinds = ", ".join(CONNECTION_KINDS)
    connections = meta.get("connections")
    if connections is not None and not isinstance(connections, list):
        print("Error: 'connections' must be a list of entries with a 'kind'.", file=sys.stderr)
        sys.exit(1)
    for entry in connections or []:
        kind = entry.get("kind") if isinstance(entry, dict) else None
        if not kind:
            print(f"Error: every connections entry needs a 'kind'. Valid kinds: {valid_kinds}.", file=sys.stderr)
            sys.exit(1)
        if kind not in CONNECTION_KINDS:
            print(f"Error: connection kind '{kind}' is not in the enum. Valid kinds: {valid_kinds}.", file=sys.stderr)
            sys.exit(1)

    agents = meta.get("agents")
    if agents is not None:
        if not isinstance(agents, list) or not all(
            isinstance(a, str) and ID_RE.match(a) for a in agents
        ):
            print("Error: 'agents' must be a list of agent ids (lowercase letters, digits, and hyphens).", file=sys.stderr)
            sys.exit(1)
        if agent_id in agents:
            print("Error: an agent cannot require itself.", file=sys.stderr)
            sys.exit(1)
        if agents:
            try:
                catalog = registry_mod.load_catalog()
            except registry_mod.RegistryError:
                print("Warning: could not reach the registry; required agent ids not verified.")
                catalog = None
            if catalog is not None:
                by_id = {e.get("id"): e for e in catalog}
                for dep in agents:
                    if dep not in by_id:
                        print(f"Error: required agent '{dep}' is not in the registry.", file=sys.stderr)
                        sys.exit(1)
                # Walk the dependency chains in the catalog; reaching this
                # agent's own id again means the requirement graph has a cycle.
                seen = set()
                stack = list(agents)
                while stack:
                    current = stack.pop()
                    if current == agent_id:
                        print(f"Error: dependency cycle: '{agent_id}' is required by one of its own required agents.", file=sys.stderr)
                        sys.exit(1)
                    if current in seen:
                        continue
                    seen.add(current)
                    stack.extend(by_id.get(current, {}).get("agents") or [])

    configurable = meta.get("configurable")
    if configurable is not None:
        if not isinstance(configurable, list) or not all(isinstance(c, str) for c in configurable):
            print("Error: 'configurable' must be a list of file path strings.", file=sys.stderr)
            sys.exit(1)
        for c in configurable:
            if not (folder / c).exists():
                print(f"Error: configurable file '{c}' does not exist in the folder.", file=sys.stderr)
                sys.exit(1)

    shares = meta.get("shares")
    if shares is not None:
        if not isinstance(shares, list):
            print("Error: 'shares' must be a list of entries with a 'path'.", file=sys.stderr)
            sys.exit(1)
        for entry in shares:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                print("Error: every shares entry needs a 'path' string.", file=sys.stderr)
                sys.exit(1)
            if "description" in entry and not isinstance(entry["description"], str):
                print("Error: shares entry 'description' must be a string.", file=sys.stderr)
                sys.exit(1)

    flow = meta.get("flow")
    if not isinstance(flow, list) or not flow or not all(isinstance(s, str) and s.strip() for s in flow):
        print("Error: 'flow' must be a non-empty list of strings (the agent's loop, one line per beat).", file=sys.stderr)
        sys.exit(1)

    if not (folder / "steps").is_dir():
        print("Error: steps/ folder not found.", file=sys.stderr)
        sys.exit(1)

    if not (folder / "runs" / "example").is_dir():
        print("Error: runs/example/ folder not found.", file=sys.stderr)
        sys.exit(1)

    runs = folder / "runs"
    if runs.is_dir():
        offenders = sorted(
            p.name for p in runs.iterdir()
            if not p.name.startswith(".") and not (p.name == "example" and p.is_dir())
        )
        if offenders:
            print(f"Error: runs/ may contain only the example/ folder; found: {', '.join(offenders)}.", file=sys.stderr)
            sys.exit(1)

    setup_path = folder / "commands" / "setup.md"
    if setup_path.exists():
        try:
            setup_meta, setup_body = parse_command(setup_path.read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"Error: commands/setup.md: {e}.", file=sys.stderr)
            sys.exit(1)
        if not setup_meta.get("description"):
            print("Error: commands/setup.md frontmatter is missing 'description'.", file=sys.stderr)
            sys.exit(1)
        first_line = next((ln.strip() for ln in setup_body.splitlines() if ln.strip()), "")
        heading = re.match(r"^#\s+(.*)$", first_line)
        if heading:
            text = heading.group(1).strip()
            if text == "Setup" or text.startswith("Welcome"):
                print(
                    "Error: commands/setup.md opens with a greeting heading. "
                    "setup.md supplies steps only; the framework owns the dialogue "
                    "(see docs/setup-script.md).",
                    file=sys.stderr,
                )
                sys.exit(1)

    from .fs import _index_siblings, index_format_issues, INDEX_SHAPE

    for child_index in sorted(folder.rglob("index.md")):
        rel_parts = child_index.relative_to(folder).parts
        if any(p.startswith(".") or p.startswith("__") for p in rel_parts):
            continue
        siblings = _index_siblings(child_index.parent)
        if child_index.parent == folder:
            # README.md at the agent root documents the agent on GitHub;
            # the registry build excludes it from installs, so the map
            # must not list it.
            siblings = [n for n in siblings if n != "README.md"]
        issues = index_format_issues(
            child_index.read_text(encoding="utf-8"),
            siblings,
        )
        if issues:
            rel = "/".join(rel_parts)
            for issue in issues:
                print(f"Error: {rel}: {issue}.", file=sys.stderr)
            print(f"Error: {INDEX_SHAPE}", file=sys.stderr)
            sys.exit(1)

    return meta


def bundle_files(folder: Path) -> list[dict]:
    """Walk a template folder and return [{path, content}] for all text files.

    Skips dotfiles/dirs and __pycache__. Warns and skips non-UTF-8 files.
    """
    files = []
    for filepath in sorted(folder.rglob("*")):
        if not filepath.is_file():
            continue
        rel_parts = filepath.relative_to(folder).parts
        if any(p.startswith(".") or p.startswith("__") for p in rel_parts):
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            print(f"Skipping {filepath.relative_to(folder)}: not a text file.", file=sys.stderr)
            continue
        files.append({"path": str(filepath.relative_to(folder)), "content": content})
    return files


def cmd_share(args):
    folder = Path(args.module_path).resolve()
    if not folder.is_dir():
        print(f"Error: {args.module_path} is not a directory.", file=sys.stderr)
        sys.exit(1)

    meta = validate_template(folder)
    files = bundle_files(folder)
    agent_id = meta["id"]

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} validated agent {agent_id} ({len(files)} files)")
    print()
    print("To publish this agent, open a PR against the registry:")
    print("  https://github.com/bleak-ai/agents")
    print()
    print(f"Add the agent folder as {agent_id}/ at the repository root, then open a pull request.")

    if shutil.which("gh"):
        print()
        print("Commands to run:")
        print()
        print("  gh repo fork bleak-ai/agents --clone")
        print("  cd agents")
        print(f"  cp -r {folder} {agent_id}")
        print(f"  git add {agent_id}")
        print(f'  git commit -m "Add {agent_id} agent"')
        print(f'  gh pr create --title "Add {agent_id}" --body "New agent: {meta["name"]}"')


def cmd_update(args):
    project_dir = find_project_dir(args.project)
    try:
        report = registry_mod.update_agent(project_dir, args.id)
    except (registry_mod.RegistryError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(registry_mod.format_update_report(report))
    if report.get("backed_up"):
        print()
        print("Backed-up files saved as <name>.pre-update. Review and merge your changes.")
    if report.get("commands_changed"):
        print()
        print("Commands changed: restart the server to re-register them (stop, gcontext up, reconnect the client).")


def cmd_search(args):
    try:
        entries = registry_mod.search_catalog(args.query or "")
    except (registry_mod.RegistryError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not entries:
        print(f"No agents match '{args.query}'.")
        return

    for e in entries:
        tags = ", ".join(e.get("tags", []))
        print(f"  {e['id']}  {e['name']}  [{tags}]")
        if e.get("description"):
            print(f"    {DIM}{e['description']}{RESET}")
    print()
    print("Install: gcontext add <id>")


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
        p.add_argument("--port", type=int, help=f"Server port (default: {DEFAULT_PORT}, or port: in gcontext.yaml)")

    up_parser = subparsers.add_parser("up", help="Start the server. Clients connect to its URL")
    add_common(up_parser)

    status_parser = subparsers.add_parser("status", help="Server up? Who is connected? Plus connections, secrets, modules")
    add_common(status_parser)

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

    add_parser = subparsers.add_parser("add", help="Install an agent from the GitHub registry into agents/")
    add_parser.add_argument("source", help="Agent id (e.g. browser-recipes) or GitHub URL (e.g. https://github.com/owner/repo/tree/main/path)")
    add_parser.add_argument("project", nargs="?", help="Path to gcontext project directory")

    share_parser = subparsers.add_parser("share", help="Validate an agent template and show how to submit it via PR")
    share_parser.add_argument("module_path", help="Path to the template folder")

    remove_parser = subparsers.add_parser("remove", help="Uninstall an agent and optionally archive its data")
    remove_parser.add_argument("id", help="Agent id (the agents/ folder name)")
    remove_parser.add_argument("project", nargs="?", help="Path to gcontext project directory")

    update_parser = subparsers.add_parser("update", help="Update an installed agent from the registry")
    update_parser.add_argument("id", help="Agent id (the agents/ folder name)")
    update_parser.add_argument("project", nargs="?", help="Path to gcontext project directory")

    search_parser = subparsers.add_parser("search", help="Search the agent registry")
    search_parser.add_argument("query", nargs="?", default="", help="Substring to match against id, name, description, tags")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "up": cmd_up,
        "status": cmd_status,
        "connect": cmd_connect,
        "context": cmd_context,
        "add": cmd_add,
        "remove": cmd_remove,
        "share": cmd_share,
        "update": cmd_update,
        "search": cmd_search,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
