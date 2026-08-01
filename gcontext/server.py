"""The MCP surface: everything an attached agent can reach, in one file.

Six tools (defined below, their agent-facing text in prompts/tools/*.md),
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
        """The resource list is the state folder, scanned live: every listable
        file at gcontext://<path>, so runtimes can offer them for attachment."""
        result = await call_next(context)
        for rel in fs.walk_files(PROJECT_DIR):
            mime = "text/markdown" if rel.endswith(".md") else "text/plain"
            result.append(Resource(uri=f"gcontext://{rel}", name=rel, mime_type=mime))
        return result

    async def on_read_resource(self, context, call_next):
        uri = str(getattr(context.message, "uri", "?"))
        start = time.perf_counter()
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
    })


def register_commands() -> int:
    """Register command files as MCP prompts. Call once, after PROJECT_DIR is set."""
    return commands_mod.register_commands(mcp, PROJECT_DIR)


def register_framework_prompts() -> int:
    """Register the package's own prompts (setup). Call once at startup."""
    return commands_mod.register_framework_prompts(mcp)


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


@mcp.resource("gcontext://{path*}",
              description=(_PROMPTS_DIR / "resources.md").read_text().strip())
def state_resource(path: str) -> str:
    rel = path.rstrip("/")
    target, error = fs.resolve_path(PROJECT_DIR, rel)
    if error:
        return f"Error: {error}."
    if target.is_dir():
        return fs.list_dir(PROJECT_DIR, rel or ".")
    return fs.read_file(PROJECT_DIR, rel)


# output_schema=None on every tool: with a schema, FastMCP wraps the string
# result as structured content {"result": ...} and runtimes like Claude Code
# display that JSON (newlines escaped) instead of the readable text block.
@mcp.tool(description=_tool_doc("read_file"), output_schema=None)
def read_file(path: str) -> str:
    return fs.read_file(PROJECT_DIR, path)


@mcp.tool(description=_tool_doc("write_file"), output_schema=None)
def write_file(path: str, content: str) -> str:
    return fs.write_file(PROJECT_DIR, path, content)


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
) -> str:
    return _exec_result(exec_mod.run_script(PROJECT_DIR, path, args=args, params=params))


@mcp.tool(description=_tool_doc("run_adhoc_script"), output_schema=None)
def run_adhoc_script(
    code: str,
    params: dict[str, str] | None = None,
) -> str:
    return _exec_result(exec_mod.run_adhoc_script(PROJECT_DIR, code, params=params))




from . import dashboard  # noqa: E402,F401  registers /api/* and the static catch-all
