<p align="center">
  <img src="src/kanana_banana/assets/kanana.png" alt="Kanana Banana" width="300">
</p>

# Kanana Banana

A simple local kanban board for tracking projects, tasks, and subtasks.

Kanana Banana is a kanban board for hobby-code projects. Software engineers are used to using kanban boards for project management, and for communicating to teammates where changes to the codebase are being made and their status of progression with those changes. 

Kanban boards are often associated with SCRUM like product management frameworks, in which tickets are usually defined by what is delivered and the time it is expected to take to complete that delivery. These are tried and tested methods for delivering high quality software at pace.

However, after you've cooked dinner, finished eating, and cleaned the dishes, the last thing you might want to do is assign yourself a time-sensitive task. 

Some software, we develop for our own enjoyment, our own education, and simply for fun. That doesn't mean the code beneath a hobby project isn't complex, and so we still may need to manage and plan out our ideas into well defined itemised actions. 

Hence, Kanana Banana. A kanban board with the hobbyist at heart. 

The philosophy of a Kanana Banana project is:

- Every repository of code has its own kanana banana board
- Every big feature is assigned a PROJECT ticket 
- Every task needed to complete that PROJECT is assigned a TASK ticket
- Code reviews should be performed for every TASK
- If a TASK needs to be split into multiple pull requests to keep review manageable, it should be split into SUBTASK tickets
- Miscellaneous tasks, such as fixes, should be assigned a TASK ticket with no parent PROJECT

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
