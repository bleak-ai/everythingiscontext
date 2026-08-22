import asyncio
import json

import pytest
from starlette.testclient import TestClient

from gcontext import dashboard, server


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: t\ndescription: test agent\n")
    (tmp_path / "agent.md").write_text("# Agent\nbe useful\n")
    (tmp_path / "secrets.env").write_text("API_KEY=sk-verysecret\nEMPTY=\n")
    conn = tmp_path / "connections" / "gmail"
    conn.mkdir(parents=True)
    conn.joinpath("connection.yaml").write_text(
        "name: gmail\ndescription: mail\nsecrets: [API_KEY, MISSING_KEY]\ndeps: [requests]\n"
    )
    conn.joinpath("index.md").write_text("# gmail docs")
    mod = tmp_path / "modules" / "notes"
    mod.mkdir(parents=True)
    mod.joinpath("module.yaml").write_text("name: notes\ndescription: keep notes\n")
    mod.joinpath("index.md").write_text("# notes")
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    server.EVENTS.clear()
    return tmp_path


@pytest.fixture
def client(project):
    with TestClient(server.mcp.http_app()) as c:
        yield c


def test_api_project(client):
    data = client.get("/api/project").json()
    assert data["name"] == "t"
    assert data["description"] == "test agent"
    assert data["has_instructions"] is True
    assert data["instructions_lines"] == 2


def test_api_connections_no_secret_values(client):
    resp = client.get("/api/connections")
    data = resp.json()
    assert len(data) == 1
    gmail = data[0]
    assert gmail["ready"] is False
    assert {"name": "API_KEY", "filled": True} in gmail["secrets"]
    assert {"name": "MISSING_KEY", "filled": False} in gmail["secrets"]
    assert "connections/gmail/index.md" in gmail["files"]
    assert "sk-verysecret" not in resp.text


def test_api_modules(client):
    data = client.get("/api/modules").json()
    assert data[0]["name"] == "notes"
    assert "modules/notes/index.md" in data[0]["files"]


def test_api_ledger(client):
    data = client.get("/api/ledger").json()
    assert any(p["id"] == "G0" for p in data["ledger"])


def test_api_file(client):
    data = client.get("/api/file", params={"path": "connections/gmail/index.md"}).json()
    assert data["content"] == "# gmail docs"
    assert client.get("/api/file", params={"path": "secrets.env"}).status_code == 403
    assert client.get("/api/file", params={"path": "../outside.txt"}).status_code == 403
    assert client.get("/api/file", params={"path": ".venv/bin/python"}).status_code == 403
    assert client.get("/api/file", params={"path": "nope.md"}).status_code == 404
    assert client.get("/api/file").status_code == 400


def test_api_tree_excludes_machine_and_secret_files(client):
    paths = [e["path"] for e in client.get("/api/tree").json()["tree"]]
    assert "connections/gmail/index.md" in paths
    assert "secrets.env" not in paths
    assert not any(p.startswith(".venv") for p in paths)


def test_status_reports_staleness(client, project):
    import os

    server.snapshot_startup_files()
    stale = client.get("/status").json()["stale"]
    assert stale == {"agent_md": False, "commands": False}

    agent_md = project / "agent.md"
    os.utime(agent_md, (agent_md.stat().st_mtime + 10,) * 2)
    stale = client.get("/status").json()["stale"]
    assert stale["agent_md"] is True
    assert stale["commands"] is False

    cmd = project / "modules" / "notes" / "commands" / "report.md"
    cmd.parent.mkdir(parents=True)
    cmd.write_text("---\ndescription: d\n---\nbody\n")
    stale = client.get("/status").json()["stale"]
    assert stale["commands"] is True


def test_api_events_limit_since_and_ring_cap(client):
    for i in range(350):
        server.record_event("s", "tool", f"tool{i}")
    assert len(server.EVENTS) == 300

    data = client.get("/api/events?limit=10").json()
    assert len(data["events"]) == 10
    assert data["latest_id"] == data["events"][-1]["id"]

    since = data["events"][-1]["id"] - 3
    newer = client.get(f"/api/events?since={since}").json()["events"]
    assert all(e["id"] > since for e in newer)

    assert client.get("/api/events?limit=x").status_code == 400


