"""controls.yaml: the full registry of everything the server exposes.

Disk is the source of what exists; controls.yaml is the authoritative on/off
overlay, healed to completeness: every disk item gets a line, appended as
auto for commands and on for resources.
Design decisions: docs/controls-registry-spec.md in the lab repo.

Key scheme:
- commands: "<owner>/<stem>". Framework prompts use owner "framework". A
  template (`each:`) file gets ONE line; a generated entry can be overridden
  by a hand-written "<owner>/<template-stem>_<entry>" line. Values are
  three-state: on (always), off (never), auto (follow the owner cascade).
- resources: "modules/<name>", "connections/<name>", "agents/<name>".
  agents/<name> never reaches the picker; the line exists only so the
  whole-owner cascade covers the agent's commands. Values are strictly
  on/off.

Enablement chain for a command: explicit on/off command entry > template
entry (for generated commands, when not auto) > owner resource entry (when
the command entry is auto) > on. Pins are independent of owner state.
Unlisted anything is on (the heal adds the line, auto for commands).

Failure handling: parse errors raise ControlsError. The server fails loud at
startup and keeps the last good registry at request time. Duplicate keys
resolve off-wins. Heal writes are atomic (temp file + os.replace) under a
lock file and append-only for existing content, so hand-written comments and
ordering survive.
"""

from __future__ import annotations

import fnmatch
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:
    import fcntl
except ImportError:  # Windows: no flock; atomic replace still applies
    fcntl = None

FRAMEWORK_SKIP = {"framework-instructions", "resources", "README"}
COMMAND_GLOBS = (
    "connections/*/commands/*", "modules/*/commands/*", "agents/*/commands/*"
)
OWNER_KINDS = ("modules", "connections", "agents")
OLD_KEYS = {"hidden_commands", "hidden_resources", "pinned_resources"}


class ControlsError(Exception):
    """controls.yaml is unreadable as a registry."""


@dataclass
class Registry:
    # Command values are three-state: True (on, always), False (off, never),
    # None (auto, follow the owner cascade). Resources stay strictly bool.
    commands: dict[str, bool | None] = field(default_factory=dict)
    resources: dict[str, bool] = field(default_factory=dict)
    pinned: list[str] = field(default_factory=list)


class _DupLoader(yaml.SafeLoader):
    """SafeLoader whose mappings resolve duplicate keys off-wins."""


def _construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        value = loader.construct_object(value_node, deep=deep)
        if key in mapping and (mapping[key] is False or value is False):
            mapping[key] = False
        else:
            mapping[key] = value
    return mapping


_DupLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _load_yaml(path: Path) -> dict | None:
    """Raw mapping from *path*. None when the file is missing.
    Raises ControlsError on malformed yaml or a non-mapping document."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.load(text, Loader=_DupLoader)
    except yaml.YAMLError as e:
        raise ControlsError(f"controls.yaml is not valid YAML: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ControlsError("controls.yaml must be a YAML mapping")
    return data


def parse(path: Path) -> Registry | None:
    """The registry in *path*. None when the file is missing.
    Raises ControlsError on malformed content."""
    data = _load_yaml(path)
    if data is None:
        return None

    def section(name: str, allow_auto: bool = False) -> dict[str, bool | None]:
        raw = data.get(name)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ControlsError(f"'{name}' must be a mapping of key: on|off")
        out: dict[str, bool | None] = {}
        for k, v in raw.items():
            if allow_auto and isinstance(v, str) and v == "auto":
                out[str(k)] = None
                continue
            if not isinstance(v, bool):
                raise ControlsError(
                    f"'{name}' entry '{k}' must be on, off"
                    + (" or auto" if allow_auto else "")
                    + f", got {v!r}"
                )
            out[str(k)] = v
        return out

    raw_pinned = data.get("pinned")
    if raw_pinned is None:
        pinned: list[str] = []
    elif isinstance(raw_pinned, list):
        pinned = [str(v) for v in raw_pinned]
    else:
        raise ControlsError("'pinned' must be a list")
    return Registry(
        commands=section("commands", allow_auto=True),
        resources=section("resources"),
        pinned=pinned,
    )


def _framework_keys() -> list[str]:
    prompts_dir = Path(__file__).parent / "prompts"
    return sorted(
        f"framework/{p.stem}"
        for p in prompts_dir.glob("*.md")
        if p.stem not in FRAMEWORK_SKIP
    )


def inventory(root: Path) -> tuple[list[str], list[str]]:
    """(command keys, resource keys) discovered on disk, both sorted.

    A template file yields one key like any plain command file; generated
    entries never appear (per-entry lines are hand-written overrides only)."""
    cmds = set(_framework_keys())
    for pattern in COMMAND_GLOBS:
        for p in root.glob(pattern):
            if p.suffix in (".md", ".py"):
                cmds.add(f"{p.parent.parent.name}/{p.stem}")
    res: set[str] = set()
    for kind in OWNER_KINDS:
        base = root / kind
        if base.is_dir():
            for d in base.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    res.add(f"{kind}/{d.name}")
    return sorted(cmds), sorted(res)


def owner_resource_key(root: Path, owner: str) -> str | None:
    """The resource key of a command owner, from its folder on disk."""
    for kind in OWNER_KINDS:
        if (root / kind / owner).is_dir():
            return f"{kind}/{owner}"
    return None


def command_enabled(reg: Registry, root: Path | None, key: str,
                    template_key: str | None = None) -> bool:
    """Explicit command entry > template entry > owner cascade > on.

    Command values are three-state: True/False decide outright; None (auto)
    falls through to the next step in the chain. *template_key* is the
    template file's own key when *key* names a generated entry; a
    hand-written per-entry line overrides it. *root* is None when no project
    root is known yet (e.g. before startup); the owner cascade is skipped in
    that case and the default is on."""
    if key in reg.commands and reg.commands[key] is not None:
        return reg.commands[key]
    if template_key is not None and template_key in reg.commands:
        template_value = reg.commands[template_key]
        if template_value is not None:
            return template_value
    owner = key.split("/", 1)[0]
    if owner == "framework":
        return True
    if root is not None:
        okey = owner_resource_key(root, owner)
        if okey is not None and okey in reg.resources:
            return reg.resources[okey]
    return True


def resource_enabled(reg: Registry, key: str) -> bool:
    return reg.resources.get(key, True)


SCAFFOLD_HEADER = (
    "# controls.yaml: everything this agent exposes, one line per item.\n"
    "# commands keys are <owner>/<stem>; resources keys are\n"
    "# modules|connections|agents/<name>.\n"
    "# commands: on (always), off (never), or auto (follow the owner).\n"
    "# resources: on or off. An owner set to off hides it and disables its\n"
    "# auto commands; a command line set to on or off overrides its owner\n"
    "# either way. The server appends new commands as auto and new\n"
    "# resources as on.\n"
    "# pinned lists exact file paths shown in the resource picker.\n"
)


def _section_bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    """(header index, insertion index) of top-level section *name*.
    The insertion index sits before the next top-level key, skipping the
    blank lines that pad the section's end. None when the section is absent."""
    start = None
    end = len(lines)
    for i, ln in enumerate(lines):
        bare = ln.split("#", 1)[0].rstrip()
        if start is None:
            if bare == f"{name}:":
                start = i
            continue
        if ln and ln[0] not in " \t#":
            end = i
            break
    if start is None:
        return None
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return start, end


def _dedupe(lines: list[str]) -> tuple[list[str], bool]:
    """Drop duplicate '  key: value' lines per section, off-wins.
    A repeated top-level section header is dropped, but the lines that
    followed it still belong to that section for de-dup purposes.
    Resolving a duplicate to off rewrites the first line and drops any
    inline comment on it (accepted tradeoff)."""
    out: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    seen_headers: set[str] = set()
    section = None
    changed = False
    for ln in lines:
        bare = ln.split("#", 1)[0].strip()
        if ln and ln[0] not in " \t#" and bare.endswith(":"):
            section = bare[:-1]
            if section in seen_headers:  # repeated section header: drop it
                changed = True
                continue
            seen_headers.add(section)
            out.append(ln)
            continue
        if section in ("commands", "resources") and bare and ":" in bare:
            key, _, value = bare.partition(":")
            ident = (section, key.strip())
            if ident in seen:
                changed = True
                if value.strip() in ("off", "false", "no"):
                    out[seen[ident]] = f"  {key.strip()}: off"
                continue
            seen[ident] = len(out)
        out.append(ln)
    return out, changed


