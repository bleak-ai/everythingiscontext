#!/usr/bin/env python3
"""Read rule toggles from rules.yaml."""

from pathlib import Path


def load(path=None):
    """Parse rules.yaml and return a dict of toggle booleans.

    Accepts ``key: true|false`` lines, blank lines, and ``#`` comments.
    Raises ValueError on any other line.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "rules.yaml"
    result = {}
    if not Path(path).is_file():
        # v9: toggles folded into rules.md; no file means no toggles.
        return result
    for lineno, raw in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ": " not in line:
            raise ValueError(f"rules.yaml:{lineno}: bad line: {raw}")
        key, value = line.split(": ", 1)
        if value == "true":
            result[key] = True
        elif value == "false":
            result[key] = False
        else:
            raise ValueError(
                f"rules.yaml:{lineno}: value must be true or false: {raw}"
            )
    return result
