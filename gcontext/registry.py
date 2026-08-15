"""Agent registry: fetch, install, check, and update agents from a GitHub registry.

The registry is a GitHub repo with one folder per agent template.
The env var GCONTEXT_REGISTRY accepts "owner/repo@ref" or a direct URL to
a .tar.gz (useful for tests). All failures raise RegistryError; callers
handle the presentation (CLI prints and exits, server tool returns a string).
"""

import hashlib
import io
import json
import os
import ssl
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

import certifi
import yaml


class RegistryError(Exception):
    pass


DEFAULT_REGISTRY = "bleak-ai/agents@main"
DEFAULT_API = "https://api.gcontext.ai"
MANIFEST_NAME = ".template.yaml"


def registry_spec() -> str:
    return os.environ.get("GCONTEXT_REGISTRY", DEFAULT_REGISTRY)


def registry_name() -> str:
    spec = registry_spec()
    if spec.startswith("http://") or spec.startswith("https://"):
        return spec
    return spec.rsplit("@", 1)[0] if "@" in spec else spec


def codeload_url(spec: str) -> str:
    if "@" in spec:
        repo_part, ref = spec.rsplit("@", 1)
    else:
        repo_part, ref = spec, "main"
    return f"https://codeload.github.com/{repo_part}/tar.gz/refs/heads/{ref}"


def parse_registry() -> str:
    spec = registry_spec()
    if spec.startswith("http://") or spec.startswith("https://"):
        return spec
    return codeload_url(spec)


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx


def download_tarball(url: str) -> tarfile.TarFile:
    try:
        with urllib.request.urlopen(url, timeout=30, context=_ssl_context()) as resp:
            data = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        raise RegistryError(f"could not reach the registry at {url}")
    try:
        return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError:
        raise RegistryError("the registry did not return a valid tarball")


def tarball_ref(tf: tarfile.TarFile) -> str:
    return (getattr(tf, "pax_headers", None) or {}).get("comment") or "unknown"


def extract_files(tf: tarfile.TarFile, subpath: str = "") -> list[dict]:
    files = []
    for member in tf.getmembers():
        if not member.isfile():
            continue
        if member.issym() or member.islnk():
            continue
        parts = PurePosixPath(member.name).parts
        if len(parts) < 2:
            continue
        rel = str(PurePosixPath(*parts[1:]))
        if subpath:
            norm = subpath.rstrip("/") + "/"
            if not (rel + "/").startswith(norm) and rel != subpath.rstrip("/"):
                continue
            rel = rel[len(norm):] if rel.startswith(norm) else ""
            if not rel:
                continue
        try:
            raw = tf.extractfile(member)
            if raw is None:
                continue
            content = raw.read().decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        files.append({"path": rel, "content": content})
    return files


def parse_github_url(url: str) -> tuple[str, str, str]:
    cleaned = url
    if cleaned.startswith("github.com/"):
        cleaned = "https://" + cleaned
    path = cleaned.split("github.com/", 1)[1] if "github.com/" in cleaned else ""
    segments = path.strip("/").split("/")
    if len(segments) < 2:
        raise RegistryError(f"cannot parse GitHub URL: {url}")
    owner_repo = f"{segments[0]}/{segments[1]}"
    ref = "main"
    subpath = ""
    if len(segments) > 3 and segments[2] == "tree":
        ref = segments[3]
        if len(segments) > 4:
            subpath = "/".join(segments[4:])
    return owner_repo, ref, subpath


def fetch_agent_by_id(agent_id: str) -> tuple[list[dict], str]:
    url = parse_registry()
    tf = download_tarball(url)
    ref = tarball_ref(tf)
    all_files = extract_files(tf)
    prefix = agent_id + "/"
    matched = []
    for f in all_files:
        if f["path"].startswith(prefix):
            matched.append({"path": f["path"][len(prefix):], "content": f["content"]})
        elif f["path"] == agent_id:
            matched.append({"path": f["path"], "content": f["content"]})
    if not matched:
        raise RegistryError(f"no agent '{agent_id}' found in the registry")
    return matched, ref


