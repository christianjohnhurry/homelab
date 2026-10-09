"""Command-line interface and entry point."""

import typer

from dev_spaces import __version__, config

app = typer.Typer(
    help="Sandboxed Docker containers per ticket.",
    no_args_is_help=True,
)


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


def main() -> None:
    """Entry point for the `dev-spaces` script."""
    app()
