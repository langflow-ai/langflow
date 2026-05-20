"""Chat query logging for analytics. Uses DATABASE_URL (Postgres); no secrets in repo."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = None
SessionLocal = None


class ChatQuery(Base):
    __tablename__ = "chat_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(Text, nullable=False, index=True)
    session_id = Column(Text, nullable=True, index=True)
    flow_id = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metadata_ = Column("metadata", JSONB, nullable=True)


def _ensure_engine():
    global engine, SessionLocal
    if engine is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL must be set (e.g. postgresql://user:pass@host:25060/defaultdb?sslmode=require)"
            )
        url = DATABASE_URL
        if "postgresql" in url and "sslmode" not in url:
            url = f"{url}&sslmode=require" if "?" in url else f"{url}?sslmode=require"
        engine = create_engine(url, pool_pre_ping=True, echo=os.environ.get("SQL_ECHO") == "1")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


def init_db():
    if not DATABASE_URL:
        return
    _ensure_engine()
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def log_query(
    query_text: str,
    *,
    session_id: str | None = None,
    flow_id: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    if not DATABASE_URL:
        return
    _ensure_engine()
    with get_db() as db:
        db.add(ChatQuery(query_text=query_text, session_id=session_id, flow_id=flow_id, metadata_=metadata))
