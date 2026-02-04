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

## Development

This project uses [pixi](https://pixi.sh) for dependency management.

```bash
# Install dependencies
pixi install

# Run the kanban board
pixi run kanana-banana
```