def test_middleware_records_scrubbed_tool_event(project):
    class Msg:
        name = "write_file"
        arguments = {"path": "a.md", "content": "top secret document"}

    class Ctx:
        message = Msg()
        fastmcp_context = None

    class Result:
        class Block:
            text = "Written: a.md, key sk-verysecret leaked"
        content = [Block()]

    async def call_next(context):
        return Result()

    tracker = server.ConnectionTracker()
    asyncio.run(tracker.on_call_tool(Ctx(), call_next))

    event = server.EVENTS[-1]
    assert event["kind"] == "tool"
    assert event["name"] == "write_file"
    assert "top secret document" not in json.dumps(event)
    assert "sk-verysecret" not in event["preview"]
    assert "***" in event["preview"]
    assert event["detail"] == "a.md (19 bytes)"


def test_middleware_records_error_and_reraises(project):
    class Msg:
        name = "read_file"
        arguments = {}

    class Ctx:
        message = Msg()
        fastmcp_context = None

    async def call_next(context):
        raise RuntimeError("boom")

    tracker = server.ConnectionTracker()
    with pytest.raises(RuntimeError):
        asyncio.run(tracker.on_call_tool(Ctx(), call_next))
    event = server.EVENTS[-1]
    assert event["kind"] == "error"
    assert event["error"] is True
    assert "boom" in event["preview"]


@pytest.fixture
def controls_project(project):
    """The dashboard project plus command files and a controls.yaml with one
    off command, one off owner, and a template."""
    from gcontext import commands as commands_mod

    cmds = project / "modules" / "notes" / "commands"
    cmds.mkdir(parents=True)
    (cmds / "report.md").write_text("---\ndescription: d\n---\nbody\n")
    (cmds / "voice.md").write_text(
        "---\ndescription: d\neach: profiles/*\n---\nbody $each\n"
    )
    (project / "modules" / "notes" / "profiles" / "reddit").mkdir(parents=True)
    gcmds = project / "connections" / "gmail" / "commands"
    gcmds.mkdir(parents=True)
    (gcmds / "send.md").write_text("---\ndescription: d\n---\nbody\n")
    (project / "controls.yaml").write_text(
        "commands:\n"
        "  notes/report: on  # explicit on under off owner\n"
        "  notes/voice: off\n"
        "  gmail/send: off\n"
        "  gone/away: off\n"
        "resources:\n"
        "  modules/notes: off\n"
        "  connections/gmail: on\n"
        "pinned:\n"
        "  - modules/notes/index.md\n"
    )
    saved_registry = commands_mod._REGISTRY
    saved_root = commands_mod._ROOT
    saved_keys = dict(commands_mod._STABLE_KEYS)
    saved_registered = dict(commands_mod._REGISTERED)
    commands_mod.load_manifest(project)
    yield project
    commands_mod._REGISTRY = saved_registry
    commands_mod._ROOT = saved_root
    commands_mod._STABLE_KEYS.clear()
    commands_mod._STABLE_KEYS.update(saved_keys)
    commands_mod._REGISTERED.clear()
    commands_mod._REGISTERED.update(saved_registered)


def test_api_controls_get_flat_and_effective(client, controls_project):
    """Flat shape: top-level commands, resources, pinned, stale."""
    data = client.get("/api/controls").json()
    assert set(data) >= {"commands", "resources", "pinned", "stale"}
    # -- commands --
    by_key = {c["key"]: c for c in data["commands"]}
    report = by_key["notes/report"]
    assert report["owner"] == "notes"
    assert report["raw"] == "on" and report["effective"] is True
    assert report["template"] is False
    assert report["description"] == "d"
    assert report["path"] == "modules/notes/commands/report.md"
    assert "locked" not in report
    voice = by_key["notes/voice"]
    assert voice["raw"] == "off" and voice["effective"] is False
    assert voice["template"] is True
    send = by_key["gmail/send"]
    assert send["owner"] == "gmail"
    assert send["raw"] == "off" and send["effective"] is False
    # framework rows: normal rows, no locked flag
    setup = by_key["framework/setup"]
    assert setup["owner"] == "framework"
    assert setup["path"].startswith("gcontext/prompts/")
    assert "locked" not in setup
    explain = by_key["framework/explain"]
    assert "locked" not in explain
    # -- resources --
    res_by_key = {r["key"]: r for r in data["resources"]}
    notes_res = res_by_key["modules/notes"]
    assert notes_res["kind"] == "modules"
    assert notes_res["raw"] == "off" and notes_res["effective"] is False
    assert {"name", "custom", "description"} <= set(notes_res)
    gmail_res = res_by_key["connections/gmail"]
    assert gmail_res["raw"] == "on" and gmail_res["effective"] is True
    # -- pinned and stale --
    assert data["pinned"] == ["modules/notes/index.md"]
    assert {"section": "commands", "key": "gone/away"} in data["stale"]


