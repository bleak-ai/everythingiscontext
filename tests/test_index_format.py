"""Tests for the index.md format validator and its two enforcement sites."""

import pytest

from gcontext import fs
from gcontext.fs import index_format_issues


VALID = (
    "# Notes\n"
    "\n"
    "Everything the agent knows about notes. Kept short on purpose.\n"
    "\n"
    "- `decisions.md`: the decision log\n"
    "- `playbooks/`: proven procedures\n"
)


def test_valid_index_passes():
    assert index_format_issues(VALID, ["decisions.md", "playbooks"]) == []


def test_missing_title_fails():
    issues = index_format_issues("Just a paragraph.\n", [])
    assert any("'# ' title" in i for i in issues)


def test_extra_heading_fails():
    content = VALID + "\n## More\n"
    issues = index_format_issues(content, ["decisions.md", "playbooks"])
    assert any("extra heading" in i for i in issues)


def test_content_after_bullets_fails():
    content = VALID + "\nA trailing paragraph that should not be here.\n"
    issues = index_format_issues(content, ["decisions.md", "playbooks"])
    assert any("after the bullet list" in i for i in issues)


def test_missing_sibling_fails():
    issues = index_format_issues(VALID, ["decisions.md", "playbooks", "log.md"])
    assert any("log.md" in i for i in issues)


def test_substring_sibling_not_satisfied_by_longer_name():
    content = (
        "# M\n\nSummary line.\n\n- `changelog.md`: the changelog\n"
    )
    issues = index_format_issues(content, ["changelog.md", "log.md"])
    assert any(i == "no bullet references log.md" for i in issues)


def test_frontmatter_is_stripped():
    content = (
        "---\nid: demo\nname: Demo\n---\n\n" + VALID
    )
    assert index_format_issues(content, ["decisions.md", "playbooks"]) == []


def test_wrapped_bullet_continuation_accepted():
    content = (
        "# Notes\n\nSummary line.\n\n"
        "- `decisions.md`: a long description that wraps onto\n"
        "  a second, indented line\n"
    )
    assert index_format_issues(content, ["decisions.md"]) == []


def test_bullet_referencing_no_sibling_fails():
    content = VALID + "- `ghost.md`: does not exist\n"
    issues = index_format_issues(content, ["decisions.md", "playbooks"])
    assert any("references no file" in i for i in issues)


def test_directory_matches_with_and_without_slash():
    with_slash = "# M\n\nSummary.\n\n- `steps/`: the steps\n"
    without_slash = "# M\n\nSummary.\n\n- [steps](steps/): the steps\n"
    assert index_format_issues(with_slash, ["steps"]) == []
    assert index_format_issues(without_slash, ["steps"]) == []


def test_empty_file_reports_single_issue():
    assert index_format_issues("", []) == ["the file is empty"]
    assert index_format_issues("\n\n", []) == ["the file is empty"]


def test_title_only_reports_missing_summary():
    issues = index_format_issues("# M\n", [])
    assert any("summary paragraph" in i for i in issues)


def test_long_summary_fails():
    content = "# M\n\n" + "\n".join(f"Line {i}." for i in range(7)) + "\n"
    issues = index_format_issues(content, [])
    assert any("longer than" in i for i in issues)


def test_two_summary_paragraphs_fail():
    content = "# M\n\nFirst paragraph.\n\nSecond paragraph.\n"
    issues = index_format_issues(content, [])
    assert any("single paragraph" in i for i in issues)


def test_write_file_warns_but_writes(tmp_path):
    mod = tmp_path / "modules" / "notes"
    mod.mkdir(parents=True)
    (mod / "decisions.md").write_text("log")
    bad = "no title, no bullets\n"
    out = fs.write_file(tmp_path, "modules/notes/index.md", bad)
    assert "Warning" in out
    assert "index format" in out
    assert "'# ' title" in out
    assert (mod / "index.md").read_text() == bad  # advisory: write went through


def test_write_file_valid_index_no_warning(tmp_path):
    mod = tmp_path / "modules" / "notes"
    mod.mkdir(parents=True)
    (mod / "decisions.md").write_text("log")
    (mod / "playbooks").mkdir()
    out = fs.write_file(tmp_path, "modules/notes/index.md", VALID)
    assert "Warning" not in out
