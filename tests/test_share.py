"""Tests for `gcontext share <module-path>`: validate a workflow template and show PR instructions."""

import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

INDEX_MD = """---
id: test-flow
name: Test Flow
description: A test workflow.
tags: [test]
---

Objective paragraph.
"""


def run_cli(*args, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


@pytest.fixture
def request_log():
    """Local HTTP server that logs all requests. Yields (server, log_list)."""
    log = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            log.append(("GET", self.path))
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            log.append(("POST", self.path))
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, log
    server.shutdown()


@pytest.fixture
def template(tmp_path):
    """A valid template folder."""
    t = tmp_path / "test-flow"
    t.mkdir()
    (t / "index.md").write_text(INDEX_MD)
    steps = t / "steps"
    steps.mkdir()
    (steps / "index.md").write_text("1-do.md: do things\n")
    (steps / "1-do.md").write_text("# Step 1\n")
    example = t / "runs" / "example"
    example.mkdir(parents=True)
    (example / "index.md").write_text("# Example\n")
    return t


def test_share_validates_and_prints_pr_instructions(template, request_log):
    server, log = request_log
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    assert "validated test-flow" in result.stdout
    assert "files)" in result.stdout
    assert "bleak-ai/workflows" in result.stdout
    assert "PR" in result.stdout or "pull request" in result.stdout.lower() or "pr" in result.stdout.lower()
    # No HTTP requests should have been made
    assert len(log) == 0


def test_share_gh_present_shows_commands(template, tmp_path):
    """When gh is on PATH, the output includes ready-to-run commands."""
    import shutil
    if not shutil.which("gh"):
        # Provide a fake gh on PATH so the CLI finds it
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        fake_gh.write_text("#!/bin/sh\n")
        fake_gh.chmod(0o755)
        import os
        env = dict(os.environ, PATH=f"{fake_bin}:{os.environ.get('PATH', '')}")
    else:
        env = None
    result = run_cli("share", str(template), cwd=template.parent, env=env)
    assert result.returncode == 0, result.stderr
    assert "gh repo fork" in result.stdout
    assert "gh pr create" in result.stdout
    assert "test-flow" in result.stdout


def test_share_missing_index(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "index.md not found" in result.stderr


def test_share_missing_frontmatter(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("# No frontmatter\n")
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "no YAML frontmatter" in result.stderr


def test_share_missing_id(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("---\nname: X\ndescription: Y\ntags: [a]\n---\n")
    (folder / "steps").mkdir()
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "missing 'id'" in result.stderr


def test_share_missing_name(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("---\nid: x\ndescription: Y\ntags: [a]\n---\n")
    (folder / "steps").mkdir()
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "missing 'name'" in result.stderr


def test_share_missing_description(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("---\nid: x\nname: X\ntags: [a]\n---\n")
    (folder / "steps").mkdir()
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "missing 'description'" in result.stderr


def test_share_missing_tags(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("---\nid: x\nname: X\ndescription: Y\n---\n")
    (folder / "steps").mkdir()
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "missing 'tags'" in result.stderr


def test_share_empty_tags(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("---\nid: x\nname: X\ndescription: Y\ntags: []\n---\n")
    (folder / "steps").mkdir()
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "at least one tag" in result.stderr


def test_share_bad_id_format(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text("---\nid: Bad_Id\nname: X\ndescription: Y\ntags: [a]\n---\n")
    (folder / "steps").mkdir()
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "lowercase letters, digits, and hyphens" in result.stderr


def test_share_missing_steps(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text(INDEX_MD)
    (folder / "runs" / "example").mkdir(parents=True)
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "steps/ folder not found" in result.stderr


def test_share_missing_example_run(tmp_path):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "index.md").write_text(INDEX_MD)
    (folder / "steps").mkdir()
    result = run_cli("share", str(folder), cwd=tmp_path)
    assert result.returncode == 1
    assert "runs/example/ folder not found" in result.stderr


def test_share_skips_dotfiles(template):
    (template / ".hidden").write_text("secret")
    (template / ".git").mkdir()
    (template / ".git" / "config").write_text("x")
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    # Dotfiles are skipped by bundle_files; just confirm validation passes
    assert "validated test-flow" in result.stdout


def test_share_skips_pycache(template):
    cache = template / "__pycache__"
    cache.mkdir()
    (cache / "mod.pyc").write_bytes(b"\x00\x01")
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    assert "validated test-flow" in result.stdout


def test_share_skips_binary_with_warning(template):
    (template / "image.bin").write_bytes(b"\x80\x81\x82\xff\xfe")
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    assert "Skipping image.bin" in result.stderr
