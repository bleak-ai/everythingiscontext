"""Tests for gcontext init."""

import datetime
import json
import subprocess
from pathlib import Path

import pytest

from gcontext import init as init_mod


@pytest.fixture
def fresh_dir(tmp_path):
    """A clean directory with no context/ yet."""
    return tmp_path


@pytest.fixture
def git_dir(tmp_path):
    """A directory initialized as a git repo."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


def test_fresh_dir_writes_all_files(fresh_dir, monkeypatch):
    """First init writes every bundled file and creates CLAUDE.md."""
    monkeypatch.setattr(
        init_mod.subprocess, "run",
        lambda *a, **kw: type("R", (), {"returncode": 0})(),
    )

    lines = init_mod._write_files(fresh_dir, "2026-09-07")

    wrote = [l for l in lines if l.startswith("wrote ")]
    assert len(wrote) > 0, "Should write at least one file"

    # Check key files exist
    assert (fresh_dir / "context" / "system" / "rules.md").is_file()
    assert (fresh_dir / "context" / "system" / "log.md").is_file()
    assert (fresh_dir / "context" / "system" / "scripts" / "sync-index-files.py").is_file()
    assert (fresh_dir / "context" / "system" / "scripts" / "githooks" / "pre-commit").is_file()
    assert (fresh_dir / "context" / "project" / "index.md").is_file()
    assert (fresh_dir / "context" / "index.md").is_file()
    assert (fresh_dir / ".claude" / "commands" / "save.md").is_file()
    assert (fresh_dir / ".claude" / "commands" / "check-structure.md").is_file()


def test_second_run_keeps_everything(fresh_dir, monkeypatch):
    """Second init keeps all existing files."""
    monkeypatch.setattr(
        init_mod.subprocess, "run",
        lambda *a, **kw: type("R", (), {"returncode": 0})(),
    )

    init_mod._write_files(fresh_dir, "2026-09-07")
    lines2 = init_mod._write_files(fresh_dir, "2026-09-07")

    kept = [l for l in lines2 if l.startswith("kept ")]
    wrote = [l for l in lines2 if l.startswith("wrote ")]
    assert len(wrote) == 0, "Second run should write nothing"
    assert len(kept) > 0, "Second run should keep existing files"


def test_claude_md_created_and_appended(fresh_dir):
    """CLAUDE.md is created with both lines on fresh dir."""
    claude_lines = init_mod._update_claude_md(fresh_dir)
    assert "wrote CLAUDE.md" in claude_lines

    content = (fresh_dir / "CLAUDE.md").read_text()
    assert "Read context/project/index.md" in content
    assert "Follow context/system/rules.md" in content


def test_claude_md_appended_once(fresh_dir):
    """Existing CLAUDE.md gets the lines appended only once."""
    (fresh_dir / "CLAUDE.md").write_text("# My project\n\nSome notes.\n")

    init_mod._update_claude_md(fresh_dir)
    content1 = (fresh_dir / "CLAUDE.md").read_text()
    assert "Read context/project/index.md" in content1

    # Second run should not duplicate
    init_mod._update_claude_md(fresh_dir)
    content2 = (fresh_dir / "CLAUDE.md").read_text()
    assert content2.count("Read context/project/index.md") == 1
    assert content2.count("Follow context/system/rules.md") == 1


def test_claude_md_existing_with_lines_already(fresh_dir):
    """CLAUDE.md that already has both lines is kept unchanged."""
    (fresh_dir / "CLAUDE.md").write_text(
        "Read context/project/index.md at the start of every session.\n"
        "Follow context/system/rules.md for saves and structure changes.\n"
    )
    claude_lines = init_mod._update_claude_md(fresh_dir)
    assert "kept CLAUDE.md" in claude_lines


def test_hook_path_set_in_git_repo(git_dir, monkeypatch):
    """Git hooks path is configured when init runs in a git repo."""
    result = init_mod._configure_git_hooks(git_dir)
    assert "hooks path set" in result

    out = subprocess.run(
        ["git", "config", "core.hooksPath"],
        capture_output=True, text=True, cwd=git_dir,
    )
    assert "context/system/scripts/githooks" in out.stdout


def test_hook_path_not_set_outside_git(fresh_dir):
    """No git repo means hooks path is not set."""
    result = init_mod._configure_git_hooks(fresh_dir)
    assert "no git repo" in result


def test_log_date_substituted(fresh_dir):
    """log.md has {date} replaced with today's date."""
    today = "2026-09-07"
    init_mod._write_files(fresh_dir, today)

    log = (fresh_dir / "context" / "system" / "log.md").read_text()
    assert "{date}" not in log
    assert f"- {today}:" in log


