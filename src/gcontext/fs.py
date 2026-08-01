"""File access for the read_file, write_file, list_dir and grep tools.

Every path is resolved and confined to the project root; secrets.env is
unreadable and unwritable, connection.yaml is unwritable (the secret grant
stays human-edited). Errors come back as strings because tool results are
strings the agent reads.
"""

import fnmatch
import re
from pathlib import Path

# Machine folders: never served to the dashboard browser, skipped by
# list_dir and grep.
SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules"}
BROWSER_BLOCKED = SKIP_DIRS

GREP_MAX_MATCHES = 100
GREP_MAX_LINE = 200


def resolve_path(root: Path, path: str) -> tuple[Path | None, str | None]:
    """Resolve an agent path to (target, None) or (None, error).

    Confinement to the project root plus the secrets.env block, shared by
    every file tool.
    """
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        return None, f"path {path} is outside the project directory"
    if target.name == "secrets.env":
        return None, "secrets.env is not accessible through the agent"
    return target, None


def resolve_browser_path(root: Path, path: str) -> tuple[Path | None, str | None]:
    """Resolve a dashboard read to (target, None) or (None, error).

    Same confinement as read_file, plus the browser surface never sees
    machine folders. secrets.env stays unreadable everywhere.
    """
    target, error = resolve_path(root, path)
    if error:
        return None, error
    if SKIP_DIRS & set(target.relative_to(root.resolve()).parts):
        return None, f"path {path} is not readable"
    return target, None


def read_file(root: Path, path: str) -> str:
    target, error = resolve_path(root, path)
    if error:
        return f"Error: {error}."
    if not target.exists():
        return f"Error: {path} does not exist."
    if not target.is_file():
        return f"Error: {path} is not a file."
    return target.read_text()


def write_file(root: Path, path: str, content: str) -> str:
    target, error = resolve_path(root, path)
    if error:
        return f"Error: {error}."
    if target.name == "connection.yaml":
        return "Error: cannot write to connection.yaml through the agent."

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Written: {path} ({len(content)} bytes)"


def list_dir(root: Path, path: str = ".") -> str:
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        return f"Error: path {path} is outside the project directory."
    if not target.exists():
        return f"Error: {path} does not exist."
    if not target.is_dir():
        return f"Error: {path} is not a directory."

    dirs, files = [], []
    for entry in sorted(target.iterdir(), key=lambda e: e.name):
        if entry.name in SKIP_DIRS:
            continue
        if entry.is_dir():
            dirs.append(f"{entry.name}/")
        else:
            files.append(f"{entry.name} ({entry.stat().st_size} bytes)")
    entries = dirs + files
    if not entries:
        return f"{path}: empty directory"
    return "\n".join(entries)


def grep(root: Path, pattern: str, path: str = ".", glob: str = "") -> str:
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        return f"Error: path {path} is outside the project directory."
    if not target.exists():
        return f"Error: {path} does not exist."

    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return f"Error: invalid regex: {exc}"

    resolved_root = root.resolve()
    candidates = [target] if target.is_file() else sorted(target.rglob("*"))
    matches = []
    truncated = False
    for f in candidates:
        if not f.is_file():
            continue
        rel_parts = f.relative_to(resolved_root).parts
        if SKIP_DIRS & set(rel_parts):
            continue
        if f.name == "secrets.env":
            continue
        if glob and not fnmatch.fnmatch(f.name, glob):
            continue
        try:
            text = f.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        rel = "/".join(rel_parts)
        for lineno, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                matches.append(f"{rel}:{lineno}: {line.strip()[:GREP_MAX_LINE]}")
                if len(matches) >= GREP_MAX_MATCHES:
                    truncated = True
                    break
        if truncated:
            break

    if not matches:
        return f"No matches for {pattern!r}."
    if truncated:
        matches.append(f"... truncated at {GREP_MAX_MATCHES} matches, narrow the pattern or path.")
    return "\n".join(matches)
