import asyncio
from pathlib import Path

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


@pytest.fixture(autouse=True)
def _reset_manifest():
    commands._DISABLED = set()
    commands._STABLE_KEYS.clear()
    yield
    commands._DISABLED = set()
    commands._STABLE_KEYS.clear()


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
            md = await c.get_prompt("refund_reply", {"email": "a@b.c"})
            py = await c.get_prompt("cancel", {"email": "a@b.c"})
            return names, md, py

    names, md, py = asyncio.run(go())
    assert names == ["cancel", "refund_reply"]
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
            await c.get_prompt("refund_reply", {})

    with pytest.raises(Exception):
        asyncio.run(go())


def test_commands_ledger_pipe(project):
    _write_commands(project)
    g6 = [p for p in ledger.build(project) if p["id"] == "G6"]
    assert g6 and "4 built-in (agents, ask, explain, setup) + 2 project command(s)" in g6[0]["detail"]


def test_file_command_hyphens_normalized(tmp_path):
    d = tmp_path / "modules" / "ops" / "commands"
    d.mkdir(parents=True)
    (d / "sync-data.md").write_text("---\ndescription: d\n---\nbody")
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "sync_data" in names


def test_file_command_collision_both_prefixed(tmp_path):
    for owner_kind, owner in (("connections", "stripe"), ("modules", "support")):
        d = tmp_path / owner_kind / owner / "commands"
        d.mkdir(parents=True)
        (d / "export.md").write_text("---\ndescription: d\n---\nbody")
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "stripe__export" in names
    assert "support__export" in names
    assert "export" not in names


def test_file_command_framework_names_reserved(tmp_path):
    d = tmp_path / "modules" / "support" / "commands"
    d.mkdir(parents=True)
    (d / "setup.md").write_text("---\ndescription: d\n---\nbody")
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "support__setup" in names
    assert "setup" not in names


def test_register_module_commands_short_then_prefixed(tmp_path):
    d1 = tmp_path / "modules" / "a" / "commands"
    d1.mkdir(parents=True)
    (d1 / "deploy.md").write_text("---\ndescription: d\n---\nbody")
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    d2 = tmp_path / "modules" / "b" / "commands"
    d2.mkdir(parents=True)
    (d2 / "deploy.md").write_text("---\ndescription: d\n---\nbody")
    commands.register_module_commands(mcp, tmp_path, "b")
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "deploy" in names
    assert "b__deploy" in names


def test_same_owner_stem_clash_registers_one(tmp_path):
    d = tmp_path / "modules" / "ops" / "commands"
    d.mkdir(parents=True)
    (d / "sync.md").write_text("---\ndescription: d\n---\nbody")
    (d / "sync.py").write_text(PY_COMMAND)
    mcp = FastMCP("t")
    assert commands.register_commands(mcp, tmp_path) == 1
    names = [p.name for p in asyncio.run(_prompts(mcp))]
    assert names.count("ops__sync") == 1
    assert len(names) == 1


def test_collision_prefixed_names_normalize_hyphens(tmp_path):
    for owner in ("my-ops", "your-ops"):
        d = tmp_path / "modules" / owner / "commands"
        d.mkdir(parents=True)
        (d / "export-csv.md").write_text("---\ndescription: d\n---\nbody")
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "my_ops__export_csv" in names
    assert "your_ops__export_csv" in names
    assert not any("-" in n for n in names)


def test_register_module_commands_reregister_keeps_name(tmp_path):
    d = tmp_path / "modules" / "foo" / "commands"
    d.mkdir(parents=True)
    (d / "deploy.md").write_text("---\ndescription: d\n---\nversion one")
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    (d / "deploy.md").write_text("---\ndescription: d\n---\nversion two")
    commands.register_module_commands(mcp, tmp_path, "foo")
    names = [p.name for p in asyncio.run(_prompts(mcp))]
    assert names.count("deploy") == 1
    assert "foo__deploy" not in names

    # the re-registered prompt serves the new body
    async def go():
        async with Client(mcp) as c:
            r = await c.get_prompt("deploy", {})
            return r.messages[0].content.text

    assert "version two" in asyncio.run(go())


EACH_TEMPLATE = """\
---
description: Run a saved recipe
each: recipes/*/
---
Execute recipe `$each` for $month.
"""

RECIPE_INDEX = """\
---
description: Export invoices as CSV
parameters:
  - name: month
    required: true
  - name: format
    description: Output format
---
# export-invoices
"""


