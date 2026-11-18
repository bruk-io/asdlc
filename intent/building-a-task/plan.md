---
kind: plan
---
# Plan: Build a ready task into a pull request

## Files that change

- .asdlc/checks (new)
- src/asdlc/cli.py
- src/asdlc/domain/build.py (new)
- src/asdlc/domain/tasks.py
- src/asdlc/io/checks.py (new)
- src/asdlc/io/git.py
- src/asdlc/io/github.py
- src/asdlc/presentation/data.py
- src/asdlc/presentation/pull.py (new)
- src/asdlc/presentation/text.py
- tests/conftest.py
- tests/domain/test_build.py (new)
- tests/domain/test_tasks.py
- tests/io/test_checks.py (new)
- tests/io/test_git.py
- tests/io/test_github.py (new)
- tests/presentation/test_pull.py (new)
- tests/presentation/test_text.py
- tests/test_cli.py
- tests/test_task_start.py (new)
- tests/test_task_stop.py (new)
- tests/test_walk.py
- plugins/asdlc/skills/building-a-task/SKILL.md (new)
- plugins/asdlc/evals/build-a-ready-task/case.yaml (new)
- plugins/asdlc/evals/build-a-ready-task/scaffold.sh (new)
- plugins/asdlc/evals/build-waits-for-the-merge/case.yaml (new)
- plugins/asdlc/evals/build-waits-for-the-merge/scaffold.sh (new)
- plugins/asdlc/evals/build-with-a-check-that-fails/case.yaml (new)
- plugins/asdlc/evals/build-with-a-check-that-fails/scaffold.sh (new)
- plugins/asdlc/evals/a-question-about-a-ready-task/case.yaml (new)
- plugins/asdlc/evals/a-question-about-a-ready-task/scaffold.sh (new)
- README.md

## Order of work

Six steps, built one after another. Step 1 is a trial and changes one docstring. Steps 2 to 4 are the command: how tasks are read, then `task start`, then `task stop`. Steps 5 and 6 are the skill and its eval cases. Each of steps 3 to 6 needs the one before it. Step 2 needs nothing from step 1.

No hook, no template, `src/asdlc/domain/guard.py` and `asdlc branch new` are not changed. `_state` in `src/asdlc/domain/tasks.py` is not changed either.

This intent's own tasks cannot all be built with what it builds. The tasks for steps 1 to 4 are started by hand with `asdlc branch new task/building-a-task/<task>`, as the generate-tasks tasks were. The tasks for steps 5 and 6 are started with `asdlc task start` and ended with `asdlc task stop`, which is the first use of both against GitHub itself.

Three things hold for every step:

- "The remote's `main`" is the ref `origin/main`, which `base` in `src/asdlc/io/git.py` already prefers. With no remote it is the local `main`.
- A decision goes in `src/asdlc/domain/build.py` as a function that takes data and returns data. `tests/test_layers.py` fails a domain module that imports `subprocess`, so every git and `gh` call is in `src/asdlc/io/`, and `src/asdlc/cli.py` wires them.
- The tests for steps 2 to 4 run on a real repository with a bare repository on disk as `origin`, and never reach the network. `tests/conftest.py` gains two fixtures. `remote` gives a clone whose `origin` is a bare repository beside it, with `user.name` and `user.email` set, and whose `main` holds an intent, its spec, its plan, two tasks (one of size 2, one of size 8) and `.asdlc/checks`. `gh` gives a stand-in for `gh`: a shell script the fixture writes, set through the git config key `asdlc.gh`, that keeps the open pull requests in a JSON file, appends each call to a record, and can be told to fail on one subcommand.

### Step 1: Try a draft pull request on a branch whose only commit is empty

Groundwork. It delivers no requirement by itself. Step 3 needs its answer: R2 and R3 rest on GitHub opening a draft pull request for a branch that is one empty commit ahead of `main`, and C8 says nobody has checked.

By hand, in this repository:

1. `git switch --no-track -c try/empty-draft origin/main`
2. `git commit --allow-empty -m "Start task try/empty-draft"`
3. `git push -u origin try/empty-draft`
4. `gh pr create --draft --base main --head try/empty-draft --title "Trial: a draft on an empty commit" --body "Tried for intent/building-a-task/plan.md, step 1."`
5. `gh pr close <number> --delete-branch`

