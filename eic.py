#!/usr/bin/env python3
"""eic.py — Everything Is Context module manager.

Usage:
    python eic.py init
    python eic.py new <kind> <name>
    python eic.py load <name> [name2 ...]
    python eic.py unload <name>
    python eic.py ls
    python eic.py env
    python eic.py validate [name]
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# Resolve paths relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
CORE_DIR = SCRIPT_DIR / "core"
MODULES_DIR = SCRIPT_DIR / "modules-repo"
CONTEXT_DIR = SCRIPT_DIR / "context"
TEMPLATES_DIR = CORE_DIR / "templates"
SECRETS_MD = SCRIPT_DIR / "secrets.md"

sys.path.insert(0, str(SCRIPT_DIR))

from core.manifest import ModuleManifest, read_manifest, write_manifest
from core.kind_specs import KIND_SPECS, INTEGRATION_INFO_SECTIONS
from core.schemas import validate_module_name
from core.llms_gen import generate_root_llms_txt, generate_structure_md, generate_system_md


def _copy_static_files():
    """Copy static template files into context/."""
    for name in ["principles.md", "module_features.md"]:
        src = TEMPLATES_DIR / name
        if src.exists():
            shutil.copy2(src, CONTEXT_DIR / name)
    if SECRETS_MD.exists():
        shutil.copy2(SECRETS_MD, CONTEXT_DIR / "secrets.md")


def _regenerate():
    """Regenerate all auto-generated files in context/."""
    template_content = (TEMPLATES_DIR / "system.md").read_text()
    generate_root_llms_txt(CONTEXT_DIR)
    generate_structure_md(CONTEXT_DIR)
    generate_system_md(CONTEXT_DIR, template_content)
    _copy_static_files()
    _generate_env_example()


def _generate_env_example():
    """Generate .env.example from all loaded modules' secrets lists."""
    lines = []
    for mod_dir in sorted(CONTEXT_DIR.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("."):
            continue
        manifest = read_manifest(mod_dir)
        if manifest.secrets:
            lines.append(f"# {manifest.name}")
            for secret in manifest.secrets:
                lines.append(f"{secret}=")
            lines.append("")
    env_example = SCRIPT_DIR / ".env.example"
    if lines:
        env_example.write_text("\n".join(lines) + "\n")
    elif env_example.exists():
        env_example.unlink()


def cmd_init(args):
    """Initialize the workspace."""
    MODULES_DIR.mkdir(exist_ok=True)
    CONTEXT_DIR.mkdir(exist_ok=True)

    # Create .gitignore if it doesn't exist
    gitignore = SCRIPT_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".env\n")
    else:
        content = gitignore.read_text()
        if ".env" not in content.splitlines():
            gitignore.write_text(content.rstrip("\n") + "\n.env\n")

    _regenerate()
    print("Created modules-repo/")
    print("Created context/")
    print("Ready. Create your first module with: python eic.py new integration <name>")


