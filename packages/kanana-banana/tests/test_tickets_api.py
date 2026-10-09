import pytest


@pytest.fixture
def tree(api):
    """Board -> project -> task -> subtask."""
    board = api.board(repo_url="https://github.com/o/homelab")
    project = api.project("Project", board=board)
    task = api.ticket("Task", "task", parent_id=project["id"])
    subtask = api.ticket("Subtask", "subtask", parent_id=task["id"])
    return {"board": board, "project": project, "task": task, "subtask": subtask}


class TestCreate:
    def test_defaults(self, tree):
        project = tree["project"]
        assert project["status"] == "to-do"
        assert project["description"] == ""
        assert project["parent_id"] is None
        assert {"id", "created_at", "updated_at"} <= project.keys()

    def test_children_inherit_board(self, tree):
        board_id = tree["board"]["id"]
        assert tree["task"]["board_id"] == board_id
        assert tree["subtask"]["board_id"] == board_id

    def test_child_board_id_is_ignored_in_favour_of_parent(self, client, api, tree):
        other = api.board("Other")
        task = api.ticket("T", "task", parent_id=tree["project"]["id"], board_id=other["id"])
        assert task["board_id"] == tree["board"]["id"]

    @pytest.mark.parametrize(
        ("ticket_type", "parent", "message"),
        [
            ("project", "project", "Projects cannot have a parent"),
            ("task", "task", "Tasks must have a project"),
            ("task", "subtask", "Tasks must have a project"),
            ("subtask", "project", "Subtasks must have a task"),
            ("subtask", "subtask", "Subtasks must have a task"),
        ],
    )
    def test_hierarchy_rules(self, client, tree, ticket_type, parent, message):
        body = {"name": "x", "ticket_type": ticket_type, "parent_id": tree[parent]["id"]}
        if ticket_type == "project":
            body["board_id"] = tree["board"]["id"]
        r = client.post("/api/v1/tickets", json=body)
        assert r.status_code == 400
        assert message in r.json()["detail"]

    def test_project_needs_board(self, client):
        r = client.post("/api/v1/tickets", json={"name": "p", "ticket_type": "project"})
        assert r.status_code == 400
        assert "must belong to a board" in r.json()["detail"]

    def test_parentless_task(self, client, tree):
        r = client.post("/api/v1/tickets", json={
            "name": "Fix typo", "ticket_type": "task", "board_id": tree["board"]["id"],
        })
        assert r.status_code == 201
        assert r.json()["parent_id"] is None
        assert r.json()["board_id"] == tree["board"]["id"]
        assert r.json()["key"] == "HOMELAB-4"

    def test_parentless_task_needs_board(self, client):
        r = client.post("/api/v1/tickets", json={"name": "x", "ticket_type": "task"})
        assert r.status_code == 400
        assert "must belong to a board" in r.json()["detail"]

    def test_parentless_task_board_must_exist(self, client):
        r = client.post("/api/v1/tickets", json={"name": "x", "ticket_type": "task", "board_id": 999})
        assert r.status_code == 400

    def test_parentless_task_can_have_subtasks(self, api, tree):
        task = api.ticket("Loose", "task", board_id=tree["board"]["id"])
        subtask = api.ticket("Part", "subtask", parent_id=task["id"])
        assert subtask["board_id"] == tree["board"]["id"]

    def test_detach_task_from_project(self, client, tree):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"parent_id": None})
        assert r.status_code == 200
        assert r.json()["parent_id"] is None
        assert r.json()["board_id"] == tree["board"]["id"]

    def test_project_board_must_exist(self, client):
        r = client.post("/api/v1/tickets", json={"name": "p", "ticket_type": "project", "board_id": 999})
        assert r.status_code == 400
        assert "not found" in r.json()["detail"]

    @pytest.mark.parametrize("ticket_type", ["task", "subtask"])
    def test_missing_parent(self, client, ticket_type):
        r = client.post("/api/v1/tickets", json={"name": "x", "ticket_type": ticket_type, "parent_id": 999})
        assert r.status_code == 400
        assert "not found" in r.json()["detail"]

    def test_subtask_needs_parent(self, client):
        r = client.post("/api/v1/tickets", json={"name": "x", "ticket_type": "subtask"})
        assert r.status_code == 400

    def test_name_required(self, client, tree):
        r = client.post("/api/v1/tickets", json={"ticket_type": "task", "parent_id": tree["project"]["id"]})
        assert r.status_code == 422

    def test_name_length_limit(self, client, tree):
        r = client.post("/api/v1/tickets", json={
            "name": "x" * 201, "ticket_type": "task", "parent_id": tree["project"]["id"],
        })
        assert r.status_code == 422


