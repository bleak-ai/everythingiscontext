"""The local dashboard: read-only JSON API plus the built web app.

Registered on the same server as the MCP endpoint, so `gcontext up` serves
the dashboard at / while agents talk to /mcp. Everything here is a pure read
of the project folder or of in-memory server state (SESSIONS, EVENTS).
Nothing writes; secret values never leave secrets.py as anything but
presence booleans.

Route order matters: fastmcp appends custom routes after the MCP routes in
registration order, so the /{path:path} catch-all at the bottom of this file
must stay last.
"""

from importlib import metadata
from pathlib import Path

import yaml

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

from . import commands as commands_mod
from . import fs
from . import ledger as ledger_mod
from . import secrets as secrets_mod
from . import server
from . import state

mcp = server.mcp

# cli.py mutates server.PROJECT_DIR after import; always read it via the module.


def _root() -> Path:
    return server.PROJECT_DIR


def _version() -> str:
    try:
        return metadata.version("gcontext-ai")
    except metadata.PackageNotFoundError:
        return "dev"


@mcp.custom_route("/api/project", methods=["GET"])
async def api_project(request: Request) -> JSONResponse:
    root = _root()
    config = state.load_gcontext_yaml(root)
    instructions = root / "agent.md"
    return JSONResponse({
        "name": config.get("name", root.name),
        "description": config.get("description", ""),
        "project_dir": str(root.resolve()),
        "has_instructions": instructions.exists(),
        "instructions_lines": len(instructions.read_text().splitlines()) if instructions.exists() else 0,
        "archived": state.archived(root),
        "version": _version(),
    })


@mcp.custom_route("/api/connections", methods=["GET"])
async def api_connections(request: Request) -> JSONResponse:
    root = _root()
    secrets = secrets_mod.load(root)
    result = []
    for cname, conn in state.load_connections(root).items():
        secret_status = [
            {"name": s, "filled": bool(secrets.get(s))} for s in conn.secrets
        ]
        result.append({
            "name": cname,
            "description": conn.description,
            "deps": conn.deps,
            "secrets": secret_status,
            "ready": all(s["filled"] for s in secret_status),
            "files": state.connection_files(root, cname),
        })
    return JSONResponse(result)


@mcp.custom_route("/api/modules", methods=["GET"])
async def api_modules(request: Request) -> JSONResponse:
    root = _root()
    result = []
    for mname, mod in state.discover_modules(root).items():
        result.append({
            "name": mname,
            "description": mod.description,
            "tags": mod.tags,
            "files": state.module_files(root, mname),
        })
    return JSONResponse(result)


@mcp.custom_route("/api/agents", methods=["GET"])
async def api_agents(request: Request) -> JSONResponse:
    root = _root()
    result = []
    for aname, agent in state.discover_agents(root).items():
        result.append({
            "name": aname,
            "display_name": agent.name,
            "description": agent.description,
            "tags": agent.tags,
            "files": state.agent_files(root, aname),
        })
    return JSONResponse(result)


def _command_entry(path: Path, name: str, owner: str, rel: str, kind: str, key: str = "", disabled: bool = False) -> dict:
    entry = {"owner": owner, "name": name, "kind": kind, "path": rel, "key": key, "disabled": disabled}
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            meta, _ = commands_mod.parse_command(text)
        else:
            meta = commands_mod.parse_script_command(text)
        entry["description"] = meta.get("description", "")
        entry["args"] = [
            {
                "name": p.get("name", "?"),
                "description": p.get("description", ""),
                "required": bool(p.get("required", False)),
            }
            for p in (meta.get("parameters") or [])
        ]
    except (ValueError, KeyError, yaml.YAMLError) as e:
        entry["error"] = str(e)
    return entry


