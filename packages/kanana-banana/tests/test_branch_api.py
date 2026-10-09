"""POST /api/v1/tickets/{id}/branch against a fake GitHub."""

import json

import httpx2
import pytest

from kanana_banana import config, github
from kanana_banana.app import app
from kanana_banana.routers.tickets import get_github_factory


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
    fake = FakeGitHub()
    app.dependency_overrides[get_github_factory] = lambda: (
        lambda: github.GitHub("test-token", transport=httpx2.MockTransport(fake))
    )
    return fake


@pytest.fixture
def tree(api):
    board = api.board("Homelab", key="hml", repo_url="https://github.com/o/homelab")
    project = api.project("Project", board=board)
    task = api.ticket("Add login flow", "task", parent_id=project["id"])
    subtask = api.ticket("Login form UI", "subtask", parent_id=task["id"])
    return {"board": board, "project": project, "task": task, "subtask": subtask}


def branch(client, ticket):
    return client.post(f"/api/v1/tickets/{ticket['id']}/branch")


def test_task_branch_from_default(client, gh, tree):
    r = branch(client, tree["task"])
    assert r.status_code == 201, r.text
    assert r.json()["branch"] == "hml-2-add-login-flow"
    assert gh.created_from["hml-2-add-login-flow"] == "sha-main"
    assert client.get(f"/api/v1/tickets/{tree['task']['id']}").json()["branch"] == "hml-2-add-login-flow"


def test_subtask_stacked_on_task_branch(client, gh, tree):
    branch(client, tree["task"])
    r = branch(client, tree["subtask"])
    assert r.status_code == 201, r.text
    assert r.json()["branch"] == "hml-3-login-form-ui"
    assert gh.created_from["hml-3-login-form-ui"] == "sha-hml-2-add-login-flow"


def test_subtask_needs_task_branch_first(client, gh, tree):
    r = branch(client, tree["subtask"])
    assert r.status_code == 400
    assert "Create HML-2's branch first" in r.json()["detail"]
    assert gh.requests == []


def test_parentless_task(client, gh, api, tree):
    fix = api.ticket("Fix typo", "task", board_id=tree["board"]["id"])
    assert branch(client, fix).json()["branch"] == "hml-4-fix-typo"


def test_project_refused(client, gh, tree):
    r = branch(client, tree["project"])
    assert r.status_code == 400
    assert "Projects don't get branches" in r.json()["detail"]
    assert gh.requests == []


def test_already_branched(client, gh, tree):
    branch(client, tree["task"])
    count = len(gh.requests)
    r = branch(client, tree["task"])
    assert r.status_code == 409
    assert "already has branch hml-2-add-login-flow" in r.json()["detail"]
    assert len(gh.requests) == count


def test_board_without_repo(client, gh, api):
    board = api.board("Bare", key="bare")
    task = api.ticket("T", "task", board_id=board["id"])
    r = branch(client, task)
    assert r.status_code == 400
    assert "no GitHub repo URL" in r.json()["detail"]


def test_branch_exists_on_github_leaves_ticket_unchanged(client, gh, tree):
    gh.branches["hml-2-add-login-flow"] = "sha-other"
    r = branch(client, tree["task"])
    assert r.status_code == 409
    assert client.get(f"/api/v1/tickets/{tree['task']['id']}").json()["branch"] is None


def test_github_failure_leaves_ticket_unchanged(client, gh, tree):
    gh.fail_with = 403
    r = branch(client, tree["task"])
    assert r.status_code == 502
    assert client.get(f"/api/v1/tickets/{tree['task']['id']}").json()["branch"] is None


def test_rename_keeps_branch(client, gh, tree):
    branch(client, tree["task"])
    r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"name": "Totally different"})
    assert r.json()["branch"] == "hml-2-add-login-flow"


def test_branch_not_settable_by_client(client, gh, tree):
    r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"branch": "sneaky"})
    assert r.json()["branch"] is None


def test_missing_ticket(client, gh):
    assert client.post("/api/v1/tickets/999/branch").status_code == 404


def test_branch_shown_in_detail_view(client, gh, tree):
    branch(client, tree["task"])
    html = client.get(f"/tickets/{tree['task']['id']}").text
    assert "<code>hml-2-add-login-flow</code>" in html


class TestToken:
    """The real factory, reading GH_TOKEN from kanana-banana's secrets.env."""

    @pytest.fixture
    def secrets_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KANANA_BANANA_CONFIG_DIR", str(tmp_path))
        return tmp_path

    def test_missing_token(self, client, tree, secrets_dir):
        r = branch(client, tree["task"])
        assert r.status_code == 503
        assert "GH_TOKEN is not set" in r.json()["detail"]
        assert str(secrets_dir / "secrets.env") in r.json()["detail"]

    def test_checks_run_before_token(self, client, tree, secrets_dir):
        assert branch(client, tree["project"]).status_code == 400

    def test_read_secret(self, secrets_dir):
        (secrets_dir / "secrets.env").write_text("# c\nOTHER=x\nGH_TOKEN=abc=def\n")
        assert config.read_secret("GH_TOKEN") == "abc=def"
        assert config.read_secret("NOPE") == ""

    def test_read_secret_no_file(self, secrets_dir):
        assert config.read_secret("GH_TOKEN") == ""
