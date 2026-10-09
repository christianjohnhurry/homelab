"""Command-line interface and entry point."""

import typer

from dev_spaces import __version__

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


def main() -> None:
    """Entry point for the `dev-spaces` script."""
    app()