class TestRead:
    def test_get(self, client, tree):
        r = client.get(f"/api/v1/tickets/{tree['task']['id']}")
        assert r.status_code == 200
        assert r.json()["name"] == "Task"

    def test_get_missing(self, client):
        assert client.get("/api/v1/tickets/999").status_code == 404

    def test_list_all(self, client, tree):
        assert len(client.get("/api/v1/tickets").json()) == 3

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({"ticket_type": "task"}, {"Task"}),
            ({"ticket_type": "project"}, {"Project"}),
            ({"status": "done"}, {"Subtask"}),
        ],
    )
    def test_list_filters(self, client, tree, params, expected):
        client.patch(f"/api/v1/tickets/{tree['subtask']['id']}/status", params={"new_status": "done"})
        names = {t["name"] for t in client.get("/api/v1/tickets", params=params).json()}
        assert names == expected

    def test_list_by_parent(self, client, api, tree):
        api.ticket("Task 2", "task", parent_id=tree["project"]["id"])
        r = client.get("/api/v1/tickets", params={"parent_id": tree["project"]["id"]})
        assert {t["name"] for t in r.json()} == {"Task", "Task 2"}

    def test_invalid_filter(self, client):
        assert client.get("/api/v1/tickets", params={"status": "nope"}).status_code == 422


class TestUpdate:
    def test_partial(self, client, tree):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"description": "new"})
        assert r.status_code == 200
        assert r.json()["description"] == "new"
        assert r.json()["name"] == "Task"

    def test_bumps_updated_at(self, client, tree):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"name": "Renamed"})
        assert r.json()["updated_at"] > tree["task"]["updated_at"]

    def test_status(self, client, tree):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"status": "on-hold"})
        assert r.json()["status"] == "on-hold"

    def test_reparent_task_within_board(self, client, api, tree):
        other = api.project("Other project", board=tree["board"])
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"parent_id": other["id"]})
        assert r.status_code == 200
        assert r.json()["parent_id"] == other["id"]
        assert r.json()["key"] == tree["task"]["key"]

    def test_cannot_move_between_boards(self, client, api, tree):
        other = api.project("Other project", board=api.board("Other"))
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"parent_id": other["id"]})
        assert r.status_code == 400
        assert "between boards" in r.json()["detail"]
        assert client.get(f"/api/v1/tickets/{tree['task']['id']}").json()["parent_id"] == tree["project"]["id"]

    def test_project_cannot_change_board(self, client, api, tree):
        other = api.board("Other")
        r = client.patch(f"/api/v1/tickets/{tree['project']['id']}", json={"board_id": other["id"]})
        assert r.status_code == 400

    def test_reparent_breaking_hierarchy(self, client, tree):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"parent_id": tree["subtask"]["id"]})
        assert r.status_code == 400

    def test_missing(self, client):
        assert client.patch("/api/v1/tickets/999", json={"name": "x"}).status_code == 404


class TestStatusEndpoint:
    @pytest.mark.parametrize("status", ["to-do", "in-progress", "on-hold", "done"])
    def test_move(self, client, tree, status):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}/status", params={"new_status": status})
        assert r.status_code == 200
        assert r.json()["status"] == status

    def test_invalid(self, client, tree):
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}/status", params={"new_status": "nope"})
        assert r.status_code == 422

    def test_missing(self, client):
        r = client.patch("/api/v1/tickets/999/status", params={"new_status": "done"})
        assert r.status_code == 404


class TestDelete:
    def test_leaf(self, client, tree):
        assert client.delete(f"/api/v1/tickets/{tree['subtask']['id']}").status_code == 204
        assert client.get(f"/api/v1/tickets/{tree['subtask']['id']}").status_code == 404
        assert client.get(f"/api/v1/tickets/{tree['task']['id']}").status_code == 200

    def test_cascades_to_all_descendants(self, client, tree):
        assert client.delete(f"/api/v1/tickets/{tree['project']['id']}").status_code == 204
        for key in ("project", "task", "subtask"):
            assert client.get(f"/api/v1/tickets/{tree[key]['id']}").status_code == 404
        assert client.get("/api/v1/tickets").json() == []

    def test_missing(self, client):
        assert client.delete("/api/v1/tickets/999").status_code == 404


