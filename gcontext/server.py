"""The MCP surface: everything an attached agent can reach, in one file.

Seven tools (defined below, their agent-facing text in prompts/tools/*.md),
state files as MCP resources (gcontext://<path>, listed live), commands
registered as prompts, a /status route, and session tracking.
The actual work lives in the per-concern modules:

    fs.py        read_file / write_file / list_dir / grep (path confinement, guards)
    exec.py      run_script / run_adhoc_script (venv, secrets injection, output scrubbing)
    state.py     connections / modules / archive scanning
    secrets.py   secrets.env parsing and output scrubbing
    ledger.py    the context ledger
    commands.py  commands/ folders -> MCP prompts

If it is not in this file, the agent cannot invoke it.
"""

import itertools
import json
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.resources import Resource
from fastmcp.server.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import commands as commands_mod
from . import exec as exec_mod
from . import fs
from . import registry as registry_mod
from . import report_strings
from . import secrets as secrets_mod
from . import state

mcp = FastMCP("gcontext")

# Set by cli.py before the server starts
PROJECT_DIR: Path = Path(".")

# Agent-facing tool text lives in markdown, not in code.
_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _tool_doc(name: str) -> str:
    return (_PROMPTS_DIR / "tools" / f"{name}.md").read_text().strip()


# Live MCP sessions, keyed by session id: {"client": ..., "connected": ..., "last_seen": ...}
SESSIONS: dict[str, dict] = {}

# Two file classes load only at server start: agent.md (pushed in the MCP
# handshake) and command files (registered as prompts). No watchers, per the
# no-background-behavior design: a startup snapshot of their mtimes, compared
# lazily on tool calls, with one stderr line per class per server lifetime.
STARTUP_SNAPSHOT: dict = {"agent_md": None, "commands": {}}
_STALE = {"agent_md": False, "commands": False}
_STALE_WARNED = {"agent_md": False, "commands": False}
_STALE_CHECK_INTERVAL = 5.0
_last_stale_check = 0.0


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def snapshot_startup_files():
    """Record the state of the start-time-loaded files. Call once, after
    load_instructions() and register_commands() have run."""
    STARTUP_SNAPSHOT["agent_md"] = _mtime(PROJECT_DIR / "agent.md")
    STARTUP_SNAPSHOT["commands"] = {
        str(p): _mtime(p) for p in commands_mod.discover(PROJECT_DIR)
    }
    _STALE.update(agent_md=False, commands=False)
    _STALE_WARNED.update(agent_md=False, commands=False)


def check_staleness(force: bool = False) -> dict:
    """Compare the current files against the startup snapshot.

    Once a class is stale it stays stale until restart, so the comparison for
    it stops. Throttled to one filesystem check per few seconds unless forced.
    """
    global _last_stale_check
    now = time.monotonic()
    if not force and now - _last_stale_check < _STALE_CHECK_INTERVAL:
        return dict(_STALE)
    _last_stale_check = now
    if not _STALE["agent_md"]:
        _STALE["agent_md"] = _mtime(PROJECT_DIR / "agent.md") != STARTUP_SNAPSHOT["agent_md"]
    if not _STALE["commands"]:
        current = {str(p): _mtime(p) for p in commands_mod.discover(PROJECT_DIR)}
        _STALE["commands"] = current != STARTUP_SNAPSHOT["commands"]
    if _STALE["agent_md"] and not _STALE_WARNED["agent_md"]:
        _STALE_WARNED["agent_md"] = True
        print("  ! agent.md changed since start; restart to push the new version "
              "(stop, gcontext up, reconnect the client)", file=sys.stderr)
    if _STALE["commands"] and not _STALE_WARNED["commands"]:
        _STALE_WARNED["commands"] = True
        print("  ! commands changed since start; restart to re-register them",
              file=sys.stderr)
    return dict(_STALE)

