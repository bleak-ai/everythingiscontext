import os
import subprocess
import sys


def run_cli(*args, cwd, env_extra=None):
    # Point telemetry at an unreachable local port so tests never hit the network.
    env = {**os.environ, "GCONTEXT_API": "http://127.0.0.1:9", **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def test_init_scaffolds_agent(tmp_path):
    result = run_cli("init", "my-agent", cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    agent = tmp_path / "my-agent"
    for rel in [
        "agent.md",
        "secrets.env",
        ".gitignore",
    ]:
        assert (agent / rel).is_file(), rel
    assert not (agent / "gcontext.yaml").exists()
    assert (agent / "connections").is_dir()
    assert not any((agent / "connections").glob("*/connection.yaml"))
    assert "secrets.env" in (agent / ".gitignore").read_text()


def test_init_prints_telemetry_notice(tmp_path):
    result = run_cli("init", "my-agent", cwd=tmp_path)
    assert result.returncode == 0
    assert "GCONTEXT_TELEMETRY=0" in result.stdout


def test_init_no_telemetry_notice_when_disabled(tmp_path):
    result = run_cli("init", "my-agent", cwd=tmp_path, env_extra={"GCONTEXT_TELEMETRY": "0"})
    assert result.returncode == 0
    assert "anonymous install event" not in result.stdout


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
    assert "agent.md" in result.stdout
    assert "commands" in result.stdout


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
