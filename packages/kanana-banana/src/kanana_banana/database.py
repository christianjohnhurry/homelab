from pathlib import Path
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from kanana_banana.config import settings


# Create the database engine
# check_same_thread=False is required for SQLite with FastAPI
# because FastAPI may access the DB from different threads
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # Log all SQL statements when debug=True
    connect_args={"check_same_thread": False},
)


def ensure_database_dir(database_url: str) -> None:
    """Create the parent directory of a file-based SQLite database."""
    prefix = "sqlite:///"
    if database_url.startswith(prefix) and len(database_url) > len(prefix):
        Path(database_url.removeprefix(prefix)).parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """
    Create the database directory and all tables.

    Called once at application startup. SQLModel.metadata contains
    all table definitions from classes with table=True.
    """
    ensure_database_dir(settings.database_url)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Usage in a route:
        @app.get("/items")
        def get_items(session: Session = Depends(get_session)):
            ...

    The session is automatically closed after the request completes,
    even if an exception is raised.
    """
    with Session(engine) as session:
        yield session
