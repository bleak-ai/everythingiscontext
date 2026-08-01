"""The context ledger: every pipe that inserts context into the agent.

Statuses: loaded (pushed at start), on demand (agent pulls, visible as a
tool call), skipped (nothing to push), uncontrolled (runtime-owned).
"""

from pathlib import Path

from . import commands as commands_mod
from . import state


def build(root: Path) -> list[dict]:
    instructions = root / "instructions.md"
    connections = state.load_connections(root)
    modules = state.discover_modules(root)
    n_files = sum(len(state.connection_files(root, c)) for c in connections)
    n_files += sum(len(state.module_files(root, m)) for m in modules)

    ledger = []

    if instructions.exists():
        n = len(instructions.read_text().splitlines())
        ledger.append({"id": "G0", "label": "instructions.md", "detail": f"pushed at connect in the MCP handshake ({n} lines)", "status": "loaded"})
    else:
        ledger.append({"id": "G0", "label": "instructions.md", "detail": "file missing, nothing pushed at connect", "status": "skipped"})

    ledger.append({"id": "G1", "label": "tool descriptions", "detail": "6 gcontext tools, pushed at connect", "status": "loaded"})
    ledger.append({"id": "G2", "label": "overview()", "detail": "project map, secret status", "status": "on demand"})
    g3_detail = f"{n_files} files in connections/ + modules/"
    if state.archived(root):
        g3_detail += "; archive/ not scanned, readable by path"
    ledger.append({"id": "G3", "label": "read_file()", "detail": g3_detail, "status": "on demand"})
    ledger.append({"id": "G4", "label": "list_dir() / grep()", "detail": "tree navigation and search, matches only", "status": "on demand"})
    ledger.append({"id": "G5", "label": "run_script() output", "detail": "secret values scrubbed", "status": "on demand"})
    n_commands = len(commands_mod.discover(root))
    ledger.append({"id": "G6", "label": "commands", "detail": f"{n_commands} command(s) as MCP prompts; a command's text enters context only when the user invokes it", "status": "on demand"})

    ledger.append({"id": "R1", "label": "runtime system prompt", "detail": "runtime-owned", "status": "uncontrolled"})
    ledger.append({"id": "R2", "label": "user/project CLAUDE.md", "detail": "runtime-owned", "status": "uncontrolled"})
    ledger.append({"id": "R3", "label": "other MCP servers, skills, memory", "detail": "runtime-owned", "status": "uncontrolled"})

    return ledger


def render_plain(root: Path) -> list[str]:
    lines = []
    for i, pipe in enumerate(build(root), 1):
        label = f"{pipe['label']} ".ljust(36, ".")
        lines.append(f"{i}. [{pipe['id']}] {label} {pipe['status']}: {pipe['detail']}")
    return lines
