# 🍌 Kanana Banana

A simple local kanban board for tracking projects, tasks, and subtasks.

## Features

- **Ticket hierarchy:** Projects → Tasks → Subtasks
- **Kanban board:** Drag-free UI with move buttons (To-Do, In Progress, On Hold, Done)
- **Markdown export:** Export tickets for use with Claude Code
- **REST API:** Full CRUD operations at `/api/v1/tickets`
- **HTMX-powered:** Instant updates without page reloads

## Quick Start

```bash
# From the homelab root
pixi run kanana-banana
```

Open http://127.0.0.1:8000/

## API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tickets` | List tickets (filter by type/status/parent_id) |
| GET | `/api/v1/tickets/{id}` | Get ticket by id |
| POST | `/api/v1/tickets` | Create ticket |
| PATCH | `/api/v1/tickets/{id}` | Update ticket |
| DELETE | `/api/v1/tickets/{id}` | Delete ticket (cascades to children) |
| GET | `/api/v1/tickets/{id}/export` | Export ticket as markdown |

### Example: Create a Project

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "ticket_type": "project"}'
```

### Example: Create a Task under a Project

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"name": "Build feature X", "ticket_type": "task", "parent_id": 1}'
```

## Ticket Types

| Type | Parent | Children |
|------|--------|----------|
| project | None | tasks |
| task | project | subtasks |
| subtask | task | None |

## Configuration

Set environment variables to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `KANANA_BANANA_DATABASE_URL` | `sqlite:///kanana_banana.db` | Database connection string |
| `KANANA_BANANA_DEBUG` | `True` | Enable SQL query logging |

## Tech Stack

- **FastAPI** — Web framework
- **SQLModel** — ORM (SQLAlchemy + Pydantic)
- **SQLite** — Database
- **Jinja2 + HTMX** — Frontend