# Activity feed for the dashboard: in-memory ring buffer, gone on restart.
EVENTS: deque = deque(maxlen=300)
_EVENT_SEQ = itertools.count(1)


def _session_id(context) -> str:
    ctx = getattr(context, "fastmcp_context", None)
    return getattr(ctx, "session_id", None) or "session"


def record_event(session: str, kind: str, name: str, detail: str = "",
                 preview: str = "", error: bool = False, tier: int = 1,
                 tokens_in: int = 0, tokens_out: int = 0, duration_ms: int = 0):
    EVENTS.append({
        "id": next(_EVENT_SEQ),
        "ts": int(time.time() * 1000),
        "session": session,
        "kind": kind,
        "name": name,
        "detail": detail,
        "preview": preview,
        "error": error,
        "tier": tier,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "duration_ms": duration_ms,
    })


def _event_detail(name: str, arguments: dict) -> str:
    """Summarize tool arguments for the feed. Never file content or code:
    the feed goes to a browser, tool arguments may hold whole documents."""
    if name == "write_file":
        path = arguments.get("path", "?")
        return f"{path} ({len(arguments.get('content') or '')} bytes)"
    if name == "grep":
        pattern = arguments.get("pattern", "?")
        path = arguments.get("path") or "."
        return f"{pattern!r} in {path}"
    if name == "run_script":
        return str(arguments.get("path", "?"))
    if name == "run_adhoc_script":
        return f"inline code ({len(arguments.get('code') or '')} chars)"
    if arguments.get("path"):
        return str(arguments["path"])
    return ", ".join(sorted(arguments)) if arguments else ""


def _result_text(result) -> str:
    content = getattr(result, "content", None) or []
    return "\n".join(t for t in (getattr(b, "text", None) for b in content) if t)


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
        record_event(_session_id(context), "connect", client,
                     detail=version, tier=0)
        print(f"  + {client} {version} connected ({now})", file=sys.stderr)
        return await call_next(context)

    async def on_call_tool(self, context, call_next):
        check_staleness()
        name = getattr(context.message, "name", "?")
        arguments = getattr(context.message, "arguments", None) or {}
        detail = _event_detail(name, arguments)
        tokens_in = len(json.dumps(arguments, default=str)) // 4
        start = time.perf_counter()
        try:
            result = await call_next(context)
        except Exception as exc:
            record_event(_session_id(context), "error", name, detail=detail,
                         preview=str(exc)[:400], error=True, tokens_in=tokens_in,
                         duration_ms=round((time.perf_counter() - start) * 1000))
            raise
        text = _result_text(result)
        preview = secrets_mod.scrub(text[:400], secrets_mod.load(PROJECT_DIR))
        record_event(_session_id(context), "tool", name, detail=detail,
                     preview=preview, error=text.startswith("Error:"),
                     tokens_in=tokens_in, tokens_out=len(text) // 4,
                     duration_ms=round((time.perf_counter() - start) * 1000))
        return result

    async def on_get_prompt(self, context, call_next):
        name = getattr(context.message, "name", "?")
        arguments = getattr(context.message, "arguments", None) or {}
        record_event(_session_id(context), "prompt", name,
                     detail=", ".join(sorted(arguments)) if arguments else "",
                     tier=2)
        return await call_next(context)

    async def on_list_resources(self, context, call_next):
        """Curated resource list: the agent entry point plus each module and
        connection.  Only the entry points appear as suggestions; every file
        stays readable via the read_file tool."""
        await call_next(context)
        result = []
        config = state.load_gcontext_yaml(PROJECT_DIR)
        agent_name = config.get("name", PROJECT_DIR.name)
        result.append(Resource(
            uri=f"agent://{agent_name}",
            name=agent_name,
            mime_type="text/markdown",
        ))
        modules = state.discover_modules(PROJECT_DIR)
        if modules:
            result.append(Resource(
                uri=f"agent://{agent_name}/modules",
                name="modules",
                mime_type="text/markdown",
            ))
            for name in modules:
                result.append(Resource(
                    uri=f"agent://{agent_name}/modules/{name}",
                    name=f"modules / {name}",
                    mime_type="text/markdown",
                ))
        connections = state.load_connections(PROJECT_DIR)
        if connections:
            result.append(Resource(
                uri=f"agent://{agent_name}/connections",
                name="connections",
                mime_type="text/markdown",
            ))
            for name in connections:
                result.append(Resource(
                    uri=f"agent://{agent_name}/connections/{name}",
                    name=f"connections / {name}",
                    mime_type="text/markdown",
                ))
        return result

    async def on_read_resource(self, context, call_next):
        from fastmcp.resources.base import ResourceResult
        uri = str(getattr(context.message, "uri", "?"))
        start = time.perf_counter()
        text = _resolve_resource_uri(uri)
        if text is not None:
            result = ResourceResult(text)
        else:
            result = await call_next(context)
        record_event(_session_id(context), "resource", "resource", detail=uri,
                     duration_ms=round((time.perf_counter() - start) * 1000))
        return result

    async def on_message(self, context, call_next):
        session = SESSIONS.get(_session_id(context))
        if session:
            session["last_seen"] = datetime.now().isoformat(timespec="seconds")
        return await call_next(context)


