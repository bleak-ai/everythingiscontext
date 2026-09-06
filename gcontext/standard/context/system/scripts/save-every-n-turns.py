#!/usr/bin/env python3
"""Force a context save every N assistant turns via a Claude Code Stop hook.

Reads the Stop hook JSON from stdin. Keeps a per-session counter in
a file under <tempdir>/gcontext-save-turns/. On every Nth turn it
returns a block decision whose reason tells the agent to run the save
procedure. When stop_hook_active is true it never blocks (prevents
re-triggering during a save turn). Failures are silent (exit 0).

Hook contract: stdin is JSON with session_id, transcript_path, cwd,
hook_event_name, stop_hook_active. To block, print a JSON object with
decision and reason to stdout and exit 0.

N defaults to 5 and is overridable by the GCONTEXT_SAVE_EVERY env var.

Usage:
    echo '{"session_id":"abc","stop_hook_active":false}' | \\
        uv run --no-project python3 save-every-n-turns.py
    save-every-n-turns.py --reset <session_id>
    save-every-n-turns.py --status <session_id>
"""

import json
import os
import sys
import tempfile
from pathlib import Path


def _counter_dir() -> Path:
    """Return the directory that holds per-session counter files."""
    return Path(tempfile.gettempdir()) / "gcontext-save-turns"


def _counter_path(session_id: str) -> Path:
    """Return the counter file for a session."""
    safe = session_id.replace("/", "_").replace("\\", "_")
    return _counter_dir() / f"{safe}.txt"


def _read_counter(path: Path) -> int:
    """Read the integer counter from a file. Returns 0 when missing."""
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_counter(path: Path, value: int) -> None:
    """Write the integer counter to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value) + "\n")


def _get_n() -> int:
    """Return the save interval from the env or the default (5)."""
    raw = os.environ.get("GCONTEXT_SAVE_EVERY", "5")
    try:
        n = int(raw)
        return n if n > 0 else 5
    except ValueError:
        return 5


BLOCK_REASON = (
    "gcontext: turn {n}. Save now, without asking. "
    "Read context/system/rules.md, section Save. "
    "Save every durable fact learned since the last save into context/project, "
    "in the file of its subject: decisions, facts about the code, results, corrections. "
    "Skip chatter. "
    "Then run `uv run context/system/scripts/sync-index-files.py --write`, then `--check`, "
    "and report the paths written in one line. "
    "Then continue with what you were doing, or stop if the task is done."
)


def main() -> int:
    try:
        # Handle --reset and --status flags
        if "--reset" in sys.argv:
            idx = sys.argv.index("--reset")
            if idx + 1 < len(sys.argv):
                sid = sys.argv[idx + 1]
                p = _counter_path(sid)
                if p.exists():
                    p.unlink()
            return 0

        if "--status" in sys.argv:
            idx = sys.argv.index("--status")
            if idx + 1 < len(sys.argv):
                sid = sys.argv[idx + 1]
                p = _counter_path(sid)
                print(_read_counter(p))
            return 0

        # Read stdin JSON (tolerate empty or invalid)
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return 0

        # When stop_hook_active is true, do not increment, exit 0
        if data.get("stop_hook_active", False):
            return 0

        session_id = data.get("session_id")
        if not session_id:
            return 0

        # Increment counter
        path = _counter_path(session_id)
        count = _read_counter(path) + 1
        _write_counter(path, count)

        # Check if this is an Nth turn
        n = _get_n()
        if count % n == 0:
            reason = BLOCK_REASON.format(n=count)
            print(json.dumps({"decision": "block", "reason": reason}))

    except Exception:
        pass  # All exceptions swallowed, exit 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
