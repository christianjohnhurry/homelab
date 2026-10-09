"""Shared fixtures: the real app against a fresh SQLite database per test."""

import os

# Settings are read at import time, so configure before importing the app:
# no SQL echo, and never touch a real database file.
os.environ["KANANA_BANANA_DEBUG"] = "false"
os.environ["KANANA_BANANA_DATABASE_URL"] = "sqlite://"

import json

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from kanana_banana import github
from kanana_banana.app import app
from kanana_banana.database import get_session
from kanana_banana.routers.tickets import get_github_factory


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


@pytest.fixture
def kb(client, monkeypatch):
    """Run `kb` against the in-process app: the CLI's HTTP client is the TestClient."""
    from typer.testing import CliRunner

    from kanana_banana import cli

    monkeypatch.setattr(cli, "make_client", lambda: client)
    # No git repo by default, so board resolution needs --board unless a test sets one
    monkeypatch.setattr(cli, "git_origin_repo", lambda: None)
    runner = CliRunner()

    def run(*args: str, input: str | None = None):
        return runner.invoke(cli.app, list(args), input=input)

    return run


class FakeGitHub:
    """Records requests; repo o/homelab with default branch main and whatever branches exist."""

    def __init__(self):
        self.requests = []
        self.branches = {"main": "sha-main"}
        self.created_from = {}
        self.fail_with = None

    def __call__(self, request):
        self.requests.append(request)
        if self.fail_with:
            return httpx2.Response(self.fail_with, json={"message": "nope"})
        path = request.url.path
        if path == "/repos/o/homelab":
            return httpx2.Response(200, json={"default_branch": "main"})
        if path.startswith("/repos/o/homelab/git/ref/heads/"):
            name = path.removeprefix("/repos/o/homelab/git/ref/heads/")
            if name in self.branches:
                return httpx2.Response(200, json={"object": {"sha": self.branches[name]}})
            return httpx2.Response(404, json={"message": "Not Found"})
        if path == "/repos/o/homelab/git/refs" and request.method == "POST":
            body = json.loads(request.read())
            name = body["ref"].removeprefix("refs/heads/")
            if name in self.branches:
                return httpx2.Response(422, json={"message": "Reference already exists"})
            self.branches[name] = f"sha-{name}"
            self.created_from[name] = body["sha"]
            return httpx2.Response(201, json={})
        return httpx2.Response(404, json={"message": "Not Found"})


@pytest.fixture
def gh(client):
    """Route the server's GitHub calls to a FakeGitHub."""
    fake = FakeGitHub()
    app.dependency_overrides[get_github_factory] = lambda: (
        lambda: github.GitHub("test-token", transport=httpx2.MockTransport(fake))
    )
    return fake
