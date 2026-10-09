"""Shared fixtures: the real app against a fresh SQLite database per test."""

import os

# Settings are read at import time, so configure before importing the app:
# no SQL echo, and never touch a real database file.
os.environ["KANANA_BANANA_DEBUG"] = "false"
os.environ["KANANA_BANANA_DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from kanana_banana.app import app
from kanana_banana.database import get_session


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(engine):
    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    # Not used as a context manager: the lifespan (init_db on the real engine) never runs
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def api(client):
    """Small helpers for building fixtures through the real API."""

    class Api:
        def board(self, name="Homelab", key=None, **fields):
            # Default key: the name's letters, e.g. "Other Board" -> OTHERBOARD
            key = key or "".join(c for c in name if c.isalpha()).upper()
            r = client.post("/api/v1/boards", json={"key": key, "name": name, **fields})
            assert r.status_code == 201, r.text
            return r.json()

        def ticket(self, name, ticket_type="task", **fields):
            r = client.post("/api/v1/tickets", json={"name": name, "ticket_type": ticket_type, **fields})
            assert r.status_code == 201, r.text
            return r.json()

        def project(self, name="Project", board=None, **fields):
            board = board or self.board()
            return self.ticket(name, "project", board_id=board["id"], **fields)

    return Api()
