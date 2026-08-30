"""Script execution: saved scripts by path (run_script) and ad-hoc agent
code (run_adhoc_script), in the project venv.

The venv lives at <project>/.venv.
Secrets are injected as env vars and scrubbed from the output. Both paths
share _run, so cwd, env, timeout, capping and scrubbing behave identically.
Results are structured dicts (stdout, stderr, exit_code, timed_out,
truncated, duration_ms, plus hint on a missing import); argument problems
raise ValueError, which the MCP layer surfaces as a tool error.
"""

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import secrets as secrets_mod

SCRIPT_TIMEOUT = 60
MAX_TIMEOUT = 600
MAX_OUTPUT = 100_000  # chars per stream; beyond this the stream is capped


def venv_dir(root: Path) -> Path:
    return root.resolve() / ".venv"


def venv_python(root: Path) -> Path:
    venv = venv_dir(root)
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


class VenvSyncBusy(Exception):
    pass


LOCK_STALE_SECONDS = 600


def _sync_lock(root: Path) -> Path:
    return root.resolve() / ".venv-sync.lock"


def _acquire_sync_lock(root: Path) -> Path:
    """Take the exclusive sync lock, or raise VenvSyncBusy.

    A lock older than LOCK_STALE_SECONDS is from a dead sync: remove it and
    retry the acquire once.
    """
    lock = _sync_lock(root)
    for attempt in (0, 1):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # the lock vanished between open and stat; retry
            if attempt == 0 and age > LOCK_STALE_SECONDS:
                lock.unlink(missing_ok=True)
                continue
            raise VenvSyncBusy("venv sync already in progress")
    raise VenvSyncBusy("venv sync already in progress")


def deps_marker(root: Path) -> Path:
    return venv_dir(root) / "gcontext-deps.txt"


def ensure_venv(root: Path) -> None:
    """Create the project venv if it is missing."""
    wanted = ""
    marker = deps_marker(root)
    if venv_dir(root).is_dir() and marker.exists() and marker.read_text() == wanted:
        return

    lock = _acquire_sync_lock(root)
    try:
        if not venv_dir(root).is_dir():
            subprocess.run(
                ["uv", "venv", str(venv_dir(root)), "--quiet"],
                check=True,
                cwd=str(root),
            )
        # Written only after a successful sync: a failed sync leaves the old
        # marker (or none), so the next call retries.
        marker.write_text(wanted)
    finally:
        lock.unlink(missing_ok=True)


_MISSING_MODULE_RE = re.compile(
    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)


def missing_module_hint(root: Path, stderr: str) -> str | None:
    """A hint shown only when a run fails on a missing import."""
    match = _MISSING_MODULE_RE.search(stderr)
    if not match:
        return None
    module = match.group(1).split(".")[0]
    return (
        f"Package '{module}' is not installed in the project environment. "
        "Add it to the project dependencies, then sync the environment. "
        "The package name can differ from the import name."
    )


def _cap(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT:
        return text, False
    dropped = len(text) - MAX_OUTPUT
    return text[:MAX_OUTPUT] + f"\n[truncated, {dropped} more chars]", True


def _run(
    root: Path,
    script_path: str,
    args: list[str] | None,
    params: dict[str, str] | None,
    timeout: int | None = None,
) -> dict:
    if timeout is not None and (timeout < 1 or timeout > MAX_TIMEOUT):
        raise ValueError(f"timeout must be between 1 and {MAX_TIMEOUT} seconds")
    timeout = timeout or SCRIPT_TIMEOUT

    secrets = secrets_mod.load(root)
    try:
        ensure_venv(root)
    except VenvSyncBusy:
        return {
            "stdout": "",
            "stderr": "venv sync already in progress (another exec call is "
                      "installing deps); retry in a few seconds",
            "exit_code": -1,
            "timed_out": False,
            "truncated": False,
            "duration_ms": 0,
        }

    env = os.environ.copy()
    env.update(secrets)
    for k, v in (params or {}).items():
        env[f"PARAM_{k.upper()}"] = str(v)

    start = time.perf_counter()
    # start_new_session puts the script in its own process group, so a
    # timeout kill reaches grandchildren (spawned browsers) too. On Windows
    # there is no process group here: proc.kill() only kills the direct
    # child. Known limit.
    proc = subprocess.Popen(
        [str(venv_python(root)), script_path, *(args or [])],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(root),
        start_new_session=(sys.platform != "win32"),
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        exit_code, timed_out = proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        if sys.platform != "win32":
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
        else:
            proc.kill()
        out_rest, err_rest = proc.communicate()
        stdout = (exc.stdout or "") + (out_rest or "")
        stderr = (exc.stderr or "") + (err_rest or "") + f"\n[timed out after {timeout}s]"
        exit_code, timed_out = -1, True
    duration_ms = round((time.perf_counter() - start) * 1000)

    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    out, out_truncated = _cap(secrets_mod.scrub(stdout, secrets))
    err, err_truncated = _cap(secrets_mod.scrub(stderr, secrets))

    result = {
        "stdout": out,
        "stderr": err,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "truncated": out_truncated or err_truncated,
        "duration_ms": duration_ms,
    }
    hint = missing_module_hint(root, err)
    if hint:
        result["hint"] = hint
    return result


def run_script(
    root: Path,
    path: str,
    args: list[str] | None = None,
    params: dict[str, str] | None = None,
    timeout: int | None = None,
) -> dict:
    if not path:
        raise ValueError("path is required")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path {path} is outside the project directory")
    if not target.is_file():
        raise ValueError(f"{path} is not a file")
    if target.name == "secrets.env":
        return {
            "stdout": "",
            "stderr": "Error: cannot execute secrets.env",
            "exit_code": -1,
            "timed_out": False,
            "truncated": False,
            "duration_ms": 0,
        }
    return _run(root, str(target), args, params, timeout=timeout)


def run_adhoc_script(
    root: Path,
    code: str,
    params: dict[str, str] | None = None,
    timeout: int | None = None,
) -> dict:
    if not code:
        raise ValueError("code is required")
    try:
        ensure_venv(root)
    except VenvSyncBusy:
        return {
            "stdout": "",
            "stderr": "venv sync already in progress (another exec call is "
                      "installing deps); retry in a few seconds",
            "exit_code": -1,
            "timed_out": False,
            "truncated": False,
            "duration_ms": 0,
        }
    tmp_dir = venv_dir(root)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=tmp_dir
    ) as f:
        f.write(code)
    try:
        return _run(root, f.name, None, params, timeout=timeout)
    finally:
        Path(f.name).unlink(missing_ok=True)
