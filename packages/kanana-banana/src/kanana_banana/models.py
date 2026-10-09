import enum
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import ConfigDict, field_validator
from sqlmodel import SQLModel, Field, Relationship


def utc_now() -> datetime:
    """Current time in UTC, timezone-aware (SQLModel rejects naive datetimes)."""
    return datetime.now(timezone.utc)


class TicketType(str, enum.Enum):
    """Type of ticket in the hierarchy."""

    PROJECT = "project"
    TASK = "task"
    SUBTASK = "subtask"


# =============================================================================
# Board Model
# =============================================================================
# A Board represents a repository/project namespace. Each board has its own
# kanban view with its own set of projects (and their tasks/subtasks).
# =============================================================================


class Board(SQLModel, table=True):
    """
    A board represents a repository or project namespace.

    Each board contains its own set of projects, which in turn contain
    tasks and subtasks. This allows you to have separate kanban views
    for different repos.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    # Short uppercase code that prefixes ticket keys (HML-42) and branch names.
    # Set once at creation and never changed, because branch names embed it.
    key: str = Field(max_length=50, unique=True, index=True)
    name: str = Field(max_length=200, index=True)
    repo_url: Optional[str] = Field(default=None, max_length=500)
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    # Next ticket number on this board. Only ever increases, so numbers are never reused.
    next_number: int = Field(default=1)

    # Relationship: a board has many tickets (specifically, projects)
    # The back_populates="board" links to Ticket.board
    tickets: list["Ticket"] = Relationship(back_populates="board")


BOARD_KEY_PATTERN = re.compile(r"^[A-Za-z]+$")


def normalise_board_key(value: str) -> str:
    """Board keys are letters only, of any length, stored uppercase."""
    value = value.strip()
    if not BOARD_KEY_PATTERN.match(value):
        raise ValueError("Board key must be letters only, e.g. HML")
    return value.upper()


class BoardCreate(SQLModel):
    """Schema for creating a board."""

    key: str = Field(max_length=50)
    name: str = Field(max_length=200)
    repo_url: Optional[str] = Field(default=None, max_length=500)
    description: str = Field(default="")

    @field_validator("key")
    @classmethod
    def _normalise_key(cls, value: str) -> str:
        return normalise_board_key(value)


class BoardUpdate(SQLModel):
    """
    Schema for partial board updates.

    There is no key field: keys can't change. Unknown fields are rejected,
    so an attempt to change the key fails loudly instead of being ignored.
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, max_length=200)
    repo_url: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None


class BoardRead(SQLModel):
    """Schema for board API responses."""

    id: int
    key: str
    name: str
    repo_url: Optional[str]
    description: str
    created_at: datetime
    updated_at: datetime


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
    parent_id: Optional[int] = Field(default=None, foreign_key="ticket.id")
    # board_id links this ticket to a Board. Projects MUST have a board_id.
    # Tasks and subtasks inherit it from their parent project.
    # It's nullable during migration, but we enforce it in CRUD logic.
    board_id: Optional[int] = Field(default=None, foreign_key="board.id", index=True)


class Ticket(TicketBase, table=True):
    """
    Database table model for a ticket.

    Hierarchy:
    - project: no parent, can have task children
    - task: parent must be a project, can have subtask children
    - subtask: parent must be a task, no children
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    # Per-board number and its key (HML-42), assigned on create. Tickets never
    # move between boards, so a key is fixed for life, like the branch name.
    number: Optional[int] = Field(default=None)
    key: Optional[str] = Field(default=None, max_length=60, unique=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Self-referential relationships
    # "back_populates" creates a bidirectional link between parent and children
    parent: Optional["Ticket"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Ticket.id"},
    )
    # Deleting a ticket deletes its children (and theirs). SQLite doesn't
    # enforce foreign keys by default, so the ORM does the cascade.
    children: list["Ticket"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )

    # Board relationship - links this ticket to a Board
    # The back_populates="tickets" connects to Board.tickets
    board: Optional["Board"] = Relationship(back_populates="tickets")


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
    parent_id: Optional[int] = None
    board_id: Optional[int] = None


class TicketRead(TicketBase):
    """Schema for API responses. Includes id, key and timestamps."""

    id: int
    number: int
    key: str
    created_at: datetime
    updated_at: datetime
