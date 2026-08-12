"""Build registry.json from an agents repo checkout.

Usage: uv run scripts/build_registry.py <path-to-agents-checkout>

Scans each top-level directory for an index.md with valid frontmatter,
collects id/name/description/tags and the file list, and writes
registry.json at the checkout root.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build(checkout: Path) -> dict:
    from gcontext.commands import parse_command

    agents = []
    for d in sorted(checkout.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        index = d / "index.md"
        if not index.exists():
            continue
        try:
            meta, _ = parse_command(index.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not meta.get("id"):
            continue

        files = []
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            rel_parts = f.relative_to(d).parts
            if any(p.startswith(".") or p.startswith("__") for p in rel_parts):
                continue
            try:
                f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            files.append(str(f.relative_to(d)))

        agents.append({
            "id": meta["id"],
            "name": meta.get("name", meta["id"]),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "files": files,
        })

    agents.sort(key=lambda a: a["id"])
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agents": agents,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run scripts/build_registry.py <path-to-agents-checkout>")
        sys.exit(1)

    checkout = Path(sys.argv[1]).resolve()
    if not checkout.is_dir():
        print(f"Error: {checkout} is not a directory.")
        sys.exit(1)

    catalog = build(checkout)
    out = checkout / "registry.json"
    out.write_text(json.dumps(catalog, indent=2) + "\n")

    for a in catalog["agents"]:
        print(f"  {a['id']} ({len(a['files'])} files)")
    print(f"\n{len(catalog['agents'])} agents written to {out}")


if __name__ == "__main__":
    main()
