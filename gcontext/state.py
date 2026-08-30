"""Project state scanning: connections, modules, agents, archive.

Everything here is a pure read of the project folder. Nothing is cached and
nothing is stored: state is computed from the files on every call.
"""

from pathlib import Path

import yaml

from .models import ConnectionManifest, ModuleManifest


def load_gcontext_yaml(root: Path) -> dict:
    p = root / "gcontext.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text()) or {}
    return {}


def load_connections(root: Path) -> dict[str, ConnectionManifest]:
    """Scan connections/ for subdirectories containing connection.yaml."""
    conns_dir = root / "connections"
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


def connection_files(root: Path, name: str) -> list[str]:
    """List non-yaml files in a connection folder."""
    conn_dir = root / "connections" / name
    if not conn_dir.is_dir():
        return []
    files = []
    for f in sorted(conn_dir.rglob("*")):
        if f.is_file() and f.name != "connection.yaml":
            files.append(str(f.relative_to(root)))
    return files


def discover_modules(root: Path) -> dict[str, ModuleManifest]:
    """Scan modules/ for folders; module.yaml is optional."""
    modules_dir = root / "modules"
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


def module_files(root: Path, name: str) -> list[str]:
    """List content files in a module folder."""
    mod_dir = root / "modules" / name
    if not mod_dir.is_dir():
        return []
    files = []
    for f in sorted(mod_dir.rglob("*")):
        if f.is_file() and f.name not in ("module.yaml", ".gitkeep"):
            files.append(str(f.relative_to(root)))
    return files


def discover_agents(root: Path) -> dict[str, ModuleManifest]:
    """Scan agents/ for folders with index.md frontmatter."""
    from .commands import parse_command

    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return {}
    result = {}
    for item in sorted(agents_dir.iterdir()):
        if not item.is_dir():
            continue
        index = item / "index.md"
        if index.exists():
            try:
                meta, _ = parse_command(index.read_text(encoding="utf-8"))
                manifest = ModuleManifest(
                    name=meta.get("name", item.name),
                    description=meta.get("description", ""),
                    tags=meta.get("tags", []),
                )
            except (ValueError, KeyError):
                manifest = ModuleManifest(name=item.name, description="")
        else:
            manifest = ModuleManifest(name=item.name, description="")
        result[item.name] = manifest
    return result


def agent_files(root: Path, name: str) -> list[str]:
    """List content files in an agent folder."""
    agent_dir = root / "agents" / name
    if not agent_dir.is_dir():
        return []
    files = []
    for f in sorted(agent_dir.rglob("*")):
        if f.is_file() and f.name != ".gitkeep":
            files.append(str(f.relative_to(root)))
    return files


def archived(root: Path) -> dict[str, list[str]]:
    """Names of archived items per category, from archive/{connections,modules}/.

    Anything under archive/ is never scanned into the ledger
    counts. It stays readable by path via read_file. Archiving is a plain
    folder move; there is no metadata and no automatic behavior.
    """
    result = {}
    for category in ("connections", "modules", "agents"):
        d = root / "archive" / category
        if d.is_dir():
            items = [i.name for i in sorted(d.iterdir()) if i.is_dir()]
            if items:
                result[category] = items
    return result


def archived_line(root: Path) -> str:
    items_by_cat = archived(root)
    if not items_by_cat:
        return ""
    parts = [f"{len(items)} {cat}" for cat, items in items_by_cat.items()]
    return f"archive/: {', '.join(parts)} (not scanned, readable by path)"
