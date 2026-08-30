"""controls.yaml: the full registry of everything the server exposes.

Disk is the source of what exists; controls.yaml is the authoritative on/off
overlay, healed to completeness: every disk item gets a line, appended as on.
Design decisions: docs/controls-registry-spec.md in the lab repo.

Key scheme:
- commands: "<owner>/<stem>". Framework prompts use owner "framework". A
  template (``each:``) file gets ONE line; a generated entry can be overridden
  by a hand-written "<owner>/<template-stem>_<entry>" line. Values are
  two-state: on or off.
- resources: "modules/<name>", "connections/<name>", "agents/<name>".
  A resource toggle controls picker listing only; it does not cascade to
  commands. Values are on or off.
- names: optional overrides for display or invocation names. A command key
  value becomes the registered MCP prompt name (and so the slash invocation);
  charset is restricted to a-z, 0-9, underscore, and hyphen. A resource key
  value is a free-text picker display title. URIs never change. Collisions
  are resolved at registration time by keeping the default and warning.

Enablement chain for a command: explicit on/off command entry > template
entry (for generated commands) > on. No owner cascade: a resource toggle
controls picker listing only. Pins are independent of owner state.
Unlisted anything is on (the heal adds the line).

Failure handling: parse errors raise ControlsError. The server fails loud at
startup and keeps the last good registry at request time. Duplicate keys
resolve off-wins. Heal writes are atomic (temp file + os.replace) under a
lock file and append-only for existing content, so hand-written comments and
ordering survive.
"""

from __future__ import annotations

import fnmatch
import os
import re
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
_NAME_RE = re.compile(r"[a-z0-9_-]+")
_RESOURCE_PREFIXES = tuple(f"{k}/" for k in OWNER_KINDS)
OLD_KEYS = {"hidden_commands", "hidden_resources", "pinned_resources"}


class ControlsError(Exception):
    """controls.yaml is unreadable as a registry."""


def _is_resource_key(key: str) -> bool:
    """True when *key* starts with a known owner kind prefix (modules/, etc.)."""
    return key.startswith(_RESOURCE_PREFIXES)


