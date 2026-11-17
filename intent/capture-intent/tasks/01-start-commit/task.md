---
kind: task
step: 1
delivers: [R17]
size: 1
---
# Task: asdlc intent new records the start of an intent

## What to build

Step 1 of the plan. `asdlc intent new` makes an empty commit on the intent's branch before it writes `intent.md`, so the time from the start of an intent to its committed `intent.md` can be read from git.

- `src/asdlc/io/git.py` gains a function that makes an empty commit and says whether git accepted it.
- `intent new` in `src/asdlc/cli.py` calls it when the branch has no commit of its own. The subject is `Start intent <slug>`.
- `spec new`, `plan new` and `task new` do not change.

## Done when

- After `asdlc intent new` in a new repository, the branch is one commit ahead of `main` and that commit changes no file.
- `asdlc branch check` is clean once `intent.md` is committed on that branch.
- When git cannot tell who is committing, the command says so, exits 1 and writes no file.
- `just check` passes.
