"""Module manifest (module.yaml) read/write service.

Each module declares its name, kind, secrets, dependencies, and optional
jobs in module.yaml. Replaces per-module .env.schema and requirements.txt.
"""
import re
import typing
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

ModuleKind = Literal["integration", "task", "workflow"]


_EVERY_RE = re.compile(r"^(\d+)([smh])$")
_EVERY_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}

# Must match jobs.TICK_SECONDS — keep as a constant here to avoid
# importing jobs.py from manifest.py (circular).
_MIN_EVERY_SECONDS = 30


def parse_every(value: str) -> int:
    """Convert '30s' / '5m' / '1h' to a number of seconds.

    Raises ValueError on any malformed input or values below the
    scheduler tick (30 s) — sub-tick intervals would round up anyway
    and surprise the user.
    """
    if not isinstance(value, str):
        raise ValueError(f"every must be a string, got {type(value).__name__}")
    match = _EVERY_RE.fullmatch(value)
    if not match:
        raise ValueError(
            f"invalid every '{value}': expected <digits><s|m|h>, e.g. '30s', '5m', '1h'"
        )
    n = int(match.group(1))
    if n == 0:
        raise ValueError(f"invalid every '{value}': must be > 0")
    seconds = n * _EVERY_UNIT_SECONDS[match.group(2)]
    if seconds < _MIN_EVERY_SECONDS:
        raise ValueError(
            f"invalid every '{value}': minimum is {_MIN_EVERY_SECONDS}s"
        )
    return seconds


class JobSpec(BaseModel):
    name: str = Field(..., description="Job identifier; unique within the module.")
    script: str = Field(
        ...,
        description="Relative path to the script inside the module directory. Absolute paths and `..` traversal are rejected.",
    )
    every: str = Field(
        ...,
        description="Cron-like cadence as `<digits><s|m|h>` (e.g. `30s`, `5m`, `1h`). Minimum 30s.",
    )

    @field_validator("script")
    @classmethod
    def _no_absolute_or_traversal(cls, v: str) -> str:
        if v.startswith("/") or ".." in Path(v).parts:
            raise ValueError(f"invalid script path '{v}': must be relative inside the module")
        return v

    @field_validator("every")
    @classmethod
    def _validate_every(cls, v: str) -> str:
        parse_every(v)  # raises on bad values
        return v

    @property
    def every_seconds(self) -> int:
        return parse_every(self.every)


class ModuleManifest(BaseModel):
    name: str = Field(
        ...,
        description="Folder slug; must match the module directory name.",
    )
    kind: ModuleKind = Field(
        default="integration",
        description='One of: "integration", "task", "workflow". Drives how the module is rendered in the sidebar.',
    )
    archived: bool = Field(
        default=False,
        description="Hide from the active sidebar without deleting. Archived modules appear under a collapsed Archived section and cannot be loaded into the workspace.",
    )
    secrets: list[str] = Field(
        default_factory=list,
        description="Environment variable names this module needs at runtime. Resolved via varlock from the workspace .env.schema.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Python packages required at runtime. Installed into the platform venv at boot.",
    )
    icon: str = Field(
        default="",
        description="Icon name for the module's app card (e.g. 'globe', 'server'). Empty means auto-derived.",
    )
    jobs: list[JobSpec] = Field(
        default_factory=list,
        description="Cron-like scheduled scripts owned by this module.",
    )


def read_manifest(module_dir: Path) -> ModuleManifest:
    """Read module.yaml from a module directory.

    Returns a manifest with defaults (name inferred from dir) if the
    file doesn't exist.
    """
    manifest_path = module_dir / "module.yaml"
    if not manifest_path.exists():
        return ModuleManifest(name=module_dir.name)
    raw = yaml.safe_load(manifest_path.read_text()) or {}
    raw.setdefault("name", module_dir.name)
    return ModuleManifest(**raw)


def write_manifest(module_dir: Path, manifest: ModuleManifest) -> None:
    """Write a ModuleManifest to module.yaml, omitting empty optional fields."""
    data: dict[str, str | bool | list[str]] = {"name": manifest.name}
    if manifest.kind != "integration":
        data["kind"] = manifest.kind
    if manifest.archived:
        data["archived"] = manifest.archived
    if manifest.icon:
        data["icon"] = manifest.icon
    if manifest.secrets:
        data["secrets"] = manifest.secrets
    if manifest.dependencies:
        data["dependencies"] = manifest.dependencies
    if manifest.jobs:
        data["jobs"] = [
            {"name": j.name, "script": j.script, "every": j.every}
            for j in manifest.jobs
        ]
    (module_dir / "module.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False)
    )


_SLUG_NON_ALPHANUM = re.compile(r"[^a-z0-9-]")
_SLUG_DASH_RUN = re.compile(r"-+")


def slugify_task_name(name: str) -> str:
    """Convert a human task name to a folder-safe slug."""
    slug = name.strip().lower().replace("_", "-")
    slug = _SLUG_NON_ALPHANUM.sub("-", slug)
    slug = _SLUG_DASH_RUN.sub("-", slug)
    return slug.strip("-")


_PRIMITIVE_NAMES = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
}


def _format_default(field) -> str:
    if field.is_required():
        return "required"
    factory = field.default_factory
    if factory is not None:
        try:
            default = factory()
        except TypeError:
            default = None
    else:
        default = field.default
    if isinstance(default, bool):
        return "default false" if default is False else "default true"
    if isinstance(default, str):
        return f'default "{default}"'
    if isinstance(default, list) and not default:
        return "default []"
    return f"default {default!r}"


def _format_type(annotation) -> str:
    if annotation in _PRIMITIVE_NAMES:
        return _PRIMITIVE_NAMES[annotation]
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        (inner,) = annotation.__args__
        if inner is JobSpec:
            return "list[JobSpec]"
        return f"list[{_PRIMITIVE_NAMES.get(inner, inner.__name__)}]"
    if typing.get_origin(annotation) is Literal:
        return " | ".join(repr(v) for v in typing.get_args(annotation))
    return getattr(annotation, "__name__", str(annotation))


def render_schema_md() -> str:
    """Render ModuleManifest as a markdown schema block for prompt injection.

    Walks the model's fields and emits one bullet per field with type,
    default, and description. Single source of truth for what the AI
    should write into module.yaml — adding a new field here makes it
    visible to the chat agent automatically.
    """
    lines = ["## module.yaml schema", ""]
    for field_name, field in ModuleManifest.model_fields.items():
        type_str = _format_type(field.annotation)
        default_str = _format_default(field)
        desc = field.description or ""
        lines.append(f"- `{field_name}` ({type_str}, {default_str}) — {desc}")
        if type_str == "list[JobSpec]":
            for sub_name, sub in JobSpec.model_fields.items():
                sub_type = _format_type(sub.annotation)
                sub_default = _format_default(sub)
                sub_desc = sub.description or ""
                lines.append(f"  - `{sub_name}` ({sub_type}, {sub_default}) — {sub_desc}")
    lines.append("")
    lines.append(
        "Omit fields that match their default. Unknown fields are rejected."
    )
    return "\n".join(lines)
