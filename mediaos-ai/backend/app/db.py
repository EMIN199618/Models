"""PostgreSQL bağlantısı. PostgreSQL sistemin yeganə həqiqət mənbəyidir."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Testlərdə başqa bazaya keçmək üçün."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s


def init_db() -> None:
    """İdempotent sxem yaradılması (miqrasiya 001)."""
    from app import models  # noqa: F401  — cədvəlləri qeydiyyata salır

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING gin (to_tsvector('simple', text))"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_version (version int PRIMARY KEY, applied_at timestamptz DEFAULT now())"
        ))
        conn.execute(text("INSERT INTO schema_version(version) VALUES (1) ON CONFLICT DO NOTHING"))
        # Miqrasiya 002 — sosial şəbəkə sahələri (mövcud bazalar üçün; yeni baza create_all ilə alır)
        for col, typ in (("platform", "varchar(16)"), ("external_id", "varchar(64)"),
                         ("author_handle", "varchar(128)"), ("engagement", "jsonb DEFAULT '{}'::jsonb")):
            conn.execute(text(f"ALTER TABLE news_items ADD COLUMN IF NOT EXISTS {col} {typ}"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_news_platform_external "
                          "ON news_items (platform, external_id) WHERE external_id IS NOT NULL"))
        conn.execute(text("INSERT INTO schema_version(version) VALUES (2) ON CONFLICT DO NOTHING"))


def drop_db() -> None:
    """Rollback: MediaOS AI cədvəllərini silir (yalnız dev/test)."""
    from app import models  # noqa: F401

    engine = get_engine()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS schema_version"))
