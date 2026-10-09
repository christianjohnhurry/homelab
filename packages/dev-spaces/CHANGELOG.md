# Changelog

All notable changes to dev-spaces are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project plan (`PLAN.md`) covering commands, behaviour, versioning and roadmap.
- `dev-spaces` CLI with `--version`, runnable via `pixi run dev-spaces`.
- `dev-spaces init` creates `~/.config/dev-spaces/` with `config.toml` (git identity prefilled from global git config), `secrets.env` (mode 600) and starter `.zshrc`/`.devrc` dotfiles. Never overwrites existing files, and warns if `secrets.env` is readable by others.
- `dev-spaces build` builds the `dev-spaces-base:<version>` image: Debian trixie-slim (arm64) with git, gh, zsh, pixi, uv and Claude Code, running as user `dev` with passwordless sudo.
