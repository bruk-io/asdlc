---
kind: task
step: 4
delivers: [R10, R12, R13, R14, R15, R16, R17]
depends: [06-task-stop]
size: 3
---
# Task: asdlc task stop merges the remote's branch and main first

## What to build

The second of three pieces of step 4 of the plan: the merges `asdlc task stop` makes before it runs the checks (R15), and the push the remote refuses because its branch moved (the last sentence of R16). Task 06 built the command. `merge`, `conflicts` and `merging` are in `src/asdlc/io/git.py` from task 03.

In `src/asdlc/cli.py`, in the plan's list for step 4:

- Item 3: a merge that is already in progress is not refused as an uncommitted change. Print the files still in conflict, or say that the merge is to be committed when none is left, and exit 1.
- Item 5: when `origin/task/<slug>/<task>` has a commit the checkout lacks, merge it in. This comes before the refusal of a branch that changes no file.
- Item 8: merge `origin/main`, after the guard is asked and before the checks run. The guard comes first, so that a refusal leaves no merge of `main` on top of a commit the builder has to make again.
- A clean merge is committed. A merge that conflicts is left as git left it, its files are printed, and the command exits 1 with nothing run, pushed or posted.
- Item 10: when the remote refuses the push for a commit the checkout lacks, exit 1, post nothing, and say to run the command again. `push` in `src/asdlc/io/git.py` says whether a push that was not taken was refused for that.

Tests, in `tests/test_task_stop.py`: the plan's two for these items, the one that starts "`main` moved" and the one that starts "The remote's branch ahead of the checkout". The commit that arrives between the fetch and the push is staged with a check line that pushes from a second clone, because the checks run between the two.

This task is started by hand, with `asdlc branch new task/building-a-task/07-stop-merges`. Task 08 can be built at the same time, and task 05 gives the same answer for a merge in progress in `asdlc task start --resume`. Whichever merges second resolves the conflict.

It is a 3. The git calls are there and the order is given. The work is in the tests, which need a second clone and a merge left half done.

## Done when

- `just check` passes, and its output is in the pull request.
- When `main` moved with no conflict, it is merged and committed, and the checks run on the merge.
- A conflict with `main` prints the files, exits 1 and leaves the merge, and nothing is run, pushed or posted.
- A second run with that merge still in progress prints the files again. With the files resolved and staged and the merge not committed, it says the merge is to be committed. After the merge is committed the run goes on.
- With a commit on each side of the task's branch, the remote's is merged in and the run goes on.
- When the remote's branch gains a commit between the fetch and the push, the run exits 1, posts nothing and says to run it again.
- A branch the guard denies has no merge commit added.
