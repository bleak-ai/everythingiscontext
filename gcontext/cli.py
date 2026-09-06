"""gcontext CLI. A standard for a context/ folder, plus a small CLI."""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from . import commands as commands_mod
from . import exec as exec_mod
from . import secrets as secrets_mod
from . import server

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

DEFAULT_PORT = 4242
PORT_LOCKFILE = ".gcontext-port"


def find_project_dir(path: str | None) -> Path:
    p = Path(path).resolve() if path else Path.cwd().resolve()
    if p.is_dir():
        return p
    print(f"Error: project folder does not exist: {p}", file=sys.stderr)
    sys.exit(1)


def resolve_port(args, project_dir: Path) -> int:
    if getattr(args, "port", None):
        return args.port
    env = os.environ.get("GCONTEXT_PORT")
    if env:
        try:
            return int(env)
        except ValueError:
            print(f"Error: GCONTEXT_PORT='{env}' is not a valid number.", file=sys.stderr)
            sys.exit(1)
    lockfile = project_dir / PORT_LOCKFILE
    if lockfile.exists():
        try:
            return int(lockfile.read_text().strip())
        except (ValueError, OSError):
            pass
    return DEFAULT_PORT


def write_port_lockfile(project_dir: Path, port: int) -> None:
    (project_dir / PORT_LOCKFILE).write_text(str(port))


def remove_port_lockfile(project_dir: Path) -> None:
    lockfile = project_dir / PORT_LOCKFILE
    if lockfile.exists():
        lockfile.unlink()


def server_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/mcp"


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_free_port(start: int, attempts: int = 50) -> int:
    for port in range(start, start + attempts):
        if port_is_free(port):
            return port
    print(f"Error: no free port found in {start}-{start + attempts - 1}.", file=sys.stderr)
    sys.exit(1)


def cmd_init(args):
    from . import init as init_mod
    target_dir = find_project_dir(args.project)
    exit_code = init_mod.run_init(target_dir)
    sys.exit(exit_code)


def cmd_serve(args):
    project_dir = find_project_dir(args.project)
    server.PROJECT_DIR = project_dir
    name = project_dir.name
    port = resolve_port(args, project_dir)

    if not port_is_free(port):
        if getattr(args, "port", None):
            print(f"Error: port {port} (from --port) is already in use.", file=sys.stderr)
            print("Free it, or pick another port with --port.", file=sys.stderr)
            sys.exit(1)
        chosen = find_free_port(port + 1)
        print(f"{YELLOW}{BOLD}Port {port} is taken.{RESET}")
        print(f"{YELLOW}{BOLD}Using port {chosen} instead.{RESET}")
        print()
        port = chosen

    url = server_url(port)

    exec_mod.ensure_venv(project_dir)
    n_framework_prompts = server.register_framework_prompts()
    n_commands = server.register_commands()
    n_base_lines, n_instruction_lines = server.load_instructions()
    server.snapshot_startup_files()

    print(f"{BOLD}gcontext{RESET} {DIM}-{RESET} serving {name} {DIM}({__version__}){RESET}")
    print(f"{DIM}State: {project_dir}{RESET}")
    print()
    print(f"Serving at {BOLD}{url}{RESET}")
    print()
    env_file = project_dir / "secrets.env"
    if env_file.exists() and (env_file.stat().st_mode & 0o077):
        print(f"{DIM}note: secrets.env is readable by other users on this machine; consider: chmod 600 secrets.env{RESET}")
        print()

    print("Connect a client (once per client, works from any directory):")
    print(f"  Claude Code:     claude mcp add --transport http {name} {url}")
    print(f"  Claude Desktop:  Settings -> Connectors -> Add custom connector -> {url}")
    print(f'  Cursor:          "{name}": {{"url": "{url}"}} in ~/.cursor/mcp.json')
    print(f'  Codex:           [mcp_servers.{name}] url = "{url}" in ~/.codex/config.toml')
    print()
    print(f"Instructions: {n_base_lines} framework + {n_instruction_lines} project lines, pushed at connect.")
    builtin_names = ", ".join(p.stem for p in commands_mod.discover_framework_prompts())
    prompt_bits = [f"{n_framework_prompts} built-in ({builtin_names})"]
    if n_commands:
        prompt_bits.append(f"{n_commands} project command(s)")
    print(f"Commands: {' + '.join(prompt_bits)}")
    print()
    print("Clients appear below as they connect. Ctrl+C stops the server.")
    print()

    write_port_lockfile(project_dir, port)
    try:
        server.mcp.run(
            transport="http", host="127.0.0.1", port=port, path="/mcp",
            show_banner=False, log_level="warning", stateless_http=True,
        )
    finally:
        remove_port_lockfile(project_dir)


def find_context_project_dir(path: str | None) -> Path:
    project_dir = Path(path).resolve() if path else Path.cwd().resolve()
    if (project_dir / "context").is_dir():
        return project_dir
    print(f"Error: no context/ folder found in {project_dir}.", file=sys.stderr)
    print("You must set up the context standard first, then run this command again.", file=sys.stderr)
    sys.exit(1)


def parse_package_manifest(content: str) -> dict:
    manifest = {}
    current_list = None
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw_line[0].isspace() and ":" in raw_line:
            key, _, value = raw_line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "[]":
                manifest[key] = []
            elif value:
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                manifest[key] = value
            else:
                manifest[key] = []
            current_list = key
        elif current_list and raw_line.startswith("  - "):
            value = raw_line[4:].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            manifest[current_list].append(value)
    return manifest


