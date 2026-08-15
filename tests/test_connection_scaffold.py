"""Tests for connection validation and scaffolding on install (friction fixes WU1)."""

from pathlib import Path

import pytest
import yaml

from gcontext import registry as registry_mod


def _bundle(frontmatter_extra=""):
    index = (
        "---\n"
        "id: demo-flow\n"
        "name: Demo Flow\n"
        "description: A tiny demo agent for tests.\n"
        "tags: [demo]\n"
        f"{frontmatter_extra}"
        "---\n\nBody.\n"
    )
    return [{"path": "index.md", "content": index}]


# --- validate_bundle: connections key ---

def test_no_connections_key_is_valid():
    meta = registry_mod.validate_bundle(_bundle())
    assert "connections" not in meta


def test_valid_connections_pass():
    meta = registry_mod.validate_bundle(_bundle(
        "connections:\n"
        "  - kind: browser\n"
        "    description: A browser.\n"
        "    examples: [Chrome CDP]\n"
        "    deps: [playwright]\n"
        "    secrets: [BROWSER_TOKEN]\n"
    ))
    assert meta["connections"][0]["kind"] == "browser"


def test_connections_not_a_list_fails():
    with pytest.raises(ValueError, match="'connections' must be a list"):
        registry_mod.validate_bundle(_bundle("connections: browser\n"))


def test_connection_entry_not_a_dict_fails():
    with pytest.raises(ValueError, match=r"connections\[0\]"):
        registry_mod.validate_bundle(_bundle("connections: [browser]\n"))


def test_connection_missing_kind_fails():
    with pytest.raises(ValueError, match=r"connections\[0\]: missing 'kind'"):
        registry_mod.validate_bundle(_bundle(
            "connections:\n  - description: no kind here\n"
        ))


def test_connection_unknown_kind_fails_with_valid_list():
    with pytest.raises(ValueError, match=r"connections\[0\]: unknown kind 'browsers' \(valid: .*browser.*\)"):
        registry_mod.validate_bundle(_bundle("connections:\n  - kind: browsers\n"))


def test_connection_bad_deps_type_fails():
    with pytest.raises(ValueError, match=r"connections\[0\]: 'deps' must be a list of strings"):
        registry_mod.validate_bundle(_bundle(
            "connections:\n  - kind: browser\n    deps: playwright\n"
        ))


def test_second_bad_entry_reports_its_index():
    with pytest.raises(ValueError, match=r"connections\[1\]"):
        registry_mod.validate_bundle(_bundle(
            "connections:\n  - kind: browser\n  - kind: nonsense\n"
        ))


# --- scaffold_connections ---

BROWSER_META = {
    "id": "demo-flow",
    "connections": [
        {
            "kind": "browser",
            "description": "A browser over CDP.",
            "deps": ["playwright"],
            "secrets": ["BROWSER_TOKEN"],
        }
    ],
}


def test_scaffold_no_connections_is_noop(tmp_path):
    assert registry_mod.scaffold_connections(tmp_path, {"id": "x"}) == []
    assert not (tmp_path / "connections").exists()


def test_scaffold_creates_stub(tmp_path):
    report = registry_mod.scaffold_connections(tmp_path, BROWSER_META)
    assert report == [
        {"kind": "browser", "status": "created", "path": "connections/browser"}
    ]
    manifest = yaml.safe_load(
        (tmp_path / "connections" / "browser" / "connection.yaml").read_text()
    )
    assert manifest == {
        "name": "browser",
        "description": "A browser over CDP.",
        "kind": "browser",
        "secrets": ["BROWSER_TOKEN"],
        "deps": ["playwright"],
    }
    index = (tmp_path / "connections" / "browser" / "index.md").read_text()
    assert index.startswith("# browser\n")
    assert "Stub created on install of demo-flow." in index
    assert "connection.yaml:" in index


def test_scaffold_defaults_empty_fields(tmp_path):
    report = registry_mod.scaffold_connections(
        tmp_path, {"id": "x", "connections": [{"kind": "browser"}]}
    )
    assert report[0]["status"] == "created"
    manifest = yaml.safe_load(
        (tmp_path / "connections" / "browser" / "connection.yaml").read_text()
    )
    assert manifest["description"] == ""
    assert manifest["secrets"] == []
    assert manifest["deps"] == []