def _write_template(root):
    tpl = root / "modules" / "cookbook" / "commands" / "recipe.md"
    tpl.parent.mkdir(parents=True)
    tpl.write_text(EACH_TEMPLATE)
    rec = root / "modules" / "cookbook" / "recipes" / "export-invoices"
    rec.mkdir(parents=True)
    (rec / "index.md").write_text(RECIPE_INDEX)
    bare = root / "modules" / "cookbook" / "recipes" / "check-orders"
    bare.mkdir()
    (bare / "index.md").write_text("# check orders, no frontmatter\n")


async def _prompts(mcp):
    async with Client(mcp) as c:
        return await c.list_prompts()


def test_template_expands_one_prompt_per_entry(tmp_path):
    _write_template(tmp_path)
    mcp = FastMCP("t")
    assert commands.register_commands(mcp, tmp_path) == 2

    async def go():
        async with Client(mcp) as c:
            listed = await c.list_prompts()
            filled = await c.get_prompt(
                "recipe_export_invoices",
                {"month": "2026-07", "format": "csv"},
            )
            return {p.name: p.description for p in listed}, filled

    prompts, filled = asyncio.run(go())
    assert prompts["recipe_export_invoices"] == "Export invoices as CSV"
    # entry without frontmatter falls back to the template's description
    assert prompts["recipe_check_orders"] == "Run a saved recipe"
    text = filled.messages[0].content.text
    assert "`export-invoices`" in text and "$each" not in text
    assert "2026-07" in text and "$month" not in text
    # `format` is not referenced by the template body: appended automatically
    assert 'format: "csv"' in text


def test_template_param_default_is_optional_and_noted(tmp_path):
    _write_template(tmp_path)
    rec = tmp_path / "modules" / "cookbook" / "recipes" / "export-contacts"
    rec.mkdir(parents=True)
    (rec / "index.md").write_text(
        "---\n"
        "description: Export contacts\n"
        "parameters:\n"
        "  - name: month\n"
        "    required: true\n"
        "  - name: out\n"
        "    description: Output path\n"
        "    required: true\n"
        "    default: contacts.csv\n"
        "---\n# export-contacts\n"
    )
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)

    async def go():
        async with Client(mcp) as c:
            listed = await c.list_prompts()
            # `out` has a default, so invoking without it must succeed
            filled = await c.get_prompt(
                "recipe_export_contacts", {"month": "2026-07"}
            )
            return listed, filled

    listed, filled = asyncio.run(go())
    args = {
        a.name: a.required
        for p in listed
        if p.name == "recipe_export_contacts"
        for a in p.arguments
    }
    # a default overrides required: true; the argument is optional
    assert args == {"month": True, "out": False}
    text = filled.messages[0].content.text
    assert 'out: "contacts.csv" (default when empty: contacts.csv)' in text


def test_template_skips_entry_with_malformed_default(tmp_path):
    _write_template(tmp_path)
    rec = tmp_path / "modules" / "cookbook" / "recipes" / "bad-default"
    rec.mkdir(parents=True)
    (rec / "index.md").write_text(
        "---\n"
        "description: Bad\n"
        "parameters:\n"
        "  - name: out\n"
        "    default: [a, b]\n"
        "---\nx\n"
    )
    mcp = FastMCP("t")
    # the two healthy entries from _write_template still expand
    assert commands.register_commands(mcp, tmp_path) == 2
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "recipe_bad_default" not in names


def test_template_skips_malformed_entry_and_escaping_glob(tmp_path):
    _write_template(tmp_path)
    bad = tmp_path / "modules" / "cookbook" / "recipes" / "broken"
    bad.mkdir()
    (bad / "index.md").write_text("---\ndescription: [unclosed\n---\nx\n")
    escape = tmp_path / "modules" / "cookbook" / "commands" / "sneaky.md"
    escape.write_text("---\ndescription: x\neach: ../../*/\n---\nx\n")
    mcp = FastMCP("t")
    assert commands.register_commands(mcp, tmp_path) == 2
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "recipe_broken" not in names
    assert not any("sneaky" in n for n in names)


def test_template_collision_falls_back_to_owner_prefix(tmp_path):
    _write_template(tmp_path)
    other = tmp_path / "modules" / "cookbook2" / "commands" / "recipe.md"
    other.parent.mkdir(parents=True)
    other.write_text(EACH_TEMPLATE)
    rec = tmp_path / "modules" / "cookbook2" / "recipes" / "export-invoices"
    rec.mkdir(parents=True)
    (rec / "index.md").write_text(RECIPE_INDEX)
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    # first template (sorted order) takes the short name, second falls back
    assert "recipe_export_invoices" in names
    assert "cookbook2__recipe_export_invoices" in names