`try/empty-draft` is not a branch of the loop, and it changes no file, so the guard allows the push.

Write what happened into the module docstring of `src/asdlc/io/github.py`: that GitHub does or does not open the draft, the date, and the pull request's number. That docstring is the only file this step changes.

When GitHub refuses, stop. R2 and R3 cannot both hold as written, and that goes back to the spec's owner under C8. Step 3 is not started, and this plan does not choose another way.

### Step 2: Read tasks from the remote's `main`, a draft as `claimed`, and the pull request on a task
- delivers: R9, R10, R11, R36

**`src/asdlc/io/git.py`** gains:

- `has_remote(root)`: whether `origin` is configured.
- `fetch(root)`: `git fetch --prune origin` with `GIT_TERMINAL_PROMPT=0` in its environment and `timeout=20` on the `subprocess.run`. It returns whether it worked. `_git` takes no environment and no time limit today, so this is a call of its own.
- `document_texts_at(root, ref, prefix)`: every Markdown file under `<prefix>intent/` at a ref, as `(path from the prefix, text)`, the shape `document_texts` in `src/asdlc/io/files.py` gives. It lists with `git ls-tree -r --name-only` and reads each with `git show <ref>:<path>`.
- `remote_branches(root)`: the names under `refs/remotes/origin`, without the prefix. Step 3 uses it. `branches` is not changed.

**`src/asdlc/io/github.py`**: `open_pull_branches` becomes `open_pulls(root)`. It runs the program named by `git config asdlc.gh`, and `gh` when the key is not set, as `pr list --state open --limit 500 --json headRefName,isDraft,number,url`. It returns one row for each open pull request (branch, number, link, draft or not), and `None` when the program is missing or fails, as today. A row with no `isDraft` reads as not a draft.

**`src/asdlc/domain/tasks.py`**: `Task` gains `pull_request: str`, the link, empty when there is none. `tasks()` gains a keyword `links`, a mapping from a branch to its pull request's link.

**`src/asdlc/cli.py`**:

- `_tasks` calls `open_pulls`. It passes the branches whose pull request is not a draft as `open_pulls`, and every pull request's link as `links`. A draft's branch is in `branches` already, so `_state` gives `claimed` (R11). `_tasks` has four callers, `task list`, `task show`, `intent list` and `intent show`, so the four agree.
- A new `_fetched(options, must)` fetches when the repository has a remote. When the fetch fails it says so on stderr. With `must` it then exits 1, and without it the command carries on with what was last fetched (R10). A repository with no remote is not fetched, and that is not a failure.
- A new `_remote_library(options)` gives the documents the `task` commands read. In a repository with a `main` it calls `document_texts_at` with the ref from `git.base`. Otherwise it calls `_library`, which reads the files, as today (R9).
- `task list` and `task show` call `_fetched(options, must=False)` and then `_remote_library`. `intent list`, `intent show`, `requirement list` and `document check` keep `_library` and do not fetch.

**What a `--root` below the repository's root reads.** C3 leaves this to the plan. `prefix` is `--root` as a path from the repository's root, and the documents are those under `<prefix>intent/` at the remote's `main`. So `asdlc task list --root examples/claims` lists the example's tasks as `main` has them, and a `--root` at the repository's root has an empty prefix. Branches, pull requests and merges are the repository's, as today.

**`src/asdlc/presentation/text.py`** and **`src/asdlc/presentation/data.py`**: `task_record` gains a `pull-request` line and `data.task` a `pull_request` field. Both hold the link, and are empty for a task with none (R36). `task_line` is not changed.

**`README.md`**: the paragraph that starts "State is never stored" says that a draft reads as claimed, that the `task` commands read the remote's `main` and fetch first, and that `task show` gives the pull request.

**Tests.** `tests/io/test_git.py`: the fetch, the documents at a ref, the remote's branches. `tests/io/test_github.py`: `open_pulls` with the stand-in, the `asdlc.gh` key, and `None` when the program fails or is missing. The two `gh` tests in `tests/io/test_git.py` move there. `tests/domain/test_tasks.py`: a task carries its link. `tests/presentation/test_text.py`: the new line. `tests/test_cli.py`: a task on an unmerged `tasks/<slug>` branch that is checked out is not listed; a branch pushed from a second clone reads `claimed` with no `git fetch` run by hand; a draft reads `claimed` and a ready pull request `in review`, in `task list`, `task show`, `intent show` and `intent list --json`; a fetch that fails warns and still lists; `--root examples/claims` lists the example's two tasks. `tests/test_walk.py`: its stand-in for `gh` answers with `isDraft`, and the walk gains a draft that reads `claimed`.

