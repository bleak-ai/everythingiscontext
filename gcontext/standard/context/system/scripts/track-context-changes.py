#!/usr/bin/env python3
"""Count context growth and journal sessions that need review.

Run after every assistant turn, or from the statusline wrapper.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

STRUCTURE_CHECK_RE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}):\s*structure check,\s*(\d+)\s+facts?,\s*(\d+)\s+folders?"
)
JOURNAL_REVIEW_RE = re.compile(
    r"^- \d{4}-\d{2}-\d{2}: journal review, \d+ sessions, up to (\S+)$"
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


def read_journal_marker(log_path: Path) -> str | None:
    """Return the timestamp from the newest journal review line."""
    if not log_path.is_file():
        return None
    marker = None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = JOURNAL_REVIEW_RE.match(line)
        if match:
            marker = match.group(1)
    return marker


def iso_timestamp(value: str) -> float:
    """Return epoch seconds for an ISO timestamp."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(value).timestamp()


def count_journal_sessions(journal: Path, log_path: Path) -> int:
    """Count journal Markdown files modified after the review marker."""
    if not journal.is_dir():
        return 0
    marker = read_journal_marker(log_path)
    threshold = iso_timestamp(marker) if marker is not None else None
    total = 0
    for path in sorted(journal.rglob("*.md")):
        if not path.is_file() or path.name == "index.md":
            continue
        if threshold is None or path.stat().st_mtime > threshold:
            total += 1
    return total


def level(facts_delta: int, folders_delta: int) -> str:
    """Return green, amber, or red from the growth thresholds."""
    if facts_delta < 10 and folders_delta < 3:
        return "green"
    if facts_delta < 20 and folders_delta < 5:
        return "amber"
    return "red"


def journal_level(sessions: int) -> str:
    """Return the journal level from its review thresholds."""
    if sessions < 3:
        return "green"
    if sessions < 6:
        return "amber"
    return "red"


GUIDE = {
    "green": "structure ok",
    "amber": "run /check-structure soon",
    "red": "run /check-structure now",
}

CODES = {"green": "\033[32m", "amber": "\033[33m", "red": "\033[31m"}
LEVEL_ORDER = {"green": 0, "amber": 1, "red": 2}


def guide_for(structure: str, journal: str) -> str:
    """Return guidance for the worse context level."""
    if structure == "red" and journal == "red":
        return "run /check-structure now, then /add-to-context"
    if LEVEL_ORDER[journal] > LEVEL_ORDER[structure]:
        return "run /add-to-context"
    return GUIDE[structure]


def overall_level(structure: str, journal: str) -> str:
    """Return the worse of the structure and journal levels."""
    if LEVEL_ORDER[journal] > LEVEL_ORDER[structure]:
        return journal
    return structure


def colorize(
    text: str,
    facts_delta: int,
    folders_delta: int,
    journal_sessions: int = 0,
) -> str:
    """Wrap text in an ANSI color based on the worse context level."""
    structure = level(facts_delta, folders_delta)
    journal = journal_level(journal_sessions)
    code = CODES[overall_level(structure, journal)]
    return f"{code}{text}\033[0m"


def run(root: Path, use_color: bool) -> str:
    """Build the one-line tracker output."""
    project = root / "context" / "project"
    journal_path = root / "context" / "journal"
    log_path = root / "context" / "system" / "log.md"

    facts = count_facts(project)
    folders = count_folders(project)
    base_facts, base_folders, check_date = read_baseline(log_path)
    sessions = count_journal_sessions(journal_path, log_path)

    delta_facts = facts - base_facts
    delta_folders = folders - base_folders

    if check_date is not None:
        suffix = f"since the structure check ({check_date})"
    else:
        suffix = "since the start"

    structure = level(delta_facts, delta_folders)
    journal = journal_level(sessions)
    guide = guide_for(structure, journal)
    parts = [
        f"context: +{delta_facts} facts, +{delta_folders} folders {suffix}"
    ]
    if sessions:
        parts.append(f"{sessions} sessions to review")
    parts.append(guide)
    line = ", ".join(parts)

    if use_color:
        line = colorize(line, delta_facts, delta_folders, sessions)
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
