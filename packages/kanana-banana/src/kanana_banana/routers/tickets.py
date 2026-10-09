"""REST API endpoints for ticket CRUD operations."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from kanana_banana.database import get_session
from kanana_banana.models import (
    Ticket,
    TicketCreate,
    TicketUpdate,
    TicketRead,
    TicketType,
    TicketStatus,
)
from kanana_banana import config, crud, export, github


def get_github_factory():
    """
    FastAPI dependency: a factory for the GitHub client, using GH_TOKEN from
    kanana-banana's secrets.env. Tests override it with a fake transport.
    """
    def factory() -> github.GitHub:
        token = config.read_secret("GH_TOKEN")
        if not token:
            raise github.MissingTokenError(
                f"GH_TOKEN is not set in {config.secrets_path()}. Add a fine-grained token "
                "with Contents: read/write on the board's repo (file mode 600)."
            )
        return github.GitHub(token)
    return factory


router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketRead])
def list_tickets(
    ticket_type: Optional[TicketType] = None,
    status: Optional[TicketStatus] = None,
    parent_id: Optional[int] = None,
    session: Session = Depends(get_session),
) -> list[Ticket]:
    """
    List all tickets with optional filters.

    Query parameters:
    - ticket_type: Filter by project/task/subtask
    - status: Filter by to-do/in-progress/on-hold/done
    - parent_id: Filter by parent ticket id
    """
    return crud.list_tickets(
        session,
        ticket_type=ticket_type,
        status=status,
        parent_id=parent_id,
    )


@router.get("/by-key/{key}", response_model=TicketRead)
def get_ticket_by_key(
    key: str,
    session: Session = Depends(get_session),
) -> Ticket:
    """Get a single ticket by key, e.g. HML-42 (case-insensitive)."""
    ticket = crud.get_ticket_by_key(session, key)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {key.upper()} not found",
        )
    return ticket


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
) -> Ticket:
    """Get a single ticket by id."""
    ticket = crud.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found",
        )
    return ticket


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket_create: TicketCreate,
    session: Session = Depends(get_session),
) -> Ticket:
    """
    Create a new ticket.

    Hierarchy rules are enforced:
    - Projects cannot have a parent, and need a board_id
    - Tasks have a project as parent, or no parent and a board_id
    - Subtasks must have a task as parent
    """
    try:
        return crud.create_ticket(session, ticket_create)
    except crud.HierarchyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    ticket_update: TicketUpdate,
    session: Session = Depends(get_session),
) -> Ticket:
    """
    Update a ticket with the provided fields.

    Only include the fields you want to update in the request body.
    """
    try:
        ticket = crud.update_ticket(session, ticket_id, ticket_update)
    except crud.HierarchyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found",
        )
    return ticket


@router.patch("/{ticket_id}/status", response_model=TicketRead)
def update_ticket_status(
    ticket_id: int,
    new_status: TicketStatus,
    session: Session = Depends(get_session),
) -> Ticket:
    """Move a ticket to a new status column."""
    ticket = crud.update_ticket_status(session, ticket_id, new_status)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found",
        )
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
) -> None:
    """
    Delete a ticket and all its children.

    Deletion cascades to child tickets.
    """
    deleted = crud.delete_ticket(session, ticket_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found",
        )


@router.get("/{ticket_id}/export")
def export_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
):
    """
    Export a ticket as markdown.

    Returns the ticket formatted for Claude Code consumption.
    """
    from fastapi.responses import PlainTextResponse

    markdown = export.export_ticket_markdown(session, ticket_id)
    if markdown is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found",
        )

    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.post("/{ticket_id}/branch", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket_branch(
    ticket_id: int,
    session: Session = Depends(get_session),
    github_factory=Depends(get_github_factory),
) -> Ticket:
    """
    Create the ticket's branch on GitHub (e.g. hml-42-add-login-flow) and record it.

    Tasks branch from the repo's default branch; subtasks from their task's branch.
    """
    try:
        ticket = crud.create_ticket_branch(session, ticket_id, github_factory)
    except crud.TicketBranchError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (crud.AlreadyBranchedError, github.BranchExistsError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except github.MissingTokenError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except github.GitHubError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found",
        )
    return ticket
