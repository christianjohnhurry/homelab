"""
Migration: Add boards table and assign existing tickets to a default board.

This migration:
1. Assumes the board table already exists (created by SQLModel.metadata.create_all)
2. Creates a "Default Board" if there are any orphan projects
3. Assigns all orphan projects to the default board
4. Propagates board_id to all tasks and subtasks

Run this AFTER the new Board model is added to models.py and init_db() is called.
"""

from sqlmodel import Session, select

from kanana_banana.database import engine
from kanana_banana.models import Board, Ticket, TicketType


def migrate() -> None:
    """
    Migrate existing tickets to use the new board system.

    This is idempotent - it can be run multiple times safely.
    """
    with Session(engine) as session:
        # Check if there are any projects without a board_id
        orphan_projects = session.exec(
            select(Ticket).where(
                Ticket.ticket_type == TicketType.PROJECT,
                Ticket.board_id == None,  # noqa: E711 (SQLAlchemy needs == None)
            )
        ).all()

        if not orphan_projects:
            print("Migration: No orphan projects found, nothing to migrate.")
            return

        print(f"Migration: Found {len(orphan_projects)} projects without a board.")

        # Create or get the default board
        default_board = session.exec(
            select(Board).where(Board.name == "Default Board")
        ).first()

        if default_board is None:
            default_board = Board(
                name="Default Board",
                description="Auto-created during migration. Rename me!",
            )
            session.add(default_board)
            session.commit()
            session.refresh(default_board)
            print(f"Migration: Created 'Default Board' with id {default_board.id}")
        else:
            print(f"Migration: Using existing 'Default Board' (id {default_board.id})")

        # Assign all orphan projects to the default board
        for project in orphan_projects:
            project.board_id = default_board.id
            # If the project has a repo_url, optionally use it for the board
            # (only if the board doesn't have one yet)
            if project.repo_url and not default_board.repo_url:
                default_board.repo_url = project.repo_url

        session.commit()
        print(f"Migration: Assigned {len(orphan_projects)} projects to Default Board.")

        # Now propagate board_id to all tasks (children of projects)
        tasks_updated = 0
        tasks = session.exec(
            select(Ticket).where(
                Ticket.ticket_type == TicketType.TASK,
                Ticket.board_id == None,  # noqa: E711
            )
        ).all()

        for task in tasks:
            if task.parent_id:
                parent = session.get(Ticket, task.parent_id)
                if parent and parent.board_id:
                    task.board_id = parent.board_id
                    tasks_updated += 1

        session.commit()
        if tasks_updated:
            print(f"Migration: Propagated board_id to {tasks_updated} tasks.")

        # Propagate to subtasks (children of tasks)
        subtasks_updated = 0
        subtasks = session.exec(
            select(Ticket).where(
                Ticket.ticket_type == TicketType.SUBTASK,
                Ticket.board_id == None,  # noqa: E711
            )
        ).all()

        for subtask in subtasks:
            if subtask.parent_id:
                parent = session.get(Ticket, subtask.parent_id)
                if parent and parent.board_id:
                    subtask.board_id = parent.board_id
                    subtasks_updated += 1

        session.commit()
        if subtasks_updated:
            print(f"Migration: Propagated board_id to {subtasks_updated} subtasks.")

        print("Migration: Complete!")