@dataclass
class Registry:
    # Command values are two-state: True (on) or False (off).
    # Resources are the same: True (on) or False (off).
    commands: dict[str, bool] = field(default_factory=dict)
    resources: dict[str, bool] = field(default_factory=dict)
    pinned: list[str] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)


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

    def section(name: str) -> dict[str, bool]:
        raw = data.get(name)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ControlsError(f"'{name}' must be a mapping of key: on|off")
        out: dict[str, bool] = {}
        for k, v in raw.items():
            if isinstance(v, str) and v == "auto":
                raise ControlsError(
                    f"'{name}' entry '{k}' is auto: auto was removed; "
                    "use on or off (the server migrates old files at startup)"
                )
            if not isinstance(v, bool):
                raise ControlsError(
                    f"'{name}' entry '{k}' must be on or off, got {v!r}"
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

    raw_names = data.get("names")
    names: dict[str, str] = {}
    if raw_names is not None:
        if not isinstance(raw_names, dict):
            raise ControlsError("'names' must be a mapping of key: name")
        for k, v in raw_names.items():
            k, v = str(k), str(v)
            if not v:
                continue
            if not _is_resource_key(k) and not _NAME_RE.fullmatch(v):
                raise ControlsError(
                    f"'names' entry '{k}': command names may use only "
                    f"a-z, 0-9, _ and -, got {v!r}")
            names[k] = v

    return Registry(
        commands=section("commands"),
        resources=section("resources"),
        pinned=pinned,
        names=names,
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


def command_enabled(reg: Registry, key: str,
                    template_key: str | None = None) -> bool:
    """Explicit command entry > template entry > on. No owner cascade:
    a resource toggle controls picker listing only."""
    if key in reg.commands:
        return reg.commands[key]
    if template_key is not None and template_key in reg.commands:
        return reg.commands[template_key]
    return True


def resource_enabled(reg: Registry, key: str) -> bool:
    return reg.resources.get(key, True)


SCAFFOLD_HEADER = (
    "# controls.yaml: the on/off registry for everything this agent exposes.\n"
    "# The server maintains it.\n"
    "# Format: https://github.com/bleak-ai/gcontext/blob/main/docs/reference.md#controls\n"
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
    inline comment on it (accepted tradeoff). The names section is
    deduped too; duplicate names lines keep the first occurrence."""
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
        if section in ("commands", "resources", "names") and bare and ":" in bare:
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


def _auto_keys(lines: list[str]) -> list[int]:
    """Indexes of '  key: auto' lines inside the commands section."""
    bounds = _section_bounds(lines, "commands")
    if bounds is None:
        return []
    start, end = bounds
    return [
        i for i in range(start + 1, end)
        if lines[i].split("#", 1)[0].strip().endswith(": auto")
    ]


def _migrate_auto(root: Path, path: Path) -> bool:
    """Rewrite every '  key: auto' command line to its resolved on/off value,
    using the pre-removal cascade one last time (explicit > template > owner
    resource > on). Trailing comments on the rewritten lines survive. Returns
    True when the file changed. Caller holds the lock."""
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError:
        return False
    idxs = _auto_keys(lines)
    if not idxs:
        return False
    # tolerant read: resources section parses normally, auto commands skipped
    data = _load_yaml(path) or {}
    raw_res = data.get("resources") or {}
    resources = {str(k): v for k, v in raw_res.items() if isinstance(v, bool)}
    raw_cmds = data.get("commands") or {}
    explicit = {str(k): v for k, v in raw_cmds.items() if isinstance(v, bool)}

    def resolved(key: str) -> bool:
        owner = key.split("/", 1)[0]
        if owner == "framework":
            return True
        okey = owner_resource_key(root, owner)
        if okey is not None and okey in resources:
            return resources[okey]
        return True

    for i in idxs:
        key = lines[i].split("#", 1)[0].strip().rsplit(":", 1)[0].strip()
        value = explicit.get(key, resolved(key))
        lines[i] = f"  {key}: {'on' if value else 'off'}{_line_comment(lines[i])}"
    _atomic_write(path, lines)
    return True


def heal(root: Path, warn: bool = False) -> bool:
    """Append every unlisted disk item as on; dedupe duplicates off-wins.

    On the first call after auto was removed, migrates any remaining auto
    lines to their resolved on/off value (one-time). Append-only for existing
    content (comments and ordering survive), atomic write under a lock file.
    Returns True when the file changed. With warn=True, report entries that
    match nothing on disk (kept, not pruned). Raises ControlsError when the
    existing file is malformed."""
    path = root / "controls.yaml"
    with open(root / ".controls.lock", "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        migrated = _migrate_auto(root, path)
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
                + ["", "commands:"] + [f"  {k}: on" for k in cmds]
                + ["", "resources:"] + [f"  {k}: on" for k in res]
                + ["", "pinned: []"]
            )
            _atomic_write(path, lines)
            return True
        lines, changed = _dedupe(lines)
        changed = changed or migrated
        for section in ("commands", "resources"):
            if not missing[section]:
                continue
            default = "on"
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


def _line_comment(line: str) -> str:
    """The trailing '  # note' part of a '  key: value  # note' line, with its
    leading spacing, or '' when the line has no comment."""
    idx = line.find("#")
    if idx == -1:
        return ""
    head = line[:idx].rstrip()
    return line[len(head):]


def _rewrite_entry(lines: list[str], section: str, key: str, value: str) -> list[str]:
    """Rewrite (or append) one '  key: value' line inside *section*.
    A trailing comment on the rewritten line survives; every other line is
    left byte-identical. Creates the section at the end when absent."""
    bounds = _section_bounds(lines, section)
    if bounds is None:
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            lines.append("")
        lines += [f"{section}:", f"  {key}: {value}"]
        return lines
    start, end = bounds
    for i in range(start + 1, end):
        bare = lines[i].split("#", 1)[0].strip()
        entry_key, sep, _ = bare.partition(":")
        if sep and entry_key.strip() == key:
            lines[i] = f"  {key}: {value}{_line_comment(lines[i])}"
            return lines
    lines[end:end] = [f"  {key}: {value}"]
    return lines


def _remove_entry(lines: list[str], section: str, key: str) -> list[str]:
    """Delete the '  key: value' line inside *section*; drop the section
    header too when nothing but blank lines remain under it."""
    bounds = _section_bounds(lines, section)
    if bounds is None:
        return lines
    start, end = bounds
    for i in range(start + 1, end):
        bare = lines[i].split("#", 1)[0].strip()
        entry_key, sep, _ = bare.partition(":")
        if sep and entry_key.strip() == key:
            del lines[i]
            break
    bounds = _section_bounds(lines, section)
    if bounds is not None:
        start, end = bounds
        if not any(
            lines[i].split("#", 1)[0].strip()
            for i in range(start + 1, end)
        ):
            del lines[start:end]
    return lines


def set_name(root: Path, key: str, value: str) -> Registry:
    """Set or clear one names: override. Empty *value* removes the line.
    Command values are charset-checked; resource values are free text.
    Atomic write under the lock file. Returns the new registry."""
    value = value.strip()
    if value and not _is_resource_key(key) and not _NAME_RE.fullmatch(value):
        raise ValueError("command names may use only a-z, 0-9, _ and -")
    path = root / "controls.yaml"
    with open(root / ".controls.lock", "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        parse(path)  # malformed file: raise before touching anything
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError:
            lines = []
        if value:
            lines = _rewrite_entry(lines, "names", key, value)
        else:
            lines = _remove_entry(lines, "names", key)
        _atomic_write(path, lines)
        return parse(path) or Registry()


def set_entry(root: Path, section: str, key: str, value: str) -> Registry:
    """Set one registry entry to on or off, editing a single line.

    Line-based like the heal: comments and ordering elsewhere survive, the
    rewritten line keeps its own trailing comment. When the key has no line
    yet (a per-entry template override, or an item the heal has not seen),
    it is appended at the section's end. Atomic write under the lock file.
    Returns the new registry. Raises ValueError on a bad section or value
    and ControlsError when the existing file is malformed (never guess on a
    broken file)."""
    if section not in ("commands", "resources"):
        raise ValueError(f"section must be commands or resources, got {section!r}")
    if value not in ("on", "off"):
        raise ValueError(f"value must be on or off, got {value!r}")
    path = root / "controls.yaml"
    with open(root / ".controls.lock", "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        parse(path)  # malformed file: raise before touching anything
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError:
            lines = []
        lines = _rewrite_entry(lines, section, key, value)
        _atomic_write(path, lines)
        return parse(path) or Registry()


def set_pinned(root: Path, pin_path: str, pinned: bool) -> Registry:
    """Add or remove one '  - path' line in the pinned section.

    Creates the section when absent; removing the last pin leaves
    'pinned: []'. An inline 'pinned: [...]' line is expanded to block form
    on the first add. Atomic write under the lock file. Returns the new
    registry. Raises ControlsError when the existing file is malformed."""
    path = root / "controls.yaml"
    with open(root / ".controls.lock", "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        reg = parse(path) or Registry()
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError:
            lines = []
        inline_idx = next(
            (i for i, ln in enumerate(lines)
             if (b := ln.split("#", 1)[0].strip()).startswith("pinned:")
             and b != "pinned:"),
            None,
        )
        if inline_idx is not None:
            # inline form (e.g. the scaffold's "pinned: []"): rebuild from
            # the parsed list, block form when anything remains
            items = [p for p in reg.pinned if p != pin_path or pinned]
            if pinned and pin_path not in items:
                items.append(pin_path)
            if items:
                lines[inline_idx:inline_idx + 1] = (
                    ["pinned:"] + [f"  - {p}" for p in items]
                )
            else:
                lines[inline_idx] = "pinned: []"
        else:
            bounds = _section_bounds(lines, "pinned")
            if bounds is None:
                while lines and not lines[-1].strip():
                    lines.pop()
                if lines:
                    lines.append("")
                if pinned:
                    lines += ["pinned:", f"  - {pin_path}"]
                else:
                    lines.append("pinned: []")
            else:
                start, end = bounds
                existing = [
                    i for i in range(start + 1, end)
                    if lines[i].split("#", 1)[0].strip() == f"- {pin_path}"
                ]
                if pinned and not existing:
                    lines[end:end] = [f"  - {pin_path}"]
                elif not pinned and existing:
                    for i in reversed(existing):
                        del lines[i]
                    start, end = _section_bounds(lines, "pinned")
                    if not any(
                        lines[i].split("#", 1)[0].strip().startswith("- ")
                        for i in range(start + 1, end)
                    ):
                        lines[start] = "pinned: []"
        _atomic_write(path, lines)
        return parse(path) or Registry()


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
