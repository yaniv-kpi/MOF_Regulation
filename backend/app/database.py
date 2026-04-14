from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread=False; PostgreSQL uses connection pooling
if _IS_SQLITE:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_db_extensions():
    """Enable PostgreSQL-specific extensions (no-op for SQLite)."""
    if _IS_SQLITE:
        return
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        conn.commit()
