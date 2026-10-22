# asdlc

An agentic SDLC as a Claude Code plugin, built on Anthropic's AI-native SDLC playbook. It builds itself: every change starts as an intent in `intent/` and runs through the plugin's own loop.

## Install

uv is the one prerequisite: the plugin's hooks and checks are Python 3.15 scripts run through it, and uv fetches 3.15 on first use. Install it from <https://docs.astral.sh/uv/>.

Then, in Claude Code:

```
/plugin install asdlc --marketplace bruk-io/asdlc
```

## What version 0 does

| Play | What you get |
|---|---|
| Capture intent | `/asdlc:intent` and the `capture-intent` skill: an interview, an intent in the requester's words, a pull request whose merge accepts it |
| Plan mode | `/asdlc:plan` and the `plan-change` skill: files, order, risks and proof, citing the spec's requirements, approved by merge |
| Skills | The `write-policy-skill` skill and a template that names each policy's owner, source and enforcement |
| Feedback loop | One check command per repository, and a hook that stops a bug fix on a `fix/` branch from changing an existing test, through the file tools or plain shell writes |
| Hooks | Every hook decision logged to `.asdlc/hooks.jsonl` |
| CLAUDE.md | A check that keeps it to at most 60 lines |

Templates for intents, specs and plans are in `templates/`, and `scripts/artefacts.py` checks that each artefact has what the next stage needs.

## Shared board

For a team whose engineers each run several agents. Work is tracked on a [Backlog.md](https://github.com/MrLesk/Backlog.md) board in its own repository, with no code in it. Every board change is committed and pushed straight to that repository's `main` with git hooks off, an agent claims a task before it starts, and each claimed task gets its own worktree in the code repository. `scripts/asdlc` does all of it; link it onto your `PATH` as `asdlc`. It needs Backlog.md 1.55.1 or later (`npm i -g backlog.md@1.55.2`), because older versions drop frontmatter keys they don't know when a task is edited.

Set up once:

```sh
asdlc init-board ~/src/team-board            # git init, backlog init, this board's statuses, types and size labels
git -C ~/src/team-board remote add origin <the board repository's url>
git -C ~/src/team-board push -u origin main
```

Each person clones the board, then points each code repository at their clone: `git config asdlc.board ~/src/team-board`. `--board <path>` or `ASDLC_BOARD` override it.

| Command | What it does |
|---|---|
| `asdlc board <backlog arguments>` | Runs `backlog` on the board and pushes what it committed. If someone pushed first it rebases and retries; if the rebase conflicts, your change is dropped and the message names the task file, so run it again on the new state. |
| `asdlc next --as <agent>` | Claims the highest-priority unassigned To Do leaf task that can start, and prints its worktree. Prints `no work available` when there is none. |
| `asdlc claim <id> --as <agent>` | Claims one task: In Progress, assigned to `@<agent>`, pushed. Of two agents claiming at once, git accepts one push; the other is told "Another agent claimed <id> first" and its claim is undone. |
| `asdlc release <id> --as <agent>` | Puts your claimed task back to To Do with no assignee. Its worktree is left alone. |
| `asdlc route <id>` | The model and effort for a task, as JSON: intents, spikes and parents get opus/high, `size-1` haiku (its plan needs numbered steps), `size-2` to `size-5` sonnet/medium. `size-8` is refused until it is split, and a task needs exactly one size label. |

A claimed task's worktree is `<repo>.worktrees/<id>` beside the repository, on a branch named from the task, started from `origin`'s default branch and tracking nothing. Its `.asdlc-task` marker says which task it holds.

The `guard_board` hook refuses, with the reason:

- Editing a board's `backlog/` files by hand, so every change is committed and pushed where other agents see it.
- `backlog` or `asdlc board` setting To Do or Done, promoting a draft, or creating a task without `--draft` (it would start as accepted To Do work): accepting and closing work are a person's decisions. `asdlc release` is the way to hand a task back.
- Editing a code repository that has `asdlc.board` set outside a claimed task's worktree, so no two agents change the same work.
- `git push` to that repository's default branch, so changes arrive through review. Pushes to the board are allowed.

Stale claims are released by hand for now: `asdlc release`, run as the agent that holds the task.

## Review

Every pull request to this repository is reviewed by Claude in CI, using Anthropic's `code-review` plugin under the rules in [`REVIEW.md`](REVIEW.md), both read from `main`. Findings arrive as inline comments and never approve or block; the cost of each review is in the run's job summary.

## What it does not do yet

- No eval suite, so changes merge on review alone until the eval gate lands.
- The requirements-and-design play, approval gates, CI/CD and closing the loop on metrics are specified in `spec/agentic-sdlc-plugin.md` and come in later versions.

## How it is built

- [The intent](intent/agentic-sdlc-plugin.md)
- [The spec](spec/agentic-sdlc-plugin.md) and [its evals](spec/agentic-sdlc-plugin-evals.md)
- [The plan for version 0](plan/v0-bootstrap.md)
