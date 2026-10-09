# Kanana Banana 0.2.0: Plan

Adds `kb`, a command-line client for the board, plus board keys, per-board ticket numbers
(`HML-42`) and ticket branches created on GitHub. Also adds a Claude skill describing the
Kanana Banana + dev-spaces workflow.

## Decisions

| Topic | Decision |
|-------|----------|
| Users | Just you, on the Mac. Agents inside dev-spaces containers don't use `kb` |
| Architecture | `kb` talks to the REST API. The server keeps all the rules |
| Server | Started by hand (`pixi run kanana-banana`). `kb` gives a clear error if it's down |
| Database | Fixed location `~/.local/share/kanana-banana/kanana_banana.db`. Start fresh, with no migration of old data |
| Command | A new `kb` script. `kanana-banana` still starts the server, unchanged |
| Board keys | Letters only, any length, stored uppercase, unique, can't change once set |
| Ticket numbers | Per board: `HML-1`, `HML-2`, … for every ticket type |
| Branches | Tasks and subtasks only, never projects. Created on GitHub, recorded on the ticket |
| Branch names | `hml-42-add-login-flow`: lowercase key, number and slug, with no type. Never renamed |
| Stacking | Subtask branches are cut from the parent task's branch. Task branches are cut from the repo's default branch |
| GitHub token | Kanana Banana's own `~/.config/kanana-banana/secrets.env` |
| Status | Moved by hand only. Creating a branch or merging a PR never changes it |
| Packages | kanana-banana and dev-spaces stay independent. A Claude skill ties them together |
| Versioning | Semver plus a changelog starting at 0.2.0. No release until the new CLI **and** the existing API are tested |

## Data Model Changes

**Board**
- `key: str`: required, unique, matches `^[A-Za-z]+$`, stored uppercase. Can't be changed (`BoardUpdate` has no `key`).
- `next_number: int = 1`: per-board ticket counter.

**Ticket**
- `number: int`: assigned from the board's `next_number` on create. Unique per `(board_id, number)`.
- `branch: str | None`: set once by the branch endpoint. Never changed afterwards.
- `TicketRead` gains a computed `key` (`"HML-42"`).

**Hierarchy:** a task may have **no parent** if it gives a `board_id`, for miscellaneous fixes,
as the README's philosophy describes. It may still have a project as its parent.

## API Changes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/boards` | Now requires `key` |
| GET | `/api/v1/boards?key=HML` | Filter by key |
| GET | `/api/v1/tickets/by-key/{key}` | Look up `HML-42`, case-insensitively |
| POST | `/api/v1/tickets/{id}/branch` | Create the ticket's branch on GitHub and record it |

