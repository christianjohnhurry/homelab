# HomeLab Kanban Board MVP — Session Plan

## Tech Stack
- **Python 3.12+**, **FastAPI**, **SQLModel** (SQLAlchemy + Pydantic wrapper)
- **SQLite** via SQLModel, **Jinja2 + HTMX** for the UI
- **Pixi** workspace with kanban as a subpackage

## Directory Structure

```
~/code/homelab/
├── pyproject.toml              # Root pixi workspace
├── .gitignore
├── README.md
└── packages/
    └── kanban/
        ├── pyproject.toml      # Kanban subpackage (fastapi, sqlmodel, jinja2, uvicorn)
        └── src/
            └── kanban/
                ├── __init__.py
                ├── app.py          # FastAPI app factory + main() entry point
                ├── config.py       # Settings (DB path, debug)
                ├── database.py     # Engine, session, init_db
                ├── models.py       # Ticket model + enums + schemas
                ├── crud.py         # CRUD with hierarchy validation
                ├── export.py       # Markdown export logic
                ├── routers/
                │   ├── __init__.py
                │   ├── tickets.py  # REST JSON API (/api/v1/tickets)
                │   └── board.py    # HTML board routes (/, /tickets/...)
                ├── templates/
                │   ├── base.html
                │   ├── board.html
                │   └── partials/
                │       ├── column.html
                │       ├── ticket_card.html
                │       ├── ticket_form.html
                │       └── ticket_detail.html
                └── static/
                    └── style.css
```

## Data Model

**Single `ticket` table** with self-referential `parent_id`:

| Field | Type | Notes |
|-------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | VARCHAR(200) | Required |
| ticket_type | ENUM | project / task / subtask |
| status | ENUM | to-do / in-progress / on-hold / done |
| description | TEXT | Optional |
| repo_url | VARCHAR(500) | Only meaningful on projects |
| parent_id | INTEGER FK → ticket.id | Nullable, cascade delete |
| created_at | TIMESTAMP | Auto |
| updated_at | TIMESTAMP | Auto |

**Hierarchy rules** (enforced in CRUD layer):
- `project` → no parent, can have task children
- `task` → parent must be a project, can have subtask children
- `subtask` → parent must be a task, no children

## API Endpoints

### REST API (`/api/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tickets` | List (filter by type/status/parent_id) |
| GET | `/api/v1/tickets/{id}` | Get with children |
| POST | `/api/v1/tickets` | Create |
| PATCH | `/api/v1/tickets/{id}` | Update fields |
| DELETE | `/api/v1/tickets/{id}` | Delete (cascades) |
| GET | `/api/v1/tickets/{id}/export` | Markdown export |

### Board HTML Routes (`/`)
| Method | Path | HTMX? | Description |
|--------|------|-------|-------------|
| GET | `/` | No | Full board page |
| GET | `/board/column/{status}` | Yes | Render single column |
| GET | `/tickets/new` | Yes | Create form |
| POST | `/tickets` | Yes | Handle create |
| GET | `/tickets/{id}` | Yes | Ticket detail |
| GET | `/tickets/{id}/edit` | Yes | Edit form |
| POST | `/tickets/{id}/edit` | Yes | Handle edit |
| POST | `/tickets/{id}/move` | Yes | Change status (OOB swap both columns) |
| POST | `/tickets/{id}/delete` | Yes | Delete ticket |

## Implementation Steps

### Step 1: Scaffold the repo
- `pixi init --format pyproject` in `~/code/homelab/`
- Edit root `pyproject.toml` to define workspace with `members = ["packages/kanban"]`
- Create `packages/kanban/` directory tree and its `pyproject.toml` with dependencies
- Add kanban as editable pypi dependency in root
- `pixi install`
- `git init`, write `.gitignore`

### Step 2: Data layer (`config.py`, `models.py`, `database.py`)
- `config.py` — Settings class with `database_url` defaulting to `sqlite:///` + path relative to package
- `models.py` — `TicketType` enum, `TicketStatus` enum, `Ticket` table model, `TicketCreate`/`TicketUpdate`/`TicketRead` schemas
- `database.py` — engine creation, `get_session()` dependency, `init_db()` that calls `create_all()`

### Step 3: CRUD layer (`crud.py`)
- `create_ticket()` with hierarchy validation
- `get_ticket()` with eager-loaded children
- `list_tickets()` with optional type/status/parent_id filters
- `update_ticket()`, `update_ticket_status()`
- `delete_ticket()`

### Step 4: FastAPI app + REST API (`app.py`, `routers/tickets.py`)
- `app.py` — app factory with lifespan (init_db on startup), mount static files, configure templates, include routers, `main()` entry point calling `uvicorn.run()`
- `routers/tickets.py` — JSON CRUD endpoints under `/api/v1/`

### Step 5: Board UI (`routers/board.py`, templates, CSS)
- `base.html` — layout with HTMX script, nav, modal div
- `board.html` — 4-column grid, one per status
- `partials/column.html` — column header + ticket cards loop
- `partials/ticket_card.html` — card with type badge, name, move buttons
- `partials/ticket_form.html` — create/edit form with parent dropdown
- `partials/ticket_detail.html` — full ticket view with children list
- `routers/board.py` — HTML routes with HTMX partial responses, OOB swaps for move operations
- `style.css` — CSS Grid board, color-coded columns and type badges

### Step 6: Markdown export (`export.py`)
- `export_ticket_markdown()` — generates markdown per ticket with hierarchy
- Wire into REST API as `GET /api/v1/tickets/{id}/export`

## Verification
1. `pixi install` succeeds
2. `pixi run kanban` starts the server on localhost:8000
3. Navigate to `http://localhost:8000/` — board renders with 4 empty columns
4. Create a project, then a task under it, then a subtask — all appear on board
5. Move tickets between columns via buttons — board updates correctly
6. Export a ticket as markdown via `/api/v1/tickets/{id}/export`