mcp.add_middleware(ConnectionTracker())


@mcp.custom_route("/status", methods=["GET"])
async def status_route(request: Request) -> JSONResponse:
    config = state.load_gcontext_yaml(PROJECT_DIR)
    return JSONResponse({
        "name": config.get("name", PROJECT_DIR.name),
        "project_dir": str(PROJECT_DIR.resolve()),
        "sessions": list(SESSIONS.values()),
        "stale": check_staleness(force=True),
    })


def register_commands() -> int:
    """Register command files as MCP prompts. Call once, after PROJECT_DIR is set."""
    return commands_mod.register_commands(mcp, PROJECT_DIR)


def register_framework_prompts() -> int:
    """Register the package's own prompts (setup, explain). Call once at
    startup, after PROJECT_DIR is set: the $setup_report and
    $explain_report placeholders are filled from this project's state at
    invocation time."""
    return commands_mod.register_framework_prompts(mcp, PROJECT_DIR)


def load_instructions() -> tuple[int, int]:
    """Serve instructions in the MCP handshake: gcontext's own, then the project's.

    Two files, two owners. prompts/framework-instructions.md ships with the
    framework (what gcontext is, how the tools and the folder work; ledger
    pipe G0) and is always pushed. The project's agent.md defines the
    particular agent (ledger pipe G1) and is appended when it exists. Editing
    the project file (plus a restart) changes what every future session
    receives. Returns (base_lines, project_lines); project_lines is 0 when
    the file is missing.
    """
    base = (_PROMPTS_DIR / "framework-instructions.md").read_text()
    instructions = PROJECT_DIR / "agent.md"
    if not instructions.exists():
        mcp.instructions = base
        return len(base.splitlines()), 0
    text = instructions.read_text()
    mcp.instructions = f"{base}\n{text}"
    return len(base.splitlines()), len(text.splitlines())


def _resolve_resource_uri(uri: str) -> str | None:
    """Resolve a resource URI to text content, or None if unrecognised."""
    if uri.startswith("agent://"):
        path = uri[len("agent://"):].rstrip("/")
        parts = path.split("/", 1)
        rel = parts[1] if len(parts) > 1 else ""
        if not rel:
            return _ask_resource()
        target, error = fs.resolve_path(PROJECT_DIR, rel)
        if error:
            return f"Error: {error}."
        if target.is_dir():
            index = target / "index.md"
            if index.is_file():
                return fs.read_file(PROJECT_DIR, f"{rel}/index.md")
            return fs.list_dir(PROJECT_DIR, rel)
        return fs.read_file(PROJECT_DIR, rel)
    if uri.startswith("gcontext://"):
        rel = uri[len("gcontext://"):].rstrip("/")
        target, error = fs.resolve_path(PROJECT_DIR, rel)
        if error:
            return f"Error: {error}."
        if target.is_dir():
            return fs.list_dir(PROJECT_DIR, rel or ".")
        return fs.read_file(PROJECT_DIR, rel)
    return None


