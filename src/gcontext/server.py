"""The MCP surface: everything an attached agent can reach, in one file.

Six tools (defined below, their agent-facing text in prompts/tools/*.md),
commands registered as prompts, a /status route, and session tracking.
The actual work lives in the per-concern modules:

    fs.py        read_file / write_file / list_dir / grep (path confinement, guards)
    exec.py      run_script (venv, secrets injection, output scrubbing)
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
from fastmcp.server.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import commands as commands_mod
from . import exec as exec_mod
from . import fs
from . import ledger as ledger_mod
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
        if arguments.get("path"):
            return str(arguments["path"])
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


def load_instructions() -> int:
    """Serve the project's instructions.md in the MCP handshake.

    This is THE file pushed to every agent at connect: what it says is exactly
    what the agent starts with, the ledger declares it as G0, and editing the
    file (plus a restart) changes what every future session receives. Returns
    the line count, 0 if the file does not exist (nothing is pushed then).
    """
    instructions = PROJECT_DIR / "instructions.md"
    if not instructions.exists():
        mcp.instructions = None
        return 0
    text = instructions.read_text()
    mcp.instructions = text
    return len(text.splitlines())


@mcp.tool(description=_tool_doc("overview"))
def overview() -> str:
    root = PROJECT_DIR
    config = state.load_gcontext_yaml(root)
    connections = state.load_connections(root)
    secrets = secrets_mod.load(root)
    modules = state.discover_modules(root)

    lines = []
    name = config.get("name", root.name)
    desc = config.get("description", "")
    lines.append(f"# {name}")
    if desc:
        lines.append(desc)
    lines.append("")

    lines.append("## Context ledger")
    lines.append("Everything that enters your context from this server, and how:")
    lines.extend(ledger_mod.render_plain(root))
    lines.append("")

    instructions = root / "instructions.md"
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
        lines.append(f"- **{cname}**: {status}")
        if conn.description:
            lines.append(f"  {conn.description}")
        for s in conn.secrets:
            has_value = s in secrets and bool(secrets[s])
            lines.append(f"  - {s}: {'filled' if has_value else 'MISSING'}")
        if conn.deps:
            lines.append(f"  Deps: {', '.join(conn.deps)}")
        for f in state.connection_files(root, cname):
            lines.append(f"  - {f}")
    lines.append("")

    if modules:
        lines.append("## Modules")
        for mname, mod in modules.items():
            tag_str = f" [{', '.join(mod.tags)}]" if mod.tags else ""
            lines.append(f"- **{mname}** (v{mod.version}){tag_str}")
            if mod.description:
                lines.append(f"  {mod.description}")
            for f in state.module_files(root, mname):
                lines.append(f"  - {f}")
        lines.append("")

    archived = state.archived(root)
    if archived:
        lines.append("## Archive")
        for cat, items in archived.items():
            lines.append(f"- archive/{cat}/: {', '.join(items)}")
        lines.append("Archived items are never scanned or listed above; read them by path if needed.")

    return "\n".join(lines).rstrip()


@mcp.tool(description=_tool_doc("read_file"))
def read_file(path: str) -> str:
    return fs.read_file(PROJECT_DIR, path)


@mcp.tool(description=_tool_doc("write_file"))
def write_file(path: str, content: str) -> str:
    return fs.write_file(PROJECT_DIR, path, content)


@mcp.tool(description=_tool_doc("list_dir"))
def list_dir(path: str = ".") -> str:
    return fs.list_dir(PROJECT_DIR, path)


@mcp.tool(description=_tool_doc("grep"))
def grep(pattern: str, path: str = ".", glob: str = "") -> str:
    return fs.grep(PROJECT_DIR, pattern, path=path, glob=glob)


@mcp.tool(description=_tool_doc("run_script"))
def run_script(
    code: str = "",
    path: str = "",
    args: list[str] | None = None,
    params: dict[str, str] | None = None,
) -> str:
    return exec_mod.run(PROJECT_DIR, code=code, path=path, args=args, params=params)




from . import dashboard  # noqa: E402,F401  registers /api/* and the static catch-all
