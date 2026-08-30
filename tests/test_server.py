import pytest

from gcontext import ledger, server, state
from gcontext.secrets import load, scrub


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


def test_load_strips_surrounding_quotes(tmp_path):
    (tmp_path / "secrets.env").write_text(
        'A=plain\nB="double quoted"\nC=\'single quoted\'\nD="unbalanced\n'
    )
    pairs = load(tmp_path)
    assert pairs["A"] == "plain"
    assert pairs["B"] == "double quoted"
    assert pairs["C"] == "single quoted"
    assert pairs["D"] == '"unbalanced'


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


def test_write_then_read_roundtrip(project):
    server.write_file("modules/notes/index.md", "hello")
    assert server.read_file("modules/notes/index.md") == "hello"


def test_index_write_warns_about_unreferenced_siblings(project):
    notes = project / "modules" / "notes"
    notes.mkdir(parents=True)
    (notes / "decisions.md").write_text("log")
    (notes / "playbooks").mkdir()
    out = server.write_file("modules/notes/index.md", "summary only")
    assert "Warning" in out
    assert "decisions.md" in out
    assert "playbooks" in out
    out = server.write_file(
        "modules/notes/index.md",
        "# Notes\n\nNotes module summary.\n\n"
        "- [decisions.md](decisions.md): log\n- playbooks/: procedures\n",
    )
    assert "Warning" not in out


def test_index_check_ignores_machine_and_exempt_entries(project):
    notes = project / "modules" / "notes"
    (notes / "archive").mkdir(parents=True)
    (notes / "__pycache__").mkdir()
    (notes / "secrets.env").write_text("X=1")
    out = server.write_file("modules/notes/index.md", "# Notes\n\nNothing linked here.\n")
    assert "Warning" not in out


def test_new_file_warns_when_parent_index_misses_it(project):
    notes = project / "modules" / "notes"
    notes.mkdir(parents=True)
    (notes / "index.md").write_text("Summary, no links.")
    out = server.write_file("modules/notes/decisions.md", "log")
    assert "Warning" in out
    assert "modules/notes/index.md" in out
    # Overwriting an existing file does not re-warn.
    out = server.write_file("modules/notes/decisions.md", "log v2")
    assert "Warning" not in out
    # A file the index already mentions is fine.
    (notes / "index.md").write_text("Summary.\n- notes.md: things\n")
    out = server.write_file("modules/notes/notes.md", "things")
    assert "Warning" not in out


def test_new_file_without_parent_index_does_not_warn(project):
    out = server.write_file("modules/fresh/first.md", "hi")
    assert "Warning" not in out


def test_agent_md_write_notes_restart(project):
    out = server.write_file("agent.md", "# Agent\nbe useful\n")
    assert "Note: agent.md is pushed at connect" in out
    assert "restart" in out
    assert "Warning" not in out  # agent.md stays exempt from the index check


def test_command_write_notes_restart(project):
    out = server.write_file(
        "connections/gmail/commands/send.md", "---\ndescription: d\n---\nbody\n"
    )
    assert "Note: commands are registered at server start" in out
    out = server.write_file(
        "modules/notes/commands/report.py", "# ---\n# description: d\n# ---\n"
    )
    assert "Note: commands are registered at server start" in out
    # Not a command file: wrong folder or wrong extension.
    assert "Note:" not in server.write_file("modules/notes/scripts/report.py", "x")
    assert "Note:" not in server.write_file("modules/notes/commands/notes.txt", "x")


def test_ordinary_write_has_no_restart_note(project):
    out = server.write_file("modules/notes/index.md", "summary")
    assert "Note:" not in out


def test_write_new_file_reports_size_and_lines(project):
    out = server.write_file("modules/notes/note.md", "one\ntwo\n")
    assert out.startswith("Created: modules/notes/note.md")
    assert "2 lines" in out
    assert "---" not in out  # no diff for a new file


def test_write_update_returns_unified_diff(project):
    server.write_file("modules/notes/note.md", "one\ntwo\n")
    out = server.write_file("modules/notes/note.md", "one\nthree\n")
    assert out.startswith("Updated: modules/notes/note.md")
    assert "-two" in out
    assert "+three" in out
    assert "a/modules/notes/note.md" in out


def test_write_identical_content_reports_unchanged(project):
    server.write_file("modules/notes/note.md", "same\n")
    out = server.write_file("modules/notes/note.md", "same\n")
    assert out.startswith("Unchanged: modules/notes/note.md")
    assert "+same" not in out


