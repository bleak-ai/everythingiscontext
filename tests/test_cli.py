from argparse import Namespace
from pathlib import Path

import pytest

from gcontext import cli


def test_serve_subcommand_routes_to_server(monkeypatch, tmp_path: Path) -> None:
    called = []

    monkeypatch.setattr(cli, "cmd_serve", lambda args: called.append(args.project))
    monkeypatch.setattr("sys.argv", ["gcontext", "serve", str(tmp_path)])

    cli.main()

    assert called == [str(tmp_path)]


def test_check_runs_sync_index_files_and_returns_its_exit_code(
    monkeypatch, tmp_path: Path
) -> None:
    completed = Namespace(returncode=7)
    calls = []

    def fake_run(command, cwd):
        calls.append((command, cwd))
        return completed

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc:
        cli.cmd_check(Namespace(project=str(tmp_path)))

    assert exc.value.code == 7
    assert calls == [
        (
            ["uv", "run", "context/system/scripts/sync-index-files.py", "--check"],
            tmp_path.resolve(),
        )
    ]


def test_init_subcommand_routes_to_init(monkeypatch, tmp_path: Path) -> None:
    called = []

    def fake_run_init(target_dir):
        called.append(str(target_dir))
        return 0

    from gcontext import init as init_mod
    monkeypatch.setattr(init_mod, "run_init", fake_run_init)
    monkeypatch.setattr("sys.argv", ["gcontext", "init", str(tmp_path)])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 0
    assert called == [str(tmp_path.resolve())]
