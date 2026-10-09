"""Detect and install a cloned repo's dependencies inside a container."""

from dev_spaces import docker

CODE_DIR = "/home/dev/code"


def _exists(container: str, path: str) -> bool:
    return docker.run("exec", container, "test", "-f", f"{CODE_DIR}/{path}", check=False).returncode == 0


def _uses_pixi(container: str) -> bool:
    if _exists(container, "pixi.toml"):
        return True
    result = docker.run(
        "exec", container, "grep", "-q", r"^\[tool\.pixi", f"{CODE_DIR}/pyproject.toml",
        check=False,
    )
    return result.returncode == 0


def detect(container: str) -> list[str] | None:
    """The install command for the repo in the container, or None if unrecognised."""
    if _uses_pixi(container):
        return ["pixi", "install"]
    if _exists(container, "uv.lock"):
        return ["uv", "sync"]
    return None
