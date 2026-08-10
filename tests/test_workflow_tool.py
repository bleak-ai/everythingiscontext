"""Tests for the workflow MCP tool: search, install, check, update."""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

from gcontext import registry as registry_mod, server, fs

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

BUNDLE_FILES = [
    {"path": "index.md", "content": INDEX_MD},
    {"path": "steps/index.md", "content": "1-sync.md: sync things\n"},
    {"path": "steps/1-sync.md", "content": "# Step 1\n\nSync.\n"},
    {"path": "commands/setup.md", "content": SETUP_MD},
    {"path": "runs/example/index.md", "content": "# Example run\n"},
]

CATALOG = {
    "generated": "2026-08-10T12:00:00Z",
    "workflows": [
        {
            "id": "demo-flow",
            "name": "Demo Flow",
            "description": "A tiny demo workflow for tests.",
            "tags": ["demo"],
            "files": [f["path"] for f in BUNDLE_FILES],
        },
        {
            "id": "ops-flow",
            "name": "Ops Flow",
            "description": "An operations workflow.",
            "tags": ["ops", "infra"],
            "files": ["index.md"],
        },
    ],
}


def _build_tarball(files, prefix="workflows-main"):
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


def _registry_files(workflow_id="demo-flow"):
    return [{"path": f"{workflow_id}/{f['path']}", "content": f["content"]} for f in BUNDLE_FILES]


def _file_hash(content):
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


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


def _tarball_with_catalog(extra_files=None):
    files = _registry_files()
    catalog_content = json.dumps(CATALOG)
    files.append({"path": "registry.json", "content": catalog_content})
    if extra_files:
        files.extend(extra_files)
    return _build_tarball(files)


# --- Search tests ---

def test_search_returns_all(registry, project):
    registry[0] = _tarball_with_catalog()
    result = server.workflow(action="search")
    assert "demo-flow" in result
    assert "ops-flow" in result


def test_search_filters_by_query(registry, project):
    registry[0] = _tarball_with_catalog()
    result = server.workflow(action="search", query="demo")
    assert "demo-flow" in result
    assert "ops-flow" not in result


def test_search_case_insensitive(registry, project):
    registry[0] = _tarball_with_catalog()
    result = server.workflow(action="search", query="DEMO")
    assert "demo-flow" in result


def test_search_no_match(registry, project):
    registry[0] = _tarball_with_catalog()
    result = server.workflow(action="search", query="nomatch")
    assert "No workflows match" in result


def test_search_without_catalog_errors(registry, project):
    registry[0] = _build_tarball(_registry_files())
    result = server.workflow(action="search")
    assert result.startswith("Error:")
    assert "registry.json" in result


# --- Install tests ---

def test_install_creates_module_and_manifest(registry, project):
    registry[0] = _tarball_with_catalog()
    result = server.workflow(action="install", id="demo-flow")
    assert "Demo Flow" in result
    assert "commands/setup.md" in result

    module = project / "modules" / "demo-flow"
    assert (module / "index.md").exists()
    assert (module / "steps" / "1-sync.md").exists()

    manifest = yaml.safe_load((module / ".template.yaml").read_text())
    assert manifest["template"] == "demo-flow"
    assert manifest["installed_ref"] == "unknown"
    for f in BUNDLE_FILES:
        assert manifest["files"][f["path"]] == _file_hash(f["content"])


def test_install_existing_module_refuses(registry, project):
    marker = project / "modules" / "demo-flow" / "personal.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("mine")
    registry[0] = _tarball_with_catalog()
    result = server.workflow(action="install", id="demo-flow")
    assert result.startswith("Error:")
    assert "already exists" in result
    assert marker.read_text() == "mine"


def test_install_missing_id(registry, project):
    result = server.workflow(action="install")
    assert result.startswith("Error:")
    assert "needs an id" in result


def test_unknown_action(registry, project):
    result = server.workflow(action="frobnicate")
    assert result.startswith("Error:")
    assert "unknown action" in result


# --- Hidden manifest tests ---

def test_template_manifest_hidden_from_list_dir(project):
    mod = project / "modules" / "demo"
    mod.mkdir(parents=True)
    (mod / ".template.yaml").write_text("template: demo\n")
    (mod / "index.md").write_text("# demo\n")
    result = fs.list_dir(project, "modules/demo")
    assert "index.md" in result
    assert ".template.yaml" not in result


def test_template_manifest_hidden_from_grep(project):
    mod = project / "modules" / "demo"
    mod.mkdir(parents=True)
    (mod / ".template.yaml").write_text("template: demo\n")
    (mod / "index.md").write_text("# demo\n")
    result = fs.grep(project, "template", "modules")
    assert ".template.yaml" not in result


def test_template_manifest_hidden_from_walk(project):
    mod = project / "modules" / "demo"
    mod.mkdir(parents=True)
    (mod / ".template.yaml").write_text("template: demo\n")
    (mod / "index.md").write_text("# demo\n")
    walked = fs.walk_files(project)
    assert not any(".template.yaml" in p for p in walked)


def test_template_manifest_still_readable(project):
    mod = project / "modules" / "demo"
    mod.mkdir(parents=True)
    (mod / ".template.yaml").write_text("template: demo\n")
    result = fs.read_file(project, "modules/demo/.template.yaml")
    assert "template: demo" in result


