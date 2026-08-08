INDEX_MD = """---
id: demo-flow
name: Demo Flow
description: >
  A demo workflow used by the tests.
tags: [demo, testing]
---

# demo-flow

Body text.
"""


def bundle(index_content=INDEX_MD, extra=None):
    files = [
        {"path": "index.md", "content": index_content},
        {"path": "steps/index.md", "content": "one line per step"},
        {"path": "steps/1-do.md", "content": "do the thing"},
        {"path": "commands/setup.md", "content": "the install interview"},
        {"path": "runs/example/index.md", "content": "example run"},
    ]
    if extra:
        files += extra
    return {"files": files}


def submit(client, **kwargs):
    return client.post("/api/workflows", json=bundle(**kwargs))


def test_submit_lands_pending_and_invisible(client, admin):
    resp = submit(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "demo-flow"
    assert body["name"] == "Demo Flow"
    assert body["description"] == "A demo workflow used by the tests."
    assert body["tags"] == ["demo", "testing"]
    assert body["status"] == "pending"

    assert client.get("/api/workflows").json() == []
    assert client.get("/api/workflows/demo-flow").status_code == 404

    pending = client.get("/api/moderation/workflows", headers=admin).json()
    assert [p["id"] for p in pending] == ["demo-flow"]


def test_approve_makes_public_with_full_bundle(client, admin):
    submit(client)
    resp = client.post("/api/moderation/workflows/demo-flow/approve", headers=admin)
    assert resp.status_code == 200

    directory = client.get("/api/workflows").json()
    assert [d["id"] for d in directory] == ["demo-flow"]
    assert directory[0]["tags"] == ["demo", "testing"]

    full = client.get("/api/workflows/demo-flow").json()
    paths = {f["path"] for f in full["files"]}
    assert paths == {
        "index.md",
        "steps/index.md",
        "steps/1-do.md",
        "commands/setup.md",
        "runs/example/index.md",
    }
    index = next(f for f in full["files"] if f["path"] == "index.md")
    assert index["content"] == INDEX_MD


def test_reject_hides(client, admin):
    submit(client)
    resp = client.post("/api/moderation/workflows/demo-flow/reject", headers=admin)
    assert resp.status_code == 200
    assert client.get("/api/workflows").json() == []
    assert client.get("/api/moderation/workflows", headers=admin).json() == []


def test_rejected_id_does_not_block_resubmission(client, admin):
    submit(client)
    client.post("/api/moderation/workflows/demo-flow/reject", headers=admin)
    assert submit(client).status_code == 201


def test_new_pending_replaces_old_pending(client, admin):
    submit(client)
    updated = INDEX_MD.replace("Demo Flow", "Demo Flow v2")
    resp = submit(client, index_content=updated)
    assert resp.status_code == 201
    pending = client.get("/api/moderation/workflows", headers=admin).json()
    assert len(pending) == 1
    assert pending[0]["name"] == "Demo Flow v2"


def test_approving_replacement_swaps_content(client, admin):
    submit(client)
    client.post("/api/moderation/workflows/demo-flow/approve", headers=admin)

    updated = INDEX_MD.replace("Demo Flow", "Demo Flow v2")
    submit(client, index_content=updated)
    # Old version stays live while the replacement is pending.
    assert client.get("/api/workflows/demo-flow").json()["name"] == "Demo Flow"

    client.post("/api/moderation/workflows/demo-flow/approve", headers=admin)
    assert client.get("/api/workflows/demo-flow").json()["name"] == "Demo Flow v2"
    assert len(client.get("/api/workflows").json()) == 1


def test_moderation_requires_token(client):
    assert client.get("/api/moderation/workflows").status_code == 401
    bad = {"Authorization": "Bearer wrong"}
    assert client.get("/api/moderation/workflows", headers=bad).status_code == 401
    assert (
        client.post("/api/moderation/workflows/x/approve", headers=bad).status_code
        == 401
    )


def test_moderation_view_of_pending_bundle(client, admin):
    submit(client)
    full = client.get("/api/moderation/workflows/demo-flow", headers=admin).json()
    assert len(full["files"]) == 5


def test_invalid_bundles_rejected(client):
    no_index = {"files": [{"path": "steps/1-do.md", "content": "x"}]}
    assert client.post("/api/workflows", json=no_index).status_code == 422

    no_frontmatter = submit(client, index_content="# no frontmatter here")
    assert no_frontmatter.status_code == 422

    missing_id = submit(
        client, index_content="---\nname: X\ndescription: Y\n---\nbody"
    )
    assert missing_id.status_code == 422

    bad_slug = submit(
        client,
        index_content="---\nid: Bad Slug!\nname: X\ndescription: Y\n---\nbody",
    )
    assert bad_slug.status_code == 422


def test_path_traversal_rejected(client):
    evil = bundle(extra=[{"path": "../outside.md", "content": "x"}])
    assert client.post("/api/workflows", json=evil).status_code == 422
    absolute = bundle(extra=[{"path": "/etc/passwd", "content": "x"}])
    assert client.post("/api/workflows", json=absolute).status_code == 422
    duplicate = bundle(extra=[{"path": "index.md", "content": "x"}])
    assert client.post("/api/workflows", json=duplicate).status_code == 422
