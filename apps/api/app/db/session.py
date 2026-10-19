from functools import lru_cache
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True,
        pool_timeout=settings.database_pool_timeout_seconds,
        connect_args={'connect_timeout': settings.database_connect_timeout_seconds,
                      'options': f'-c statement_timeout={settings.database_statement_timeout_ms} -c lock_timeout=5000'})


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
