---
name: ticket-workflow
description: Plan and work on code using Kanana Banana tickets (kb) and dev-spaces containers. Use when the user wants to plan a feature into tickets, start or pick up a ticket (HML-42 style keys), create a ticket's branch, spin up a dev-space for it, split a PR into subtasks, or tidy up after a ticket is merged. Also use when the user mentions kb, kanana banana, dev-spaces, or a board key.
---

# Ticket workflow: Kanana Banana + dev-spaces

The user tracks hobby-project work on a local Kanana Banana board and does the work in
disposable dev-spaces Docker containers, one per ticket. Two independent tools:

- **`kb`**: the board's CLI. Tickets have keys like `HML-42` (board key + number).
- **`dev-spaces`**: creates a container, clones a repo, checks out a branch, installs dependencies.

## Running the commands

The user's shell aliases aren't available to you, and shell state doesn't persist
between your commands. Start **every** command that uses these tools by defining them:

```bash
kb() { ~/.pixi/bin/pixi run --manifest-path ~/code/homelab/pyproject.toml kb "$@"; }
dev-spaces() { PATH="$HOME/.docker/bin:$PATH" ~/.pixi/bin/pixi run --manifest-path ~/code/homelab/pyproject.toml dev-spaces "$@"; }
kb list --tree
```

The examples below assume these functions are defined.

- If `kb` says Kanana Banana isn't running, ask the user to start `pixi run kanana-banana`.
  Or, with their OK, start it yourself as a background process from `~/code/homelab`.
- Use `--json` on `kb list` and `kb show` when you need to read tickets. Use the table
  output when showing tickets to the user.
- `kb list` and `kb add` without a parent pick the board from the current repo's git
  origin. Pass `--board KEY` when you're not inside the board's repo.

## The philosophy (follow it when planning)

- One board per repository.
- A big feature is a **project**.
- Each piece of work needed for the project is a **task**, and **a task is one pull
  request**: sized so the review stays manageable.
- If a task's PR would be too big, split it into **subtasks**, each its own PR, **stacked**
  on the task's branch.
- Miscellaneous work, such as fixes, is a **task with no parent project**.
- Every task gets a code review.

## Workflows

### Plan a feature into tickets
1. Read enough of the codebase to know what the feature touches.
2. Propose the breakdown to the user first: the project, its tasks (one PR each), and
   any subtasks, with a one-line description each. **Wait for their OK before creating
   tickets.**
3. Create them:
   ```bash
   kb add "Feature name" --project -d "What and why"   # -> HML-10
   kb add "First PR-sized piece" --parent HML-10 -d "..." # -> task
   kb add "Part of a big task" --parent HML-11            # -> subtask
   ```
   `kb add` works out the type from the parent. Report the keys you created.

### Start a ticket
1. `kb show HML-42 --json`: read the description, parent and existing branch.
2. If it has no branch yet: `kb branch HML-42`. This creates `hml-42-<slug>` on GitHub.
   - A **subtask** needs its task's branch first. If `kb` refuses, branch the task, then the subtask.
   - **Projects** never get branches. Work happens on their tasks.
3. Create the container, using the command `kb branch` printed:
   ```bash
   dev-spaces create owner/repo hml-42-add-login-flow
   ```
4. Tell the user to open it with `dev-spaces shell <name>`, where `yolo` runs Claude
   inside with permissions skipped. `dev-spaces shell` is interactive, so you can't run it.
   For one-off checks, use `docker exec <name> git -C /home/dev/code status`.
5. **Suggest** moving the ticket to in-progress. Only move it if they say so:
   `kb move HML-42 in-progress`.

### Split a task into stacked PRs
- Create subtasks under the task (`kb add "..." --parent HML-42`), then `kb branch` each.
  Each subtask branches from the task's branch.
- Each subtask's PR targets **the task's branch**, not main. The task's PR targets main.
- One container can hold all of a task's branches: `git switch` between them inside it.

### Finish a ticket
- After the PR is merged, **suggest** `kb move HML-42 done`. Merging never moves tickets
  automatically, and you only move statuses when the user asks.
- Clean up the container: `dev-spaces remove <name>`. It refuses while there's uncommitted,
  unpushed or stashed work, and lists what it found. Report that to the user rather than
  reaching for `--force`. Only use `--force` when the user explicitly says to discard
  the work.

## Rules
- **Never move a ticket's status unless the user asks.** Suggest moves instead.
- **Never `kb delete` or `dev-spaces remove --force` without the user's explicit OK.**
- Ticket names become branch slugs, so keep them short and descriptive. Renaming a
  ticket later doesn't rename its branch.
- Tickets can't move between boards.
