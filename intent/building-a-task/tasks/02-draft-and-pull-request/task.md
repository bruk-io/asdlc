---
kind: task
step: 1
delivers: [R9, R10, R11, R36]
depends: [01-tasks-from-the-remote]
size: 3
---
# Task: a draft reads as claimed, and a task carries its pull request

## What to build

The second of two pieces of step 1 of the plan: the pull requests (R11 and R36). Task 01 is the other piece. This one needs the `remote` fixture that task builds.

- `src/asdlc/io/github.py`: `open_pull_branches` becomes `open_pulls(root)`. It gives one row for each open pull request (branch, number, link, draft or not), and `None` when the program is missing or fails. It runs the program named by `git config asdlc.gh`, and `gh` when the key is not set. The module's docstring gains the line the plan gives about pull request #101.
- `src/asdlc/domain/tasks.py`: `Task` gains `pull_request`, and `tasks()` gains the keyword `links`. `_state` is not changed.
- `src/asdlc/cli.py`: `_tasks` passes the branches whose pull request is not a draft as `open_pulls`, and every pull request's link as `links`. It has four callers, so `task list`, `task show`, `intent list` and `intent show` agree.
- `src/asdlc/presentation/text.py` and `src/asdlc/presentation/data.py`: `task_record` gains a `pull-request` line and `data.task` a `pull_request` field.
- `tests/conftest.py` gains the fixture `gh`, as the plan's "Four things hold for every step" describes it: a stand-in for `gh`, written as a shell script and set through `asdlc.gh`, that keeps the open pull requests in a JSON file, appends each call to a record, and can be told to fail on one subcommand. Its files are beside the clone and not in its working tree. This task uses only its `pr list`. Tasks 03 and 06 use `pr create`, `pr comment` and `pr ready`, so build those now.
- `tests/test_walk.py`: its own stand-in answers with `isDraft`, and the walk gains a draft that reads `claimed`.
- `README.md`: the paragraph that starts "State is never stored" says that a draft reads as claimed and that `task show` gives the pull request.
- Tests: `tests/io/test_github.py` (new), which also takes the two `gh` tests out of `tests/io/test_git.py`; `tests/domain/test_tasks.py`; `tests/presentation/test_text.py`; and the test about a draft in `tests/test_cli.py`.

This task is started by hand, with `asdlc branch new task/building-a-task/02-draft-and-pull-request`.

It is a 3. The change is small in each file, and it reaches every place a state is shown. The stand-in is the part with real work in it: tasks 03 to 09 are tested against it, and a copy of it goes into each eval scaffold in task 10.

## Done when

- `just check` passes, and its output is in the pull request.
- A task whose pull request is a draft reads `claimed`, and `in review` once the pull request is ready, in `task list`, `task show`, `intent show` and `intent list --json`.
- `asdlc task show` has a `pull-request` line with the link, and under `--json` a `pull_request` field. Both are empty for a task with none.
- With `git config asdlc.gh` set, that program is run in place of `gh`.
- With a `gh` that is missing or fails, `task list` still lists, and no task reads `in review`, as today.
- The stand-in's script, its JSON file and its record are outside the clone's working tree: `git status --porcelain` in the clone prints nothing once the fixture is set up.
- The stand-in answers `pr create --draft`, `pr comment`, `pr ready` and `pr ready --undo`, and a test shows it failing on one subcommand when told to.
