"""Shared fixtures: an isolated config dir and a scripted fake of the docker module."""

import subprocess
from dataclasses import dataclass, field

import pytest

from dev_spaces import config, docker


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """A fresh config dir per test, with a fixed git identity."""
    path = tmp_path / "dev-spaces"
    monkeypatch.setenv("DEV_SPACES_CONFIG_DIR", str(path))
    identity = {"user.name": "Test User", "user.email": "test@example.com"}
    monkeypatch.setattr(config, "_git_global", lambda key: identity.get(key, ""))
    return path


@pytest.fixture
def initialised(config_dir):
    """A config dir after `init`, with both tokens filled in."""
    config.init()
    config.secrets_path().write_text("GH_TOKEN=gh-test-token\nCLAUDE_CODE_OAUTH_TOKEN=claude-test-token\n")
    return config_dir


def container_info(
    name: str,
    *,
    running: bool = True,
    labels: dict[str, str] | None = None,
    ports: dict[str, str] | None = None,
) -> dict:
    """A minimal `docker inspect` record for a container."""
    if labels is None:
        labels = {
            "dev-spaces": "1",
            "dev-spaces.repo": "owner/repo",
            "dev-spaces.branch": f"feat/{name}",
        }
    return {
        "Name": f"/{name}",
        "State": {"Running": running, "Status": "running" if running else "exited"},
        "Config": {"Labels": labels},
        "NetworkSettings": {
            "Ports": {
                f"{c}/tcp": [{"HostIp": "127.0.0.1", "HostPort": h}]
                for c, h in (ports or {}).items()
            }
            if running
            else {},
        },
    }


@dataclass
class FakeDocker:
    """
    Stands in for dev_spaces.docker.

    Responses are scripted by argument prefix: `respond("exec", "c", "git",
    "status", stdout="M x")` matches any call starting with those arguments.
    Later scripts take precedence. Unscripted calls succeed with empty output.
    Every call is recorded in `calls` as a tuple of arguments.
    """

    calls: list[tuple[str, ...]] = field(default_factory=list)
    responses: list[tuple[tuple[str, ...], int, str]] = field(default_factory=list)
    containers: dict[str, dict] = field(default_factory=dict)
    exec_interactive_args: tuple[str, ...] | None = None

    def respond(self, *prefix: str, returncode: int = 0, stdout: str = "") -> None:
        self.responses.insert(0, (prefix, returncode, stdout))

    def _result(self, args: tuple[str, ...]) -> tuple[int, str]:
        for prefix, returncode, stdout in self.responses:
            if args[: len(prefix)] == prefix:
                return returncode, stdout
        return 0, ""

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        returncode, stdout = self._result(args)
        if check and returncode != 0:
            raise docker.DockerError(f"docker {args[0]} failed")
        return subprocess.CompletedProcess(args, returncode, stdout, "")

    def stream(self, *args: str) -> int:
        self.calls.append(args)
        return self._result(args)[0]

    def inspect(self, *names: str) -> list[dict]:
        missing = [n for n in names if n not in self.containers]
        if missing:
            raise docker.DockerError(f"No such container: {missing[0]}")
        return [self.containers[n] for n in names]

    def find(self, label: str) -> list[str]:
        key, _, value = label.partition("=")
        return sorted(
            name for name, info in self.containers.items()
            if info["Config"]["Labels"].get(key) == value
        )

    def exec_interactive(self, *args: str) -> None:
        self.exec_interactive_args = args

    def ping(self) -> None:
        pass

    def called(self, *prefix: str) -> list[tuple[str, ...]]:
        """Recorded calls starting with prefix."""
        return [c for c in self.calls if c[: len(prefix)] == prefix]


@pytest.fixture
def fake_docker(monkeypatch):
    fake = FakeDocker()
    for name in ("run", "stream", "inspect", "find", "exec_interactive", "ping"):
        monkeypatch.setattr(docker, name, getattr(fake, name))
    return fake
