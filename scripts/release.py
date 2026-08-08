"""Bump version, clean old artifacts, build web + package.

Run from the gcontext/ directory:
    uv run python scripts/release.py <new-version>

Produces wheel + sdist in dist/. Does NOT publish; the agent handles
that through the pypi connection.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent  # gcontext/
PYPROJECT = REPO / "pyproject.toml"
DIST = REPO / "dist"


def bump_version(new: str) -> str:
    text = PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        sys.exit("could not find version in pyproject.toml")
    old = match.group(1)
    if old == new:
        sys.exit(f"version is already {new}")
    updated = text.replace(f'version = "{old}"', f'version = "{new}"')
    PYPROJECT.write_text(updated)
    print(f"version: {old} -> {new}")
    return old


def clean_dist():
    if DIST.exists():
        shutil.rmtree(DIST)
        print("cleaned dist/")


def build():
    print("building web + package...")
    result = subprocess.run(["make", "build"], cwd=REPO, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"build failed (exit {result.returncode})")
    artifacts = sorted(DIST.glob("gcontext_ai-*"))
    for a in artifacts:
        print(f"  {a.name}")
    if len(artifacts) != 2:
        sys.exit(f"expected 2 artifacts, got {len(artifacts)}")
    print("build ok")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: uv run python scripts/release.py <new-version>")
    new_version = sys.argv[1]
    bump_version(new_version)
    clean_dist()
    build()
    print(f"\nready to publish {new_version}")


if __name__ == "__main__":
    main()