def test_write_diff_is_capped(project):
    from gcontext import fs

    before = "\n".join(f"line {i}" for i in range(400)) + "\n"
    after = "\n".join(f"LINE {i}" for i in range(400)) + "\n"
    server.write_file("modules/notes/big.md", before)
    out = server.write_file("modules/notes/big.md", after)
    assert f"diff truncated at {fs.DIFF_MAX_LINES} lines" in out
    assert len(out.splitlines()) <= fs.DIFF_MAX_LINES + 5


def test_list_dir_lists_entries_and_blocks_traversal(project):
    (project / "modules" / "notes").mkdir(parents=True)
    (project / "modules" / "notes" / "index.md").write_text("x")
    out = server.list_dir("modules")
    assert "notes/" in out
    out = server.list_dir("modules/notes")
    assert "index.md" in out
    assert "outside the project" in server.list_dir("..")


def test_list_dir_hides_machine_folders(project):
    (project / ".git").mkdir()
    (project / "kept.md").write_text("x")
    out = server.list_dir(".")
    assert ".git" not in out
    assert "kept.md" in out


def test_grep_finds_lines_and_respects_glob(project):
    (project / "modules" / "m").mkdir(parents=True)
    (project / "modules" / "m" / "index.md").write_text("refund policy\nother\n")
    (project / "modules" / "m" / "notes.txt").write_text("refund notes\n")
    out = server.grep("refund")
    assert "modules/m/index.md:1: refund policy" in out
    assert "notes.txt" in out
    out = server.grep("refund", glob="*.md")
    assert "index.md" in out
    assert "notes.txt" not in out


def test_grep_never_reads_secrets_env(project):
    (project / "secrets.env").write_text("API_KEY=sk-verysecret\n")
    out = server.grep("verysecret")
    assert "sk-verysecret" not in out
    assert "No matches" in out


def test_grep_invalid_regex(project):
    assert "invalid regex" in server.grep("[unclosed")


def test_removed_tools_are_gone():
    assert not hasattr(server, "list_connections")
    assert not hasattr(server, "overview")


def test_archive_not_scanned_but_reported(project):
    (project / "modules" / "active").mkdir(parents=True)
    (project / "modules" / "active" / "index.md").write_text("x")
    (project / "archive" / "modules" / "old").mkdir(parents=True)
    (project / "archive" / "modules" / "old" / "index.md").write_text("x")

    modules = state.discover_modules(project)
    assert "active" in modules and "old" not in modules

    assert state.archived(project) == {"modules": ["old"]}
    assert "archive/" in server.list_dir(".")


def test_archive_readable_by_path(project):
    (project / "archive").mkdir()
    (project / "archive" / "note.md").write_text("kept")
    assert server.read_file("archive/note.md") == "kept"


def test_run_adhoc_script_returns_readable_text(project):
    out = server.run_adhoc_script(code="print('hi')")
    assert out.startswith("[exit 0 | ")
    assert out.endswith(" ms]\nhi")


def test_exec_dict_has_all_fields(project):
    from gcontext import exec as exec_mod

    out = exec_mod.run_adhoc_script(project, "print('hi')")
    assert out["stdout"] == "hi\n"
    assert out["stderr"] == ""
    assert out["exit_code"] == 0
    assert out["timed_out"] is False
    assert out["truncated"] is False
    assert out["duration_ms"] >= 0
    assert "hint" not in out


def test_run_adhoc_script_params(project):
    out = server.run_adhoc_script(
        code="import os\nprint(os.environ['PARAM_EMAIL'])", params={"email": "x@y.z"}
    )
    assert out.startswith("[exit 0 | ")
    assert "x@y.z" in out


def test_run_script_path_mode_with_args_and_params(project):
    script = project / "modules" / "m" / "scripts" / "s.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import os, sys\nprint(sys.argv[1], os.environ['PARAM_EMAIL'])\n"
    )
    out = server.run_script(
        path="modules/m/scripts/s.py", args=["a1"], params={"email": "x@y.z"}
    )
    assert out.startswith("[exit 0 | ")
    assert "a1 x@y.z" in out


def test_run_script_rejects_bad_paths(project):
    with pytest.raises(ValueError, match="outside the project"):
        server.run_script(path="../evil.py")
    with pytest.raises(ValueError, match="not a file"):
        server.run_script(path="missing.py")


def test_run_adhoc_script_missing_module_hint(project):
    (project / "connections" / "c").mkdir(parents=True)
    (project / "connections" / "c" / "connection.yaml").write_text(
        "name: c\ndeps: [pyyaml]\n"
    )
    out = server.run_adhoc_script(code="import definitely_not_a_module")
    assert not out.startswith("[exit 0 | ")
    assert "[hint]" in out
    assert "definitely_not_a_module" in out
    assert "connection.yaml" in out


