"""Minimal GitHub REST client for creating branches."""

import re

import httpx2

API = "https://api.github.com"

_REPO_PATTERNS = [
    re.compile(r"^https?://github\.com/(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?/?$"),
    re.compile(r"^git@github\.com:(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?$"),
]


class GitHubError(Exception):
    pass


class BranchExistsError(GitHubError):
    pass


class MissingTokenError(GitHubError):
    """GH_TOKEN isn't configured: a local setup problem, not a GitHub failure."""


def parse_repo(url: str) -> str | None:
    """`owner/repo` from a GitHub https or SSH URL, or None if it isn't one."""
    for pattern in _REPO_PATTERNS:
        if m := pattern.match(url.strip()):
            return m["repo"]
    return None


class GitHub:
    def __init__(self, token: str, transport: httpx2.BaseTransport | None = None):
        self._client = httpx2.Client(
            base_url=API,
            transport=transport,
            timeout=15,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx2.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx2.HTTPError as e:
            raise GitHubError(f"Could not reach GitHub: {type(e).__name__}") from None
        return response

    @staticmethod
    def _message(response: httpx2.Response) -> str:
        try:
            return response.json().get("message", "")
        except ValueError:
            return ""

    def default_branch(self, repo: str) -> str:
        r = self._request("GET", f"/repos/{repo}")
        if r.status_code != 200:
            raise GitHubError(
                f"Could not read {repo} ({r.status_code} {self._message(r)}). "
                "Check the board's repo URL and that GH_TOKEN can access it."
            )
        return r.json()["default_branch"]

    def branch_sha(self, repo: str, branch: str) -> str:
        r = self._request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        if r.status_code != 200:
            raise GitHubError(f"Branch {branch} not found on {repo} ({r.status_code}).")
        return r.json()["object"]["sha"]

    def create_branch(self, repo: str, name: str, sha: str) -> None:
        r = self._request("POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{name}", "sha": sha})
        if r.status_code == 422:
            raise BranchExistsError(f"Branch {name} already exists on {repo}.")
        if r.status_code != 201:
            raise GitHubError(
                f"Could not create {name} on {repo} ({r.status_code} {self._message(r)}). "
                "GH_TOKEN needs Contents: read/write."
            )
