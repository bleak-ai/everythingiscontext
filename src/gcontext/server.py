"""gcontext MCP server. Reads a project directory and exposes it to any MCP client."""

import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile

import yaml
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import flows as flows_mod
from .models import ConnectionManifest, ModuleManifest

mcp = FastMCP("gcontext")

# Set by cli.py before the server starts
PROJECT_DIR: Path = Path(".")

# Live MCP sessions, keyed by session id: {"client": ..., "connected": ..., "last_seen": ...}
SESSIONS: dict[str, dict] = {}


def _session_id(context) -> str:
    ctx = getattr(context, "fastmcp_context", None)
    return getattr(ctx, "session_id", None) or "session"


class ConnectionTracker(Middleware):
    """Records who is connected, straight from the MCP initialize handshake."""

    async def on_initialize(self, context, call_next):
        params = getattr(context.message, "params", None) or context.message
        info = getattr(params, "clientInfo", None)
        client = getattr(info, "name", None) or "unknown client"
        version = getattr(info, "version", "") or ""
        now = datetime.now().isoformat(timespec="seconds")
        SESSIONS[_session_id(context)] = {
            "client": client,
            "version": version,
            "connected": now,
            "last_seen": now,
        }
        print(f"  + {client} {version} connected ({now})", file=sys.stderr)
        return await call_next(context)

    async def on_message(self, context, call_next):
        session = SESSIONS.get(_session_id(context))
        if session:
            session["last_seen"] = datetime.now().isoformat(timespec="seconds")
        return await call_next(context)


mcp.add_middleware(ConnectionTracker())


@mcp.custom_route("/status", methods=["GET"])
async def status_route(request: Request) -> JSONResponse:
    config = _load_gcontext_yaml()
    flow_summary = {}
    for fname, flow in flows_mod.load_flows(PROJECT_DIR).items():
        board = flows_mod.flow_board(PROJECT_DIR, flow)
        flow_summary[fname] = {
            "done": sum(1 for s in board if s["status"] == "done"),
            "total": len(board),
            "actionable": [s["id"] for s in flows_mod.actionable(board)],
        }
    return JSONResponse({
        "name": config.get("name", PROJECT_DIR.name),
        "project_dir": str(PROJECT_DIR.resolve()),
        "sessions": list(SESSIONS.values()),
        "flows": flow_summary,
    })


def _load_gcontext_yaml() -> dict:
    p = PROJECT_DIR / "gcontext.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text()) or {}
    return {}


def _load_connections() -> dict[str, ConnectionManifest]:
    """Scan connections/ for subdirectories containing connection.yaml."""
    conns_dir = PROJECT_DIR / "connections"
    if not conns_dir.is_dir():
        return {}
    result = {}
    for item in sorted(conns_dir.iterdir()):
        if not item.is_dir():
            continue
        conn_file = item / "connection.yaml"
        if not conn_file.exists():
            continue
        data = yaml.safe_load(conn_file.read_text()) or {}
        manifest = ConnectionManifest(**data)
        result[manifest.name] = manifest
    return result


def _connection_files(name: str) -> list[str]:
    """List non-yaml files in a connection folder."""
    conn_dir = PROJECT_DIR / "connections" / name
    if not conn_dir.is_dir():
        return []
    files = []
    for f in sorted(conn_dir.rglob("*")):
        if f.is_file() and f.name != "connection.yaml":
            files.append(str(f.relative_to(PROJECT_DIR)))
    return files


def _load_secrets_env() -> dict[str, str]:
    env_file = PROJECT_DIR / "secrets.env"
    if not env_file.exists():
        return {}
    pairs = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            pairs[key.strip()] = value.strip()
    return pairs


def _archived() -> dict[str, list[str]]:
    """Names of archived items per category, from archive/{connections,modules,flows}/.

    Anything under archive/ is never scanned into overview, the ledger counts,
    or the flow boards. It stays readable by path via read_context. Archiving
    is a plain folder move; there is no metadata and no automatic behavior.
    """
    result = {}
    for category in ("connections", "modules", "flows"):
        d = PROJECT_DIR / "archive" / category
        if d.is_dir():
            items = [i.name for i in sorted(d.iterdir()) if i.is_dir()]
            if items:
                result[category] = items
    return result