def test_pre_commit_is_executable(fresh_dir):
    """pre-commit hook is made executable."""
    init_mod._write_files(fresh_dir, "2026-09-07")
    init_mod._set_hook_executable(fresh_dir)

    hook = fresh_dir / "context" / "system" / "scripts" / "githooks" / "pre-commit"
    assert hook.stat().st_mode & 0o111


def test_settings_json_created_when_missing(fresh_dir):
    """settings.json is created with the Stop hook when it does not exist."""
    msg = init_mod._update_settings_json(fresh_dir)
    assert msg == "wrote .claude/settings.json"

    data = json.loads((fresh_dir / ".claude" / "settings.json").read_text())
    assert "Stop" in data["hooks"]
    commands = [
        h["command"]
        for entry in data["hooks"]["Stop"]
        for h in entry.get("hooks", [])
    ]
    assert any("save-every-n-turns.py" in c for c in commands)


def test_settings_json_updated_when_existing(fresh_dir):
    """settings.json with other hooks gets the Stop hook appended."""
    (fresh_dir / ".claude").mkdir(parents=True, exist_ok=True)
    existing = {"hooks": {"PreToolUse": [{"matcher": "Bash"}]}}
    (fresh_dir / ".claude" / "settings.json").write_text(json.dumps(existing))

    msg = init_mod._update_settings_json(fresh_dir)
    assert msg == "updated .claude/settings.json"

    data = json.loads((fresh_dir / ".claude" / "settings.json").read_text())
    assert "PreToolUse" in data["hooks"]
    assert "Stop" in data["hooks"]


def test_settings_json_kept_when_already_present(fresh_dir):
    """settings.json with the hook already registered is left unchanged."""
    (fresh_dir / ".claude").mkdir(parents=True, exist_ok=True)
    existing = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'uv run --no-project python3 "$CLAUDE_PROJECT_DIR"/context/system/scripts/save-every-n-turns.py',
                            "timeout": 10,
                        }
                    ]
                }
            ]
        }
    }
    (fresh_dir / ".claude" / "settings.json").write_text(json.dumps(existing))

    msg = init_mod._update_settings_json(fresh_dir)
    assert msg == "kept .claude/settings.json"


def test_settings_json_invalid_json(fresh_dir):
    """Invalid JSON in settings.json is reported but does not crash."""
    (fresh_dir / ".claude").mkdir(parents=True, exist_ok=True)
    (fresh_dir / ".claude" / "settings.json").write_text("not valid {json")

    msg = init_mod._update_settings_json(fresh_dir)
    assert msg == "kept .claude/settings.json (could not parse)"


def test_save_every_n_turns_script_in_bundle(fresh_dir, monkeypatch):
    """The save-every-n-turns.py script is written by init."""
    monkeypatch.setattr(
        init_mod.subprocess, "run",
        lambda *a, **kw: type("R", (), {"returncode": 0})(),
    )
    init_mod._write_files(fresh_dir, "2026-09-07")
    assert (fresh_dir / "context" / "system" / "scripts" / "save-every-n-turns.py").is_file()


def test_sync_standard_check(tmp_path):
    """sync-standard.py --check passes when bundle matches canonical source."""
    import importlib.util

    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / "context" / "system" / "rules.md").is_file():
        pytest.skip("parent repo not available")

    spec = importlib.util.spec_from_file_location(
        "sync_standard",
        repo_root / "gcontext" / "scripts" / "sync-standard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    diffs = mod.sync(repo_root, check_only=True)
    assert diffs == [], f"bundled files differ from canonical: {diffs}"
