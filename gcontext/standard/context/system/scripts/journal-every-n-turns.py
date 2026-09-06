#!/usr/bin/env python3
"""Request a journal entry every N assistant turns through a Stop hook.

The script keeps one counter per session in the OS temp directory. It
prints a block decision on each Nth turn. All failures are silent, and
the process always exits with status 0.
"""

import argparse
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path


DEFAULT_INTERVAL = 10
BLOCK_REASON = (
    "gcontext: turn {n}. Append the facts learned since the last entry "
    "to context/journal/{date}/{session}.md with one Write or Edit call: "
    "heading `## Entry {k} ({time})`, then one fact line per durable fact "
    "(decisions, paths, names, numbers, results, traps). Create the file "
    "with the title `# Session {session}` when it does not exist. Write "
    "nothing else. No report. No index sync. Then continue with what you "
    "were doing, or stop if the task is done."
)


def counter_dir() -> Path:
    """Return the folder that holds per-session counters."""
    return Path(tempfile.gettempdir()) / "gcontext-save-turns"


def safe_session_id(session_id: str) -> str:
    """Return a session identifier that is safe as one file name."""
    return session_id.replace("/", "_").replace("\\", "_")


def counter_path(session_id: str) -> Path:
    """Return the counter path for one session."""
    return counter_dir() / f"{safe_session_id(session_id)}.txt"


def read_counter(path: Path) -> int:
    """Read a counter, or return zero when it is absent or invalid."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, OSError, ValueError):
        return 0


def write_counter(path: Path, value: int) -> None:
    """Write one counter value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n", encoding="utf-8")


def interval() -> int:
    """Return the configured positive interval or the default."""
    raw = os.environ.get("GCONTEXT_SAVE_EVERY", str(DEFAULT_INTERVAL))
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_INTERVAL
    return value if value > 0 else DEFAULT_INTERVAL


def local_now() -> datetime.datetime:
    """Return the current local date and time."""
    return datetime.datetime.now()


def root_from_script() -> Path:
    """Walk up from this script to the repository root."""
    script_dir = Path(__file__).resolve().parent
    for candidate in [script_dir, *script_dir.parents]:
        if (candidate / "context/system/scripts").is_dir():
            return candidate
    return script_dir


def repository_root(data: dict) -> Path:
    """Return the repo root from hook data, the env, or the script path."""
    cwd = data.get("cwd")
    if isinstance(cwd, str) and cwd:
        return Path(cwd).resolve()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        return Path(project_dir).resolve()
    return root_from_script()


def existing_session_file(root: Path, session_id: str) -> Path | None:
    """Return an existing journal file for the session on any day."""
    journal = root / "context/journal"
    if not journal.is_dir():
        return None
    filename = f"{safe_session_id(session_id)}.md"
    for day in sorted(journal.iterdir()):
        candidate = day / filename
        if day.is_dir() and candidate.is_file():
            return candidate
    return None


def journal_target(root: Path, session_id: str) -> tuple[str, Path]:
    """Return the journal date and target path for one session."""
    existing = existing_session_file(root, session_id)
    if existing is not None:
        return existing.parent.name, existing
    date = local_now().date().isoformat()
    target = root / "context/journal" / date / f"{safe_session_id(session_id)}.md"
    return date, target


def next_entry_number(path: Path) -> int:
    """Return one plus the number of existing journal entry headings."""
    if not path.is_file():
        return 1
    try:
        count = sum(
            line.startswith("## Entry")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    except OSError:
        return 1
    return count + 1


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse reset and status flags without rejecting extra hook args."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--reset", nargs="?")
    parser.add_argument("--status", nargs="?")
    arguments, _ = parser.parse_known_args(argv)
    return arguments


def main(argv: list[str] | None = None) -> int:
    """Run the Stop hook or one counter command. Always return zero."""
    try:
        arguments = parse_arguments(argv)
        if arguments.reset:
            path = counter_path(arguments.reset)
            if path.exists():
                path.unlink()
            return 0
        if arguments.status:
            print(read_counter(counter_path(arguments.status)))
            return 0

        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        if not isinstance(data, dict):
            return 0
        if data.get("stop_hook_active", False):
            return 0

        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return 0

        path = counter_path(session_id)
        count = read_counter(path) + 1
        write_counter(path, count)
        if count % interval() != 0:
            return 0

        root = repository_root(data)
        date, target = journal_target(root, session_id)
        now = local_now()
        reason = BLOCK_REASON.format(
            n=count,
            date=date,
            session=safe_session_id(session_id),
            k=next_entry_number(target),
            time=now.strftime("%H:%M"),
        )
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
