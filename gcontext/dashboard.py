"""The local dashboard: read-only JSON API plus the built web app.

Registered on the same server as the MCP endpoint, so `gcontext up` serves
the dashboard at / while agents talk to /mcp. Everything here is a pure read
of the project folder or of in-memory server state (SESSIONS, EVENTS).
Nothing writes except POST /api/controls, which edits controls.yaml entries
through the same lock-guarded, comment-preserving writers the heal uses;
secret values never leave secrets.py as anything but presence booleans.

GET /api/controls returns a flat payload with five keys: commands (list of
command rows), resources (list of resource rows), structural (picker entries
the server always lists: the agent root plus the modules/connections group
indexes; no toggle, no rename), pinned (list of pinned paths), stale
(entries in controls.yaml that match nothing on disk).
POST /api/controls applies one change and returns the same shape plus a note.
The write path covers toggles (on/off, including framework/setup), pins,
renames (names: override, with live re-registration for commands), and bulk
owner changes (all commands under an owner at once). A command rename
re-registers prompts live so the client sees the new name after /mcp
reconnect.

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
from . import controls
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


# --- Controls: the one write path in the dashboard --------------------------
# GET returns a flat list of commands and resources with names, descriptions,
# and paths. POST applies exactly one change per request through
# controls.set_entry / set_pinned / set_name (line-based, lock-guarded,
# comment-preserving). The write path covers toggles, pins, renames, and bulk
# owner changes. A command rename re-registers prompts live.

_RAW = {True: "on", False: "off"}


def _template_keys(root: Path) -> set[str]:
    """Stable keys of template (`each:`) command files on disk."""
    return {
        f"{p.parent.parent.name}/{p.stem}"
        for p in commands_mod.discover(root)
        if commands_mod._is_template(p)
    }


def _first_line_description(root: Path, rkey: str) -> str:
    """Resource description: index.md frontmatter description, else the
    first non-heading paragraph's first line, truncated."""
    idx = root / rkey / "index.md"
    try:
        text = idx.read_text(encoding="utf-8")
    except OSError:
        return ""
    desc, body = "", text
    try:
        meta, body = commands_mod.parse_command(text)
        desc = str(meta.get("description") or "")
    except ValueError:
        pass
    if not desc:
        # Strip heading lines, then take the first non-empty paragraph.
        non_heading = "\n".join(
            ln for ln in body.split("\n") if not ln.lstrip().startswith("#")
        )
        para = next(
            (p.strip() for p in non_heading.split("\n\n") if p.strip()), "")
        desc = para.split("\n")[0]
    return desc[:160]


def _default_prompt_name(key: str) -> str:
    """The un-overridden short name for a stable key (display fallback for
    rows that are currently off, so not registered)."""
    return commands_mod._short_name(key.split("/", 1)[-1])


def _controls_payload(root: Path) -> dict:
    """Flat commands and resources with names, descriptions, and paths.
    Raises ControlsError when controls.yaml is malformed (never guess)."""
    reg = controls.parse(root / "controls.yaml") or controls.Registry()
    cmds, res = controls.inventory(root)
    templates = _template_keys(root)
    key_to_path: dict[str, Path] = {}
    for p in commands_mod.discover(root):
        key_to_path[commands_mod._stable_key(p, root)] = p
    for p in commands_mod.discover_framework_prompts():
        key_to_path[f"framework/{p.stem}"] = p
    command_rows = []
    for key in cmds:
        owner = key.split("/", 1)[0]
        path = key_to_path.get(key)
        registered = commands_mod.prompt_name_for_key(key)
        default = _default_prompt_name(key)
        custom = key in reg.names
        name = registered or (
            commands_mod._short_name(reg.names[key]) if custom else default)
        row: dict = {
            "key": key,
            "owner": owner,
            "name": name,
            "default_name": default,
            "custom": custom,
            "raw": _RAW[reg.commands[key]] if key in reg.commands else None,
            "effective": controls.command_enabled(reg, key),
            "template": key in templates,
            "description": "",
            "path": "",
        }
        if path is not None:
            row["path"] = (
                f"gcontext/prompts/{path.name}" if owner == "framework"
                else str(path.relative_to(root)))
            try:
                text = path.read_text(encoding="utf-8")
                meta = (commands_mod.parse_command(text)[0]
                        if path.suffix == ".md"
                        else commands_mod.parse_script_command(text))
                row["description"] = str(meta.get("description") or "")
            except (ValueError, KeyError, yaml.YAMLError, OSError):
                pass
        command_rows.append(row)
    resource_rows = []
    for rkey in res:
        kind, _, rname = rkey.partition("/")
        resource_rows.append({
            "key": rkey,
            "kind": kind,
            "name": commands_mod.resource_display(rkey, rname),
            "default_name": rname,
            "custom": rkey in reg.names,
            "raw": _RAW[reg.resources[rkey]] if rkey in reg.resources else None,
            "effective": controls.resource_enabled(reg, rkey),
            "description": _first_line_description(root, rkey),
        })
    # Structural picker entries: always listed by the server, never in the
    # registry (no toggle). Mirrors on_list_resources in server.py.
    config = state.load_gcontext_yaml(root)
    agent_name = config.get("name", root.name)
    structural = [{
        "key": "root",
        "name": agent_name,
        "description": _first_line_description(root, "")
        or "The agent entry point, the top-level index.md.",
        "path": "index.md",
    }]
    if state.discover_modules(root):
        structural.append({
            "key": "modules",
            "name": "modules",
            "description": "Generated index that lists every module.",
            "path": "",
        })
    if state.load_connections(root):
        structural.append({
            "key": "connections",
            "name": "connections",
            "description": "Generated index that lists every connection.",
            "path": "",
        })
    if state.discover_agents(root):
        structural.append({
            "key": "agents",
            "name": "agents",
            "description": "Generated index that lists every installed agent.",
            "path": "",
        })
    known_cmds = set(cmds)
    stale = [
        {"section": "commands", "key": key}
        for key in reg.commands
        if key not in known_cmds
        and not any(key.startswith(t + "_") for t in known_cmds)
    ] + [
        {"section": "resources", "key": key}
        for key in reg.resources if key not in set(res)
    ]
    return {
        "commands": command_rows,
        "resources": resource_rows,
        "structural": structural,
        "pinned": list(reg.pinned),
        "stale": stale,
    }


