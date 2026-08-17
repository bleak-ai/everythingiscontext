"""Tests for agent dependencies: `agents:` in the manifest frontmatter.

Covers install resolution (MCP tool and CLI add) and the share validator.
"""

import io
import json
import os
import subprocess
import sys
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import yaml

from gcontext import registry as registry_mod, server


def _index_md(agent_id, name, agents=None):
    meta = {
        "id": agent_id,
        "name": name,
        "description": f"{name} for tests.",
        "tags": ["test"],
    }
    if agents is not None:
        meta["agents"] = agents
    return f"---\n{yaml.safe_dump(meta)}---\n\nObjective paragraph.\n"


def _bundle(agent_id, name, agents=None):
    return [
        {"path": f"{agent_id}/index.md", "content": _index_md(agent_id, name, agents)},
        {"path": f"{agent_id}/steps/index.md", "content": "1-do.md: do things\n"},
        {"path": f"{agent_id}/steps/1-do.md", "content": "# Step 1\n"},
        {"path": f"{agent_id}/runs/example/index.md", "content": "# Example run\n"},
        {"path": f"{agent_id}/commands/setup.md", "content": "---\ndescription: Set up.\n---\n\n1. Ask.\n"},
    ]


def _build_tarball(files, prefix="agents-main"):
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


@pytest.fixture
def registry(monkeypatch):
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

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{srv.server_port}/registry.tar.gz"
    monkeypatch.setenv("GCONTEXT_REGISTRY", url)
    yield tarball_data, url
    srv.shutdown()


@pytest.fixture
def project(tmp_path, monkeypatch):
    p = tmp_path / "agent"
    p.mkdir()
    (p / "gcontext.yaml").write_text("name: test-agent\n")
    (p / "agents").mkdir()
    (p / "connections").mkdir()
    monkeypatch.setattr(server, "PROJECT_DIR", p)
    return p


def _set_registry(tarball_data, *bundles):
    files = []
    for b in bundles:
        files.extend(b)
    tarball_data[0] = _build_tarball(files)


# --- Install resolution (MCP agent tool) ---

def test_install_pulls_missing_dependency(registry, project):
    tarball_data, _ = registry
    _set_registry(
        tarball_data,
        _bundle("parent-flow", "Parent Flow", agents=["dep-flow"]),
        _bundle("dep-flow", "Dep Flow"),
    )
    result = server.agent(action="install", id="parent-flow")
    assert (project / "agents" / "parent-flow" / "index.md").exists()
    assert (project / "agents" / "dep-flow" / "index.md").exists()
    assert (project / "agents" / "dep-flow" / registry_mod.MANIFEST_NAME).exists()
    assert "Installed Parent Flow" in result
    assert "Installed Dep Flow" in result
    assert "(required by parent-flow)" in result


def test_install_skips_present_dependency(registry, project):
    tarball_data, _ = registry
    _set_registry(
        tarball_data,
        _bundle("parent-flow", "Parent Flow", agents=["dep-flow"]),
        _bundle("dep-flow", "Dep Flow"),
    )
    server.agent(action="install", id="dep-flow")
    result = server.agent(action="install", id="parent-flow")
    assert "Installed Parent Flow" in result
    assert "required by" not in result


def test_install_cycle_installs_each_once(registry, project):
    tarball_data, _ = registry
    _set_registry(
        tarball_data,
        _bundle("a-flow", "A Flow", agents=["b-flow"]),
        _bundle("b-flow", "B Flow", agents=["a-flow"]),
    )
    result = server.agent(action="install", id="a-flow")
    assert (project / "agents" / "a-flow" / "index.md").exists()
    assert (project / "agents" / "b-flow" / "index.md").exists()
    assert "Installed A Flow" in result
    assert "Installed B Flow" in result


def test_install_missing_dependency_fails_clean(registry, project):
    tarball_data, _ = registry
    _set_registry(
        tarball_data,
        _bundle("parent-flow", "Parent Flow", agents=["ghost-flow"]),
    )
    result = server.agent(action="install", id="parent-flow")
    assert result.startswith("Error:")
    assert "ghost-flow" in result
    assert not (project / "agents" / "parent-flow").exists()


def test_install_bad_agents_field_rejected(registry, project):
    files = _bundle("parent-flow", "Parent Flow")
    files[0]["content"] = files[0]["content"].replace(
        "tags:", "agents: not-a-list-but-a-string\ntags:"
    )
    tarball_data, _ = registry
    _set_registry(tarball_data, files)
    result = server.agent(action="install", id="parent-flow")
    assert result.startswith("Error:")
    assert "agents" in result


# --- CLI add banner ---

