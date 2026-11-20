---
kind: task
step: 1
delivers: [R9, R10, R11, R36]
size: 3
---
# Task: the task commands read the remote's main, and fetch first

## What to build

The first of two pieces of step 1 of the plan: where the `task` commands read from (R9 and R10). Task 02 is the other piece, the pull requests (R11 and R36), and is built after this one. The plan's step 1 gives each function and each test in full.

- `src/asdlc/io/git.py` gains `has_remote`, `fetch`, `document_texts_at` and `remote_branches`. `fetch` is a call of its own and does not go through `_git`, because it sets `GIT_TERMINAL_PROMPT=0` and a limit of 20 seconds.
- `src/asdlc/cli.py` gains `_fetched(options, must)` and `_remote_library(options)`. `task list` and `task show` call `_fetched(options, must=False)` and then read through `_remote_library`. `intent list`, `intent show`, `requirement list` and `document check` are not changed.
- A `--root` below the top of its repository reads the documents under `<prefix>intent/` at the remote's `main`, as the plan's paragraph "What a `--root` below the repository's root reads" says.
- `tests/conftest.py` gains the fixture `remote`, as the plan's "Four things hold for every step" describes it: a clone with a bare repository beside it as `origin`, whose `main` holds an intent, its spec, its plan, two tasks (one of size 2, one of size 8) and `.asdlc/checks`. Every later task's tests stand on it, so its documents have to pass `asdlc document check`.
- `README.md`: the paragraph that starts "State is never stored" says that the `task` commands read the remote's `main` and fetch first.
- Tests: `tests/io/test_git.py` for the four functions, and in `tests/test_cli.py` every test the plan's step 1 lists there but the one about a draft.

`open_pulls`, the `gh` fixture, the link on a task and `tests/test_walk.py` are task 02's. Leave `open_pull_branches` as it is.

This task is started by hand, with `asdlc branch new task/building-a-task/01-tasks-from-the-remote`, because `asdlc task start` is not built yet.

It is a 3. The approach is written out in the plan and nothing in it is unknown. The work is in the fixture, and in a fetch that must never hang or ask for a password.

## Done when

- `just check` passes, and its output is in the pull request.
- `asdlc task list` in a clone whose local `main` is behind the remote's lists a task that only the remote's `main` has.
- A task on a `tasks/<slug>` branch that is checked out and not merged is not listed.
- A branch pushed from a second clone reads `claimed` with no `git fetch` run by hand.
- With the remote unreachable, `task list` says so on stderr, still lists what was last fetched, and exits 0.
- `task list --root <folder>`, for a folder below the top that holds an `intent/` of its own on `main`, lists that folder's tasks.
- A repository with no remote reads its local `main`, and a folder that is no repository reads its files, as today.
- `intent list`, `intent show`, `requirement list` and `document check` do not fetch.
