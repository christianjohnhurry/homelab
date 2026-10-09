# Changelog

All notable changes to Kanana Banana are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions before 0.1.1 predate this changelog.

## [Unreleased]

### Changed
- **BREAKING:** The database now lives at `~/.local/share/kanana-banana/kanana_banana.db` (or under `$XDG_DATA_HOME`) instead of the directory the server was started from, so the board is the same wherever you start it. An old `kanana_banana.db` is not migrated. Point `KANANA_BANANA_DATABASE_URL` at it to keep using it.

### Removed
- The startup migration that assigned pre-board tickets to a default board.

### Added
- Plan for 0.2.0 (`PLAN.md`): the `kb` CLI, board keys, per-board ticket numbers and ticket branches.

## [0.1.1] - 2026-10-10

### Fixed
- Creating or updating boards and tickets failed with "Datetime values must have timezone information" after the SQLModel upgrade. Timestamps are now timezone-aware UTC.
- Every web page failed to render after the Starlette 1.x upgrade. Template responses now use the `TemplateResponse(request, name, context)` signature.
- Deleting a ticket now deletes its children, as documented. Previously they were left behind as orphans.
