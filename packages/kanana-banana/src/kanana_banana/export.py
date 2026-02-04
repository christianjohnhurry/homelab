"""Markdown export for Claude Code consumption."""

import re
from sqlmodel import Session

from kanana_banana.models import Ticket, TicketType, TicketStatus
from kanana_banana import crud


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.

    Security: Prevents path traversal by removing / and \\ characters,
    and replaces other unsafe characters with underscores.
    """
    # Remove path separators to prevent traversal
    name = name.replace("/", "_").replace("\\", "_")
    # Replace other unsafe characters
    name = re.sub(r'[<>:"|?*]', "_", name)
    # Limit length
    return name[:100]


def status_checkbox(status: TicketStatus) -> str:
    """Return a checkbox character based on status."""
    if status == TicketStatus.DONE:
        return "[x]"
    return "[ ]"


def export_ticket_markdown(session: Session, ticket_id: int) -> str | None:
    """
    Export a single ticket as markdown.

    Format is designed for Claude Code consumption:
    - Uses markdown headers for structure
    - Includes metadata as a list
    - Shows subtasks with checkbox syntax
    - Includes parent/child relationships

    Returns None if ticket not found.
    """
    ticket = crud.get_ticket(session, ticket_id)
    if ticket is None:
        return None

    lines = []

    # Header with type badge
    lines.append(f"# [{ticket.ticket_type.value.upper()}] {ticket.name}")
    lines.append("")

    # Metadata section
    lines.append(f"- **ID:** {ticket.id}")
    lines.append(f"- **Type:** {ticket.ticket_type.value}")
    lines.append(f"- **Status:** {ticket.status.value}")

    if ticket.parent:
        parent = crud.get_ticket(session, ticket.parent_id)
        if parent:
            lines.append(
                f"- **Parent:** [{parent.ticket_type.value.upper()}] {parent.name} (#{parent.id})"
            )

    if ticket.repo_url:
        lines.append(f"- **Repo:** {ticket.repo_url}")

    lines.append(f"- **Created:** {ticket.created_at.strftime('%Y-%m-%d')}")
    lines.append(f"- **Updated:** {ticket.updated_at.strftime('%Y-%m-%d')}")
    lines.append("")

    # Description
    if ticket.description:
        lines.append("## Description")
        lines.append("")
        lines.append(ticket.description)
        lines.append("")

    # Children (subtasks/tasks)
    if ticket.children:
        child_type = "Tasks" if ticket.ticket_type == TicketType.PROJECT else "Subtasks"
        lines.append(f"## {child_type}")
        lines.append("")
        for child in ticket.children:
            checkbox = status_checkbox(child.status)
            status_text = child.status.value
            lines.append(
                f"- {checkbox} [{child.ticket_type.value.upper()}] {child.name} (#{child.id}) — {status_text}"
            )
        lines.append("")

    return "\n".join(lines)


def export_project_full_markdown(session: Session, project_id: int) -> str | None:
    """
    Export a project with its full hierarchy as markdown.

    Includes all tasks and subtasks nested under the project.
    Useful for getting a complete view of a project's status.

    Returns None if project not found.
    """
    project = crud.get_ticket(session, project_id)
    if project is None or project.ticket_type != TicketType.PROJECT:
        return None

    lines = []

    # Project header
    lines.append(f"# [{project.ticket_type.value.upper()}] {project.name}")
    lines.append("")

    # Metadata
    if project.repo_url:
        lines.append(f"- **Repo:** {project.repo_url}")
    lines.append(f"- **Status:** {project.status.value}")
    lines.append(f"- **Created:** {project.created_at.strftime('%Y-%m-%d')}")
    lines.append("")

    # Description
    if project.description:
        lines.append("## Description")
        lines.append("")
        lines.append(project.description)
        lines.append("")

    # Tasks and their subtasks
    if project.children:
        lines.append("## Tasks")
        lines.append("")

        for task in project.children:
            # Get full task with children
            full_task = crud.get_ticket(session, task.id)
            checkbox = status_checkbox(task.status)

            lines.append(
                f"### {checkbox} [{task.ticket_type.value.upper()}] {task.name} (#{task.id}) — {task.status.value}"
            )

            if task.description:
                lines.append("")
                lines.append(task.description)

            # Subtasks
            if full_task and full_task.children:
                lines.append("")
                for subtask in full_task.children:
                    sub_checkbox = status_checkbox(subtask.status)
                    lines.append(
                        f"- {sub_checkbox} {subtask.name} (#{subtask.id}) — {subtask.status.value}"
                    )

            lines.append("")

    return "\n".join(lines)


def get_export_filename(ticket: Ticket) -> str:
    """Generate a safe filename for a ticket export."""
    safe_name = sanitize_filename(ticket.name)
    return f"{ticket.id:04d}_{safe_name}.md"
