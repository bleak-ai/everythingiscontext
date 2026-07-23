"""Flows: declarative information dependencies, computed from the filesystem.

A flow is data, not a program. Each step declares which files it needs and
which files it produces. Status is a pure function of the filesystem:

  blocked  some needed file does not exist yet
  ready    all needs exist, some produced file is missing
  stale    everything exists, but a need is newer than a produce (make semantics)
  done     all produces exist and are up to date

gcontext never executes a step. A runtime completes a step by writing the
declared produces (write_context, or any editor); status recomputes from the
files on the next read. There is no run state stored anywhere else.
"""

from pathlib import Path

import yaml

from .models import FlowManifest, FlowStep


def load_flows(project_dir: Path) -> dict[str, FlowManifest]:
    """Scan flows/ for subdirectories containing flow.yaml."""
    flows_dir = project_dir / "flows"
    if not flows_dir.is_dir():
        return {}
    result = {}
    for item in sorted(flows_dir.iterdir()):
        flow_file = item / "flow.yaml"
        if not item.is_dir() or not flow_file.exists():
            continue
        data = yaml.safe_load(flow_file.read_text()) or {}
        manifest = FlowManifest(**data)
        result[manifest.name] = manifest
    return result


def step_state(project_dir: Path, step: FlowStep) -> dict:
    """Compute a step's status purely from the files it declares."""
    needs = [(p, project_dir / p) for p in step.needs]
    produces = [(p, project_dir / p) for p in step.produces]

    missing_needs = [p for p, f in needs if not f.is_file()]
    if missing_needs:
        return {"status": "blocked", "missing": missing_needs}

    missing_produces = [p for p, f in produces if not f.is_file()]
    if missing_produces:
        return {"status": "ready", "missing": missing_produces}

    if needs and produces:
        oldest_produce = min(f.stat().st_mtime for _, f in produces)
        stale_needs = [p for p, f in needs if f.stat().st_mtime > oldest_produce]
        if stale_needs:
            return {"status": "stale", "stale_needs": stale_needs}

    return {"status": "done"}


def flow_board(project_dir: Path, flow: FlowManifest) -> list[dict]:
    """Every step of a flow with its computed state."""
    board = []
    for step in flow.steps:
        state = step_state(project_dir, step)
        board.append({
            "id": step.id,
            "description": step.description,
            "needs": step.needs,
            "produces": step.produces,
            "instructions": step.instructions,
            **state,
        })
    return board


def actionable(board: list[dict]) -> list[dict]:
    return [s for s in board if s["status"] in ("ready", "stale")]


def render_flow(project_dir: Path, flow: FlowManifest, with_instructions: bool = True) -> list[str]:
    """Plain-text board for one flow. Instructions surface only for actionable steps."""
    board = flow_board(project_dir, flow)
    done = sum(1 for s in board if s["status"] == "done")

    lines = [f"## {flow.name} ({done}/{len(board)} done)"]
    if flow.description:
        lines.append(flow.description)
    lines.append("")

    for step in board:
        lines.append(f"- [{step['status']}] {step['id']}: {step['description']}")
        if step["needs"]:
            lines.append(f"    needs: {', '.join(step['needs'])}")
        if step["produces"]:
            lines.append(f"    produces: {', '.join(step['produces'])}")
        if step["status"] == "blocked":
            lines.append(f"    waiting on: {', '.join(step['missing'])}")
        if step["status"] == "stale":
            lines.append(f"    stale: {', '.join(step['stale_needs'])} changed after the produces were written")

    ready = actionable(board)
    if ready and with_instructions:
        lines.append("")
        lines.append("Actionable now:")
        for step in ready:
            lines.append(f"### {step['id']}")
            if step["instructions"]:
                lines.append(step["instructions"].rstrip())
            missing = step.get("missing") or step["produces"]
            lines.append(f"Complete it by writing: {', '.join(missing)}")

    return lines
