# Changelog

All notable changes to Kanana Banana are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions before 0.2.0 predate this changelog.

## [Unreleased]

### Fixed
- Creating or updating boards and tickets failed with "Datetime values must have timezone information" after the SQLModel upgrade. Timestamps are now timezone-aware UTC.
- Every web page failed to render after the Starlette 1.x upgrade. Template responses now use the `TemplateResponse(request, name, context)` signature.

### Added
- Plan for 0.2.0 (`PLAN.md`): the `kb` CLI, board keys, per-board ticket numbers and ticket branches.