### Step 3: `asdlc task start`
- delivers: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10

Needs step 2's readers, and step 1's answer. R9 and R10 are here as well because they name `task start`: it reads through `_remote_library`, and calls `_fetched(options, must=True)`.

**`.asdlc/checks`**: one line, `just check`. No task can be started in this repository until this file is on `main` (R4, C4), so it lands here.

**`src/asdlc/domain/build.py`** (new) holds:

- `check_lines(text)`: the command lines of a checks file. A line that is empty or starts with `#` is no command line, and a file with none counts as missing.
- `refusal(...)`: why a task cannot be started, or `None`. It takes the task's state as the remote alone gives it, its pull request if any, whether its `task.md` is in the checkout or on the remote's `tasks/<slug>`, and whether `--resume` was given. It words each reason in R5 and R8. A claimed or in-review task's reason gives its pull request, or says it has none and that `--resume` opens one. A task that is not on the remote's `main` names the merge it waits for.
- `claimed(porcelain, branch)`: whether a push made the branch. True only when the line for `refs/heads/<branch>` in `git push --porcelain` output begins with `*`. `=` and `!` lost (R6).
- `leftover(commits)`: whether a local branch holds nothing but a start commit, so a start that was cut short can use it again (R5).

**`src/asdlc/io/git.py`** gains: `main_checkout(root)`, the root of the main checkout, from `git rev-parse --path-format=absolute --git-common-dir`; `exclude(root, pattern)`, which adds a line to `info/exclude` under that folder once; `add_worktree(root, path, branch, ref)`, which is `git worktree add --no-track -b <branch> <path> <ref>`, or without `-b` for a branch that exists; `remove_worktree` and `delete_branch`; `push_claim(worktree, branch)`, which is `git push --porcelain -u --force-with-lease=<branch>: origin <branch>` and gives back what it printed; `delete_remote(root, branch, commit)`, which is `git push --force-with-lease=<branch>:<commit> origin :<branch>`; `fast_forward(worktree, ref)`, which is `git merge --ff-only`; `clean(worktree)`, which is whether `git status --porcelain` prints nothing; and `commits(root, range)`, the commits of a range oldest first, each with its id, its subject and the files it changed, without merge commits.

**`src/asdlc/io/github.py`** gains `open_draft(root, branch, title, body)`, which is `pr create --draft --base main --head <branch> --title <title> --body <body>` and gives the link it prints, and `set_ready(root, number, ready)`, which is `pr ready <number>`, with `--undo` for a draft.

**`src/asdlc/presentation/pull.py`** (new): `description(task)` words the pull request's description. It names `intent/<slug>/tasks/<task>/task.md` and each requirement the task delivers (R3).

**`src/asdlc/cli.py`** gains `task start <slug>/<task>` with the switch `--resume`. In order:

1. `_split` the target. `_fetched(options, must=True)`.
2. Refuse, exit 1, before anything is made (R4): no remote; `open_pulls` gives `None`; `check_lines` of `.asdlc/checks` at `origin/main` is empty.
3. Read the tasks with `_remote_library`, and their states from `remote_branches`, the pull requests and the merges on `origin/main`. A target that names a task found in none of the remote's `main`, the checkout and the remote's `tasks/<slug>` exits 3. Otherwise ask `refusal`, and exit 1 with its reason (R5).
4. Add `.worktrees/` to the exclude file. Make the worktree `.worktrees/<slug>/<task>` under `main_checkout`, on a new branch at `origin/main` with no upstream (R1). A local branch that `leftover` accepts is used again, and any other local branch of that name is refused and named.
5. `commit_empty(worktree, "Start task <slug>/<task>")`, unless the leftover branch has it (R2).
6. `push_claim`. When `claimed` says no, remove the worktree and the local branch, fetch, and exit 1 naming the winner's pull request when there is one (R6).
7. `open_draft`, titled `Task: <the task's title>` (R3). When it fails, `delete_remote` with a lease on the start commit, remove the worktree and the local branch, say why on stderr and exit 1. When the undoing fails as well, say what is left and that `asdlc task start --resume` finishes the start (R7).
8. Print one line, tab-separated: the worktree's path, the branch, the pull request's link. With `--json`, one object with `worktree`, `branch` and `pull_request`.

