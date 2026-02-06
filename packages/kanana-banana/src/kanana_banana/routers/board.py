"""
HTML routes for the kanban board UI.

This router handles the main board views and ticket operations.
All board views are now scoped to a specific board (repository).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from kanana_banana.templating import templates
from kanana_banana.database import get_session
from kanana_banana.models import Ticket, TicketType, TicketStatus
from kanana_banana import crud


router = APIRouter(tags=["board"])


def get_context(request: Request, session: Session) -> dict:
    """
    Base context for all templates.

    Now includes the list of boards for the sidebar navigation.
    """
    return {
        "request": request,
        "statuses": list(TicketStatus),
        "ticket_types": list(TicketType),
        "boards": crud.list_boards(session),  # For sidebar
    }


# =============================================================================
# Main Entry Points
# =============================================================================


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Landing page - redirect to first board or show empty state.

    If there are boards, redirects to the first one.
    If no boards exist, shows a prompt to create one.
    """
    boards = crud.list_boards(session)
    if boards:
        # Redirect to the first board
        return RedirectResponse(url=f"/boards/{boards[0].id}", status_code=302)

    # No boards - show empty state
    context = get_context(request, session)
    context["no_boards"] = True
    context["board"] = None
    context["current_board_id"] = None
    context["tickets_by_status"] = {s: [] for s in TicketStatus}
    return templates.TemplateResponse("board.html", context)


@router.get("/boards/{board_id}", response_class=HTMLResponse)
def board_view(
    request: Request,
    board_id: int,
    session: Session = Depends(get_session),
):
    """Render the kanban board for a specific board (repository)."""
    board = crud.get_board(session, board_id)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )

    # Get tickets for this board, grouped by status
    all_tickets = crud.list_tickets(session, board_id=board_id)
    tickets_by_status = {s: [] for s in TicketStatus}
    for ticket in all_tickets:
        tickets_by_status[ticket.status].append(ticket)

    context = get_context(request, session)
    context["board"] = board
    context["current_board_id"] = board_id
    context["tickets_by_status"] = tickets_by_status
    context["no_boards"] = False

    return templates.TemplateResponse("board.html", context)


@router.get("/boards/{board_id}/tree", response_class=HTMLResponse)
def board_tree_view(
    request: Request,
    board_id: int,
    session: Session = Depends(get_session),
):
    """Render the banana tree visualization for a specific board."""
    board = crud.get_board(session, board_id)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )

    # Get projects with their full hierarchy (tasks and subtasks)
    projects = crud.get_board_tree(session, board_id)

    context = get_context(request, session)
    context["board"] = board
    context["current_board_id"] = board_id
    context["projects"] = projects
    context["no_boards"] = False

    return templates.TemplateResponse("tree_view.html", context)


# =============================================================================
# Column Routes (HTMX partials)
# =============================================================================


@router.get("/boards/{board_id}/column/{status}", response_class=HTMLResponse)
def get_column(
    request: Request,
    board_id: int,
    status: TicketStatus,
    session: Session = Depends(get_session),
):
    """
    Render a single column for a board (HTMX partial).

    Used by HTMX to refresh a column after a ticket moves.
    """
    tickets = crud.list_tickets(session, status=status, board_id=board_id)

    context = get_context(request, session)
    context["status"] = status
    context["tickets"] = tickets
    context["current_board_id"] = board_id

    return templates.TemplateResponse("partials/column.html", context)


# =============================================================================
# Ticket Form Routes
# =============================================================================


@router.get("/boards/{board_id}/tickets/new", response_class=HTMLResponse)
def new_ticket_form(
    request: Request,
    board_id: int,
    session: Session = Depends(get_session),
):
    """Render the create ticket form for a specific board (HTMX partial)."""
    board = crud.get_board(session, board_id)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )

    # Get possible parents - only from this board
    projects = crud.list_tickets(session, ticket_type=TicketType.PROJECT, board_id=board_id)
    tasks = crud.list_tickets(session, ticket_type=TicketType.TASK, board_id=board_id)

    context = get_context(request, session)
    context["ticket"] = None
    context["possible_parents"] = projects + tasks
    context["current_board_id"] = board_id
    context["board"] = board

    return templates.TemplateResponse("partials/ticket_form.html", context)


