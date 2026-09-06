#!/usr/bin/env python3
"""Sync generated index blocks and check context/ structure (v9).

Keeps the tree consistent with context/system/rules.md.
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import rules_config
except ImportError:
    rules_config = None


TASK_STATE_NAMES = ("backlog", "in_progress", "done")
EXEMPT_DIRECTORIES = {
    ".claude",
    ".git",
    ".venv",
    "__pycache__",
    "data",
    "logs",
    "node_modules",
    "out",
    "runs",
    "versions",
}
MARKER = "<!-- GENERATED BELOW -->"
STAMP_TEXT = (
    "by context/system/scripts/sync-index-files.py."
    " Do not hand-edit below the marker."
)
ENTRY_PATTERN = re.compile(r"^- (.+?) \(([^)]+)\): (.*)$")
ENTRY_CONTINUATION_PATTERN = re.compile(r"^  (\S.*)$")
POINTER_PATTERN = re.compile(r"^-> (\S+\.md):")


# ---- path helpers ----

def relative_name(path, root):
    """Return a stable repository-relative path."""
    return path.relative_to(root).as_posix()


def repository_root(script_path):
    """Return the repository root for the checker in system/scripts/."""
    return script_path.resolve().parents[3]


def has_uppercase(name):
    """Return whether a name contains an uppercase letter."""
    return any(c.isupper() for c in name)


def is_exempt_path(path, root):
    """Return whether a path is inside an exempt directory."""
    relative_parts = path.relative_to(root).parts
    if relative_parts[:2] == ("context", "journal"):
        return True
    if any(part in EXEMPT_DIRECTORIES for part in relative_parts[:-1]):
        return True
    return is_package_subpath(path, root, "state")


def is_package_subpath(path, root, folder_name):
    """Return whether a path is inside one named package subfolder."""
    parts = path.relative_to(root).parts
    return (
        len(parts) >= 4
        and parts[0] == "context"
        and parts[1] == "packages"
        and parts[3] == folder_name
    )


# ---- file scanning ----

def context_markdown_files(root):
    """List context Markdown files that are in scope."""
    context = root / "context"
    if not context.is_dir():
        return []
    return sorted(
        path
        for path in context.rglob("*.md")
        if path.is_file() and not is_exempt_path(path, root)
    )


def folder_index_path(folder):
    """Return the generated index path for a folder."""
    return folder / "index.md"


def task_state_paths(root):
    """Return the three allowed task state folder paths."""
    tasks = root / "context/packages/tasks"
    return {tasks / name for name in TASK_STATE_NAMES}


def visible_entries(folder, root):
    """List direct entries that count toward an index."""
    index_path = folder_index_path(folder)
    entries = []
    for entry in folder.iterdir():
        if entry == index_path:
            continue
        if entry.is_dir() and entry.name in EXEMPT_DIRECTORIES:
            continue
        if entry.is_dir() and is_package_subpath(entry, root, "state"):
            continue
        entries.append(entry)
    if folder == root / "context/packages/tasks":
        for state_path in task_state_paths(root):
            if state_path not in entries:
                entries.append(state_path)
    return sorted(entries, key=lambda item: item.name)


def governed_folders(root):
    """List every folder governed by generated indexes."""
    folders = []
    for name in ("context/system", "context/packages", "context/project"):
        base = root / name
        if not base.is_dir():
            continue
        for current, directory_names, _ in os.walk(base):
            current_path = Path(current)
            directory_names[:] = sorted(
                d
                for d in directory_names
                if d not in EXEMPT_DIRECTORIES
                and not is_package_subpath(
                    current_path / d,
                    root,
                    "state",
                )
            )
            folders.append(current_path)
    return sorted(set(folders), key=lambda item: relative_name(item, root))


# ---- purpose extraction ----

def purpose_candidate(path):
    """Read the first paragraph after a Markdown title."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        return None
    purpose_lines = []
    for line in lines[1:]:
        candidate = line.strip()
        if not candidate:
            if purpose_lines:
                break
            continue
        purpose_lines.append(candidate)
    return "\n".join(purpose_lines) if purpose_lines else None


