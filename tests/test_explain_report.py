"""Tests for the explain report: the agent list, the per-agent
Does / Connects / Learns / Flow block, and the prompt injection."""

import asyncio
from datetime import datetime

from fastmcp import Client, FastMCP

from gcontext import commands, registry
from gcontext import report_strings as S
from gcontext.report import build_explain_report

INDEX_MD = """---
id: browser-recipes
name: Browser Recipes
description: A test agent that drives a browser.
connections:
  - kind: browser
    description: A browser the agent can drive
flow:
  - Describe a browser action in plain words
  - The agent reuses a saved recipe when one matches
  - Otherwise it explores the site live and records every step
  - A tested script is saved for next time
  - Broken recipes are re-explored and replaced
learns: Recipes per action and the quirks of your sites.
---

Objective paragraph.
"""

CONNECTION_YAML = """name: chrome-cdp
description: Chrome over CDP
kind: browser
secrets: []
deps: []
"""


def _write_agent(root, index_md=INDEX_MD, name="browser-recipes"):
    module = root / "modules" / name
    module.mkdir(parents=True)
    (module / "index.md").write_text(index_md)
    return module


def _write_connection(root, yaml_text=CONNECTION_YAML, name="chrome-cdp"):
    conn = root / "connections" / name
    conn.mkdir(parents=True)
    (conn / "connection.yaml").write_text(yaml_text)
    return conn


def _today():
    return datetime.now().strftime("%Y-%m-%d")


# --- List mode ---


def test_explain_no_agents(tmp_path):
    assert build_explain_report(tmp_path) == f"{S.HEADER}\n{S.NO_AGENTS}"


def test_explain_list_mode(tmp_path):
    _write_agent(tmp_path)
    second = INDEX_MD.replace("browser-recipes", "deploy-watch").replace(
        "kind: browser", "kind: deploy-target"
    )
    _write_agent(tmp_path, index_md=registry.stamp_setup_pending(second), name="deploy-watch")
    _write_connection(tmp_path)
    report = build_explain_report(tmp_path)
    assert report == (
        f"{S.HEADER}\n"
        f"browser-recipes     {S.STATUS_READY}\n"
        f"deploy-watch        {S.STATUS_NEEDS_SETUP}"
    )


def test_explain_list_connection_missing(tmp_path):
    _write_agent(tmp_path)
    report = build_explain_report(tmp_path)
    assert "browser-recipes" in report
    assert S.STATUS_CONNECTION_MISSING in report


# --- Per-agent mode ---


def test_explain_agent_with_flow(tmp_path):
    module = _write_agent(tmp_path)
    recipes = module / "recipes"
    recipes.mkdir()
    (recipes / "export-report.py").write_text("# recipe\n")
    (recipes / "export-report.md").write_text("# meta\n")
    _write_connection(tmp_path)
    report = build_explain_report(tmp_path, "browser-recipes")
    assert report == (
        f"{S.AGENT_LABEL} browser-recipes\n"
        "\n"
        f"{S.DOES_LABEL:<10}A test agent that drives a browser.\n"
        f"{S.CONNECTS_LABEL:<10}browser        {S.CONNECTION_OK}\n"
        f"{S.LEARNS_LABEL:<10}Recipes per action and the quirks of your sites.\n"
        f"          recipes/  2 {S.FILES_WORD}\n"
        f"          {S.LAST_ACTIVITY_LABEL}  {_today()}\n"
        f"{S.FLOW_LABEL:<10}1. Describe a browser action in plain words\n"
        "          2. The agent reuses a saved recipe when one matches\n"
        "          3. Otherwise it explores the site live and records every step\n"
        "          4. A tested script is saved for next time\n"
        "          5. Broken recipes are re-explored and replaced"
    )


def test_explain_agent_without_flow(tmp_path):
    flow_block = (
        "flow:\n"
        "  - Describe a browser action in plain words\n"
        "  - The agent reuses a saved recipe when one matches\n"
        "  - Otherwise it explores the site live and records every step\n"
        "  - A tested script is saved for next time\n"
        "  - Broken recipes are re-explored and replaced\n"
    )
    _write_agent(tmp_path, index_md=INDEX_MD.replace(flow_block, "", 1))
    report = build_explain_report(tmp_path, "browser-recipes")
    assert f"{S.FLOW_LABEL:<10}{S.FLOW_NOT_DECLARED}" in report
    assert "1." not in report


def test_explain_agent_missing_connection(tmp_path):
    _write_agent(tmp_path)
    report = build_explain_report(tmp_path, "browser-recipes")
    assert f"{S.CONNECTS_LABEL:<10}browser        {S.CONNECTION_MISSING}" in report


def test_explain_live_counts_skip_machine_folders(tmp_path):
    module = _write_agent(tmp_path)
    (module / "runs").mkdir()
    (module / "runs" / "index.md").write_text("run\n")
    (module / ".git").mkdir()
    (module / ".git" / "HEAD").write_text("ref\n")
    (module / "__pycache__").mkdir()
    (module / "__pycache__" / "x.pyc").write_text("")
    report = build_explain_report(tmp_path, "browser-recipes")
    assert f"runs/  1 {S.FILES_WORD}" in report
    assert ".git" not in report
    assert "__pycache__" not in report
    assert f"{S.LAST_ACTIVITY_LABEL}  {_today()}" in report


def test_explain_unknown_agent(tmp_path):
    _write_agent(tmp_path)
    report = build_explain_report(tmp_path, "nope")
    assert report == S.UNKNOWN_AGENT.format(agent="nope", ids="browser-recipes")


def test_explain_unknown_agent_no_agents(tmp_path):
    report = build_explain_report(tmp_path, "nope")
    assert report == S.UNKNOWN_AGENT.format(agent="nope", ids=S.NO_INSTALLED_IDS)


# --- Server-side injection into the explain prompt ---


def test_explain_prompt_injects_agent_report(tmp_path):
    _write_agent(tmp_path)
    _write_connection(tmp_path)
    mcp = FastMCP("t")
    commands.register_framework_prompts(mcp, root=tmp_path)

    async def go():
        async with Client(mcp) as c:
            return await c.get_prompt("explain", {"agent": "browser-recipes"})

    text = asyncio.run(go()).messages[0].content.text
    assert "$explain_report" not in text
    assert f"{S.AGENT_LABEL} browser-recipes" in text
    assert f"{S.DOES_LABEL:<10}A test agent that drives a browser." in text
    assert f"{S.FLOW_LABEL:<10}1. Describe a browser action in plain words" in text


def test_explain_prompt_injects_list_without_agent(tmp_path):
    _write_agent(tmp_path)
    _write_connection(tmp_path)
    mcp = FastMCP("t")
    commands.register_framework_prompts(mcp, root=tmp_path)

    async def go():
        async with Client(mcp) as c:
            return await c.get_prompt("explain", {})

    text = asyncio.run(go()).messages[0].content.text
    assert "$explain_report" not in text
    assert S.HEADER in text
    assert S.STATUS_READY in text
    assert f"{S.FLOW_LABEL:<10}" not in text
