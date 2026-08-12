"""Tests for scripts/build_registry.py: registry.json generation."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "build_registry", REPO_ROOT / "scripts" / "build_registry.py"
)
build_registry = importlib.util.module_from_spec(spec)
sys.modules["build_registry"] = build_registry
spec.loader.exec_module(build_registry)


def _agent(checkout, agent_id, extra_frontmatter=""):
    d = checkout / agent_id
    d.mkdir()
    (d / "index.md").write_text(
        f"---\nid: {agent_id}\nname: {agent_id.title()}\n"
        f"description: An agent.\ntags: [test]\n{extra_frontmatter}---\n\nBody.\n"
    )
    return d


def test_entry_carries_declared_agents(tmp_path):
    _agent(tmp_path, "growth-agent", "agents: [browser-cookbook]\n")
    _agent(tmp_path, "browser-cookbook")
    catalog = build_registry.build(tmp_path)
    by_id = {a["id"]: a for a in catalog["agents"]}
    assert by_id["growth-agent"]["agents"] == ["browser-cookbook"]


def test_entry_without_dependencies_has_no_agents_field(tmp_path):
    _agent(tmp_path, "browser-cookbook")
    catalog = build_registry.build(tmp_path)
    (entry,) = catalog["agents"]
    assert "agents" not in entry