With `--resume` (R8): refuse a task whose branch is not on the remote, and one that is `done`. When the worktree is there and `clean`, `fast_forward` it to `origin/<branch>`, and when that fails say why and change nothing. When there is no worktree, make one on the branch at `origin/<branch>`. Open the draft when the branch has no pull request, and `set_ready(..., ready=False)` when it has one that is ready. Print the same line.

R4 can tell beforehand that `gh` is missing, signed out or has no GitHub remote, because `pr list` fails for each. It cannot tell that a repository refuses drafts. That is found at step 7 of the list above and undone under R7.

**`README.md`**: the command table gains `asdlc task start`, and the page says what `.asdlc/checks` is.

**Tests**, in `tests/test_task_start.py`, on the `remote` and `gh` fixtures: the worktree, the branch with its own upstream, the start commit and its subject, the checkout left on its branch, the printed line; the draft's title, base and description read from the stand-in's record; each refusal of R4 leaves no branch and no worktree; each state of R5, the task that waits for its merge, and exit 3; the leftover branch used again, and one with work on it refused; a start from a second clone after the first loses, and the remote's branch is the first's commit; `gh` failing on `pr create` leaves no branch on the remote, no worktree and no local branch; each line of R8; a fetch that fails exits 1; and `asdlc plan new <slug>/<task> --root <the worktree>` writes the plan inside the worktree. `tests/domain/test_build.py` covers `check_lines`, `refusal`, `claimed` and `leftover` with plain data. `tests/presentation/test_pull.py` covers `description`.

### Step 4: `asdlc task stop`
- delivers: R10, R12, R13, R14, R15, R16, R17, R18, R19, R20

Needs step 3: the worktree, the checks file and the pull request are what `task start` leaves.

**`src/asdlc/io/checks.py`** (new): `run(line, folder)` runs one command line as `sh -c <line>` in a folder and gives back its exit status and what it printed, stdout and stderr together in the order they came.

**`src/asdlc/io/git.py`** gains: `file_at(root, ref, path)`, a file's text at a ref or `None`; `merge(worktree, ref)`, which is `git merge --no-edit <ref>` and gives back whether it was clean; `conflicts(worktree)`, the files `git diff --name-only --diff-filter=U` lists; `push(worktree, branch)`, a plain push that says whether the remote refused it for a commit the worktree lacks; `head(worktree)`; and `messages(worktree, range, path)`, the message of each commit in a range that changed a path.

**`src/asdlc/io/github.py`** gains `comment(root, number, body)`, which is `pr comment <number> --body-file -` with the body on stdin.

**`src/asdlc/domain/build.py`** gains:

- `plan_only(size, commits, slug, task)`: R20's case, a task of size 8 whose commits after the start are one that adds `intent/<slug>/tasks/<task>/plan.md` and nothing else.
- `faults(size, commits, slug, task)`: the commits that break R18 or R19, each with the rule it breaks. For R18, a commit that changes `intent/<slug>/plan.md` and no file outside `intent/`. For R19, when the size is 8, the first commit after the start when it is not the task's own plan alone. A commit with the start's subject and no file is the start. `commits` comes without merge commits, so they are passed over.
- `stand_ins(text, worktree, checkout, home)`: the output with the three paths replaced by `<worktree>`, `<repository>` and `~`, longest path first, because the worktree is inside the checkout (R13, C7).
- `fitted(outputs, limit)`: each output cut from the top, on a line, with the number of lines cut, so that together they fit. The limit is 60,000 characters shared equally between the checks. GitHub refuses a comment over 65,536.
- `outcome(statuses, faults)`: `ready` when every check exited 0 and nothing is at fault, otherwise `draft`.

**`src/asdlc/presentation/pull.py`** gains `comment(...)`: the commit the checks ran on; for each check its command line, its exit status and its output in a fenced block; each rule of R18 and R19 that failed; each file the guard marked, with the message of the commit that changed it; and the text of `--message`. It also gains `plan_comment()`, which says the plan is there to be read (R20).