def _warn_stale(reg: Registry, cmds: list[str], res: list[str]) -> None:
    known = set(cmds)
    for key in reg.commands:
        if key in known:
            continue
        if any(key.startswith(t + "_") for t in known):
            continue  # a hand-written per-entry override of a template
        print(f"  ! controls.yaml: command entry {key} matches nothing on "
              "disk (kept; delete the line if it is stale)", file=sys.stderr)
    for key in reg.resources:
        if key not in set(res):
            print(f"  ! controls.yaml: resource entry {key} matches nothing "
                  "on disk (kept; delete the line if it is stale)",
                  file=sys.stderr)


def _atomic_write(path: Path, lines: list[str]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    os.replace(tmp, path)


def heal(root: Path, warn: bool = False) -> bool:
    """Append every unlisted disk item (commands as auto, resources as on);
    dedupe duplicates off-wins.

    Append-only for existing content (comments and ordering survive), atomic
    write under a lock file. Returns True when the file changed. With
    warn=True, report entries that match nothing on disk (kept, not pruned).
    Raises ControlsError when the existing file is malformed."""
    path = root / "controls.yaml"
    with open(root / ".controls.lock", "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        reg = parse(path) or Registry()
        cmds, res = inventory(root)
        if warn:
            _warn_stale(reg, cmds, res)
        missing = {
            "commands": [k for k in cmds if k not in reg.commands],
            "resources": [k for k in res if k not in reg.resources],
        }
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError:
            lines = None
        if lines is None:
            lines = (
                SCAFFOLD_HEADER.split("\n")[:-1]
                + ["", "commands:"] + [f"  {k}: auto" for k in cmds]
                + ["", "resources:"] + [f"  {k}: on" for k in res]
                + ["", "pinned: []"]
            )
            _atomic_write(path, lines)
            return True
        lines, changed = _dedupe(lines)
        for section in ("commands", "resources"):
            if not missing[section]:
                continue
            default = "auto" if section == "commands" else "on"
            new = [f"  {k}: {default}" for k in missing[section]]
            bounds = _section_bounds(lines, section)
            if bounds is None:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.append(f"{section}:")
                lines.extend(new)
            else:
                _, end = bounds
                lines[end:end] = new
            changed = True
        if changed:
            _atomic_write(path, lines)
        return changed


def migrate(root: Path) -> bool:
    """Rewrite the old three-list controls.yaml into the registry format.

    Runs once: a file without the old keys is left alone. Globs in
    hidden_resources expand against the disk at migration time. Every command
    gets an explicit line, so the owner cascade cannot change what the old
    format allowed (old resource hiding never disabled commands). The old
    file's comments do not survive; the migration is a full rewrite."""
    path = root / "controls.yaml"
    data = _load_yaml(path)
    if data is None or not (OLD_KEYS & set(data)):
        return False

    new_keys = {"commands", "resources", "pinned"} & set(data)
    if new_keys:
        print(f"  ! controls.yaml: discarding new-format sections "
              f"({', '.join(sorted(new_keys))}) found alongside the old "
              "format; review the migrated file", file=sys.stderr)

    def old_list(key: str) -> list[str]:
        value = data.get(key)
        return [str(v) for v in value] if isinstance(value, list) else []

    hidden_cmds = set(old_list("hidden_commands"))
    hidden_res = old_list("hidden_resources")
    pinned = old_list("pinned_resources")
    cmds, res = inventory(root)
    lines = SCAFFOLD_HEADER.split("\n")[:-1] + ["", "commands:"]
    lines += [f"  {k}: {'off' if k in hidden_cmds else 'on'}" for k in cmds]
    lines += ["", "resources:"]
    lines += [
        f"  {k}: "
        f"{'off' if any(fnmatch.fnmatch(k, p) for p in hidden_res) else 'on'}"
        for k in res
    ]
    if pinned:
        lines += ["", "pinned:"] + [f"  - {p}" for p in pinned]
    else:
        lines += ["", "pinned: []"]
    _atomic_write(path, lines)
    print("  migrated controls.yaml to the registry format", file=sys.stderr)
    return True
