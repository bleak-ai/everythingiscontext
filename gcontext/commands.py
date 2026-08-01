"""Commands: files under `connections/*/commands/` and `modules/*/commands/`
exposed as MCP prompts.

Two file types (design ported from the maat-agent S13 spike). Both surface as
slash commands in Claude Code (`/mcp__<server>__<owner>__<command>`); neither
adds a tool, so the tool list stays at the six generic tools and the command
text enters context only when the user invokes it.

- `.md` (prompt command): the rendered body is injected into the conversation
  and the agent acts on it. `$name` placeholders are filled from the prompt
  arguments declared in the frontmatter.
- `.py` (script command): the injected text instructs the agent to execute the
  file through the generic `run_script` tool, passing the arguments as
  `params` (which the server turns into `PARAM_<NAME>` environment variables).

Commands are discovered once at server startup; restart to pick up new files.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from string import Template
from typing import Any

import yaml

FRONTMATTER_DELIM = "---"
COMMAND_GLOBS = ("connections/*/commands/*", "modules/*/commands/*")


def parse_command(text: str) -> tuple[dict[str, Any], str]:
    """Split a `.md` command file into (frontmatter, body).

    The file must start with a `---` YAML block. Raises ValueError otherwise,
    so a malformed file fails loudly at startup instead of silently missing
    from the prompt list.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError("missing frontmatter: file must start with ---")
    try:
        end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() == FRONTMATTER_DELIM)
    except StopIteration:
        raise ValueError("unterminated frontmatter: no closing ---")
    meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    body = "\n".join(lines[end + 1 :]).strip()
    return meta, body


def parse_script_command(text: str) -> dict[str, Any]:
    """Read the frontmatter of a `.py` command: a `# ---` comment block at the top.

    # ---
    # description: ...
    # parameters:
    #   - name: email
    #     required: true
    # ---
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != f"# {FRONTMATTER_DELIM}":
        raise ValueError("missing frontmatter: file must start with # ---")
    block: list[str] = []
    for line in lines[1:]:
        if line.strip() == f"# {FRONTMATTER_DELIM}":
            meta = yaml.safe_load("\n".join(block)) or {}
            if not isinstance(meta, dict):
                raise ValueError("frontmatter must be a YAML mapping")
            return meta
        if not line.startswith("#"):
            raise ValueError("non-comment line inside frontmatter block")
        block.append(line[1:].removeprefix(" "))
    raise ValueError("unterminated frontmatter: no closing # ---")


def _script_prompt_body(rel_path: str, meta: dict[str, Any]) -> str:
    """The injected text for a script command invoked as a slash command."""
    params = meta.get("parameters") or []
    if params:
        rendered = ", ".join(f'"{p["name"]}": "${p["name"]}"' for p in params)
        params_line = f" and params {{{rendered}}}"
    else:
        params_line = ""
    return (
        f"Execute the script command `{rel_path}`: call the `run_script` tool "
        f"with path `{rel_path}`{params_line}, then report its output to the "
        "user. Do not read or rewrite the script first; run it as is."
    )


def _render_fn(body: str, params: list[dict[str, Any]]):
    """A render function whose signature carries the declared parameters, so
    FastMCP derives the prompt arguments (and rejects missing required ones)."""

    def render(**kwargs: str) -> str:
        return Template(body).safe_substitute(**kwargs)

    sig_params = [
        inspect.Parameter(
            p["name"],
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty if p.get("required", False) else "",
            annotation=str,
        )
        for p in params
    ]
    render.__signature__ = inspect.Signature(sig_params)
    render.__annotations__ = {p["name"]: str for p in params} | {"return": str}
    return render


def discover(root: Path) -> list[Path]:
    """Command files in registration order."""
    return sorted(
        p
        for pattern in COMMAND_GLOBS
        for p in root.glob(pattern)
        if p.suffix in (".md", ".py")
    )


def register_framework_prompts(mcp) -> int:
    """Register the framework's own prompts, shipped in the package.

    Same file format as project commands, but framework-owned: they update
    with the package and exist in every instance. Currently one: `setup`,
    the guided add-a-connection / add-a-module / health-check flow.
    """
    from fastmcp.prompts.prompt import Prompt

    prompts_dir = Path(__file__).parent / "prompts"
    count = 0
    for path in sorted(prompts_dir.glob("*.md")):
        if path.stem in ("framework-instructions", "resources", "README"):
            continue
        meta, body = parse_command(path.read_text(encoding="utf-8"))
        fn = _render_fn(body, meta.get("parameters") or [])
        fn.__name__ = path.stem
        mcp.add_prompt(
            Prompt.from_function(fn, name=path.stem, description=meta.get("description", ""))
        )
        count += 1
    return count


def register_commands(mcp, root: Path) -> int:
    """Scan connection and module `commands/` folders and register each file
    as a prompt named `<owner>__<command>`."""
    from fastmcp.prompts.prompt import Prompt

    count = 0
    for path in discover(root):
        owner = path.parent.parent.name
        name = f"{owner}__{path.stem}"
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".md":
                meta, body = parse_command(text)
            else:
                meta = parse_script_command(text)
                body = _script_prompt_body(str(path.relative_to(root)), meta)
            fn = _render_fn(body, meta.get("parameters") or [])
            fn.__name__ = name
            mcp.add_prompt(
                Prompt.from_function(fn, name=name, description=meta.get("description", ""))
            )
        except (ValueError, KeyError, yaml.YAMLError) as e:
            print(f"  ! skipping command {path}: {e}", file=sys.stderr)
            continue
        count += 1
    return count
