"""Tests for exec.py: dep marker cache, sync lock, timeout, process kill."""

import os
import subprocess
import time

import pytest

from gcontext import exec as exec_mod


@pytest.fixture
def root(tmp_path):
    return tmp_path


# --- Dep marker cache ---

def test_first_sync_writes_empty_marker(root):
    exec_mod.ensure_venv(root)
    assert exec_mod.deps_marker(root).read_text() == ""


def test_second_ensure_venv_runs_no_uv(root, monkeypatch):
    exec_mod.ensure_venv(root)
    calls = []
    monkeypatch.setattr(
        exec_mod.subprocess, "run", lambda *a, **k: calls.append(a)
    )
    exec_mod.ensure_venv(root)
    assert calls == []


# --- Sync lock ---

def test_fresh_lock_returns_busy_result(root):
    exec_mod._sync_lock(root).write_text("123")
    result = exec_mod.run_adhoc_script(root, "print(1)")
    assert result["exit_code"] == -1
    assert result["timed_out"] is False
    assert "venv sync already in progress" in result["stderr"]


def test_stale_lock_is_removed_and_sync_proceeds(root):
    lock = exec_mod._sync_lock(root)
    lock.write_text("123")
    old = time.time() - 700
    os.utime(lock, (old, old))
    exec_mod.ensure_venv(root)
    assert not lock.exists()
    assert exec_mod.deps_marker(root).exists()


def test_lock_released_after_sync(root):
    exec_mod.ensure_venv(root)
    assert not exec_mod._sync_lock(root).exists()


def test_lock_released_after_failed_sync(root, monkeypatch):
    def failing_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(exec_mod.subprocess, "run", failing_run)
    with pytest.raises(subprocess.CalledProcessError):
        exec_mod.ensure_venv(root)
    assert not exec_mod._sync_lock(root).exists()


def test_fast_path_ignores_lock(root):
    exec_mod.ensure_venv(root)
    exec_mod._sync_lock(root).write_text("123")
    exec_mod.ensure_venv(root)  # marker matches: no VenvSyncBusy


# --- Timeout ---

def test_timeout_out_of_range_raises(root):
    with pytest.raises(ValueError, match="timeout must be between 1 and 600"):
        exec_mod.run_adhoc_script(root, "print(1)", timeout=601)
    with pytest.raises(ValueError, match="timeout must be between 1 and 600"):
        exec_mod.run_adhoc_script(root, "print(1)", timeout=0)


def test_custom_timeout_kills_and_reports(root):
    result = exec_mod.run_adhoc_script(
        root, "import time; time.sleep(5)", timeout=1
    )
    assert result["timed_out"] is True
    assert result["exit_code"] == -1
    assert "[timed out after 1s]" in result["stderr"]


def test_timeout_kills_grandchildren(root):
    code = (
        "import pathlib, subprocess, time\n"
        "p = subprocess.Popen(['sleep', '100'])\n"
        "pathlib.Path('child.pid').write_text(str(p.pid))\n"
        "time.sleep(30)\n"
    )
    result = exec_mod.run_adhoc_script(root, code, timeout=2)
    assert result["timed_out"] is True
    pid = int((root / "child.pid").read_text())
    deadline = time.time() + 5
    alive = True
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
            break
        time.sleep(0.2)
    assert not alive


def test_default_timeout_unchanged(root):
    result = exec_mod.run_adhoc_script(root, "print('ok')")
    assert result["exit_code"] == 0
    assert "ok" in result["stdout"]
