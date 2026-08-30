"""Tests for the code-built setup report."""

import asyncio

from fastmcp import Client, FastMCP

from gcontext import commands
from gcontext import report_strings as S
from gcontext.report import build_setup_report

INDEX_MD = """---
id: browser-recipes
name: Browser Recipes
description: A test agent that drives a browser.
connections:
  - kind: browser
    description: A browser the agent can drive
---

Objective paragraph.
"""

def _write_agent(root, index_md=INDEX_MD, name="browser-recipes"):
    module = root / "agents" / name
    module.mkdir(parents=True)
    (module / "index.md").write_text(index_md)
    return module


def _write_connection(root, name="browser"):
    conn = root / "connections" / name
    conn.mkdir(parents=True)
    return conn


def _with_setup_pending(text):
    return text.replace("\n---\n", "\nsetup: pending\n---\n", 1)


# --- The report ---


def test_report_no_agents(tmp_path):
    assert build_setup_report(tmp_path) == f"{S.HEADER}\n{S.NO_AGENTS}"


def test_report_module_without_connections_is_not_an_agent(tmp_path):
    _write_agent(tmp_path, index_md="---\nid: notes\nname: Notes\ndescription: x.\n---\n\nBody.\n", name="notes")
    assert build_setup_report(tmp_path) == f"{S.HEADER}\n{S.NO_AGENTS}"


def test_report_needs_setup(tmp_path):
    _write_agent(tmp_path, index_md=_with_setup_pending(INDEX_MD))
    report = build_setup_report(tmp_path)
    assert report == (
        f"{S.HEADER}\n"
        f"{S.AGENT_LABEL} browser-recipes\n"
        "\n"
        f"{S.CONNECTIONS_HEADING}\n"
        f"  browser        {S.CONNECTION_MISSING}\n"
        "\n"
        f"{S.STATUS_LABEL} {S.STATUS_NEEDS_SETUP}"
    )


def test_report_needs_setup_wins_over_satisfied_connections(tmp_path):
    _write_agent(tmp_path, index_md=_with_setup_pending(INDEX_MD))
    _write_connection(tmp_path)
    report = build_setup_report(tmp_path)
    assert f"  browser        {S.CONNECTION_OK}" in report
    assert f"{S.STATUS_LABEL} {S.STATUS_NEEDS_SETUP}" in report


def test_report_connection_missing(tmp_path):
    _write_agent(tmp_path)
    report = build_setup_report(tmp_path)
    assert f"  browser        {S.CONNECTION_MISSING}" in report
    assert f"{S.STATUS_LABEL} {S.STATUS_CONNECTION_MISSING}" in report


def test_report_ready_when_kind_matches(tmp_path):
    _write_agent(tmp_path)
    _write_connection(tmp_path)
    report = build_setup_report(tmp_path)
    assert f"  browser        {S.CONNECTION_OK}" in report
    assert f"{S.STATUS_LABEL} {S.STATUS_READY}" in report


def test_report_declared_connection_without_kind_is_missing(tmp_path):
    index = INDEX_MD.replace("  - kind: browser\n", "  - description: something\n", 1)
    index = index.replace("    description: A browser the agent can drive\n", "", 1)
    _write_agent(tmp_path, index_md=index)
    _write_connection(tmp_path)
    report = build_setup_report(tmp_path)
    assert S.CONNECTION_MISSING in report
    assert f"{S.STATUS_LABEL} {S.STATUS_CONNECTION_MISSING}" in report


def test_report_multiple_agents_share_one_header(tmp_path):
    _write_agent(tmp_path)
    second = INDEX_MD.replace("browser-recipes", "deploy-watch").replace(
        "kind: browser", "kind: deploy-target"
    )
    _write_agent(tmp_path, index_md=second, name="deploy-watch")
    _write_connection(tmp_path)
    report = build_setup_report(tmp_path)
    assert report.count(S.HEADER) == 1
    assert report.index(f"{S.AGENT_LABEL} browser-recipes") < report.index(f"{S.AGENT_LABEL} deploy-watch")
    assert f"\n\n{S.AGENT_LABEL} deploy-watch" in report


# --- Server-side injection into the setup prompt ---


def test_setup_prompt_injects_report(tmp_path):
    _write_agent(tmp_path, index_md=_with_setup_pending(INDEX_MD))
    mcp = FastMCP("t")
    commands.register_framework_prompts(mcp, root=tmp_path)

    async def go():
        async with Client(mcp) as c:
            return await c.get_prompt("setup", {"request": "hello"})

    text = asyncio.run(go()).messages[0].content.text
    assert "$setup_report" not in text
    assert S.HEADER in text
    assert f"{S.STATUS_LABEL} {S.STATUS_NEEDS_SETUP}" in text
    assert "hello" in text