def has_valid_purpose(path):
    """Return whether a context file has a valid short purpose block."""
    purpose = purpose_candidate(path)
    lines = purpose.splitlines() if purpose else []
    return bool(
        1 <= len(lines) <= 2
        and all(len(line) <= 80 for line in lines)
    )


def folder_description(folder):
    """First purpose line from a folder's index.md, above the marker."""
    index_path = folder_index_path(folder)
    if not index_path.is_file():
        return None
    folder_purpose, _ = previous_index_data(index_path)
    for line in folder_purpose:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


# ---- index reading and writing ----

def previous_index_data(index_path):
    """Read the folder purpose and saved entry descriptions from an index."""
    if not index_path.is_file():
        return [], {}
    lines = index_path.read_text(encoding="utf-8").splitlines()
    if MARKER not in lines:
        start = 1
        if len(lines) > 1 and lines[1].startswith("GENERATED "):
            start = 2
        folder_purpose = lines[start:]
        while folder_purpose and not folder_purpose[0].strip():
            folder_purpose.pop(0)
        while folder_purpose and not folder_purpose[-1].strip():
            folder_purpose.pop()
        return folder_purpose, {}
    marker_position = lines.index(MARKER)
    folder_purpose = lines[2:marker_position]
    while folder_purpose and not folder_purpose[0].strip():
        folder_purpose.pop(0)
    while folder_purpose and not folder_purpose[-1].strip():
        folder_purpose.pop()
    descriptions = {}
    current_name = None
    for line in lines[marker_position + 1:]:
        match = ENTRY_PATTERN.match(line)
        if match:
            descriptions[match.group(1)] = match.group(3)
            current_name = match.group(1)
            continue
        continuation = ENTRY_CONTINUATION_PATTERN.match(line)
        if continuation and current_name is not None:
            descriptions[current_name] += f"\n{continuation.group(1)}"
            current_name = None
            continue
        current_name = None
    return folder_purpose, descriptions


def rendered_description(description):
    """Render a one- or two-line description in index continuation form."""
    lines = description.splitlines()[:2]
    return lines[0] + "".join(f"\n  {line}" for line in lines[1:])


def entry_line(entry, root, descriptions):
    """Render one generated index entry."""
    if entry.is_dir() or entry in task_state_paths(root):
        name = f"{entry.name}/"
        description = folder_description(entry) or "TODO(describe)"
        return f"- {name} (dir): {rendered_description(description)}"

    name = entry.name
    is_context_markdown = (
        entry.suffix == ".md"
        and relative_name(entry, root).startswith("context/")
    )
    if is_context_markdown:
        entry_type = "md"
        description = purpose_candidate(entry) or "TODO(describe)"
    else:
        entry_type = entry.suffix.lstrip(".").lower() or "file"
        description = descriptions.get(name, "") or "TODO(describe)"
    return f"- {name} ({entry_type}): {rendered_description(description)}"


def render_index(folder, root, today):
    """Render the current generated index content for a folder."""
    index_path = folder_index_path(folder)
    folder_purpose, descriptions = previous_index_data(index_path)
    lines = [
        f"# {folder.name}/",
        f"GENERATED {today.isoformat()} {STAMP_TEXT}",
        "",
    ]
    if folder_purpose:
        lines.extend(folder_purpose)
        lines.append("")
    lines.append(MARKER)
    lines.extend(
        entry_line(entry, root, descriptions)
        for entry in visible_entries(folder, root)
    )
    return "\n".join(lines) + "\n"


def write_indexes(root, today):
    """Create or refresh all required generated indexes."""
    root = Path(root).resolve()
    # Write children before parents so folder descriptions are current.
    for folder in reversed(governed_folders(root)):
        index_path = folder_index_path(folder)
        index_path.write_text(
            render_index(folder, root, today),
            encoding="utf-8",
        )


# ---- checks ----

