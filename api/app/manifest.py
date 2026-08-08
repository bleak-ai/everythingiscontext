"""Parse and validate a submitted bundle.

The manifest is the YAML frontmatter of the bundle's index.md. The client's
words are never trusted: id, name, description, and tags are read from the
frontmatter here, exactly as `gcontext add` reads them on install.
"""

import re

import yaml

from . import settings

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class BundleError(ValueError):
    pass


def validate_files(files: list[dict]) -> None:
    if not files:
        raise BundleError("bundle has no files")
    if len(files) > settings.MAX_FILES:
        raise BundleError(f"bundle exceeds {settings.MAX_FILES} files")
    total = 0
    seen: set[str] = set()
    for f in files:
        path, content = f["path"], f["content"]
        if not path or path.startswith("/") or ".." in path.split("/") or "\\" in path:
            raise BundleError(f"invalid path: {path!r}")
        if path in seen:
            raise BundleError(f"duplicate path: {path!r}")
        seen.add(path)
        size = len(content.encode("utf-8"))
        if size > settings.MAX_FILE_BYTES:
            raise BundleError(f"file too large: {path!r}")
        total += size
    if total > settings.MAX_BUNDLE_BYTES:
        raise BundleError("bundle too large")


def parse_manifest(files: list[dict]) -> dict:
    index = next((f for f in files if f["path"] == "index.md"), None)
    if index is None:
        raise BundleError("bundle has no index.md")
    match = _FRONTMATTER_RE.match(index["content"])
    if match is None:
        raise BundleError("index.md has no YAML frontmatter")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise BundleError(f"frontmatter does not parse: {exc}") from exc
    if not isinstance(data, dict):
        raise BundleError("frontmatter is not a mapping")

    workflow_id = data.get("id")
    name = data.get("name")
    description = data.get("description")
    tags = data.get("tags", [])

    if not isinstance(workflow_id, str) or not ID_RE.match(workflow_id):
        raise BundleError("frontmatter id is missing or not a url-safe slug")
    if not isinstance(name, str) or not name.strip():
        raise BundleError("frontmatter name is missing")
    if not isinstance(description, str) or not description.strip():
        raise BundleError("frontmatter description is missing")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise BundleError("frontmatter tags must be a list of strings")

    return {
        "id": workflow_id,
        "name": name.strip(),
        "description": description.strip(),
        "tags": tags,
    }
