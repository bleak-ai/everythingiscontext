"""Tests for `gcontext add <workflow-id>`: install a workflow template from the API."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

INDEX_MD = """---
id: demo-flow
name: Demo Flow
description: A tiny demo workflow for tests.
tags: [demo]
---

Objective paragraph.
"""

SETUP_MD = """---
description: Set up the demo workflow
---

Interview the user.
"""

BUNDLE = {
    "id": "demo-flow",
    "name": "Demo Flow",
    "description": "A tiny demo workflow for tests.",
    "tags": ["demo"],
    "files": [
        {"path": "index.md", "content": INDEX_MD},
        {"path": "steps/index.md", "content": "1-sync.md: sync things\n"},
        {"path": "steps/1-sync.md", "content": "# Step 1\n\nSync.\n"},
        {"path": "commands/setup.md", "content": SETUP_MD},
        {"path": "runs/example/index.md", "content": "# Example run\n"},
    ],
}


def run_cli(*args, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


@pytest.fixture
def api(monkeypatch):
    """Local HTTP stub for the workflows API. Yields a dict: path -> (status, body)."""
    responses = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = responses.get(self.path, (404, {"detail": "not found"}))
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("GCONTEXT_API_URL", f"http://127.0.0.1:{server.server_port}")
    yield responses
    server.shutdown()


@pytest.fixture
def agent(tmp_path):
    """A fresh scaffolded instance; returns its directory."""
    result = run_cli("init", "a", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    return tmp_path / "a"


def test_add_installs_bundle_into_modules(api, agent):
    api["/api/workflows/demo-flow"] = (200, BUNDLE)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    module = agent / "modules" / "demo-flow"
    for f in BUNDLE["files"]:
        assert (module / f["path"]).read_text() == f["content"]
    assert "Demo Flow" in result.stdout
    assert "commands/setup.md" in result.stdout


def test_add_existing_module_warns_and_stops(api, agent):
    api["/api/workflows/demo-flow"] = (200, BUNDLE)
    marker = agent / "modules" / "demo-flow" / "personal.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("mine")
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert "never overwritten" in result.stderr
    assert marker.read_text() == "mine"
    assert not (agent / "modules" / "demo-flow" / "index.md").exists()


def test_add_unknown_id_reports_404(api, agent):
    result = run_cli("add", "nope", cwd=agent)
    assert result.returncode == 1
    assert "no published workflow" in result.stderr


def test_add_rejects_bundle_without_index(api, agent):
    bad = dict(BUNDLE, files=[{"path": "steps/1-sync.md", "content": "x"}])
    api["/api/workflows/demo-flow"] = (200, bad)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "invalid workflow bundle" in result.stderr
    assert not (agent / "modules" / "demo-flow").exists()


def test_add_rejects_bad_frontmatter(api, agent):
    bad_index = {"path": "index.md", "content": "# No frontmatter here\n"}
    bad = dict(BUNDLE, files=[bad_index])
    api["/api/workflows/demo-flow"] = (200, bad)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "invalid workflow bundle" in result.stderr
    assert not (agent / "modules" / "demo-flow").exists()


def test_add_rejects_path_traversal(api, agent):
    evil = dict(BUNDLE, files=BUNDLE["files"] + [{"path": "../evil.md", "content": "x"}])
    api["/api/workflows/demo-flow"] = (200, evil)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "unsafe file path" in result.stderr
    assert not (agent / "modules" / "demo-flow").exists()
    assert not (agent / "modules" / "evil.md").exists()
    assert not (agent / "evil.md").exists()


def test_add_folder_named_from_frontmatter_id(api, agent):
    renamed_index = {"path": "index.md", "content": INDEX_MD.replace("id: demo-flow", "id: real-name")}
    bundle = dict(BUNDLE, files=[renamed_index] + BUNDLE["files"][1:])
    api["/api/workflows/demo-flow"] = (200, bundle)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    assert (agent / "modules" / "real-name" / "index.md").exists()
    assert not (agent / "modules" / "demo-flow").exists()
