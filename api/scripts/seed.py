"""Submit a template folder to the workflows API and approve it.

Runs the real submit-for-review path, then approves with the admin token.

Usage:
    uv run python scripts/seed.py <template-folder> --api-url <url>

The admin token is read from the ADMIN_TOKEN env var.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def request(url: str, method: str = "GET", body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="template folder (its name is not used; the manifest id is)")
    parser.add_argument("--api-url", required=True, help="base URL, e.g. https://api.gcontext.ai")
    args = parser.parse_args()

    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        print("ADMIN_TOKEN env var is required", file=sys.stderr)
        return 1

    root = Path(args.folder)
    files = [
        {"path": p.relative_to(root).as_posix(), "content": p.read_text(encoding="utf-8")}
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    print(f"submitting {len(files)} files from {root}")

    base = args.api_url.rstrip("/")
    submitted = request(f"{base}/api/workflows", "POST", {"files": files})
    workflow_id = submitted["id"]
    print(f"submitted: id={workflow_id} status={submitted['status']}")

    approved = request(
        f"{base}/api/moderation/workflows/{workflow_id}/approve", "POST", {}, token
    )
    print(f"approved: {approved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
