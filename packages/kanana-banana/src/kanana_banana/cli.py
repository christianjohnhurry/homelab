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


# --- tickets ---------------------------------------------------------------------

STATUSES = ["to-do", "in-progress", "on-hold", "done"]
TYPES = ["project", "task", "subtask"]


def get_ticket(client: Api, key: str) -> dict:
    return client.get(f"/api/v1/tickets/by-key/{key}")


def _descendants(client: Api, ticket: dict) -> list[dict]:
    children = client.get("/api/v1/tickets", params={"parent_id": ticket["id"]})
    return children + [d for c in children for d in _descendants(client, c)]


def _line(ticket: dict) -> str:
    return f"{ticket['key']} [{ticket['ticket_type'].upper()}] {ticket['name']}"


@app.command()
def add(
    name: str = typer.Argument(..., help="Ticket name."),
    parent: Optional[str] = typer.Option(None, "--parent", help="Parent key: a project (makes a task) or a task (makes a subtask)."),
    project: bool = typer.Option(False, "--project", help="Create a project."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    board: Optional[str] = typer.Option(None, "--board", help="Board key. Default: the board for this git repo."),
) -> None:
    """
    Add a ticket.

    The type follows from the parent: none makes a task (or a project with
    --project), a project parent makes a task, a task parent a subtask.
    """
    client = api()
    body = {"name": name, "description": description}
    if project and parent:
        _fail("a project can't have a parent")
    if parent:
        parent_ticket = get_ticket(client, parent)
        child_type = {"project": "task", "task": "subtask"}.get(parent_ticket["ticket_type"])
        if child_type is None:
            _fail(f"{parent_ticket['key']} is a subtask; subtasks can't have children")
        body |= {"ticket_type": child_type, "parent_id": parent_ticket["id"]}
    else:
        body |= {
            "ticket_type": "project" if project else "task",
            "board_id": resolve_board(client, board)["id"],
        }
    ticket = client.post("/api/v1/tickets", json=body)
    typer.echo(f"Created {_line(ticket)}")


@app.command("list")
def list_(
    status: Optional[str] = typer.Option(None, "--status", "-s", help=f"One of: {', '.join(STATUSES)}."),
    ticket_type: Optional[str] = typer.Option(None, "--type", "-t", help=f"One of: {', '.join(TYPES)}."),
    tree: bool = typer.Option(False, "--tree", help="Show projects > tasks > subtasks."),
    board: Optional[str] = typer.Option(None, "--board", help="Board key. Default: the board for this git repo."),
    as_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """List a board's tickets."""
    if status and status not in STATUSES:
        _fail(f"status must be one of: {', '.join(STATUSES)}")
    if ticket_type and ticket_type not in TYPES:
        _fail(f"type must be one of: {', '.join(TYPES)}")
    if tree and (status or ticket_type):
        _fail("--tree shows the whole board; it can't be combined with --status or --type")
    client = api()
    board_data = resolve_board(client, board)
    params = {"board_id": board_data["id"]}
    if status:
        params["status"] = status
    if ticket_type:
        params["ticket_type"] = ticket_type
    tickets = client.get("/api/v1/tickets", params=params)

    if as_json:
        _print_json(tickets)
    elif not tickets:
        typer.echo(f"No tickets on {board_data['key']}.")
    elif tree:
        _print_tree(tickets)
    else:
        _table([("KEY", "TYPE", "STATUS", "NAME")] + [
            (t["key"], t["ticket_type"], t["status"], t["name"]) for t in tickets
        ])


def _print_tree(tickets: list[dict]) -> None:
    children: dict[int | None, list[dict]] = {}
    for t in tickets:
        children.setdefault(t["parent_id"], []).append(t)

    def show(ticket: dict, depth: int) -> None:
        typer.echo(f"{'  ' * depth}{ticket['key']}  {ticket['name']}  ({ticket['status']})")
        for child in children.get(ticket["id"], []):
            show(child, depth + 1)

    roots = children.get(None, [])
    # Projects first, then tasks without a project
    for ticket in sorted(roots, key=lambda t: t["ticket_type"] != "project"):
        show(ticket, 0)


@app.command()
def show(
    key: str = typer.Argument(..., help="Ticket key, e.g. HML-42."),
    as_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """Show a ticket."""
    client = api()
    ticket = get_ticket(client, key)
    children = client.get("/api/v1/tickets", params={"parent_id": ticket["id"]})
    parent = client.get(f"/api/v1/tickets/{ticket['parent_id']}") if ticket["parent_id"] else None
    if as_json:
        _print_json(ticket | {
            "parent_key": parent["key"] if parent else None,
            "children": [{"key": c["key"], "name": c["name"], "status": c["status"]} for c in children],
        })
        return
    typer.echo(_line(ticket))
    typer.echo(f"  Status:  {ticket['status']}")
    if parent:
        typer.echo(f"  Parent:  {_line(parent)}")
    typer.echo(f"  Branch:  {ticket['branch'] or '-'}")
    if ticket["description"]:
        typer.echo("")
        typer.echo(ticket["description"])
    if children:
        typer.echo("")
        for child in children:
            typer.echo(f"  - {_line(child)}  ({child['status']})")


@app.command()
def move(
    key: str = typer.Argument(..., help="Ticket key, e.g. HML-42."),
    status: str = typer.Argument(..., help=f"One of: {', '.join(STATUSES)}."),
) -> None:
    """Move a ticket to another status."""
    if status not in STATUSES:
        _fail(f"status must be one of: {', '.join(STATUSES)}")
    client = api()
    ticket = get_ticket(client, key)
    client.patch(f"/api/v1/tickets/{ticket['id']}/status", params={"new_status": status})
    typer.echo(f"{ticket['key']}: {ticket['status']} → {status}")


@app.command()
def edit(
    key: str = typer.Argument(..., help="Ticket key, e.g. HML-42."),
    name: Optional[str] = typer.Option(None, "--name", help="New name. The branch name doesn't change."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
) -> None:
    """Edit a ticket's name or description."""
    changes = {k: v for k, v in {"name": name, "description": description}.items() if v is not None}
    if not changes:
        _fail("nothing to change: pass --name and/or --description")
    client = api()
    ticket = get_ticket(client, key)
    updated = client.patch(f"/api/v1/tickets/{ticket['id']}", json=changes)
    typer.echo(f"Updated {_line(updated)}")


@app.command()
def delete(
    key: str = typer.Argument(..., help="Ticket key, e.g. HML-42."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation."),
) -> None:
    """Delete a ticket and everything under it."""
    client = api()
    ticket = get_ticket(client, key)
    descendants = _descendants(client, ticket)
    if not yes:
        under = f" and the {len(descendants)} ticket(s) under it" if descendants else ""
        typer.confirm(f"Delete {_line(ticket)}{under}?", abort=True)
    client.delete(f"/api/v1/tickets/{ticket['id']}")
    typer.echo(f"Deleted {ticket['key']}" + (f" and {len(descendants)} more" if descendants else ""))


@app.command()
def export(key: str = typer.Argument(..., help="Ticket key, e.g. HML-42.")) -> None:
    """Print a ticket as markdown, for pasting into Claude Code."""
    client = api()
    ticket = get_ticket(client, key)
    typer.echo(client.get(f"/api/v1/tickets/{ticket['id']}/export").rstrip("\n"))


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
