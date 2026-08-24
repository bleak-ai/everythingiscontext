"""Tests for the reload-visibility feature: BOOT_PROMPTS, LAST_SERVED,
client_behind(), and the statusline formatter."""

import pytest

from gcontext import commands as commands_mod
from gcontext import server


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: test-agent\n")
    (tmp_path / "agent.md").write_text("# Test agent\n")
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(server, "BOOT_PROMPTS", set())
    monkeypatch.setattr(server, "LAST_SERVED", {})
    return tmp_path


# --- Task 2: BOOT_PROMPTS and LAST_SERVED ---

def test_freeze_boot_prompts_captures_current_set(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw", "explain": "fw"})
    server.freeze_boot_prompts()
    assert server.BOOT_PROMPTS == {"ask", "explain"}


def test_freeze_boot_prompts_is_a_copy(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    commands_mod._REGISTERED["new_cmd"] = "path"
    assert "new_cmd" not in server.BOOT_PROMPTS


def test_snapshot_last_served_records_prompts_and_hash(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw", "explain": "fw"})
    server.snapshot_last_served()
    assert server.LAST_SERVED["prompts"] == {"ask", "explain"}
    assert server.LAST_SERVED["agent_md_hash"] != ""
    assert "at" in server.LAST_SERVED


def test_snapshot_last_served_empty_agent_md(project, monkeypatch):
    (project / "agent.md").unlink()
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.snapshot_last_served()
    assert server.LAST_SERVED["agent_md_hash"] == ""


def test_agent_md_hash_changes_with_content(project):
    h1 = server._agent_md_hash()
    (project / "agent.md").write_text("# Updated agent\n")
    h2 = server._agent_md_hash()
    assert h1 != h2


# --- Task 3: client_behind() ---

def test_client_behind_no_handshake_yet(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    result = server.client_behind()
    assert result["behind"] is True
    assert result["reason"] == "server_restarted"


def test_client_behind_current(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    server.snapshot_last_served()
    result = server.client_behind()
    assert result["behind"] is False


def test_client_behind_new_command(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    server.snapshot_last_served()
    commands_mod._REGISTERED["new_cmd"] = "path"
    result = server.client_behind()
    assert result["behind"] is True
    assert result["reason"] == "commands_changed"
    assert "new_cmd" in result["new_commands"]


def test_client_behind_removed_command(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw", "old": "path"})
    server.freeze_boot_prompts()
    server.snapshot_last_served()
    del commands_mod._REGISTERED["old"]
    result = server.client_behind()
    assert result["behind"] is True
    assert "old" in result["removed_commands"]


def test_client_behind_agent_md_changed(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    server.snapshot_last_served()
    (project / "agent.md").write_text("# Changed\n")
    result = server.client_behind()
    assert result["behind"] is True
    assert result["reason"] == "agent_md_changed"
    assert result["agent_md_changed"] is True


def test_client_behind_mixed_changes(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    server.snapshot_last_served()
    commands_mod._REGISTERED["new_cmd"] = "path"
    (project / "agent.md").write_text("# Changed\n")
    result = server.client_behind()
    assert result["behind"] is True
    assert result["agent_md_changed"] is True
    assert "new_cmd" in result["new_commands"]


def test_client_behind_server_stale(project, monkeypatch):
    monkeypatch.setattr(commands_mod, "_REGISTERED", {"ask": "fw"})
    server.freeze_boot_prompts()
    server.snapshot_last_served()
    monkeypatch.setattr(server, "_STALE", {"agent_md": False, "commands": True})
    result = server.client_behind()
    assert result["behind"] is True
    assert result["reason"] == "server_stale"


# --- Task 6: statusline formatter ---

def test_format_statusline_ok():
    status = {"name": "my-agent", "client_behind": {"behind": False}}
    assert server.format_statusline(status) == "gcontext ok"


def test_format_statusline_new_commands():
    status = {
        "name": "my-agent",
        "client_behind": {
            "behind": True,
            "reason": "commands_changed",
            "new_commands": ["publish", "scan"],
            "removed_commands": [],
            "agent_md_changed": False,
        },
    }
    line = server.format_statusline(status)
    assert "RECONNECT NEEDED FOR my-agent" in line
    assert "/publish" in line
    assert "/scan" in line


def test_format_statusline_removed_commands():
    status = {
        "name": "my-agent",
        "client_behind": {
            "behind": True,
            "reason": "commands_changed",
            "new_commands": [],
            "removed_commands": ["old_cmd"],
            "agent_md_changed": False,
        },
    }
    line = server.format_statusline(status)
    assert "-old_cmd" in line


def test_format_statusline_server_restarted():
    status = {
        "name": "my-agent",
        "client_behind": {
            "behind": True,
            "reason": "server_restarted",
            "new_commands": [],
            "removed_commands": [],
            "agent_md_changed": False,
        },
    }
    line = server.format_statusline(status)
    assert "RECONNECT NEEDED FOR my-agent" in line
    assert "server restarted" in line


def test_format_statusline_stale():
    status = {
        "name": "my-agent",
        "client_behind": {
            "behind": True,
            "reason": "server_stale",
            "new_commands": [],
            "removed_commands": [],
            "agent_md_changed": False,
        },
    }
    line = server.format_statusline(status)
    assert "STALE" in line
    assert "gcontext reload" in line


def test_format_statusline_down():
    assert server.format_statusline(None) == "gcontext down"


def test_format_statusline_color():
    status = {
        "name": "my-agent",
        "client_behind": {
            "behind": True,
            "reason": "commands_changed",
            "new_commands": ["cmd"],
            "removed_commands": [],
            "agent_md_changed": False,
        },
    }
    line = server.format_statusline(status, color=True)
    assert "\033[33m" in line
    assert "\033[0m" in line
