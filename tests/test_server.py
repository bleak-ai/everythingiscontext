import pytest

from gcontext import ledger, server, state
from gcontext.secrets import scrub


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "gcontext.yaml").write_text("name: t\n")
    monkeypatch.setattr(server, "PROJECT_DIR", tmp_path)
    return tmp_path


def test_scrub_output():
    secrets = {"API_KEY": "sk-verysecret", "SHORT": "ab"}
    out = scrub("token sk-verysecret used, ab kept", secrets)
    assert "sk-verysecret" not in out
    assert "***" in out
    assert "ab kept" in out  # values of length <= 3 are not scrubbed


def test_read_file_blocks_traversal(project):
    assert "outside the project" in server.read_file("../gcontext.yaml")
    assert "outside the project" in server.read_file("/etc/hosts")


def test_read_file_refuses_secrets_env(project):
    (project / "secrets.env").write_text("API_KEY=sk-verysecret\n")
    result = server.read_file("secrets.env")
    assert "Error" in result
    assert "sk-verysecret" not in result


def test_write_file_blocks_traversal_and_protected_files(project):
    assert "outside the project" in server.write_file("../x.md", "hi")
    assert "Error" in server.write_file("secrets.env", "STOLEN=1")
    assert "Error" in server.write_file("connections/a/connection.yaml", "nope")


def test_write_then_read_roundtrip(project):
    server.write_file("modules/notes/index.md", "hello")
    assert server.read_file("modules/notes/index.md") == "hello"


def test_archive_not_scanned_but_reported(project):
    (project / "modules" / "active").mkdir(parents=True)
    (project / "modules" / "active" / "index.md").write_text("x")
    (project / "archive" / "modules" / "old").mkdir(parents=True)
    (project / "archive" / "modules" / "old" / "index.md").write_text("x")

    modules = state.discover_modules(project)
    assert "active" in modules and "old" not in modules

    assert state.archived(project) == {"modules": ["old"]}
    overview = server.overview()
    assert "## Archive" in overview
    assert "old" in overview


def test_archive_readable_by_path(project):
    (project / "archive").mkdir()
    (project / "archive" / "note.md").write_text("kept")
    assert server.read_file("archive/note.md") == "kept"


def test_run_script_requires_exactly_one_mode(project):
    assert "exactly one" in server.run_script()
    assert "exactly one" in server.run_script(code="print(1)", path="x.py")


def test_run_script_code_mode_header(project):
    out = server.run_script(code="print('hi')")
    assert out.splitlines()[0].startswith("[code | exit 0 | ")
    assert "hi" in out


def test_run_script_path_mode_with_args_and_params(project):
    script = project / "modules" / "m" / "scripts" / "s.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import os, sys\nprint(sys.argv[1], os.environ['PARAM_EMAIL'])\n"
    )
    out = server.run_script(
        path="modules/m/scripts/s.py", args=["a1"], params={"email": "x@y.z"}
    )
    assert out.splitlines()[0].startswith("[modules/m/scripts/s.py | exit 0 | ")
    assert "a1 x@y.z" in out


def test_run_script_path_blocks_traversal(project):
    assert "outside the project" in server.run_script(path="../evil.py")


def test_run_script_missing_module_hint(project):
    (project / "connections" / "c").mkdir(parents=True)
    (project / "connections" / "c" / "connection.yaml").write_text(
        "name: c\ndeps: [pyyaml]\n"
    )
    out = server.run_script(code="import definitely_not_a_module")
    assert "[hint]" in out
    assert "definitely_not_a_module" in out
    assert "connection.yaml" in out


def test_instructions_pushed_in_handshake(project):
    (project / "instructions.md").write_text("line one\nline two\n")
    assert server.load_instructions() == 2

    import asyncio

    from fastmcp import Client

    async def go():
        async with Client(server.mcp) as c:
            return c.initialize_result.instructions

    assert asyncio.run(go()) == "line one\nline two\n"

    g0 = [p for p in ledger.build(project) if p["id"] == "G0"]
    assert g0[0]["status"] == "loaded"
    assert "pushed at connect" in g0[0]["detail"]


def test_no_instructions_file_pushes_nothing(project):
    assert server.load_instructions() == 0
    assert server.mcp.instructions is None
    g0 = [p for p in ledger.build(project) if p["id"] == "G0"]
    assert g0[0]["status"] == "skipped"


def test_ledger_has_no_flow_pipe(project):
    ids = [p["id"] for p in ledger.build(project)]
    assert "G6" in ids  # commands pipe
    assert not any("flow" in p["label"] for p in ledger.build(project))
