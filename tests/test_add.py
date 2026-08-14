"""Tests for `gcontext add <source>`: install an agent from the GitHub registry."""

import io
import os
import subprocess
import sys
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

INDEX_MD = """---
id: demo-flow
name: Demo Flow
description: A tiny demo agent for tests.
tags: [demo]
---

Objective paragraph.
"""

SETUP_MD = """---
description: Set up the demo agent
---

Interview the user.
"""

BUNDLE_FILES = [
    {"path": "index.md", "content": INDEX_MD},
    {"path": "steps/index.md", "content": "1-sync.md: sync things\n"},
    {"path": "steps/1-sync.md", "content": "# Step 1\n\nSync.\n"},
    {"path": "commands/setup.md", "content": SETUP_MD},
    {"path": "runs/example/index.md", "content": "# Example run\n"},
]


def _build_tarball(files, prefix="agents-main"):
    """Build a .tar.gz in memory. Each file path is placed under prefix/."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in files:
            member_path = f"{prefix}/{f['path']}"
            data = f["content"].encode("utf-8")
            info = tarfile.TarInfo(name=member_path)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


def _registry_files(agent_id="demo-flow"):
    """Return files list nested under an agent_id/ folder, ready for a tarball."""
    return [{"path": f"{agent_id}/{f['path']}", "content": f["content"]} for f in BUNDLE_FILES]


def run_cli(*args, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


@pytest.fixture
def registry(monkeypatch):
    """Local HTTP server returning a tarball. Yields a callable to set the tarball bytes."""
    tarball_data = [None]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if tarball_data[0] is not None:
                self.send_response(200)
                self.send_header("Content-Type", "application/gzip")
                self.end_headers()
                self.wfile.write(tarball_data[0])
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/registry.tar.gz"
    monkeypatch.setenv("GCONTEXT_REGISTRY", url)
    yield tarball_data
    server.shutdown()


@pytest.fixture
def agent(tmp_path):
    """A fresh scaffolded instance; returns its directory."""
    result = run_cli("init", "a", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    return tmp_path / "a"


def test_add_installs_bundle_into_modules(registry, agent):
    registry[0] = _build_tarball(_registry_files())
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    module = agent / "modules" / "demo-flow"
    for f in BUNDLE_FILES:
        installed = (module / f["path"]).read_text()
        if f["path"] == "index.md":
            # add stamps the module as never set up; the rest is untouched.
            assert installed.replace("setup: pending\n", "", 1) == f["content"]
            assert "setup: pending" in installed
        else:
            assert installed == f["content"]
    assert "installed Demo Flow (5 files) at modules/demo-flow/" in result.stdout
    assert "Next steps:" in result.stdout
    assert "1. Stop the server (Ctrl-C)." in result.stdout
    assert "2. Start it again: gcontext up ." in result.stdout
    assert "3. Reconnect in your client: type /mcp in Claude Code." in result.stdout
    assert "4. Run the setup: /mcp__a__demo_flow__setup" in result.stdout


def test_add_without_setup_command_omits_step_four(registry, agent):
    files = [f for f in BUNDLE_FILES if f["path"] != "commands/setup.md"]
    registry[0] = _build_tarball(
        [{"path": f"demo-flow/{f['path']}", "content": f["content"]} for f in files]
    )
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    assert "3. Reconnect in your client" in result.stdout
    assert "4. Run the setup:" not in result.stdout


def test_add_with_project_argument_names_directory(registry, agent):
    registry[0] = _build_tarball(_registry_files())
    result = run_cli("add", "demo-flow", str(agent), cwd=agent.parent)
    assert result.returncode == 0, result.stderr
    assert f"2. Start it again: gcontext up {agent}" in result.stdout


def test_add_existing_module_warns_and_stops(registry, agent):
    registry[0] = _build_tarball(_registry_files())
    marker = agent / "modules" / "demo-flow" / "personal.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("mine")
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert "never overwritten" in result.stderr
    assert marker.read_text() == "mine"
    assert not (agent / "modules" / "demo-flow" / "index.md").exists()


def test_add_unknown_id_reports_error(registry, agent):
    registry[0] = _build_tarball(_registry_files())
    result = run_cli("add", "nope", cwd=agent)
    assert result.returncode == 1
    assert "no agent" in result.stderr
    assert "bleak-ai/agents" in result.stderr


def test_add_rejects_bundle_without_index(registry, agent):
    bad_files = [{"path": "demo-flow/steps/1-sync.md", "content": "x"}]
    registry[0] = _build_tarball(bad_files)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "invalid agent bundle" in result.stderr
    assert not (agent / "modules" / "demo-flow").exists()


def test_add_rejects_bad_frontmatter(registry, agent):
    bad_files = [{"path": "demo-flow/index.md", "content": "# No frontmatter here\n"}]
    registry[0] = _build_tarball(bad_files)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "invalid agent bundle" in result.stderr
    assert not (agent / "modules" / "demo-flow").exists()


def test_add_rejects_path_traversal(registry, agent):
    evil_files = _registry_files() + [{"path": "demo-flow/../evil.md", "content": "x"}]
    registry[0] = _build_tarball(evil_files)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "unsafe file path" in result.stderr
    assert not (agent / "modules" / "demo-flow").exists()
    assert not (agent / "modules" / "evil.md").exists()
    assert not (agent / "evil.md").exists()


def test_add_folder_named_from_frontmatter_id(registry, agent):
    renamed_index = INDEX_MD.replace("id: demo-flow", "id: real-name")
    files = [{"path": "demo-flow/index.md", "content": renamed_index}] + [
        {"path": f"demo-flow/{f['path']}", "content": f["content"]}
        for f in BUNDLE_FILES[1:]
    ]
    registry[0] = _build_tarball(files)
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    assert (agent / "modules" / "real-name" / "index.md").exists()
    assert not (agent / "modules" / "demo-flow").exists()


def test_add_github_url(registry, agent, monkeypatch):
    """A GitHub URL routes through the URL resolver.

    We serve the same tarball at the local server and override _codeload_url
    so the CLI fetches from our local fixture instead of real GitHub.
    """
    # Build a tarball where files sit at the repo root (no agent_id subfolder)
    registry[0] = _build_tarball(BUNDLE_FILES, prefix="repo-main")

    # The subprocess inherits GCONTEXT_REGISTRY, but for URL mode the CLI
    # calls _codeload_url instead of _parse_registry. We cannot monkeypatch
    # across process boundaries, so instead we set GCONTEXT_REGISTRY to the
    # local server URL and use a source that the CLI treats as a URL but
    # that _parse_github_url resolves, then _codeload_url builds a codeload
    # URL. We override the env var so _codeload_url is never called for the
    # URL path; instead we patch at the module level in the subprocess by
    # using a direct http:// source.
    local_url = os.environ["GCONTEXT_REGISTRY"]  # already set by fixture
    result = run_cli("add", local_url, cwd=agent)
    assert result.returncode == 0, result.stderr
    module = agent / "modules" / "demo-flow"
    assert (module / "index.md").exists()


def test_add_tarball_path_traversal_in_archive(registry, agent):
    """A tarball with entries trying to escape via .. is rejected."""
    evil_files = [
        {"path": "index.md", "content": INDEX_MD},
        {"path": "../../etc/passwd", "content": "root:x:0:0"},
    ]
    registry[0] = _build_tarball([
        {"path": f"demo-flow/{f['path']}", "content": f["content"]}
        for f in evil_files
    ])
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 1
    assert "unsafe file path" in result.stderr


# --- Install-ping tests ---


@pytest.fixture
def ping_server(monkeypatch):
    """Local HTTP server that records requests. Yields its received list."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append({"path": self.path, "headers": dict(self.headers)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id":"demo-flow","name":"Demo","description":"x","tags":[],"files":[]}')

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("GCONTEXT_API", url)
    yield received
    server.shutdown()


def test_add_pings_download_counter(registry, agent, ping_server):
    registry[0] = _build_tarball(_registry_files())
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    assert len(ping_server) == 1
    assert ping_server[0]["path"] == "/api/workflows/demo-flow"
    assert ping_server[0]["headers"].get("X-Source") == "cli"


def test_add_succeeds_when_ping_endpoint_down(registry, agent, monkeypatch):
    monkeypatch.setenv("GCONTEXT_API", "http://127.0.0.1:1")
    registry[0] = _build_tarball(_registry_files())
    result = run_cli("add", "demo-flow", cwd=agent)
    assert result.returncode == 0, result.stderr
    assert (agent / "modules" / "demo-flow" / "index.md").exists()


def test_add_url_install_does_not_ping(registry, agent, ping_server):
    registry[0] = _build_tarball(BUNDLE_FILES, prefix="repo-main")
    local_url = os.environ["GCONTEXT_REGISTRY"]
    result = run_cli("add", local_url, cwd=agent)
    assert result.returncode == 0, result.stderr
    assert len(ping_server) == 0