def test_api_controls_get_malformed_409(client, controls_project):
    (controls_project / "controls.yaml").write_text("commands:\n\t- bad\n")
    resp = client.get("/api/controls")
    assert resp.status_code == 409
    assert "controls.yaml" in resp.json()["error"]


def test_api_controls_post_resource_off_is_live(client, controls_project):
    from gcontext import commands as commands_mod

    resp = client.post("/api/controls", json={
        "section": "resources", "key": "connections/gmail", "value": "off",
    })
    assert resp.status_code == 200
    data = resp.json()
    gmail_res = next(r for r in data["resources"] if r["key"] == "connections/gmail")
    assert gmail_res["raw"] == "off" and gmail_res["effective"] is False
    assert commands_mod.is_resource_hidden("connections/gmail") is True
    assert "reload" not in data["note"]


def test_api_controls_post_command_off_reload_note(client, controls_project):
    resp = client.post("/api/controls", json={
        "section": "commands", "key": "notes/report", "value": "off",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "gcontext reload" in data["note"]
    text = (controls_project / "controls.yaml").read_text()
    assert "notes/report: off  # explicit on under off owner" in text


def test_api_controls_post_bad_requests(client, controls_project):
    assert client.post("/api/controls", json={
        "section": "resources", "key": "modules/notes", "value": "auto",
    }).status_code == 400
    # auto is also rejected for commands now
    assert client.post("/api/controls", json={
        "section": "commands", "key": "notes/report", "value": "auto",
    }).status_code == 400
    assert client.post("/api/controls", json={
        "section": "prompts", "key": "x", "value": "on",
    }).status_code == 400
    assert client.post("/api/controls", json={}).status_code == 400
    assert client.post(
        "/api/controls", content=b"not json",
        headers={"content-type": "application/json"},
    ).status_code == 400


def test_api_controls_post_pin_round_trip(client, controls_project):
    resp = client.post("/api/controls", json={
        "pin": "modules/notes/notes.md", "pinned": True,
    })
    assert resp.status_code == 200
    assert "modules/notes/notes.md" in resp.json()["pinned"]
    resp = client.post("/api/controls", json={
        "pin": "modules/notes/notes.md", "pinned": False,
    })
    assert "modules/notes/notes.md" not in resp.json()["pinned"]


def test_api_controls_post_malformed_file_409(client, controls_project):
    (controls_project / "controls.yaml").write_text("commands:\n\t- bad\n")
    resp = client.post("/api/controls", json={
        "section": "commands", "key": "notes/report", "value": "off",
    })
    assert resp.status_code == 409


@pytest.fixture
def flat_project(tmp_path, monkeypatch):
    """Minimal project for flat-shape payload tests: module 'm' with one
    command, controls.yaml with a names override, and a pinned entry."""
    from gcontext import commands as commands_mod

    (tmp_path / "gcontext.yaml").write_text("name: t\n")
    (tmp_path / "agent.md").write_text("# Agent\n")
    cmds = tmp_path / "modules" / "m" / "commands"
    cmds.mkdir(parents=True)
    (cmds / "craft.md").write_text("---\ndescription: d\n---\nbody\n")
    (tmp_path / "modules" / "m" / "index.md").write_text(
        "---\ndescription: module m help\n---\n# Module M\nSome intro.\n"
    )
    (tmp_path / "controls.yaml").write_text(
        "commands:\n  m/craft: off\nnames:\n  m/craft: craft-post\n"
        "pinned:\n  - modules/m/index.md\n"
    )
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    saved_registry = commands_mod._REGISTRY
    saved_root = commands_mod._ROOT
    saved_keys = dict(commands_mod._STABLE_KEYS)
    saved_registered = dict(commands_mod._REGISTERED)
    commands_mod._STABLE_KEYS.clear()
    commands_mod._REGISTERED.clear()
    commands_mod.load_manifest(tmp_path)
    yield tmp_path
    commands_mod._REGISTRY = saved_registry
    commands_mod._ROOT = saved_root
    commands_mod._STABLE_KEYS.clear()
    commands_mod._STABLE_KEYS.update(saved_keys)
    commands_mod._REGISTERED.clear()
    commands_mod._REGISTERED.update(saved_registered)


def test_controls_payload_flat_shape(flat_project):
    """The payload has the five expected top-level keys and each command row
    carries owner, name, default_name, custom, raw, effective, description,
    and path."""
    payload = dashboard._controls_payload(flat_project)
    assert set(payload) == {
        "commands", "resources", "structural", "pinned", "stale"}
    cmd = next(c for c in payload["commands"] if c["key"] == "m/craft")
    assert cmd["owner"] == "m"
    assert cmd["name"] == "craft_post"          # override, normalized
    assert cmd["default_name"] == "craft"
    assert cmd["custom"] is True
    assert cmd["raw"] == "off" and cmd["effective"] is False
    assert cmd["description"] == "d"
    assert cmd["path"] == "modules/m/commands/craft.md"
    fw = next(c for c in payload["commands"] if c["key"] == "framework/setup")
    assert fw["owner"] == "framework"
    assert fw["path"].startswith("gcontext/prompts/")
    assert "locked" not in fw
    res = next(r for r in payload["resources"] if r["key"] == "modules/m")
    assert res["kind"] == "modules"
    assert {"name", "default_name", "custom", "raw", "effective", "description"} <= set(res)
    assert res["default_name"] == "m"
    assert payload["pinned"] == ["modules/m/index.md"]


def test_structural_rows_match_picker(flat_project):
    """Structural rows mirror the always-listed picker entries: the agent
    root plus the modules group index (no connections here). Each row has
    key, name, description, and path; none carries a toggle state."""
    payload = dashboard._controls_payload(flat_project)
    rows = {r["key"]: r for r in payload["structural"]}
    assert set(rows) == {"root", "modules"}
    assert rows["root"]["name"] == "t"
    assert rows["root"]["path"] == "index.md"
    assert rows["root"]["description"]
    assert rows["modules"]["name"] == "modules"
    for row in rows.values():
        assert "raw" not in row and "effective" not in row


def test_structural_root_description_from_index(flat_project):
    """The root structural row takes its description from the top-level
    index.md when one exists."""
    (flat_project / "index.md").write_text(
        "---\ndescription: agent overview\n---\n# T\nbody\n")
    payload = dashboard._controls_payload(flat_project)
    root_row = next(r for r in payload["structural"] if r["key"] == "root")
    assert root_row["description"] == "agent overview"


def test_resource_description_from_frontmatter_and_fallback(flat_project):
    """Resource description prefers index.md frontmatter description, falls
    back to the first non-heading paragraph."""
    # flat_project's modules/m/index.md has frontmatter description
    payload = dashboard._controls_payload(flat_project)
    m_res = next(r for r in payload["resources"] if r["key"] == "modules/m")
    assert m_res["description"] == "module m help"

    # Now remove frontmatter, keep only body with heading + paragraph
    idx = flat_project / "modules" / "m" / "index.md"
    idx.write_text("# Module M\n\nSome intro paragraph.\n")
    payload2 = dashboard._controls_payload(flat_project)
    m_res2 = next(r for r in payload2["resources"] if r["key"] == "modules/m")
    assert m_res2["description"] == "Some intro paragraph."


@pytest.fixture
def live_project(tmp_path, monkeypatch):
    """Project with full command registration so reregister_all works.
    Module 'm' has two commands (craft, draft); controls.yaml starts clean."""
    from gcontext import commands as commands_mod

    (tmp_path / "gcontext.yaml").write_text("name: t\n")
    (tmp_path / "agent.md").write_text("# Agent\n")
    cmds = tmp_path / "modules" / "m" / "commands"
    cmds.mkdir(parents=True)
    (cmds / "craft.md").write_text("---\ndescription: d\n---\nbody\n")
    (cmds / "draft.md").write_text("---\ndescription: d2\n---\nbody\n")
    (tmp_path / "modules" / "m" / "index.md").write_text("# M\nModule intro.\n")
    (tmp_path / "controls.yaml").write_text(
        "commands:\n  m/craft: on\n  m/draft: on\n"
        "resources:\n  modules/m: on\n"
    )
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    saved_registry = commands_mod._REGISTRY
    saved_root = commands_mod._ROOT
    saved_keys = dict(commands_mod._STABLE_KEYS)
    saved_registered = dict(commands_mod._REGISTERED)
    commands_mod.load_manifest(tmp_path)
    commands_mod.reregister_all(server.mcp, tmp_path)
    server.snapshot_startup_files()
    yield tmp_path
    commands_mod._REGISTRY = saved_registry
    commands_mod._ROOT = saved_root
    commands_mod._STABLE_KEYS.clear()
    commands_mod._STABLE_KEYS.update(saved_keys)
    commands_mod._REGISTERED.clear()
    commands_mod._REGISTERED.update(saved_registered)


@pytest.fixture
def live_client(live_project):
    with TestClient(server.mcp.http_app()) as c:
        yield c


def test_post_setup_toggle_allowed(live_client, live_project):
    """POST framework/setup off returns 200 with reload and bootstrap note."""
    resp = live_client.post("/api/controls", json={
        "section": "commands", "key": "framework/setup", "value": "off",
    })
    assert resp.status_code == 200
    data = resp.json()
    setup = next(c for c in data["commands"] if c["key"] == "framework/setup")
    assert setup["raw"] == "off"
    assert "gcontext reload" in data["note"]
    assert "bootstrap" in data["note"].lower() or "setup is the bootstrap" in data["note"]


def test_post_name_command_rename(live_client, live_project):
    """POST name rename writes controls.yaml, re-registers live, returns
    the new name with custom flag, and the note mentions /mcp."""
    from gcontext import commands as commands_mod

    resp = live_client.post("/api/controls", json={
        "name": {"key": "m/craft", "value": "craft-post"},
    })
    assert resp.status_code == 200
    data = resp.json()
    text = (live_project / "controls.yaml").read_text()
    assert "m/craft: craft-post" in text
    assert "/mcp" in data["note"]
    assert "gcontext reload" not in data["note"]
    cmd = next(c for c in data["commands"] if c["key"] == "m/craft")
    assert cmd["name"] == "craft_post"
    assert cmd["custom"] is True


def test_post_name_resource_rename_live(live_client, live_project):
    """POST name rename on a resource key returns 200 with a live note."""
    resp = live_client.post("/api/controls", json={
        "name": {"key": "modules/m", "value": "My module"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "live" in data["note"].lower() or "Live" in data["note"]
    res = next(r for r in data["resources"] if r["key"] == "modules/m")
    assert res["name"] == "My module"


def test_post_name_invalid_charset_400(live_client, live_project):
    """POST name with bad charset returns 400."""
    resp = live_client.post("/api/controls", json={
        "name": {"key": "m/craft", "value": "Bad Name!"},
    })
    assert resp.status_code == 400
    assert "a-z" in resp.json()["error"] or "charset" in resp.json()["error"].lower()


def test_post_name_clear(live_client, live_project):
    """POST name with empty value clears a previous rename."""
    live_client.post("/api/controls", json={
        "name": {"key": "m/craft", "value": "craft-post"},
    })
    text = (live_project / "controls.yaml").read_text()
    assert "m/craft: craft-post" in text
    resp = live_client.post("/api/controls", json={
        "name": {"key": "m/craft", "value": ""},
    })
    assert resp.status_code == 200
    text = (live_project / "controls.yaml").read_text()
    assert "craft-post" not in text


def test_post_bulk_owner_off(live_client, live_project):
    """POST bulk off for owner 'm' turns off both commands; unknown owner 400."""
    resp = live_client.post("/api/controls", json={
        "bulk": {"owner": "m", "value": "off"},
    })
    assert resp.status_code == 200
    data = resp.json()
    text = (live_project / "controls.yaml").read_text()
    assert "m/craft: off" in text
    assert "m/draft: off" in text
    assert "gcontext reload" in data["note"]
    # unknown owner
    resp2 = live_client.post("/api/controls", json={
        "bulk": {"owner": "nope", "value": "off"},
    })
    assert resp2.status_code == 400
    assert "nope" in resp2.json()["error"]


def test_first_line_description_heading_adjacent(flat_project):
    """An index.md with a heading immediately followed by a paragraph (no blank
    line separator) still yields the paragraph text."""
    idx = flat_project / "modules" / "m" / "index.md"
    idx.write_text("# T\nIntro line.\n")
    desc = dashboard._first_line_description(flat_project, "modules/m")
    assert desc == "Intro line."


def test_catch_all_serves_spa(client, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "x.js").write_text("js")
    monkeypatch.setattr(dashboard, "_DIST_CANDIDATES", [dist])

    assert client.get("/").text == "<html>app</html>"
    assert client.get("/some/route").text == "<html>app</html>"
    assert client.get("/assets/x.js").text == "js"
    assert client.get("/api/nope").status_code == 404


def test_catch_all_without_dist(client, monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "_DIST_CANDIDATES", [tmp_path / "missing"])
    resp = client.get("/")
    assert resp.status_code == 503
    assert "not built" in resp.text
