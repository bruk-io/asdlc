---
kind: task
step: 3
delivers: [R8]
depends: [03-task-start]
size: 3
---
# Task: asdlc task start --resume

## What to build

Step 3 of the plan: the switch `--resume` on `asdlc task start`, which puts the checkout on the branch of a task that is already started.

- `src/asdlc/io/git.py` gains `switch_from_remote(root, branch)`: `git switch -C <branch> origin/<branch>`.
- `src/asdlc/domain/build.py`: `refusal` gains two reasons for a resume, a task whose branch is not on the remote and a task that is `done`.
- `src/asdlc/cli.py`: with `--resume` the command works through the five items the plan's step 3 lists. The merge of the remote's branch is last, so that a merge left in conflict still leaves the task reading `claimed`. When opening the pull request fails, the command switches back, and deletes the local branch when this run made it. A conflict is left as git left it.
- A merge already in progress on the task's branch is not refused as an uncommitted change. The command prints the files still in conflict, or says that the merge is to be committed when none is left, and exits 1.
- `README.md`: the command table's row for `asdlc task start` gains `--resume`.
- Tests, in `tests/test_task_start.py`: the twelve the plan's step 3 lists.

This task is started by hand, with `asdlc branch new task/building-a-task/05-task-start-resume`. Tasks 04 and 06 can be built at the same time and change the same files, and task 07 gives the same answer for a merge in progress in `asdlc task stop`. Whichever merges second resolves the conflict.

It is a 3. Every function it needs but one is there from task 03, and the order is given. The work is in the tests, one for each state a resume can meet.

## Done when

- `just check` passes, and its output is in the pull request.
- A clone with no local branch for the task gets one at the remote's commit.
- A branch left by a start that was cut short is replaced by the remote's, and holds one start commit.
- A task whose pull request was lost gets a draft opened, and a ready pull request becomes a draft.
- A local branch that is behind is brought up. With a commit on each side the remote's branch is merged in, and a push afterwards is taken.
- A merge that conflicts prints the files, exits 1 and leaves the merge, and the pull request is already a draft.
- A merge already in progress prints the files in conflict and exits 1. With none left in conflict the command says the merge is to be committed.
- Run in a checkout that is already on the task's branch, it leaves the checkout there.
- Refused, with nothing changed: an uncommitted change, a branch that is not on the remote, a task that is `done`, a checkout on the branch of another task that is claimed, and a branch a second worktree holds, with that worktree's path in the reason.
- A pull request that cannot be opened leaves the checkout where it was.
- `asdlc task start` without `--resume` does what it did before this task.
