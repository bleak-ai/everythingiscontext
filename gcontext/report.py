"""The setup report: Block 1 of docs/setup-script.md, computed from state.

build_setup_report scans modules/ for agents (modules whose index.md
frontmatter declares a `connections:` list), matches each declared kind
against the connection.yaml files under connections/, and renders the text
the setup prompt shows verbatim. Code owns this report; the model never
rewrites it.
"""

from pathlib import Path

import yaml

from .commands import parse_command

HEADER = "Welcome to gcontext"
SETUP_FIELD = "setup"
SETUP_PENDING = "pending"
_MIN_PAD = 15


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


def _agents(project_dir: Path) -> list[tuple[str, dict, list]]:
    """(id, frontmatter, declared connections) per agent module, sorted."""
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
        agents.append((meta.get("id") or item.name, meta, declared))
    return agents


def _agent_block(agent_id: str, meta: dict, declared: list, available: set[str]) -> str:
    lines = [f"Agent: {agent_id}", "", "Connections"]
    labels = []
    matches = []
    for entry in declared:
        kind = entry.get("kind") if isinstance(entry, dict) else None
        if isinstance(kind, str) and kind:
            labels.append(kind)
            matches.append(kind in available)
        else:
            labels.append("(no kind)")
            matches.append(False)
    pad = max(max(len(label) for label in labels) + 5, _MIN_PAD)
    for label, matched in zip(labels, matches):
        lines.append(f"  {label:<{pad}}{'OK' if matched else 'MISSING'}")
    if meta.get(SETUP_FIELD) == SETUP_PENDING:
        status = "needs setup"
    elif not all(matches):
        status = "connection missing"
    else:
        status = "ready"
    lines.extend(["", f"Status: {status}"])
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
        for agent_id, meta, declared in agents
    ]
    return HEADER + "\n" + "\n\n".join(blocks)
