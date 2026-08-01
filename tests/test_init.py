import subprocess
import sys


def run_cli(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_init_scaffolds_agent(tmp_path):
    result = run_cli("init", "my-agent", cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    agent = tmp_path / "my-agent"
    for rel in [
        "gcontext.yaml",
        "instructions.md",
        "secrets.env",
        ".gitignore",
    ]:
        assert (agent / rel).is_file(), rel
    assert (agent / "connections").is_dir()
    assert not any((agent / "connections").glob("*/connection.yaml"))
    assert "name: my-agent" in (agent / "gcontext.yaml").read_text()
    assert "secrets.env" in (agent / ".gitignore").read_text()


def test_init_refuses_non_empty_dir(tmp_path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "x").write_text("x")
    result = run_cli("init", "taken", cwd=tmp_path)
    assert result.returncode == 1
    assert "not empty" in result.stderr


def test_scaffolded_agent_works_with_cli(tmp_path):
    run_cli("init", "a", cwd=tmp_path)
    result = run_cli("context", "a", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "instructions.md" in result.stdout
    assert "commands" in result.stdout


def test_persist_port_replaces_commented_template_line(tmp_path):
    from gcontext.cli import persist_port

    yaml_file = tmp_path / "gcontext.yaml"
    yaml_file.write_text("name: a\ndescription: d\n# port: 4242\n")
    persist_port(tmp_path, 4243)
    text = yaml_file.read_text()
    assert "port: 4243\n" in text
    assert "# port:" not in text
    assert "name: a" in text


def test_persist_port_updates_existing_and_appends_when_missing(tmp_path):
    from gcontext.cli import persist_port

    yaml_file = tmp_path / "gcontext.yaml"
    yaml_file.write_text("name: a\nport: 4243\n")
    persist_port(tmp_path, 5000)
    assert yaml_file.read_text() == "name: a\nport: 5000\n"

    yaml_file.write_text("name: a\n")
    persist_port(tmp_path, 4244)
    assert yaml_file.read_text() == "name: a\nport: 4244\n"


def test_find_free_port_skips_taken_port():
    import socket

    from gcontext.cli import find_free_port, port_is_free

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        taken = s.getsockname()[1]
        assert not port_is_free(taken)
        chosen = find_free_port(taken)
        assert chosen > taken
        assert port_is_free(chosen)