def _archived_line() -> str:
    archived = _archived()
    if not archived:
        return ""
    parts = [f"{len(items)} {cat}" for cat, items in archived.items()]
    return f"archive/: {', '.join(parts)} (not scanned, readable by path)"


def _discover_modules() -> dict[str, ModuleManifest]:
    """Scan modules/ for folders with module.yaml."""
    modules_dir = PROJECT_DIR / "modules"
    if not modules_dir.is_dir():
        return {}
    result = {}
    for item in sorted(modules_dir.iterdir()):
        if not item.is_dir():
            continue
        manifest_file = item / "module.yaml"
        if manifest_file.exists():
            data = yaml.safe_load(manifest_file.read_text()) or {}
            manifest = ModuleManifest(**data)
        else:
            manifest = ModuleManifest(name=item.name, description="")
        result[manifest.name] = manifest
    return result


def _module_files(name: str) -> list[str]:
    """List content files in a module folder."""
    mod_dir = PROJECT_DIR / "modules" / name
    if not mod_dir.is_dir():
        return []
    files = []
    for f in sorted(mod_dir.rglob("*")):
        if f.is_file() and f.name not in ("module.yaml", ".gitkeep"):
            files.append(str(f.relative_to(PROJECT_DIR)))
    return files


SCRIPT_TIMEOUT = 60


def _scrub_output(text: str, secrets: dict[str, str]) -> str:
    for value in secrets.values():
        if value and len(value) > 3:
            text = text.replace(value, "***")
    return text


def _venv_dir() -> Path:
    return PROJECT_DIR.resolve() / ".venv"


def _venv_python() -> Path:
    venv = _venv_dir()
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _collect_deps() -> set[str]:
    connections = _load_connections()
    all_deps = set()
    for conn in connections.values():
        for dep in conn.deps:
            all_deps.add(dep)
    return all_deps


def ensure_venv() -> None:
    """Create the project venv if missing and sync connection deps into it."""
    venv_dir = _venv_dir()

    if not venv_dir.is_dir():
        subprocess.run(
            ["uv", "venv", str(venv_dir), "--quiet"],
            check=True,
            cwd=str(PROJECT_DIR),
        )

    all_deps = _collect_deps()
    if all_deps:
        subprocess.run(
            ["uv", "pip", "install", "--quiet", "--python", str(_venv_python())]
            + sorted(all_deps),
            check=True,
            cwd=str(PROJECT_DIR),
        )


def build_ledger(mode: str) -> list[dict]:
    """Every pipe that inserts context into the agent for a mode ('chat' or 'mcp').

    Statuses: loaded (pushed at start), on demand (agent pulls, visible as a
    tool call), skipped (closed by a launch flag), uncontrolled (runtime-owned).
    """
    instructions = PROJECT_DIR / "instructions.md"
    connections = _load_connections()
    modules = _discover_modules()
    n_files = sum(len(_connection_files(c)) for c in connections)
    n_files += sum(len(_module_files(m)) for m in modules)

    ledger = []

    if mode == "chat":
        if instructions.exists():
            n = len(instructions.read_text().splitlines())
            ledger.append({"id": "G0", "label": "instructions.md", "detail": f"system prompt ({n} lines)", "status": "loaded"})
        else:
            ledger.append({"id": "G0", "label": "instructions.md", "detail": "file missing, no system prompt", "status": "skipped"})
    else:
        ledger.append({"id": "G0", "label": "instructions.md", "detail": "not auto-loaded in MCP mode, read it via read_context", "status": "on demand"})

    ledger.append({"id": "G1", "label": "tool descriptions", "detail": "6 gcontext tools, pushed at connect", "status": "loaded"})
    ledger.append({"id": "G2", "label": "overview()", "detail": "project map, secret status", "status": "on demand"})
    g3_detail = f"{n_files} files in connections/ + modules/"
    if _archived():
        g3_detail += "; archive/ not scanned, readable by path"
    ledger.append({"id": "G3", "label": "read_context()", "detail": g3_detail, "status": "on demand"})
    ledger.append({"id": "G4", "label": "list_connections()", "detail": f"{len(connections)} connection(s)", "status": "on demand"})
    ledger.append({"id": "G5", "label": "run_script() output", "detail": "secret values scrubbed", "status": "on demand"})
    all_flows = flows_mod.load_flows(PROJECT_DIR)
    ledger.append({"id": "G6", "label": "flows()", "detail": f"{len(all_flows)} flow(s); step instructions surface only when the step is actionable", "status": "on demand"})

    if mode == "chat":
        ledger.append({"id": "R1", "label": "claude default system prompt", "detail": "replaced by --system-prompt", "status": "skipped"})
        ledger.append({"id": "R2", "label": "~/.claude/CLAUDE.md + settings", "detail": "closed via --setting-sources ''", "status": "skipped"})
        ledger.append({"id": "R3", "label": "other MCP servers", "detail": "closed via --strict-mcp-config", "status": "skipped"})
        ledger.append({"id": "R4", "label": "claude tool harness", "detail": "runtime-owned", "status": "uncontrolled"})
    else:
        ledger.append({"id": "R1", "label": "runtime system prompt", "detail": "runtime-owned", "status": "uncontrolled"})
        ledger.append({"id": "R2", "label": "user/project CLAUDE.md", "detail": "runtime-owned", "status": "uncontrolled"})
        ledger.append({"id": "R3", "label": "other MCP servers, skills, memory", "detail": "runtime-owned", "status": "uncontrolled"})

    return ledger