### Branch endpoint
1. The ticket must be a task or subtask, must not already have a branch, and its board must have a GitHub `repo_url`.
2. **Base branch:** a task uses the repo's default branch. A subtask uses its parent task's branch, and fails with "create HML-41's branch first" if there isn't one.
3. **Name:** `{key}-{number}-{slug}` in lowercase. The slug is the ticket name with anything that isn't `[a-z0-9]` replaced by `-`, repeated dashes collapsed, and cut to 40 characters at a dash.
4. **GitHub calls** (with `GH_TOKEN` from kanana-banana's `secrets.env`):
   - `GET /repos/{o}/{r}` gives the default branch.
   - `GET /repos/{o}/{r}/git/ref/heads/{base}` gives the base commit.
   - `POST /repos/{o}/{r}/git/refs` creates the branch.
5. Saves `branch` on the ticket. If the branch already exists on GitHub (`422`), fail and change nothing.

The work lives in the server so the web UI can get a "Create branch" button later.

## `kb` Commands

```
kb board add <KEY> <name> [--repo URL] [--description TEXT]
kb board list

kb add <name> [--parent HML-3] [--project] [--description TEXT] [--board KEY]
kb list [--status S] [--type T] [--tree] [--board KEY] [--json]
kb show <HML-42> [--json]
kb move <HML-42> <to-do|in-progress|on-hold|done>
kb edit <HML-42> [--name N] [--description D]
kb delete <HML-42> [--yes]
kb export <HML-42>
kb branch <HML-42>
```

- **`add` works out the type:** `--project` makes a project. A project parent makes a task, a task parent makes a subtask, and no parent makes a parentless task.
- **Finding the board** (for `add` without a parent, and for `list`): `--board KEY` wins. Otherwise `kb` matches the current repo's `origin` URL against each board's `repo_url`. If neither works, it fails and lists the boards. Ticket keys like `HML-42` already carry their board.
- **`delete`** asks for confirmation (it also deletes the ticket's children) unless you pass `--yes`.
- **`branch`** prints the branch name and the matching command, `dev-spaces create owner/repo hml-42`.
- **Server URL:** `KB_URL`, default `http://127.0.0.1:8000`. If the server is unreachable: "Kanana Banana isn't running. Start it with `pixi run kanana-banana`."
- **`--json`** on `list` and `show`, for scripts and the skill.

## Configuration

- **Database:** `KANANA_BANANA_DATABASE_URL` still overrides it. The default is now under `~/.local/share/kanana-banana/`, and the folder is created on startup.
- **Secrets:** `~/.config/kanana-banana/secrets.env` (folder `700`, file `600`) holds `GH_TOKEN=`. `KANANA_BANANA_CONFIG_DIR` overrides the location. The token needs **Contents: read/write** on each board's repo.
- **Obsolete migration:** `migrations/add_boards.py` is removed, since we start fresh.

## Web UI (small changes)
- The board form gets a required **key** field.
- Cards and detail views show the ticket key (`HML-42`).
- Detail views show the branch if there is one.

## Claude Skill

`skills/ticket-workflow/SKILL.md` in the homelab repo, symlinked into `~/.claude/skills/` so
every project can use it. It explains:
- the Kanana Banana philosophy (projects, then tasks as PRs, then subtasks as split PRs)
- using `kb` to find or create tickets, with `--json` for reading them
- `kb branch` and then `dev-spaces create owner/repo <key-number>`, and stacking for subtasks
- working in the container, opening a PR (a subtask's PR targets its task's branch)
- that you move statuses yourself: Claude suggests moves but doesn't make them unless asked

The README documents the symlink setup.

## Testing

pytest in the existing pixi `test` feature, run with `pixi run test-kanana-banana`.

- **API:** FastAPI `TestClient` with a temporary SQLite database for each test, using `app.dependency_overrides[get_session]`.
- **GitHub:** faked with `httpx2.MockTransport`, which records requests and returns canned responses. The real API is never called.
- **CLI:** `kb` takes an injectable `httpx2.Client`. Tests pass the `TestClient`, so the CLI runs against the real app in the same process.

### Tests that gate 0.2.0
**Existing API (a safety net before any changes):**
- board CRUD
- ticket CRUD
- hierarchy rules
- cascading deletes
- status updates
- the markdown export

**New:**
- **Board keys:** validation, storing uppercase, uniqueness, can't change.
- **Ticket numbers:** per-board sequences, not reused after a delete, uniqueness. `by-key` works in any letter case.
- **Parentless tasks.**
- **Branch endpoint:**
  - naming and slug edge cases
  - the base branch for a task and a subtask (stacked)
  - refusing projects
  - refusing a ticket that already has a branch, a subtask whose parent has no branch, and a board with no repo
  - a GitHub 422 leaves the ticket unchanged
  - the token never appears in errors
- **`kb`:**
  - every command
  - type inference
  - board lookup through the git remote
  - the server-down message
  - `--json` output
  - the delete confirmation

## Versioning

Same rules as dev-spaces: semver, Keep a Changelog, and no release without passing tests.
- The current code counts as **0.1.0**. `CHANGELOG.md` starts with `[Unreleased]` and becomes `[0.2.0]` at release.
- Tags are `kanana-banana-vX.Y.Z`.

## Roadmap (0.2.0)

One commit each, with changelog entries alongside:

1. **Test setup + tests for the existing API**, as a safety net
2. **Database location + remove the obsolete migration**
3. **Board keys:** model, API, board form
4. **Per-board ticket numbers + `key` + by-key lookup**, with keys shown in the UI
5. **Parentless tasks**
6. **Ticket branches:** `branch` column, GitHub client, branch endpoint, branch shown in the UI
7. **`kb` scaffold:** client, server check, board lookup, `board add/list`
8. **`kb` ticket commands:** `add`, `list`, `show`, `move`, `edit`, `delete`, `export`
9. **`kb branch`**
10. **Docs:** README (fixing the out-of-date API section), configuration, `kb` usage
11. **Claude skill** plus the symlink instructions
12. **Release 0.2.0**

## Later
- A "Create branch" button in the web UI
- Recording the PR URL on tickets
- Starting the server automatically with launchd
- A combined `start` command across kb and dev-spaces (once the packages are allowed to depend on each other)
