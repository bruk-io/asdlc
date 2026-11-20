---
kind: task
step: 2
delivers: [R1, R2, R3, R4, R5, R6, R7, R9, R10]
depends: [03-task-start]
size: 3
---
# Task: a start that loses the claim, or cannot open its pull request

## What to build

The second of two pieces of step 2 of the plan: what `asdlc task start` does when its push claimed nothing (R6), and when the pull request cannot be opened after the push (R7). Task 03 built the command, and already ends both in the undo of the checkout with exit 1. This piece adds what each owes the remote and the person.

- `src/asdlc/io/git.py` gains `delete_remote(root, branch, commit)`: `git push --force-with-lease=<branch>:<commit> origin :<branch>`.
- `src/asdlc/cli.py`, item 6 of the plan's list for step 2: when `claimed` says no, fetch, and exit 1 naming the pull request of the start that did claim the task, when there is one.
- Item 7 of that list: when `open_draft` fails, `delete_remote` with a lease on this start's own commit, say why on stderr and exit 1. When the remote's branch cannot be deleted either, say that it is left there and that `asdlc task start --resume` finishes the start.
- Tests, in `tests/test_task_start.py`: the race for R6 in its two stagings, and the three tests for R7, as the plan's step 2 gives them.

The race is staged after the second start's fetch, by running the first clone's whole `task start` from a git hook in the second clone. From a `post-checkout` hook, with both start commits pinned to one instant through `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`, the second push answers `=`. From a `pre-push` hook it answers `!`. The hook clears git's own `GIT_*` variables and uses the interpreter the tests run under. A start run from a second clone after the first has finished is refused before it pushes, so that is not the test.

This task is started by hand, with `asdlc branch new task/building-a-task/04-start-undone`. Tasks 05 and 06 can be built at the same time and change the same files. Whichever merges second resolves the conflict.

It is a 3. The code is a few lines in two places. The work is in the tests: a race staged on one machine through a hook, and a remote taken away in the middle of a command.

## Done when

- `just check` passes, and its output is in the pull request.
- In both stagings of the race the second start exits 1, its checkout is back where it was with no local task branch, the remote's branch is the first start's commit, the stand-in holds one pull request, and the reason names that pull request.
- One staging's push answers `=` and the other's `!`, and each test shows which it got.
- With the stand-in failing on `pr create`, the remote has no branch for the task, the checkout is where it was, the clone has no local task branch, and stderr says why.
- When the remote's branch moved before the delete, it is not deleted.
- When the remote's branch cannot be deleted, the message says it is left there and names `asdlc task start --resume`.
