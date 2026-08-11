def test_telemetry_stores_install(client):
    payload = {
        "install_id": "abc-123",
        "version": "0.5.0",
        "os": "Darwin",
        "platform": "arm64",
    }
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 204

    from sqlalchemy import text

    from app.db import engine

    with engine().begin() as conn:
        rows = conn.execute(text(
            "SELECT install_id, version, os, platform FROM installs"
        )).fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == ("abc-123", "0.5.0", "Darwin", "arm64")


def test_telemetry_rejects_missing_fields(client):
    resp = client.post("/api/telemetry", json={"install_id": "x"})
    assert resp.status_code == 422


def test_telemetry_duplicate_install_id_allowed(client):
    payload = {
        "install_id": "dup-1",
        "version": "0.5.0",
        "os": "Linux",
        "platform": "x86_64",
    }
    resp1 = client.post("/api/telemetry", json=payload)
    resp2 = client.post("/api/telemetry", json=payload)
    assert resp1.status_code == 204
    assert resp2.status_code == 204


import os


def test_admin_list_installs(client):
    client.post("/api/telemetry", json={
        "install_id": "admin-test",
        "version": "0.5.0",
        "os": "Darwin",
        "platform": "arm64",
    })
    resp = client.get(
        "/api/admin/installs",
        headers={"Authorization": f"Bearer {os.environ['ADMIN_TOKEN']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(i["install_id"] == "admin-test" for i in data)


def test_admin_installs_requires_auth(client):
    resp = client.get("/api/admin/installs")
    assert resp.status_code == 401