def fetch_agent_by_url(url: str) -> tuple[list[dict], str]:
    if "github.com/" in url or url.startswith("github.com/"):
        owner_repo, ref, subpath = parse_github_url(url)
        tarball_url = codeload_url(f"{owner_repo}@{ref}")
    else:
        tarball_url = url
        subpath = ""
    tf = download_tarball(tarball_url)
    ref = tarball_ref(tf)
    files = extract_files(tf, subpath=subpath)
    if not files:
        raise RegistryError(f"no files found at {url}")
    return files, ref


def validate_bundle(files) -> dict:
    from .commands import parse_command

    if not isinstance(files, list) or not files:
        raise ValueError("the bundle has no files")
    for f in files:
        path = f.get("path") or ""
        parts = PurePosixPath(path).parts
        if not path or path.startswith("/") or "\\" in path or ".." in parts:
            raise ValueError(f"unsafe file path in bundle: {path!r}")
    index = next((f for f in files if f["path"] == "index.md"), None)
    if index is None:
        raise ValueError("the bundle has no index.md")
    try:
        meta, _ = parse_command(index["content"])
    except ValueError as e:
        raise ValueError(f"index.md frontmatter: {e}")
    for field in ("id", "name", "description"):
        if not meta.get(field):
            raise ValueError(f"index.md frontmatter is missing '{field}'")
    agents = meta.get("agents")
    if agents is not None and (
        not isinstance(agents, list) or not all(isinstance(a, str) and a for a in agents)
    ):
        raise ValueError("'agents' must be a list of agent ids")
    return meta


