import pytest
from typer.testing import CliRunner

from dev_spaces import __version__, branches, cli, config
from dev_spaces.cli import app

from conftest import container_info

CODE = cli.CODE_DIR
runner = CliRunner()


def invoke(*args: str, input: str | None = None):
    return runner.invoke(app, list(args), input=input)


def test_version():
    result = invoke("--version")
    assert result.exit_code == 0
    assert result.output.strip() == f"dev-spaces {__version__}"


# --- create ------------------------------------------------------------------

REMOTE = ["feat/login-flow", "feat/logout", "fix/export-bug", "main"]


@pytest.fixture
def remote(monkeypatch):
    """Fake GitHub: the remote branches and default branch create will see."""
    state = {"branches": list(REMOTE), "default": "main", "tokens": []}

    def remote_branches(repo, token):
        state["tokens"].append(token)
        return state["branches"]

    monkeypatch.setattr(branches, "remote_branches", remote_branches)
    monkeypatch.setattr(branches, "default_branch", lambda repo, token: state["default"])
    return state


@pytest.fixture
def ready(initialised, fake_docker, remote):
    """Everything create needs: config, image present, no existing container."""
    fake_docker.respond("container", "inspect", returncode=1)
    return fake_docker


def created(fake) -> bool:
    return bool(fake.called("run"))


def call_index(fake, *prefix: str) -> int:
    for i, call in enumerate(fake.calls):
        if call[: len(prefix)] == prefix:
            return i
    raise AssertionError(f"no call starting with {prefix}")


class TestCreateArguments:
    @pytest.mark.parametrize(
        "args", [["owner/repo"], ["owner/repo", "feat", "--new", "x"]]
    )
    def test_needs_exactly_one_of_prefix_or_new(self, ready, args):
        result = invoke("create", *args)
        assert result.exit_code == 1
        assert "either a branch PREFIX or --new NAME" in result.output
        assert not created(ready)

    def test_without_init(self, config_dir, fake_docker):
        result = invoke("create", "owner/repo", "feat")
        assert result.exit_code == 1
        assert "dev-spaces init" in result.output

    def test_without_secrets_file(self, initialised, fake_docker, remote):
        config.secrets_path().unlink()
        result = invoke("create", "owner/repo", "feat")
        assert result.exit_code == 1
        assert "secrets.env not found" in result.output
        assert not created(fake_docker)

    def test_missing_image(self, ready):
        ready.respond("image", "inspect", returncode=1)
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 1
        assert "dev-spaces build" in result.output
        assert not created(ready)

    def test_bad_repo(self, ready):
        result = invoke("create", "not-a-repo", "fix")
        assert result.exit_code == 1
        assert "owner/repo" in result.output
        assert not created(ready)

    def test_container_exists(self, ready):
        ready.respond("container", "inspect", "export-bug")
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 1
        assert "dev-spaces shell export-bug" in result.output
        assert not created(ready)

    def test_new_branch_already_on_remote(self, ready):
        result = invoke("create", "owner/repo", "--new", "main")
        assert result.exit_code == 1
        assert "already exists" in result.output
        assert not created(ready)

    def test_uses_github_token(self, ready, remote):
        invoke("create", "owner/repo", "fix")
        assert remote["tokens"] == ["gh-test-token"]

    def test_warns_without_claude_token(self, ready):
        config.secrets_path().write_text("GH_TOKEN=gh-test-token\nCLAUDE_CODE_OAUTH_TOKEN=\n")
        result = invoke("create", "owner/repo", "fix")
        assert "claude setup-token" in result.output
        assert result.exit_code == 0


class TestBranchResolution:
    def test_single_match_no_prompt(self, ready):
        result = invoke("create", "owner/repo", "FIX/")
        assert result.exit_code == 0
        assert "@ fix/export-bug" in result.output
        assert "Pick one" not in result.output

    def test_no_match_asks_again(self, ready):
        result = invoke("create", "owner/repo", "nope", input="also-nope\nmain\n")
        assert result.exit_code == 0
        assert result.output.count("No remote branch starts with") == 2
        assert "@ main" in result.output

    def test_several_matches_pick(self, ready):
        result = invoke("create", "owner/repo", "feat/log", input="2\n")
        assert result.exit_code == 0
        assert "1. feat/login-flow" in result.output
        assert "2. feat/logout" in result.output
        assert "@ feat/logout" in result.output

    def test_out_of_range_pick_asks_again(self, ready):
        result = invoke("create", "owner/repo", "feat/log", input="0\n3\n1\n")
        assert result.exit_code == 0
        assert "@ feat/login-flow" in result.output

    def test_nothing_created_before_resolved(self, ready):
        # Input runs out while still prompting: no container should exist
        result = invoke("create", "owner/repo", "nope", input="")
        assert result.exit_code != 0
        assert not created(ready)


