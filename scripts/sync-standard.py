"""Copy canonical standard files from the parent repo into gcontext/standard/.

Usage:
    uv run python scripts/sync-standard.py [REPO_ROOT]
    uv run python scripts/sync-standard.py --check [REPO_ROOT]

REPO_ROOT defaults to ../ (the gcontext-framework repo).
--check exits 1 and lists files that differ without writing.
"""

import argparse
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "gcontext" / "standard"

# Files that are verbatim copies of canonical sources.
# Index files (scripts/index.md, system/index.md, githooks/index.md) are
# templates in the bundle and intentionally differ from the canonical source,
# so they are not synced.
COPY_MAP = [
    ("context/system/rules.md", "context/system/rules.md"),
    ("context/system/scripts/sync-index-files.py", "context/system/scripts/sync-index-files.py"),
    ("context/system/scripts/rules_config.py", "context/system/scripts/rules_config.py"),
    ("context/system/scripts/track-context-changes.py", "context/system/scripts/track-context-changes.py"),
    ("context/system/scripts/save-every-n-turns.py", "context/system/scripts/save-every-n-turns.py"),
    ("context/system/scripts/githooks/pre-commit", "context/system/scripts/githooks/pre-commit"),
    (".claude/commands/save.md", "commands/save.md"),
    (".claude/commands/check-structure.md", "commands/check-structure.md"),
]


def sync(repo_root: Path, check_only: bool = False) -> list[str]:
    """Sync or check canonical files. Returns a list of differing paths."""
    diffs = []
    for src_rel, dst_rel in COPY_MAP:
        src = repo_root / src_rel
        dst = PACKAGE_DIR / dst_rel
        if not src.is_file():
            diffs.append(f"missing source: {src}")
            continue
        src_content = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == src_content:
            continue
        diffs.append(dst_rel)
        if not check_only:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            print(f"copied {dst_rel}")
    return diffs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_root", nargs="?", default="..",
                        help="Path to the gcontext-framework repo root")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if any file differs, without writing")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not (repo_root / "context" / "system" / "rules.md").is_file():
        print(f"Error: {repo_root} does not look like the gcontext-framework repo.",
              file=sys.stderr)
        sys.exit(1)

    diffs = sync(repo_root, check_only=args.check)

    if args.check:
        if diffs:
            print("Files differ:")
            for d in diffs:
                print(f"  {d}")
            sys.exit(1)
        else:
            print("All bundled files match their canonical source.")
    elif not diffs:
        print("All files already up to date.")


if __name__ == "__main__":
    main()