def test_run_adhoc_script_scrubs_secrets(project):
    (project / "secrets.env").write_text("API_KEY=sk-verysecret\n")
    out = server.run_adhoc_script(code="import os\nprint(os.environ['API_KEY'])")
    assert "sk-verysecret" not in out
    assert "***" in out


def test_run_adhoc_script_truncates_long_output(project, monkeypatch):
    from gcontext import exec as exec_mod

    monkeypatch.setattr(exec_mod, "MAX_OUTPUT", 50)
    out = server.run_adhoc_script(code="print('x' * 200)")
    assert "| truncated]" in out
    assert "[truncated," in out


def test_run_adhoc_script_timeout(project, monkeypatch):
    from gcontext import exec as exec_mod

    monkeypatch.setattr(exec_mod, "SCRIPT_TIMEOUT", 1)
    out = server.run_adhoc_script(code="import time\ntime.sleep(5)")
    assert "| timed out]" in out
    assert out.startswith("[exit -1 | ")
    assert "timed out after 1s" in out


def test_instructions_pushed_in_handshake(project):
    (project / "agent.md").write_text("line one\nline two\n")
    n_base, n_project = server.load_instructions()
    assert n_base > 0
    assert n_project == 2

    import asyncio

    from fastmcp import Client

    async def go():
        async with Client(server.mcp) as c:
            return c.initialize_result.instructions

    pushed = asyncio.run(go())
    assert pushed.startswith("# gcontext")
    assert pushed.endswith("line one\nline two\n")

    pipes = {p["id"]: p for p in ledger.build(project)}
    assert pipes["G0"]["status"] == "loaded"
    assert "framework-owned" in pipes["G0"]["detail"]
    assert pipes["G1"]["status"] == "loaded"
    assert "pushed at connect" in pipes["G1"]["detail"]


def test_no_instructions_file_pushes_only_base(project):
    n_base, n_project = server.load_instructions()
    assert n_base > 0
    assert n_project == 0
    assert server.mcp.instructions.startswith("# gcontext")
    pipes = {p["id"]: p for p in ledger.build(project)}
    assert pipes["G0"]["status"] == "loaded"
    assert pipes["G1"]["status"] == "skipped"


def test_state_files_are_resources(project):
    (project / "modules" / "m").mkdir(parents=True)
    (project / "modules" / "m" / "index.md").write_text("topic notes")
    (project / "secrets.env").write_text("API_KEY=sk-verysecret\n")
    (project / "archive").mkdir()
    (project / "archive" / "old.md").write_text("kept")

    import asyncio

    from fastmcp import Client

    async def go():
        async with Client(server.mcp) as c:
            listed = [str(r.uri) for r in await c.list_resources()]
            file = await c.read_resource("gcontext://modules/m/index.md")
            folder = await c.read_resource("gcontext://modules/m/")
            archived = await c.read_resource("gcontext://archive/old.md")
            blocked = await c.read_resource("gcontext://secrets.env")
            return listed, file[0].text, folder[0].text, archived[0].text, blocked[0].text

    listed, file_text, folder_text, archived_text, blocked_text = asyncio.run(go())
    assert any(u.startswith("agent://") and u.endswith("/modules/m") for u in listed)
    assert any(u.startswith("agent://") and "modules" not in u and "connections" not in u for u in listed)
    assert not any("secrets.env" in u for u in listed)
    assert not any(u.startswith("gcontext://archive/") for u in listed)
    assert file_text == "topic notes"
    assert "index.md" in folder_text
    assert archived_text == "kept"
    assert "Error" in blocked_text and "sk-verysecret" not in blocked_text


def test_ledger_has_resources_pipe(project):
    (project / "modules" / "m").mkdir(parents=True)
    (project / "modules" / "m" / "index.md").write_text("x")
    pipes = {p["id"]: p for p in ledger.build(project)}
    assert pipes["G7"]["status"] == "on demand"
    assert "gcontext://" in pipes["G7"]["detail"]


def test_ledger_has_no_flow_pipe(project):
    ids = [p["id"] for p in ledger.build(project)]
    assert "G6" in ids  # commands pipe
    assert not any("flow" in p["label"] for p in ledger.build(project))


def test_run_adhoc_script_accepts_timeout(project):
    out = server.run_adhoc_script(code="print('ok')", timeout=30)
    assert "ok" in out


def test_run_script_accepts_timeout(project):
    script = project / "s.py"
    script.write_text("print('ok')\n")
    out = server.run_script(path="s.py", timeout=30)
    assert "ok" in out
