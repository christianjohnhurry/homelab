# dev-spaces — Plan

A CLI that creates a sandboxed Docker container per ticket: it clones a repo into
`~/code`, checks out a branch, and installs dependencies. Containers are disposable,
so nothing lives on the Mac for long.

## Goals

- **Isolation for agents:** Claude Code can run freely inside a container without risking the Mac.
- **Separate dependencies:** every project gets its own environment.
- **Parallel branches:** one container per ticket, so several can run side by side.
- **A clean Mac:** build, use, destroy. Work lives on the remote, not locally.

One container per **ticket**. A ticket usually means one branch, but a container can hold
several branches, for example when one PR is split into several.

## Tech Stack

- **Python 3.12+**, **Typer** for the CLI
- The `docker` CLI called through `subprocess` (no Docker SDK), so every step is a command you could type yourself
- **Docker Desktop** on macOS (Apple Silicon)
- A second package in the homelab pixi workspace, alongside `kanana-banana`

## Directory Structure

```
packages/dev-spaces/
├── PLAN.md
├── CHANGELOG.md
├── README.md
├── pyproject.toml
└── src/dev_spaces/
    ├── __init__.py       # __version__
    ├── cli.py            # Typer app + main()
    ├── config.py         # Loads ~/.config/dev-spaces/config.toml
    ├── docker.py         # Thin wrappers over the docker CLI
    ├── branches.py       # Remote branch lookup + prefix matching
    ├── deps.py           # Dependency auto-detection
    └── image/
        └── Dockerfile    # Base image
```

User config, outside the repo:

```
~/.config/dev-spaces/     # chmod 700
├── config.toml           # git name/email, image tag, ports
├── secrets.env           # GH_TOKEN, CLAUDE_CODE_OAUTH_TOKEN (chmod 600, never committed)
└── dotfiles/             # .zshrc, .devrc: copied into every container
```

## Commands

| Command | Description |
|---------|-------------|
| `dev-spaces init` | Creates `~/.config/dev-spaces/` with a starter `config.toml`, `secrets.env` (600) and `dotfiles/`. Never overwrites existing files |
| `dev-spaces build` | Builds the base image |
| `dev-spaces create <owner/repo> <prefix>` | Matches the branch, then starts a container, clones, checks out and installs dependencies |
| `dev-spaces create <owner/repo> --new <name>` | Same, but creates a new branch from the default branch |
| `dev-spaces list` | Shows each container's name, repo, branch, status and ports |
| `dev-spaces shell <name>` | Opens zsh in `~/code` inside the container |
| `dev-spaces ports <name>` | Shows the container's port mappings |
| `dev-spaces start <name>` / `stop <name>` | Starts or stops a container |
| `dev-spaces remove <name> [--force]` | Deletes a container, but refuses if work would be lost |
| `dev-spaces --version` | Prints the version |

## Behaviour

### Branch matching (`create <repo> <prefix>`)
Matching happens **before** anything is created, so a typo never leaves a half-built container behind.

1. Read the remote branches with `git ls-remote --heads`, authenticated with `GH_TOKEN`.
2. Match case-insensitively on the prefix:
   - **No match:** print an error and ask for the prefix again.
   - **Several matches:** list them numbered and let the user pick one.
   - **One match:** carry on.

`--new <name>` skips matching, fails if `<name>` already exists on the remote, and branches
from the remote's default branch.

### Container identity
- Named after the starting branch: `feat/login-flow` becomes `login-flow`. The name stays the same as more branches are added inside the container.
- Docker labels (`dev-spaces=1`, `dev-spaces.repo`, `dev-spaces.branch`) record what each container holds. `list` filters on them, so the tool needs no database.
- If the container already exists, `create` fails and suggests `shell`.

### Base image
- Debian slim (arm64), with git, gh, zsh, curl, pixi, uv and Claude Code.
- Runs as a non-root user `dev`, with code in `/home/dev/code`.
- Kept alive with `sleep infinity`. Commands run through `docker exec`.

