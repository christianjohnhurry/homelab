import json

import pytest

from kanana_banana import cli


@pytest.fixture
def board(kb):
    kb("board", "add", "hml", "Homelab", "--repo", "https://github.com/o/homelab")


@pytest.fixture
def tree(kb, board):
    """HML-1 project > HML-2 task > HML-3 subtask, plus HML-4 parentless task."""
    for args in [
        ("add", "Big Project", "--project", "--board", "hml"),
        ("add", "Add login", "--parent", "HML-1", "-d", "Login with GitHub."),
        ("add", "Login form", "--parent", "hml-2"),
        ("add", "Fix typo", "--board", "hml"),
    ]:
        r = kb(*args)
        assert r.exit_code == 0, r.output


def show_json(kb, key):
    return json.loads(kb("show", key, "--json").output)


class TestAdd:
    def test_types_follow_parent(self, kb, tree):
        types = {k: show_json(kb, k)["ticket_type"] for k in ["HML-1", "HML-2", "HML-3", "HML-4"]}
        assert types == {"HML-1": "project", "HML-2": "task", "HML-3": "subtask", "HML-4": "task"}

    def test_output(self, kb, board):
        r = kb("add", "Something", "--board", "hml")
        assert r.output.strip() == "Created HML-1 [TASK] Something"

    def test_parentless_task_has_no_parent(self, kb, tree):
        assert show_json(kb, "HML-4")["parent_id"] is None

    def test_description(self, kb, tree):
        assert show_json(kb, "HML-2")["description"] == "Login with GitHub."

    def test_board_from_git_origin(self, kb, board, monkeypatch):
        monkeypatch.setattr(cli, "git_origin_repo", lambda: "o/homelab")
        r = kb("add", "From repo")
        assert r.exit_code == 0, r.output
        assert "HML-1" in r.output

    def test_parent_carries_board(self, kb, tree, monkeypatch):
        monkeypatch.setattr(cli, "git_origin_repo", lambda: "o/somewhere-else")
        assert kb("add", "Child", "--parent", "HML-1").exit_code == 0

    def test_subtask_cannot_have_children(self, kb, tree):
        r = kb("add", "Too deep", "--parent", "HML-3")
        assert r.exit_code == 1
        assert "subtasks can't have children" in r.output

    def test_project_with_parent(self, kb, tree):
        r = kb("add", "x", "--project", "--parent", "HML-1")
        assert r.exit_code == 1
        assert "can't have a parent" in r.output

    def test_unknown_parent(self, kb, tree):
        r = kb("add", "x", "--parent", "HML-99")
        assert r.exit_code == 1
        assert "HML-99 not found" in r.output

    def test_no_board(self, kb, board):
        r = kb("add", "x")
        assert r.exit_code == 1
        assert "Pass --board KEY" in r.output


class TestList:
    def test_table_in_number_order(self, kb, tree):
        lines = kb("list", "--board", "hml").output.splitlines()
        assert lines[0].split() == ["KEY", "TYPE", "STATUS", "NAME"]
        assert [line.split()[0] for line in lines[1:]] == ["HML-1", "HML-2", "HML-3", "HML-4"]
        assert lines[2].split() == ["HML-2", "task", "to-do", "Add", "login"]

    def test_only_this_board(self, kb, tree):
        kb("board", "add", "oth", "Other")
        kb("add", "Elsewhere", "--board", "oth")
        assert "Elsewhere" not in kb("list", "--board", "hml").output
        assert "OTH-1" in kb("list", "--board", "oth").output

    def test_filters(self, kb, tree):
        kb("move", "HML-3", "done")
        assert [l.split()[0] for l in kb("list", "--board", "hml", "-s", "done").output.splitlines()[1:]] == ["HML-3"]
        assert [l.split()[0] for l in kb("list", "--board", "hml", "-t", "task").output.splitlines()[1:]] == ["HML-2", "HML-4"]

    @pytest.mark.parametrize(("flag", "value"), [("--status", "nope"), ("--type", "epic")])
    def test_invalid_filter(self, kb, tree, flag, value):
        r = kb("list", "--board", "hml", flag, value)
        assert r.exit_code == 1
        assert "must be one of" in r.output

    def test_tree(self, kb, tree):
        assert kb("list", "--board", "hml", "--tree").output.splitlines() == [
            "HML-1  Big Project  (to-do)",
            "  HML-2  Add login  (to-do)",
            "    HML-3  Login form  (to-do)",
            "HML-4  Fix typo  (to-do)",
        ]

    def test_tree_with_filter_refused(self, kb, tree):
        assert kb("list", "--board", "hml", "--tree", "-s", "done").exit_code == 1

    def test_json(self, kb, tree):
        tickets = json.loads(kb("list", "--board", "hml", "--json").output)
        assert [t["key"] for t in tickets] == ["HML-1", "HML-2", "HML-3", "HML-4"]

    def test_empty(self, kb, board):
        assert "No tickets on HML" in kb("list", "--board", "hml").output