class TestCreate:
    def test_run_arguments(self, ready):
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 0, result.output
        [run] = ready.called("run")
        assert run[-1] == f"dev-spaces-base:{__version__}"
        for label in [
            "dev-spaces=1",
            "dev-spaces.repo=owner/repo",
            "dev-spaces.branch=fix/export-bug",
            f"dev-spaces.version={__version__}",
        ]:
            assert label in run
        assert ("--name", "export-bug") == run[run.index("--name") : run.index("--name") + 2]
        assert run[run.index("--env-file") + 1] == str(config.secrets_path())
        assert "DEV_SPACE=export-bug" in run
        assert "--init" in run
        published = [run[i + 1] for i, a in enumerate(run) if a == "--publish"]
        assert published == ["127.0.0.1::8000", "127.0.0.1::8080", "127.0.0.1::5173", "127.0.0.1::3000"]

    def test_setup_order(self, ready):
        invoke("create", "owner/repo", "fix")
        order = [
            call_index(ready, "run"),
            call_index(ready, "cp"),
            call_index(ready, "exec", "--user", "root", "export-bug", "chown"),
            call_index(ready, "exec", "export-bug", "gh", "auth", "setup-git"),
            call_index(ready, "exec", "--workdir", CODE, "export-bug", "git", "clone"),
            call_index(ready, "exec", "--workdir", CODE, "export-bug", "git", "checkout", "fix/export-bug"),
            call_index(ready, "exec", "--workdir", CODE, "export-bug", "pixi", "install"),
        ]
        assert order == sorted(order)

    def test_git_identity_and_push_default(self, ready):
        invoke("create", "owner/repo", "fix")
        assert ready.called("exec", "export-bug", "git", "config", "--global", "user.name", "Test User")
        assert ready.called("exec", "export-bug", "git", "config", "--global", "user.email", "test@example.com")
        assert ready.called("exec", "export-bug", "git", "config", "--global", "push.autoSetupRemote", "true")

    def test_clones_into_code(self, ready):
        invoke("create", "https://github.com/owner/repo.git", "fix")
        assert ready.called(
            "exec", "--workdir", CODE, "export-bug",
            "git", "clone", "https://github.com/owner/repo.git", CODE,
        )

    def test_new_branch_has_no_upstream(self, ready, remote):
        remote["default"] = "trunk"
        result = invoke("create", "owner/repo", "--new", "feat/Shiny")
        assert result.exit_code == 0, result.output
        assert ready.called(
            "exec", "--workdir", CODE, "shiny",
            "git", "switch", "--no-track", "--create", "feat/Shiny", "origin/trunk",
        )
        assert not ready.called("exec", "--workdir", CODE, "shiny", "git", "checkout")

    def test_failed_clone_removes_container(self, ready):
        ready.respond("exec", "--workdir", CODE, "export-bug", "git", "clone", returncode=128)
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 1
        assert ready.called("rm", "--force", "export-bug")
        assert "Removed export-bug" in result.output

    def test_failed_setup_step_removes_container(self, ready):
        ready.respond("exec", "export-bug", "gh", "auth", returncode=1)
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 1
        assert ready.called("rm", "--force", "export-bug")

    def test_failed_run_reports_error(self, ready):
        ready.respond("run", returncode=125)
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 1
        assert not ready.called("exec")

    def test_failed_install_keeps_container(self, ready):
        ready.respond("exec", "--workdir", CODE, "export-bug", "pixi", returncode=1)
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 0
        assert "warning:" in result.output
        assert not ready.called("rm")
        assert "Ready: export-bug" in result.output

    def test_unrecognised_project_skips_install(self, ready):
        ready.respond("exec", "export-bug", "test", "-f", returncode=1)
        ready.respond("exec", "export-bug", "grep", returncode=1)
        result = invoke("create", "owner/repo", "fix")
        assert result.exit_code == 0
        assert "skipping dependency install" in result.output
        assert not ready.called("exec", "--workdir", CODE, "export-bug", "pixi")


# --- inspecting containers ------------------------------------------------------


@pytest.fixture
def containers(fake_docker):
    fake_docker.containers = {
        "login-flow": container_info("login-flow", ports={"8000": "55012", "3000": "55010"}),
        "export-bug": container_info("export-bug", running=False),
        "not-ours": container_info("not-ours", labels={}),
    }
    fake_docker.respond(
        "exec", "login-flow", "git", "-C", CODE, "branch", "--show-current",
        stdout="feat/login-flow-part-2\n",
    )
    return fake_docker


class TestList:
    def test_table(self, containers):
        result = invoke("list")
        assert result.exit_code == 0
        lines = result.output.splitlines()
        assert lines[0].split() == ["NAME", "REPO", "BRANCH", "STATUS", "PORTS"]
        assert lines[1].split() == [
            "export-bug", "owner/repo", "feat/export-bug", "exited", "-",
        ]
        assert lines[2].split() == [
            "login-flow", "owner/repo", "feat/login-flow-part-2", "running", "3000→55010", "8000→55012",
        ]
        assert "not-ours" not in result.output

    def test_stopped_shows_label_branch_without_exec(self, containers):
        invoke("list")
        assert not containers.called("exec", "export-bug")

    def test_empty(self, fake_docker):
        result = invoke("list")
        assert result.exit_code == 0
        assert "No dev-spaces containers" in result.output