def stamp_setup_pending(content: str) -> str:
    """Insert `setup: pending` as the last frontmatter line of an index.md.

    The setup flow removes the field when the smoke test passes; the manifest
    keeps the hash of the unstamped content, so a finished setup leaves no
    drift against the registry copy. Everything except the added line is
    preserved byte for byte.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return content
    for i, ln in enumerate(lines[1:], 1):
        if ln.strip() == "---":
            return "\n".join(lines[:i] + ["setup: pending"] + lines[i:])
    return content


def file_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def write_manifest(module_dir: Path, agent_id: str, ref: str, files: list[dict]):
    data = {
        "template": agent_id,
        "registry": registry_name(),
        "installed_ref": ref,
        "files": {f["path"]: file_hash(f["content"]) for f in sorted(files, key=lambda f: f["path"])},
    }
    (module_dir / MANIFEST_NAME).write_text(yaml.safe_dump(data, sort_keys=False))


def read_manifest(module_dir: Path) -> dict | None:
    path = module_dir / MANIFEST_NAME
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text())
    except (yaml.YAMLError, OSError):
        return None


def _ping_download(agent_id: str) -> None:
    """Notify the API of a CLI install so the download counter stays accurate."""
    try:
        # /api/workflows/ is the retired-but-live API's real endpoint path.
        # Kept as "workflows" on purpose: that service is out of scope for
        # this rename, and the path must match what it actually serves.
        req = urllib.request.Request(
            f"{os.environ.get('GCONTEXT_API', DEFAULT_API)}/api/workflows/"
            f"{urllib.parse.quote(agent_id, safe='')}",
            headers={"X-Source": "cli", "User-Agent": "gcontext-cli"},
        )
        with urllib.request.urlopen(req, timeout=3, context=_ssl_context()):
            pass
    except Exception:
        pass


def _write_module(module_dir: Path, meta: dict, files: list[dict], ref: str):
    for f in files:
        dest = module_dir / f["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = f["content"]
        if f["path"] == "index.md":
            content = stamp_setup_pending(content)
        dest.write_text(content)

    # Hashes cover the unstamped registry content: once setup removes the
    # `setup: pending` line, the module reads as unmodified again.
    write_manifest(module_dir, meta["id"], ref, files)


def install_agent(project_dir: Path, source: str) -> dict:
    is_registry_install = not ("://" in source or source.startswith("github.com/"))
    if is_registry_install:
        files, ref = fetch_agent_by_id(source)
    else:
        files, ref = fetch_agent_by_url(source)

    try:
        meta = validate_bundle(files)
    except ValueError as e:
        raise RegistryError(f"invalid agent bundle: {e}")

    module_dir = project_dir / "modules" / meta["id"]
    if module_dir.exists():
        raise RegistryError(
            f"module '{meta['id']}' already exists at modules/{meta['id']}. "
            "Installs are snapshots: your copy is personalized and is never overwritten."
        )

    # Resolve the declared `agents:` dependencies before writing anything,
    # so a bad dependency never leaves a half-installed set. An id already
    # present under modules/ is satisfied; the visited set breaks cycles.
    to_write = [(meta, files, ref, "")]
    visited = {meta["id"]}
    pending = [(dep_id, meta["id"]) for dep_id in meta.get("agents") or []]
    while pending:
        dep_id, required_by = pending.pop(0)
        if dep_id in visited:
            continue
        visited.add(dep_id)
        if (project_dir / "modules" / dep_id).exists():
            continue
        dep_files, dep_ref = fetch_agent_by_id(dep_id)
        try:
            dep_meta = validate_bundle(dep_files)
        except ValueError as e:
            raise RegistryError(f"invalid agent bundle for '{dep_id}': {e}")
        pending.extend((d, dep_id) for d in dep_meta.get("agents") or [])
        to_write.append((dep_meta, dep_files, dep_ref, required_by))

    dependencies = []
    for m, fl, r, required_by in to_write:
        _write_module(project_dir / "modules" / m["id"], m, fl, r)
        if required_by:
            dependencies.append({
                "id": m["id"], "name": m["name"], "count": len(fl),
                "path": f"modules/{m['id']}", "required_by": required_by,
            })

    if is_registry_install and (
        os.environ.get("GCONTEXT_API") or registry_spec() == DEFAULT_REGISTRY
    ):
        _ping_download(meta["id"])

    return {
        "id": meta["id"], "name": meta["name"], "count": len(files),
        "path": f"modules/{meta['id']}", "dependencies": dependencies,
    }


# --- Catalog (search) ---

def load_catalog() -> list[dict]:
    url = parse_registry()
    tf = download_tarball(url)
    all_files = extract_files(tf)
    catalog_file = next((f for f in all_files if f["path"] == "registry.json"), None)
    if catalog_file is None:
        raise RegistryError("the registry has no registry.json catalog")
    try:
        catalog = json.loads(catalog_file["content"])
        return catalog["agents"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise RegistryError("the registry has no registry.json catalog")


def search_catalog(query: str = "") -> list[dict]:
    entries = load_catalog()
    if not query:
        return entries
    q = query.lower()
    return [
        e for e in entries
        if q in e.get("id", "").lower()
        or q in e.get("name", "").lower()
        or q in e.get("description", "").lower()
        or any(q in t.lower() for t in e.get("tags", []))
    ]


# --- Check and update ---

def check_agent(project_dir: Path, module_name: str, upstream: dict | None = None) -> dict:
    module_dir = project_dir / "modules" / module_name
    manifest = read_manifest(module_dir)
    if manifest is None:
        return {"id": module_name, "status": "untracked"}

    template_id = manifest.get("template", module_name)
    if upstream is None:
        try:
            files, ref = fetch_agent_by_id(template_id)
        except RegistryError:
            return {"id": module_name, "status": "missing-upstream"}
        upstream_map = {f["path"]: f["content"] for f in files}
    else:
        upstream_map, ref = upstream

    base_hashes = manifest.get("files", {})
    all_paths = set(base_hashes) | set(upstream_map)

    changed = {}
    for path in sorted(all_paths):
        base = base_hashes.get(path)
        upstream_content = upstream_map.get(path)
        upstream_h = file_hash(upstream_content) if upstream_content is not None else None

        local_file = module_dir / path
        try:
            local_content = local_file.read_text() if local_file.exists() else None
        except (OSError, UnicodeDecodeError):
            local_content = None
        local_h = file_hash(local_content) if local_content is not None else None

        if base is None:
            if upstream_h is not None and local_h is None:
                changed[path] = "new-upstream"
            elif upstream_h is not None and local_h is not None:
                if upstream_h == local_h:
                    continue
                changed[path] = "both-changed"
            continue

        if upstream_h is None:
            if local_h == base:
                changed[path] = "deleted-upstream"
            elif local_h is not None:
                changed[path] = "deleted-upstream-modified-locally"
            else:
                continue
            continue

        if local_h is None:
            changed[path] = "deleted-locally"
            continue

        if local_h == upstream_h:
            continue
        if local_h == base and upstream_h != base:
            changed[path] = "upstream-changed"
        elif local_h != base and upstream_h == base:
            changed[path] = "local-changed"
        elif local_h != base and upstream_h != base:
            changed[path] = "both-changed"

    status = "up-to-date" if not changed else "changes"
    return {"id": module_name, "status": status, "ref": ref, "files": changed}


def check_all(project_dir: Path) -> list[dict]:
    modules_dir = project_dir / "modules"
    if not modules_dir.is_dir():
        return []

    tracked = {}
    for d in sorted(modules_dir.iterdir()):
        if not d.is_dir():
            continue
        manifest = read_manifest(d)
        if manifest is None:
            continue
        tracked[d.name] = manifest.get("template", d.name)

    if not tracked:
        return []

    url = parse_registry()
    tf = download_tarball(url)
    ref = tarball_ref(tf)
    all_files = extract_files(tf)

    upstream_by_template = {}
    for template_id in set(tracked.values()):
        prefix = template_id + "/"
        matched = {}
        for f in all_files:
            if f["path"].startswith(prefix):
                matched[f["path"][len(prefix):]] = f["content"]
        upstream_by_template[template_id] = matched

    results = []
    for module_name, template_id in tracked.items():
        upstream_map = upstream_by_template.get(template_id, {})
        report = check_agent(project_dir, module_name, upstream=(upstream_map, ref))
        results.append(report)
    return results


def update_agent(project_dir: Path, module_name: str) -> dict:
    module_dir = project_dir / "modules" / module_name
    manifest = read_manifest(module_dir)
    if manifest is None:
        raise RegistryError(
            f"modules/{module_name} has no {MANIFEST_NAME}; "
            "it was not installed from the registry"
        )

    template_id = manifest.get("template", module_name)
    files, ref = fetch_agent_by_id(template_id)
    upstream_map = {f["path"]: f["content"] for f in files}
    base_hashes = dict(manifest.get("files", {}))
    new_hashes = dict(base_hashes)

    all_paths = set(base_hashes) | set(upstream_map)

    report = {
        "id": module_name,
        "ref": ref,
        "updated": [],
        "kept_local": [],
        "conflicts": [],
        "added": [],
        "deleted": [],
        "kept_deleted_upstream": [],
        "commands_changed": False,
    }

    for path in sorted(all_paths):
        base = base_hashes.get(path)
        upstream_content = upstream_map.get(path)
        upstream_h = file_hash(upstream_content) if upstream_content is not None else None

        local_file = module_dir / path
        try:
            local_content = local_file.read_text() if local_file.exists() else None
        except (OSError, UnicodeDecodeError):
            local_content = None
        local_h = file_hash(local_content) if local_content is not None else None

        if base is None:
            if upstream_h is not None and local_h is None:
                dest = module_dir / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(upstream_content)
                new_hashes[path] = upstream_h
                report["added"].append(path)
            elif upstream_h is not None and local_h is not None:
                if upstream_h == local_h:
                    new_hashes[path] = upstream_h
                else:
                    new_path = module_dir / (path + ".new")
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    new_path.write_text(upstream_content)
                    new_hashes[path] = upstream_h
                    report["conflicts"].append(path)
            continue

        if upstream_h is None:
            if local_h == base:
                if local_file.exists():
                    local_file.unlink()
                new_hashes.pop(path, None)
                report["deleted"].append(path)
            elif local_h is not None:
                new_hashes.pop(path, None)
                report["kept_deleted_upstream"].append(path)
            else:
                new_hashes.pop(path, None)
            continue

        if local_h is None:
            report["kept_local"].append(path + " (deleted locally)")
            continue

        if local_h == upstream_h:
            new_hashes[path] = upstream_h
            continue

        if local_h == base and upstream_h != base:
            local_file.write_text(upstream_content)
            new_hashes[path] = upstream_h
            report["updated"].append(path)
        elif local_h != base and upstream_h == base:
            report["kept_local"].append(path)
        elif local_h != base and upstream_h != base:
            new_path = module_dir / (path + ".new")
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(upstream_content)
            new_hashes[path] = upstream_h
            report["conflicts"].append(path)

    commands_paths = report["updated"] + report["added"] + report["conflicts"] + report["deleted"]
    report["commands_changed"] = any(p.startswith("commands/") for p in commands_paths)

    manifest_data = {
        "template": template_id,
        "registry": manifest.get("registry", registry_name()),
        "installed_ref": ref,
        "files": dict(sorted(new_hashes.items())),
    }
    (module_dir / MANIFEST_NAME).write_text(yaml.safe_dump(manifest_data, sort_keys=False))

    return report


# --- Report formatting (shared by CLI and server tool) ---

def format_check_report(report: dict) -> str:
    if report["status"] == "untracked":
        return f"{report['id']}: not tracked (no {MANIFEST_NAME})"
    if report["status"] == "missing-upstream":
        return f"{report['id']}: template not found in the registry"
    if report["status"] == "up-to-date":
        return f"{report['id']}: up to date (ref {report.get('ref', 'unknown')})"
    lines = [f"{report['id']}: changes available (ref {report.get('ref', 'unknown')})"]
    labels = {
        "upstream-changed": "upstream changed",
        "local-changed": "locally modified",
        "both-changed": "both changed",
        "new-upstream": "new upstream file",
        "deleted-upstream": "deleted upstream",
        "deleted-upstream-modified-locally": "deleted upstream, modified locally",
        "deleted-locally": "deleted locally",
    }
    for path, classification in sorted(report.get("files", {}).items()):
        lines.append(f"  {path}: {labels.get(classification, classification)}")
    return "\n".join(lines)


def format_update_report(report: dict) -> str:
    lines = []

    if not any(report.get(k) for k in ("updated", "added", "deleted", "conflicts", "kept_local", "kept_deleted_upstream")):
        lines.append(f"{report['id']}: up to date")
    else:
        lines.append(f"{report['id']}: updated")

    if report.get("updated"):
        lines.append("Updated:")
        for p in report["updated"]:
            lines.append(f"  {p}")
    if report.get("added"):
        lines.append("Added:")
        for p in report["added"]:
            lines.append(f"  {p}")
    if report.get("deleted"):
        lines.append("Deleted:")
        for p in report["deleted"]:
            lines.append(f"  {p}")
    if report.get("conflicts"):
        lines.append("Conflicts (merge <file>.new into <file>, then delete the .new file):")
        for p in report["conflicts"]:
            lines.append(f"  {p}")
    if report.get("kept_local"):
        lines.append("Kept local changes:")
        for p in report["kept_local"]:
            lines.append(f"  {p}")
    if report.get("kept_deleted_upstream"):
        lines.append("Kept (upstream deleted, you modified):")
        for p in report["kept_deleted_upstream"]:
            lines.append(f"  {p}")

    lines.append(f"Manifest updated to ref {report.get('ref', 'unknown')}.")
    return "\n".join(lines)
