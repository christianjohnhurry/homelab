import json
import subprocess

import httpx2
import pytest
import typer

from kanana_banana import __version__, cli


def test_version(kb):
    result = kb("--version")
    assert result.output.strip() == f"kb {__version__}"


def test_server_down(monkeypatch):
    from typer.testing import CliRunner
    # Nothing listens on port 9: connection refused
    monkeypatch.setattr(cli, "make_client", lambda: httpx2.Client(base_url="http://127.0.0.1:9"))
    result = CliRunner().invoke(cli.app, ["board", "list"])
    assert result.exit_code == 1
    assert "isn't running at http://127.0.0.1:9" in result.output
    assert "pixi run kanana-banana" in result.output


def test_kb_url_env(monkeypatch):
    monkeypatch.setenv("KB_URL", "http://example.test:1234")
    assert str(cli.make_client().base_url) == "http://example.test:1234"


def test_default_url(monkeypatch):
    monkeypatch.delenv("KB_URL", raising=False)
    assert str(cli.make_client().base_url) == "http://127.0.0.1:8000"


class TestBoardCommands:
    def test_add_and_list(self, kb):
        r = kb("board", "add", "hml", "Homelab", "--repo", "https://github.com/o/homelab")
        assert r.exit_code == 0, r.output
        assert "Created board HML: Homelab" in r.output
        kb("board", "add", "oth", "Other")
        lines = kb("board", "list").output.splitlines()
        assert lines[0].split() == ["KEY", "NAME", "REPO"]
        assert lines[1].split() == ["HML", "Homelab", "https://github.com/o/homelab"]
        assert lines[2].split() == ["OTH", "Other", "-"]

    def test_list_empty(self, kb):
        assert "No boards yet" in kb("board", "list").output

    def test_list_json(self, kb):
        kb("board", "add", "hml", "Homelab")
        boards = json.loads(kb("board", "list", "--json").output)
        assert [b["key"] for b in boards] == ["HML"]

    @pytest.mark.parametrize(("key", "message"), [("hm1", "letters only"), ("hml", "already used")])
    def test_add_errors_are_clean(self, kb, key, message):
        kb("board", "add", "hml", "Homelab")
        r = kb("board", "add", key, "Dup")
        assert r.exit_code == 1
        assert message in r.output.lower()
        assert "Traceback" not in r.output


class TestResolveBoard:
    @pytest.fixture
    def boards(self, kb):
        kb("board", "add", "hml", "Homelab", "--repo", "https://github.com/o/homelab")
        kb("board", "add", "oth", "Other", "--repo", "git@github.com:o/other.git")

    @pytest.fixture
    def api(self, client):
        return cli.Api(client)

    def test_by_key(self, boards, api):
        assert cli.resolve_board(api, "oth")["key"] == "OTH"

    def test_unknown_key_lists_boards(self, boards, api, capsys):
        with pytest.raises(typer.Exit):
            cli.resolve_board(api, "nope")
        assert "No board with key NOPE" in capsys.readouterr().err

    @pytest.mark.parametrize("repo", ["o/homelab", "o/other"])
    def test_by_git_origin(self, boards, api, monkeypatch, repo):
        monkeypatch.setattr(cli, "git_origin_repo", lambda: repo)
        board = cli.resolve_board(api, None)
        assert board["key"] == {"o/homelab": "HML", "o/other": "OTH"}[repo]

    def test_key_beats_git_origin(self, boards, api, monkeypatch):
        monkeypatch.setattr(cli, "git_origin_repo", lambda: "o/homelab")
        assert cli.resolve_board(api, "oth")["key"] == "OTH"

    def test_repo_without_board(self, boards, api, monkeypatch, capsys):
        monkeypatch.setattr(cli, "git_origin_repo", lambda: "o/unknown")
        with pytest.raises(typer.Exit):
            cli.resolve_board(api, None)
        err = capsys.readouterr().err
        assert "No board for o/unknown" in err
        assert "HML (Homelab)" in err

    def test_not_in_repo(self, boards, api, capsys):
        with pytest.raises(typer.Exit):
            cli.resolve_board(api, None)
        assert "Pass --board KEY" in capsys.readouterr().err


class TestGitOrigin:
    def git(self, path, *args):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)

    @pytest.mark.parametrize(
        "url", ["https://github.com/o/homelab", "https://github.com/o/homelab.git", "git@github.com:o/homelab.git"]
    )
    def test_reads_origin(self, tmp_path, monkeypatch, url):
        self.git(tmp_path, "init", "-q")
        self.git(tmp_path, "remote", "add", "origin", url)
        monkeypatch.chdir(tmp_path)
        assert cli.git_origin_repo() == "o/homelab"

    def test_not_a_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cli.git_origin_repo() is None

    def test_no_origin(self, tmp_path, monkeypatch):
        self.git(tmp_path, "init", "-q")
        monkeypatch.chdir(tmp_path)
        assert cli.git_origin_repo() is None

    def test_non_github_origin(self, tmp_path, monkeypatch):
        self.git(tmp_path, "init", "-q")
        self.git(tmp_path, "remote", "add", "origin", "https://gitlab.com/o/x")
        monkeypatch.chdir(tmp_path)
        assert cli.git_origin_repo() is None
