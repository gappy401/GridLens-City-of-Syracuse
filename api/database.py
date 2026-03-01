"""api/database.py — SQLAlchemy engine + session dependency for FastAPI."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from pipeline.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # recycles stale connections
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
