"""The kind enum has one documented home: docs/setup-script.md.

This test parses the list between the HTML comment markers in that doc and
asserts set equality with CONNECTION_KINDS in gcontext/kinds.py, so the
remaining documented copy cannot drift from the code.
"""

import re
from pathlib import Path

from gcontext.kinds import CONNECTION_KINDS

DOC = Path(__file__).resolve().parent.parent / "docs" / "setup-script.md"

START = "<!-- kind-enum:start -->"
END = "<!-- kind-enum:end -->"


def test_setup_script_kind_list_matches_enum():
    text = DOC.read_text(encoding="utf-8")
    assert START in text, f"missing {START} marker in {DOC}"
    assert END in text, f"missing {END} marker in {DOC}"
    block = text.split(START, 1)[1].split(END, 1)[0]
    documented = re.findall(r"^- `([a-z0-9-]+)`$", block, flags=re.MULTILINE)
    assert documented, "no kind bullets found between the markers"
    assert sorted(documented) == sorted(CONNECTION_KINDS)
    # No duplicates in the doc list.
    assert len(documented) == len(set(documented))
