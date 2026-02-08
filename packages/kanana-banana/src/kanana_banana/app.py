"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from kanana_banana.database import init_db


# Resolve paths relative to this file
PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
ASSETS_DIR = PACKAGE_DIR / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Code before 'yield' runs at startup.
    Code after 'yield' runs at shutdown.
    """
    # Startup: create database tables
    init_db()
    yield
    # Shutdown: nothing to clean up for now


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title="Kanana Banana",
        description="A simple kanban board for tracking projects, tasks, and subtasks.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount static files (CSS, JS, images)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    # Import routers here to avoid circular imports
    from kanana_banana.routers import tickets, board, boards

    # Include API routers
    app.include_router(tickets.router)

    # Include board management routes (API + HTML for modals)
    app.include_router(boards.router)

    # Include main board HTML router (must be last due to catch-all routes)
    app.include_router(board.router)

    return app


# Create the app instance (used by uvicorn)
app = create_app()


def main() -> None:
    """
    CLI entry point.

    Run with: kanana-banana
    Or: pixi run kanana-banana
    """
    import uvicorn

    uvicorn.run(
        "kanana_banana.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload on code changes during development
    )


if __name__ == "__main__":
    main()
