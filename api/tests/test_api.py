def test_first_get_creates_row_with_count_1(client):
    resp = client.get("/api/workflows/demo-flow")
    assert resp.status_code == 200
    assert resp.json() == {"id": "demo-flow", "downloads": 1}


def test_repeated_gets_increment(client, admin):
    for _ in range(3):
        client.get("/api/workflows/demo-flow")
    listed = client.get("/api/admin/workflows", headers=admin).json()
    assert len(listed) == 1
    assert listed[0]["id"] == "demo-flow"
    assert listed[0]["downloads"] == 3


def test_site_header_does_not_increment(client, admin):
    client.get("/api/workflows/demo-flow", headers={"X-Source": "site"})
    listed = client.get("/api/admin/workflows", headers=admin).json()
    assert listed == []


def test_site_header_missing_id_returns_zero(client):
    resp = client.get("/api/workflows/unknown-flow", headers={"X-Source": "site"})
    assert resp.status_code == 200
    assert resp.json() == {"id": "unknown-flow", "downloads": 0}


def test_cli_header_increments(client, admin):
    resp = client.get("/api/workflows/demo-flow", headers={"X-Source": "cli"})
    assert resp.status_code == 200
    assert resp.json()["downloads"] == 1
    listed = client.get("/api/admin/workflows", headers=admin).json()
    assert listed[0]["downloads"] == 1


def test_admin_list_requires_token(client):
    assert client.get("/api/admin/workflows").status_code == 401
    bad = {"Authorization": "Bearer wrong"}
    assert client.get("/api/admin/workflows", headers=bad).status_code == 401


def test_admin_list_returns_all_ids(client, admin):
    client.get("/api/workflows/alpha")
    client.get("/api/workflows/beta")
    client.get("/api/workflows/beta")
    listed = client.get("/api/admin/workflows", headers=admin).json()
    by_id = {w["id"]: w["downloads"] for w in listed}
    assert by_id == {"alpha": 1, "beta": 2}


def test_invalid_slug_rejected(client):
    assert client.get("/api/workflows/Bad Slug!").status_code == 404
    assert client.get("/api/workflows/../escape").status_code == 404
    assert client.get("/api/workflows/-starts-dash").status_code == 404


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_migration_from_legacy_tables(postgres):
    """Simulate the one-time migration from the old marketplace schema."""
    from sqlalchemy import text

    from app.db import engine, init_db
    from app.models import Base

    eng = engine()
    Base.metadata.drop_all(eng)

    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE templates ("
            "  pk SERIAL PRIMARY KEY,"
            "  id TEXT NOT NULL,"
            "  name TEXT NOT NULL,"
            "  description TEXT NOT NULL,"
            "  status TEXT NOT NULL,"
            "  downloads INTEGER NOT NULL DEFAULT 0"
            ")"
        ))
        conn.execute(text(
            "CREATE TABLE template_files ("
            "  pk SERIAL PRIMARY KEY,"
            "  template_pk INTEGER REFERENCES templates(pk),"
            "  path TEXT NOT NULL,"
            "  content TEXT NOT NULL"
            ")"
        ))
        conn.execute(text(
            "INSERT INTO templates (id, name, description, status, downloads) VALUES "
            "('support-ops', 'Support Ops', 'desc', 'approved', 7),"
            "('browser-recipes', 'Browser Recipes', 'desc', 'approved', 3),"
            "('coolify-ops', 'Coolify Ops', 'desc', 'rejected', 2)"
        ))

    init_db()

    with eng.begin() as conn:
        rows = conn.execute(text("SELECT id, downloads FROM workflows ORDER BY id")).fetchall()
        by_id = {r[0]: r[1] for r in rows}
        assert by_id == {"browser-recipes": 3, "coolify-ops": 2, "support-ops": 7}

        assert not conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'templates'"
        )).fetchone()
        assert not conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'template_files'"
        )).fetchone()

    init_db()
    with eng.begin() as conn:
        rows = conn.execute(text("SELECT id, downloads FROM workflows ORDER BY id")).fetchall()
        assert len(rows) == 3
