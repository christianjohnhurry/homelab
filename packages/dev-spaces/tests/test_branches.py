import base64
import subprocess

import pytest

from dev_spaces import branches
from dev_spaces.branches import BranchError

TOKEN = "github_pat_SECRET123"


class TestParseRepo:
    @pytest.mark.parametrize(
        "value",
        [
            "owner/repo",
            "owner/repo.git",
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "https://github.com/owner/repo/",
            "git@github.com:owner/repo.git",
            "git@github.com:owner/repo",
            "  owner/repo  ",
        ],
    )
    def test_normalises(self, value):
        assert branches.parse_repo(value) == "owner/repo"

    def test_keeps_dots_and_dashes(self):
        assert branches.parse_repo("my-org/my.repo-name") == "my-org/my.repo-name"

    @pytest.mark.parametrize(
        "value",
        [
            "repo",
            "",
            "https://gitlab.com/owner/repo",
            "https://github.com/owner/repo/tree/main",
            "owner/repo/extra",
        ],
    )
    def test_rejects(self, value):
        with pytest.raises(BranchError):
            branches.parse_repo(value)


class TestMatch:
    BRANCHES = ["feat/Login-Flow", "feat/logout", "fix/export-bug", "main"]

    def test_case_insensitive(self):
        assert branches.match(self.BRANCHES, "FEAT/LOGIN") == ["feat/Login-Flow"]

    def test_several_keep_order(self):
        assert branches.match(self.BRANCHES, "feat/log") == ["feat/Login-Flow", "feat/logout"]

    def test_no_match(self):
        assert branches.match(self.BRANCHES, "nope") == []

    def test_prefix_only(self):
        assert branches.match(self.BRANCHES, "login") == []

    def test_empty_prefix_matches_all(self):
        assert branches.match(self.BRANCHES, "") == self.BRANCHES


class TestContainerName:
    @pytest.mark.parametrize(
        ("branch", "expected"),
        [
            ("feat/Login-Flow", "login-flow"),
            ("main", "main"),
            ("user/feat/deep-name", "deep-name"),
            ("feat/Foo Bar!!", "foo-bar"),
            ("fix/_under_score.", "under_score"),
            ("KB-42_thing", "kb-42_thing"),
        ],
    )
    def test_derives(self, branch, expected):
        assert branches.container_name(branch) == expected

    @pytest.mark.parametrize("branch", ["feat/!!!", "feat/", "..."])
    def test_rejects_unusable(self, branch):
        with pytest.raises(BranchError):
            branches.container_name(branch)


class FakeGit:
    """Records `git ls-remote` invocations and returns canned output."""

    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


@pytest.fixture
def fake_git(monkeypatch):
    def install(**kwargs):
        fake = FakeGit(**kwargs)
        monkeypatch.setattr(branches.subprocess, "run", fake)
        return fake
    return install


class TestRemote:
    HEADS = (
        "aaa\trefs/heads/main\n"
        "bbb\trefs/heads/feat/login\n"
        "ccc\trefs/heads/fix/bug\n"
    )

    def test_remote_branches_sorted(self, fake_git):
        fake_git(stdout=self.HEADS)
        assert branches.remote_branches("owner/repo", TOKEN) == ["feat/login", "fix/bug", "main"]

    def test_remote_branches_ignores_other_refs(self, fake_git):
        fake_git(stdout=self.HEADS + "ddd\trefs/tags/v1\neee\trefs/pull/1/head\n")
        assert branches.remote_branches("owner/repo", TOKEN) == ["feat/login", "fix/bug", "main"]

    def test_remote_branches_empty_repo(self, fake_git):
        fake_git(stdout="")
        assert branches.remote_branches("owner/repo", TOKEN) == []

    def test_url_before_patterns(self, fake_git):
        git = fake_git(stdout="ref: refs/heads/main\tHEAD\naaa\tHEAD\n")
        branches.default_branch("owner/repo", TOKEN)
        argv = git.calls[0][0]
        assert argv == ["git", "ls-remote", "--symref", "https://github.com/owner/repo.git", "HEAD"]

    def test_default_branch(self, fake_git):
        fake_git(stdout="ref: refs/heads/trunk\tHEAD\naaa\tHEAD\n")
        assert branches.default_branch("owner/repo", TOKEN) == "trunk"

    def test_default_branch_missing(self, fake_git):
        fake_git(stdout="aaa\tHEAD\n")
        with pytest.raises(BranchError, match="default branch"):
            branches.default_branch("owner/repo", TOKEN)

    def test_failure_raises(self, fake_git):
        fake_git(returncode=128, stderr="fatal: repository not found")
        with pytest.raises(BranchError, match="repository not found"):
            branches.remote_branches("owner/repo", TOKEN)


class TestTokenSafety:
    def test_token_not_in_argv(self, fake_git):
        git = fake_git(stdout="")
        branches.remote_branches("owner/repo", TOKEN)
        argv, _ = git.calls[0]
        assert not any(TOKEN in arg for arg in argv)

    def test_token_not_in_error(self, fake_git):
        fake_git(returncode=128, stderr="fatal: Authentication failed")
        with pytest.raises(BranchError) as exc:
            branches.remote_branches("owner/repo", TOKEN)
        assert TOKEN not in str(exc.value)

    def test_auth_header(self, fake_git):
        git = fake_git(stdout="")
        branches.remote_branches("owner/repo", TOKEN)
        env = git.calls[0][1]["env"]
        assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraHeader"
        scheme, encoded = env["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: ").split()
        assert scheme == "Basic"
        assert base64.b64decode(encoded).decode() == f"x-access-token:{TOKEN}"

    def test_never_prompts(self, fake_git):
        git = fake_git(stdout="")
        branches.remote_branches("owner/repo", TOKEN)
        assert git.calls[0][1]["env"]["GIT_TERMINAL_PROMPT"] == "0"
