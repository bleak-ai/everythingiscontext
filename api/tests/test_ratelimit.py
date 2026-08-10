"""The submit endpoint is rate limited per client IP."""

from app.ratelimit import limiter

INDEX_MD = """---
id: ratelimit-test
name: Rate Limit Test
description: >
  A workflow used by the rate limit test.
tags: [test]
---

# ratelimit-test

Body text.
"""


def _bundle():
    return {
        "files": [
            {"path": "index.md", "content": INDEX_MD},
            {"path": "steps/index.md", "content": "one line per step"},
            {"path": "steps/1-do.md", "content": "do the thing"},
            {"path": "commands/setup.md", "content": "the install interview"},
            {"path": "runs/example/index.md", "content": "example run"},
        ]
    }


def test_submit_rate_limited(client):
    limiter.reset()
    for i in range(5):
        resp = client.post("/api/workflows", json=_bundle())
        assert resp.status_code in (201, 422), (
            f"request {i + 1} returned {resp.status_code}"
        )
    resp = client.post("/api/workflows", json=_bundle())
    assert resp.status_code == 429
