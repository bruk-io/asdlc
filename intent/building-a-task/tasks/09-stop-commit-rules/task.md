---
kind: task
step: 5
delivers: [R18, R19, R20]
depends: [06-task-stop, 07-stop-merges]
size: 3
---
# Task: asdlc task stop and the rules about commits

## What to build

Step 5 of the plan: the three rules `asdlc task stop` reads from a branch's commits.

- `src/asdlc/domain/build.py` gains `plan_only(size, commits, slug, task)` and `faults(size, commits, slug, task)`, as the plan's step 5 gives them. `commits` in `src/asdlc/io/git.py` leaves merge commits out, so both pass over them. A commit with the start's subject and no file is the start.
- `src/asdlc/presentation/pull.py`: `comment(...)` gains each rule that failed, and a new `plan_comment()` says the plan is there to be read.
- `src/asdlc/cli.py`, in two places of the list in the plan's step 4:
  - After the guard is asked and before `main` is merged: read the task's size from the `task.md` on `origin/main`, and ask `faults`. A commit at fault that is not on the remote yet is named with its rule, and the command exits 1 and pushes nothing. One that is already on the remote goes to `outcome`, which gives `draft`, and to the comment.
  - After `main` is merged and before the checks: when `plan_only`, push, post `plan_comment`, print the link and `plan`, and exit 0. No check is run.
- `README.md`: "When each thing runs" says what `task stop` holds back, and what `plan` means.
- Tests: the five in `tests/test_task_stop.py` that the plan's step 5 lists, and `tests/domain/test_build.py` for the two functions.

It needs task 07 as well as task 06, because both places are fixed by where `main` is merged.

This task is started by hand, with `asdlc branch new task/building-a-task/09-stop-commit-rules`. Task 08 can be built at the same time and changes `comment(...)` too. Whichever merges second resolves the conflict.

It is a 3. Two pure functions decide everything, and the `remote` fixture already has a task of size 8. The part to get right is the difference between a commit at fault that is still local, which is refused, and one that is already pushed, which gives a draft.

## Done when

- `just check` passes, and its output is in the pull request.
- A commit that changes the intent's `plan.md` and no file outside `intent/`, not yet pushed, is refused and named with exit 1. Nothing is pushed and no merge commit is added.
- The same commit, already on the remote, gives `draft`, and the comment names the rule.
- For a task of size 8 whose first commit after the start is code: refused when it is not yet pushed, a draft when it is.
- A task of size 8 whose branch holds only its plan gives `plan` and exit 0, with the branch pushed, a comment posted and no check run.
- The same after the plan is changed in a second commit.
- A merge of `main` between the plan and the code is passed over.
- A task that is not of size 8 is held to no rule about its first commit.
