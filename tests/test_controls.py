from pathlib import Path

import pytest

from gcontext import controls


def test_parse_missing_file_returns_none(tmp_path):
    assert controls.parse(tmp_path / "controls.yaml") is None


def test_parse_empty_file_returns_empty_registry(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("")
    reg = controls.parse(p)
    assert reg.commands == {} and reg.resources == {} and reg.pinned == []


def test_parse_sections(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text(
        "commands:\n"
        "  framework/explain: off\n"
        "  bot-commenter/setup: on\n"
        "resources:\n"
        "  modules/bot-commenter: off\n"
        "pinned:\n"
        "  - modules/lab-repo/decisions-in-force.md\n"
    )
    reg = controls.parse(p)
    assert reg.commands == {"framework/explain": False, "bot-commenter/setup": True}
    assert reg.resources == {"modules/bot-commenter": False}
    assert reg.pinned == ["modules/lab-repo/decisions-in-force.md"]


def test_parse_malformed_yaml_raises(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("commands:\n\t- bad tab\n")
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_parse_non_mapping_raises(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("- just\n- a list\n")
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_parse_duplicate_key_off_wins(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text(
        "commands:\n"
        "  a/x: on\n"
        "  a/x: off\n"
        "resources:\n"
        "  modules/m: off\n"
        "  modules/m: on\n"
    )
    reg = controls.parse(p)
    assert reg.commands == {"a/x": False}
    assert reg.resources == {"modules/m": False}


def _make_state(root: Path):
    """A small state folder: one module with a command and a template, one
    connection with a command, one agent, plus a matched template entry."""
    (root / "modules/bot/commands").mkdir(parents=True)
    (root / "modules/bot/commands/setup.md").write_text(
        "---\ndescription: d\n---\nbody\n"
    )
    (root / "modules/bot/commands/profile.md").write_text(
        "---\ndescription: d\neach: profiles/*\n---\nbody $each\n"
    )
    (root / "modules/bot/profiles/reddit").mkdir(parents=True)
    (root / "connections/api/commands").mkdir(parents=True)
    (root / "connections/api/commands/ping.py").write_text(
        "# ---\n# description: d\n# ---\nprint('x')\n"
    )
    (root / "agents/crafter/commands").mkdir(parents=True)
    (root / "agents/crafter/commands/run.md").write_text(
        "---\ndescription: d\n---\nbody\n"
    )


def test_inventory_commands_and_resources(tmp_path):
    _make_state(tmp_path)
    cmds, res = controls.inventory(tmp_path)
    assert "bot/setup" in cmds
    assert "bot/profile" in cmds          # template: one key, no per-entry keys
    assert "bot/profile_reddit" not in cmds
    assert "api/ping" in cmds
    assert "crafter/run" in cmds
    assert "framework/setup" in cmds      # framework prompts included
    assert "framework/framework-instructions" not in cmds
    assert res == ["agents/crafter", "connections/api", "modules/bot"]


def test_inventory_empty_root(tmp_path):
    cmds, res = controls.inventory(tmp_path)
    assert res == []
    assert all(k.startswith("framework/") for k in cmds)
    assert cmds  # framework prompts always exist


def test_command_enabled_chain(tmp_path):
    _make_state(tmp_path)
    reg = controls.Registry(
        commands={
            "bot/setup": True,          # explicit on under off owner: stays live
            "api/ping": False,          # explicit off under on owner
            "bot/profile": True,        # template entry
            "bot/profile_reddit": False,  # per-entry override beats template
        },
        resources={"modules/bot": False, "connections/api": True},
    )
    root = tmp_path
    # explicit entries win over everything
    assert controls.command_enabled(reg, root, "bot/setup") is True
    assert controls.command_enabled(reg, root, "api/ping") is False
    # generated entry: per-entry override > template entry
    assert controls.command_enabled(
        reg, root, "bot/profile_reddit", template_key="bot/profile") is False
    assert controls.command_enabled(
        reg, root, "bot/profile_other", template_key="bot/profile") is True
    # unlisted command under an off owner: cascade disables it
    assert controls.command_enabled(reg, root, "bot/unlisted") is False
    # unlisted command under an on owner, and under an unlisted owner: on
    assert controls.command_enabled(reg, root, "api/unlisted") is True
    assert controls.command_enabled(reg, root, "crafter/run") is True
    # framework: no owner folder, no cascade, default on
    assert controls.command_enabled(reg, root, "framework/setup") is True


def test_template_off_disables_generated(tmp_path):
    _make_state(tmp_path)
    reg = controls.Registry(commands={"bot/profile": False})
    assert controls.command_enabled(
        reg, tmp_path, "bot/profile_reddit", template_key="bot/profile") is False


def test_parse_null_value_raises(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("commands:\n  a/x:\n")
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_parse_quoted_string_value_raises(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text('commands:\n  a/x: "off"\n')
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_parse_nested_mapping_value_raises(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("commands:\n  a/x: {nested: 1}\n")
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_parse_pinned_non_list_raises(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("pinned: not-a-list\n")
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_resource_enabled_default_on():
    reg = controls.Registry(resources={"modules/bot": False})
    assert controls.resource_enabled(reg, "modules/bot") is False
    assert controls.resource_enabled(reg, "modules/other") is True
    assert controls.resource_enabled(reg, "root") is True


def test_heal_scaffolds_missing_file(tmp_path):
    _make_state(tmp_path)
    assert controls.heal(tmp_path) is True
    reg = controls.parse(tmp_path / "controls.yaml")
    cmds, res = controls.inventory(tmp_path)
    assert set(reg.commands) == set(cmds)
    assert set(reg.resources) == set(res)
    assert all(v is None for v in reg.commands.values())
    assert all(reg.resources.values())


def test_heal_is_idempotent(tmp_path):
    _make_state(tmp_path)
    controls.heal(tmp_path)
    assert controls.heal(tmp_path) is False


def test_heal_appends_and_preserves_comments_and_off(tmp_path):
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "# my note\n"
        "commands:\n"
        "  bot/setup: off  # keep this off\n"
        "resources:\n"
        "  modules/bot: on\n"
    )
    assert controls.heal(tmp_path) is True
    text = (tmp_path / "controls.yaml").read_text()
    assert "# my note" in text
    assert "bot/setup: off  # keep this off" in text
    reg = controls.parse(tmp_path / "controls.yaml")
    assert reg.commands["bot/setup"] is False        # off survives the heal
    assert reg.commands["api/ping"] is None          # missing entry appended auto
    assert reg.resources["connections/api"] is True


def test_heal_creates_missing_section(tmp_path):
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text("commands:\n  bot/setup: on\n")
    controls.heal(tmp_path)
    reg = controls.parse(tmp_path / "controls.yaml")
    assert reg.resources["modules/bot"] is True


def test_heal_dedupes_off_wins(tmp_path):
    _make_state(tmp_path)
    controls.heal(tmp_path)
    with open(tmp_path / "controls.yaml", "a") as f:
        f.write("commands:\n  bot/setup: off\n")
    # duplicate section and key: after a heal the file has one line, off
    controls.heal(tmp_path)
    text = (tmp_path / "controls.yaml").read_text()
    assert text.count("bot/setup:") == 1
    assert controls.parse(tmp_path / "controls.yaml").commands["bot/setup"] is False


def test_heal_keeps_stale_entries(tmp_path, capsys):
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "commands:\n  gone/away: off\nresources:\n  modules/gone: off\n"
    )
    controls.heal(tmp_path, warn=True)
    reg = controls.parse(tmp_path / "controls.yaml")
    assert reg.commands["gone/away"] is False        # kept, never pruned
    assert reg.resources["modules/gone"] is False
    err = capsys.readouterr().err
    assert "gone/away" in err and "modules/gone" in err


def test_heal_malformed_yaml_raises(tmp_path):
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text("commands:\n\t- bad\n")
    with pytest.raises(controls.ControlsError):
        controls.heal(tmp_path)


def test_migrate_old_format(tmp_path):
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - framework/explain\n"
        "hidden_resources:\n"
        "  - modules/bot\n"
        "  - connections/*\n"
        "pinned_resources:\n"
        "  - modules/bot/learnings/x.md\n"
    )
    assert controls.migrate(tmp_path) is True
    reg = controls.parse(tmp_path / "controls.yaml")
    # hidden command becomes off
    assert reg.commands["framework/explain"] is False
    # old resource hiding never touched commands: every command under the
    # hidden owner gets an explicit on line, so the cascade cannot kill it
    assert reg.commands["bot/setup"] is True
    assert reg.commands["api/ping"] is True
    # hidden resources (including glob expansion at migration time) become off
    assert reg.resources["modules/bot"] is False
    assert reg.resources["connections/api"] is False
    assert reg.resources["agents/crafter"] is True
    assert reg.pinned == ["modules/bot/learnings/x.md"]
    # the whole disk inventory is present
    cmds, res = controls.inventory(tmp_path)
    assert set(reg.commands) == set(cmds)
    assert set(reg.resources) == set(res)


def test_migrate_skips_new_format(tmp_path):
    _make_state(tmp_path)
    controls.heal(tmp_path)
    before = (tmp_path / "controls.yaml").read_text()
    assert controls.migrate(tmp_path) is False
    assert (tmp_path / "controls.yaml").read_text() == before


def test_migrate_skips_missing_file(tmp_path):
    assert controls.migrate(tmp_path) is False


def test_migrate_warns_on_mixed_format(tmp_path, capsys):
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n"
        "  - framework/explain\n"
        "commands:\n"
        "  bot/setup: off\n"
    )
    assert controls.migrate(tmp_path) is True
    reg = controls.parse(tmp_path / "controls.yaml")
    # the migrated registry comes purely from the old keys
    assert reg.commands["framework/explain"] is False
    assert reg.commands["bot/setup"] is True
    err = capsys.readouterr().err
    assert "discarding" in err


def test_parse_auto_value(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("commands:\n  a/x: auto\n")
    reg = controls.parse(p)
    assert reg.commands["a/x"] is None


def test_parse_auto_rejected_in_resources(tmp_path):
    p = tmp_path / "controls.yaml"
    p.write_text("resources:\n  modules/m: auto\n")
    with pytest.raises(controls.ControlsError):
        controls.parse(p)


def test_auto_follows_owner_cascade(tmp_path):
    _make_state(tmp_path)
    reg = controls.Registry(
        commands={"bot/setup": None},
        resources={"modules/bot": False},
    )
    assert controls.command_enabled(reg, tmp_path, "bot/setup") is False
    reg.resources["modules/bot"] = True
    assert controls.command_enabled(reg, tmp_path, "bot/setup") is True


def test_owner_off_disables_healed_commands_end_to_end(tmp_path):
    # the scenario that motivated auto: heal first, then flip the owner off
    _make_state(tmp_path)
    controls.heal(tmp_path)
    text = (tmp_path / "controls.yaml").read_text()
    (tmp_path / "controls.yaml").write_text(
        text.replace("modules/bot: on", "modules/bot: off")
    )
    controls.heal(tmp_path)  # must not resurrect anything
    reg = controls.parse(tmp_path / "controls.yaml")
    assert controls.command_enabled(reg, tmp_path, "bot/setup") is False
    assert controls.command_enabled(reg, tmp_path, "api/ping") is True


def test_auto_template_entry_follows_owner(tmp_path):
    _make_state(tmp_path)
    reg = controls.Registry(
        commands={"bot/profile": None},
        resources={"modules/bot": False},
    )
    assert controls.command_enabled(
        reg, tmp_path, "bot/profile_reddit", template_key="bot/profile") is False


def test_command_enabled_no_root_skips_cascade():
    reg = controls.Registry(resources={"modules/bot": False})
    assert controls.command_enabled(reg, None, "bot/unlisted") is True


def test_server_load_controls_migrates_heals_and_counts(tmp_path, monkeypatch):
    from gcontext import commands as commands_mod
    from gcontext import server
    _make_state(tmp_path)
    (tmp_path / "controls.yaml").write_text(
        "hidden_commands:\n  - framework/explain\n"
        "hidden_resources:\n  - modules/bot\n"
    )
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    # commands_mod._REGISTRY is process-global state; other test modules
    # (e.g. test_explain_report.py) register framework prompts assuming a
    # clean registry, so restore it once this test's assertions are done.
    saved_registry, saved_root = commands_mod._REGISTRY, commands_mod._ROOT
    try:
        n_off_cmds, n_off_res = server.load_controls()
        assert n_off_cmds == 1 and n_off_res == 1
        # migrated to the new format and healed to completeness
        reg = controls.parse(tmp_path / "controls.yaml")
        cmds, res = controls.inventory(tmp_path)
        assert set(reg.commands) == set(cmds)
        assert set(reg.resources) == set(res)
    finally:
        commands_mod._REGISTRY, commands_mod._ROOT = saved_registry, saved_root


def test_on_list_resources_warns_once_then_resets(tmp_path, monkeypatch, capsys):
    import asyncio

    from gcontext import commands as commands_mod
    from gcontext import server

    _make_state(tmp_path)
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    server._CONTROLS_WARNED = False

    async def call_next(context):
        return None

    tracker = server.ConnectionTracker()

    # heal() raises ControlsError on every request while controls.yaml stays
    # malformed: the stderr line must print once, not once per request.
    monkeypatch.setattr(
        server.controls_mod, "heal",
        lambda root: (_ for _ in ()).throw(server.controls_mod.ControlsError("bad")),
    )
    asyncio.run(tracker.on_list_resources(None, call_next))
    asyncio.run(tracker.on_list_resources(None, call_next))
    err = capsys.readouterr().err
    assert err.count("keeping the last good controls state") == 1
    assert server._CONTROLS_WARNED is True

    # once heal+load succeed again, the flag resets so a later failure warns
    # again instead of staying silent forever.
    monkeypatch.undo()
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    saved_registry, saved_root = commands_mod._REGISTRY, commands_mod._ROOT
    try:
        asyncio.run(tracker.on_list_resources(None, call_next))
    finally:
        commands_mod._REGISTRY, commands_mod._ROOT = saved_registry, saved_root
    assert server._CONTROLS_WARNED is False


def test_cmd_init_scaffolds_controls(tmp_path, monkeypatch):
    from gcontext import cli, telemetry

    monkeypatch.setattr(telemetry, "ping_install", lambda *a, **k: None)

    class Args:
        directory = str(tmp_path / "fresh")

    cli.cmd_init(Args())
    reg = controls.parse(tmp_path / "fresh" / "controls.yaml")
    assert reg is not None
    assert any(k.startswith("framework/") for k in reg.commands)
    assert all(v is None for v in reg.commands.values())