def test_module_file_evicts_generated_short_name(tmp_path):
    _write_template(tmp_path)
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    d = tmp_path / "modules" / "newmod" / "commands"
    d.mkdir(parents=True)
    (d / "recipe_export_invoices.md").write_text(
        "---\ndescription: d\n---\nfile body wins"
    )
    commands.register_module_commands(mcp, tmp_path, "newmod")
    names = [p.name for p in asyncio.run(_prompts(mcp))]
    assert names.count("recipe_export_invoices") == 1
    assert "newmod__recipe_export_invoices" not in names

    async def go():
        async with Client(mcp) as c:
            r = await c.get_prompt("recipe_export_invoices", {})
            return r.messages[0].content.text

    assert "file body wins" in asyncio.run(go())


def test_refresh_generated_tracks_entry_changes(tmp_path):
    _write_template(tmp_path)
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)

    new = tmp_path / "modules" / "cookbook" / "recipes" / "find-posts"
    new.mkdir()
    (new / "index.md").write_text("---\ndescription: Find posts\n---\nx\n")
    commands.refresh_generated(
        mcp, tmp_path, "modules/cookbook/recipes/find-posts/index.md"
    )
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "recipe_find_posts" in names

    new.rename(tmp_path / "modules" / "cookbook" / "recipes" / "find-articles")
    commands.refresh_generated(
        mcp, tmp_path, "modules/cookbook/recipes/find-articles/index.md"
    )
    names = {p.name for p in asyncio.run(_prompts(mcp))}
    assert "recipe_find_articles" in names
    assert "recipe_find_posts" not in names


def test_refresh_generated_ignores_unrelated_paths(tmp_path):
    _write_template(tmp_path)
    mcp = FastMCP("t")
    commands.register_commands(mcp, tmp_path)
    before = {p.name for p in asyncio.run(_prompts(mcp))}
    commands.refresh_generated(mcp, tmp_path, "modules/other/notes.md")
    assert {p.name for p in asyncio.run(_prompts(mcp))} == before


def test_register_framework_prompts_setup():
    mcp = FastMCP("t")
    assert commands.register_framework_prompts(mcp) == 4

    async def go():
        async with Client(mcp) as c:
            listed = await c.list_prompts()
            empty = await c.get_prompt("setup", {})
            filled = await c.get_prompt("setup", {"request": "add a slack connection"})
            return listed, empty, filled

    listed, empty, filled = asyncio.run(go())
    setup = next(p for p in listed if p.name == "setup")
    assert setup.description
    empty_text = empty.messages[0].content.text
    assert '""' in empty_text and "$request" not in empty_text
    filled_text = filled.messages[0].content.text
    assert "add a slack connection" in filled_text
    for step in (
        "Block 1: the report",
        "Block 2: the plan",
        "Block 3: questions",
        "Block 4: build progress",
        "Block 5: examples explained",
        "Block 6: completion",
    ):
        assert step in filled_text


# -- manifest & stable-key tests --


def test_load_manifest_returns_disabled_set(tmp_path):
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - hetzner-vps/show-stats\n"
        "  - framework/explain\n"
    )
    commands.load_manifest(tmp_path)
    assert commands._DISABLED == {"hetzner-vps/show-stats", "framework/explain"}


def test_load_manifest_missing_file_returns_empty(tmp_path):
    commands.load_manifest(tmp_path)
    assert commands._DISABLED == set()


def test_load_manifest_empty_list_returns_empty(tmp_path):
    (tmp_path / "controls.yaml").write_text("hidden_commands: []\n")
    commands.load_manifest(tmp_path)
    assert commands._DISABLED == set()


def test_stable_key_project_command(tmp_path):
    path = tmp_path / "connections" / "stripe" / "commands" / "cancel.py"
    assert commands._stable_key(path, tmp_path) == "stripe/cancel"


def test_stable_key_module_command(tmp_path):
    path = tmp_path / "modules" / "lab-repo" / "commands" / "update-gcontext.md"
    assert commands._stable_key(path, tmp_path) == "lab-repo/update-gcontext"


def test_stable_key_framework(tmp_path):
    path = Path("/some/package/prompts/setup.md")
    assert commands._stable_key(path, tmp_path) == "framework/setup"


