"""kb: command-line client for the Kanana Banana REST API."""

import json
import os
import subprocess
from typing import NoReturn, Optional

import httpx2
import typer

from kanana_banana import __version__
from kanana_banana.github import parse_repo

DEFAULT_URL = "http://127.0.0.1:8000"

app = typer.Typer(help="Kanana Banana from the command line.", no_args_is_help=True)
board_app = typer.Typer(help="Manage boards.", no_args_is_help=True)
app.add_typer(board_app, name="board")


def _fail(message: str) -> NoReturn:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def make_client() -> httpx2.Client:
    """The HTTP client for the server. Tests replace this with the app's TestClient."""
    return httpx2.Client(base_url=os.environ.get("KB_URL", DEFAULT_URL), timeout=30)


class Api:
    """REST calls with errors turned into clean CLI failures."""

    def __init__(self, client: httpx2.Client):
        self.client = client

    def request(self, method: str, path: str, **kwargs):
        try:
            r = self.client.request(method, path, **kwargs)
        except httpx2.TransportError:
            _fail(
                f"Kanana Banana isn't running at {self.client.base_url}. "
                "Start it with `pixi run kanana-banana`."
            )
        if r.status_code >= 400:
            try:
                detail = r.json()["detail"]
            except (ValueError, KeyError, TypeError):
                detail = r.text or r.reason_phrase
            if isinstance(detail, list):  # FastAPI validation errors
                detail = "; ".join(d.get("msg", str(d)) for d in detail)
            _fail(str(detail))
        if r.status_code == 204:
            return None
        ctype = r.headers.get("content-type", "")
        return r.json() if ctype.startswith("application/json") else r.text

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)


def api() -> Api:
    return Api(make_client())


# --- boards ----------------------------------------------------------------------


def git_origin_repo() -> Optional[str]:
    """`owner/repo` of the current directory's git origin, if it's on GitHub."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"], capture_output=True, text=True
    )
    return parse_repo(result.stdout.strip()) if result.returncode == 0 else None


def resolve_board(client: Api, key: Optional[str]) -> dict:
    """
    The board to use: --board KEY if given, otherwise the board whose repo_url
    matches the current git repo's origin. Fails listing the boards if neither works.
    """
    if key:
        boards = client.get("/api/v1/boards", params={"key": key})
        if not boards:
            _fail(f"No board with key {key.upper()}.{_board_list(client)}")
        return boards[0]

    repo = git_origin_repo()
    if repo:
        for board in client.get("/api/v1/boards"):
            if parse_repo(board.get("repo_url") or "") == repo:
                return board
        _fail(f"No board for {repo}. Pass --board KEY.{_board_list(client)}")
    _fail(f"Not in a GitHub repo with a board. Pass --board KEY.{_board_list(client)}")


def _board_list(client: Api) -> str:
    boards = client.get("/api/v1/boards")
    if not boards:
        return " No boards yet: create one with `kb board add`."
    return " Boards: " + ", ".join(f"{b['key']} ({b['name']})" for b in boards)


def _table(rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    for row in rows:
        typer.echo(("  ".join(c.ljust(w) for c, w in zip(row, widths)) + "  " + row[-1]).rstrip())


def _print_json(data) -> None:
    typer.echo(json.dumps(data, indent=2))


@board_app.command("add")
def board_add(
    key: str = typer.Argument(..., help="Letters only, e.g. HML. Can't be changed later."),
    name: str = typer.Argument(..., help="Board name."),
    repo: Optional[str] = typer.Option(None, "--repo", help="GitHub repo URL, needed for branches."),
    description: str = typer.Option("", "--description", help="What the board is for."),
) -> None:
    """Create a board."""
    board = api().post(
        "/api/v1/boards",
        json={"key": key, "name": name, "repo_url": repo, "description": description},
    )
    typer.echo(f"Created board {board['key']}: {board['name']}")


@board_app.command("list")
def board_list(as_json: bool = typer.Option(False, "--json", help="Output JSON.")) -> None:
    """List boards."""
    boards = api().get("/api/v1/boards")
    if as_json:
        _print_json(boards)
        return
    if not boards:
        typer.echo("No boards yet. Create one with `kb board add KEY NAME`.")
        return
    _table([("KEY", "NAME", "REPO")] + [(b["key"], b["name"], b["repo_url"] or "-") for b in boards])


# --- entry point -------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    """Kanana Banana from the command line. Needs the server: `pixi run kanana-banana`."""


def main() -> None:
    app()