@mcp.custom_route("/api/controls", methods=["GET"])
async def api_controls(request: Request) -> JSONResponse:
    try:
        return JSONResponse(_controls_payload(_root()))
    except controls.ControlsError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


def _owner_command_keys(root: Path, owner: str) -> list[tuple[str, Path]]:
    """(stable key, path) of every command file the owner holds on disk.
    framework maps to the packaged prompts."""
    if owner == "framework":
        return [(f"framework/{p.stem}", p)
                for p in commands_mod.discover_framework_prompts()]
    return [
        (commands_mod._stable_key(p, root), p)
        for p in commands_mod.discover(root)
        if p.parent.parent.name == owner
    ]


@mcp.custom_route("/api/controls", methods=["POST"])
async def api_controls_post(request: Request) -> JSONResponse:
    root = _root()
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    try:
        if "pin" in body:
            pin, pinned = body.get("pin"), body.get("pinned")
            if not isinstance(pin, str) or not pin or not isinstance(pinned, bool):
                return JSONResponse(
                    {"error": 'a pin change needs {"pin": "<path>", "pinned": true|false}'},
                    status_code=400,
                )
            controls.set_pinned(root, pin, pinned)
            note = "Live now: the resource picker reflects pins on the next list."
        elif "name" in body:
            spec = body.get("name")
            if not isinstance(spec, dict) or not isinstance(spec.get("key"), str) or not spec.get("key"):
                return JSONResponse(
                    {"error": 'a rename needs {"name": {"key": "...", "value": "..."}}'},
                    status_code=400)
            key, value = spec["key"], str(spec.get("value") or "")
            try:
                controls.set_name(root, key, value)
            except ValueError as e:
                return JSONResponse({"error": str(e)}, status_code=400)
            if controls._is_resource_key(key):
                note = "Live now: the picker shows the new title on the next list."
            else:
                commands_mod.load_manifest(root)
                commands_mod.reregister_all(server.mcp, root)
                server._notify_prompts_changed()
                note = ("Renamed live. Reconnect the client to see the new "
                        "name: run /mcp and reconnect the server.")
        elif "bulk" in body:
            spec = body.get("bulk")
            if (not isinstance(spec, dict)
                    or not isinstance(spec.get("owner"), str)
                    or spec.get("value") not in ("on", "off")):
                return JSONResponse(
                    {"error": 'bulk needs {"bulk": {"owner": "...", "value": "on"|"off"}}'},
                    status_code=400)
            owner, value = spec["owner"], spec["value"]
            keys = [k for k, _ in _owner_command_keys(root, owner)]
            if not keys:
                return JSONResponse(
                    {"error": f"no commands found for owner {owner!r}"},
                    status_code=400)
            for k in keys:
                controls.set_entry(root, "commands", k, value)
            note = (f'Saved {len(keys)} entries. Command changes apply after '
                    '"gcontext reload", then reconnect the client: run /mcp.')
        else:
            section, key, value = body.get("section"), body.get("key"), body.get("value")
            if not isinstance(key, str) or not key:
                return JSONResponse({"error": "key is required"}, status_code=400)
            try:
                controls.set_entry(root, section, key, str(value))
            except ValueError as e:
                return JSONResponse({"error": str(e)}, status_code=400)
            if section == "resources":
                note = "Live now: resource listing follows the registry per request."
            elif section == "commands" and key == "framework/setup" and str(value) == "off":
                note = (
                    'Saved. setup is the bootstrap prompt; re-enable it here '
                    'or in controls.yaml when you need it. '
                    'Command changes apply after "gcontext reload", '
                    'then reconnect the client: run /mcp.'
                )
            else:
                note = (
                    'Saved. Command changes apply after "gcontext reload", '
                    'then reconnect the client: run /mcp.'
                )
    except controls.ControlsError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    # apply resource hiding to the live registry now and re-arm the manifest
    # snapshot so the dashboard's own write never trips the staleness warning
    # (command staleness still trips, correctly: those need a reload)
    commands_mod.load_manifest(root)
    server._resnapshot_manifest()
    payload = _controls_payload(root)
    payload["note"] = note
    return JSONResponse(payload)


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
