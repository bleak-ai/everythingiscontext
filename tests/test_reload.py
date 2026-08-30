"""server.reload(): apply agent.md and command edits in place."""

import asyncio

import pytest
from fastmcp import Client

from gcontext import __version__, cli, commands, server

MD_COMMAND = """\
---
description: Draft a refund reply
---
Draft a refund reply and show it to the user.
"""


@pytest.fixture(autouse=True)
def _reset_commands():
    commands._STABLE_KEYS.clear()
    yield
    commands._STABLE_KEYS.clear()


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: t\n")
    (tmp_path / "agent.md").write_text("# Agent\n\noriginal instructions\n")
    cmd = tmp_path / "modules" / "support" / "commands" / "refund_reply.md"
    cmd.parent.mkdir(parents=True)
    cmd.write_text(MD_COMMAND)
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    # simulate startup
    commands.reregister_all(server.mcp, tmp_path)
    server.load_instructions()
    server.snapshot_startup_files()
    return tmp_path


def _prompt_names() -> set[str]:
    async def go():
        async with Client(server.mcp) as c:
            return {p.name for p in await c.list_prompts()}

    return asyncio.run(go())


def test_reload_picks_up_agent_md_edit(project):
    (project / "agent.md").write_text("# Agent\n\nrewritten instructions\n")
    report = server.reload()
    assert "rewritten instructions" in server.mcp.instructions
    assert report["agent_md_changed"] is True
    assert report["client_reconnect_needed"] is True
    assert report["version"] == __version__
    # staleness re-armed: nothing stale right after a reload
    stale = server.check_staleness(force=True)
    assert stale == {"agent_md": False, "commands": False}


def test_reload_no_changes_needs_no_reconnect(project):
    report = server.reload()
    assert report["removed"] == [] and report["added"] == []
    assert report["agent_md_changed"] is False
    assert report["client_reconnect_needed"] is False


def test_reload_new_command_file(project):
    (project / "modules" / "support" / "commands" / "escalate.md").write_text(
        "---\ndescription: d\n---\nbody"
    )
    report = server.reload()
    assert "escalate" in report["added"]
    assert "escalate" in _prompt_names()
    assert report["client_reconnect_needed"] is True


# -- CLI report printer --


def test_format_reload_report_live_now():
    lines = cli.format_reload_report({
        "version": __version__, "framework_prompts": 4, "project_commands": 2,
        "removed": [], "added": [], "agent_md_changed": False,
        "client_reconnect_needed": False,
    })
    text = "\n".join(lines)
    assert "Live now." in text
    assert "Reconnect" not in text


def test_format_reload_report_reconnect_and_diff():
    lines = cli.format_reload_report({
        "version": __version__, "framework_prompts": 4, "project_commands": 3,
        "removed": ["old_cmd"], "added": ["new_cmd"], "agent_md_changed": True,
        "client_reconnect_needed": True,
    })
    text = "\n".join(lines)
    assert "old_cmd" in text and "new_cmd" in text
    assert "/mcp" in text
    assert "Live now." not in text


def test_format_reload_report_version_drift():
    lines = cli.format_reload_report({
        "version": "0.0.1", "framework_prompts": 4, "project_commands": 0,
        "removed": [], "added": [], "agent_md_changed": False,
        "client_reconnect_needed": False,
    })
    text = "\n".join(lines)
    assert "0.0.1" in text and __version__ in text
    assert "full restart" in text.lower() or "gcontext up" in text


def test_format_reload_report_error():
    lines = cli.format_reload_report({"error": "reload failed",
                                      "version": __version__})
    text = "\n".join(lines)
    assert "reload failed" in text
