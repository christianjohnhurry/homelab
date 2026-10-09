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

- **Boards per repo:** each board has a short key (`HML`) and optionally its GitHub repo
- **Ticket hierarchy:** Projects → Tasks → Subtasks, plus tasks with no project for miscellaneous work
- **Ticket keys:** numbered per board (`HML-1`, `HML-2`, …) and shown on every card
- **Branches:** `kb branch HML-42` creates `hml-42-add-login-flow` on GitHub. Subtask branches stack on their task's branch
- **`kb` CLI:** add, list, move, edit and branch tickets from the terminal
- **Kanban board:** drag-free UI with move buttons (To-Do, In Progress, On Hold, Done) and a banana tree view
- **Markdown export:** export tickets for use with Claude Code
- **REST API:** everything the UI and `kb` do, under `/api/v1`

## Quick Start

```bash
# From the homelab root: start the server (leave it running)
pixi run kanana-banana
```

Open http://127.0.0.1:8000/, or use `kb` in another terminal:

```bash
pixi run kb board add HML "Homelab" --repo https://github.com/you/homelab
pixi run kb add "Kanban CLI" --project --board hml     # HML-1
pixi run kb add "Add kb ticket commands" --parent HML-1  # HML-2, a task
pixi run kb branch HML-2                                 # creates hml-2-add-kb-ticket-commands
```

To run `kb` from any directory, add an alias to your `~/.zshrc`:

```bash
alias kb='pixi run --manifest-path ~/code/homelab/pyproject.toml kb'
```

## Using `kb`

`kb` talks to the running server. If it isn't running, `kb` says how to start it.

```
kb board add KEY NAME [--repo URL] [--description TEXT]
kb board list [--json]

kb add NAME [--parent KEY] [--project] [-d TEXT] [--board KEY]
kb list [-s STATUS] [-t TYPE] [--tree] [--board KEY] [--json]
kb show KEY [--json]
kb move KEY to-do|in-progress|on-hold|done
kb edit KEY [--name NAME] [-d TEXT]
kb delete KEY [--yes]
kb export KEY
kb branch KEY
```

- **Keys** like `HML-42` work in any letter case.
- **Which board:** `add` (without a parent) and `list` use `--board KEY`, or else the board whose repo matches the current git repo's `origin`.
- **The type follows from the parent:** none makes a task (or a project with `--project`), a project parent makes a task, and a task parent makes a subtask.
- **`delete`** removes everything under the ticket and asks first, unless you pass `--yes`.
- **Statuses only change when you move them.** Creating a branch or merging a PR never moves a ticket.

### Branches

`kb branch HML-42` creates the ticket's branch on GitHub and records it on the ticket:

- **Name:** `{key}-{number}-{slug}` in lowercase, e.g. `hml-42-add-login-flow`. There is no type prefix, and the slug is cut at a word to 40 characters.
- **Tasks** branch from the repo's default branch.
- **Subtasks** are stacked: they branch from their task's branch, so create the task's branch first. Open the subtask's PR against the task branch.
- **Projects** never get branches.
- **Renaming** a ticket never renames its branch.

It prints the command to start work in a [dev-spaces](../dev-spaces/README.md) container:

```bash
dev-spaces create you/homelab hml-42-add-login-flow
```

Creating branches needs a GitHub token. Create `~/.config/kanana-banana/secrets.env`:

```bash
mkdir -p ~/.config/kanana-banana && chmod 700 ~/.config/kanana-banana
echo 'GH_TOKEN=github_pat_...' > ~/.config/kanana-banana/secrets.env
chmod 600 ~/.config/kanana-banana/secrets.env
```

Use a fine-grained token limited to your board repos, with **Contents: read/write**. Write the value with no quotes. The server reads it each time it creates a branch, so there's no need to restart.

## Ticket Types

| Type | Parent | Children | Branch |
|------|--------|----------|--------|
| project | none | tasks | never |
| task | a project, or none | subtasks | from the default branch |
| subtask | a task | none | stacked on the task's branch |

Tickets can't move between boards, because their keys embed the board key.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/boards` | List boards (`?key=HML` to find one by key) |
| POST | `/api/v1/boards` | Create a board (`key` and `name` required) |
| GET | `/api/v1/boards/{id}` | Get a board |
| PATCH | `/api/v1/boards/{id}` | Update a board's name, repo or description (not its key) |
| DELETE | `/api/v1/boards/{id}` | Delete an empty board |
| GET | `/api/v1/tickets` | List tickets (filter by `board_id`, `ticket_type`, `status`, `parent_id`) |
| GET | `/api/v1/tickets/by-key/{key}` | Get a ticket by key, e.g. `HML-42` |
| GET | `/api/v1/tickets/{id}` | Get a ticket |
| POST | `/api/v1/tickets` | Create a ticket |
| PATCH | `/api/v1/tickets/{id}` | Update a ticket |
| PATCH | `/api/v1/tickets/{id}/status?new_status=done` | Move a ticket |
| DELETE | `/api/v1/tickets/{id}` | Delete a ticket and everything under it |
| GET | `/api/v1/tickets/{id}/export` | Export as markdown |
| POST | `/api/v1/tickets/{id}/branch` | Create the ticket's branch on GitHub |

Interactive docs are at http://127.0.0.1:8000/docs.

```bash
# A board, then a project on it
curl -X POST http://127.0.0.1:8000/api/v1/boards \
  -H "Content-Type: application/json" \
  -d '{"key": "HML", "name": "Homelab", "repo_url": "https://github.com/you/homelab"}'

curl -X POST http://127.0.0.1:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "ticket_type": "project", "board_id": 1}'
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `KANANA_BANANA_DATABASE_URL` | `sqlite:///~/.local/share/kanana-banana/kanana_banana.db` (respects `XDG_DATA_HOME`) | Database. The same file whichever directory you start the server from |
| `KANANA_BANANA_CONFIG_DIR` | `~/.config/kanana-banana` | Where `secrets.env` lives |
| `KANANA_BANANA_DEBUG` | `True` | Log SQL queries |
| `KB_URL` | `http://127.0.0.1:8000` | Server address `kb` talks to |

## Development

```bash
pixi run test-kanana-banana   # API, web UI, kb and GitHub (faked) tests
```

See [PLAN.md](PLAN.md) for the 0.2.0 design and [CHANGELOG.md](CHANGELOG.md) for changes.
Versioning follows semver. Releases are tagged `kanana-banana-vX.Y.Z`.

## Tech Stack

- **FastAPI**: web framework
- **SQLModel**: ORM (SQLAlchemy + Pydantic)
- **SQLite**: database
- **Jinja2 + HTMX**: frontend
- **Typer + httpx2**: `kb` CLI and GitHub client
