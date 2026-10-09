import json

import pytest


@pytest.fixture
def tree(kb, gh):
    kb("board", "add", "hml", "Homelab", "--repo", "https://github.com/o/homelab")
    kb("add", "Big Project", "--project", "--board", "hml")
    kb("add", "Add login flow", "--parent", "HML-1")
    kb("add", "Login form UI", "--parent", "HML-2")


def test_task(kb, gh, tree):
    r = kb("branch", "hml-2")
    assert r.exit_code == 0, r.output
    assert r.output.splitlines() == [
        "Created branch hml-2-add-login-flow for HML-2 [TASK] Add login flow",
        "",
        "Start working on it:",
        "  dev-spaces create o/homelab hml-2-add-login-flow",
    ]
    assert gh.created_from["hml-2-add-login-flow"] == "sha-main"


def test_subtask_stacked(kb, gh, tree):
    kb("branch", "HML-2")
    r = kb("branch", "HML-3")
    assert r.exit_code == 0, r.output
    assert "Created branch hml-3-login-form-ui" in r.output
    assert "Stacked on hml-2-add-login-flow: open its PR against that branch." in r.output
    assert "dev-spaces create o/homelab hml-3-login-form-ui" in r.output
    assert gh.created_from["hml-3-login-form-ui"] == "sha-hml-2-add-login-flow"


def test_subtask_before_task(kb, gh, tree):
    r = kb("branch", "HML-3")
    assert r.exit_code == 1
    assert "Create HML-2's branch first" in r.output


def test_project(kb, gh, tree):
    r = kb("branch", "HML-1")
    assert r.exit_code == 1
    assert "Projects don't get branches" in r.output


def test_twice(kb, gh, tree):
    kb("branch", "HML-2")
    r = kb("branch", "HML-2")
    assert r.exit_code == 1
    assert "already has branch hml-2-add-login-flow" in r.output


def test_recorded_on_ticket(kb, gh, tree):
    kb("branch", "HML-2")
    assert json.loads(kb("show", "HML-2", "--json").output)["branch"] == "hml-2-add-login-flow"
    assert "Branch:  hml-2-add-login-flow" in kb("show", "HML-2").output


def test_github_failure_is_clean(kb, gh, tree):
    gh.fail_with = 403
    r = kb("branch", "HML-2")
    assert r.exit_code == 1
    assert "Could not read o/homelab (403" in r.output
    assert "Traceback" not in r.output
