import os

import yaml

from gcontext.flows import flow_board, load_flows, step_state
from gcontext.models import FlowStep

FLOW = {
    "name": "f",
    "steps": [
        {"id": "capture", "produces": ["brief.md"]},
        {"id": "draft", "needs": ["brief.md"], "produces": ["draft.md"]},
    ],
}


def make_flow(project, data=FLOW):
    d = project / "flows" / data["name"]
    d.mkdir(parents=True)
    (d / "flow.yaml").write_text(yaml.safe_dump(data))


def test_load_flows(tmp_path):
    make_flow(tmp_path)
    flows = load_flows(tmp_path)
    assert list(flows) == ["f"]
    assert [s.id for s in flows["f"].steps] == ["capture", "draft"]


def test_no_needs_is_ready(tmp_path):
    state = step_state(tmp_path, FlowStep(id="s", produces=["out.md"]))
    assert state["status"] == "ready"
    assert state["missing"] == ["out.md"]


def test_blocked_then_ready_then_done(tmp_path):
    step = FlowStep(id="s", needs=["brief.md"], produces=["draft.md"])

    state = step_state(tmp_path, step)
    assert state["status"] == "blocked"
    assert state["missing"] == ["brief.md"]

    (tmp_path / "brief.md").write_text("brief")
    assert step_state(tmp_path, step)["status"] == "ready"

    (tmp_path / "draft.md").write_text("draft")
    assert step_state(tmp_path, step)["status"] == "done"


def test_stale_when_need_changes_after_produce(tmp_path):
    step = FlowStep(id="s", needs=["brief.md"], produces=["draft.md"])
    brief = tmp_path / "brief.md"
    draft = tmp_path / "draft.md"
    brief.write_text("brief")
    draft.write_text("draft")

    now = draft.stat().st_mtime
    os.utime(brief, (now + 10, now + 10))

    state = step_state(tmp_path, step)
    assert state["status"] == "stale"
    assert state["stale_needs"] == ["brief.md"]


def test_board_statuses(tmp_path):
    make_flow(tmp_path)
    flow = load_flows(tmp_path)["f"]
    assert [s["status"] for s in flow_board(tmp_path, flow)] == ["ready", "blocked"]

    (tmp_path / "brief.md").write_text("brief")
    assert [s["status"] for s in flow_board(tmp_path, flow)] == ["done", "ready"]
