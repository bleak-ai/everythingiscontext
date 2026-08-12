"""The code-built reports: Block 1 of docs/setup-script.md, computed from state.

build_setup_report scans modules/ for agents (modules whose index.md
frontmatter declares a `connections:` list), matches each declared kind
against the connection.yaml files under connections/, and renders the text
the setup prompt shows verbatim. build_explain_report renders the explain
prompt's report the same way: the agent list without an agent id, the
per-agent Does / Connects / Learns / Flow block with one. Code owns these
reports; the model never rewrites them.
"""

import textwrap
from datetime import datetime
from pathlib import Path

import yaml

from .commands import parse_command

HEADER = "Welcome to gcontext"
SETUP_FIELD = "setup"
SETUP_PENDING = "pending"
_MIN_PAD = 15
_LABEL_PAD = 10
_WRAP_WIDTH = 62


def _available_kinds(project_dir: Path) -> set[str]:
    """Kinds carried by the connection.yaml files under connections/."""
    kinds = set()
    conns_dir = project_dir / "connections"
    if not conns_dir.is_dir():
        return kinds
    for item in sorted(conns_dir.iterdir()):
        if not item.is_dir():
            continue
        conn_file = item / "connection.yaml"
        if not conn_file.exists():
            continue
        try:
            data = yaml.safe_load(conn_file.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        kind = data.get("kind") if isinstance(data, dict) else None
        if isinstance(kind, str) and kind:
            kinds.add(kind)
    return kinds


def _agents(project_dir: Path) -> list[tuple[str, dict, list, Path]]:
    """(id, frontmatter, declared connections, path) per agent module, sorted."""
    modules_dir = project_dir / "modules"
    if not modules_dir.is_dir():
        return []
    agents = []
    for item in sorted(modules_dir.iterdir()):
        if not item.is_dir():
            continue
        index = item / "index.md"
        if not index.is_file():
            continue
        try:
            meta, _ = parse_command(index.read_text(encoding="utf-8"))
        except (ValueError, OSError, yaml.YAMLError):
            continue
        declared = meta.get("connections")
        if not isinstance(declared, list) or not declared:
            continue
        agents.append((meta.get("id") or item.name, meta, declared, item))
    return agents


def _connection_rows(declared: list, available: set[str]) -> list[tuple[str, bool]]:
    """(label, matched) per declared connection, in declaration order."""
    rows = []
    for entry in declared:
        kind = entry.get("kind") if isinstance(entry, dict) else None
        if isinstance(kind, str) and kind:
            rows.append((kind, kind in available))
        else:
            rows.append(("(no kind)", False))
    return rows


def _status(meta: dict, rows: list[tuple[str, bool]]) -> str:
    if meta.get(SETUP_FIELD) == SETUP_PENDING:
        return "needs setup"
    if not all(matched for _, matched in rows):
        return "connection missing"
    return "ready"


def _agent_block(agent_id: str, meta: dict, declared: list, available: set[str]) -> str:
    lines = [f"Agent: {agent_id}", "", "Connections"]
    rows = _connection_rows(declared, available)
    pad = max(max(len(label) for label, _ in rows) + 5, _MIN_PAD)
    for label, matched in rows:
        lines.append(f"  {label:<{pad}}{'OK' if matched else 'MISSING'}")
    lines.extend(["", f"Status: {_status(meta, rows)}"])
    return "\n".join(lines)


def build_setup_report(project_dir: Path) -> str:
    """The Block 1 report for every installed agent, or the no-agents line."""
    project_dir = Path(project_dir)
    agents = _agents(project_dir)
    if not agents:
        return f"{HEADER}\nNo agents installed."
    available = _available_kinds(project_dir)
    blocks = [
        _agent_block(agent_id, meta, declared, available)
        for agent_id, meta, declared, _path in agents
    ]
    return HEADER + "\n" + "\n\n".join(blocks)


def _labeled(label: str, value_lines: list[str]) -> list[str]:
    """The value lines with `label` in the aligned label column of line one."""
    return [
        f"{label if i == 0 else '':<{_LABEL_PAD}}{line}"
        for i, line in enumerate(value_lines)
    ]


def _wrapped(text: str) -> list[str]:
    return textwrap.wrap(
        " ".join(text.split()), width=_WRAP_WIDTH, break_on_hyphens=False
    )


def _module_files(module_dir: Path) -> list[Path]:
    """Every non-hidden file under the module, machine folders excluded."""
    files = []
    for path in sorted(module_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(module_dir)
        if any(part.startswith((".", "__")) for part in rel.parts):
            continue
        files.append(path)
    return files


def _learns_lines(module_dir: Path, meta: dict) -> list[str]:
    lines = []
    learns = meta.get("learns")
    if isinstance(learns, str) and learns.strip():
        lines.extend(_wrapped(learns))
    for item in sorted(module_dir.iterdir()):
        if not item.is_dir() or item.name.startswith((".", "__")):
            continue
        n = len(_module_files(item))
        lines.append(f"{item.name}/  {n} files")
    files = _module_files(module_dir)
    if files:
        newest = max(f.stat().st_mtime for f in files)
        stamp = datetime.fromtimestamp(newest).strftime("%Y-%m-%d")
        lines.append(f"last activity  {stamp}")
    return lines


def _explain_block(agent_id: str, meta: dict, declared: list, available: set[str], module_dir: Path) -> str:
    lines = [f"Agent: {agent_id}", ""]
    lines.extend(_labeled("Does", _wrapped(meta.get("description") or "(no description)")))
    rows = _connection_rows(declared, available)
    pad = max(max(len(label) for label, _ in rows) + 5, _MIN_PAD)
    lines.extend(_labeled("Connects", [
        f"{label:<{pad}}{'OK' if matched else 'MISSING'}" for label, matched in rows
    ]))
    lines.extend(_labeled("Learns", _learns_lines(module_dir, meta)))
    flow = meta.get("flow")
    if isinstance(flow, list) and flow:
        flow_lines = [f"{i}. {step}" for i, step in enumerate(flow, 1)]
    else:
        flow_lines = ["not declared"]
    lines.extend(_labeled("Flow", flow_lines))
    return "\n".join(lines)


def build_explain_report(project_dir: Path, agent: str | None = None) -> str:
    """The explain report: the agent list, or one agent's full block.

    Without `agent`: one line per installed agent, id plus status, under the
    shared header. With an agent id: the Does / Connects / Learns / Flow
    block for that agent. An unknown id gets a one-line message listing the
    valid ids.
    """
    project_dir = Path(project_dir)
    agents = _agents(project_dir)
    if not agent:
        if not agents:
            return f"{HEADER}\nNo agents installed."
        available = _available_kinds(project_dir)
        pad = max(max(len(a[0]) for a in agents) + 5, _MIN_PAD)
        lines = [HEADER]
        for agent_id, meta, declared, _path in agents:
            rows = _connection_rows(declared, available)
            lines.append(f"{agent_id:<{pad}}{_status(meta, rows)}")
        return "\n".join(lines)
    for agent_id, meta, declared, path in agents:
        if agent_id == agent:
            return _explain_block(agent_id, meta, declared, _available_kinds(project_dir), path)
    ids = ", ".join(a[0] for a in agents) if agents else "none"
    return f'Unknown agent "{agent}". Installed agents: {ids}.'
