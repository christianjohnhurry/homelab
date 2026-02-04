"""HTML routes for the kanban board UI."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from kanana_banana.templating import templates
from kanana_banana.database import get_session
from kanana_banana.models import Ticket, TicketType, TicketStatus
from kanana_banana import crud


router = APIRouter(tags=["board"])


def get_context(request: Request) -> dict:
    """Base context for all templates."""
    return {
        "request": request,
        "statuses": list(TicketStatus),
        "ticket_types": list(TicketType),
    }


@router.get("/", response_class=HTMLResponse)
def board(
    request: Request,
    session: Session = Depends(get_session),
):
    """Render the full kanban board page."""
    # Get all tickets grouped by status
    all_tickets = crud.list_tickets(session)
    tickets_by_status = {s: [] for s in TicketStatus}
    for ticket in all_tickets:
        tickets_by_status[ticket.status].append(ticket)

    context = get_context(request)
    context["tickets_by_status"] = tickets_by_status

    return templates.TemplateResponse("board.html", context)


@router.get("/board/column/{status}", response_class=HTMLResponse)
def get_column(
    request: Request,
    status: TicketStatus,
    session: Session = Depends(get_session),
):
    """
    Render a single column (HTMX partial).

    This is used by HTMX to refresh a column after a ticket moves.
    """
    tickets = crud.list_tickets(session, status=status)

    context = get_context(request)
    context["status"] = status
    context["tickets"] = tickets

    return templates.TemplateResponse("partials/column.html", context)


@router.get("/tickets/new", response_class=HTMLResponse)
def new_ticket_form(
    request: Request,
    session: Session = Depends(get_session),
):
    """Render the create ticket form (HTMX partial)."""
    # Get possible parents (projects and tasks)
    projects = crud.list_tickets(session, ticket_type=TicketType.PROJECT)
    tasks = crud.list_tickets(session, ticket_type=TicketType.TASK)

    context = get_context(request)
    context["ticket"] = None
    context["possible_parents"] = projects + tasks

    return templates.TemplateResponse("partials/ticket_form.html", context)


@router.post("/tickets", response_class=HTMLResponse)
def create_ticket(
    request: Request,
    name: str = Form(...),
    ticket_type: TicketType = Form(...),
    status: TicketStatus = Form(...),
    parent_id: Optional[str] = Form(None),
    repo_url: Optional[str] = Form(None),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    """Handle ticket creation from form submission."""
    # Convert empty string to None for parent_id
    parent_id_int = int(parent_id) if parent_id else None

    ticket_create = crud.TicketCreate(
        name=name,
        ticket_type=ticket_type,
        status=status,
        parent_id=parent_id_int,
        repo_url=repo_url if repo_url else None,
        description=description,
    )

    try:
        crud.create_ticket(session, ticket_create)
    except crud.HierarchyError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Return empty response - the form uses JS to reload the page on success
    return HTMLResponse("")


@router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def get_ticket_detail(
    request: Request,
    ticket_id: int,
    session: Session = Depends(get_session),
):
    """Render ticket detail view (HTMX partial)."""
    ticket = crud.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    context = get_context(request)
    context["ticket"] = ticket

    return templates.TemplateResponse("partials/ticket_detail.html", context)


@router.get("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def edit_ticket_form(
    request: Request,
    ticket_id: int,
    session: Session = Depends(get_session),
):
    """Render the edit ticket form (HTMX partial)."""
    ticket = crud.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Get possible parents based on ticket type
    if ticket.ticket_type == TicketType.TASK:
        possible_parents = crud.list_tickets(session, ticket_type=TicketType.PROJECT)
    elif ticket.ticket_type == TicketType.SUBTASK:
        possible_parents = crud.list_tickets(session, ticket_type=TicketType.TASK)
    else:
        possible_parents = []

    context = get_context(request)
    context["ticket"] = ticket
    context["possible_parents"] = possible_parents

    return templates.TemplateResponse("partials/ticket_form.html", context)


@router.post("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def update_ticket(
    request: Request,
    ticket_id: int,
    name: str = Form(...),
    status: TicketStatus = Form(...),
    parent_id: Optional[str] = Form(None),
    repo_url: Optional[str] = Form(None),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    """Handle ticket update from form submission."""
    parent_id_int = int(parent_id) if parent_id else None

    ticket_update = crud.TicketUpdate(
        name=name,
        status=status,
        parent_id=parent_id_int,
        repo_url=repo_url if repo_url else None,
        description=description,
    )

    try:
        ticket = crud.update_ticket(session, ticket_id, ticket_update)
    except crud.HierarchyError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if ticket is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    return HTMLResponse("")


@router.post("/tickets/{ticket_id}/move", response_class=HTMLResponse)
def move_ticket(
    request: Request,
    ticket_id: int,
    status: TicketStatus,
    session: Session = Depends(get_session),
):
    """
    Move a ticket to a new status column.

    Returns the updated target column HTML, plus an OOB swap for the source column.
    """
    ticket = crud.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    old_status = ticket.status
    crud.update_ticket_status(session, ticket_id, status)

    # Render the target column (this is the main response)
    target_tickets = crud.list_tickets(session, status=status)
    context = get_context(request)
    context["status"] = status
    context["tickets"] = target_tickets
    target_html = templates.TemplateResponse(
        "partials/column.html", context
    ).body.decode()

    # If the ticket actually moved (not just refreshed), also update the source column
    if old_status != status:
        source_tickets = crud.list_tickets(session, status=old_status)
        context["status"] = old_status
        context["tickets"] = source_tickets
        source_html = templates.TemplateResponse(
            "partials/column.html", context
        ).body.decode()

        # Use HTMX out-of-band swap to update the source column too
        # The hx-swap-oob="innerHTML" tells HTMX to find the element with this id
        # and replace its innerHTML
        oob_html = f'<div id="column-{old_status.value}" hx-swap-oob="innerHTML">{source_html}</div>'
        return HTMLResponse(target_html + oob_html)

    return HTMLResponse(target_html)


@router.post("/tickets/{ticket_id}/delete", response_class=HTMLResponse)
def delete_ticket(
    request: Request,
    ticket_id: int,
    session: Session = Depends(get_session),
):
    """Delete a ticket."""
    deleted = crud.delete_ticket(session, ticket_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Return empty - the button uses JS to reload the page
    return HTMLResponse("")
