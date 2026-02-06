from datetime import datetime
from typing import Optional

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from kanana_banana.models import (
    Board,
    BoardCreate,
    BoardUpdate,
    Ticket,
    TicketCreate,
    TicketUpdate,
    TicketType,
    TicketStatus,
)


class HierarchyError(ValueError):
    """Raised when a ticket hierarchy constraint is violated."""

    pass


# =============================================================================
# Board CRUD Operations
# =============================================================================


def create_board(session: Session, board_create: BoardCreate) -> Board:
    """
    Create a new board.

    A board represents a repository or project namespace with its own
    kanban view.
    """
    board = Board.model_validate(board_create)
    session.add(board)
    session.commit()
    session.refresh(board)
    return board


def get_board(session: Session, board_id: int) -> Optional[Board]:
    """Get a board by id. Returns None if not found."""
    return session.get(Board, board_id)


def list_boards(session: Session) -> list[Board]:
    """List all boards ordered by name."""
    statement = select(Board).order_by(Board.name)
    return list(session.exec(statement).all())


def update_board(
    session: Session,
    board_id: int,
    board_update: BoardUpdate,
) -> Optional[Board]:
    """
    Update a board with the provided fields.

    Only non-None fields in board_update are applied.
    Returns the updated board, or None if not found.
    """
    board = session.get(Board, board_id)
    if board is None:
        return None

    update_data = board_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(board, key, value)

    board.updated_at = datetime.utcnow()
    session.add(board)
    session.commit()
    session.refresh(board)
    return board


def delete_board(session: Session, board_id: int) -> bool:
    """
    Delete a board.

    This will fail if there are tickets associated with the board.
    Move or delete tickets first before deleting the board.

    Returns True if deleted, False if not found.
    Raises ValueError if board has tickets.
    """
    board = session.get(Board, board_id)
    if board is None:
        return False

    # Check for existing tickets on this board
    tickets = session.exec(
        select(Ticket).where(Ticket.board_id == board_id)
    ).all()

    if tickets:
        raise ValueError(
            f"Cannot delete board with {len(tickets)} tickets. "
            "Move or delete them first."
        )

    session.delete(board)
    session.commit()
    return True


# =============================================================================
# Ticket CRUD Operations
# =============================================================================


def validate_hierarchy(
    session: Session,
    ticket_type: TicketType,
    parent_id: Optional[int],
    board_id: Optional[int] = None,
) -> Optional[int]:
    """
    Validate that a ticket's parent relationship follows the hierarchy rules.

    Rules:
    - project: no parent allowed, board_id required
    - task: parent must exist and be a project, inherits board from parent
    - subtask: parent must exist and be a task, inherits board from parent

    Args:
        session: Database session
        ticket_type: The type of ticket being created/updated
        parent_id: The parent ticket id (None for projects)
        board_id: The board id (required for projects, inherited for others)

    Returns:
        The board_id to use (either provided or inherited from parent)

    Raises:
        HierarchyError: If the hierarchy constraint is violated.
    """
    if ticket_type == TicketType.PROJECT:
        if parent_id is not None:
            raise HierarchyError("Projects cannot have a parent ticket.")
        if board_id is None:
            raise HierarchyError("Projects must belong to a board.")
        # Verify board exists
        board = session.get(Board, board_id)
        if board is None:
            raise HierarchyError(f"Board with id {board_id} not found.")
        return board_id

    # Tasks and subtasks require a parent
    if parent_id is None:
        raise HierarchyError(f"{ticket_type.value.title()}s must have a parent ticket.")

    # Fetch the parent to check its type
    parent = session.get(Ticket, parent_id)
    if parent is None:
        raise HierarchyError(f"Parent ticket with id {parent_id} not found.")

    if ticket_type == TicketType.TASK:
        if parent.ticket_type != TicketType.PROJECT:
            raise HierarchyError("Tasks must have a project as their parent.")
    elif ticket_type == TicketType.SUBTASK:
        if parent.ticket_type != TicketType.TASK:
            raise HierarchyError("Subtasks must have a task as their parent.")

    # Inherit board_id from parent (tasks/subtasks get the same board as their parent)
    return parent.board_id


def create_ticket(session: Session, ticket_create: TicketCreate) -> Ticket:
    """
    Create a new ticket with hierarchy validation.

    For projects: board_id must be provided in ticket_create
    For tasks/subtasks: board_id is inherited from the parent

    Returns the created ticket with its id populated.
    """
    # Validate hierarchy and get the board_id (either provided or inherited)
    board_id = validate_hierarchy(
        session,
        ticket_create.ticket_type,
        ticket_create.parent_id,
        ticket_create.board_id,
    )

    ticket = Ticket.model_validate(ticket_create)
    # Ensure board_id is set (important for tasks/subtasks that inherit it)
    ticket.board_id = board_id
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def get_ticket(session: Session, ticket_id: int) -> Optional[Ticket]:
    """
    Get a ticket by id with its children eagerly loaded.

    Returns None if not found.
    """
    statement = (
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.children))
    )
    return session.exec(statement).first()


def list_tickets(
    session: Session,
    ticket_type: Optional[TicketType] = None,
    status: Optional[TicketStatus] = None,
    parent_id: Optional[int] = None,
    board_id: Optional[int] = None,
) -> list[Ticket]:
    """
    List tickets with optional filters.

    Args:
        ticket_type: Filter by type (project/task/subtask)
        status: Filter by status (to-do/in-progress/on-hold/done)
        parent_id: Filter by parent ticket id
        board_id: Filter by board id (tickets belonging to this board)

    Returns:
        List of matching tickets with children eagerly loaded.
    """
    statement = select(Ticket).options(selectinload(Ticket.children))

    if ticket_type is not None:
        statement = statement.where(Ticket.ticket_type == ticket_type)
    if status is not None:
        statement = statement.where(Ticket.status == status)
    if parent_id is not None:
        statement = statement.where(Ticket.parent_id == parent_id)
    if board_id is not None:
        statement = statement.where(Ticket.board_id == board_id)

    return list(session.exec(statement).all())


def update_ticket(
    session: Session,
    ticket_id: int,
    ticket_update: TicketUpdate,
) -> Optional[Ticket]:
    """
    Update a ticket with the provided fields.

    Only non-None fields in ticket_update are applied.
    If parent_id is being changed, hierarchy is re-validated.

    Returns the updated ticket, or None if not found.
    """
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        return None

    update_data = ticket_update.model_dump(exclude_unset=True)

    # If parent_id or board_id is changing, validate the new hierarchy
    if "parent_id" in update_data or "board_id" in update_data:
        new_parent_id = update_data.get("parent_id", ticket.parent_id)
        new_board_id = update_data.get("board_id", ticket.board_id)
        # Validate and get the correct board_id (may be inherited from parent)
        resolved_board_id = validate_hierarchy(
            session, ticket.ticket_type, new_parent_id, new_board_id
        )
        update_data["board_id"] = resolved_board_id

    # Apply updates
    for key, value in update_data.items():
        setattr(ticket, key, value)

    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def update_ticket_status(
    session: Session,
    ticket_id: int,
    new_status: TicketStatus,
) -> Optional[Ticket]:
    """
    Update just the status of a ticket.

    This is a convenience method for the common "move ticket" operation.

    Returns the updated ticket, or None if not found.
    """
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        return None

    ticket.status = new_status
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def delete_ticket(session: Session, ticket_id: int) -> bool:
    """
    Delete a ticket and all its children (cascade).

    Returns True if the ticket was found and deleted, False otherwise.
    """
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        return False

    session.delete(ticket)
    session.commit()
    return True
