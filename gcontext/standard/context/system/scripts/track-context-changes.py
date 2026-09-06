#!/usr/bin/env python3
"""Count facts and folders added since the last structure check.

Run after every assistant turn, or from the statusline wrapper.
"""

import argparse
import re
import sys
from pathlib import Path

STRUCTURE_CHECK_RE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}):\s*structure check,\s*(\d+)\s+facts?,\s*(\d+)\s+folders?"
)


def find_root(start: Path) -> Path | None:
    """Walk up from *start* until a directory holds the tracker script."""
    marker = Path("context/system/scripts/track-context-changes.py")
    current = start.resolve()
    for directory in [current, *current.parents]:
        if (directory / marker).is_file():
            return directory
    return None


def count_facts(project: Path) -> int:
    """Count lines that start with '- ' in .md files, excluding index.md."""
    total = 0
    if not project.is_dir():
        return total
    for md in sorted(project.rglob("*.md")):
        if md.name == "index.md":
            continue
        if not md.is_file():
            continue
        for line in md.read_text(encoding="utf-8").splitlines():
            if line.startswith("- "):
                total += 1
    return total


def count_folders(project: Path) -> int:
    """Count every directory under project/."""
    total = 0
    if not project.is_dir():
        return total
    for entry in sorted(project.rglob("*")):
        if entry.is_dir():
            total += 1
    return total


def read_baseline(log_path: Path) -> tuple[int, int, str | None]:
    """Read the newest structure check line from log.md.

    Returns (facts, folders, date_string). When no line exists,
    returns (0, 0, None).
    """
    if not log_path.is_file():
        return 0, 0, None
    last_date = None
    last_facts = 0
    last_folders = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = STRUCTURE_CHECK_RE.match(line)
        if m:
            last_date = m.group(1)
            last_facts = int(m.group(2))
            last_folders = int(m.group(3))
    if last_date is None:
        return 0, 0, None
    return last_facts, last_folders, last_date


def level(facts_delta: int, folders_delta: int) -> str:
    """Return green, amber, or red from the growth thresholds."""
    if facts_delta < 10 and folders_delta < 3:
        return "green"
    if facts_delta < 20 and folders_delta < 5:
        return "amber"
    return "red"


GUIDE = {
    "green": "structure ok",
    "amber": "run /check-structure soon",
    "red": "run /check-structure now",
}

CODES = {"green": "\033[32m", "amber": "\033[33m", "red": "\033[31m"}


def colorize(text: str, facts_delta: int, folders_delta: int) -> str:
    """Wrap text in an ANSI color based on growth thresholds."""
    code = CODES[level(facts_delta, folders_delta)]
    return f"{code}{text}\033[0m"


def run(root: Path, use_color: bool) -> str:
    """Build the one-line tracker output."""
    project = root / "context" / "project"
    log_path = root / "context" / "system" / "log.md"

    facts = count_facts(project)
    folders = count_folders(project)
    base_facts, base_folders, check_date = read_baseline(log_path)

    delta_facts = facts - base_facts
    delta_folders = folders - base_folders

    if check_date is not None:
        suffix = f"since the structure check ({check_date})"
    else:
        suffix = "since the start"

    guide = GUIDE[level(delta_facts, delta_folders)]
    line = (
        f"context: +{delta_facts} facts, +{delta_folders} folders "
        f"{suffix}, {guide}"
    )

    if use_color:
        line = colorize(line, delta_facts, delta_folders)
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=None,
                        help="directory that holds context/")
    parser.add_argument("--color", action="store_true",
                        help="ANSI color by growth threshold")
    args = parser.parse_args()

    try:
        if args.root is not None:
            root = Path(args.root).resolve()
        else:
            root = find_root(Path.cwd())
            if root is None:
                print("context: tracker error FileNotFoundError")
                return 0
        print(run(root, args.color))
    except Exception as exc:
        print(f"context: tracker error {type(exc).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
