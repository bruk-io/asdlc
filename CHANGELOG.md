# Changelog

## 0.1.0 - 2026-10-22

The team pilot: several engineers, each with one orchestrator session and its workers, sharing one board. [docs/guide.md](docs/guide.md) is the page for a developer joining it.

### The shared board (#16)

- `scripts/asdlc`: a Backlog.md board in its own repository, every change committed and pushed straight to its `main` with git hooks off, retried when someone pushed first.
- Atomic claims: a claim is a pushed commit, so of two agents claiming one task exactly one wins and the other is told.
- A worktree per claimed task, beside the code repository, on a branch named from the task.
- Routing in one table: intents, spikes and parents get opus/high, `size-1` haiku with numbered steps, `size-2` to `size-5` sonnet/medium; `size-8` is refused until split.
- The board guard: no hand edits of `backlog/`, no To Do or Done, no promotion, no task created without `--draft`, no code edited outside a claimed worktree, no push to a code repository's default branch.

### The tasks repository as a marketplace (#17)

- `asdlc init-board` makes the tasks repository a Claude Code plugin marketplace with a `team` plugin (testing skill and rules, the lead's contract), `asdlc.toml` and `devs/`.
- The `load_rules` hook delivers the team's rules and each code repository's own rules, scoped by path and layer, once per session and subagent, capped at 10,000 characters.
- `docs/repo-plugins.md`: the format of a per-repository plugin.

### Orchestration (#18)

- Engineers (`git config asdlc.engineer`), workers (`kyle.w1`) and reservations in the assignee list.
- `asdlc next` ranks work reserved for you, then your preferred repositories, then priority, spreads workers over equal work, and stops at your `workers` cap.
- `whoami`, `register`, `repos`, `lead`, `lead-of`, `heartbeat`, `reap`, `accept`, `mine` and `record-check`.
- One lead per large piece of work, claimed like a task; the `orchestrate` and `lead` skills and the `worker` agent.
- `asdlc accept` promotes an intent and its draft children together; the guard refuses it from agents.

### Onboarding a repository (#19)

- `scripts/asdlc-plugin`: `status`, `scaffold`, `verify-command`, `check` and `publish` a repository's plugin, in a worktree of the tasks repository so claims keep working.
- Commands are dated `verified` only by running them on a clean checkout of the default branch.
- The `onboard-repo` skill reads the repository and writes its commands, layers and rules.

### Cross-machine review (#20)

- `asdlc review-next` and `review-done`: any other engineer's orchestrator claims a finished task's review atomically; changes go back to the worker that built it, a clean review waits for a person to merge.
- The author's own machine may review it after `review_fallback_after`, marked as a same-machine review.
- The `reviewer` agent: read-only, from a fresh context, comments on the pull request and never approves.

### Pilot readiness (this release)

- One board lookup order everywhere: `--board`, then `ASDLC_BOARD`, then `git config asdlc.board`.
- The guard refuses agents approving, requesting changes on or merging a pull request, through `gh pr` or `gh api`.
- The orchestrator decides onboarding with `asdlc-plugin status --json`; reviewers review in a worktree of the registered repository, so its rules reach them.
- `init-board` writes the `changes-requested` and `review-passed` labels.
- `asdlc doctor`: is this machine ready, with what to do about each problem.
- `asdlc stats`: claims, review times, round trips, same-machine reviews, lost races, onboardings and skipped plan approvals, from the board's history and a per-machine event log of claim attempts.
- `docs/guide.md` for developers joining the pilot.
- This repository's own loop is lighter: each change carries a plan, approved in the session before building, in the same pull request.

### Fixes from the independent review (this release)

An independent review of the combined pilot ran each claim below as an experiment; each fix has a regression test that reproduces it.

- A worker's state changes go through commands that check it still holds the task: `asdlc finish <id> --as <worker> [--pr <url>] --notes ...` hands a task to review (and back, after changes), and `asdlc record-check <id> --as <worker> -- <command>` runs only in the task's worktree and records the worktree, branch and commit. The guard refuses agents setting In Progress or In Review, changing assignees, archiving or demoting tasks, or touching the review labels through `asdlc board` or `backlog`, so a reaped worker can't finish a task someone else now holds.
- A claim records the task's branch (`asdlc_branch`); every later claim resumes it, from `origin/<branch>` once it was pushed. A reaped task that a review sent back stays reserved for its author's engineer. Workers never force-push, and the guard refuses force pushes to code repositories.
- An interrupted asdlc command drops its unpushed board change (at once on Ctrl-C or SIGTERM, on the next command after a kill) and never pushes it later; commits asdlc didn't make are refused, not pushed. Every board commit asdlc makes carries an `Asdlc-Transaction` trailer. The lock wait is 45 seconds.
- `asdlc approve <id>...`, a person's command the guard refuses from agents, records plan approval; `record-check` and `finish` refuse size 2 and up without it.
- `asdlc accept` promotes the whole draft subtree, at any depth, comments the old and new ids on the intent and marks each task with `asdlc_accepted_from`; heartbeats, releases and `lead-of` find a task by its old draft id, and `lead` refuses an old draft id unless `--new`.
- A claim is its first heartbeat; heartbeat on a task that left In Progress is a quiet no-op. The orchestrator heartbeats what its agents are working on at the top of every round, never from a detached loop, and adopts its engineer's claims on start.
- With `review: true`, `asdlc next` leaves a slot for a waiting review, and the orchestrator reviews before it picks; `mine` reports the reviews waiting.
- Reviewers judge a team's code by the team's policy, `plugins/team/review.md` in the tasks repository (plus a repository plugin's own `review.md`), named in the review claim's `policies`; never by asdlc's own `REVIEW.md`.
- No permission prompts in normal work: `asdlc permissions` prints the Claude Code allow rules this machine needs (asdlc's commands, backlog's reads, git, `gh pr create`/`view`/`comment`, `uv run`, each registered repository's verified commands, edits in the worktree folders), and `asdlc permissions --write`, a person's command, merges them into `~/.claude/settings.json` after a backup. `asdlc doctor` warns when they are missing. The guard only denies or allows, never asks.
- asdlc works through the `backlog` CLI only: `asdlc doctor` warns when Backlog.md's MCP server is configured, and the guide says not to add it.
- The guard reads `~`, `git -C`, loops and conditionals, `bash -lc` and `xargs`; a claim under a name already holding the task is refused; `init-board` ignores `.asdlc/` in the tasks repository.
- Re-run `asdlc init-board` on an existing tasks repository to add `plugins/team/review.md` and the `.gitignore` line. It never overwrites, so a board made earlier keeps its old `plugins/team/skills/testing/SKILL.md`, whose evidence step now uses `asdlc record-check`: update it by hand.
