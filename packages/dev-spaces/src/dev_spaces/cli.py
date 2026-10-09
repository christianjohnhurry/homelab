"""Command-line interface and entry point."""

from importlib.resources import files
from typing import NoReturn

import click
import typer

from dev_spaces import __version__, branches, config, deps, docker

IMAGE_DIR = files("dev_spaces") / "image"
CODE_DIR = deps.CODE_DIR
LABEL = "dev-spaces"

app = typer.Typer(
    help="Sandboxed Docker containers per ticket.",
    no_args_is_help=True,
)


def _fail(message: str) -> NoReturn:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _load_config() -> config.Config:
    try:
        return config.load()
    except config.ConfigError as e:
        _fail(str(e))


def image_ref(cfg: config.Config) -> str:
    """The base image is tagged with the dev-spaces version."""
    return f"{cfg.image_name}:{__version__}"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dev-spaces {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Sandboxed Docker containers per ticket."""


@app.command()
def init() -> None:
    """Create ~/.config/dev-spaces with starter config, secrets and dotfiles."""
    for path, created in config.init():
        label = "created" if created else "exists "
        typer.echo(f"{label}  {path}")
    if warning := config.check_secrets_permissions():
        typer.secho(f"warning: {warning}", fg=typer.colors.YELLOW, err=True)
    typer.echo(f"\nNext: add your tokens to {config.secrets_path()}")


@app.command()
def build() -> None:
    """Build the base image, tagged with the dev-spaces version."""
    cfg = _load_config()
    ref = image_ref(cfg)
    try:
        docker.ping()
    except docker.DockerError as e:
        _fail(str(e))
    typer.echo(f"Building {ref}")
    code = docker.stream(
        "build",
        "--tag", ref,
        "--build-arg", f"DEV_SPACES_VERSION={__version__}",
        str(IMAGE_DIR),
    )
    if code != 0:
        _fail("image build failed")
    typer.secho(f"Built {ref}", fg=typer.colors.GREEN)


def _resolve_branch(available: list[str], prefix: str) -> str:
    """Prefix-match a branch, asking again on no match and choosing on several."""
    while True:
        matches = branches.match(available, prefix)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            typer.secho(f"No remote branch starts with {prefix!r}.", fg=typer.colors.RED, err=True)
            prefix = typer.prompt("Branch prefix")
            continue
        typer.echo(f"Several branches start with {prefix!r}:")
        for i, branch in enumerate(matches, 1):
            typer.echo(f"  {i}. {branch}")
        choice = typer.prompt("Pick one", type=click.IntRange(1, len(matches)))
        return matches[choice - 1]


def _exec(container: str, *cmd: str, user: str | None = None) -> None:
    """Run a command in the container, streaming output; raise on failure."""
    user_args = ["--user", user] if user else []
    if docker.stream("exec", *user_args, "--workdir", CODE_DIR, container, *cmd) != 0:
        raise docker.DockerError(f"`{' '.join(cmd)}` failed in {container}")


def _container_exists(name: str) -> bool:
    return docker.run("container", "inspect", name, check=False).returncode == 0


def _setup(name: str, repo: str, branch: str, base: str | None, cfg: config.Config) -> None:
    """Credentials, identity, dotfiles, clone and checkout inside a new container."""
    dotfiles = config.dotfiles_dir()
    if dotfiles.is_dir() and any(dotfiles.iterdir()):
        docker.run("cp", f"{dotfiles}/.", f"{name}:/home/dev/")
        copied = [f"/home/dev/{p.name}" for p in dotfiles.iterdir()]
        docker.run("exec", "--user", "root", name, "chown", "-R", "dev:dev", *copied)

    docker.run("exec", name, "gh", "auth", "setup-git")
    docker.run("exec", name, "git", "config", "--global", "push.autoSetupRemote", "true")
    if cfg.git_name:
        docker.run("exec", name, "git", "config", "--global", "user.name", cfg.git_name)
    if cfg.git_email:
        docker.run("exec", name, "git", "config", "--global", "user.email", cfg.git_email)

    typer.echo(f"Cloning {repo}")
    _exec(name, "git", "clone", branches.clone_url(repo), CODE_DIR)
    if base is None:
        _exec(name, "git", "checkout", branch)
    else:
        # No upstream yet: push.autoSetupRemote creates it on the first push
        _exec(name, "git", "switch", "--no-track", "--create", branch, f"origin/{base}")


def _install_deps(name: str) -> None:
    command = deps.detect(name)
    if command is None:
        typer.secho("warning: no pixi or uv project found; skipping dependency install",
                    fg=typer.colors.YELLOW, err=True)
        return
    typer.echo(f"Installing dependencies: {' '.join(command)}")
    try:
        _exec(name, *command)
    except docker.DockerError as e:
        # Keep the container: the code is there and the install can be fixed inside it
        typer.secho(f"warning: {e}", fg=typer.colors.YELLOW, err=True)


@app.command()
def create(
    repo: str = typer.Argument(..., help="GitHub repo: owner/repo or URL."),
    prefix: str = typer.Argument(None, help="Prefix of an existing remote branch (case-insensitive)."),
    new: str = typer.Option(None, "--new", help="Create a new branch from the default branch instead."),
) -> None:
    """Create a container, clone REPO and check out a branch."""
    if (prefix is None) == (new is None):
        _fail("give either a branch PREFIX or --new NAME")
    cfg = _load_config()
    if warning := config.check_secrets_permissions():
        typer.secho(f"warning: {warning}", fg=typer.colors.YELLOW, err=True)
    secrets = config.read_secrets()
    if not secrets.get("CLAUDE_CODE_OAUTH_TOKEN"):
        typer.secho("warning: CLAUDE_CODE_OAUTH_TOKEN is empty; run `claude setup-token`",
                    fg=typer.colors.YELLOW, err=True)
    ref = image_ref(cfg)

    try:
        token = config.github_token()
        docker.ping()
        if docker.run("image", "inspect", ref, check=False).returncode != 0:
            _fail(f"image {ref} not found. Run `dev-spaces build` first.")

        # Resolve everything remote before creating anything local
        repo = branches.parse_repo(repo)
        available = branches.remote_branches(repo, token)
        if new is not None:
            if new in available:
                _fail(f"branch {new!r} already exists on {repo}. Drop --new to use it.")
            branch, base = new, branches.default_branch(repo, token)
        else:
            branch, base = _resolve_branch(available, prefix), None

        name = branches.container_name(branch)
        if _container_exists(name):
            _fail(f"container {name!r} already exists. Use `dev-spaces shell {name}`.")
    except (config.ConfigError, branches.BranchError, docker.DockerError) as e:
        _fail(str(e))

    typer.echo(f"Creating {name} for {repo} @ {branch}")
    port_args = [arg for port in cfg.ports for arg in ("--publish", f"127.0.0.1::{port}")]
    try:
        docker.run(
            "run", "--detach",
            "--name", name,
            "--hostname", name,
            "--label", f"{LABEL}=1",
            "--label", f"{LABEL}.repo={repo}",
            "--label", f"{LABEL}.branch={branch}",
            "--label", f"{LABEL}.version={__version__}",
            "--env-file", str(config.secrets_path()),
            "--env", f"DEV_SPACE={name}",
            *port_args,
            ref,
        )
    except docker.DockerError as e:
        _fail(str(e))

    try:
        _setup(name, repo, branch, base, cfg)
    except docker.DockerError as e:
        # Don't leave a half-built container behind
        docker.run("rm", "--force", name, check=False)
        _fail(f"{e}. Removed {name}.")

    _install_deps(name)
    typer.secho(f"\nReady: {name}", fg=typer.colors.GREEN)
    typer.echo(f"  dev-spaces shell {name}")


def main() -> None:
    """Entry point for the `dev-spaces` script."""
    app()