def test_manifest_disables_project_command(tmp_path):
    _write_commands(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - stripe/cancel\n"
    )
    mcp_inst = FastMCP("t")
    commands.load_manifest(tmp_path)
    commands.register_commands(mcp_inst, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp_inst))}
    assert "refund_reply" in names
    assert "cancel" not in names


def test_no_manifest_registers_all(tmp_path):
    _write_commands(tmp_path)
    commands.load_manifest(tmp_path)  # no controls.yaml exists
    mcp_inst = FastMCP("t")
    commands.register_commands(mcp_inst, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp_inst))}
    assert "refund_reply" in names
    assert "cancel" in names


def test_manifest_disables_framework_prompt(tmp_path):
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - framework/explain\n"
    )
    mcp_inst = FastMCP("t")
    commands.load_manifest(tmp_path)
    commands.register_framework_prompts(mcp_inst, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp_inst))}
    assert "setup" in names
    assert "agents" in names
    assert "ask" in names
    assert "explain" not in names


def test_manifest_disables_agent_command_at_install(tmp_path):
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - newmod/deploy\n"
    )
    mcp_inst = FastMCP("t")
    commands.load_manifest(tmp_path)
    commands.register_commands(mcp_inst, tmp_path)
    d = tmp_path / "modules" / "newmod" / "commands"
    d.mkdir(parents=True)
    (d / "deploy.md").write_text("---\ndescription: d\n---\ndeploy body")
    commands.register_agent_commands(mcp_inst, tmp_path, "newmod")
    names = {p.name for p in asyncio.run(_prompts(mcp_inst))}
    assert "deploy" not in names
    assert "newmod__deploy" not in names


def test_manifest_disables_generated_command(tmp_path):
    _write_template(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - cookbook/recipe_export-invoices\n"
    )
    mcp_inst = FastMCP("t")
    commands.load_manifest(tmp_path)
    commands.register_commands(mcp_inst, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp_inst))}
    assert "recipe_export_invoices" not in names
    assert "recipe_check_orders" in names


# -- hidden resource tests --


def test_is_resource_hidden_no_manifest(tmp_path):
    commands.load_manifest(tmp_path)
    assert commands.is_resource_hidden("modules/lab-repo") is False


def test_is_resource_hidden_empty_list(tmp_path):
    (tmp_path / "controls.yaml").write_text("hidden_resources: []\n")
    commands.load_manifest(tmp_path)
    assert commands.is_resource_hidden("modules/lab-repo") is False


def test_is_resource_hidden_exact_key(tmp_path):
    (tmp_path / "controls.yaml").write_text(
        "hidden_resources:\n"
        "  - modules/bot-commenter\n"
        "  - connections/hetzner-vps\n"
    )
    commands.load_manifest(tmp_path)
    assert commands.is_resource_hidden("modules/bot-commenter") is True
    assert commands.is_resource_hidden("connections/hetzner-vps") is True
    assert commands.is_resource_hidden("modules/lab-repo") is False
    assert commands.is_resource_hidden("root") is False


def test_is_resource_hidden_glob(tmp_path):
    (tmp_path / "controls.yaml").write_text(
        "hidden_resources:\n"
        "  - modules/*\n"
    )
    commands.load_manifest(tmp_path)
    assert commands.is_resource_hidden("modules/lab-repo") is True
    assert commands.is_resource_hidden("modules/bot-commenter") is True
    assert commands.is_resource_hidden("connections/stripe") is False
    assert commands.is_resource_hidden("modules") is False


def test_is_resource_hidden_file_level_key(tmp_path):
    (tmp_path / "controls.yaml").write_text(
        "hidden_resources:\n"
        "  - modules/lab-repo/decisions.md\n"
    )
    commands.load_manifest(tmp_path)
    assert commands.is_resource_hidden("modules/lab-repo/decisions.md") is True
    assert commands.is_resource_hidden("modules/lab-repo") is False


def test_controls_yaml_carries_both_keys(tmp_path):
    _write_commands(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - stripe/cancel\n"
        "hidden_resources:\n"
        "  - modules/lab-repo\n"
    )
    mcp_inst = FastMCP("t")
    commands.load_manifest(tmp_path)
    commands.register_commands(mcp_inst, tmp_path)
    names = {p.name for p in asyncio.run(_prompts(mcp_inst))}
    assert "cancel" not in names
    assert commands.is_resource_hidden("modules/lab-repo") is True