def render_ledger_plain(mode: str) -> list[str]:
    lines = []
    for i, pipe in enumerate(build_ledger(mode), 1):
        label = f"{pipe['label']} ".ljust(36, ".")
        lines.append(f"{i}. [{pipe['id']}] {label} {pipe['status']}: {pipe['detail']}")
    return lines


@mcp.tool
def overview() -> str:
    """Show project info, all connections with their secret status, and all modules with descriptions."""
    config = _load_gcontext_yaml()
    connections = _load_connections()
    secrets = _load_secrets_env()
    modules = _discover_modules()

    lines = []
    name = config.get("name", PROJECT_DIR.name)
    desc = config.get("description", "")
    lines.append(f"# {name}")
    if desc:
        lines.append(desc)
    lines.append("")

    lines.append("## Context ledger")
    lines.append("Everything that enters your context from this server, and how:")
    lines.extend(render_ledger_plain("mcp"))
    lines.append("")

    instructions = PROJECT_DIR / "instructions.md"
    if instructions.exists():
        lines.append(f"System prompt: instructions.md ({len(instructions.read_text().splitlines())} lines)")
        lines.append("")

    lines.append("## Connections")
    if not connections:
        lines.append("No connections defined.")
    for cname, conn in connections.items():
        filled = sum(1 for s in conn.secrets if s in secrets and secrets[s])
        total = len(conn.secrets)
        status = "ready" if filled == total else f"missing {total - filled} secret(s)"
        missing = [s for s in conn.secrets if s not in secrets or not secrets[s]]
        lines.append(f"- **{cname}**: {status}")
        if conn.description:
            lines.append(f"  {conn.description}")
        if missing:
            lines.append(f"  Missing: {', '.join(missing)}")
        if conn.deps:
            lines.append(f"  Deps: {', '.join(conn.deps)}")
        for f in _connection_files(cname):
            lines.append(f"  - {f}")
    lines.append("")

    if modules:
        lines.append("## Modules")
        for mname, mod in modules.items():
            tag_str = f" [{', '.join(mod.tags)}]" if mod.tags else ""
            lines.append(f"- **{mname}** (v{mod.version}){tag_str}")
            if mod.description:
                lines.append(f"  {mod.description}")
            for f in _module_files(mname):
                lines.append(f"  - {f}")
        lines.append("")

    all_flows = flows_mod.load_flows(PROJECT_DIR)
    if all_flows:
        lines.append("## Flows")
        for fname, flow in all_flows.items():
            board = flows_mod.flow_board(PROJECT_DIR, flow)
            done = sum(1 for s in board if s["status"] == "done")
            ready = [s["id"] for s in flows_mod.actionable(board)]
            ready_str = f", actionable: {', '.join(ready)}" if ready else ""
            lines.append(f"- **{fname}**: {done}/{len(board)} done{ready_str}")
            if flow.description:
                lines.append(f"  {flow.description}")
        lines.append("Call flows() for step details and instructions.")
        lines.append("")

    archived = _archived()
    if archived:
        lines.append("## Archive")
        for cat, items in archived.items():
            lines.append(f"- archive/{cat}/: {', '.join(items)}")
        lines.append("Archived items are never scanned or listed above; read them by path if needed.")

    return "\n".join(lines).rstrip()


