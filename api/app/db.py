from sqlalchemy import create_engine
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


def get_session():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=engine(), expire_on_commit=False)
    session: Session = _session_factory()
    try:
        yield session
    finally:
        session.close()
