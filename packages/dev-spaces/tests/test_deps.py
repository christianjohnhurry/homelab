import pytest

from dev_spaces import deps

CODE = deps.CODE_DIR


@pytest.fixture
def repo(fake_docker):
    """Script which files exist in the container's ~/code. Everything else is absent."""
    fake_docker.respond("exec", "c", "test", "-f", returncode=1)
    fake_docker.respond("exec", "c", "grep", returncode=1)

    def files(*names: str, pixi_in_pyproject: bool = False):
        for name in names:
            fake_docker.respond("exec", "c", "test", "-f", f"{CODE}/{name}")
        if pixi_in_pyproject:
            fake_docker.respond("exec", "c", "grep", "-q", r"^\[tool\.pixi", f"{CODE}/pyproject.toml")
    return files


def test_pixi_toml(repo):
    repo("pixi.toml")
    assert deps.detect("c") == ["pixi", "install"]


def test_pixi_in_pyproject(repo):
    repo("pyproject.toml", pixi_in_pyproject=True)
    assert deps.detect("c") == ["pixi", "install"]


def test_uv(repo):
    repo("pyproject.toml", "uv.lock")
    assert deps.detect("c") == ["uv", "sync"]


def test_pixi_wins_over_uv(repo):
    repo("pixi.toml", "uv.lock")
    assert deps.detect("c") == ["pixi", "install"]


def test_plain_pyproject_is_unrecognised(repo):
    repo("pyproject.toml")
    assert deps.detect("c") is None


def test_nothing(repo):
    repo()
    assert deps.detect("c") is None