def naming_failures(root):
    """Report context files or folders with uppercase letters."""
    failures = []
    context = root / "context"
    if not context.is_dir():
        return failures
    for path in sorted(context.rglob("*")):
        if is_exempt_path(path, root):
            continue
        if "__pycache__" in path.parts:
            continue
        name = path.name
        if name == "index.md":
            continue
        if has_uppercase(name):
            failures.append(
                f"uppercase in name: {relative_name(path, root)} "
                "(use lowercase and hyphens)"
            )
    return failures


def completeness_failures(root):
    """Report index entries that are missing or refer to absent entries."""
    failures = []
    for folder in governed_folders(root):
        index_path = folder_index_path(folder)
        if not index_path.is_file():
            continue
        entries = visible_entries(folder, root)
        entry_names = set()
        for entry in entries:
            if entry.is_dir() or entry in task_state_paths(root):
                entry_names.add(f"{entry.name}/")
            else:
                entry_names.add(entry.name)
        _, descriptions = previous_index_data(index_path)
        indexed_names = set(descriptions.keys())
        rel = relative_name(index_path, root)
        for name in sorted(entry_names - indexed_names):
            failures.append(
                f"missing index entry: {rel}: {name} "
                "(run: uv run context/system/scripts/sync-index-files.py --write)"
            )
        for name in sorted(indexed_names - entry_names):
            failures.append(
                f"orphan index entry: {rel}: {name} "
                "(entry does not exist; run --write to remove it)"
            )
    return failures


def todo_failures(root):
    """Report TODO(describe) placeholders in any generated index."""
    failures = []
    for folder in governed_folders(root):
        index_path = folder_index_path(folder)
        if not index_path.is_file():
            continue
        for line_number, line in enumerate(
            index_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "TODO(describe)" not in line:
                continue
            match = ENTRY_PATTERN.match(line)
            detail = match.group(1) if match else str(line_number)
            failures.append(
                f"TODO(describe): {relative_name(index_path, root)}: {detail} "
                "(replace with a 1-2 line description of the file or directory)"
            )
    return failures


def dangling_pointer_failures(root):
    """Report pointer lines whose target file does not exist."""
    failures = []
    project = root / "context/project"
    if not project.is_dir():
        return failures
    for path in sorted(project.rglob("*.md")):
        if not path.is_file():
            continue
        if is_exempt_path(path, root):
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            m = POINTER_PATTERN.match(line)
            if m:
                target = m.group(1)
                target_path = project / target
                if not target_path.is_file():
                    rel = relative_name(path, root)
                    failures.append(
                        f"dangling pointer: {rel}:{lineno} "
                        f"-> {target}"
                    )
    return failures


def check_repository(root, today, toggles=None):
    """Run every context standard check."""
    root = Path(root).resolve()
    failures = []

    # Naming: uppercase
    failures.extend(naming_failures(root))

    # Purpose line per non-index markdown file
    for path in context_markdown_files(root):
        if path.name == "index.md":
            continue
        if not has_valid_purpose(path):
            failures.append(
                f"missing purpose line: {relative_name(path, root)} "
                "(add 1-2 lines under the title, max 80 chars each)"
            )

    # Missing index.md per governed folder
    for folder in governed_folders(root):
        index_path = folder_index_path(folder)
        if not index_path.is_file():
            failures.append(
                f"missing index: {relative_name(index_path, root)} "
                "(run: uv run context/system/scripts/sync-index-files.py --write)"
            )

    # Index completeness
    failures.extend(completeness_failures(root))

    # TODO(describe) placeholders
    failures.extend(todo_failures(root))

    # Dangling pointer lines
    failures.extend(dangling_pointer_failures(root))

    return failures


# ---- CLI ----

def parse_arguments():
    """Parse the generator mode."""
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    return parser.parse_args()


def main():
    """Run the command-line interface."""
    arguments = parse_arguments()
    root = repository_root(Path(__file__))
    today = datetime.date.today()
    toggles = rules_config.load() if rules_config else {}
    if arguments.write:
        write_indexes(root, today)
        return 0

    failures = check_repository(root, today, toggles)
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
