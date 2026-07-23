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
        "connections/httpbin/connection.yaml",
        "flows/demo-brief/flow.yaml",
    ]:
        assert (agent / rel).is_file(), rel
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
    result = run_cli("flows", "a", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "demo-brief" in result.stdout
    assert "capture" in result.stdout
