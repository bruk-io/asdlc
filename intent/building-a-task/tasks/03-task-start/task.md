---
kind: task
step: 2
delivers: [R1, R2, R3, R4, R5, R6, R7, R9, R10]
depends: [01-tasks-from-the-remote, 02-draft-and-pull-request]
size: 5
---
# Task: asdlc task start

## What to build

The first of two pieces of step 2 of the plan: `asdlc task start <slug>/<task>`, for a start that nothing goes wrong with after its push, with every refusal before anything is made, and the undo of the checkout. Task 04 is the other piece: what the command owes the remote and the person when its push claimed nothing, or its pull request cannot be opened (R6 and R7).

The plan's step 2 gives each file, each function and the order the command works in. In this piece:

- `.asdlc/checks` (new), one line, `just check`. `.gitignore` gains `.claude/worktrees/` and `.DS_Store`. `CLAUDE.md`: the line for `src/asdlc/io/` says it reads and writes files, git and GitHub, and still decides nothing.
- `src/asdlc/domain/build.py` (new): `check_lines`, `refusal`, `claimed` and `leftover`.
- `src/asdlc/io/git.py`: `uncommitted`, `position`, `checked_out`, `switch_new`, `delete_branch`, `push_claim`, `commits`, `merge`, `conflicts` and `merging`. The last three have no caller yet. They land here so that tasks 05 and 06 do not both add them.
- `src/asdlc/io/github.py`: `open_draft` and `set_ready`. `set_ready` has no caller yet, for the same reason.
- `src/asdlc/presentation/pull.py` (new): `description(task)`.
- `src/asdlc/cli.py`: `task start`, items 1 to 8 of the plan's list, with one undo around items 4 to 7. Whatever fails after the checkout has moved, the command switches back to where it was and deletes the local branch it made. In this piece a push that `claimed` says no to, and an `open_draft` that fails, each end in that undo and exit 1 with git's or `gh`'s own words. Nothing is deleted from the remote here.
- `README.md`: the command table gains `asdlc task start`. The page says what `.asdlc/checks` is, that `task start` moves the checkout it is run in to the task's branch, and that building tasks side by side means a session for each, started with `claude --worktree`.
- Tests: `tests/test_task_start.py` (new) on the `remote` and `gh` fixtures, with every test the plan lists for step 2 but the race for R6 and the three for R7. `tests/domain/test_build.py` (new), `tests/presentation/test_pull.py` (new), and `tests/io/test_git.py` and `tests/io/test_github.py` for the new functions.

This task is started by hand, with `asdlc branch new task/building-a-task/03-task-start`.

It is a 5. The plan calls step 2 the riskiest: it is the only command that publishes, and it has to leave the checkout exactly as it found it when anything fails. It has many parts and no unknown, because each git and `gh` call it makes was tried against GitHub on pull request #101. The step was split once, and task 04 took the two failures after the push. This piece is not split again: the refusals and the undo are what make a start safe to merge, and the functions under the command have no other caller to be tried through.

## Done when

- `just check` passes, and its output is in the pull request.
- After `asdlc task start` the checkout is on `task/<slug>/<task>`, which is the remote's `main` and one empty commit with the subject `Start task <slug>/<task>`. The branch does not have `origin/main` as its upstream, and the branch the checkout was on is as it was.
- The same holds when it is run in a linked worktree, and the main checkout is not touched.
- The command prints the branch and the pull request's link, tab-separated, and under `--json` one object with `branch` and `pull_request`.
- The stand-in's record holds `pr create --draft --base main` with the title `Task: <the task's title>` and a description that names the task's `task.md` and each requirement it delivers.
- Each refusal of R4 exits 1, makes no branch and leaves the checkout where it was: no remote, a failing `gh`, no checks on `main`, a changed tracked file, an untracked file, a checkout on the branch of another task that is claimed, and a task whose branch another worktree holds. The reason names the files, or the worktree. An ignored file does not refuse, and neither does a checkout on the branch of a task that is in review.
- Each of `waiting`, `claimed`, `in review` and `done` is refused with its reason, a task that is not on the remote's `main` is refused with the merge it waits for, and a task found nowhere exits 3.
- A local branch that holds at most a start commit is used again, and one with work on it is refused and named.
- With `user.useConfigOnly` set and no name, and with the remote gone by the time of the push, the command exits 1 and leaves the checkout where it was with no task branch.
- `claimed` is true only for a push that answers `*`, and not for `=` or `!`.
- A fetch that fails exits 1, and a `--root` below the top of the repository exits 2.
- `asdlc plan new <slug>/<task>`, run on the task's branch after a start, writes the task's own `plan.md` and makes no branch.