def update_package_dependencies(pyproject_path: Path, deps: list[str]) -> None:
    content = pyproject_path.read_text()
    section_match = re.search(
        r"(?ms)^\[project\.optional-dependencies\]\s*\n(.*?)(?=^\[|\Z)",
        content,
    )
    existing = []
    if section_match:
        packages_match = re.search(
            r"(?ms)^packages\s*=\s*\[(.*?)\]",
            section_match.group(1),
        )
        if packages_match:
            existing = re.findall(r"[\"']([^\"']+)[\"']", packages_match.group(1))

    merged = list(dict.fromkeys(existing + deps))
    packages_line = "packages = [" + ", ".join(json.dumps(dep) for dep in merged) + "]"

    if not section_match:
        separator = "" if not content or content.endswith("\n\n") else "\n"
        content += f"{separator}[project.optional-dependencies]\n{packages_line}\n"
    else:
        section = section_match.group(0)
        packages_match = re.search(r"(?ms)^packages\s*=\s*\[.*?\]", section)
        if packages_match:
            updated_section = section[:packages_match.start()] + packages_line + section[packages_match.end():]
        else:
            updated_section = section.rstrip() + f"\n{packages_line}\n"
        content = content[:section_match.start()] + updated_section + content[section_match.end():]

    pyproject_path.write_text(content)


def cmd_install(args):
    project_dir = find_context_project_dir(args.project)
    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        print(f"Error: package source is not a local folder: {source}", file=sys.stderr)
        sys.exit(1)

    source_manifest = source / "package.yaml"
    if not source_manifest.is_file():
        print(f"Error: package.yaml not found in {source}.", file=sys.stderr)
        sys.exit(1)

    packages_dir = project_dir / "context" / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    installed_dir = packages_dir / source.name
    if installed_dir.exists():
        print(f"Error: package '{source.name}' is already installed at {installed_dir}.", file=sys.stderr)
        sys.exit(1)
    shutil.copytree(source, installed_dir)

    manifest = parse_package_manifest((installed_dir / "package.yaml").read_text())
    required_secrets = manifest.get("secrets") or []
    env_path = project_dir / "secrets.env"
    available_secrets = secrets_mod.parse_dotenv(env_path.read_text() if env_path.exists() else "")
    missing_secrets = [name for name in required_secrets if name not in available_secrets]
    if missing_secrets and not args.skip_secrets:
        print("Error: missing required secrets:", file=sys.stderr)
        for name in missing_secrets:
            print(f"  {name}", file=sys.stderr)
        print("Add these entries to secrets.env, then run the command again.", file=sys.stderr)
        sys.exit(1)

    deps = manifest.get("deps") or []
    if deps:
        pyproject_path = project_dir / "pyproject.toml"
        if pyproject_path.exists():
            update_package_dependencies(pyproject_path, deps)
            subprocess.run(["uv", "sync"], cwd=project_dir, check=True)
            deps_status = f"installed {len(deps)} dependency entry or entries"
        else:
            deps_status = "skipped because pyproject.toml does not exist"
    else:
        deps_status = "no dependencies required"

    template = installed_dir / "config.yaml.template"
    if template.exists():
        local_dir = project_dir / "local"
        local_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, local_dir / "config.yaml")
        print("Config: created local/config.yaml. Fill in all REQUIRED fields.")

    file_count = sum(1 for item in installed_dir.rglob("*") if item.is_file())
    if missing_secrets:
        secrets_status = "skipped missing secret check: " + ", ".join(missing_secrets)
    elif required_secrets:
        secrets_status = "all required secrets are present"
    else:
        secrets_status = "no secrets required"
    print(f"Package: {source.name}")
    print(f"Files installed: {file_count}")
    print(f"Secrets: {secrets_status}")
    print(f"Dependencies: {deps_status}")


def cmd_check(args):
    project_dir = find_project_dir(args.project)
    result = subprocess.run(
        ["uv", "run", "context/system/scripts/sync-index-files.py", "--check"],
        cwd=project_dir,
    )
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        prog="gcontext",
        description="A standard for a context/ folder, plus a small CLI: init, install, serve, check.",
    )
    parser.add_argument("--version", action="version", version=f"gcontext {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    def add_common(p):
        p.add_argument("project", nargs="?", help="Path to project directory")
        p.add_argument("--port", type=int, help=f"Server port (default: {DEFAULT_PORT})")

    init_parser = subparsers.add_parser(
        "init", help="Write the context standard into a project directory"
    )
    init_parser.add_argument("project", nargs="?", help="Path to project directory (default: .)")

    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the MCP server for a project",
    )
    add_common(serve_parser)

    install_parser = subparsers.add_parser("install", help="Install a local package into context/packages/")
    install_parser.add_argument("source", help="Path to a local package folder")
    install_parser.add_argument("--project", help="Project root that contains context/")
    install_parser.add_argument("--skip-secrets", action="store_true", help="Install even if required secrets are missing")

    check_parser = subparsers.add_parser(
        "check", help="Run the context/ standard checks"
    )
    check_parser.add_argument("project", nargs="?", help="Project root that contains context/")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "serve": cmd_serve,
        "install": cmd_install,
        "check": cmd_check,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
