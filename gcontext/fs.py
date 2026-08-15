"""File access for the read_file, write_file, list_dir and grep tools.

Every path is resolved and confined to the project root; secrets.env is
unreadable and unwritable (secret values never enter the context window).
Errors come back as strings because tool results are strings the agent
reads.
"""

import difflib
import fnmatch
import re
from pathlib import Path

# Machine folders: never served to the dashboard browser, skipped by
# list_dir and grep.
SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules"}
SKIP_FILES = {".template.yaml", ".venv-sync.lock"}
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


def walk_files(root: Path) -> list[str]:
    """Relative paths of every listable state file, sorted.

    Same visibility as the scanning surface: machine folders and secrets.env
    never appear, archive/ is not scanned (still readable by path).
    """
    resolved = root.resolve()
    out = []
    for f in sorted(resolved.rglob("*")):
        if not f.is_file():
            continue
        parts = f.relative_to(resolved).parts
        if (SKIP_DIRS | {"archive"}) & set(parts):
            continue
        if f.name == "secrets.env" or f.name in SKIP_FILES:
            continue
        out.append("/".join(parts))
    return out


def read_file(root: Path, path: str) -> str:
    target, error = resolve_path(root, path)
    if error:
        return f"Error: {error}."
    if not target.exists():
        return f"Error: {path} does not exist."
    if not target.is_file():
        return f"Error: {path} is not a file."
    return target.read_text()


def _index_siblings(folder: Path) -> list[str]:
    """Names an index.md in this folder must reference: every visible sibling.

    Machine folders, secrets.env and archive/ (retired state, not part of the
    map) are exempt. Directory names come without the trailing slash so a
    plain-name mention in the index counts.
    """
    names = []
    for entry in sorted(folder.iterdir(), key=lambda e: e.name):
        if entry.name.startswith(".") or entry.name in SKIP_DIRS | SKIP_FILES | {"index.md", "secrets.env", "archive"}:
            continue
        names.append(entry.name)
    return names


INDEX_SHAPE = (
    "An index.md is a '# ' title, a 2-3 sentence summary paragraph, then one "
    "'- `file`: description' bullet per sibling, nothing else."
)

_HEADING_RE = re.compile(r"^#{1,6}(\s|$)")
_MAX_SUMMARY_LINES = 5


def _strip_frontmatter(lines: list[str]) -> list[str]:
    """Drop a leading `---` YAML block (agent root manifests carry one)."""
    if lines and lines[0].strip() == "---":
        for i, ln in enumerate(lines[1:], 1):
            if ln.strip() == "---":
                return lines[i + 1 :]
    return lines


def _mentions(text: str, name: str) -> bool:
    """True when text references name as a whole token.

    Accepts backticks, markdown links, plain mentions, a trailing slash, and
    paths under a directory (`steps/1-do.md` mentions `steps`). Rejects
    substrings of longer names (`changelog.md` does not mention `log.md`).
    """
    return re.search(r"(?<![\w.-])" + re.escape(name) + r"(/|(?![\w-]))", text) is not None


def index_format_issues(content: str, siblings: list[str]) -> list[str]:
    """Ways this index.md content breaks the map convention; empty list = valid.

    Shape: a `# ` title, one plain-text summary paragraph (max
    _MAX_SUMMARY_LINES lines), then one bullet per sibling, nothing else.
    Frontmatter is stripped first; indented lines after a bullet count as
    that bullet's continuation.
    """
    issues: list[str] = []
    lines = _strip_frontmatter(content.splitlines())
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ["the file is empty"]

    if lines[0].startswith("# "):
        body = lines[1:]
    else:
        issues.append("the first line must be a '# ' title")
        body = lines

    summary_lines: list[str] = []
    in_summary_gap = False
    bullets: list[str] = []
    seen_bullet = False
    for ln in body:
        stripped = ln.strip()
        if not stripped:
            if summary_lines and not seen_bullet:
                in_summary_gap = True
            continue
        if _HEADING_RE.match(ln):
            issues.append(f"extra heading is not allowed: {stripped[:60]!r}")
            continue
        if ln.startswith("- "):
            seen_bullet = True
            bullets.append(stripped)
            continue
        if seen_bullet:
            if ln[:1] in (" ", "\t") and bullets:
                bullets[-1] += " " + stripped
            else:
                issues.append(f"content after the bullet list is not allowed: {stripped[:60]!r}")
            continue
        if in_summary_gap:
            issues.append("the summary must be a single paragraph")
            in_summary_gap = False
        summary_lines.append(stripped)

    if not summary_lines:
        issues.append("a summary paragraph after the title is missing")
    elif len(summary_lines) > _MAX_SUMMARY_LINES:
        issues.append(f"the summary paragraph is longer than {_MAX_SUMMARY_LINES} lines")

    joined = "\n".join(bullets)
    if siblings:
        for b in bullets:
            if not any(_mentions(b, n) for n in siblings):
                issues.append(f"bullet references no file in this folder: {b[:60]!r}")
    for n in siblings:
        if not _mentions(joined, n):
            issues.append(f"no bullet references {n}")
    return issues