def cmd_new(args):
    """Scaffold a new module."""
    kind = args.kind
    name = args.name

    if kind not in KIND_SPECS:
        print(f"Error: unknown kind '{kind}'. Must be one of: {', '.join(KIND_SPECS.keys())}")
        sys.exit(1)

    try:
        name = validate_module_name(name)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    mod_dir = MODULES_DIR / name
    if mod_dir.exists():
        print(f"Error: module '{name}' already exists at {mod_dir}")
        sys.exit(1)

    mod_dir.mkdir(parents=True)
    spec = KIND_SPECS[kind]

    # Write module.yaml
    manifest = ModuleManifest(name=name, kind=kind)
    write_manifest(mod_dir, manifest)

    # Write llms.txt
    starter_desc = spec.starter_outline
    llms_content = f"# {name}\n\n> One-line summary of this module\n\n"
    llms_content += f"- [{spec.starter_file}]({spec.starter_file}): {starter_desc}\n"
    llms_content += "- [module.yaml](module.yaml): Module configuration\n"
    (mod_dir / "llms.txt").write_text(llms_content)

    # Write starter file(s)
    if kind == "integration":
        sections = []
        for s in INTEGRATION_INFO_SECTIONS:
            sections.append(f"## {s.name}\n{s.purpose}\n")
        (mod_dir / "info.md").write_text(f"# {name}\n\n" + "\n".join(sections))

    elif kind == "task":
        (mod_dir / "brief.md").write_text(
            f"# {name}\n\n## Goal\nWhat this task should accomplish.\n\n## Context\nBackground and constraints.\n"
        )
        (mod_dir / "status.md").write_text(
            "# Status\n\n## Subtasks\n- [ ] First subtask\n"
        )

    elif kind == "workflow":
        (mod_dir / "steps.md").write_text(
            f"# {name}\n\n## Steps\n1. First step\n2. Second step\n"
        )

    for f in spec.required_files:
        print(f"Created modules-repo/{name}/{f}")
    print(f'Module "{name}" created. Edit the files, then load it with: python eic.py load {name}')


def cmd_load(args):
    """Load modules into the workspace via symlinks."""
    if not CONTEXT_DIR.exists():
        print("Error: workspace not initialized. Run: python eic.py init")
        sys.exit(1)

    for name in args.names:
        mod_source = MODULES_DIR / name
        if not mod_source.is_dir():
            print(f"Error: module '{name}' not found in modules-repo/")
            sys.exit(1)

        link_path = CONTEXT_DIR / name
        if link_path.is_symlink() or link_path.exists():
            print(f"Already loaded: {name}")
            continue

        # Relative symlink for portability
        link_path.symlink_to(Path("..") / "modules-repo" / name)
        print(f"Loaded {name}")

    _regenerate()
    loaded_count = sum(1 for p in CONTEXT_DIR.iterdir() if p.is_symlink())
    print(f"Regenerated context/ ({loaded_count} modules)")


def cmd_unload(args):
    """Remove a module from the workspace."""
    name = args.name
    link_path = CONTEXT_DIR / name

    if not link_path.is_symlink():
        print(f"Error: '{name}' is not loaded")
        sys.exit(1)

    link_path.unlink()
    print(f"Unloaded {name}")

    _regenerate()
    loaded_count = sum(1 for p in CONTEXT_DIR.iterdir() if p.is_symlink())
    print(f"Regenerated context/ ({loaded_count} modules)")


def cmd_ls(args):
    """List all modules and their status."""
    if not MODULES_DIR.exists():
        print("No modules-repo/ directory. Run: python eic.py init")
        return

    loaded_names = set()
    if CONTEXT_DIR.exists():
        loaded_names = {p.name for p in CONTEXT_DIR.iterdir() if p.is_symlink()}

    all_modules = sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir())

    if not all_modules:
        print("No modules found. Create one with: python eic.py new integration <name>")
        return

    loaded = [(n, read_manifest(MODULES_DIR / n)) for n in all_modules if n in loaded_names]
    available = [(n, read_manifest(MODULES_DIR / n)) for n in all_modules if n not in loaded_names]

    from core.llms_gen import extract_module_summary

    def _summary(name):
        llms_file = MODULES_DIR / name / "llms.txt"
        if llms_file.exists():
            return extract_module_summary(llms_file.read_text())
        return ""

    if loaded:
        print("LOADED")
        for name, m in loaded:
            summary = _summary(name)
            print(f"  {name:<20s} {m.kind:<14s} {summary}")
        print()

    if available:
        print("AVAILABLE")
        for name, m in available:
            summary = _summary(name)
            print(f"  {name:<20s} {m.kind:<14s} {summary}")