class TestExport:
    def test_task(self, client, tree):
        client.patch(f"/api/v1/tickets/{tree['subtask']['id']}/status", params={"new_status": "done"})
        client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"description": "Do the thing."})
        r = client.get(f"/api/v1/tickets/{tree['task']['id']}/export")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/markdown")
        md = r.text
        assert md.startswith("# [TASK] Task\n")
        assert "- **Key:** HOMELAB-2" in md
        assert "- **Status:** to-do" in md
        assert "- **Parent:** [PROJECT] Project (HOMELAB-1)" in md
        assert "- **Repo:** https://github.com/o/homelab" in md
        assert "## Description\n\nDo the thing." in md
        assert "- [x] [SUBTASK] Subtask (HOMELAB-3) — done" in md

    def test_project_lists_tasks(self, client, tree):
        md = client.get(f"/api/v1/tickets/{tree['project']['id']}/export").text
        assert "## Tasks" in md
        assert "- [ ] [TASK] Task (HOMELAB-2) — to-do" in md

    def test_missing(self, client):
        assert client.get("/api/v1/tickets/999/export").status_code == 404


class TestNumbersAndKeys:
    def test_sequential_per_board(self, tree):
        assert [tree[k]["number"] for k in ("project", "task", "subtask")] == [1, 2, 3]
        assert [tree[k]["key"] for k in ("project", "task", "subtask")] == [
            "HOMELAB-1", "HOMELAB-2", "HOMELAB-3",
        ]

    def test_boards_number_independently(self, api, tree):
        other = api.project("P", board=api.board("Other", key="oth"))
        assert other["key"] == "OTH-1"
        assert api.ticket("T", parent_id=tree["project"]["id"])["key"] == "HOMELAB-4"

    def test_numbers_not_reused_after_delete(self, client, api, tree):
        client.delete(f"/api/v1/tickets/{tree['subtask']['id']}")
        assert api.ticket("S2", "subtask", parent_id=tree["task"]["id"])["key"] == "HOMELAB-4"

    def test_failed_create_does_not_use_a_number(self, client, api, tree):
        client.post("/api/v1/tickets", json={"name": "bad", "ticket_type": "subtask", "parent_id": tree["project"]["id"]})
        assert api.ticket("Good", parent_id=tree["project"]["id"])["key"] == "HOMELAB-4"

    def test_key_and_number_not_settable(self, client, tree):
        r = client.post("/api/v1/tickets", json={
            "name": "x", "ticket_type": "task", "parent_id": tree["project"]["id"],
            "key": "HOMELAB-99", "number": 99,
        })
        assert r.json()["key"] == "HOMELAB-4"
        r = client.patch(f"/api/v1/tickets/{tree['task']['id']}", json={"key": "X-1", "number": 7})
        assert (r.json()["key"], r.json()["number"]) == ("HOMELAB-2", 2)

    @pytest.mark.parametrize("key", ["HOMELAB-2", "homelab-2", " Homelab-2 "])
    def test_by_key(self, client, tree, key):
        r = client.get(f"/api/v1/tickets/by-key/{key}")
        assert r.status_code == 200
        assert r.json()["id"] == tree["task"]["id"]

    @pytest.mark.parametrize("key", ["HOMELAB-99", "NOPE-1", "garbage"])
    def test_by_key_missing(self, client, tree, key):
        r = client.get(f"/api/v1/tickets/by-key/{key}")
        assert r.status_code == 404


class TestListByBoard:
    def test_board_filter_and_order(self, client, api, tree):
        other = api.project("Elsewhere", board=api.board("Other"))
        api.ticket("Late task", parent_id=tree["project"]["id"])
        r = client.get("/api/v1/tickets", params={"board_id": tree["board"]["id"]})
        assert [t["key"] for t in r.json()] == ["HOMELAB-1", "HOMELAB-2", "HOMELAB-3", "HOMELAB-4"]
        assert other["key"] not in {t["key"] for t in r.json()}
