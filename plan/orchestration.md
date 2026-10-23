# Plan: orchestrators, leads and workers on the shared board

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R2 (accepting work stays a person's command), R7 (intents on the board), R9 (plans before edits, approved for size 2 and up), R12 (each worker in its own claimed worktree), R16 and R26 (the guard refuses agents accepting work, with the reason, and logs it)

The second of the pilot's pull requests, stacked on the shared board (#16). Each engineer talks to one orchestrator session; its workers are background subagents, each in a claimed worktree in the right code repository on that machine. A large piece of work has one lead, claimed atomically on its intent. Orchestrators on different machines share nothing but the board, so identity, reservations, preferences, leads, heartbeats and reaping are all board state or machine registration, decided by `asdlc` with the same compare-and-swap push as a claim. Review claims and the review loop come in PR 2b; the team plugin and rule loading are PR 3; per-repository plugin onboarding is PR 4.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | Engineer identity (`git config asdlc.engineer`) and worker names; reservations in the assignee list; `whoami`, `register`, `repos`, `lead`, `lead-of`, `heartbeat`, `reap`, `accept`, `mine`, `record-check`; `next` eligibility, ranking and spreading; worktrees in the registered repository; `--json` output; draft parents for children drafted under a draft intent; one compare-and-swap transaction every new board change uses, claims included | R2, R9, R12 |
| `scripts/repo_slug.py` | yes | Copied byte for byte from PR 3 (#17), so both pull requests derive the slug in one place | R12 |
| `hooks/guard_board.py` | no | Refuses agents running `asdlc accept`; judges the command `asdlc record-check` runs | R2, R16, R26 |
| `agents/worker.md` | yes | The worker subagent: one task, one worktree, plan then build, the finish step | R9, R12 |
| `skills/orchestrate/SKILL.md` | yes | The engineer's orchestrator loop | R9, R12 |
| `skills/lead/SKILL.md` | yes | The lead's spec, contracts, breakdown, change requests and consistency checks | R7, R9 |
| `skills/capture-intent/SKILL.md` | no | The intent as a draft of type intent on the board; files only in a repository that keeps them | R7 |
| `skills/plan-change/SKILL.md` | no | The plan in the task's plan section; numbered steps for size 1; files only in a repository that keeps them | R9 |
| `commands/intent.md` | no | Points at the board | R7 |
| `commands/plan.md` | no | Takes a claimed task | R9 |
| `tests/test_asdlc.py` | no | The new logic, and every new command against real repositories and the backlog CLI | R2, R9, R12 |
| `tests/test_repo_slug.py` | yes | PR 3's tests for the slug, copied with it | R12 |
| `tests/test_guard_board.py` | no | The accept rule and the record-check rule, as logic and through the hook | R16, R26 |
| `tests/test_demo_orchestration.py` | yes | The two-machine demonstration, as a test | R12 |
| `README.md` | no | The new commands and an Orchestration section | - |

## Order of work

1. Identity and reservations: `engineer_name`, `worker_for`, people and workers in the assignee list; `claim_refusal` and `race_result` learn reservations; the claim keeps the person and adds the worker; `release` puts a reservation back.
2. One transaction for board changes: decide on the clone level with `origin/main`, change, squash to one commit, push; on a rejected push, drop it and decide again on the new state. Claims move onto it unchanged in behaviour (the race test holds).
3. Machine and board configuration: `register`, `repos`, the registry in `${XDG_CONFIG_HOME:-~/.config}/asdlc/repos.toml`, the board's `projects`, `devs/<name>.yaml` in a strict flat subset, `asdlc.toml`; `whoami`.
4. `next`: eligibility (registered repository, dependencies Done, route accepts, reservation), ranking (reserved, preferred, priority and ordinal), spreading by worker name, the workers cap; claims make the worktree in the registered repository.
5. Leads and liveness: `lead`, `lead-of`, `heartbeat`, `reap` with `now` passed in.
6. `accept`, draft parents through `asdlc board`, and the guard rule.
7. `mine` and `record-check`.
8. Skills, the worker agent, commands and README.
9. The demonstration: two machines, one intent with four children across two repositories, one reserved.

## Risks

- **Two orchestrators changing the same task at once.** Every new board change decides on the current `origin/main`, pushes, and on a rejected push decides again on the new state; a lead lost at the push says who won. Tested by forcing the race with the interfering backlog wrapper, and the existing claim race still runs ten times.
- **A heartbeat and a reap at once.** `reap` judges staleness again inside its transaction, on the newest board, so a heartbeat pushed first wins and the claim stays.
- **Staleness from commit times.** `reap` reads the committer date of the last commit touching the task file on `origin/main`, so a machine whose clock is far off can make a claim look older or newer than it is. Heartbeats every 30 minutes against a 2h timeout leave room.
- **Draft ids are reused after promotion.** Backlog only lets an accepted task be a parent, so `asdlc board task create --draft -p DRAFT-<n>` records the draft parent itself, and `accept` promotes the intent and its children together, re-parenting and carrying dependencies over. A person who promotes the intent with `backlog draft promote` instead orphans its children; the README and the lead skill say to use `asdlc accept`.
- **Keys Backlog doesn't know.** Leads and heartbeats are frontmatter keys (`asdlc_lead`, `asdlc_heartbeat`). Backlog 1.55.1 and later keep unknown keys through edits and promotion, checked here; asdlc already refuses older versions.
- **A global `asdlc.board` would guard every repository.** `register` sets it in each code repository instead, and the README says not to set it globally.
- **The guard is a guardrail.** `asdlc accept` through a path it doesn't parse gets through, as before.

## Departures from the brief

- `next` also enforces the `workers` cap, so an orchestrator that miscounts can't exceed it.
- `avoid` excludes a repository's work unless it is reserved for the engineer, as PR 3's `devs/README.md` defines it, rather than ranking it last. The devs format is PR 3's: bracket lists only, `name` required, `workers` defaulting to 3.
- The settings keys are PR 3's: `stale_after` and `review_fallback_after`.
- `register` always sets the repository's `asdlc.board`, not only when `--board` is given (Risks).
- The board is also found from the board clone the command runs in, and from a global `asdlc.board`, so an orchestrator in the tasks repository needs no flag.
- A task with no `project` is skipped by `next`, with a reason; `claim` still takes it and, as before, makes the worktree in the code repository the command runs in.
- `release` also gives up a lead.
- `accept` on an intent that is already accepted promotes only its new draft children.
- `record-check` was added on the coordinator's request; the guard judges the command it runs.
- Existing tests' worker names became `<engineer>.<label>`, since a worker must now belong to the engineer.
- `README.md` still says stale claims are released by hand: PR 3 inserts its section beside that line, so it is left for whichever pull request merges second to correct.

## Proof

- `./scripts/check` passes: every new command against real git repositories with a bare `origin` and the real backlog CLI, the lead race forced at the push, and the claim race ten times.
- `tests/test_demo_orchestration.py` with `ASDLC_DEMO=1` prints the two-machine story quoted in the pull request.
