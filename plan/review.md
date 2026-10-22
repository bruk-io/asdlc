# Plan: cross-machine review on the shared board

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R2 (a person merges; a review never approves), R12 (the reviewer is a subagent definition in the repository, in a checkout of its own), R15 (every finished task gets the passes `REVIEW.md` defines, and the engineer whose agent wrote a change does not review it unless nobody else does, and then visibly)

PR 2b of the pilot, stacked on orchestration (#18) and the shared board (#16). A finished task is In Review with its branch and pull request on the board. Any orchestrator whose engineer didn't write it claims the review atomically, its reviewer agent judges the diff from a fresh context, and the verdict goes on the task: changes send it back to the worker that built it, a clean review leaves it for a person to merge. If nobody else claims a review within `review_fallback_after`, the author's own machine may review it, marked as a same-machine review. Orchestrators still share nothing but the board, so every step is a board change through the same compare-and-swap transaction as a claim.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | The review route (sonnet/medium) in the routing table; the review keys `asdlc_reviewer` and `asdlc_review_kind`, and task references; `review-next` (eligibility, ordering, the same-machine fallback with the clock passed in) and `review-done` (verdict, labels, status), both through `_transact`; `reap` and `heartbeat` for review claims; `mine` lists review claims and tasks sent back; review claims count against the `workers` cap | R2, R15 |
| `agents/reviewer.md` | yes | The reviewer subagent: read-only tools, `REVIEW.md` from the plugin and the repository's default branch, the task, plan, acceptance criteria and contracts, the size-1 check, the diff in a detached checkout, `review-done`, a pull request comment through `gh`, never an approval | R12, R15 |
| `skills/orchestrate/SKILL.md` | no | The loop claims reviews when the engineer reviews and a slot is free, launches the reviewer with the route `review-next` prints, and hands `changes-requested` tasks back to their worker | R12, R15 |
| `agents/worker.md` | no | Fixing review findings: fix, record checks, push the same branch, In Review again without the label | R9, R15 |
| `tests/test_asdlc.py` | no | The review logic, and every review command against real repositories and the backlog CLI | R15 |
| `tests/test_demo_review.py` | yes | The two-machine review demonstration, as a test | R15 |
| `README.md` | no | The two commands, the changed `heartbeat`, `reap` and `mine` rows, and a Cross-machine review section | - |

## Order of work

1. Logic: the review keys and references on `Task`; `reviewer_for`; `authors`, `review_kind`, `review_refusal`, `review_candidates` (others' work first, then longest-waiting), `review_refs`, `review_done_refusal`, `review_comment`; the review route; `busy` for the cap; `Hold.REVIEW` in `stale_holds` and `reap_comment`; `mine_report`'s reviews and changes requested. Unit tests for each.
2. When a task entered In Review: the newest commit on the board whose diff adds or removes its `status: In Review` line, read with `git log -G`. The task is In Review now, so that commit is the one that put it there.
3. `review-next`: refresh, refuse when the engineer doesn't review or is at the cap, rank, claim the first through `_transact` (re-judged on the current board, so a reviewer who loses the push moves on to the next task), print the claim.
4. `review-done`: only the claiming reviewer, a verdict and non-empty notes; one board commit with the comment, the labels, the status and the claim cleared.
5. `reap` and `heartbeat` for review claims; `next` counts review claims against the cap.
6. Command tests: the claim race forced at the push and run concurrently on two clones, the author refused without `--fallback` and before the timeout, the timeout from `asdlc.toml`, both verdicts, only the claiming reviewer finishing, reaping a stale review claim, the review preference off.
7. The reviewer agent, the orchestrate skill, the worker agent, the README.
8. The demonstration.

## Risks

- **Two reviewers claiming one review.** The claim decides on the current `origin/main` and pushes; a rejected push drops it and decides again, so the loser sees the winner's `asdlc_reviewer` and moves on. Tested by forcing the race at the push and by racing two clones at once.
- **When a task entered In Review.** Read from the board's history, not a key, because the worker sets In Review with a plain `asdlc board task edit`. A task file renamed after it entered In Review (a title edit) reads as entering at the rename, so the fallback waits longer, never less. Commit times come from the committer's clock, as for `reap`.
- **A reviewer that edits the work.** The agent has no Edit or Write tool and reviews in its own detached checkout; Bash could still write, so its prompt forbids it, and the board guard still refuses edits to a code repository outside a claimed worktree.
- **An approval on GitHub.** The agent's prompt says comment only; nothing enforces it yet (see Departures).
- **A worker name holding two tasks.** A task sent back keeps its worker assignee, which the orchestrator may have reused for new work since. Each claim is its own task, heartbeat and agent, and both count against the cap, so nothing collides; the skill says to resume or relaunch under the name on the task.
- **Review claims and the cap.** `next` now counts review claims against `workers`, so an engineer reviewing at the cap picks no new work until a review finishes. That is the point of a slot; `mine` shows both counts.

## Departures from the brief

- The time a task entered In Review is read from the board's history (`git log -G` on its status line) rather than `_touched` or a new key: `_touched` restarts on any comment, and a key would need the worker's finish step to change from `asdlc board task edit` to a new command.
- `--fallback` also offers other engineers' work, ranked before the engineer's own, so the orchestrator always passes it and one call does the right thing.
- Reviewer names must be `<engineer>.r<n>`; `review-next` and `review-done` refuse any other name.
- Review claims count against the `workers` cap in `next` and `review-next`, since the orchestrator reviews "when a worker slot is free".
- `review-done` refuses empty notes and a task that is no longer In Review; `asdlc_review_kind` stays on the task after the review (for the person who merges) and is cleared only when a review claim is reaped.
- `heartbeat` keeps review claims alive, so a long review isn't reaped.
- Nothing yet stops an agent running `gh pr review --approve`; a board guard rule for it belongs with the guard, not this pull request.

## Proof

- `./scripts/check` passes: the review logic, every review command against real git repositories with a bare `origin` and the real backlog CLI, the review claim lost at the push, and two clones racing for reviews.
- `tests/test_demo_review.py` with `ASDLC_DEMO=1` prints the two-machine review story quoted in the pull request.
