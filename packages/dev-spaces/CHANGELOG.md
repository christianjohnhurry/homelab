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
- `dev-spaces create <owner/repo> <prefix>` matches a remote branch by case-insensitive prefix. It asks again when nothing matches and lets you pick when several do, all before anything is created. It then starts a labelled container with secrets, dotfiles and git identity, clones into `~/code`, checks out the branch and installs dependencies (`pixi install` or `uv sync`).
- `dev-spaces create <owner/repo> --new <name>` creates a new branch from the remote's default branch. The first `git push` sets its upstream.
- Container ports from `config.toml` are published to random free ports on `127.0.0.1`.
- A container whose clone or checkout fails is removed. A failed dependency install only warns and keeps the container.
- `dev-spaces list` shows every dev-spaces container with its repo, current branch, status and port mappings.
- `dev-spaces shell <name>` opens zsh in `~/code`, starting the container first if it's stopped.
- `dev-spaces ports <name>` shows each published port as a `localhost` URL.
- `dev-spaces start <name>` and `dev-spaces stop <name>`. Containers run with `--init`, so stopping is instant.
- `dev-spaces remove <name>` refuses while the container has uncommitted changes, unpushed commits or stashes, and lists them. `--force` overrides it. A stopped container is started briefly for the check and stopped again.
