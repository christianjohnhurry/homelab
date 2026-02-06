"""
API and HTML routes for board management.

This router handles:
- REST API endpoints for board CRUD (under /api/v1/boards)
- HTML form routes for creating/editing boards (for HTMX modals)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from kanana_banana.templating import templates
from kanana_banana.database import get_session
from kanana_banana.models import Board, BoardCreate, BoardUpdate, BoardRead
from kanana_banana import crud


router = APIRouter(tags=["boards"])


# =============================================================================
# REST API Routes
# =============================================================================
# These return JSON and are useful for programmatic access or testing.


@router.get("/api/v1/boards", response_model=list[BoardRead])
def api_list_boards(session: Session = Depends(get_session)) -> list[Board]:
    """List all boards."""
    return crud.list_boards(session)


@router.post(
    "/api/v1/boards",
    response_model=BoardRead,
    status_code=http_status.HTTP_201_CREATED,
)
def api_create_board(
    board_create: BoardCreate,
    session: Session = Depends(get_session),
) -> Board:
    """Create a new board."""
    return crud.create_board(session, board_create)


@router.get("/api/v1/boards/{board_id}", response_model=BoardRead)
def api_get_board(
    board_id: int,
    session: Session = Depends(get_session),
) -> Board:
    """Get a single board by id."""
    board = crud.get_board(session, board_id)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )
    return board


@router.patch("/api/v1/boards/{board_id}", response_model=BoardRead)
def api_update_board(
    board_id: int,
    board_update: BoardUpdate,
    session: Session = Depends(get_session),
) -> Board:
    """Update a board with the provided fields."""
    board = crud.update_board(session, board_id, board_update)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )
    return board


@router.delete("/api/v1/boards/{board_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def api_delete_board(
    board_id: int,
    session: Session = Depends(get_session),
) -> None:
    """
    Delete a board.

    Fails if the board has any tickets - delete or move them first.
    """
    try:
        if not crud.delete_board(session, board_id):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# HTML Routes (for HTMX)
# =============================================================================
# These return HTML fragments for the modal system.


@router.get("/boards/new", response_class=HTMLResponse)
def new_board_form(request: Request):
    """Render the create board form (HTMX partial for modal)."""
    return templates.TemplateResponse(
        "partials/board_form.html",
        {"request": request, "board": None},
    )


@router.post("/boards", response_class=HTMLResponse)
def create_board(
    request: Request,
    name: str = Form(...),
    repo_url: Optional[str] = Form(None),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    """
    Handle board creation from form submission.

    On success, returns empty response (JS will reload the page).
    """
    board_create = BoardCreate(
        name=name,
        repo_url=repo_url if repo_url else None,
        description=description,
    )
    crud.create_board(session, board_create)
    return HTMLResponse("")


@router.get("/boards/{board_id}/edit", response_class=HTMLResponse)
def edit_board_form(
    request: Request,
    board_id: int,
    session: Session = Depends(get_session),
):
    """Render the edit board form (HTMX partial for modal)."""
    board = crud.get_board(session, board_id)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )

    return templates.TemplateResponse(
        "partials/board_form.html",
        {"request": request, "board": board},
    )


@router.post("/boards/{board_id}/edit", response_class=HTMLResponse)
def update_board(
    request: Request,
    board_id: int,
    name: str = Form(...),
    repo_url: Optional[str] = Form(None),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    """
    Handle board update from form submission.

    On success, returns empty response (JS will reload the page).
    """
    board_update = BoardUpdate(
        name=name,
        repo_url=repo_url if repo_url else None,
        description=description,
    )
    board = crud.update_board(session, board_id, board_update)
    if board is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Board not found",
        )
    return HTMLResponse("")


@router.post("/boards/{board_id}/delete", response_class=HTMLResponse)
def delete_board(
    request: Request,
    board_id: int,
    session: Session = Depends(get_session),
):
    """
    Delete a board.

    On success, returns empty response (JS will redirect to /).
    Fails if board has tickets.
    """
    try:
        if not crud.delete_board(session, board_id):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return HTMLResponse("")
