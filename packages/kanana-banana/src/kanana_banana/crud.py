from datetime import datetime
from typing import Optional

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from kanana_banana.models import (
    Ticket,
    TicketCreate,
    TicketUpdate,
    TicketType,
    TicketStatus,
)


class HierarchyError(ValueError):
    """Raised when a ticket hierarchy constraint is violated."""

    pass


def validate_hierarchy(
    session: Session,
    ticket_type: TicketType,
    parent_id: Optional[int],
) -> None:
    """
    Validate that a ticket's parent relationship follows the hierarchy rules.

    Rules:
    - project: no parent allowed
    - task: parent must exist and be a project
    - subtask: parent must exist and be a task

    Raises:
        HierarchyError: If the hierarchy constraint is violated.
    """
    if ticket_type == TicketType.PROJECT:
        if parent_id is not None:
            raise HierarchyError("Projects cannot have a parent ticket.")
        return

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


def create_ticket(session: Session, ticket_create: TicketCreate) -> Ticket:
    """
    Create a new ticket with hierarchy validation.

    Returns the created ticket with its id populated.
    """
    validate_hierarchy(session, ticket_create.ticket_type, ticket_create.parent_id)

    ticket = Ticket.model_validate(ticket_create)
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
) -> list[Ticket]:
    """
    List tickets with optional filters.

    Args:
        ticket_type: Filter by type (project/task/subtask)
        status: Filter by status (to-do/in-progress/on-hold/done)
        parent_id: Filter by parent ticket id

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

    # If parent_id is changing, validate the new hierarchy
    if "parent_id" in update_data:
        validate_hierarchy(session, ticket.ticket_type, update_data["parent_id"])

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