def _ask_resource() -> str:
    """Build the 'ask' resource: agent.md plus a map of modules and connections."""
    config = state.load_gcontext_yaml(PROJECT_DIR)
    agent_name = config.get("name", PROJECT_DIR.name)
    parts = [f"# {agent_name}\n"]
    agent_md = PROJECT_DIR / "agent.md"
    if agent_md.exists():
        parts.append(agent_md.read_text().strip())
        parts.append("")
    modules = state.discover_modules(PROJECT_DIR)
    if modules:
        parts.append("## Modules")
        for name, manifest in modules.items():
            desc = f" - {manifest.description}" if manifest.description else ""
            parts.append(f"- {name}{desc}")
        parts.append("")
    connections = state.load_connections(PROJECT_DIR)
    if connections:
        parts.append("## Connections")
        for name, manifest in connections.items():
            desc = f" - {manifest.description}" if manifest.description else ""
            parts.append(f"- {name}{desc}")
        parts.append("")
    return "\n".join(parts)


# output_schema=None on every tool: with a schema, FastMCP wraps the string
# result as structured content {"result": ...} and runtimes like Claude Code
# display that JSON (newlines escaped) instead of the readable text block.
@mcp.tool(description=_tool_doc("read_file"), output_schema=None)
def read_file(path: str) -> str:
    return fs.read_file(PROJECT_DIR, path)


@mcp.tool(description=_tool_doc("write_file"), output_schema=None)
def write_file(path: str, content: str) -> str:
    result = fs.write_file(PROJECT_DIR, path, content)
    try:
        commands_mod.refresh_generated(mcp, PROJECT_DIR, path)
    except Exception as e:
        print(f"  ! generated-command refresh failed: {e}", file=sys.stderr)
    return result


@mcp.tool(description=_tool_doc("list_dir"), output_schema=None)
def list_dir(path: str = ".") -> str:
    return fs.list_dir(PROJECT_DIR, path)


@mcp.tool(description=_tool_doc("grep"), output_schema=None)
def grep(pattern: str, path: str = ".", glob: str = "") -> str:
    return fs.grep(PROJECT_DIR, pattern, path=path, glob=glob)


def _exec_result(result: dict) -> str:
    """Render an exec dict as readable text: status line, stdout, stderr, hint.

    Text only, no structured content: when a tool declares structured content,
    Claude Code displays that JSON instead of the text block, and stdout
    renders with escaped newlines. The status line keeps the structured facts
    (exit code, duration, timed out / truncated).
    """
    status = f"exit {result['exit_code']} | {result['duration_ms']} ms"
    if result["timed_out"]:
        status += " | timed out"
    if result["truncated"]:
        status += " | truncated"
    parts = [f"[{status}]"]
    if result["stdout"].strip():
        parts.append(result["stdout"].rstrip())
    if result["stderr"].strip():
        parts.append(f"[stderr]\n{result['stderr'].rstrip()}")
    if not result["stdout"].strip() and not result["stderr"].strip():
        parts.append("(no output)")
    if result.get("hint"):
        parts.append(f"[hint] {result['hint']}")
    return "\n".join(parts)


@mcp.tool(description=_tool_doc("run_script"), output_schema=None)
def run_script(
    path: str,
    args: list[str] | None = None,
    params: dict[str, str] | None = None,
    timeout: int | None = None,
) -> str:
    return _exec_result(
        exec_mod.run_script(PROJECT_DIR, path, args=args, params=params, timeout=timeout)
    )