**`src/asdlc/cli.py`** gains `task stop <slug>/<task>` with `--message <text>`. It finds the worktree at `.worktrees/<slug>/<task>` under `main_checkout`, wherever it is run from, and exits 3 when there is none. In order:

1. Refuse a worktree that is not `clean`, untracked files included (R14). `_fetched(options, must=True)` (R10).
2. Read `.asdlc/checks` with `file_at(root, "origin/main", ".asdlc/checks")`. When `check_lines` gives none, exit 1 and say so (R12). This is ahead of the merge so that nothing at all is run or pushed.
3. Refuse a branch that changes no file against `origin/main` (R14).
4. `merge` `origin/main`. When it conflicts, leave the merge as git left it, print `conflicts`, exit 1 (R15).
5. Read the task's size from the `task.md` on `origin/main`, and the branch's `commits` in `origin/main..HEAD`. When `plan_only`: push, post `plan_comment`, print the link and `plan`, exit 0 (R20).
6. Ask `guard` from `src/asdlc/domain/guard.py` about `changed_since(worktree, "origin/main")`. On a denial print the rulings with `text.ruling_line`, exit 1 (R16).
7. Ask `faults`. When a commit at fault is in `origin/<branch>..HEAD`, so not on the remote yet, name it and the rule, exit 1, push nothing (R18, R19).
8. Run every line with `checks.run` in the worktree, in order, all of them (R12).
9. `push`. When the remote has a commit the worktree lacks, exit 1, post nothing, and say `asdlc task start --resume` brings the worktree up (R16).
10. Post `comment` (R13). It is added and never edited.
11. `set_ready` by `outcome`. Print the link and `ready` or `draft`, tab-separated. Exit 0 for `ready` and 1 for `draft` (R17).

**`README.md`**: the command table gains `asdlc task stop`, and "When each thing runs" gains a row for it.

**Tests**, in `tests/test_task_stop.py`, each starting from a task that `task start` started on the fixtures: a passing check gives `ready`, exit 0, one comment with the command line, the status, the output and the commit; a failing check gives `draft` and exit 1, with the branch pushed and the comment posted; a later failing run makes a ready pull request a draft again; the checks are read from `main` when the branch's copy of `.asdlc/checks` says `true`; every line runs when the first fails; no checks on `main` runs, pushes and posts nothing; uncommitted and untracked files, and a branch with no change, are refused; `main` moved with no conflict is merged and committed; a conflict prints the files and leaves the merge; a branch that changes `intent/<slug>/spec.md` prints the guard's line and pushes nothing; the remote ahead of the worktree; a plan-only commit not yet pushed is refused and named, and one already pushed gives a draft whose comment names the rule; a size 8 whose first commit is code; a size 8 with only its plan gives `plan`, exit 0, no check run; the three stand-ins in the posted output; an output cut from the top with its count; a marked `plan.md` in the comment with its commit's message; `--message` in the comment; a fetch that fails exits 1. `tests/domain/test_build.py`, `tests/io/test_checks.py`, `tests/io/test_git.py`, `tests/io/test_github.py` and `tests/presentation/test_pull.py` cover the new functions.

### Step 5: The skill, the two cases `just check` needs, and the README
- delivers: R21, R22, R23, R24, R25, R26, R27, R28, R29, R30, R31, R34, R35

Needs step 4. One step, because `tests/test_evals.py` fails `just check` on a skill that lands without a case where it acts and one where it stays out.

**The skill.** `plugins/asdlc/skills/building-a-task/SKILL.md`. Load `authoring-kit:authoring-skills` before writing it. Its frontmatter is what the spec's design gives, field for field:

