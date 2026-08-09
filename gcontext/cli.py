"""gcontext CLI. One server you start, harnesses connect to its URL. State is files."""

import argparse
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
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
DEFAULT_API_URL = "https://api.gcontext.ai"

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

The server prints a URL and the one-line command to connect your harness
(Claude Code, Claude Desktop, Codex, Cursor). The harness does the reasoning;
this folder is the memory.

What's here: `agent.md` is the agent's definition, pushed to every harness at
connect. `connections/` holds the services it can use, `modules/` its knowledge
by topic, `archive/` retired state. `secrets.env` holds secret values; it is
gitignored and never leaves this machine, so after cloning, recreate it from
the NAMEs each connection.yaml declares.
"""

def cmd_init(args):
    target = Path(args.directory).resolve()
    if target.exists() and any(target.iterdir()):
        print(f"Error: {target} already exists and is not empty.", file=sys.stderr)
        sys.exit(1)

    name = target.name
    files = {
        "gcontext.yaml": INIT_GCONTEXT_YAML.format(name=name),
        "README.md": INIT_README.format(name=name),
        "agent.md": INIT_INSTRUCTIONS,
        "secrets.env": INIT_SECRETS,
        ".gitignore": INIT_AGENT_GITIGNORE,
        "connections/.gitkeep": "",
        "modules/.gitkeep": "",
        "archive/.gitkeep": "",
    }
    for rel, content in files.items():
        f = target / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} created {name} at {target}")
    print()
    print("The folder IS your agent's state: version it with git, edit it freely.")
    print()
    pad = min(max(len(f"gcontext up {args.directory}"), len(f"/mcp__{name}__setup")) + 4, 44)
    print("Next steps:")
    print(f"  1. {f'gcontext up {args.directory}':<{pad}}  start the server")
    print(f"  2. {'connect your harness':<{pad}}  the up banner prints the exact command per harness")
    print(f"  3. {f'/mcp__{name}__setup':<{pad}}  in the harness: describe what the agent should do, it builds the rest")
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
    return int(config.get("port", DEFAULT_PORT))


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
    n_framework_prompts = server.register_framework_prompts()
    n_commands = server.register_commands()
    n_base_lines, n_instruction_lines = server.load_instructions()

    print(f"{BOLD}gcontext{RESET} {DIM}{__version__} -{RESET} {name}")
    print(f"{DIM}State: {project_dir}{RESET}")
    print()
    print(f"Serving at {BOLD}{url}{RESET}")
    print(f"Dashboard:  http://127.0.0.1:{port}/")
    print()
    print("Connect a harness (once per harness, works from any directory):")
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
    prompt_bits = [f"{n_framework_prompts} built-in (setup)"]
    if n_commands:
        prompt_bits.append(f"{n_commands} project command(s)")
    print(f"Prompts: {' + '.join(prompt_bits)} as MCP prompts (slash commands in Claude Code).")
    print()
    print("Connections appear below as harnesses attach. Ctrl+C stops the server,")
    print("and every harness cleanly loses access.")
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
    port = resolve_port(args, project_dir)

    name = config.get("name", project_dir.name)
    desc = config.get("description", "")
    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} {name}")
    if desc:
        print(f"{DIM}{desc}{RESET}")
    print(f"{DIM}State: {project_dir}{RESET}")
    print()

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
            print(f"  {DIM}no harness connected yet{RESET}")
        for s in sessions:
            print(f"  {GREEN}{s['client']}{RESET} {DIM}{s['version']}{RESET}  connected {s['connected']}  last activity {s['last_seen']}")
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

    archived_line = state.archived_line(project_dir)
    if archived_line:
        print(f"{DIM}{archived_line}{RESET}")
        print()

    print(f"{DIM}No runtime included. Point any MCP client at the URL above.{RESET}")


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


def resolve_api_url(args) -> str:
    if getattr(args, "api_url", None):
        return args.api_url.rstrip("/")
    return os.environ.get("GCONTEXT_API_URL", DEFAULT_API_URL).rstrip("/")


def fetch_workflow(workflow_id: str) -> dict:
    """Fetch one approved template bundle from the workflows API. Exits on failure."""
    base = os.environ.get("GCONTEXT_API_URL", DEFAULT_API_URL).rstrip("/")
    url = f"{base}/api/workflows/{workflow_id}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: no published workflow with id '{workflow_id}'.", file=sys.stderr)
            print("Browse the directory at https://gcontext.ai/workflows/", file=sys.stderr)
        else:
            print(f"Error: the workflows API answered {e.code} for {url}.", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, OSError, ValueError):
        print(f"Error: could not reach the workflows API at {url}.", file=sys.stderr)
        sys.exit(1)


def validate_bundle(files) -> dict:
    """Check paths and the index.md manifest; return the parsed frontmatter.

    Raises ValueError on any problem. Runs entirely in memory so a bad
    bundle never leaves files behind.
    """
    from pathlib import PurePosixPath

    from .commands import parse_command

    if not isinstance(files, list) or not files:
        raise ValueError("the bundle has no files")
    for f in files:
        path = f.get("path") or ""
        parts = PurePosixPath(path).parts
        if not path or path.startswith("/") or "\\" in path or ".." in parts:
            raise ValueError(f"unsafe file path in bundle: {path!r}")
    index = next((f for f in files if f["path"] == "index.md"), None)
    if index is None:
        raise ValueError("the bundle has no index.md")
    try:
        meta, _ = parse_command(index["content"])
    except ValueError as e:
        raise ValueError(f"index.md frontmatter: {e}")
    for field in ("id", "name", "description"):
        if not meta.get(field):
            raise ValueError(f"index.md frontmatter is missing '{field}'")
    return meta


def cmd_add(args):
    project_dir = find_project_dir(args.project)
    bundle = fetch_workflow(args.workflow_id)
    try:
        meta = validate_bundle(bundle.get("files"))
    except ValueError as e:
        print(f"Error: invalid workflow bundle: {e}", file=sys.stderr)
        sys.exit(1)

    module_dir = project_dir / "modules" / meta["id"]
    if module_dir.exists():
        print(f"Error: module '{meta['id']}' already exists at {module_dir}.", file=sys.stderr)
        print("Installs are snapshots: your copy is personalized and is never overwritten.", file=sys.stderr)
        sys.exit(1)

    for f in bundle["files"]:
        dest = module_dir / f["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f["content"])

    rel = f"modules/{meta['id']}"
    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} installed {meta['name']} ({len(bundle['files'])} files) at {rel}/")
    print()
    print("Next step: personalize it. Tell your agent to run the setup in")
    print(f"  {rel}/commands/setup.md")
    print(f"{DIM}(Re)start the server and the setup is also an MCP prompt: a slash command in Claude Code.{RESET}")


def validate_template(folder: Path) -> dict:
    """Validate a local template folder against the workflow standard.

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

    wid = meta["id"]
    if not isinstance(wid, str) or not ID_RE.match(wid):
        print("Error: id must be lowercase letters, digits, and hyphens.", file=sys.stderr)
        sys.exit(1)

    if not (folder / "steps").is_dir():
        print("Error: steps/ folder not found.", file=sys.stderr)
        sys.exit(1)

    if not (folder / "runs" / "example").is_dir():
        print("Error: runs/example/ folder not found.", file=sys.stderr)
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
    if args.status:
        _share_status(args)
        return

    folder = Path(args.module_path).resolve()
    if not folder.is_dir():
        print(f"Error: {args.module_path} is not a directory.", file=sys.stderr)
        sys.exit(1)

    meta = validate_template(folder)
    files = bundle_files(folder)
    wid = meta["id"]
    base = resolve_api_url(args)

    existing = False
    try:
        with urllib.request.urlopen(f"{base}/api/workflows/{wid}", timeout=10) as resp:
            if resp.status == 200:
                existing = True
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        pass

    if existing and not args.yes:
        print(f"Warning: '{wid}' is already published. A new submission replaces any")
        print("pending entry and enters the review queue.")
        answer = input("Continue? [y/N] ").strip()
        if answer.lower() != "y":
            print("Aborted.", file=sys.stderr)
            sys.exit(1)

    payload = json.dumps({"files": files}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/workflows",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except (json.JSONDecodeError, AttributeError):
            detail = body
        print(f"Error: the API rejected the submission: {detail}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, OSError):
        print(f"Error: could not reach the API at {base}.", file=sys.stderr)
        sys.exit(1)

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} submitted {wid} ({len(files)} files)")
    print()
    print(f"Status: {result.get('status', 'pending')} (under review)")
    print(f"Check status: gcontext share --status {wid}")


def _share_status(args):
    wid = args.module_path
    base = resolve_api_url(args)
    url = f"{base}/api/workflows/{wid}/status"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: no submission found for '{wid}'.", file=sys.stderr)
        else:
            print(f"Error: the API answered {e.code}.", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, OSError):
        print(f"Error: could not reach the API at {base}.", file=sys.stderr)
        sys.exit(1)

    submitted = data.get("submitted_at", "")[:16].replace("T", " ") + " UTC" if data.get("submitted_at") else "-"
    reviewed = data.get("reviewed_at", "")[:16].replace("T", " ") + " UTC" if data.get("reviewed_at") else "-"

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} {wid}")
    print()
    print(f"Status: {data['status']}")
    print(f"Submitted: {submitted}")
    print(f"Reviewed: {reviewed}")


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

    up_parser = subparsers.add_parser("up", help="Start the server. Harnesses connect to its URL")
    add_common(up_parser)

    status_parser = subparsers.add_parser("status", help="Server up? Who is connected? Plus connections, secrets, modules")
    add_common(status_parser)

    connect_parser = subparsers.add_parser("connect", help="Show how to point a harness at the server URL")
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

    add_parser = subparsers.add_parser("add", help="Install a published workflow from the marketplace into modules/")
    add_parser.add_argument("workflow_id", help="Workflow id from the directory (e.g. coolify-ops)")
    add_parser.add_argument("project", nargs="?", help="Path to gcontext project directory")

    share_parser = subparsers.add_parser("share", help="Submit a workflow template to the marketplace for review")
    share_parser.add_argument("module_path", help="Path to the template folder (or workflow id when used with --status)")
    share_parser.add_argument("--api-url", dest="api_url", help="Override the API base URL")
    share_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation when the workflow already exists")
    share_parser.add_argument("--status", action="store_true", help="Query submission status instead of submitting")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "up": cmd_up,
        "status": cmd_status,
        "connect": cmd_connect,
        "context": cmd_context,
        "add": cmd_add,
        "share": cmd_share,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
