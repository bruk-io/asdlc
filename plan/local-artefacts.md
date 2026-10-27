# Plan: artefacts where the repository keeps them, one machine

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in session, 2026-10-27. Implementation in progress.
- Delivers: R1 (each artefact a committed file the next stage reads), R2 (accepting stays a person's recorded action), R5 (one person may own every gate), R9 (plans approved before edits), R12 (parallel work in worktrees and subagents on one machine)

A first person to try the plugin had to create a separate tasks repository before anything worked. The spec says the plugin "keeps every artefact as a plain file in git with a pull request as each gate" (R1, R2), but the shipped skills write to a Backlog.md board in a shared tasks repository, and `scripts/asdlc` (about 5,200 lines) coordinates several engineers on several machines through atomic claims, heartbeats, leads and reaping. This plan returns the plugin to the spec's shape: artefacts live where the repository you are in already keeps them, and parallelism is subagents in worktrees on one machine. Backlog.md stays as the task board, and the user decides where it lives: a `backlog/` folder in the working repository, a separate repository, or anywhere else `asdlc` is pointed at (`--board`, `$ASDLC_BOARD` or `git config asdlc.board`, which already exist). Multi-machine coordination is removed, not adapted; it can return later as an optional adapter if someone needs it, with its own intent.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `skills/capture-intent/SKILL.md`, `skills/write-spec/SKILL.md`, `skills/break-down-intent/SKILL.md`, `skills/plan-change/SKILL.md` | no | Say what the artefact is and how it is shaped, not where it is saved. They find where the work is kept: the configured board, else a `backlog/` folder in the repository, else an existing `intent/`, `spec/` or `plan/` folder or `docs/` convention. When there is none they ask once and write the answer as one line in the repository's `CLAUDE.md` | R1, R7, R8, R9 |
| `skills/orchestrate/SKILL.md` | no | One session launches `worker` and `reviewer` subagents in worktrees on this machine, each at the model and effort its size routes to; no claims, heartbeats, reaping or leads | R9, R12 |
| `skills/lead/SKILL.md` | removed | Contract change requests and checking a plan against the contract move into `orchestrate`; the claim and cross-engineer consistency are dropped | R9 |
| `agents/worker.md`, `agents/reviewer.md` | no | Take a task from the orchestrator's brief, not from a claim on a board; the reviewer's independence from the author stays (R15) | R9, R12, R15 |
| `commands/intent.md`, `commands/plan.md` | no | Point at the skills, not the board | R7, R9 |
| `scripts/asdlc` | no | Keeps `claim`, `release`, `next`, `register`, `repos`, `approve`, `accept`, `finish`, `record-check`, `route`, `whoami`, `doctor`, `stats` and the `--board` / `asdlc.board` resolution, which already finds a `backlog/` folder in the repository you are in. Removes `lead`, `lead-of`, `heartbeat`, `reap`, `review-next` and `review-done`'s claim check; the orchestrator launches the reviewer itself. Gives the board a local mode (see the first open question). `init-board` becomes optional setup | R2, R12 |
| `hooks/guard_board.py` | no | Keeps refusing an agent that accepts or approves work, with the reason; drops the board-push rules | R2, R16, R26 |
| `templates/board/` | no | Stays as an optional scaffold for a shared board repository; nothing requires it | R1 |
| `evals/cases/` | no | `reaped-worker-stops`, `grandchild-follows-lead` and `sent-back-resumes-branch` describe behaviour that no longer exists and are retired by a person (R24); the rest keep running | R22, R24 |
| `tests/` | no | Tests for removed commands and the multi-machine demonstrations go with them; tests for what stays are not weakened | R12 |
| `README.md`, `docs/guide.md` | no | Setup becomes: install the plugin, run it in your repository | - |

## Order of work

1. Done (findings below). Write down what each `asdlc` command is used for today and by which skill, agent, hook, test and eval, so the cut list in the table is checked against the code and not my reading of the README. Settle the open questions below with the owner before step 2.
2. Rewrite the four artefact skills and `commands/` to the find-or-ask location rule. Check by running each against an empty repository and against one that already has `docs/` and `backlog/`.
3. Rewrite `orchestrate`, `worker` and `reviewer` for one machine; fold the lead's two surviving duties into `orchestrate`; remove `lead`.
4. Cut `scripts/asdlc` and `guard_board.py` to the commands that survive, with their tests, removing each command together with its tests and doc lines, not all at once.
5. Retire the eval cases (the cases need the owner's recorded approval, since this plan cannot change the suite that judges it).
6. Update the README and guide; run `./scripts/check`.

## Risks

- **Removing coordination breaks something the guard or an eval relies on.** Medium. Step 1 maps every use before any removal, and each command goes with its tests in step 4, so a break shows at once.
- **R23 forbids a pull request that changes the plugin from also changing the eval suite.** High. The retired cases and any changed expectations have to ship as a separate, person-approved change, merged first. This plan lists them but does not edit them.
- **Dropping multi-machine support loses a real user.** Low, since the intent assumes no team size, but the owner should confirm nobody depends on it. A tag on the last release keeps the old version available.
- **"Find the repository's convention" is judgement, and a skill that guesses wrong writes files in the wrong place.** Medium. The skill states where it will write before writing and asks when it finds more than one candidate.
- **A board in the working repository shares history with the code, so board commits and code commits mix.** Low to medium. Board changes go through the `asdlc board` commands as today, on the branch the user chooses; the guide says how to keep a board in its own repository instead.

## Step 1 findings

- The first draft of this plan removed `claim`, `next`, `register` and `repos`. The map shows they are not multi-machine features: `claim` is what makes a worker's worktree and marks the task In Progress, `register` and `repos` map a repository slug to its path for it, and `evals/fixtures.py`, `asdlc-plugin` and `onboard-repo` use them. They stay, and the table above is corrected.
- What goes is only what exists for several engineers: `lead`, `lead-of`, `heartbeat`, `reap` (stale claims), `review-next` (the cross-engineer review queue), and the evals and tests that exercise them (`reaped-worker-stops`, `grandchild-follows-lead`, the review-queue parts of `sent-back-resumes-branch`, `test_demo_orchestration.py`, parts of `test_demo_review.py`).
- The board's write path is the large part, about 500 lines (`_transact`, `_publish`, `_catch_up`, `_rebase`, `_drop_own`, the lock). It assumes the board is a dedicated clone on `main` with an `origin`: `_require_ready` refuses any other branch, and every change starts level with `origin/main`, pushes to it, and on a lost race resets to it. A `backlog/` folder inside a working repository, on a feature branch or with no remote, is therefore refused today.

## Open questions for the owner

- Settled: Backlog.md stays, and the user chooses where it lives.
- How should a board that is not a dedicated clone on `main` behave? I recommend a local mode: when the board is inside the working repository, or has no `origin`, `asdlc` skips fetch, push and rebase, and commits board changes to whatever branch is checked out, so they travel with the code in the same pull request. A dedicated board repository keeps today's behaviour, push-race handling included, so nothing that works now changes.
- Settled: `approve` stays. A person approves a plan in their own terminal before workers build; it is the R2 gate for plans.
- Settled: the chosen location is recorded as one line in the repository's `CLAUDE.md`; no config file.

## Proof

- `./scripts/check` passes after each step, and its output is pasted in the pull request.
- In a new empty repository with only the plugin installed, `/intent` writes an intent, the spec skill writes a spec and `/plan` writes a plan, with no tasks repository and no `asdlc init-board`, and a `backlog/` folder in that repository holds the board.
- Pointing `asdlc` at a board in a separate repository (`git config asdlc.board`) still works.
- In a repository that already keeps `docs/adr/` or a `backlog/` folder, the skills find and use it, and say where they will write before they write.
- `grep -rn "heartbeat\|reap\|review-next" skills agents commands hooks scripts README.md docs` finds nothing.
- Every test removed is for a removed command, and the diff shows no weakened assertion on anything that stays.