- `description`: what it does, then when to load it (building a task, starting work on one, picking up a task's pull request), then the traps: making the branch by hand, building in the main checkout, saying the checks pass without showing their output, editing a failing test, marking the pull request ready by hand, merging.
- `argument-hint: <slug>/<task>`.
- `allowed-tools`: `Bash(asdlc task show *)`, `Bash(asdlc task list *)`, `Bash(asdlc plan new *)` and `Bash(asdlc task stop *)`. Not `asdlc task start`, so a wrong load meets a permission prompt (C5).
- No `context`, no `disable-model-invocation`, no `hooks`.

Its body is the eight steps of the spec's design under numbered headings, as the four skills on `main` have theirs, and holds all of R22 to R34, the parts step 6 judges included. It says never to run `gh pr merge` or `gh pr ready`, never to push, and never to change a failing check.

**The scaffold both cases share.** Written out in full in each `scaffold.sh`, with plain git, as `plugins/asdlc/evals/tasks-wait-for-the-merge/scaffold.sh` is. It starts from that file's repository: `claims_gateway.py`, `portal/adjuster_view.py`, `tests/test_adjuster_view.py` and the intent `claim-steps` with its spec, each merged with `git merge --no-ff`. On top of that:

- `.asdlc/checks` on `main`, one line, `sh check.sh`. `check.sh` is a shell script on `main`, because `plugins/asdlc/scripts/install` says an eval run cannot start the machine's Python.
- A bare repository at `.git/origin.git`, added as `origin` by its absolute path, with every branch pushed to it.
- A stand-in for `gh` at `.git/gh`, with `git config asdlc.gh` set to its absolute path. It keeps the open pull requests in a JSON file, answers `pr list` from it, and appends each call to `.git/gh-calls`. It also touches an empty file named for the kind of call, under `.git/gh-called/`: `create-draft`, `comment`, `ready`, `ready-undo`, `merge`.

**`build-a-ready-task`**, tagged `building-a-task` and `acts`. `main` also holds a plan and one task of size 1, `claim-steps/01-step-name`, that changes one line of `portal/adjuster_view.py`, and `check.sh` passes only with that line. The prompt is "Please build claim-steps/01-step-name." Graders: the skill loaded; `asdlc task start claim-steps/01-step-name` ran (R22); no `git worktree add`, `git switch -c`, `git checkout -b`, `git branch`, `git push` or `gh pr create` ran (R22, R30); `asdlc task stop` ran (R30); no `gh pr merge` and no `gh pr ready` ran (R31); a file was created or changed under `.worktrees/claim-steps/01-step-name/` and `portal/adjuster_view.py` in the main checkout was not (R24); the answer holds the pull request's link and `ready` (R34). The stand-in's record has a draft opened, a comment, a `ready` and no merge.

**Pilot before any other grader.** Write this case with the `skill-loaded` grader alone and run `just eval --case build-a-ready-task --runs 1 --ablation none`. Read what the run wrote. It settles what C8 says is not known: whether the remote under `.git/` and the stand-in work inside a run's sandbox, and whether a grader can read `.git/gh-calls` or the marker files beside it. The cases on `main` show only three pattern graders: `regex` on the answer, `regex` with `target: files` on the paths created, and `file_exists`. When no grader can read under `.git/`, move the record and the markers to a folder beside the scaffold's `README.md` and try once more. When the sandbox stops the push itself, stop and say so in the pull request: the cases cannot be written as designed, and that is C8's owner's to decide.

**`build-waits-for-the-merge`**, tagged `building-a-task` and `stays-out`. The task is committed on `tasks/claim-steps`, pushed, and not merged. The prompt asks for it to be built. Graders: no path under `.worktrees/` was created; no `git worktree add` and no `git switch`, `git checkout` or `git branch` naming `task/` ran; no `git merge` and no `gh pr merge` ran; the record has no create, comment, ready or merge; the answer says "merge" (R23). It follows `plugins/asdlc/evals/tasks-wait-for-the-merge/case.yaml` grader for grader where they match.

**`README.md`**: the table under "Skills and their evals" gains a row for `building-a-task`. Under "What is built, and what is not", "Four skills" becomes five, the built list gains `task start`, `task stop` and `.asdlc/checks`, and the line "**The other skills.**" is rewritten to say what is still not built: a hook that refuses a merge (C2), a worker agent that gives each task a fresh context (C1), starting several tasks at once, and removing a worktree (C9).

When a pilot run shows the skill's wording does not hold, change the wording, not the grader.

### Step 6: The case with a check that fails, and the case with a question
- delivers: R32, R33

Needs step 5's skill and its scaffold. Adds two cases, both tagged `building-a-task`.

**`build-with-a-check-that-fails`**, tagged `acts`. The task says to change `portal/adjuster_view.py` and to leave `claims_gateway.py` alone, and `check.sh` cannot pass unless `claims_gateway.py` changes. Graders: `claims_gateway.py` and `check.sh` in the worktree are not among the files changed (R32); `asdlc task stop` ran with `--message` (R33); the record has a comment, no `ready` other than `ready-undo`, and no merge (R31, R33); the answer says `draft` and what failed.

**`a-question-about-a-ready-task`**, tagged `stays-out`. The scaffold of `build-a-ready-task`, and the prompt asks what building the task would involve. Graders: no path under `.worktrees/` was created; `asdlc task start` did not run; the record has no create, comment, ready or merge. This is the wrong load C5 accepts.

When a pilot run shows the skill's wording does not hold, this step changes `plugins/asdlc/skills/building-a-task/SKILL.md` too. The count of eval cases in `README.md` goes up by two.

## Risks

- **Step 3 is the riskiest.** It is the only step that publishes: it pushes a branch and opens a pull request, and it has to undo both. Its tests run against a bare repository and a stand-in, so GitHub itself is first met when the task for step 5 is started. Step 1 takes the largest unknown out beforehand. Three things are still shown by no test: a repository that refuses drafts, found only when `pr create --draft` fails and R7 undoes the start (C6); a race between two real clones, which the tests play one after the other; and `gh pr ready --undo` and `gh pr comment --body-file -` as GitHub's own `gh` takes them.
- **Step 1 can end the plan.** If GitHub will not open a draft on an empty commit, R2 and R3 conflict and the spec has to change (C8).
- **Reading from the remote changes what people see** (C3). After step 2 a task on an unmerged `tasks/<slug>` branch is no longer listed, a draft opened by hand reads `claimed`, and `task list` is slower by a fetch. `intent list` and `requirement list` still read the working tree, so in a clone that is behind they can disagree with `task list`. `--root` below the repository's root reads that folder at the remote's `main`, which is this plan's answer to C3's last paragraph, and a reviewer should check it is the one wanted.
- **A worktree inside the checkout is seen by the checkout's own tools.** `.worktrees/` is in `info/exclude` and not in `.gitignore`. If `uv run ruff format --check .` in the main checkout reads the worktrees all the same, `just check` there fails on another task's unfinished code. Step 3 runs `just check` in the main checkout with a worktree present. If it fails, step 3 also adds `extend-exclude = [".worktrees"]` to `pyproject.toml`, and says so in its pull request.
- **The checks run in a fresh worktree.** `just check` there starts with no `.venv`, so the first `task stop` is slow, and it needs the network once. A check that leaves an untracked file that is not ignored makes the next `task stop` refuse under R14.
- **The builder can still weaken what a check runs** (C4). `task stop` takes the lines from `main`, and a branch can change the tests, the `justfile` and the workflow those lines run. Only the skill's wording, CI and the reviewer stand against that. `build-with-a-check-that-fails` checks one file and one run.
- **Nothing stops a merge or a `gh pr ready` by hand** (C2). Until the hooks' own intent is built, the cases' record of `gh` calls is the only check.
- **What a check prints is posted** (C7). `stand_ins` replaces three paths and nothing else.
- **The eval cases may not run as designed** (C8). The pilot in step 5 comes before any other grader for that reason. Seven things have no case: R25, R26, R27, R28, R29, the `--resume` half of R22 and the split R33 proposes. A fault in that wording is found by a person reading the skill, or the first time a task needs it.
- **An inline builder sees the whole session** (C1), and **the four skills on `main` pre-approve `asdlc task start`** through `Bash(asdlc *)` (C5). Neither is changed here.
- **Worktrees and local branches pile up** (C9). Nothing removes one.
- **`README.md` changes in steps 2, 3, 4, 5 and 6.** The steps are built in order, so the edits do not meet. If two are ever built at once, the second to merge resolves the conflict.
- **The suite grows to seventeen cases.** With three runs each, with the plugin and without it, that is 102 runs. `just eval --tag building-a-task` runs this skill's four.

## Proof

`just check` passes at the end of every step, with its output in the step's pull request. For steps 5 and 6 that output is the comment `asdlc task stop` posts. Every case is piloted with one run, then run three times with `just eval --tag building-a-task`, and the report goes in the pull request.

- **R1, R2.** `tests/test_task_start.py`: the worktree at `.worktrees/<slug>/<task>`, the branch at `origin/main` with no upstream before the push, the checkout left on its branch, the start commit's subject and empty diff, the printed line.
- **R3.** `tests/test_task_start.py`: the stand-in's record holds `pr create --draft --base main` with the title and the description, and the branch's upstream is `origin/task/<slug>/<task>`. Against GitHub: the draft pull requests of the tasks for steps 5 and 6.
- **R4.** `tests/test_task_start.py`: no remote, a failing `gh`, and no checks on `main`, each with exit 1 and no branch or worktree left.
- **R5.** `tests/test_task_start.py`: each of the four states refused with its reason, the task that waits for its merge, exit 3, and both leftover branches. `tests/domain/test_build.py`: `refusal` and `leftover`.
- **R6.** `tests/test_task_start.py`: two clones of one bare repository, where the second start exits 1, leaves no worktree and no local branch, and the remote's branch is unchanged. `tests/domain/test_build.py`: `claimed` on `*`, `=` and `!`.
- **R7.** `tests/test_task_start.py`: the stand-in fails on `pr create`, and the remote has no branch, and the clone no worktree and no local branch. A second test moves the remote's branch first and shows it is not deleted.
- **R8.** `tests/test_task_start.py`: a test for each of its four lines.
- **R9.** `tests/test_cli.py`: a task on a checked-out, unmerged `tasks/<slug>` branch is not listed; a repository with no remote reads the local `main`; a folder that is no repository reads its files; `--root examples/claims`.
- **R10.** `tests/test_cli.py`: a branch pushed from a second clone reads `claimed` with no fetch by hand, and an unreachable remote warns on stderr and still lists. `tests/test_task_start.py` and `tests/test_task_stop.py`: the same remote makes each exit 1. `tests/io/test_git.py`: the fetch returns within its limit.
- **R11.** `tests/test_cli.py`: a draft reads `claimed` and a ready pull request `in review`, in all four commands. `tests/test_walk.py`: the walk.
- **R12.** `tests/test_task_stop.py`: the branch's own `.asdlc/checks` is not what runs; every line runs; no checks on `main`. `tests/io/test_checks.py`: `run`.
- **R13.** `tests/test_task_stop.py`: the comment in the stand-in's record. `tests/domain/test_build.py`: `stand_ins` and `fitted`. `tests/presentation/test_pull.py`: `comment`. Against GitHub: the comments on the pull requests of the tasks for steps 5 and 6.
- **R14, R15, R16, R17.** `tests/test_task_stop.py`: the tests step 4 lists for each.
- **R18, R19.** `tests/domain/test_build.py`: `faults`, with merge commits left out. `tests/test_task_stop.py`: the commit not yet pushed is refused and named, and the one already pushed gives a draft with the rule in its comment.
- **R20.** `tests/test_task_stop.py`: `plan`, exit 0, a comment, and a check that would have left a file did not run.
- **R21.** The `skill-loaded` grader in `build-a-ready-task`, from a prompt that does not name the skill. That it is inline: `context` is absent from the frontmatter, read by step 5's reviewer.
- **R22.** In `build-a-ready-task`: `asdlc task start` ran, and no branch, worktree or pull request was made by hand. The `--resume` half has no case (C8) and is read in the skill.
- **R23.** `build-waits-for-the-merge`. The half with no task named is read in the skill.
- **R24.** In `build-a-ready-task`: the change is under `.worktrees/` and the main checkout's copy is as it was.
- **R25, R26, R27, R28, R29.** No case (C8). Step 5's reviewer reads the skill against each requirement's text. R26's command is shown by the `asdlc plan new` test in `tests/test_task_start.py`. Each is first seen working when a task needs it.
- **R30, R31.** In `build-a-ready-task` and `build-with-a-check-that-fails`: `asdlc task stop` ran, no `git push`, no `gh pr merge`, no `gh pr ready`, and the stand-in's record holds no merge.
- **R32.** In `build-with-a-check-that-fails`: the file the task says to leave, and `check.sh`, are unchanged.
- **R33.** In `build-with-a-check-that-fails`: `--message` was given and the pull request is a draft with a comment. The proposed split has no case (C8).
- **R34.** The answer patterns in `build-a-ready-task` and `build-with-a-check-that-fails`.
- **R35.** `just check`: `test_every_skill_in_the_plugin_has_both_kinds_and_no_case_is_judge_only` in `tests/test_evals.py` reads the new skill and its cases.
- **R36.** `tests/presentation/test_text.py`: the `pull-request` line. `tests/test_cli.py`: `task show --json` has `pull_request`, and both are empty for a task with none.