@mcp.custom_route("/api/commands", methods=["GET"])
async def api_commands(request: Request) -> JSONResponse:
    root = _root()
    result = []
    # Build reverse map: file path string -> registered prompt name.
    path_to_name: dict[str, str] = {}
    for reg_name, source in commands_mod._REGISTERED.items():
        if source == "framework":
            continue
        path_to_name.setdefault(source, reg_name)
    # File commands: look up the registered name, fall back to short_name.
    for path in commands_mod.discover(root):
        if commands_mod._is_template(path):
            continue
        rel = str(path.relative_to(root))
        owner = path.parent.parent.name
        name = path_to_name.get(str(path), commands_mod._short_name(path.stem))
        key = commands_mod._STABLE_KEYS.get(name, commands_mod._stable_key(path, root))
        result.append(_command_entry(path, name, owner, rel, path.suffix.lstrip("."), key=key))
    # Template-generated entries from GENERATED.
    for tpl_path_str, info in commands_mod.GENERATED.items():
        tpl_path = Path(tpl_path_str)
        owner = Path(info["owner_dir"]).name
        for gen_name in sorted(info["names"]):
            rel = str(tpl_path.relative_to(root)) if tpl_path.is_relative_to(root) else tpl_path_str
            key = commands_mod._STABLE_KEYS.get(gen_name, "")
            result.append(_command_entry(tpl_path, gen_name, owner, rel, "md", key=key))
    # Framework prompts.
    for path in commands_mod.discover_framework_prompts():
        key = f"framework/{path.stem}"
        result.append(_command_entry(
            path, path.stem, "framework", f"gcontext/prompts/{path.name}", "md", key=key
        ))
    for disabled_key in commands_mod.disabled_commands():
        parts = disabled_key.split("/", 1)
        d_owner = parts[0] if len(parts) > 1 else ""
        d_stem = parts[1] if len(parts) > 1 else parts[0]
        result.append({
            "owner": d_owner,
            "name": d_stem,
            "kind": "",
            "path": "",
            "key": disabled_key,
            "disabled": True,
            "description": "",
        })
    return JSONResponse(result)


@mcp.custom_route("/api/ledger", methods=["GET"])
async def api_ledger(request: Request) -> JSONResponse:
    return JSONResponse({"ledger": ledger_mod.build(_root())})


@mcp.custom_route("/api/tree", methods=["GET"])
async def api_tree(request: Request) -> JSONResponse:
    root = _root().resolve()
    entries = []
    for f in sorted(root.rglob("*")):
        rel_parts = f.relative_to(root).parts
        if fs.BROWSER_BLOCKED & set(rel_parts):
            continue
        if f.name == "secrets.env":
            continue
        stat = f.stat()
        entries.append({
            "path": str(f.relative_to(root)),
            "name": f.name,
            "dir": f.is_dir(),
            "size": 0 if f.is_dir() else stat.st_size,
            "mtime": int(stat.st_mtime * 1000),
        })
    return JSONResponse({"tree": entries})


@mcp.custom_route("/api/file", methods=["GET"])
async def api_file(request: Request) -> JSONResponse:
    path = request.query_params.get("path", "")
    if not path:
        return JSONResponse({"error": "path query parameter required"}, status_code=400)
    target, error = fs.resolve_browser_path(_root(), path)
    if error:
        return JSONResponse({"error": error}, status_code=403)
    if not target.is_file():
        return JSONResponse({"error": f"{path} does not exist"}, status_code=404)
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return JSONResponse({"error": "binary file"}, status_code=400)
    stat = target.stat()
    return JSONResponse({
        "path": path,
        "content": content,
        "size": stat.st_size,
        "mtime": int(stat.st_mtime * 1000),
    })


@mcp.custom_route("/api/sessions", methods=["GET"])
async def api_sessions(request: Request) -> JSONResponse:
    sessions = [{"id": sid, **info} for sid, info in server.SESSIONS.items()]
    return JSONResponse({"sessions": sessions})


@mcp.custom_route("/api/events", methods=["GET"])
async def api_events(request: Request) -> JSONResponse:
    try:
        limit = min(int(request.query_params.get("limit", 100)), 300)
        since = int(request.query_params.get("since", 0))
    except ValueError:
        return JSONResponse({"error": "limit and since must be integers"}, status_code=400)
    events = [e for e in server.EVENTS if e["id"] > since][-limit:]
    latest = server.EVENTS[-1]["id"] if server.EVENTS else 0
    return JSONResponse({"events": events, "latest_id": latest})


# ---------------------------------------------------------------------------
# Static app. The built frontend ships inside the wheel at gcontext/web_dist;
# a repo checkout uses web/dist so `make web-build` + `uv run` works too.

_DIST_CANDIDATES = [
    Path(__file__).parent / "web_dist",
    Path(__file__).parents[1] / "web" / "dist",
]


def _dist_dir() -> Path | None:
    for candidate in _DIST_CANDIDATES:
        if (candidate / "index.html").is_file():
            return candidate
    return None


@mcp.custom_route("/{path:path}", methods=["GET"])
async def spa(request: Request):
    rel = request.path_params["path"]
    if rel.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    dist = _dist_dir()
    if dist is None:
        return PlainTextResponse(
            "gcontext dashboard is not built. Run `make web-build` in the repo, "
            "or reinstall the package.",
            status_code=503,
        )
    if rel:
        target = (dist / rel).resolve()
        if target.is_relative_to(dist.resolve()) and target.is_file():
            return FileResponse(target)
    return FileResponse(dist / "index.html")
