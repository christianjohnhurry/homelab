# dev-spaces

Sandboxed Docker containers per ticket. Give it a repo and the start of a branch name. It
creates a container, clones the repo into `~/code`, checks out the branch and installs
dependencies. Work there, push, then throw the container away.

Why containers:

- **Agents can run freely:** `claude --dangerously-skip-permissions` can't touch your Mac.
- **Each project gets its own dependencies.**
- **Parallel tickets:** one container each, side by side.
- **A clean Mac:** work lives on the remote. Containers are built, used and destroyed.

## Setup

Requires Docker Desktop (Apple Silicon) and pixi.

```bash
cd ~/code/homelab
pixi run dev-spaces init     # creates ~/.config/dev-spaces/
pixi run dev-spaces build    # builds the base image
```

Then fill in `~/.config/dev-spaces/secrets.env`, with no quotes and no spaces:

| Key | How to get it |
|-----|---------------|
| `GH_TOKEN` | GitHub → Settings → Developer settings → Fine-grained tokens. Choose **Only select repositories** and give **Contents** and **Pull requests** read/write |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` |

`init` never overwrites existing files. `secrets.env` is created with mode 600.

## Usage

```bash
dev-spaces create owner/repo feat/log      # check out the branch starting with feat/log
dev-spaces create owner/repo --new fix/x   # new branch from the default branch
dev-spaces list                            # name, repo, current branch, status, ports
dev-spaces shell <name>                    # zsh in ~/code (starts it if stopped)
dev-spaces ports <name>                    # where the container's ports are on this Mac
dev-spaces stop <name> / start <name>
dev-spaces remove <name> [--force]         # refuses if work would be lost
```

`pixi run dev-spaces ...` works from anywhere in the homelab repo.

### Branch matching
The prefix is matched case-insensitively against the **remote** branches before anything is
created. If nothing matches, you're asked for the prefix again. If several branches match,
you pick one from a numbered list.

The container is named after the branch's last segment (`feat/Login-Flow` becomes
`login-flow`). It can hold several branches, for example when one PR is split into several,
and `list` shows the branch currently checked out.

### Dependencies
After cloning, dev-spaces runs `pixi install` for pixi projects (`pixi.toml`, or `[tool.pixi]`
in `pyproject.toml`) or `uv sync` for projects with `uv.lock`. If the install fails, you get a
warning and the container is kept so you can fix it inside.

A pixi project must list `linux-aarch64` in `platforms` to install inside a container.

### Ports
The ports listed in `config.toml` (default `8000, 8080, 5173, 3000`) are published to random
free ports on `127.0.0.1`. Use `dev-spaces ports <name>` to find them. They can change when a
container restarts.

Servers inside the container must listen on `0.0.0.0`, not `127.0.0.1`, or the
published port can't reach them:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Removing
`remove` refuses while the container has uncommitted changes (including untracked files),
commits that aren't pushed on any branch, or stashes, and lists what would be lost. Push it,
discard it, or use `--force`.

## Configuration

`~/.config/dev-spaces/`:

| File | Purpose |
|------|---------|
| `config.toml` | Git identity for commits, base image name, ports to publish |
| `secrets.env` | Tokens passed into every container |
| `dotfiles/` | Copied into `/home/dev` on create. Starts with `.zshrc` and `.devrc` (aliases, sourced by `.zshrc`). Edit freely |

Set `DEV_SPACES_CONFIG_DIR` to use a different directory.

## Inside a container

- **Base image:** Debian trixie-slim (arm64) with git, gh, zsh, pixi, uv and Claude Code.
- **User:** `dev`, with passwordless `sudo`. The container is the sandbox.
- **Git:** pushes over HTTPS with `GH_TOKEN`. The first `git push` of a new branch sets its upstream.
- **Shell:** the prompt shows the container name and the current branch. `yolo` is an alias for `claude --dangerously-skip-permissions`.

The image is tagged with the dev-spaces version (`dev-spaces-base:<version>`), so run
`dev-spaces build` again after upgrading.

## Development

```bash
pixi run test-dev-spaces              # unit tests (Docker and git are faked)
```

See [PLAN.md](PLAN.md) for the design and roadmap, and [CHANGELOG.md](CHANGELOG.md) for
changes. Versioning follows semver. Releases are tagged `dev-spaces-vX.Y.Z`.
