# Changelog

All notable changes to Kanana Banana are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions before 0.1.1 predate this changelog.

## [Unreleased]

### Changed
- **BREAKING:** Tickets can't move between boards, because their keys embed the board key. Re-parenting within a board still works.
- Markdown exports refer to tickets by key (`HML-42`) instead of `#id`.
- **BREAKING:** The database now lives at `~/.local/share/kanana-banana/kanana_banana.db` (or under `$XDG_DATA_HOME`) instead of the directory the server was started from, so the board is the same wherever you start it. An old `kanana_banana.db` is not migrated. Point `KANANA_BANANA_DATABASE_URL` at it to keep using it.

### Removed
- The startup migration that assigned pre-board tickets to a default board.

### Added
- Board keys: every board has a unique key of letters (any length, stored uppercase, e.g. `HML`) that prefixes its ticket keys and branch names. The key is required when creating a board and can't be changed afterwards. `GET /api/v1/boards?key=HML` finds a board by key. The board form shows the server's error when a key is invalid or taken.
- Per-board ticket numbers: every ticket gets the next number on its board and a key such as `HML-42`, returned as `number` and `key`. Numbers are never reused.
- `GET /api/v1/tickets/by-key/{key}` looks up a ticket by key, case-insensitively.
- Ticket keys are shown on cards and in detail views.
- Tasks without a parent project, for miscellaneous work such as fixes, as the README's philosophy describes. They need a `board_id`, can have subtasks, and appear on the kanban columns. The tree view still shows only projects.
- Ticket branches: `POST /api/v1/tickets/{id}/branch` creates the ticket's branch on GitHub, named `{key}-{number}-{slug}` in lowercase (e.g. `hml-42-add-login-flow`), and records it on the ticket as `branch`. Tasks branch from the repo's default branch. Subtasks are stacked on their task's branch, which must exist first. Projects never get branches. A branch is never renamed when its ticket is.
- The GitHub token is read from `~/.config/kanana-banana/secrets.env` (`GH_TOKEN=`, needs Contents: read/write). `KANANA_BANANA_CONFIG_DIR` overrides the location.
- Ticket detail views show the branch.
- `kb`, a command-line client for the REST API (`pixi run kb`), starting with `kb board add KEY NAME [--repo URL]` and `kb board list [--json]`. It reaches the server at `KB_URL` (default `http://127.0.0.1:8000`) and says how to start it if it isn't running.
- `kb` ticket commands: `add` (the type follows from `--parent`, or `--project`), `list` (`--status`, `--type`, `--tree`, `--json`), `show` (`--json`), `move`, `edit`, `delete` (confirms, listing what's underneath, unless `--yes`), and `export`. Tickets are referred to by key in any letter case, and the board comes from `--board` or the current git repo.
- `GET /api/v1/tickets` accepts `board_id` and returns tickets in board and number order.
- `kb branch KEY` creates the ticket's branch on GitHub and prints the `dev-spaces create` command to start work on it. For a subtask, it also says which branch the PR should target.
- Plan for 0.2.0 (`PLAN.md`): the `kb` CLI, board keys, per-board ticket numbers and ticket branches.

## [0.1.1] - 2026-10-10

### Fixed
- Creating or updating boards and tickets failed with "Datetime values must have timezone information" after the SQLModel upgrade. Timestamps are now timezone-aware UTC.
- Every web page failed to render after the Starlette 1.x upgrade. Template responses now use the `TemplateResponse(request, name, context)` signature.
- Deleting a ticket now deletes its children, as documented. Previously they were left behind as orphans.
