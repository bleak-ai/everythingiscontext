"""gcontext init: write the context standard into a project directory."""

import datetime
import importlib.resources
import json
import os
import subprocess
import sys
from pathlib import Path


CLAUDE_MD_LINES = [
    "Read context/project/index.md at the start of every session.",
    "Follow context/system/rules.md for saves and structure changes.",
]
OLD_STOP_HOOK_NAME = "save" + "-every-n-turns.py"


def _standard_root():
    """Return the Path to the bundled standard/ directory."""
    return importlib.resources.files("gcontext") / "standard"


def _collect_bundle_files(standard: Path) -> list[tuple[str, str]]:
    """Walk the standard/ tree and return (bundle_rel_path, dest_rel_path) pairs.

    Files under standard/context/ map to <dir>/context/.
    Files under standard/commands/ map to <dir>/.claude/commands/.
    """
    pairs = []
    context_root = standard / "context"
    commands_root = standard / "commands"

    for base, dest_prefix in [(context_root, "context"), (commands_root, ".claude/commands")]:
        if not base.is_dir():
            continue
        for dirpath, _, filenames in os.walk(base):
            dirpath = Path(dirpath)
            for fname in sorted(filenames):
                src = dirpath / fname
                rel = src.relative_to(base)
                dest_rel = f"{dest_prefix}/{rel}"
                pairs.append((str(src), dest_rel))
    return sorted(pairs, key=lambda p: p[1])


def _write_files(target_dir: Path, today: str, init_time: str) -> list[str]:
    """Write bundled files into target_dir. Return status lines."""
    standard = _standard_root()
    pairs = _collect_bundle_files(standard)
    lines = []

    for src_path, dest_rel in pairs:
        dest = target_dir / dest_rel
        if dest.exists():
            lines.append(f"kept {dest_rel}")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        content = Path(src_path).read_text(encoding="utf-8")

        # log.md: substitute the init date and timestamp
        if dest_rel.endswith("log.md"):
            content = content.replace("{date}", today)
            content = content.replace("{iso}", init_time)

        dest.write_text(content, encoding="utf-8")
        lines.append(f"wrote {dest_rel}")

    return lines


def _set_hook_executable(target_dir: Path) -> None:
    """Make the pre-commit hook executable."""
    hook = target_dir / "context" / "system" / "scripts" / "githooks" / "pre-commit"
    if hook.exists():
        hook.chmod(hook.stat().st_mode | 0o111)


def _configure_git_hooks(target_dir: Path) -> str:
    """Set git hooks path if target_dir is a git repo root. Return a status message."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=target_dir,
        )
        if result.returncode != 0:
            return "no git repo, hooks path not set"
        toplevel = Path(result.stdout.strip()).resolve()
        if toplevel != target_dir.resolve():
            return "no git repo, hooks path not set"
        subprocess.run(
            ["git", "config", "core.hooksPath", "context/system/scripts/githooks"],
            cwd=target_dir, check=True,
        )
        return "git hooks path set to context/system/scripts/githooks"
    except (OSError, subprocess.SubprocessError):
        return "no git repo, hooks path not set"


def _update_claude_md(target_dir: Path) -> list[str]:
    """Create or update CLAUDE.md with the two required lines. Return status lines."""
    claude_md = target_dir / "CLAUDE.md"
    lines_out = []

    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
    else:
        content = ""
        lines_out.append("wrote CLAUDE.md")

    added = []
    for line in CLAUDE_MD_LINES:
        if line not in content:
            added.append(line)

    if added:
        separator = "\n" if content and not content.endswith("\n") else ""
        if not content:
            separator = ""
        content = content + separator + "\n".join(added) + "\n"
        claude_md.write_text(content, encoding="utf-8")
        if "wrote CLAUDE.md" not in lines_out:
            lines_out.append("updated CLAUDE.md")
    elif "wrote CLAUDE.md" not in lines_out:
        lines_out.append("kept CLAUDE.md")

    return lines_out


STOP_HOOK_ENTRY = {
    "hooks": [
        {
            "type": "command",
            "command": (
                'uv run --no-project python3 '
                '"$CLAUDE_PROJECT_DIR"'
                '/context/system/scripts/journal-every-n-turns.py'
            ),
            "timeout": 10,
        }
    ]
}


def _update_settings_json(target_dir: Path) -> str:
    """Create or merge the Stop hook entry into .claude/settings.json.

    Returns a status message: wrote, updated, or kept.
    """
    settings_path = target_dir / ".claude" / "settings.json"

    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"hooks": {"Stop": [STOP_HOOK_ENTRY]}}
        settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return "wrote .claude/settings.json"

    raw = settings_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return "kept .claude/settings.json (could not parse)"

    # Keep the file when the journal hook is already registered.
    hooks = data.get("hooks", {})
    stop_list = hooks.get("Stop", [])
    for entry in stop_list:
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if "journal-every-n-turns.py" in cmd:
                return "kept .claude/settings.json"

    # Rename the old hook command in place.
    for entry in stop_list:
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if OLD_STOP_HOOK_NAME in cmd:
                hook["command"] = cmd.replace(
                    OLD_STOP_HOOK_NAME,
                    "journal-every-n-turns.py",
                )
                settings_path.write_text(
                    json.dumps(data, indent=2) + "\n",
                    encoding="utf-8",
                )
                return "updated .claude/settings.json (hook renamed)"

    # Add the entry
    if "hooks" not in data:
        data["hooks"] = {}
    if "Stop" not in data["hooks"]:
        data["hooks"]["Stop"] = []
    data["hooks"]["Stop"].append(STOP_HOOK_ENTRY)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "updated .claude/settings.json"


def run_init(target_dir: Path) -> int:
    """Run the full init sequence. Returns the exit code from check."""
    now = datetime.datetime.now().astimezone()
    today = now.date().isoformat()
    init_time = now.isoformat(timespec="seconds")

    # Write bundled files
    file_lines = _write_files(target_dir, today, init_time)
    for line in file_lines:
        print(line)

    # Set pre-commit executable
    _set_hook_executable(target_dir)

    # Git hooks
    git_msg = _configure_git_hooks(target_dir)
    print(git_msg)

    # CLAUDE.md
    claude_lines = _update_claude_md(target_dir)
    for line in claude_lines:
        print(line)

    # Stop hook in .claude/settings.json
    settings_msg = _update_settings_json(target_dir)
    print(settings_msg)

    # Statusline instruction
    print()
    print("statusline: add this command to your Claude Code statusline to see context growth after every turn:")
    print("  uv run --no-project python3 context/system/scripts/track-context-changes.py . --color")
    print()

    # Run check
    result = subprocess.run(
        ["uv", "run", "context/system/scripts/sync-index-files.py", "--check"],
        cwd=target_dir,
    )
    return result.returncode
