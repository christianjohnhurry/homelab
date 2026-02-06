# Source Code Overview

Kanana Banana is a FastAPI-based kanban board for tracking projects, tasks, and subtasks. Each repository/project gets its own board, selectable via a sidebar.

## Core Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI application factory. Creates the app, mounts static files, includes routers, and handles startup (database init + migration). Entry point for `uvicorn`. |
| `config.py` | Application settings via `pydantic-settings`. Loads `KANANA_BANANA_*` env vars. Defines database URL and debug flag. |
| `models.py` | SQLModel database models. Defines `Board` and `Ticket` tables. Tickets have hierarchical types (project → task → subtask) and belong to a board. Includes Pydantic schemas for create/update/read. |
| `database.py` | Database engine setup with SQLite. Provides `get_session()` dependency for FastAPI routes. Runs migrations on startup. |
| `crud.py` | CRUD operations for boards and tickets. Enforces hierarchy rules (projects must have a board, tasks need project parent, subtasks need task parent). |
| `templating.py` | Jinja2 template configuration. Points to `templates/` directory. |
| `export.py` | Markdown export for Claude Code. Converts tickets to structured markdown with checkboxes for subtasks. |

## Routers

| File | Purpose |
|------|---------|
| `routers/board.py` | HTML routes for the kanban board UI. Serves board-specific views at `/boards/{id}`, HTMX partials for columns, ticket forms, and moves. Handles the root redirect. |
| `routers/boards.py` | Board management routes. REST API at `/api/v1/boards` plus HTML form routes for create/edit board modals. |
| `routers/tickets.py` | REST API (`/api/v1/tickets`). JSON endpoints for listing, creating, updating, deleting tickets. Includes markdown export endpoint. |

## Directories

| Directory | Contents |
|-----------|----------|
| `migrations/` | Database migration scripts. `add_boards.py` handles migrating existing tickets to the new board system. |
| `templates/` | Jinja2 HTML templates: `base.html` (with sidebar), `board.html`, and `partials/` for HTMX components |
| `static/` | CSS styles (`style.css`) including sidebar layout |

## Data Model

```
Board (repo/project namespace)
  └── Project (ticket_type=project)
        └── Task (ticket_type=task)
              └── Subtask (ticket_type=subtask)
```

Each ticket has a `board_id` linking it to a board. Projects must have a board_id; tasks and subtasks inherit it from their parent.
