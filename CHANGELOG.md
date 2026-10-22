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
