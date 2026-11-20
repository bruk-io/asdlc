---
kind: task
step: 4
delivers: [R10, R12, R13, R14, R15, R16, R17]
depends: [03-task-start]
size: 5
---
# Task: asdlc task stop runs the checks, pushes, comments, and marks ready or draft

## What to build

The first of three pieces of step 4 of the plan: `asdlc task stop <slug>/<task>`, from its refusals to `ready` or `draft`. Task 07 adds the merges (R15). Task 08 adds the rest of what the comment holds, and `--message` (the rest of R13).

The plan's step 4 lists twelve items in order. This piece is items 1, 2, 4, 6, 7, 9, 10, 11 and 12, and the refusal of uncommitted changes in item 3.

- `src/asdlc/io/checks.py` (new): `run(line, folder)`.
- `src/asdlc/io/git.py`: `file_at`, `push` and `head`. `src/asdlc/io/github.py`: `comment(root, number, body)`, with the body on stdin.
- `src/asdlc/domain/build.py`: `outcome(statuses, left, faults)`. Nothing is passed as `faults` until task 09.
- `src/asdlc/presentation/pull.py`: `comment(...)`, holding the commit the checks ran on, each check's command line, exit status and output in a fenced block, and each file the checks left changed or untracked. The output goes in as printed. Task 08 replaces the paths in it and cuts what is too long.
- `src/asdlc/cli.py`: `task stop`. It refuses a `--root` below the top with exit 2, fetches and exits 1 when that fails, refuses what R14 lists, reads `.asdlc/checks` from `origin/main` and never from the branch, asks `guard` about `changed_since(root, "origin/main")`, runs every line, pushes, posts the comment, and sets ready or draft by `outcome`. The comment is added and never edited.
- `README.md`: the command table gains `asdlc task stop`, and "When each thing runs" gains a row for it.
- Tests: `tests/test_task_stop.py` (new), each starting from a task that `asdlc task start` started on the fixtures, with the plan's tests for these items. `tests/io/test_checks.py` (new), and the domain, io and presentation tests for the new functions.

Left for task 07: a merge already in progress, merging the remote's branch for the task and the remote's `main`, and the answer when the remote's branch gains a commit after the fetch. Until then a push the remote does not take exits 1 with git's own reason, and nothing is posted. Left for task 08: `--message`, the stand-ins for paths, the cutting, and the files the guard marked.

This task is started by hand, with `asdlc branch new task/building-a-task/06-task-stop`. Tasks 04 and 05 can be built at the same time and change the same files. Whichever merges second resolves the conflict.

It is a 5. The command has many parts in a fixed order, and it runs command lines and publishes what they print. Nothing in it is unknown. The step was split, and tasks 07 and 08 took what can be added afterwards. This piece is not split again: R17 forbids marking a pull request ready without the comment, and a stop that pushed without running the checks could not be merged.

## Done when

- `just check` passes, and its output is in the pull request.
- A passing check gives `ready` and exit 0, and one comment with the command line, the exit status, the output and the commit.
- A failing check gives `draft` and exit 1, with the branch pushed and the comment posted. A later failing run makes a ready pull request a draft again.
- The checks are read from the remote's `main` when the branch's own `.asdlc/checks` says `true`. Every line runs when the first fails. With no checks on `main`, nothing is run, pushed or posted.
- Refused with exit 1, and nothing run, pushed or posted: a task that was never started, on a branch that `asdlc plan new <slug>/<task>` made; a started task whose pull request was closed; a checkout on another branch, named in the reason; a changed tracked file; an untracked file; and a branch that changes no file.
- A branch that changes `intent/<slug>/spec.md` prints the guard's line and pushes nothing.
- A check that changes a tracked file, and one that leaves an untracked file, each give `draft`, with the file named in the comment.
- When the comment cannot be added, the command exits 1 after the push. With a failing check a pull request that was ready becomes a draft, and with passing checks a draft is not marked ready.
- A `gh` that fails exits 1, and is not read as a task with no pull request.
- A fetch that fails exits 1, a `--root` below the top exits 2, and a target that names no task on the remote's `main` exits 3.
- The command prints the pull request's link and `ready` or `draft`, tab-separated.
