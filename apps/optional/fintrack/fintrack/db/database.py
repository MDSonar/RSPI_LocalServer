"""
FinTrack Database Session & Configuration
Handles SQLite initialization, migrations, and session lifecycle.
"""

import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "storage" / "fintrack.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    from fintrack.db.models import Base

    Base.metadata.create_all(bind=engine)
    logger.info("FinTrack DB initialized at %s", DB_PATH)


def get_db() -> Session:
    """Get a new database session (for dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
