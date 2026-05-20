"""Per-kind module structure: required files, default growth folders, purpose.

Single source of truth for how an `integration`, `task`, or `workflow`
module is laid out on disk.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KindSpec:
    kind: str
    purpose: str
    required_files: list[str]
    starter_file: str
    starter_outline: str
    default_growth_folders: list[dict]  # [{"name": "notes", "path": "notes/<date-slug>.md"}]


KIND_SPECS: dict[str, KindSpec] = {
    "integration": KindSpec(
        kind="integration",
        purpose="Reusable access to an external service, API, database, or local tool.",
        required_files=["module.yaml", "llms.txt", "info.md"],
        starter_file="info.md",
        starter_outline="Purpose, Access, Operations, Example usage.",
        default_growth_folders=[
            {"name": "notes", "path": "notes/<date-slug>.md"},
        ],
    ),
    "task": KindSpec(
        kind="task",
        purpose="A bounded outcome needing progress tracking, subtasks, findings.",
        required_files=["module.yaml", "llms.txt", "brief.md", "status.md"],
        starter_file="brief.md",
        starter_outline="Goal and initial request; status.md tracks subtasks.",
        default_growth_folders=[
            {"name": "progress", "path": "progress/<date-slug>.md"},
        ],
    ),
    "workflow": KindSpec(
        kind="workflow",
        purpose="A repeatable procedure or playbook that should improve across runs.",
        required_files=["module.yaml", "llms.txt", "steps.md"],
        starter_file="steps.md",
        starter_outline="The repeatable steps, numbered.",
        default_growth_folders=[
            {"name": "runs", "path": "runs/<date-slug>.md"},
            {"name": "lessons", "path": "lessons/<date-slug>.md"},
        ],
    ),
}


def render_kind_specs_md() -> str:
    """Render KIND_SPECS as markdown for structure.md."""
    lines: list[str] = []
    for spec in KIND_SPECS.values():
        lines.append(f"### `{spec.kind}`")
        lines.append("")
        lines.append(spec.purpose)
        lines.append("")
        lines.append("**Files written at creation:**")
        for f in spec.required_files:
            note = f" - {spec.starter_outline}" if f == spec.starter_file else ""
            lines.append(f"- `{f}`{note}")
        if spec.default_growth_folders:
            lines.append("")
            lines.append(
                "**Default growth folders** (lazy: created on first entry; "
                "seed these into `llms.txt` `## Where to write` at module creation):"
            )
            for ga in spec.default_growth_folders:
                lines.append(f"- `{ga['name']}` -> `{ga['path']}`")
        lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class InfoSection:
    name: str
    purpose: str
    format: str  # "freeform" or description of strict format


# Core version: 6 sections (no "Python packages" — that's added by Context Agora)
INTEGRATION_INFO_SECTIONS: list[InfoSection] = [
    InfoSection(
        "Purpose",
        "One-line summary of what this integration gives the agent access to.",
        "freeform",
    ),
    InfoSection(
        "Where it lives",
        "Upstream system: URL, host, endpoint, or local path.",
        "freeform",
    ),
    InfoSection(
        "Auth & access",
        "How the agent authenticates. Required secret names are written as `UPPER_CASE` in backticks.",
        "strict: secret names as `UPPER_CASE` backtick tokens",
    ),
    InfoSection(
        "Key entities",
        "Domain objects the agent can read or write.",
        "freeform",
    ),
    InfoSection(
        "Operations",
        "Common calls or queries with short examples.",
        "freeform",
    ),
    InfoSection(
        "Examples",
        "Runnable snippets.",
        "freeform",
    ),
]


def render_info_md_sections_md(sections: list[InfoSection] | None = None) -> str:
    """Render the integration kind's expected info.md sections for structure.md.

    Accepts an optional sections list so the platform can pass an extended
    list (e.g., with "Python packages" section). Defaults to core's 6-section list.
    """
    sections = sections or INTEGRATION_INFO_SECTIONS
    lines: list[str] = ["### `info.md` sections (integration kind)", ""]
    for s in sections:
        lines.append(f"- `## {s.name}` -- {s.purpose}")
        if s.format != "freeform":
            lines.append(f"  - Format: {s.format}")
    lines.append("")
    return "\n".join(lines)