def run_cli(*args, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def test_add_banner_lists_dependency(registry, tmp_path):
    tarball_data, url = registry
    _set_registry(
        tarball_data,
        _bundle("parent-flow", "Parent Flow", agents=["dep-flow"]),
        _bundle("dep-flow", "Dep Flow"),
    )
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "gcontext.yaml").write_text("name: proj\n")
    (proj / "connections").mkdir()
    env = dict(os.environ, GCONTEXT_REGISTRY=url)
    result = run_cli("add", "parent-flow", cwd=proj, env=env)
    assert result.returncode == 0, result.stderr
    assert "Parent Flow" in result.stdout
    assert "Dep Flow" in result.stdout
    assert "(required by parent-flow)" in result.stdout
    assert (proj / "agents" / "dep-flow" / "index.md").exists()


# --- Share validator ---

def _template(tmp_path, agent_id="test-flow", agents=None, extra_meta=None):
    meta = {
        "id": agent_id,
        "name": "Test Flow",
        "description": "A test agent.",
        "tags": ["test"],
        "connections": [{"kind": "browser", "description": "A browser."}],
        "flow": ["Ask for a page", "Open it and report back"],
    }
    if agents is not None:
        meta["agents"] = agents
    if extra_meta:
        meta.update(extra_meta)
    t = tmp_path / agent_id
    t.mkdir()
    body = (
        "# Test Flow\n\nA test agent that drives a browser.\n\n"
        "- `steps/`: the flow's step files\n"
        "- `runs/`: run folders; `example/` shows the expected shape\n"
    )
    (t / "index.md").write_text(f"---\n{yaml.safe_dump(meta)}---\n\n{body}")
    steps = t / "steps"
    steps.mkdir()
    (steps / "index.md").write_text(
        "# Steps\n\nThe steps of the test flow.\n\n- `1-do.md`: do things\n"
    )
    (steps / "1-do.md").write_text("# Step 1\n")
    example = t / "runs" / "example"
    example.mkdir(parents=True)
    (example / "index.md").write_text("# Example\n\nA placeholder example run.\n")
    return t


def _catalog_tarball(entries):
    catalog = {"generated": "2026-08-12T12:00:00Z", "agents": entries}
    return _build_tarball([{"path": "registry.json", "content": json.dumps(catalog)}])


def test_share_agents_must_be_list_of_ids(registry, tmp_path):
    _, url = registry
    t = _template(tmp_path, agents=["Bad_ID!"])
    env = dict(os.environ, GCONTEXT_REGISTRY=url)
    result = run_cli("share", str(t), cwd=tmp_path, env=env)
    assert result.returncode == 1
    assert "agents" in result.stderr


def test_share_agents_self_dependency_rejected(registry, tmp_path):
    _, url = registry
    t = _template(tmp_path, agents=["test-flow"])
    env = dict(os.environ, GCONTEXT_REGISTRY=url)
    result = run_cli("share", str(t), cwd=tmp_path, env=env)
    assert result.returncode == 1
    assert "itself" in result.stderr


def test_share_agents_unknown_id_fails(registry, tmp_path):
    tarball_data, url = registry
    tarball_data[0] = _catalog_tarball([{"id": "dep-flow", "name": "Dep Flow"}])
    t = _template(tmp_path, agents=["ghost-flow"])
    env = dict(os.environ, GCONTEXT_REGISTRY=url)
    result = run_cli("share", str(t), cwd=tmp_path, env=env)
    assert result.returncode == 1
    assert "ghost-flow" in result.stderr


def test_share_agents_known_id_passes(registry, tmp_path):
    tarball_data, url = registry
    tarball_data[0] = _catalog_tarball([{"id": "dep-flow", "name": "Dep Flow"}])
    t = _template(tmp_path, agents=["dep-flow"])
    env = dict(os.environ, GCONTEXT_REGISTRY=url)
    result = run_cli("share", str(t), cwd=tmp_path, env=env)
    assert result.returncode == 0, result.stderr
    assert "validated agent test-flow" in result.stdout


def test_share_agents_offline_warns_and_passes(tmp_path):
    t = _template(tmp_path, agents=["dep-flow"])
    env = dict(os.environ, GCONTEXT_REGISTRY="http://127.0.0.1:9/registry.tar.gz")
    result = run_cli("share", str(t), cwd=tmp_path, env=env)
    assert result.returncode == 0, result.stderr
    assert "Warning" in result.stdout or "Warning" in result.stderr


def test_share_agents_cycle_rejected(registry, tmp_path):
    tarball_data, url = registry
    tarball_data[0] = _catalog_tarball(
        [{"id": "dep-flow", "name": "Dep Flow", "agents": ["test-flow"]}]
    )
    t = _template(tmp_path, agents=["dep-flow"])
    env = dict(os.environ, GCONTEXT_REGISTRY=url)
    result = run_cli("share", str(t), cwd=tmp_path, env=env)
    assert result.returncode == 1
    assert "cycle" in result.stderr.lower()