def cmd_env(args):
    """Check which secret variables are set or missing."""
    if not CONTEXT_DIR.exists():
        print("Error: workspace not initialized. Run: python eic.py init")
        sys.exit(1)

    # Try to load .env file into a dict (don't inject into os.environ)
    env_vars = dict(os.environ)
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()

    any_missing = False
    any_secrets = False

    for mod_dir in sorted(CONTEXT_DIR.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("."):
            continue
        manifest = read_manifest(mod_dir)
        if not manifest.secrets:
            continue
        any_secrets = True
        print(f"\n{manifest.name}")
        for secret in manifest.secrets:
            if secret in env_vars and env_vars[secret]:
                print(f"  {secret:<30s} set")
            else:
                print(f"  {secret:<30s} missing")
                any_missing = True

    if not any_secrets:
        print("No loaded modules declare secrets.")
        return

    if any_missing:
        print("\nMissing variables. Add them to .env")
        sys.exit(1)
    else:
        print("\nAll variables set.")


def cmd_validate(args):
    """Validate module structure."""
    if args.name:
        names = [args.name]
    else:
        if not MODULES_DIR.exists():
            print("No modules-repo/ directory.")
            sys.exit(1)
        names = sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir())

    if not names:
        print("No modules to validate.")
        return

    all_pass = True
    for name in names:
        mod_dir = MODULES_DIR / name
        if not mod_dir.is_dir():
            print(f"{name}  FAIL  module directory not found")
            all_pass = False
            continue

        errors = []
        manifest = None

        # Check module.yaml
        manifest_path = mod_dir / "module.yaml"
        if not manifest_path.exists():
            errors.append("missing module.yaml")
        else:
            try:
                manifest = read_manifest(mod_dir)
            except Exception as e:
                errors.append(f"invalid module.yaml: {e}")

            if manifest and manifest.kind not in KIND_SPECS:
                errors.append(f"unknown kind '{manifest.kind}'")

        # Check required files per kind
        if manifest_path.exists() and manifest:
            spec = KIND_SPECS.get(manifest.kind)
            if spec:
                for req_file in spec.required_files:
                    if not (mod_dir / req_file).exists():
                        errors.append(f"missing {req_file} (required for {manifest.kind} kind)")

        # Check llms.txt links
        llms_path = mod_dir / "llms.txt"
        if llms_path.exists():
            for line in llms_path.read_text().splitlines():
                # Parse markdown links: [text](path)
                for match in re.finditer(r'\[.*?\]\((.+?)\)', line):
                    link_target = match.group(1)
                    if link_target.startswith("http"):
                        continue
                    if not (mod_dir / link_target).exists():
                        errors.append(f"llms.txt links to '{link_target}' which does not exist")

        if errors:
            print(f"{name}  FAIL")
            for e in errors:
                print(f"  - {e}")
            all_pass = False
        else:
            print(f"{name}  PASS")

    if not all_pass:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="eic.py",
        description="Everything Is Context — module manager",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize the workspace")

    # new
    new_parser = subparsers.add_parser("new", help="Scaffold a new module")
    new_parser.add_argument("kind", choices=list(KIND_SPECS.keys()), help="Module kind")
    new_parser.add_argument("name", help="Module name")

    # load
    load_parser = subparsers.add_parser("load", help="Load modules into workspace")
    load_parser.add_argument("names", nargs="+", help="Module names to load")

    # unload
    unload_parser = subparsers.add_parser("unload", help="Unload a module from workspace")
    unload_parser.add_argument("name", help="Module name to unload")

    # ls
    subparsers.add_parser("ls", help="List all modules")

    # env
    subparsers.add_parser("env", help="Check secret variable status")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate module structure")
    validate_parser.add_argument("name", nargs="?", help="Module name (validates all if omitted)")

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "new":
        cmd_new(args)
    elif args.command == "load":
        cmd_load(args)
    elif args.command == "unload":
        cmd_unload(args)
    elif args.command == "ls":
        cmd_ls(args)
    elif args.command == "env":
        cmd_env(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command is None:
        parser.print_help()
        sys.exit(1)
    else:
        print(f"Command '{args.command}' not yet implemented")
        sys.exit(1)


if __name__ == "__main__":
    main()
