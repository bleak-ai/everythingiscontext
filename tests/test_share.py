"""Tests for `gcontext share <module-path>`: validate and submit a workflow template."""

import json
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
def api(monkeypatch):
    """Local HTTP stub. Yields (responses_dict, posted_list)."""
    responses = {}
    posted = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = responses.get(self.path, (404, {"detail": "not found"}))
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length)) if length else {}
            posted.append({"path": self.path, "body": data})
            result = {
                "id": "test-flow", "name": "Test Flow",
                "description": "A test workflow.", "tags": ["test"],
                "status": "pending",
            }
            payload = json.dumps(result).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("GCONTEXT_API_URL", f"http://127.0.0.1:{server.server_port}")
    yield responses, posted
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


def test_share_submits_valid_template(api, template):
    responses, posted = api
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    assert "submitted test-flow" in result.stdout
    assert "pending" in result.stdout
    assert len(posted) == 1
    assert posted[0]["path"] == "/api/workflows"
    files = posted[0]["body"]["files"]
    paths = [f["path"] for f in files]
    assert "index.md" in paths
    assert "steps/index.md" in paths


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


def test_share_skips_dotfiles(api, template):
    responses, posted = api
    (template / ".hidden").write_text("secret")
    (template / ".git").mkdir()
    (template / ".git" / "config").write_text("x")
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    files = posted[0]["body"]["files"]
    paths = [f["path"] for f in files]
    assert ".hidden" not in paths
    assert ".git/config" not in paths


def test_share_skips_pycache(api, template):
    responses, posted = api
    cache = template / "__pycache__"
    cache.mkdir()
    (cache / "mod.pyc").write_bytes(b"\x00\x01")
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    files = posted[0]["body"]["files"]
    paths = [f["path"] for f in files]
    assert not any("__pycache__" in p for p in paths)


def test_share_skips_binary_with_warning(api, template):
    responses, posted = api
    (template / "image.bin").write_bytes(b"\x80\x81\x82\xff\xfe")
    result = run_cli("share", str(template), cwd=template.parent)
    assert result.returncode == 0, result.stderr
    assert "Skipping image.bin" in result.stderr
    files = posted[0]["body"]["files"]
    paths = [f["path"] for f in files]
    assert "image.bin" not in paths


def test_share_status_mode(api, tmp_path):
    responses, _ = api
    responses["/api/workflows/test-flow/status"] = (200, {
        "id": "test-flow",
        "status": "approved",
        "submitted_at": "2026-08-09T12:00:00Z",
        "reviewed_at": "2026-08-09T14:30:00Z",
    })
    result = run_cli("share", "--status", "test-flow", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "approved" in result.stdout
    assert "2026-08-09 12:00 UTC" in result.stdout
    assert "2026-08-09 14:30 UTC" in result.stdout


def test_share_status_not_found(api, tmp_path):
    _, _ = api
    result = run_cli("share", "--status", "nope", cwd=tmp_path)
    assert result.returncode == 1
    assert "no submission found" in result.stderr
