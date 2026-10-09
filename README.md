# HomeLab

A repository of utilities to make setting up personal coding projects easier.

## Packages

### 🍌 Kanana Banana 🍌 

A local kanban board for tracking projects, tasks, and subtasks.

```bash
cd ~/code/homelab
pixi run kanana-banana
```

Then open http://127.0.0.1:8000/

See [packages/kanana-banana/README.md](packages/kanana-banana/README.md) for details.

### 🐳 dev-spaces

Sandboxed Docker containers per ticket: clone a repo, check out a branch by prefix,
install dependencies, work (or let an agent work), push, destroy.

```bash
pixi run dev-spaces init && pixi run dev-spaces build
pixi run dev-spaces create owner/repo feat/my-bra
```

See [packages/dev-spaces/README.md](packages/dev-spaces/README.md) for details.

## Development

This project uses [pixi](https://pixi.sh) for dependency management.

```bash
# Install dependencies
pixi install

# Run the kanban board
pixi run kanana-banana
```