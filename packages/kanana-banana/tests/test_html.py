"""Smoke tests: every web page renders, and the HTMX forms change data."""

import pytest


@pytest.fixture
def tree(api):
    board = api.board("Homelab", repo_url="https://github.com/o/homelab")
    project = api.project("Big Project", board=board)
    task = api.ticket("A Task", "task", parent_id=project["id"])
    subtask = api.ticket("A Subtask", "subtask", parent_id=task["id"])
    return {"board": board, "project": project, "task": task, "subtask": subtask}


def test_index_empty(client):
    assert client.get("/").status_code == 200


def test_static_assets(client):
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/assets/kanana.png").status_code == 200


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", "Big Project"),
        ("/boards/{board}", "Big Project"),
        ("/boards/{board}/tree", "A Task"),
        ("/boards/{board}/column/to-do", "A Subtask"),
        ("/boards/new", "<form"),
        ("/boards/{board}/edit", "Homelab"),
        ("/boards/{board}/tickets/new", "<form"),
        ("/tickets/{project}", "Big Project"),
        ("/tickets/{task}", "A Task"),
        ("/tickets/{subtask}", "A Subtask"),
        ("/tickets/{task}/edit", "A Task"),
    ],
)
def test_pages_render(client, tree, path, expected):
    url = path.format(**{k: v["id"] for k, v in tree.items()})
    r = client.get(url)
    assert r.status_code == 200, r.text[:500]
    assert expected in r.text


def test_create_board_form(client):
    r = client.post("/boards", data={"key": "frm", "name": "From Form", "repo_url": "", "description": ""})
    assert r.status_code == 200
    [board] = client.get("/api/v1/boards").json()
    assert (board["key"], board["name"]) == ("FRM", "From Form")


@pytest.mark.parametrize(
    ("key", "status", "message"),
    [("HML-1", 400, "letters only"), ("HOMELAB", 409, "already used")],
)
def test_create_board_form_rejects_key(client, tree, key, status, message):
    r = client.post("/boards", data={"key": key, "name": "X", "repo_url": "", "description": ""})
    assert r.status_code == status
    assert message in r.json()["detail"]


def test_board_form_shows_key_read_only_when_editing(client, tree):
    html = client.get(f"/boards/{tree['board']['id']}/edit").text
    assert 'value="HOMELAB" disabled' in html
    assert 'name="key"' not in html


def test_create_ticket_form(client, tree):
    r = client.post(
        f"/boards/{tree['board']['id']}/tickets",
        data={
            "name": "Form Task",
            "ticket_type": "task",
            "status": "to-do",
            "parent_id": str(tree["project"]["id"]),
            "description": "",
        },
    )
    assert r.status_code == 200
    names = {t["name"] for t in client.get("/api/v1/tickets").json()}
    assert "Form Task" in names


def test_edit_ticket_form(client, tree):
    r = client.post(
        f"/tickets/{tree['task']['id']}/edit",
        data={"name": "Renamed", "status": "on-hold", "parent_id": str(tree["project"]["id"]), "description": ""},
    )
    assert r.status_code == 200
    ticket = client.get(f"/api/v1/tickets/{tree['task']['id']}").json()
    assert (ticket["name"], ticket["status"]) == ("Renamed", "on-hold")


def test_move_ticket(client, tree):
    r = client.post(
        f"/boards/{tree['board']['id']}/tickets/{tree['task']['id']}/move",
        params={"status": "in-progress"},
    )
    assert r.status_code == 200
    assert client.get(f"/api/v1/tickets/{tree['task']['id']}").json()["status"] == "in-progress"


def test_delete_ticket_form(client, tree):
    r = client.post(f"/tickets/{tree['task']['id']}/delete")
    assert r.status_code == 200
    names = {t["name"] for t in client.get("/api/v1/tickets").json()}
    assert names == {"Big Project"}


def test_openapi_version_matches_package(client):
    from kanana_banana import __version__
    assert client.get("/openapi.json").json()["info"]["version"] == __version__


def test_keys_shown_on_cards_and_details(client, tree):
    board_html = client.get(f"/boards/{tree['board']['id']}").text
    assert '<span class="ticket-key">HOMELAB-2</span>' in board_html
    for name, key in [("project", "HOMELAB-1"), ("task", "HOMELAB-2"), ("subtask", "HOMELAB-3")]:
        assert f'<span class="ticket-key">{key}</span>' in client.get(f"/tickets/{tree[name]['id']}").text
