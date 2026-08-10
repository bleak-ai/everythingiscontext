from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from . import settings
from .models import Base

_engine = None
_session_factory = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url(), pool_pre_ping=True)
    return _engine


def init_db() -> None:
    Base.metadata.create_all(engine())
    _migrate_legacy(engine())


def _migrate_legacy(eng) -> None:
    """One-time migration: copy download counts from the legacy tables and drop them."""
    if not inspect(eng).has_table("templates"):
        return
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO workflows (id, downloads) "
            "SELECT id, SUM(downloads) FROM templates GROUP BY id "
            "ON CONFLICT (id) DO NOTHING"
        ))
        conn.execute(text("DROP TABLE IF EXISTS template_files"))
        conn.execute(text("DROP TABLE IF EXISTS templates"))


def get_session():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=engine(), expire_on_commit=False)
    session: Session = _session_factory()
    try:
        yield session
    finally:
        session.close()
