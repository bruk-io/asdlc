# Plan: a shared board, claims and worktrees for the pilot

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R2 (To Do and Done stay a person's action), R9 (no edit before a claim), R12 (each task in its own worktree), R16 and R26 (the board guard blocks with the reason and logs every decision)

The pilot is a team of engineers, each on their own machine, each running several Claude Code agents. Their work is tracked on a Backlog.md board that lives in its own repository, with no code in it; the code lives in ordinary repositories. This change is the first of the pilot's pull requests: the board commands, atomic claims so no two agents anywhere work the same task, a worktree per claimed task, model routing, and a hook that keeps agents on those rails. The orchestrator, the workers, the reviewer and the finish step build on it in later pull requests.

It departs from the spec's design in one respect: the spec keeps every artefact as a plain file with no tracker. Intents, specs and plans stay plain files; the board tracks who is doing which piece of work, which the spec doesn't cover and a team of parallel agents needs. The spec should say so in its next revision.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | yes | `init-board`, `board`, `claim`, `next`, `release` and `route`; the routing table as data; pure decisions (claimability, race result, push outcome, candidates, routing) with git, files and the backlog CLI in a thin shell | R2, R9, R12 |
| `hooks/guard_board.py` | yes | The PreToolUse guard: hand edits of `backlog/`, a person's statuses, draft promotion and creating a task without `--draft`, code edits outside a claimed worktree, pushes to a code repository's default branch | R2, R9, R16, R26 |
| `hooks/hooks.json` | no | The board guard beside the test-edit guard, same matcher and uv wrapper | R16 |
| `tests/test_asdlc.py` | yes | The logic, then the script against real git repositories with a bare `origin` and the real backlog CLI: init, push, rejected push, duplicate ids, conflicts, the claim race ten times, `next`, `release`, worktrees, routing | R12 |
| `tests/test_guard_board.py` | yes | Every guard rule, deny and allow, as logic and as the hook run against real repositories; the uv wrapper | R16, R26 |
| `tests/support.py` | no | `load` imports a script without a `.py` suffix | - |
| `.github/workflows/ci.yml` | no | Installs `backlog.md@1.55.2` before `./scripts/check`, so the board tests run, and fail rather than skip, in CI | R13 |
| `README.md` | no | A "Shared board" section: setting it up, the commands, what the guard refuses and why | - |

## Order of work

1. The board commands: `init-board` writes the config (statuses To Do, In Progress, In Review, Done; types intent, task, bug, spike; size labels; `auto_commit`, `bypass_git_hooks`, `remote_operations` on; `check_active_branches` off) and commits with every hook off. `board` runs `backlog` with hooks off and pushes, rebasing and retrying up to five times with jittered backoff when someone pushed first.
2. Claiming: fetch and catch up, refuse unless the task is To Do with no assignee, commit the claim through the CLI, push. On a rejected push, read the task on `origin/main`: someone else's claim drops ours with "Another agent claimed <id> first"; anything else is rebased and retried. Then the race test: two clones, two processes started together, ten times.
3. Worktrees: `<repo>.worktrees/<id>` from `origin`'s default branch, a branch named from the task, the `.asdlc-task` marker, and the marker in `info/exclude`. `next` and `release`.
4. Routing: the table, `route`, and its refusals.
5. The guard, its tests, and its line in `hooks.json`.
6. README and CI.
7. The demonstration: ten To Do leaf tasks of mixed sizes, three clones, three `asdlc next` loops at once until no work remains.

## Risks

- **Push contention.** Every change goes to one branch, so agents race. A rejected push is rebased and retried up to five times with jittered backoff; a claim reads `origin/main` before retrying, so a lost race is never retried into a double claim. The race test runs ten times, and the demonstration runs three agents at once.
- **Two clones creating a task at once.** Both get the same id under different file names, which a rebase can't see as a conflict. After a rebase, `board` checks for a newly shared id; if there is one, it drops its own commit and runs the command again on the new state.
- **Several agents sharing one board clone.** Two asdlc commands in one clone would interleave commits and resets. Every change holds an `flock` on the clone's git directory.
- **The Backlog.md version.** 1.54 drops frontmatter keys it doesn't know on every edit. `asdlc` refuses to run with anything older than 1.55.1, and CI pins 1.55.2.
- **Stale claims.** An agent that dies keeps its task In Progress. For now a person releases it by hand with `asdlc release <id> --as <agent>`; expiring claims comes later.
- **Agent identity in the assignee.** The assignee is whatever name an agent passes to `--as`, and board commits carry the machine's git identity, not the agent's. Two agents given the same name could both work one task. The orchestrator in the next pull request hands out names.
- **The guard is a guardrail, not a wall.** A shell can write a file or set a status in a way the parser doesn't recognise, and an agent can run git with hooks off. When it can't parse a command that may touch the board, it allows and says so.
- **Default status.** `default_status` is To Do, so `backlog task create` without `--draft` makes accepted work. The guard catches an explicit `-s "To Do"` but not the default.

## Departures from the brief

- `board`, `claim`, `next` and `release` hold a lock on the board clone, because several agents on one machine may share a clone.
- A board rebase that conflicts drops this command's own commit, leaves the clone level with `origin/main`, and fails naming the task file. The brief said to abort and fail; keeping the commit would leave the clone stuck on the same conflict for every later command.
- `board` also replays its command after a rebase that leaves two tasks sharing an id (Risks).
- `claim` also refuses a task that `route` refuses (`size-8`, or not exactly one size label), and `next` skips them, since such a task can't start. `next` also skips a task whose dependencies on the board aren't Done.
- `board` prints backlog's output once the change is pushed, not while it runs, so a replayed command shows only the id that was kept.

## Proof

- `./scripts/check` passes, including the race test (ten runs, exactly one winner each time, one assignee on `origin/main`).
- The demonstration in the pull request: three agents, ten tasks, every task claimed exactly once, read from `origin/main`.
