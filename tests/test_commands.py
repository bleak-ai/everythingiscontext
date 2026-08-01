import asyncio

import pytest
from fastmcp import Client, FastMCP

from gcontext import commands, ledger, server

MD_COMMAND = """\
---
description: Draft a refund reply
parameters:
  - name: email
    description: Customer email
    required: true
---
Draft a refund reply for $email and show it to the user.
"""

PY_COMMAND = """\
# ---
# description: Cancel a subscription
# parameters:
#   - name: email
#     required: true
# ---
print("would cancel")
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: t\n")
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    return tmp_path


def _write_commands(root):
    md = root / "modules" / "support" / "commands" / "refund_reply.md"
    md.parent.mkdir(parents=True)
    md.write_text(MD_COMMAND)
    py = root / "connections" / "stripe" / "commands" / "cancel.py"
    py.parent.mkdir(parents=True)
    py.write_text(PY_COMMAND)


def test_parse_command_frontmatter_and_body():
    meta, body = commands.parse_command(MD_COMMAND)
    assert meta["description"] == "Draft a refund reply"
    assert meta["parameters"][0]["name"] == "email"
    assert body.startswith("Draft a refund reply for $email")


def test_parse_command_rejects_missing_frontmatter():
    with pytest.raises(ValueError):
        commands.parse_command("no frontmatter here")


def test_parse_script_command_comment_block():
    meta = commands.parse_script_command(PY_COMMAND)
    assert meta["description"] == "Cancel a subscription"
    assert meta["parameters"][0]["required"] is True


def test_register_commands_counts_and_skips_malformed(tmp_path):
    _write_commands(tmp_path)
    bad = tmp_path / "modules" / "support" / "commands" / "broken.md"
    bad.write_text("no frontmatter")
    mcp = FastMCP("t")
    assert commands.register_commands(mcp, tmp_path) == 2


def test_prompt_roundtrip_over_protocol(tmp_path):
    _write_commands(tmp_path)
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)

    async def go():
        async with Client(mcp) as c:
            listed = await c.list_prompts()
            names = sorted(p.name for p in listed)
            md = await c.get_prompt("support__refund_reply", {"email": "a@b.c"})
            py = await c.get_prompt("stripe__cancel", {"email": "a@b.c"})
            return names, md, py

    names, md, py = asyncio.run(go())
    assert names == ["stripe__cancel", "support__refund_reply"]
    md_text = md.messages[0].content.text
    assert "a@b.c" in md_text and "$email" not in md_text
    py_text = py.messages[0].content.text
    assert "run_script" in py_text
    assert "connections/stripe/commands/cancel.py" in py_text
    assert '"email": "a@b.c"' in py_text


def test_prompt_rejects_missing_required_argument(tmp_path):
    _write_commands(tmp_path)
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)

    async def go():
        async with Client(mcp) as c:
            await c.get_prompt("support__refund_reply", {})

    with pytest.raises(Exception):
        asyncio.run(go())


def test_commands_ledger_pipe(project):
    _write_commands(project)
    g6 = [p for p in ledger.build(project) if p["id"] == "G6"]
    assert g6 and "2 command(s)" in g6[0]["detail"]
