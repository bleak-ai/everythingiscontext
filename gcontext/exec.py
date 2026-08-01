"""Script execution: saved scripts by path (run_script) and ad-hoc agent
code (run_adhoc_script), in the project venv.

The venv lives at <project>/.venv and syncs the deps declared across all
connection.yaml files on every run (uv makes the satisfied case near-instant).
Secrets are injected as env vars and scrubbed from the output. Both paths
share _run, so cwd, env, timeout, capping and scrubbing behave identically.
Results are structured dicts (stdout, stderr, exit_code, timed_out,
truncated, duration_ms, plus hint on a missing import); argument problems
raise ValueError, which the MCP layer surfaces as a tool error.
"""

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import secrets as secrets_mod
from . import state

SCRIPT_TIMEOUT = 60
MAX_OUTPUT = 100_000  # chars per stream; beyond this the stream is capped


def venv_dir(root: Path) -> Path:
    return root.resolve() / ".venv"


def venv_python(root: Path) -> Path:
    venv = venv_dir(root)
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def collect_deps(root: Path) -> set[str]:
    all_deps = set()
    for conn in state.load_connections(root).values():
        all_deps.update(conn.deps)
    return all_deps


def ensure_venv(root: Path) -> None:
    """Create the project venv if missing and sync connection deps into it."""
    if not venv_dir(root).is_dir():
        subprocess.run(
            ["uv", "venv", str(venv_dir(root)), "--quiet"],
            check=True,
            cwd=str(root),
        )

    all_deps = collect_deps(root)
    if all_deps:
        subprocess.run(
            ["uv", "pip", "install", "--quiet", "--python", str(venv_python(root))]
            + sorted(all_deps),
            check=True,
            cwd=str(root),
        )


_MISSING_MODULE_RE = re.compile(
    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)


def missing_module_hint(root: Path, stderr: str) -> str | None:
    """A hint shown only when a run fails on a missing import."""
    match = _MISSING_MODULE_RE.search(stderr)
    if not match:
        return None
    module = match.group(1).split(".")[0]
    declared = sorted(collect_deps(root))
    declared_line = f" Currently declared: {', '.join(declared)}." if declared else ""
    return (
        f"Package '{module}' is not installed in the project venv. Declare it "
        f"under deps: in the relevant connection.yaml (ask the user, that file "
        f"is human-edited), then rerun: the venv syncs on the next call."
        f"{declared_line} Note the pip name can differ from the import name."
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
) -> dict:
    secrets = secrets_mod.load(root)
    ensure_venv(root)

    env = os.environ.copy()
    env.update(secrets)
    for k, v in (params or {}).items():
        env[f"PARAM_{k.upper()}"] = str(v)

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(venv_python(root)), script_path, *(args or [])],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=env,
            cwd=str(root),
        )
        stdout, stderr = proc.stdout, proc.stderr
        exit_code, timed_out = proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\n[timed out after {SCRIPT_TIMEOUT}s]"
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
) -> dict:
    if not path:
        raise ValueError("path is required")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path {path} is outside the project directory")
    if not target.is_file():
        raise ValueError(f"{path} is not a file")
    return _run(root, str(target), args, params)


def run_adhoc_script(
    root: Path,
    code: str,
    params: dict[str, str] | None = None,
) -> dict:
    if not code:
        raise ValueError("code is required")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=root
    ) as f:
        f.write(code)
    try:
        return _run(root, f.name, None, params)
    finally:
        Path(f.name).unlink(missing_ok=True)
