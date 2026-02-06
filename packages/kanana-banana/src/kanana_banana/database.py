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


def init_db() -> None:
    """
    Create all database tables and run migrations.

    Called once at application startup. SQLModel.metadata contains
    all table definitions from classes with table=True.

    After creating tables, we run migrations to handle any existing
    data that needs to be updated for new features (like boards).
    """
    SQLModel.metadata.create_all(engine)

    # Run migrations for existing data
    from kanana_banana.migrations.add_boards import migrate
    migrate()


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
