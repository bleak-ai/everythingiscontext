import os
import uuid

import pytest

VALID_UUID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    """Clear the in-memory rate limiter before each test."""
    from app.routes_telemetry import _rate_limit
    _rate_limit.clear()


def _valid_payload(**overrides):
    base = {
        "install_id": VALID_UUID,
        "version": "0.5.0",
        "os": "Darwin",
        "platform": "arm64",
    }
    base.update(overrides)
    return base


def test_telemetry_stores_install(client):
    payload = _valid_payload()
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 204

    from sqlalchemy import text

    from app.db import engine

    with engine().begin() as conn:
        rows = conn.execute(text(
            "SELECT install_id, version, os, platform FROM installs"
        )).fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == (VALID_UUID, "0.5.0", "Darwin", "arm64")


def test_telemetry_rejects_missing_fields(client):
    resp = client.post("/api/telemetry", json={"install_id": VALID_UUID})
    assert resp.status_code == 422


def test_telemetry_duplicate_install_id_allowed(client):
    from app.routes_telemetry import _rate_limit
    payload = _valid_payload(os="Linux", platform="x86_64")
    resp1 = client.post("/api/telemetry", json=payload)
    _rate_limit.clear()  # bypass rate limit for second call
    resp2 = client.post("/api/telemetry", json=payload)
    assert resp1.status_code == 204
    assert resp2.status_code == 204


# --- install_id validation ---

def test_telemetry_accepts_valid_uuid(client):
    payload = _valid_payload(install_id=str(uuid.uuid4()))
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 204


def test_telemetry_rejects_plain_string_install_id(client):
    payload = _valid_payload(install_id="test")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


def test_telemetry_rejects_path_install_id(client):
    payload = _valid_payload(install_id="/tmp/pp-fuzz")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


def test_telemetry_rejects_url_install_id(client):
    payload = _valid_payload(install_id="https://evil.com/payload")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


# --- version validation ---

def test_telemetry_rejects_newline_version(client):
    payload = _valid_payload(version="\n")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


def test_telemetry_rejects_path_version(client):
    payload = _valid_payload(version="/tmp/pp-fuzz")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


def test_telemetry_accepts_long_semver(client):
    payload = _valid_payload(version="1.2.3.4.5")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 204


# --- os / platform validation ---

def test_telemetry_rejects_long_os(client):
    payload = _valid_payload(os="A" * 51)
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


def test_telemetry_rejects_newline_platform(client):
    payload = _valid_payload(platform="arm64\ninjected")
    resp = client.post("/api/telemetry", json=payload)
    assert resp.status_code == 422


# --- admin ---

def test_admin_list_installs(client):
    client.post("/api/telemetry", json=_valid_payload())
    resp = client.get(
        "/api/admin/installs",
        headers={"Authorization": f"Bearer {os.environ['ADMIN_TOKEN']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(i["install_id"] == VALID_UUID for i in data)


def test_admin_installs_requires_auth(client):
    resp = client.get("/api/admin/installs")
    assert resp.status_code == 401