### Credentials
- `docker run --env-file ~/.config/dev-spaces/secrets.env` passes in `GH_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN`.
- `gh auth setup-git` inside the container makes `git clone`/`push` over HTTPS use the token.
- `GH_TOKEN` is a fine-grained PAT: selected repos only, with Contents and Pull requests set to read/write. It has no Administration permission.

### Dotfiles
On create, files in `~/.config/dev-spaces/dotfiles/` (`.zshrc`, `.devrc`) are copied into
`/home/dev`. They are curated for the container, not copied from the Mac's own dotfiles.

### Dependencies (auto-detected after clone)
| Found | Runs |
|-------|------|
| `pixi.toml`, or `[tool.pixi]` in `pyproject.toml` | `pixi install` |
| `uv.lock` | `uv sync` |
| neither | prints a warning, skips |

Add more installers only when a project needs them.

### Ports
- Each container port in `config.toml` (default `8000, 8080, 5173, 3000`) is published as `-p 127.0.0.1::<port>`, so Docker picks a free Mac port for each and only the Mac can reach them.
- `list` and `ports` show the mappings. Host ports can change when a container restarts.
- The ports are fixed when the container is created, because Docker can't add ports to an existing container.
- **Gotcha:** apps inside the container must listen on `0.0.0.0`, not `127.0.0.1`.

### `remove` safety check
Refuses if any branch in `~/code` has:
- uncommitted changes (`git status --porcelain`), or
- commits that haven't been pushed (`git log --branches --not --remotes`).

Stashed changes count too. `--force` overrides it. For a stopped container, `remove` starts it briefly to run the check.
Named `remove` rather than `rm` so it is never typed by reflex.

## Requirements for Repos

- **Pixi platforms:** a pixi repo must list `linux-aarch64` in `platforms`, or `pixi install`
  fails inside the container. Homelab lists `osx-arm64` and `linux-aarch64`.

## Versioning

dev-spaces follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

- **Single source of truth:** `version` in `packages/dev-spaces/pyproject.toml`. `dev_spaces.__version__` reads it from package metadata, and `dev-spaces --version` prints it.
- **While on `0.x`:** the CLI is not stable.
  - **MINOR** for new features *or* breaking changes (commands, flags, config format, labels).
  - **PATCH** for bug fixes and internal changes.
- **`1.0.0`:** once the command set and `config.toml` format are settled and used daily.
- **Base image:** tagged with the dev-spaces version (`dev-spaces-base:<version>`), so a container's labels show which image built it.
- **Release steps:**
  1. Bump `version` in `pyproject.toml`.
  2. Move `[Unreleased]` entries in `CHANGELOG.md` under the new version and date.
  3. Commit as `chore(dev-spaces): release vX.Y.Z`.
  4. Tag `dev-spaces-vX.Y.Z`. The tag is prefixed because the homelab repo holds several packages.

## Changelog

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

- Every user-visible change adds a line under `## [Unreleased]` **in the same commit**.
- Sections: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.
- Breaking changes are prefixed with **BREAKING:**.
- Internal refactors with no user-visible effect don't need an entry.

## Roadmap

### v0.1.0: MVP
Build in this order. Each step is one commit with its changelog entry.

1. **Scaffold:** package, `pyproject.toml`, workspace registration, `pixi run dev-spaces`, `--version`
2. **`init` + config:** config dir, starter `config.toml`, `secrets.env` (600), `dotfiles/`
3. **Base image + `build`:** Dockerfile, image tagged with the version
4. **Branch matching:** `ls-remote`, prefix match, re-prompt, numbered pick
5. **`create`:** run, labels, ports, secrets, dotfiles, clone, checkout / `--new`, dependency install
6. **`list`, `shell`, `ports`, `start`, `stop`**
7. **`remove`** with the safety check
8. **README** and release `0.1.0`

### Later
- Kanana Banana integration (create branches and containers from tickets)
- Container naming by ticket ID
- Per-project images / `.devbox/setup.sh` hook
- More dependency installers (npm, etc.) and languages
- Editor attachment (VS Code / Cursor)
- Traefik reverse proxy for `<name>.localhost` hostnames
- `prune` for stopped containers
