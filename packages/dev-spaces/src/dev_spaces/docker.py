"""Thin wrappers over the docker CLI."""

import shutil
import subprocess


class DockerError(Exception):
    pass


def _docker() -> str:
    path = shutil.which("docker")
    if path is None:
        raise DockerError(
            "docker not found on PATH. Is Docker Desktop installed? "
            "Open a new terminal so ~/.docker/bin is on your PATH."
        )
    return path


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a docker command and capture its output."""
    result = subprocess.run([_docker(), *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise DockerError(result.stderr.strip() or f"docker {args[0]} failed")
    return result


def stream(*args: str) -> int:
    """Run a docker command with output going straight to the terminal."""
    return subprocess.run([_docker(), *args]).returncode


def ping() -> None:
    """Fail early with a clear message if the Docker engine isn't running."""
    if run("info", "--format", "{{.ServerVersion}}", check=False).returncode != 0:
        raise DockerError("Docker engine isn't running. Start Docker Desktop.")