def test_index_warning_ignores_template_manifest(project):
    mod = project / "modules" / "demo"
    mod.mkdir(parents=True)
    (mod / ".template.yaml").write_text("template: demo\n")
    (mod / "steps").mkdir()
    result = fs.write_file(project, "modules/demo/index.md", "# demo\n\n- [steps](steps/)\n")
    assert ".template.yaml" not in result


# --- Check tests ---

def test_check_up_to_date(registry, project):
    registry[0] = _tarball_with_catalog()
    server.workflow(action="install", id="demo-flow")
    result = server.workflow(action="check", id="demo-flow")
    assert "up to date" in result


def test_check_detects_changes(registry, project):
    registry[0] = _tarball_with_catalog()
    server.workflow(action="install", id="demo-flow")

    modified_step = "# Step 1 MODIFIED\n\nNew sync.\n"
    modified_files = []
    for f in BUNDLE_FILES:
        if f["path"] == "steps/1-sync.md":
            modified_files.append({"path": f["path"], "content": modified_step})
        else:
            modified_files.append(f)
    new_registry = _registry_files_from(modified_files)
    new_registry.append({"path": "registry.json", "content": json.dumps(CATALOG)})
    registry[0] = _build_tarball(new_registry)

    (project / "modules" / "demo-flow" / "commands" / "setup.md").write_text("local edit")

    result = server.workflow(action="check", id="demo-flow")
    assert "upstream changed" in result
    assert "locally modified" in result


def test_check_nonexistent_module(registry, project):
    result = server.workflow(action="check", id="nope")
    assert result.startswith("Error:")
    assert "does not exist" in result


def test_check_all_no_tracked(registry, project):
    result = server.workflow(action="check")
    assert "No installed workflows" in result


# --- Update tests ---

def test_update_applies_three_way(registry, project):
    registry[0] = _tarball_with_catalog()
    server.workflow(action="install", id="demo-flow")

    (project / "modules" / "demo-flow" / "commands" / "setup.md").write_text("local edit")

    new_step = "# Step 1 UPDATED\n"
    new_index = INDEX_MD.replace("Objective paragraph.", "Updated objective.")
    modified_files = []
    for f in BUNDLE_FILES:
        if f["path"] == "steps/1-sync.md":
            modified_files.append({"path": f["path"], "content": new_step})
        elif f["path"] == "index.md":
            modified_files.append({"path": f["path"], "content": new_index})
        else:
            modified_files.append(f)
    modified_files.append({"path": "steps/2-verify.md", "content": "# Verify\n"})

    new_registry = _registry_files_from(modified_files)
    new_registry.append({"path": "registry.json", "content": json.dumps(CATALOG)})
    registry[0] = _build_tarball(new_registry)

    (project / "modules" / "demo-flow" / "index.md").write_text(
        INDEX_MD.replace("Objective paragraph.", "My local objective.")
    )

    result = server.workflow(action="update", id="demo-flow")

    assert (project / "modules" / "demo-flow" / "steps" / "1-sync.md").read_text() == new_step
    assert (project / "modules" / "demo-flow" / "commands" / "setup.md").read_text() == "local edit"
    assert (project / "modules" / "demo-flow" / "index.md.new").exists()
    assert (project / "modules" / "demo-flow" / "steps" / "2-verify.md").exists()
    assert "Conflicts" in result or "conflicts" in result.lower()


def test_update_without_manifest_errors(registry, project):
    mod = project / "modules" / "handmade"
    mod.mkdir(parents=True)
    (mod / "index.md").write_text("# handmade\n")
    result = server.workflow(action="update", id="handmade")
    assert result.startswith("Error:")
    assert ".template.yaml" in result


def test_update_missing_id(registry, project):
    result = server.workflow(action="update")
    assert result.startswith("Error:")
    assert "needs an id" in result


# --- CLI wrapper tests ---

def _run_cli(*args, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-m", "gcontext.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def test_cli_search(registry, tmp_path):
    registry[0] = _tarball_with_catalog()
    agent = tmp_path / "a"
    _run_cli("init", "a", cwd=tmp_path)
    result = _run_cli("search", "demo", cwd=agent)
    assert result.returncode == 0
    assert "demo-flow" in result.stdout


def test_cli_update_up_to_date(registry, tmp_path):
    registry[0] = _tarball_with_catalog()
    agent = tmp_path / "a"
    _run_cli("init", "a", cwd=tmp_path)
    _run_cli("add", "demo-flow", cwd=agent)
    result = _run_cli("update", "demo-flow", cwd=agent)
    assert result.returncode == 0
    assert "up to date" in result.stdout


def test_cli_update_unknown_module(registry, tmp_path):
    registry[0] = _tarball_with_catalog()
    agent = tmp_path / "a"
    _run_cli("init", "a", cwd=tmp_path)
    result = _run_cli("update", "nope", cwd=agent)
    assert result.returncode == 1
    assert "Error:" in result.stderr


# --- Helpers ---

def _registry_files_from(bundle_files, workflow_id="demo-flow"):
    return [{"path": f"{workflow_id}/{f['path']}", "content": f["content"]} for f in bundle_files]
