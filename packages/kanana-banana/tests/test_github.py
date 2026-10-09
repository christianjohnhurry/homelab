import httpx2
import pytest

from kanana_banana.github import BranchExistsError, GitHub, GitHubError, parse_repo

TOKEN = "github_pat_SECRET123"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/o/repo", "o/repo"),
        ("https://github.com/o/repo.git", "o/repo"),
        ("https://github.com/o/repo/", "o/repo"),
        ("git@github.com:o/repo.git", "o/repo"),
        ("https://gitlab.com/o/repo", None),
        ("https://github.com/o", None),
        ("", None),
    ],
)
def test_parse_repo(url, expected):
    assert parse_repo(url) == expected


def client(handler):
    requests = []

    def record(request):
        requests.append(request)
        return handler(request)

    return GitHub(TOKEN, transport=httpx2.MockTransport(record)), requests


def test_headers():
    gh, requests = client(lambda r: httpx2.Response(200, json={"default_branch": "main"}))
    gh.default_branch("o/repo")
    headers = requests[0].headers
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Accept"] == "application/vnd.github+json"
    assert str(requests[0].url) == "https://api.github.com/repos/o/repo"


def test_branch_sha():
    gh, requests = client(lambda r: httpx2.Response(200, json={"object": {"sha": "abc123"}}))
    assert gh.branch_sha("o/repo", "main") == "abc123"
    assert requests[0].url.path == "/repos/o/repo/git/ref/heads/main"


def test_create_branch_request():
    gh, requests = client(lambda r: httpx2.Response(201, json={}))
    gh.create_branch("o/repo", "hml-1-x", "abc123")
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/repos/o/repo/git/refs"
    assert requests[0].read() == b'{"ref":"refs/heads/hml-1-x","sha":"abc123"}'


def test_branch_exists():
    gh, _ = client(lambda r: httpx2.Response(422, json={"message": "Reference already exists"}))
    with pytest.raises(BranchExistsError):
        gh.create_branch("o/repo", "hml-1-x", "abc")


@pytest.mark.parametrize(
    ("call", "status"),
    [
        (lambda gh: gh.default_branch("o/repo"), 404),
        (lambda gh: gh.branch_sha("o/repo", "main"), 404),
        (lambda gh: gh.create_branch("o/repo", "b", "abc"), 403),
    ],
)
def test_errors_never_leak_token(call, status):
    gh, _ = client(lambda r: httpx2.Response(status, json={"message": "Bad credentials"}))
    with pytest.raises(GitHubError) as exc:
        call(gh)
    assert TOKEN not in str(exc.value)
    assert str(status) in str(exc.value)


def test_network_error():
    def fail(request):
        raise httpx2.ConnectError("boom", request=request)
    gh, _ = client(fail)
    with pytest.raises(GitHubError, match="Could not reach GitHub"):
        gh.default_branch("o/repo")
