import asyncio
import json

import pytest
from starlette.testclient import TestClient

from gcontext import dashboard, server


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: t\ndescription: test agent\n")
    (tmp_path / "instructions.md").write_text("# Instructions\nbe useful\n")
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
