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
- Plan for 0.2.0 (`PLAN.md`): the `kb` CLI, board keys, per-board ticket numbers and ticket branches.

## [0.1.1] - 2026-10-10

### Fixed
- Creating or updating boards and tickets failed with "Datetime values must have timezone information" after the SQLModel upgrade. Timestamps are now timezone-aware UTC.
- Every web page failed to render after the Starlette 1.x upgrade. Template responses now use the `TemplateResponse(request, name, context)` signature.
- Deleting a ticket now deletes its children, as documented. Previously they were left behind as orphans.
