import enum
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship


class TicketType(str, enum.Enum):
    """Type of ticket in the hierarchy."""

    PROJECT = "project"
    TASK = "task"
    SUBTASK = "subtask"


class TicketStatus(str, enum.Enum):
    """Status of a ticket on the kanban board."""

    TODO = "to-do"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    DONE = "done"


class TicketBase(SQLModel):
    """
    Shared fields for ticket create/update/read schemas.

    This is NOT a database table (no table=True), just a base class
    to avoid duplicating field definitions.
    """

    name: str = Field(max_length=200)
    ticket_type: TicketType = Field(default=TicketType.TASK)
    status: TicketStatus = Field(default=TicketStatus.TODO, index=True)
    description: str = Field(default="")
    repo_url: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = Field(default=None, foreign_key="ticket.id")


class Ticket(TicketBase, table=True):
    """
    Database table model for a ticket.

    Hierarchy:
    - project: no parent, can have task children
    - task: parent must be a project, can have subtask children
    - subtask: parent must be a task, no children
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Self-referential relationships
    # "back_populates" creates a bidirectional link between parent and children
    parent: Optional["Ticket"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Ticket.id"},
    )
    children: list["Ticket"] = Relationship(back_populates="parent")


class TicketCreate(TicketBase):
    """Schema for creating a ticket. No id or timestamps needed."""

    pass


class TicketUpdate(SQLModel):
    """
    Schema for partial updates.

    All fields are Optional so you can update just the fields you want.
    """

    name: Optional[str] = Field(default=None, max_length=200)
    status: Optional[TicketStatus] = None
    description: Optional[str] = None
    repo_url: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = None


class TicketRead(TicketBase):
    """Schema for API responses. Includes id and timestamps."""

    id: int
    created_at: datetime
    updated_at: datetime