@mcp.tool
def read_context(path: str) -> str:
    """Read a file from the project. Use overview() first to see available files."""
    target = (PROJECT_DIR / path).resolve()
    if not target.is_relative_to(PROJECT_DIR.resolve()):
        return f"Error: path {path} is outside the project directory."
    if not target.exists():
        return f"Error: {path} does not exist."
    if not target.is_file():
        return f"Error: {path} is not a file."
    return target.read_text()


@mcp.tool
def write_context(path: str, content: str) -> str:
    """Write or update a file in the project. Creates parent directories if needed.

    Use this to update connection context docs, create playbooks, write logs, etc.
    Cannot write to secrets.env or connection.yaml files.

    Args:
        path: Relative path within the project (e.g. 'modules/support-workflow/playbooks/refund.md')
        content: The full file content to write.
    """
    target = (PROJECT_DIR / path).resolve()
    if not target.is_relative_to(PROJECT_DIR.resolve()):
        return f"Error: path {path} is outside the project directory."
    if target.name == "secrets.env":
        return "Error: cannot write to secrets.env through the agent."
    if target.name == "connection.yaml":
        return "Error: cannot write to connection.yaml through the agent."

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Written: {path} ({len(content)} bytes)"


@mcp.tool
def run_script(code: str) -> str:
    """Run a Python script in the project's .venv with secrets as env vars.

    The .venv has all connection deps pre-installed.
    Access secrets with os.environ["SECRET_NAME"].
    Secret values are scrubbed from stdout/stderr before returning.

    Args:
        code: Python source code to execute.
    """
    secrets = _load_secrets_env()
    python = _venv_python()

    if not python.exists():
        ensure_venv()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=PROJECT_DIR
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        env = os.environ.copy()
        env.update(secrets)

        result = subprocess.run(
            [str(python), script_path],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=env,
            cwd=str(PROJECT_DIR),
        )

        output_parts = []
        if result.stdout.strip():
            output_parts.append(result.stdout.strip())
        if result.stderr.strip():
            output_parts.append(f"[stderr]\n{result.stderr.strip()}")
        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        output = "\n".join(output_parts) if output_parts else "(no output)"
        return _scrub_output(output, secrets)

    except subprocess.TimeoutExpired:
        return f"Error: script timed out after {SCRIPT_TIMEOUT} seconds."
    finally:
        Path(script_path).unlink(missing_ok=True)


@mcp.tool
def flows(name: str = "") -> str:
    """Show flows: declarative multi-step work whose state lives in files.

    Each step declares which files it needs and which it produces. Status is
    computed purely from the filesystem: blocked (a needed file is missing),
    ready (needs exist, produces missing), stale (a need changed after the
    produces were written), done. Instructions are shown only for actionable
    (ready or stale) steps.

    You complete a step by writing its declared produces with write_context.
    Nothing else tracks progress; the files are the state.

    Args:
        name: Optional flow name to show just one flow.
    """
    all_flows = flows_mod.load_flows(PROJECT_DIR)
    if not all_flows:
        return "No flows defined in flows/*/flow.yaml"

    if name:
        if name not in all_flows:
            return f"Error: no flow named {name}. Available: {', '.join(all_flows)}"
        all_flows = {name: all_flows[name]}

    lines = []
    for flow in all_flows.values():
        lines.extend(flows_mod.render_flow(PROJECT_DIR, flow))
        lines.append("")
    return "\n".join(lines).rstrip()


@mcp.tool
def list_connections() -> str:
    """Show all connections with their secrets, deps, context files, and whether each secret has a value."""
    connections = _load_connections()
    secrets = _load_secrets_env()

    if not connections:
        return "No connections defined in connections/*/connection.yaml"

    lines = []
    for cname, conn in connections.items():
        lines.append(f"## {cname}")
        if conn.description:
            lines.append(conn.description)
        lines.append("")
        lines.append("Secrets:")
        for s in conn.secrets:
            has_value = s in secrets and bool(secrets[s])
            icon = "filled" if has_value else "MISSING"
            lines.append(f"  - {s}: {icon}")
        if conn.deps:
            lines.append(f"Deps: {', '.join(conn.deps)}")
        context_files = _connection_files(cname)
        if context_files:
            lines.append("Context:")
            for f in context_files:
                lines.append(f"  - {f}")
        lines.append("")

    return "\n".join(lines)
