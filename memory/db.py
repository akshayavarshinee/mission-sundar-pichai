"""Database engine/session helpers (lazy, psycopg3 + pgvector)."""

from __future__ import annotations

import structlog

from clearport.config import settings

logger = structlog.get_logger(__name__)

_ENGINE = None
_SESSIONMAKER = None


def get_engine():  # noqa: ANN201 — SQLAlchemy Engine, imported lazily
    global _ENGINE
    if _ENGINE is None:
        from sqlalchemy import create_engine

        _ENGINE = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        logger.debug("db.engine.created", url=_redact(settings.database_url))
    return _ENGINE


def get_sessionmaker():  # noqa: ANN201
    global _SESSIONMAKER
    if _SESSIONMAKER is None:
        from sqlalchemy.orm import sessionmaker

        _SESSIONMAKER = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SESSIONMAKER


def _redact(url: str) -> str:
    # hide any password component in logs
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host = rest.split("@", 1)
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return url
