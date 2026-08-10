import os
import socket
import subprocess
import time

import pytest

CONTAINER = "gcontext-api-test-pg"
PORT = 55433


def _wait_for_port(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError("postgres did not come up")


@pytest.fixture(scope="session", autouse=True)
def postgres():
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    subprocess.run(
        [
            "docker", "run", "-d", "--name", CONTAINER,
            "-e", "POSTGRES_PASSWORD=test",
            "-e", "POSTGRES_DB=workflows",
            "-p", f"{PORT}:5432",
            "postgres:16-alpine",
        ],
        check=True,
        capture_output=True,
    )
    _wait_for_port(PORT)
    os.environ["DATABASE_URL"] = (
        f"postgresql+psycopg://postgres:test@127.0.0.1:{PORT}/workflows"
    )
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    # The port answers before postgres accepts connections; retry the first connect.
    from app.db import init_db

    for _ in range(30):
        try:
            init_db()
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("could not initialize the database")
    yield
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)


@pytest.fixture()
def client(postgres):
    from fastapi.testclient import TestClient

    from app.db import engine
    from app.main import app
    from app.models import Base
    from app.ratelimit import limiter

    limiter.reset()
    Base.metadata.drop_all(engine())
    Base.metadata.create_all(engine())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin():
    return {"Authorization": "Bearer test-admin-token"}