class TestGet:
    @pytest.mark.parametrize("command", ["shell", "ports", "start", "stop", "remove"])
    def test_unknown_name(self, containers, command):
        result = invoke(command, "nope")
        assert result.exit_code == 1
        assert "no container named 'nope'" in result.output

    @pytest.mark.parametrize("command", ["shell", "ports", "start", "stop", "remove"])
    def test_not_a_dev_space(self, containers, command):
        result = invoke(command, "not-ours")
        assert result.exit_code == 1
        assert "not a dev-spaces container" in result.output
        assert not containers.called("rm")
        assert not containers.called("stop")


class TestPorts:
    def test_urls(self, containers):
        result = invoke("ports", "login-flow")
        assert result.exit_code == 0
        assert result.output.splitlines() == [
            " 3000 → http://localhost:55010",
            " 8000 → http://localhost:55012",
        ]

    def test_stopped(self, containers):
        result = invoke("ports", "export-bug")
        assert result.exit_code == 1
        assert "stopped" in result.output


class TestShellStartStop:
    def test_shell_running(self, containers):
        result = invoke("shell", "login-flow")
        assert result.exit_code == 0
        assert containers.exec_interactive_args == ("--workdir", CODE, "login-flow", "zsh")
        assert not containers.called("start")

    def test_shell_starts_stopped(self, containers):
        result = invoke("shell", "export-bug")
        assert "Starting export-bug" in result.output
        assert containers.called("start", "export-bug")
        assert containers.exec_interactive_args == ("--workdir", CODE, "export-bug", "zsh")

    def test_start(self, containers):
        assert invoke("start", "export-bug").exit_code == 0
        assert containers.called("start", "export-bug")

    def test_stop(self, containers):
        assert invoke("stop", "login-flow").exit_code == 0
        assert containers.called("stop", "login-flow")


# --- remove ----------------------------------------------------------------------


def git_says(fake, name: str, subcommand: str, stdout: str) -> None:
    fake.respond("exec", name, "git", "-C", CODE, subcommand, stdout=stdout)


class TestRemove:
    def test_clean_container_removed(self, containers):
        result = invoke("remove", "login-flow")
        assert result.exit_code == 0
        assert containers.called("rm", "--force", "login-flow")

    @pytest.mark.parametrize(
        ("subcommand", "stdout", "reason"),
        [
            ("status", " M README.md\n?? scratch.txt", "uncommitted changes"),
            ("log", "b2d924c local only (HEAD -> feat/x)", "commits not pushed"),
            ("stash", "stash@{0}: WIP on feat/x", "stashed changes"),
        ],
    )
    def test_refuses_unsaved_work(self, containers, subcommand, stdout, reason):
        git_says(containers, "login-flow", subcommand, stdout)
        result = invoke("remove", "login-flow")
        assert result.exit_code == 1
        assert reason in result.output
        assert stdout.splitlines()[0].strip() in result.output
        assert "--force" in result.output
        assert not containers.called("rm")

    def test_lists_every_problem(self, containers):
        git_says(containers, "login-flow", "status", "?? a")
        git_says(containers, "login-flow", "log", "abc msg")
        git_says(containers, "login-flow", "stash", "stash@{0}: x")
        result = invoke("remove", "login-flow")
        for reason in ["uncommitted changes", "commits not pushed", "stashed changes"]:
            assert reason in result.output

    def test_unpushed_check_covers_all_branches(self, containers):
        invoke("remove", "login-flow")
        [log] = containers.called("exec", "login-flow", "git", "-C", CODE, "log")
        assert "--branches" in log and "--not" in log and "--remotes" in log

    def test_long_lists_are_truncated(self, containers):
        git_says(containers, "login-flow", "status", "\n".join(f"?? f{i}" for i in range(25)))
        result = invoke("remove", "login-flow")
        assert "?? f9" in result.output
        assert "?? f10" not in result.output
        assert "and 15 more" in result.output

    def test_force_skips_check(self, containers):
        git_says(containers, "login-flow", "status", "?? a")
        result = invoke("remove", "login-flow", "--force")
        assert result.exit_code == 0
        assert containers.called("rm", "--force", "login-flow")
        assert not containers.called("exec")

    def test_stopped_is_started_for_check_then_removed(self, containers):
        result = invoke("remove", "export-bug")
        assert result.exit_code == 0
        assert call_index(containers, "start", "export-bug") < call_index(containers, "rm", "--force", "export-bug")

    def test_stopped_refused_is_stopped_again(self, containers):
        git_says(containers, "export-bug", "status", "?? a")
        result = invoke("remove", "export-bug")
        assert result.exit_code == 1
        assert containers.called("start", "export-bug")
        assert containers.called("stop", "export-bug")
        assert not containers.called("rm")

    def test_running_refused_is_left_running(self, containers):
        git_says(containers, "login-flow", "status", "?? a")
        invoke("remove", "login-flow")
        assert not containers.called("stop")

    def test_no_repo_inside(self, containers):
        containers.respond("exec", "login-flow", "test", "-d", returncode=1)
        result = invoke("remove", "login-flow")
        assert result.exit_code == 0
        assert not containers.called("exec", "login-flow", "git")
        assert containers.called("rm", "--force", "login-flow")
