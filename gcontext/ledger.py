"""The context ledger: every pipe that inserts context into the agent.

Statuses: loaded (pushed at start), on demand (agent pulls, visible as a
tool call), skipped (nothing to push), uncontrolled (runtime-owned).
"""

from pathlib import Path

from . import commands as commands_mod
from . import fs
from . import state


def build(root: Path) -> list[dict]:
    instructions = root / "agent.md"
    connections = state.load_connections(root)
    modules = state.discover_modules(root)
    n_files = sum(len(state.connection_files(root, c)) for c in connections)
    n_files += sum(len(state.module_files(root, m)) for m in modules)

    ledger = []

    base = Path(__file__).parent / "prompts" / "framework-instructions.md"
    n_base = len(base.read_text().splitlines())
    ledger.append({"id": "G0", "label": "framework instructions", "detail": f"framework-owned, pushed at connect in the MCP handshake ({n_base} lines)", "status": "loaded"})

    if instructions.exists():
        n = len(instructions.read_text().splitlines())
        ledger.append({"id": "G1", "label": "agent.md", "detail": f"pushed at connect in the MCP handshake ({n} lines)", "status": "loaded"})
    else:
        ledger.append({"id": "G1", "label": "agent.md", "detail": "file missing, only the framework instructions pushed at connect", "status": "skipped"})

    ledger.append({"id": "G2", "label": "tool descriptions", "detail": "7 gcontext tools, pushed at connect", "status": "loaded"})
    g3_detail = f"{n_files} files in connections/ + modules/"
    if state.archived(root):
        g3_detail += "; archive/ not scanned, readable by path"
    ledger.append({"id": "G3", "label": "read_file()", "detail": g3_detail, "status": "on demand"})
    ledger.append({"id": "G4", "label": "list_dir() / grep()", "detail": "tree navigation and search, matches only", "status": "on demand"})
    ledger.append({"id": "G5", "label": "run_script() / run_adhoc_script() output", "detail": "secret values scrubbed", "status": "on demand"})
    n_commands = len(commands_mod.discover(root))
    n_disabled = len(commands_mod._DISABLED)
    disabled_note = f", {n_disabled} disabled" if n_disabled else ""
    builtin = [p.stem for p in commands_mod.discover_framework_prompts()]
    ledger.append({"id": "G6", "label": "commands", "detail": f"{len(builtin)} built-in ({', '.join(builtin)}) + {n_commands} project command(s){disabled_note} as MCP prompts; a command's text enters context only when the user invokes it", "status": "on demand"})
    n_resources = len(fs.walk_files(root))
    ledger.append({"id": "G7", "label": "resources", "detail": f"{n_resources} state files as MCP resources (gcontext://<path>); one enters context only when attached", "status": "on demand"})

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
