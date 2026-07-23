import pytest

from gcontext import server


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: t\n")
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    return tmp_path


def test_scrub_output():
    secrets = {"API_KEY": "sk-verysecret", "SHORT": "ab"}
    out = server._scrub_output("token sk-verysecret used, ab kept", secrets)
    assert "sk-verysecret" not in out
    assert "***" in out
    assert "ab kept" in out  # values of length <= 3 are not scrubbed


def test_read_context_blocks_traversal(project):
    assert "outside the project" in server.read_context("../gcontext.yaml")
    assert "outside the project" in server.read_context("/etc/hosts")


def test_write_context_blocks_traversal_and_protected_files(project):
    assert "outside the project" in server.write_context("../x.md", "hi")
    assert "Error" in server.write_context("secrets.env", "STOLEN=1")
    assert "Error" in server.write_context("connections/a/connection.yaml", "nope")


def test_write_then_read_roundtrip(project):
    server.write_context("modules/notes/index.md", "hello")
    assert server.read_context("modules/notes/index.md") == "hello"


def test_archive_not_scanned_but_reported(project):
    (project / "modules" / "active").mkdir(parents=True)
    (project / "modules" / "active" / "index.md").write_text("x")
    (project / "archive" / "modules" / "old").mkdir(parents=True)
    (project / "archive" / "modules" / "old" / "index.md").write_text("x")

    modules = server._discover_modules()
    assert "active" in modules and "old" not in modules

    assert server._archived() == {"modules": ["old"]}
    overview = server.overview()
    assert "## Archive" in overview
    assert "old" in overview


def test_archive_readable_by_path(project):
    (project / "archive").mkdir()
    (project / "archive" / "note.md").write_text("kept")
    assert server.read_context("archive/note.md") == "kept"


def test_flows_tool_and_ledger(project):
    d = project / "flows" / "f"
    d.mkdir(parents=True)
    (d / "flow.yaml").write_text(
        "name: f\nsteps:\n  - id: s\n    produces: [flows/f/out.md]\n    instructions: write it\n"
    )
    out = server.flows()
    assert "[ready] s" in out
    assert "write it" in out  # actionable steps expose instructions

    g6 = [p for p in server.build_ledger("mcp") if p["id"] == "G6"]
    assert g6 and "1 flow(s)" in g6[0]["detail"]
