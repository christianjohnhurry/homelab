"""Remote branch lookup and prefix matching."""

import base64
import os
import re
import subprocess


class BranchError(Exception):
    pass


_REPO_PATTERNS = [
    re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?$"),
    re.compile(r"^https://github\.com/(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?/?$"),
    re.compile(r"^git@github\.com:(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?$"),
]


def parse_repo(value: str) -> str:
    """Normalise `owner/repo`, an https URL or an SSH URL to `owner/repo`."""
    for pattern in _REPO_PATTERNS:
        if m := pattern.match(value.strip()):
            return m["repo"]
    raise BranchError(f"Not a GitHub repo: {value!r}. Use owner/repo.")


def clone_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _git_env(token: str) -> dict[str, str]:
    """
    Authenticate git over HTTPS with the token.

    The token goes in an environment-provided config header rather than the
    URL or argv, so it never shows up in `ps` or error messages.
    """
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
    }


def _ls_remote(repo: str, token: str, options: list[str], patterns: list[str]) -> str:
    result = subprocess.run(
        ["git", "ls-remote", *options, clone_url(repo), *patterns],
        capture_output=True,
        text=True,
        env=_git_env(token),
    )
    if result.returncode != 0:
        raise BranchError(
            f"Could not read {repo} from GitHub. Check the repo name and that "
            f"GH_TOKEN has access to it.\n{result.stderr.strip()}"
        )
    return result.stdout


def remote_branches(repo: str, token: str) -> list[str]:
    """All branch names on the remote."""
    out = _ls_remote(repo, token, ["--heads"], [])
    prefix = "refs/heads/"
    return sorted(
        ref[len(prefix):]
        for line in out.splitlines()
        if (ref := line.split("\t")[1]).startswith(prefix)
    )


def default_branch(repo: str, token: str) -> str:
    """The branch the remote's HEAD points at, e.g. main."""
    out = _ls_remote(repo, token, ["--symref"], ["HEAD"])
    for line in out.splitlines():
        if line.startswith("ref: refs/heads/"):
            return line.split("\t")[0].removeprefix("ref: refs/heads/")
    raise BranchError(f"Could not determine the default branch of {repo}.")


def match(branches: list[str], prefix: str) -> list[str]:
    """Branches starting with prefix, case-insensitively."""
    needle = prefix.lower()
    return [b for b in branches if b.lower().startswith(needle)]


def container_name(branch: str) -> str:
    """
    Docker-safe container name from a branch: `feat/Login-Flow` -> `login-flow`.

    Uses the last path segment, since prefixes like feat/ and fix/ are noise.
    """
    name = branch.rsplit("/", 1)[-1].lower()
    name = re.sub(r"[^a-z0-9_.-]+", "-", name).strip("-._")
    if not name:
        raise BranchError(f"Cannot derive a container name from {branch!r}.")
    return name
