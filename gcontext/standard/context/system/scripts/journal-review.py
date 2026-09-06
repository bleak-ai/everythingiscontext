#!/usr/bin/env python3
"""List journal review inputs and condense Claude session transcripts.

The command reads the last review marker from context/system/log.md.
It can list changed journal and transcript files, or reduce one JSONL
transcript to useful user text, assistant text, and short tool lines.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path


JOURNAL_REVIEW_RE = re.compile(
    r"^- \d{4}-\d{2}-\d{2}: journal review, \d+ sessions, up to (\S+)$"
)
NOISE_PREFIXES = ("<local-command", "<command-name>", "Stop hook feedback")


def repository_root(script_path: Path) -> Path:
    """Return the repo root for a script in context/system/scripts/."""
    return script_path.resolve().parents[3]


def find_root(start: Path) -> Path | None:
    """Walk up until a folder holds the journal review script."""
    marker = Path("context/system/scripts/journal-review.py")
    current = start.resolve()
    for directory in [current, *current.parents]:
        if (directory / marker).is_file():
            return directory
    return None


def read_marker(log_path: Path) -> str | None:
    """Return the timestamp from the last journal review log line."""
    if not log_path.is_file():
        return None
    marker = None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = JOURNAL_REVIEW_RE.match(line)
        if match:
            marker = match.group(1)
    return marker


def project_key(root: Path) -> str:
    """Return the Claude project folder key for an absolute repo root."""
    return str(root.resolve()).replace("/", "-")


def parse_iso(value: str) -> datetime.datetime:
    """Parse an ISO timestamp, including a trailing Z."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(value)


def modified_after(path: Path, marker: str | None) -> bool:
    """Return whether a file changed after the marker."""
    if marker is None:
        return True
    threshold = parse_iso(marker).timestamp()
    return path.stat().st_mtime > threshold


def list_changed(root: Path, since: str | None = None) -> dict:
    """Return changed journal and transcript paths for one repo."""
    root = root.resolve()
    log_path = root / "context/system/log.md"
    selected_marker = since if since is not None else read_marker(log_path)

    journal_root = root / "context/journal"
    journal = []
    if journal_root.is_dir():
        journal = [
            str(path.resolve())
            for path in sorted(journal_root.rglob("*.md"))
            if path.is_file()
            and path.name != "index.md"
            and modified_after(path, selected_marker)
        ]

    transcript_root = (
        Path.home() / ".claude/projects" / project_key(root)
    )
    transcripts = []
    if transcript_root.is_dir():
        transcripts = [
            str(path.resolve())
            for path in sorted(transcript_root.glob("*.jsonl"))
            if path.is_file() and modified_after(path, selected_marker)
        ]

    return {
        "marker": selected_marker if selected_marker is not None else "none",
        "journal": journal,
        "transcripts": transcripts,
    }


def record_is_before(record: dict, after: str | None) -> bool:
    """Return whether a transcript record is older than the filter."""
    if after is None:
        return False
    timestamp = record.get("timestamp")
    if not isinstance(timestamp, str):
        return False
    try:
        return parse_iso(timestamp).timestamp() < parse_iso(after).timestamp()
    except ValueError:
        return False


def useful_user_text(content) -> list[str]:
    """Return useful text fragments from one user message."""
    if isinstance(content, str):
        candidates = [content]
    elif isinstance(content, list):
        candidates = [
            block.get("text")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
    else:
        candidates = []
    return [
        text
        for text in candidates
        if isinstance(text, str)
        and text
        and not text.startswith(NOISE_PREFIXES)
    ]


def first_argument_value(tool_input) -> str:
    """Return the first tool argument value, cut at 120 characters."""
    if not isinstance(tool_input, dict) or not tool_input:
        return ""
    value = next(iter(tool_input.values()))
    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return rendered[:120]


def useful_assistant_text(content) -> list[str]:
    """Return text and short tool lines from one assistant message."""
    if isinstance(content, str):
        return [content] if content else []
    if not isinstance(content, list):
        return []
    output = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                output.append(text)
        elif block_type == "tool_use":
            name = block.get("name", "unknown")
            argument = first_argument_value(block.get("input"))
            output.append(f"[tool {name}: {argument}]")
    return output


def condense(transcript: Path, after: str | None = None) -> str:
    """Return a compact text view of one Claude JSONL transcript."""
    blocks = []
    for raw_line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(raw_line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        role = record.get("type")
        if role not in ("user", "assistant"):
            continue
        if record.get("isSidechain") is True or record_is_before(record, after):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if role == "user":
            text_parts = useful_user_text(content)
        else:
            text_parts = useful_assistant_text(content)
        if text_parts:
            blocks.append(f"{role}:\n" + "\n".join(text_parts))
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n\n"


def parse_arguments() -> argparse.Namespace:
    """Parse the review action and its filters."""
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--marker", action="store_true")
    actions.add_argument("--list", action="store_true", dest="list_files")
    actions.add_argument("--condense", type=Path, metavar="TRANSCRIPT")
    parser.add_argument("--since", metavar="ISO")
    parser.add_argument("--after", metavar="ISO")
    parser.add_argument("root", nargs="?", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run one journal review helper action."""
    arguments = parse_arguments()
    root = arguments.root
    if root is None:
        root = find_root(Path.cwd()) or repository_root(Path(__file__))

    if arguments.marker:
        marker = read_marker(root / "context/system/log.md")
        print(marker if marker is not None else "none")
    elif arguments.list_files:
        print(json.dumps(list_changed(root, arguments.since)))
    else:
        try:
            print(condense(arguments.condense, arguments.after), end="")
        except BrokenPipeError:
            sys.stdout = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