def _index_warning(root: Path, target: Path, content: str, existed: bool) -> str:
    """Warning text for the index.md map convention, or '' when the write is fine.

    Writing an index.md: warn about siblings the content never mentions.
    Creating any other file: warn when the parent's index.md does not mention it.
    Advisory only, the write itself always goes through.
    """
    if target.name == "index.md":
        issues = index_format_issues(content, _index_siblings(target.parent))
        if issues:
            return (
                " Warning: this index.md breaks the index format: "
                + "; ".join(issues)
                + ". "
                + INDEX_SHAPE
            )
        return ""
    if existed or target.name == "agent.md":
        return ""
    index = target.parent / "index.md"
    if index.is_file() and not _mentions(index.read_text(), target.name):
        rel = "/".join(index.relative_to(root.resolve()).parts)
        return (
            f" Warning: {rel} does not mention {target.name}. "
            "Add a one-line link for it there."
        )
    return ""


def _restart_note(root: Path, target: Path) -> str:
    """Note text for files that only load at server start, or '' otherwise.

    agent.md is pushed in the MCP handshake and command files register as
    prompts at startup; a write through this tool takes effect only after a
    restart. Advisory only, same contract as _index_warning.
    """
    parts = target.relative_to(root.resolve()).parts
    if parts == ("agent.md",):
        return (
            " Note: agent.md is pushed at connect; this change reaches clients "
            "only after a restart (stop the server, gcontext up, reconnect the client)."
        )
    if (
        len(parts) == 4
        and parts[0] in ("connections", "modules")
        and parts[2] == "commands"
        and target.suffix in (".md", ".py")
    ):
        return (
            " Note: commands are registered at server start; this command appears "
            "(or updates) only after a restart (stop the server, gcontext up, "
            "reconnect the client)."
        )
    return ""


DIFF_MAX_LINES = 200


def _write_diff(path: str, before: str, after: str) -> str:
    """Unified diff of a write, capped at DIFF_MAX_LINES, '' when identical."""
    lines = list(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    if not lines:
        return ""
    if len(lines) > DIFF_MAX_LINES:
        lines = lines[:DIFF_MAX_LINES] + [f"... diff truncated at {DIFF_MAX_LINES} lines\n"]
    diff = "".join(lines)
    if not diff.endswith("\n"):
        diff += "\n"
    return "\n" + diff


def write_file(root: Path, path: str, content: str) -> str:
    target, error = resolve_path(root, path)
    if error:
        return f"Error: {error}."
    existed = target.exists()
    before = ""
    if existed and target.is_file():
        before = target.read_text(errors="replace")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    if existed:
        line = f"Updated: {path} ({len(content)} bytes)."
        if before == content:
            line = f"Unchanged: {path} (content identical)."
    else:
        line = f"Created: {path} ({len(content)} bytes, {len(content.splitlines())} lines)."
    return (
        line
        + _index_warning(root, target, content, existed)
        + _restart_note(root, target)
        + (_write_diff(path, before, content) if existed else "")
    )


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
        if entry.is_file() and entry.name in SKIP_FILES:
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
        if f.name == "secrets.env" or f.name in SKIP_FILES:
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
