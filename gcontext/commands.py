"""Commands: files under `connections/*/commands/` and `modules/*/commands/`
exposed as MCP prompts.

Two file types (design ported from the maat-agent S13 spike). Both surface as
slash commands in Claude Code (`/mcp__<server>__<command>`); neither adds a
tool, so the tool list stays at the seven generic tools and the command text
enters context only when the user invokes it. A command's name is its bare
file stem with hyphens as underscores when that short name is unique; it
becomes `<owner>__<command>` (hyphens normalized the same way) when two
owners collide (all colliders get the prefix) or when the stem matches a
framework prompt name.

- `.md` (prompt command): the rendered body is injected into the conversation
  and the agent acts on it. `$name` placeholders are filled from the prompt
  arguments declared in the frontmatter.
- `.py` (script command): the injected text instructs the agent to execute the
  file through the generic `run_script` tool, passing the arguments as
  `params` (which the server turns into `PARAM_<NAME>` environment variables).

Commands are discovered once at server startup; restart to pick up new files.
One exception: a `.md` command whose frontmatter declares `each: <glob>` is a
template. It registers one prompt per state folder the glob matches inside its
owner, following the same naming rule as file commands (`<stem>_<match>` with
hyphens normalized to underscores; the owner prefix returns only on a name
collision; `$each` bound to the folder name), taking
description and parameters from frontmatter in the matched folder's index.md
when present (a parameter may declare `default: <value>`, which makes the
argument optional and is echoed in the appended Arguments line). Templates
re-expand after every write_file, so a new entry needs only a client
reconnect, not a server restart.
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


def _render_fn(body: str, params: list[dict[str, Any]], extra=None):
    """A render function whose signature carries the declared parameters, so
    FastMCP derives the prompt arguments (and rejects missing required ones).

    `extra` is an optional callable taking the invocation arguments and
    returning additional substitutions, computed at invocation time
    (server-filled placeholders like $setup_report and $explain_report,
    alongside the user-supplied ones like $request)."""

    def render(**kwargs: str) -> str:
        values = dict(kwargs)
        if extra is not None:
            values.update(extra(values))
        return Template(body).safe_substitute(**values)

    sig_params = [
        inspect.Parameter(
            p["name"],
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty
            if p.get("required", False)
            else str(p["default"]) if p.get("default") is not None else "",
            annotation=str,
        )
        for p in params
    ]
    render.__signature__ = inspect.Signature(sig_params)
    render.__annotations__ = {p["name"]: str for p in params} | {"return": str}
    return render


# Template expansion state, rebuilt by register_commands() at startup.
# GENERATED maps template file path -> {"owner_dir": str, "names": set[str]};
# _REGISTERED maps every registered prompt name to its source key ("framework"
# for reserved framework names, the file path for file commands, the template
# path for generated names), so generated names never shadow a real command
# file (files win) and re-registering the same file keeps its name.
GENERATED: dict[str, dict] = {}
_REGISTERED: dict[str, str] = {}


def _short_name(stem: str) -> str:
    return stem.replace("-", "_")


def _reserved_names() -> set[str]:
    """Framework prompt names; file commands never take these short names."""
    return {p.stem for p in discover_framework_prompts()}


def installed_setup_prompt(server_name: str, module_id: str) -> str:
    """Client invocation for a module's setup command.

    "setup" is a reserved framework stem, so a module's commands/setup.md
    always registers owner-prefixed; only the command part is underscored,
    the server name keeps its hyphens.
    """
    return f"/mcp__{server_name}__{_short_name(f'{module_id}__setup')}"


def _is_template(path: Path) -> bool:
    if path.suffix != ".md":
        return False
    try:
        meta, _ = parse_command(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, yaml.YAMLError):
        return False
    return "each" in meta


def _entry_frontmatter(index_path: Path) -> dict[str, Any] | None:
    """Frontmatter of a generated entry's index.md.

    Returns {} when the file is missing or has no frontmatter (the entry still
    registers with the template's own description), and None when frontmatter
    is present but malformed (the entry is skipped, loudly)."""
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if text.split("\n", 1)[0].strip() != FRONTMATTER_DELIM:
        return {}
    try:
        meta, _ = parse_command(text)
        return meta
    except (ValueError, yaml.YAMLError):
        return None


def _normalize_params(params: Any) -> list[dict[str, Any]] | None:
    """Validate a generated entry's parameter list.

    A parameter may declare `default: <scalar>`; a default makes the prompt
    argument optional regardless of `required`, because a value always exists.
    Returns None when the list is malformed (non-mapping items, missing name,
    non-scalar default), so the caller skips that entry loudly."""
    if not isinstance(params, list):
        return None
    out: list[dict[str, Any]] = []
    for p in params:
        if not isinstance(p, dict) or not p.get("name"):
            return None
        if "default" in p and p["default"] is not None:
            if isinstance(p["default"], (dict, list)):
                return None
            p = {**p, "required": False}
        out.append(p)
    return out


def _expand_template(mcp, root: Path, path: Path) -> int:
    """Register one prompt per folder matched by the template's `each` glob.

    Re-reads the template file so refresh_generated() picks up edits too.
    Returns the number of prompts registered."""
    from fastmcp.prompts.prompt import Prompt

    owner_dir = path.parent.parent
    owner = owner_dir.name
    try:
        meta, body = parse_command(path.read_text(encoding="utf-8"))
        pattern = str(meta["each"])
    except (ValueError, KeyError, OSError, yaml.YAMLError) as e:
        print(f"  ! skipping command {path}: {e}", file=sys.stderr)
        return 0
    if pattern.startswith("/") or ".." in Path(pattern).parts:
        print(f"  ! skipping command {path}: each glob must stay inside "
              f"{owner}/", file=sys.stderr)
        return 0

    names: set[str] = set()
    count = 0
    for match in sorted(owner_dir.glob(pattern)):
        if not match.is_dir():
            continue
        # Naming rule and picker rationale: see register_commands.
        short = f"{path.stem}_{match.name}".replace("-", "_")
        name = short if short not in _REGISTERED else _short_name(f"{owner}__{short}")
        entry_meta = _entry_frontmatter(match / "index.md")
        if entry_meta is None:
            print(f"  ! skipping generated command {name}: malformed "
                  f"frontmatter in {match / 'index.md'}", file=sys.stderr)
            continue
        if name in _REGISTERED:
            print(f"  ! skipping generated command {name}: name already "
                  "taken by a command file", file=sys.stderr)
            continue
        description = entry_meta.get("description") or meta.get("description", "")
        params = _normalize_params(entry_meta.get("parameters") or [])
        if params is None:
            print(f"  ! skipping generated command {name}: malformed "
                  f"parameters in {match / 'index.md'}", file=sys.stderr)
            continue
        entry_body = Template(body).safe_substitute(each=match.name)
        # A template cannot know the entry's parameter names, so any declared
        # parameter its body does not reference is appended explicitly;
        # otherwise the invocation values would never reach the agent.
        unreferenced = [
            p for p in params
            if f"${p['name']}" not in entry_body
            and "${%s}" % p["name"] not in entry_body
        ]
        if unreferenced:
            rendered = ", ".join(
                f'{p["name"]}: "${p["name"]}"'
                + (f' (default when empty: {p["default"]})'
                   if p.get("default") is not None else "")
                for p in unreferenced
            )
            entry_body += f"\n\nArguments: {rendered}"
        try:
            fn = _render_fn(entry_body, params)
            fn.__name__ = name
            mcp.add_prompt(
                Prompt.from_function(fn, name=name, description=description)
            )
        except Exception as e:
            print(f"  ! could not register prompt {name}: {e}", file=sys.stderr)
            continue
        _REGISTERED[name] = str(path)
        names.add(name)
        count += 1
    GENERATED[str(path)] = {"owner_dir": str(owner_dir), "names": names}
    return count


def _evict_generated(mcp, name: str) -> bool:
    """Remove a template-generated prompt so a command file can take its
    name (files win at runtime installs too, matching startup order).
    Returns True when a generated prompt held the name and was evicted."""
    info = GENERATED.get(_REGISTERED.get(name, ""))
    if info is None or name not in info["names"]:
        return False
    try:
        mcp._local_provider.remove_prompt(name)
    except Exception:
        pass
    _REGISTERED.pop(name, None)
    info["names"].discard(name)
    return True


def refresh_generated(mcp, root: Path, written_path: str) -> None:
    """Re-expand every template whose owner folder contains the written path.

    Called by the server after each successful write_file, so a new or changed
    entry is registered at runtime; the client sees it after a reconnect
    (Claude Code ignores prompts/list_changed, verified 2026-08-14)."""
    rel = written_path.strip("/")
    for template, info in list(GENERATED.items()):
        try:
            owner_rel = Path(info["owner_dir"]).relative_to(root).as_posix()
        except ValueError:
            continue
        if not rel.startswith(owner_rel + "/"):
            continue
        for name in info["names"]:
            try:
                mcp._local_provider.remove_prompt(name)
            except Exception:
                pass
            _REGISTERED.pop(name, None)
        _expand_template(mcp, root, Path(template))


def discover(root: Path) -> list[Path]:
    """Command files in registration order."""
    return sorted(
        p
        for pattern in COMMAND_GLOBS
        for p in root.glob(pattern)
        if p.suffix in (".md", ".py")
    )


_FRAMEWORK_SKIP = {"framework-instructions", "resources", "README"}


def discover_framework_prompts() -> list[Path]:
    """Framework-shipped prompt files (same filter as register_framework_prompts)."""
    prompts_dir = Path(__file__).parent / "prompts"
    return sorted(
        p for p in prompts_dir.glob("*.md") if p.stem not in _FRAMEWORK_SKIP
    )


def register_framework_prompts(mcp, root: Path | None = None) -> int:
    """Register the framework's own prompts, shipped in the package.

    Same file format as project commands, but framework-owned: they update
    with the package and exist in every instance (agents, ask, explain,
    setup).

    When `root` is given, the $setup_report and $explain_report
    placeholders are filled at invocation time with the code-built reports
    for that project; $explain_report uses the prompt's `agent` argument
    when one was passed.
    """
    from fastmcp.prompts.prompt import Prompt

    extra = None
    if root is not None:
        def extra(values):
            from .report import build_explain_report, build_setup_report
            return {
                "setup_report": build_setup_report(root),
                "explain_report": build_explain_report(root, values.get("agent") or None),
            }

    prompts_dir = Path(__file__).parent / "prompts"
    count = 0
    for path in sorted(prompts_dir.glob("*.md")):
        if path.stem in _FRAMEWORK_SKIP:
            continue
        meta, body = parse_command(path.read_text(encoding="utf-8"))
        fn = _render_fn(body, meta.get("parameters") or [], extra=extra)
        fn.__name__ = path.stem
        mcp.add_prompt(
            Prompt.from_function(fn, name=path.stem, description=meta.get("description", ""))
        )
        count += 1
    return count


def _register_one(mcp, root: Path, path: Path, name: str) -> bool:
    """Register a single command file as a prompt. Returns True on success."""
    from fastmcp.prompts.prompt import Prompt

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
        return False
    except Exception as e:
        print(f"  ! could not register prompt {name}: {e}", file=sys.stderr)
        return False
    _REGISTERED[name] = str(path)
    return True


def register_commands(mcp, root: Path) -> int:
    """Scan connection and module `commands/` folders and register each file
    as a prompt.

    Canonical naming rule, shared by file commands and template-generated
    commands (see _expand_template): the bare stem with hyphens as
    underscores when that short name is unique; `<owner>__<stem>` (hyphens
    normalized the same way) when two owners collide (all colliders get the
    prefix) or when the stem matches a framework prompt name. Short names
    matter because the client's slash-command picker scores the query against
    the full canonical name (mcp__<server>__<name>), so an owner prefix
    pushes real names over the score cliff, and hyphenated names drop out at
    hyphen word boundaries (both quirks probed against the real client,
    2026-08-14). Command files register first, templates (`each:`) expand
    after, so a file always wins a name clash."""
    GENERATED.clear()
    _REGISTERED.clear()
    _REGISTERED.update({n: "framework" for n in _reserved_names()})
    files: list[Path] = []
    templates: list[Path] = []
    for path in discover(root):
        (templates if _is_template(path) else files).append(path)
    shorts = [_short_name(p.stem) for p in files]
    dupes = {s for s in shorts if shorts.count(s) > 1}
    count = 0
    for path, short in zip(files, shorts):
        if short in dupes or short in _REGISTERED:
            name = _short_name(f"{path.parent.parent.name}__{path.stem}")
        else:
            name = short
        if name in _REGISTERED:
            print(f"  ! skipping command {path}: name {name} already "
                  "taken by another command file", file=sys.stderr)
            continue
        if _register_one(mcp, root, path, name):
            count += 1
    for path in templates:
        count += _expand_template(mcp, root, path)
    return count


def register_module_commands(mcp, root: Path, module_name: str) -> int:
    """Register commands for a single module (e.g. after install or update).

    Naming per command file, three branches: a name this file already holds
    is kept (re-registering replaces the prompt in place); otherwise the
    short name when it is free or held only by a template-generated prompt
    (the generated prompt is evicted, files win at runtime too); otherwise
    the owner-prefixed fallback."""
    commands_dir = root / "modules" / module_name / "commands"
    if not commands_dir.is_dir():
        return 0
    # Defense in depth: register_commands already seeds these into _REGISTERED.
    reserved = _reserved_names()
    count = 0
    templates: list[Path] = []
    for path in sorted(commands_dir.glob("*")):
        if path.suffix not in (".md", ".py"):
            continue
        if _is_template(path):
            templates.append(path)
            continue
        short = _short_name(path.stem)
        prefixed = _short_name(f"{module_name}__{path.stem}")
        src = str(path)
        if _REGISTERED.get(prefixed) == src:
            # previously registered prefixed (collision): keep the name stable
            name = prefixed
        elif _REGISTERED.get(short) == src or (
            short not in _REGISTERED and short not in reserved
        ):
            name = short
        elif _evict_generated(mcp, short):
            name = short
        else:
            name = prefixed
        if _register_one(mcp, root, path, name):
            count += 1
    for path in templates:
        count += _expand_template(mcp, root, path)
    return count
