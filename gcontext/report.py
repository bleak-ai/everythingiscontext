"""The code-built reports: Block 1 of docs/setup-script.md, computed from state.

build_setup_report scans modules/ for agents (modules whose index.md
frontmatter declares a `connections:` list), matches each declared kind
against the connection.yaml files under connections/, and renders the text
the setup prompt shows verbatim. build_explain_report renders the explain
prompt's report the same way: the agent list without an agent id, the
per-agent Does / Connects / Learns / Flow block with one. Code owns these
reports; the model never rewrites them. Every wording token lives in
report_strings.py; this module owns only the computation and the layout.
"""

import textwrap
from datetime import datetime
from pathlib import Path

import yaml

from . import report_strings as S
from . import state
from .commands import parse_command

SETUP_FIELD = "setup"
SETUP_PENDING = "pending"
_MIN_PAD = 15
_LABEL_PAD = 10
_WRAP_WIDTH = 62


def _available_kinds(project_dir: Path) -> set[str]:
    """Kinds carried by the connection.yaml files under connections/."""
    return {c.kind for c in state.load_connections(project_dir).values() if c.kind}


def _agents(project_dir: Path) -> list[tuple[str, dict, list, Path]]:
    """(id, frontmatter, declared connections, path) per agent module, sorted."""
    agents = []
    for folder_name in ("agents", "modules"):
        scan_dir = project_dir / folder_name
        if not scan_dir.is_dir():
            continue
        for item in sorted(scan_dir.iterdir()):
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
            agent_id = meta.get("id") or item.name
            if not any(a[0] == agent_id for a in agents):
                agents.append((agent_id, meta, declared, item))
    return agents


def _connection_rows(declared: list, available: set[str]) -> list[tuple[str, bool]]:
    """(label, matched) per declared connection, in declaration order."""
    rows = []
    for entry in declared:
        kind = entry.get("kind") if isinstance(entry, dict) else None
        if isinstance(kind, str) and kind:
            rows.append((kind, kind in available))
        else:
            rows.append((S.NO_KIND, False))
    return rows


def _status(meta: dict, rows: list[tuple[str, bool]]) -> str:
    if meta.get(SETUP_FIELD) == SETUP_PENDING:
        return S.STATUS_NEEDS_SETUP
    if not all(matched for _, matched in rows):
        return S.STATUS_CONNECTION_MISSING
    return S.STATUS_READY


def _agent_block(agent_id: str, meta: dict, declared: list, available: set[str]) -> str:
    lines = [f"{S.AGENT_LABEL} {agent_id}", "", S.CONNECTIONS_HEADING]
    rows = _connection_rows(declared, available)
    pad = max(max(len(label) for label, _ in rows) + 5, _MIN_PAD)
    for label, matched in rows:
        lines.append(f"  {label:<{pad}}{S.CONNECTION_OK if matched else S.CONNECTION_MISSING}")
    lines.extend(["", f"{S.STATUS_LABEL} {_status(meta, rows)}"])
    return "\n".join(lines)


def build_setup_report(project_dir: Path) -> str:
    """The Block 1 report for every installed agent, or the no-agents line."""
    project_dir = Path(project_dir)
    agents = _agents(project_dir)
    if not agents:
        return f"{S.HEADER}\n{S.NO_AGENTS}"
    available = _available_kinds(project_dir)
    blocks = [
        _agent_block(agent_id, meta, declared, available)
        for agent_id, meta, declared, _path in agents
    ]
    return S.HEADER + "\n" + "\n\n".join(blocks)


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
        lines.append(f"{item.name}/  {n} {S.FILES_WORD}")
    files = _module_files(module_dir)
    if files:
        newest = max(f.stat().st_mtime for f in files)
        stamp = datetime.fromtimestamp(newest).strftime("%Y-%m-%d")
        lines.append(f"{S.LAST_ACTIVITY_LABEL}  {stamp}")
    return lines


def _explain_block(agent_id: str, meta: dict, declared: list, available: set[str], module_dir: Path) -> str:
    lines = [f"{S.AGENT_LABEL} {agent_id}", ""]
    lines.extend(_labeled(S.DOES_LABEL, _wrapped(meta.get("description") or "(no description)")))
    rows = _connection_rows(declared, available)
    pad = max(max(len(label) for label, _ in rows) + 5, _MIN_PAD)
    lines.extend(_labeled(S.CONNECTS_LABEL, [
        f"{label:<{pad}}{S.CONNECTION_OK if matched else S.CONNECTION_MISSING}"
        for label, matched in rows
    ]))
    lines.extend(_labeled(S.LEARNS_LABEL, _learns_lines(module_dir, meta)))
    flow = meta.get("flow")
    if isinstance(flow, list) and flow:
        flow_lines = [f"{i}. {step}" for i, step in enumerate(flow, 1)]
    else:
        flow_lines = [S.FLOW_NOT_DECLARED]
    lines.extend(_labeled(S.FLOW_LABEL, flow_lines))
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
            return f"{S.HEADER}\n{S.NO_AGENTS}"
        available = _available_kinds(project_dir)
        pad = max(max(len(a[0]) for a in agents) + 5, _MIN_PAD)
        lines = [S.HEADER]
        for agent_id, meta, declared, _path in agents:
            rows = _connection_rows(declared, available)
            lines.append(f"{agent_id:<{pad}}{_status(meta, rows)}")
        return "\n".join(lines)
    for agent_id, meta, declared, path in agents:
        if agent_id == agent:
            return _explain_block(agent_id, meta, declared, _available_kinds(project_dir), path)
    ids = ", ".join(a[0] for a in agents) if agents else S.NO_INSTALLED_IDS
    return S.UNKNOWN_AGENT.format(agent=agent, ids=ids)