@router.post("/boards/{board_id}/tickets", response_class=HTMLResponse)
def create_ticket(
    request: Request,
    board_id: int,
    name: str = Form(...),
    ticket_type: TicketType = Form(...),
    status: TicketStatus = Form(...),
    parent_id: Optional[str] = Form(None),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    """Handle ticket creation for a specific board."""
    parent_id_int = int(parent_id) if parent_id else None

    ticket_create = crud.TicketCreate(
        name=name,
        ticket_type=ticket_type,
        status=status,
        parent_id=parent_id_int,
        description=description,
        board_id=board_id,  # Ticket belongs to this board
    )

    try:
        crud.create_ticket(session, ticket_create)
    except crud.HierarchyError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return HTMLResponse("")


# =============================================================================
# Ticket Detail/Edit Routes
# =============================================================================


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

    context = get_context(request, session)
    context["ticket"] = ticket
    context["current_board_id"] = ticket.board_id

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

    # Get possible parents based on ticket type - only from same board
    if ticket.ticket_type == TicketType.TASK:
        possible_parents = crud.list_tickets(
            session, ticket_type=TicketType.PROJECT, board_id=ticket.board_id
        )
    elif ticket.ticket_type == TicketType.SUBTASK:
        possible_parents = crud.list_tickets(
            session, ticket_type=TicketType.TASK, board_id=ticket.board_id
        )
    else:
        possible_parents = []

    context = get_context(request, session)
    context["ticket"] = ticket
    context["possible_parents"] = possible_parents
    context["current_board_id"] = ticket.board_id

    return templates.TemplateResponse("partials/ticket_form.html", context)


@router.post("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def update_ticket(
    request: Request,
    ticket_id: int,
    name: str = Form(...),
    status: TicketStatus = Form(...),
    parent_id: Optional[str] = Form(None),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    """Handle ticket update from form submission."""
    parent_id_int = int(parent_id) if parent_id else None

    ticket_update = crud.TicketUpdate(
        name=name,
        status=status,
        parent_id=parent_id_int,
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


# =============================================================================
# Ticket Move/Delete Routes
# =============================================================================


@router.post("/boards/{board_id}/tickets/{ticket_id}/move", response_class=HTMLResponse)
def move_ticket(
    request: Request,
    board_id: int,
    ticket_id: int,
    status: TicketStatus,
    session: Session = Depends(get_session),
):
    """
    Move a ticket to a new status column.

    Returns the updated target column HTML, plus an OOB swap for the source column.
    This allows both columns to update with a single request.
    """
    ticket = crud.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    old_status = ticket.status
    crud.update_ticket_status(session, ticket_id, status)

    # Render the target column
    context = get_context(request, session)
    context["current_board_id"] = board_id

    target_tickets = crud.list_tickets(session, status=status, board_id=board_id)
    context["status"] = status
    context["tickets"] = target_tickets
    target_html = templates.TemplateResponse(
        "partials/column.html", context
    ).body.decode()

    # If the ticket moved (not just refreshed), also update the source column
    if old_status != status:
        source_tickets = crud.list_tickets(session, status=old_status, board_id=board_id)
        context["status"] = old_status
        context["tickets"] = source_tickets
        source_html = templates.TemplateResponse(
            "partials/column.html", context
        ).body.decode()

        # HTMX out-of-band swap updates the source column too
        oob_html = f'<div id="column-{old_status.value}" hx-swap-oob="innerHTML">{source_html}</div>'
        return HTMLResponse(target_html + oob_html)

    return HTMLResponse(target_html)


@router.post("/tickets/{ticket_id}/delete", response_class=HTMLResponse)
def delete_ticket(
    request: Request,
    ticket_id: int,
    session: Session = Depends(get_session),
):
    """Delete a ticket and all its children."""
    deleted = crud.delete_ticket(session, ticket_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    return HTMLResponse("")
