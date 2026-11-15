# Intent: merging a task's pull request marks the task Done

- Author: Bruk Habtu
- Requested by: @bruk
- Status: draft. Merging this file accepts it.
- Date: 2026-11-15

## Problem

When I merge a task's pull request, the task stays In Review until I separately mark it Done. Merging was already my decision; the second step is bookkeeping. It is easy to forget, it needs a terminal or a session, and until it happens every task that depends on the merged one stays blocked.

In a recent run two merged tasks sat In Review and held the next task back, with nothing wrong with either of them except that I had not typed the second command.

## Proposed outcome

- When a task's pull request is merged into the default branch, the task becomes Done on the board without anyone typing a command, and the board's record says which pull request was merged and who merged it.
- It works with no Claude session and no terminal open, including when the merge is done from a phone: the trigger is a GitHub Action in the repository the board lives in.
- A task whose merged pull request did not pass review on the commit that was merged is not made Done: it stays In Review and is visibly marked, so the gap is seen. Which cases count as not having passed (no review, changes requested, a clean review of an earlier head followed by commits the review did not cover) is for the spec to settle.
- No agent can use this path to mark a task Done. The authority is the person's merge, verified from GitHub's own record of the merge, not from anything an agent says. The board guard still refuses an agent setting Done.
- A task with more than one pull request becomes Done only when the last of them is merged.
- A pull request closed without merging changes nothing on the board.
- Dependents of the task become available to `asdlc next` as they would after a manual Done.

## Affected users and systems

- Engineers who merge pull requests for tasks on the board, on GitHub or from a phone.
- Orchestrators and workers waiting on tasks that depend on a merged one.
- The board, its record of who closed a task and why, and the board guard.
- The repository the board lives in, which gains a GitHub Action, and code repositories whose board is kept in a separate tasks repository.
- The accepted intent `hear-github-events.md`, whose constraint says a merge does not mark a task Done. That holds for its listener; this intent is the one place a merge does.

## Constraints

- The existing manual way of marking a task Done keeps working.
- The board is changed only through asdlc's own commands: the action calls an asdlc command, it does not edit board files.
- The action copes with several writers pushing to the board at once: it retries on a rejected push, as the other board writes do.
- A board kept in a separate tasks repository from the code is considered, not only a board inside the code repository: the code repository's merge must reach the tasks repository's board.
- Nothing secret is needed beyond the token GitHub gives the action, unless the cross-repository case truly needs more, in which case the spec says so plainly.
- The guard is not weakened. Everything it refuses an agent today, it still refuses.
- The existing checks, tests and evals still pass, and none is weakened to get there.

## Open questions

- [ ] Does a clean review of an earlier head count when later commits were pushed before the merge, or only when those commits are merge commits from the default branch or test-only?
- [ ] How is asdlc installed in the action? It is a uv script today.
- [ ] How does the action find the task from the pull request: the branch name `task-<id>-...`, the pull request recorded on the task by `asdlc finish`, or both agreeing?
- [ ] What happens for a board in a separate tasks repository, where the merge and the board are in different repositories?
- [ ] Can an engineer turn this off per repository?