class TestShow:
    def test_text(self, kb, tree):
        out = kb("show", "hml-2").output
        assert out.splitlines()[0] == "HML-2 [TASK] Add login"
        assert "Status:  to-do" in out
        assert "Parent:  HML-1 [PROJECT] Big Project" in out
        assert "Branch:  -" in out
        assert "Login with GitHub." in out
        assert "- HML-3 [SUBTASK] Login form  (to-do)" in out

    def test_json_adds_parent_key_and_children(self, kb, tree):
        data = show_json(kb, "HML-2")
        assert data["key"] == "HML-2"
        assert data["parent_key"] == "HML-1"
        assert data["children"] == [{"key": "HML-3", "name": "Login form", "status": "to-do"}]

    def test_missing(self, kb, tree):
        r = kb("show", "HML-99")
        assert r.exit_code == 1
        assert "HML-99 not found" in r.output


class TestMove:
    def test_move(self, kb, tree):
        r = kb("move", "hml-2", "in-progress")
        assert r.output.strip() == "HML-2: to-do → in-progress"
        assert show_json(kb, "HML-2")["status"] == "in-progress"

    def test_invalid_status(self, kb, tree):
        r = kb("move", "HML-2", "doing")
        assert r.exit_code == 1
        assert "must be one of" in r.output
        assert show_json(kb, "HML-2")["status"] == "to-do"


class TestEdit:
    def test_name_and_description(self, kb, tree):
        r = kb("edit", "HML-2", "--name", "Add OAuth login", "-d", "New text")
        assert r.output.strip() == "Updated HML-2 [TASK] Add OAuth login"
        data = show_json(kb, "HML-2")
        assert (data["name"], data["description"]) == ("Add OAuth login", "New text")

    def test_clear_description(self, kb, tree):
        kb("edit", "HML-2", "-d", "")
        assert show_json(kb, "HML-2")["description"] == ""

    def test_nothing_to_change(self, kb, tree):
        r = kb("edit", "HML-2")
        assert r.exit_code == 1
        assert "nothing to change" in r.output


class TestDelete:
    def test_confirm_lists_descendants(self, kb, tree):
        r = kb("delete", "HML-1", input="y\n")
        assert "Delete HML-1 [PROJECT] Big Project and the 2 ticket(s) under it?" in r.output
        assert "Deleted HML-1 and 2 more" in r.output
        assert kb("show", "HML-3").exit_code == 1

    def test_declined(self, kb, tree):
        r = kb("delete", "HML-2", input="n\n")
        assert r.exit_code == 1
        assert show_json(kb, "HML-2")["key"] == "HML-2"

    def test_yes_skips_prompt(self, kb, tree):
        r = kb("delete", "HML-4", "--yes")
        assert r.exit_code == 0
        assert "?" not in r.output
        assert r.output.strip() == "Deleted HML-4"


class TestExport:
    def test_markdown(self, kb, tree):
        out = kb("export", "HML-2").output
        assert out.startswith("# [TASK] Add login\n")
        assert "- **Key:** HML-2" in out
        assert "Login form (HML-3)" in out