@mcp.tool(description=_tool_doc("run_adhoc_script"), output_schema=None)
def run_adhoc_script(
    code: str,
    params: dict[str, str] | None = None,
    timeout: int | None = None,
) -> str:
    return _exec_result(
        exec_mod.run_adhoc_script(PROJECT_DIR, code, params=params, timeout=timeout)
    )




def _register_module_commands(module_id: str):
    commands_mod.register_module_commands(mcp, PROJECT_DIR, module_id)


def _notify_prompts_changed():
    try:
        import asyncio
        from fastmcp.server.dependencies import get_context
        ctx = get_context()
        session = getattr(ctx, "session", None)
        if session and hasattr(session, "send_prompt_list_changed"):
            loop = asyncio.get_running_loop()
            loop.create_task(session.send_prompt_list_changed())
    except Exception:
        pass


@mcp.tool(description=_tool_doc("agent"), output_schema=None)
def agent(action: str, id: str = "", query: str = "") -> str:
    if action == "search":
        try:
            entries = registry_mod.search_catalog(query)
        except (registry_mod.RegistryError, ValueError) as e:
            return f"Error: {e}."
        if not entries:
            return f"No agents match '{query}'."
        lines = []
        for e in entries:
            tags = ", ".join(e.get("tags", []))
            lines.append(f"{e['id']}: {e['name']}")
            if e.get("description"):
                lines.append(f"  {e['description']}")
            if tags:
                lines.append(f"  tags: {tags}")
            lines.append("")
        lines.append('Install one with agent(action="install", id="<id>")')
        return "\n".join(lines)

    elif action == "install":
        if not id:
            return "Error: install needs an id."
        try:
            result = registry_mod.install_agent(PROJECT_DIR, id)
        except (registry_mod.RegistryError, ValueError) as e:
            return f"Error: {e}."
        _register_module_commands(result["id"])
        for dep in result.get("dependencies", []):
            _register_module_commands(dep["id"])
        _notify_prompts_changed()
        snapshot_startup_files()
        lines = [f"Installed {result['name']} ({result['count']} files) at {result['path']}/."]
        for dep in result.get("dependencies", []):
            lines.append(report_strings.INSTALLED_DEPENDENCY_LINE.format(**dep))
        for conn in result.get("connections", []):
            if conn["status"] == "created":
                lines.append(
                    report_strings.CONNECTION_STUB_CREATED_LINE.format(kind=conn["kind"])
                )
            else:
                lines.append(
                    report_strings.CONNECTION_EXISTS_LINE.format(kind=conn["kind"])
                )
        lines.append(f"Next step: run the setup in {result['path']}/commands/setup.md")
        return "\n".join(lines)

    elif action == "check":
        try:
            if id:
                module_dir = PROJECT_DIR / "modules" / id
                if not module_dir.is_dir():
                    return f"Error: modules/{id} does not exist."
                reports = [registry_mod.check_agent(PROJECT_DIR, id)]
            else:
                reports = registry_mod.check_all(PROJECT_DIR)
        except (registry_mod.RegistryError, ValueError) as e:
            return f"Error: {e}."
        if not reports:
            return f"No installed agents track a template (no {registry_mod.MANIFEST_NAME} files found)."
        return "\n".join(registry_mod.format_check_report(r) for r in reports)

    elif action == "update":
        if not id:
            return "Error: update needs an id."
        try:
            report = registry_mod.update_agent(PROJECT_DIR, id)
        except (registry_mod.RegistryError, ValueError) as e:
            return f"Error: {e}."
        if report.get("commands_changed"):
            _register_module_commands(report["id"])
            _notify_prompts_changed()
            snapshot_startup_files()
        return registry_mod.format_update_report(report)

    return f"Error: unknown action '{action}'. Use search, install, check, or update."


from . import dashboard  # noqa: E402,F401  registers /api/* and the static catch-all
