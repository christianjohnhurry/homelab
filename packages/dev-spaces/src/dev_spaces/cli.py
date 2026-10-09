"""Command-line interface and entry point."""

from importlib.resources import files
from typing import NoReturn

import typer

from dev_spaces import __version__, config, docker

IMAGE_DIR = files("dev_spaces") / "image"

app = typer.Typer(
    help="Sandboxed Docker containers per ticket.",
    no_args_is_help=True,
)


def _fail(message: str) -> NoReturn:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _load_config() -> config.Config:
    try:
        return config.load()
    except config.ConfigError as e:
        _fail(str(e))


def image_ref(cfg: config.Config) -> str:
    """The base image is tagged with the dev-spaces version."""
    return f"{cfg.image_name}:{__version__}"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dev-spaces {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Sandboxed Docker containers per ticket."""


@app.command()
def init() -> None:
    """Create ~/.config/dev-spaces with starter config, secrets and dotfiles."""
    for path, created in config.init():
        label = "created" if created else "exists "
        typer.echo(f"{label}  {path}")
    if warning := config.check_secrets_permissions():
        typer.secho(f"warning: {warning}", fg=typer.colors.YELLOW, err=True)
    typer.echo(f"\nNext: add your tokens to {config.secrets_path()}")


@app.command()
def build() -> None:
    """Build the base image, tagged with the dev-spaces version."""
    cfg = _load_config()
    ref = image_ref(cfg)
    try:
        docker.ping()
    except docker.DockerError as e:
        _fail(str(e))
    typer.echo(f"Building {ref}")
    code = docker.stream(
        "build",
        "--tag", ref,
        "--build-arg", f"DEV_SPACES_VERSION={__version__}",
        str(IMAGE_DIR),
    )
    if code != 0:
        _fail("image build failed")
    typer.secho(f"Built {ref}", fg=typer.colors.GREEN)


def main() -> None:
    """Entry point for the `dev-spaces` script."""
    app()
