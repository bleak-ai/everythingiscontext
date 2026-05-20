"""Generate workspace-level files: llms.txt, system.md, structure.md.

These files are regenerated on every load/unload operation.
"""
import logging
from pathlib import Path

import yaml

from core.kind_specs import render_kind_specs_md, render_info_md_sections_md
from core.manifest import render_schema_md

log = logging.getLogger(__name__)


def extract_module_summary(llms_txt_content: str) -> str:
    """Extract the > blockquote description from a module's llms.txt."""
    for line in llms_txt_content.splitlines():
        if line.startswith("> "):
            return line[2:].strip()
    return ""


def generate_root_llms_txt(context_dir: Path) -> None:
    """Generate root llms.txt from loaded modules' llms.txt files.

    Skips dot-prefixed directories (e.g. .claude).
    """
    entries = []
    for mod_dir in sorted(context_dir.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("."):
            continue
        llms_file = mod_dir / "llms.txt"
        if llms_file.exists():
            summary = extract_module_summary(llms_file.read_text())
        else:
            summary = "Context module"
        entries.append(f"- [{mod_dir.name}]({mod_dir.name}/llms.txt): {summary}")

    lines = ["# Context", ""]
    lines.extend(entries)
    (context_dir / "llms.txt").write_text("\n".join(lines) + "\n")


def generate_structure_md(context_dir: Path, info_sections: list | None = None) -> None:
    """Write context/structure.md from manifest schema and kind specs.

    Auto-generated reference for module.yaml fields, per-kind file
    requirements, and info.md section structure.

    Accepts optional info_sections so the platform can pass its extended
    list (with "Python packages" section). Defaults to core's 6-section list.
    """
    body = "\n".join([
        "# Module Structure",
        "",
        "Auto-generated from `manifest.py` and `kind_specs.py`. Do not edit by hand.",
        "",
        render_schema_md(),
        "",
        "## Module kinds",
        "",
        render_kind_specs_md(),
        "## Starter file structure",
        "",
        render_info_md_sections_md(info_sections),
    ])
    (context_dir / "structure.md").write_text(body)


def generate_system_md(context_dir: Path, template_content: str) -> None:
    """Write context/system.md from a template string + loaded modules table.

    The caller is responsible for reading/assembling the template content.
    This function appends the loaded modules table at the end.
    Skips dot-prefixed directories.
    """
    rows: list[tuple[str, str, str]] = []
    for mod_dir in sorted(context_dir.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("."):
            continue
        kind = "unknown"
        manifest_file = mod_dir / "module.yaml"
        if manifest_file.exists():
            try:
                data = yaml.safe_load(manifest_file.read_text())
                kind = data.get("kind", "integration") if data else "unknown"
            except Exception:
                log.warning("Failed to parse %s", manifest_file)
        llms_file = mod_dir / "llms.txt"
        summary = ""
        if llms_file.exists():
            summary = extract_module_summary(llms_file.read_text())
        rows.append((mod_dir.name, kind, summary))

    lines = [
        "",
        "## Loaded modules",
        "",
    ]
    if rows:
        lines.append("| Module | Kind | Summary |")
        lines.append("|--------|------|---------|")
        for name, kind, summary in rows:
            lines.append(f"| {name} | {kind} | {summary} |")
    else:
        lines.append("No modules loaded.")

    (context_dir / "system.md").write_text(template_content + "\n".join(lines) + "\n")