def test_scaffold_skips_existing_kind_under_other_name(tmp_path):
    conn = tmp_path / "connections" / "my-chrome"
    conn.mkdir(parents=True)
    (conn / "connection.yaml").write_text("name: my-chrome\nkind: browser\n")
    report = registry_mod.scaffold_connections(tmp_path, BROWSER_META)
    assert report[0]["status"] == "exists"
    assert not (tmp_path / "connections" / "browser").exists()


def test_scaffold_never_touches_existing_folder(tmp_path):
    conn = tmp_path / "connections" / "browser"
    conn.mkdir(parents=True)
    (conn / "notes.md").write_text("mine\n")
    report = registry_mod.scaffold_connections(tmp_path, BROWSER_META)
    assert report[0]["status"] == "exists"
    assert not (conn / "connection.yaml").exists()
    assert (conn / "notes.md").read_text() == "mine\n"


def test_scaffold_same_kind_twice_second_reports_exists(tmp_path):
    first = registry_mod.scaffold_connections(tmp_path, BROWSER_META)
    second = registry_mod.scaffold_connections(
        tmp_path, {"id": "other", "connections": [{"kind": "browser"}]}
    )
    assert first[0]["status"] == "created"
    assert second[0]["status"] == "exists"


# --- install_agent integration (registry over local HTTP, as in test_agent_tool.py) ---

import io
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from gcontext import server


INDEX_WITH_CONNECTION = """---
id: demo-flow
name: Demo Flow
description: A tiny demo agent for tests.
tags: [demo]
connections:
  - kind: browser
    description: A browser over CDP.
    deps: [playwright]
    secrets: [BROWSER_TOKEN]
---

Body.
"""


def _build_tarball(files, prefix="agents-main"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in files:
            data = f["content"].encode("utf-8")
            info = tarfile.TarInfo(name=f"{prefix}/{f['path']}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


@pytest.fixture
def registry(monkeypatch):
    tarball_data = [None]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.end_headers()
            self.wfile.write(tarball_data[0])

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv(
        "GCONTEXT_REGISTRY", f"http://127.0.0.1:{srv.server_port}/registry.tar.gz"
    )
    yield tarball_data
    srv.shutdown()


@pytest.fixture
def project(tmp_path, monkeypatch):
    p = tmp_path / "agent"
    p.mkdir()
    (p / "gcontext.yaml").write_text("name: test-agent\n")
    (p / "modules").mkdir()
    (p / "connections").mkdir()
    monkeypatch.setattr(server, "PROJECT_DIR", p)
    return p


def test_install_scaffolds_declared_connection(registry, project):
    registry[0] = _build_tarball(
        [{"path": "demo-flow/index.md", "content": INDEX_WITH_CONNECTION}]
    )
    result = server.agent(action="install", id="demo-flow")
    assert "Created connection stub connections/browser/" in result
    manifest = yaml.safe_load(
        (project / "connections" / "browser" / "connection.yaml").read_text()
    )
    assert manifest["kind"] == "browser"
    assert manifest["deps"] == ["playwright"]
    assert (project / "connections" / "browser" / "index.md").exists()


def test_install_reports_existing_connection(registry, project):
    conn = project / "connections" / "browser"
    conn.mkdir(parents=True)
    original = "name: browser\nkind: browser\ndeps: [playwright]\n"
    (conn / "connection.yaml").write_text(original)
    registry[0] = _build_tarball(
        [{"path": "demo-flow/index.md", "content": INDEX_WITH_CONNECTION}]
    )
    result = server.agent(action="install", id="demo-flow")
    assert "Connection browser already exists; the module uses it." in result
    assert (conn / "connection.yaml").read_text() == original


def test_install_bad_kind_writes_nothing(registry, project):
    bad = INDEX_WITH_CONNECTION.replace("kind: browser", "kind: nonsense")
    registry[0] = _build_tarball([{"path": "demo-flow/index.md", "content": bad}])
    result = server.agent(action="install", id="demo-flow")
    assert result.startswith("Error:")
    assert "unknown kind 'nonsense'" in result
    assert not (project / "modules" / "demo-flow").exists()
    assert not (project / "connections" / "nonsense").exists()


def test_install_without_connections_has_no_connection_lines(registry, project):
    plain = (
        "---\nid: demo-flow\nname: Demo Flow\n"
        "description: A tiny demo agent for tests.\ntags: [demo]\n---\n\nBody.\n"
    )
    registry[0] = _build_tarball([{"path": "demo-flow/index.md", "content": plain}])
    result = server.agent(action="install", id="demo-flow")
    assert "connection" not in result.lower()
