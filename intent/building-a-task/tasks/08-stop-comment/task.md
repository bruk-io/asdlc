---
kind: task
step: 4
delivers: [R10, R12, R13, R14, R15, R16, R17]
depends: [06-task-stop]
size: 3
---
# Task: what the comment from asdlc task stop holds, and --message

## What to build

The third of three pieces of step 4 of the plan: the rest of what the comment holds (R13). This is the part of the step that decides what a check's output looks like once it is public.

- `src/asdlc/domain/build.py` gains `stand_ins(text, checkout, main, home)` and `fitted(outputs, room)`, as the plan's step 4 gives them. The paths are replaced by `<checkout>`, `<repository>` and `~`, longest path first, and `main` only when the checkout is a linked worktree. Each output is cut from the top, on a line, with the number of lines cut.
- `src/asdlc/io/git.py` gains `messages(root, range, path)` and `main_checkout(root)`.
- `src/asdlc/presentation/pull.py`: `comment(...)` gains each file the guard marked, with the message of the commit that changed it, and the text of `--message`.
- `src/asdlc/cli.py`: `task stop` gains `--message <text>`. One over 10,000 characters exits 2, in item 1 of the plan's list, before anything is fetched. The command measures the rest of the comment first, and the room for the checks' output is what is left of 60,000 characters. A marked file's commit message is cut to 2,000.
- Tests, in `tests/test_task_stop.py`: the plan's for these parts. `tests/domain/test_build.py` for `stand_ins` and `fitted`.

The guard marks a file with `Verdict.MARK` in `src/asdlc/domain/guard.py`. For a task's branch that is the intent's `plan.md`. The guard is not changed.

This task is started by hand, with `asdlc branch new task/building-a-task/08-stop-comment`. Tasks 07 and 09 can be built at the same time and change the same files. Whichever merges second resolves the conflict.

It is a 3: two pure functions and their wiring, with no unknown. The care is in the limits. GitHub refuses a comment over 65,536 characters, and a comment that cannot be added stops a pull request being marked ready.

## Done when

- `just check` passes, and its output is in the pull request.
- Run in a linked worktree, the posted output has `<checkout>`, `<repository>` and `~` where the three paths were. Run in the main checkout it has `<checkout>` and `~`.
- An output too long for the comment is cut from the top, on a line, and the comment says how many lines were cut.
- A long `--message` together with a long commit message still gives a comment under 65,536 characters.
- A `--message` over 10,000 characters exits 2, and nothing is fetched, run, pushed or posted.
- A branch that changes the intent's `plan.md` together with code gives a comment that names `plan.md` and holds the message of the commit that changed it.
- The text of `--message` is in the comment.
