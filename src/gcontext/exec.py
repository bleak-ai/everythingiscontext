"""Script execution: ad-hoc agent code and saved scripts, in the project venv.

The venv lives at <project>/.venv and syncs the deps declared across all
connection.yaml files on every run (uv makes the satisfied case near-instant).
Secrets are injected as env vars and scrubbed from the output; results are
plain text starting with a status line the agent and the user can both read.
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


def run(
    root: Path,
    code: str = "",
    path: str = "",
    args: list[str] | None = None,
    params: dict[str, str] | None = None,
) -> str:
    if bool(code) == bool(path):
        return "Error: pass exactly one of code or path."

    secrets = secrets_mod.load(root)

    if path:
        target = (root / path).resolve()
        if not target.is_relative_to(root.resolve()):
            return f"Error: path {path} is outside the project directory."
        if not target.is_file():
            return f"Error: {path} is not a file."
        script_path = str(target)
        cleanup = False
        label = path
    else:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=root
        ) as f:
            f.write(code)
        script_path = f.name
        cleanup = True
        label = "code"

    ensure_venv(root)

    try:
        env = os.environ.copy()
        env.update(secrets)
        for k, v in (params or {}).items():
            env[f"PARAM_{k.upper()}"] = str(v)

        start = time.perf_counter()
        result = subprocess.run(
            [str(venv_python(root)), script_path, *(args or [])],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=env,
            cwd=str(root),
        )
        duration_ms = round((time.perf_counter() - start) * 1000)

        output_parts = [f"[{label} | exit {result.returncode} | {duration_ms} ms]"]
        if result.stdout.strip():
            output_parts.append(result.stdout.strip())
        if result.stderr.strip():
            output_parts.append(f"[stderr]\n{result.stderr.strip()}")
        if not result.stdout.strip() and not result.stderr.strip():
            output_parts.append("(no output)")
        hint = missing_module_hint(root, result.stderr)
        if hint:
            output_parts.append(f"[hint] {hint}")

        return secrets_mod.scrub("\n".join(output_parts), secrets)

    except subprocess.TimeoutExpired:
        return f"Error: script timed out after {SCRIPT_TIMEOUT} seconds."
    finally:
        if cleanup:
            Path(script_path).unlink(missing_ok=True)
