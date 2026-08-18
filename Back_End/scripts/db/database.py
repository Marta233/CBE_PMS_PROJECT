from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config import DATA_DIR


DB_PATH: Path = Path(DATA_DIR) / "pms.db"


def _db_url() -> str:
    # Use forward slashes for SQLite URLs on Windows as well.
    return f"sqlite:///{DB_PATH.as_posix()}"


engine = create_engine(
    _db_url(),
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

