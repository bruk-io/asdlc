---
kind: plan
---
# Plan: Build a ready task into a pull request

## Files that change

- .asdlc/checks (new)
- .gitignore
- CLAUDE.md
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
- tests/test_evals.py
- tests/test_layers.py
- tests/test_task_start.py (new)
- tests/test_task_stop.py (new)
- tests/test_templates.py (new)
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

Seven steps. Steps 1 and 2 are how tasks are read and `task start`. Step 3 is `task start --resume`. Steps 4 and 5 are `task stop`: first the checks, the comment and ready or draft, then its rules about commits. Steps 6 and 7 are the skill and its eval cases.

What each step needs:

- Step 2 needs step 1.
- Steps 3 and 4 each need step 2, and neither needs the other, so they can be built side by side.
- Step 5 needs step 4.
- Step 6 needs steps 3, 4 and 5, because the skill's text names what each of them builds.
- Step 7 needs step 6.

No hook, no template, `src/asdlc/domain/guard.py` and `asdlc branch new` are not changed. `_state` in `src/asdlc/domain/tasks.py` is not changed either.

Three things were tried before this plan was accepted, so no step waits on them:

- **A trial against GitHub**, on 2026-11-18, pull request #101, now closed. GitHub opens a draft pull request on a branch whose only commit is empty. The claiming push printed `*` for a new branch and `=` when run again. `gh pr list --json headRefName,isDraft,number,url`, `gh pr comment --body-file -`, `gh pr ready` and `gh pr ready --undo` all work. The leased delete removed the branch, and GitHub then closed the pull request by itself.
- **A pilot inside an eval run**, on 2026-11-18, with a throwaway plugin. A bare repository under `.git/`, named as `origin` by its absolute path, takes a fetch and a push. A stand-in program named through git config is run. Graders read the stand-in's record under `.git/`, with `file_exists` and with `regex` and `source: file`. `git worktree add` is refused there.
- **One kept run of a case on `main`**, on 2026-11-19. The run's folder held one thing the scaffold did not make: `.claude/.cc-writes/`, an empty folder, which git does not report. So the folder reads as clean to R4 at the start of a run. Whether a file appears there once the model has written one is not known, so each new scaffold ignores `.claude/` (step 6).

This intent's own tasks cannot all be built with what it builds. The tasks for steps 1 to 5 are started by hand with `asdlc branch new task/building-a-task/<task>`, as the generate-tasks tasks were. The tasks for steps 6 and 7 are started with `asdlc task start` and ended with `asdlc task stop`, which is the first use of both against GitHub itself.

Six things hold for every step:

- "The remote's `main`" is the ref `origin/main`, which `base` in `src/asdlc/io/git.py` already prefers. With no remote it is the local `main`.
- No command reads a branch's upstream. Each names the remote's branch, `origin/task/<slug>/<task>`, outright, because a sandboxed session may not be able to record one.
- A decision goes in `src/asdlc/domain/build.py` as a function that takes data and returns data. `tests/test_layers.py` fails a domain module that imports `subprocess`, so every git and `gh` call is in `src/asdlc/io/`, and `src/asdlc/cli.py` wires them.
- `src/asdlc/io/` and `src/asdlc/domain/` import nothing from each other, and `src/asdlc/cli.py` is the one module that imports from both. This is the requester's rule of 2026-11-21, made after step 2's first piece had `io` import three records and two functions from `domain`. `io` hands back plain values: a row for each commit and for each open pull request. `cli.py` turns them into the domain's records. `tests/test_layers.py` fails an `io` module that imports from `domain`, any module but `cli.py` that imports from both, a module outside the layers, a relative import, and a test under `tests/io` or `tests/domain` that imports the other layer.
- A command reads once, decides, then acts. `read_start` in `src/asdlc/cli.py` reads what the command needs into one record of plain data, with one call into `io` for each fact. A function in `src/asdlc/domain/build.py` turns that record into a refusal or into what to do. `src/asdlc/cli.py` then does it, and reads nothing more to decide by. So a command that refuses has made nothing, because it acts only on an answer that is not a refusal.
- A test is at the level of what it checks, and none reaches the network. This was changed on 2026-11-21, while step 2 was built: the plan had every test of steps 1 to 5 run a whole command on a real repository, and the suite went from 32 seconds to 60 on the requester's machine with about half of the new tests checking a decision.
  - A decision is a unit test on plain data in `tests/domain/`, with no git: every refusal, its reason and its exit status. Where a step below lists a test of a refusal or of a reason, this is what it means.
  - What is read is checked once, in `tests/test_task_start.py`, in a real clone where every fact differs from its default.
  - A test runs a whole command on a real repository only when git's own behaviour is what it checks: the branch a command makes, a push, a merge, a worktree, and a checkout put back after a step fails. These use a bare repository on disk as `origin`.

  `tests/conftest.py` gains two fixtures, and step 1 builds both. `remote` gives a clone whose `origin` is a bare repository beside it, with `user.name` and `user.email` set, and whose `main` holds an intent, its spec, its plan, two tasks (one of size 2, one of size 8) and `.asdlc/checks`. `gh` gives a stand-in for `gh`: a shell script the fixture writes, set through the git config key `asdlc.gh`, that keeps the open pull requests in a JSON file, appends each call to a record, and can be told to fail on one subcommand. The script, the JSON file and the record are beside the clone and not inside its working tree, where they would be untracked files that R4 and R14 refuse. Step 1 uses only its `pr list`. Steps 2 and 4 use the rest.

### Step 1: Read tasks from the remote's `main`, a draft as `claimed`, and the pull request on a task
- delivers: R9, R10, R11, R36

**`src/asdlc/io/git.py`** gains:

- `has_remote(root)`: whether `origin` is configured.
- `fetch(root)`: `git fetch --prune origin` with `GIT_TERMINAL_PROMPT=0` in its environment and `timeout=20` on the `subprocess.run`. It returns whether it worked. `_git` takes no environment and no time limit today, so this is a call of its own.
- `document_texts_at(root, ref, prefix)`: every Markdown file under `<prefix>intent/` at a ref, as `(path from the prefix, text)`, the shape `document_texts` in `src/asdlc/io/files.py` gives. It lists with `git ls-tree -r --name-only` and reads each with `git show <ref>:<path>`.
- `remote_branches(root)`: the names under `refs/remotes/origin`, without the prefix. Step 2 uses it. `branches` is not changed.

**`src/asdlc/io/github.py`**: `open_pull_branches` becomes `open_pulls(root)`. It runs the program named by `git config asdlc.gh`, and `gh` when the key is not set, as `pr list --state open --limit 500 --json headRefName,isDraft,number,url`. It returns one row for each open pull request (branch, number, link, draft or not), and `None` when the program is missing or fails, as today. A row with no `isDraft` reads as not a draft. The module's docstring gains one line: that GitHub opens a draft pull request on a branch whose only commit is empty, tried on 2026-11-18 with pull request #101.

**`src/asdlc/domain/tasks.py`**: `Task` gains `pull_request: str`, the link, empty when there is none. `tasks()` gains a keyword `links`, a mapping from a branch to its pull request's link.

**`src/asdlc/cli.py`**:

- `_tasks` calls `open_pulls`. It passes the branches whose pull request is not a draft as `open_pulls`, and every pull request's link as `links`. It adds each draft's branch to `branches`, so `_state` gives `claimed` (R11). A clone that has fetched has that branch already, but `intent list` and `intent show` do not fetch, so the branch is named outright. `_tasks` has four callers, `task list`, `task show`, `intent list` and `intent show`, so the four agree.
- A new `_fetched(options, must)` fetches when the repository has a remote. When the fetch fails it says so on stderr. With `must` it then exits 1, and without it the command carries on with what was last fetched (R10). A repository with no remote is not fetched, and that is not a failure.
- A new `_remote_library(options)` gives the documents the `task` commands read. In a repository with a `main` it calls `document_texts_at` with the ref from `git.base`. Otherwise it calls `_library`, which reads the files, as today (R9).
- `task list` and `task show` call `_fetched(options, must=False)` and then `_remote_library`. `intent list`, `intent show`, `requirement list` and `document check` keep `_library` and do not fetch.

**What a `--root` below the repository's root reads.** C3 leaves this to the plan. For `task list` and `task show`, `prefix` is `--root` as a path from the repository's root, and the documents are those under `<prefix>intent/` at the remote's `main`. `inside` in `src/asdlc/io/files.py` gives `.` for a root at the top, and that is read as no prefix. Branches, pull requests and merges are the repository's, as today. `task start` and `task stop` refuse a `--root` below the top (steps 2 and 4).

**`src/asdlc/presentation/text.py`** and **`src/asdlc/presentation/data.py`**: `task_record` gains a `pull-request` line and `data.task` a `pull_request` field. Both hold the link, and are empty for a task with none (R36). `task_line` is not changed.

**`README.md`**: the paragraph that starts "State is never stored" says that a draft reads as claimed, that the `task` commands read the remote's `main` and fetch first, and that `task show` gives the pull request.

**Tests.**

- `tests/io/test_git.py`: the fetch, the documents at a ref, the remote's branches.
- `tests/io/test_github.py`: `open_pulls` with the stand-in, the `asdlc.gh` key, and `None` when the program fails or is missing. The two `gh` tests in `tests/io/test_git.py` move there.
- `tests/domain/test_tasks.py`: a task carries its link.
- `tests/presentation/test_text.py`: the new line.
- `tests/test_cli.py`, on the `remote` fixture:
  - a task on an unmerged `tasks/<slug>` branch that is checked out is not listed;
  - a clone whose local `main` is behind the remote's lists the task the remote's `main` has, which catches reading the local `main`;
  - a branch pushed from a second clone reads `claimed` with no `git fetch` run by hand;
  - a draft reads `claimed` and a ready pull request `in review`, in `task list`, `task show`, `intent show` and `intent list --json`;
  - a fetch that fails warns and still lists;
  - a `--root` at a folder below the top, which holds an `intent/` of its own on `main`, lists that folder's tasks. This is tried inside the fixture and not on `examples/claims`, whose repository has GitHub as its `origin`.
- `tests/test_walk.py`: its stand-in for `gh` answers with `isDraft`, and the walk gains a draft that reads `claimed`.

### Step 2: `asdlc task start`
- delivers: R1, R2, R3, R4, R5, R6, R7, R9, R10

Needs step 1's readers. R9 and R10 are here as well because they name `task start`: it reads through `_remote_library`, and calls `_fetched(options, must=True)`.

**`.asdlc/checks`**: one line, `just check`. No task can be started in this repository until this file is on `main` (R4, C4), so it lands here.

**`.gitignore`** gains `.claude/worktrees/` and `.DS_Store`, as the spec's Design says, so the main checkout reads as clean to R4.

**`CLAUDE.md`**: the line for `src/asdlc/io/` says it reads files, git and GitHub and decides nothing. After this step it also pushes and opens a pull request, so the line says that it reads and writes them and still decides nothing.

**`src/asdlc/domain/build.py`** (new) holds:

- `check_lines(text)`: the command lines of a checks file. A line that is empty or starts with `#` is no command line, and a file with none counts as missing.
- `refusal(...)`: why a task cannot be started, or `None`. It takes the tasks on the remote's `main`, each with its state as the remote alone gives it and its pull request if any. A task that is not among them is one the command found in the checkout or on the remote's `tasks/<slug>`. It words each reason in R5. A claimed or in-review task's reason gives its pull request, or says it has none and that `--resume` opens one. A task that is not on the remote's `main` names the merge it waits for. It also takes the branch the checkout is on and which branches other worktrees hold, and words R4's two reasons about them: a checkout on the branch of another task that reads `claimed`, and a task whose branch another worktree has checked out.
- `claimed(porcelain, branch)`: whether a push made the branch. True only when the line for `refs/heads/<branch>` in `git push --porcelain` output begins with `*`. `=` and `!` lost (R6).
- `answer(porcelain, branch)`: the one character that line begins with, which `claimed` asks.
- `lost_claim(id, flag, pulls)`: the reason for a start whose push claimed nothing. For `=` and `!` it says another start claimed the task first, which of the two the remote answered, and that start's pull request when it has one.
- `unopened(id, deleted)`: the reason for a start whose pull request could not be opened: that the branch is off the remote again, or that it is left there and `asdlc task start --resume` finishes the start.
- `leftover(commits)`: whether a local branch holds at most a start commit, so a start that was cut short can use it again (R5).
- `Found`: the record the command decides from. The remote and its `main`, the open pull requests, the checks file and the documents on the remote's `main`, the remote's branches and the merges on its `main`, the uncommitted paths, the branch the checkout is on, the branches other worktrees hold, where the task's `task.md` was found, and what a local branch of the task's name holds.
- `start(id, found, documents)`: what the command does. It gives a `Start`, which says whether a leftover branch is used again and whether it has its start commit, or a `Refused` with the reason and one of three endings: refused, a target that matched nothing, or no `main`. It holds the refusals of item 2 in the list below, and asks `refusal` and `leftover`.

**`src/asdlc/io/git.py`** gains:

- `uncommitted(root)`: the paths `git status --porcelain` lists. Untracked files are among them and ignored ones are not. None means the checkout is clean.
- `position(root)`: the branch the checkout is on, or the commit when it is on none, so a start can put it back.
- `switch_back(root, position)`: puts the checkout back on that branch or that commit.
- `file_at(root, ref, path)`: a file's text at a ref, or `None`. The start reads `.asdlc/checks` on the remote's `main` with it.
- `checked_out(root)`: each branch that a worktree of the clone has checked out, with that worktree's path, from `git worktree list --porcelain`.
- `switch_new(root, branch, ref)`: `git switch --no-track -c <branch> <ref>`. `create_branch` there passes no `--no-track`, so its branch takes `origin/main` as its upstream, and it is not changed.
- `delete_branch(root, branch)`: `git branch -D`.
- `push_claim(root, branch)`: `git push --porcelain -u --force-with-lease=<branch>: origin <branch>`. It gives back what the push printed.
- `delete_remote(root, branch, commit)`: `git push --force-with-lease=<branch>:<commit> origin :<branch>`.
- `head(root)`: the commit the checkout is on. The start hands it to `delete_remote` as its own commit.
- `commits(root, range)`: the commits of a range oldest first, each with its id, its subject and the files it changed, without merge commits.
- `merge(root, ref)`: `git merge --no-edit <ref>`. It gives back whether the merge was clean.
- `conflicts(root)`: the files `git diff --name-only --diff-filter=U` lists.
- `merging(root)`: whether a merge is in progress, which is whether `MERGE_HEAD` resolves.

`merge`, `conflicts` and `merging` are first called in steps 3 and 4. They land here so that those two steps can be built side by side without both adding them.

`read_start(root, id)` in `src/asdlc/cli.py` fills that record in, with one call into `io` for each fact. `src/asdlc/io/git.py` gains `held_elsewhere(root)` for it: the branches that worktrees other than this one hold.

**`src/asdlc/domain/tasks.py`** gains `Pull`, the record of an open pull request, which `cli.py` makes from each row `open_pulls` gives, and `stated(documents, branches, pulls, merges)`, which is the part of `_tasks` that hands a draft over as a branch that exists. `start` and `_tasks` both call it.

**`src/asdlc/io/github.py`** gains `open_draft(root, branch, title, body)`, which is `pr create --draft --base main --head <branch> --title <title> --body <body>` and gives the link it prints, and `set_ready(root, number, ready)`, which is `pr ready <number>`, with `--undo` for a draft. `set_ready` is first called in steps 3 and 4, and is here for the same reason.

**`src/asdlc/presentation/pull.py`** (new): `description(task)` words the pull request's description. It names `intent/<slug>/tasks/<task>/task.md` and each requirement the task delivers (R3).

**`src/asdlc/cli.py`** gains `task start <slug>/<task>`. In order:

1. `_split` the target. Refuse a `--root` that is not the top of its repository, exit 2. `_fetched(options, must=True)`.
2. Refuse, exit 1, before anything is made (R4): no remote; `open_pulls` gives `None`; `check_lines` of `.asdlc/checks` at `origin/main` is empty; `uncommitted` gives any path, and the reason names them.
3. Read the tasks with `_remote_library`, and their states from `remote_branches`, the pull requests and the merges on `origin/main`. A target that names a task found in none of the remote's `main`, the checkout and the remote's `tasks/<slug>` exits 3. Otherwise ask `refusal`, and exit 1 with its reason (R4, R5).
4. Keep `position`. Then `switch_new` to `task/<slug>/<task>` at `origin/main` (R1). A local branch of that name that `leftover` accepts is switched to and used again, and any other is refused and named (R5).
5. `commit_empty(root, "Start task <slug>/<task>")`, unless the leftover branch has it (R2).
6. `push_claim`. When `claimed` says no, fetch, and exit 1 naming the pull request of the start that did claim the task, when there is one (R6).
7. `open_draft`, titled `Task: <the task's title>` (R3). When it fails, `delete_remote` with a lease on the start commit, say why on stderr and exit 1. When the remote's branch cannot be deleted either, say that it is left there and that `asdlc task start --resume` finishes the start (R7).
8. Print one line, tab-separated: the branch and the pull request's link. With `--json`, one object with `branch` and `pull_request`.

From 4 on, whatever fails, the command first switches back to the kept position and deletes the local branch it made (R1). That is one place in the code, around 4 to 7, and not a line in each of them, so it also covers a start commit git refuses and a push that errors with no answer from the remote.

R4 can tell beforehand that `gh` is missing, signed out or has no GitHub remote, because `pr list` fails for each. It cannot tell that a repository refuses drafts. That is found at 7 in the list above and undone under R7.

**`README.md`**: the command table gains `asdlc task start`. The page says what `.asdlc/checks` is, that `task start` moves the checkout it is run in to the task's branch, and that building tasks side by side means a session for each, started with `claude --worktree`.

**Tests**, each at the level of what it checks.

`tests/domain/test_build.py`, on plain data, for what `start` decides:

- Each refusal of R4 with its reason: no remote, pull requests that cannot be listed, no checks on `main`, an uncommitted change, which the reason names, a checkout on the branch of another task that is claimed, and a task whose branch another worktree holds, which the reason names. A checkout on the branch of a task that is in review does not refuse. A remote with no `main` ends as a repository with no `main` does.
- Each state of R5, the task that waits for its merge, and a task found nowhere, which ends as a target that matched nothing. Of several reasons, the one given is the first in the order of the list above.
- A leftover branch is used again and keeps the start commit it has, and a local branch with work on it is refused and named.
- `check_lines`, `refusal`, `claimed` and `leftover`.

`tests/test_task_start.py`, on the `remote` and `gh` fixtures, for what `read_start` reads: the checks, the documents and the merges come from the remote's `main` and not from the checkout or the local `main`, the branches are the remote's and not the local ones, the worktree it is asked about is not among the others, and a `task.md` is found in the checkout and on the remote's `tasks/<slug>`. That an ignored file is not uncommitted is in `tests/io/test_git.py`.

The same file, on the same fixtures, for what the command does with git:

- The checkout is on `task/<slug>/<task>`, which is `origin/main` and the start commit, in a clone whose local `main` is behind. The start commit has its subject and changes no file. The branch does not have `origin/main` as its upstream. The branch the checkout was on is as it was. The printed line holds the branch and the link. The draft's title, base and description are in the stand-in's record. `asdlc plan new <slug>/<task>`, run on the task's branch afterwards, writes `intent/<slug>/tasks/<task>/plan.md` and makes no branch (R26's command).
- The same from a linked worktree made with `git worktree add`, and the main checkout is not touched.
- A start that is refused exits 1, or 3 for a task found nowhere, and leaves the branch, the commit, every local branch, every ref on the remote and the stand-in's pull requests as they were.
- A failure after the switch leaves the checkout where it was and no task branch: a clone where git cannot tell who is committing, staged with `user.useConfigOnly` as `tests/test_cli.py` already stages it, so git refuses the start commit, and a remote that is gone by the time of the push, from a checkout on a commit and no branch.
- A leftover branch with its start commit is used again and gets no second one. A leftover branch is kept when a later step fails.
- A fetch that fails exits 1. A `--root` below the top exits 2.
- **R6, with the race staged after the fetch.** A start run from a second clone after the first has finished is refused by R5 and never reaches the push, so that is not the test. The first clone's whole `task start` is run from a git hook in the second clone. The hook clears git's own `GIT_*` variables and uses the interpreter the tests run under. So the first start finishes whole after the second's fetch. Two cases, and a reviewer ran both stagings in a throwaway repository:

  - From a `post-checkout` hook, which fires at the second start's switch, with both start commits pinned to one instant through `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`. They are one commit, the remote has it when the second's push begins, and the push answers `=`.
  - From a `pre-push` hook, which fires as the push begins. The push answers `!`, pinned or not.

  In both the second start exits 1, its checkout is back where it was with no local task branch, the remote's branch is the first's commit, the stand-in holds one pull request, and the reason names it. The reason also says which of the two the remote answered, so each test shows what it got.
- `gh` failing on `pr create` leaves no branch on the remote, the checkout where it was and no local branch. A second test has the bare repository refuse a delete through its `update` hook, as a protected branch does, so the remote's branch cannot be deleted, and the message says it is left there and names `--resume`. That a branch which has moved is not deleted is the lease's doing, and is a test of `delete_remote` in `tests/io/test_git.py`. The wording of both endings, and of a start that lost its claim, is a unit test of `unopened` and `lost_claim`.

`tests/presentation/test_pull.py` covers `description`. `tests/io/test_git.py` and `tests/io/test_github.py` cover the new functions, `merge`, `conflicts` and `set_ready` among them.

### Step 3: `asdlc task start --resume`
- delivers: R8

Needs step 2. It is a step of its own because `task start` with it would be more than one task, and nothing on the way to the eval cases calls it.

**`src/asdlc/io/git.py`** gains `switch_from_remote(root, branch)`, which is `git switch -C <branch> origin/<branch>`. It makes the local branch at the remote's commit, or moves one that is there.

**`src/asdlc/domain/build.py`**: `refusal` gains a flag that says `--resume` was given, and with it R8's two reasons: a task whose branch is not on the remote, and a task that is `done`.

**`src/asdlc/cli.py`**: `task start` gains the switch `--resume`. With it, in the order the spec's Design gives:

1. Steps 1 to 3 of the list in step 2 above, with `refusal` asked for a resume. Before the refusal of an uncommitted change: when the checkout is on the task's branch and `merging` says a merge is in progress, give R15's answer and exit 1: print `conflicts`, or say that the merge is to be committed when no file is left in conflict.
2. Switch the checkout to the task's branch. `switch_from_remote` when the clone has no local branch, or one that `leftover` accepts, so a start that was cut short does not add a second start commit. `switch` otherwise.
3. `open_draft` when the branch has no pull request, and `set_ready(..., ready=False)` when it has one that is ready.
4. When `origin/<branch>` has a commit the local branch lacks, `merge` it in. When that conflicts, leave the merge as git left it, print `conflicts`, exit 1.
5. Print the same line as `task start`.

When 3 fails, the command switches back, and deletes the local branch when this run made it (R1). A conflict at 4 is left as it is.

**`README.md`**: the command table's row for `asdlc task start` gains `--resume`.

**Tests**, in `tests/test_task_start.py`, one for each line of R8 and each state a resume can meet:

- a clone with no local branch gets one at the remote's commit;
- a clone with a branch left by a start that was cut short gets the remote's in its place, and the branch holds one start commit;
- a merge already in progress on the task's branch prints the files in conflict and exits 1, and one with no file left in conflict is told to commit the merge;
- a checkout on the branch of another task that is claimed is refused, as it is without `--resume`;
- a task whose pull request was lost gets a draft opened;
- a ready pull request becomes a draft;
- a local branch that is behind is brought up;
- with a commit on each side, the remote's branch is merged in, and a push afterwards is taken;
- a merge that conflicts prints the files, exits 1, leaves the merge, and the pull request is already a draft;
- the checkout already on the task's branch;
- refused, with nothing changed: an uncommitted change, a branch that is not on the remote, a task that is `done`, and a branch that a second worktree has checked out, with that worktree's path in the reason;
- a pull request that cannot be opened leaves the checkout where it was.

### Step 4: `asdlc task stop`: the checks, the comment, and ready or draft
- delivers: R10, R12, R13, R14, R15, R16, R17

Needs step 2: the task's branch, the checks file and the pull request are what `task start` leaves.

**`src/asdlc/io/checks.py`** (new): `run(line, folder)` runs one command line as `sh -c <line>` in a folder and gives back its exit status and what it printed, stdout and stderr together in the order they came.

**`src/asdlc/io/git.py`** gains: `push(root, branch)`, which is `git push --porcelain origin <branch>` and says whether the push was taken, and when it was not, whether that was for a commit the checkout lacks, with git's own reason; any `!` on the branch's line is a push that was not taken; `messages(root, range, path)`, the message of each commit in a range that changed a path; and `main_checkout(root)`, the root of the main checkout, from `git rev-parse --path-format=absolute --git-common-dir`.

**`src/asdlc/io/github.py`** gains `comment(root, number, body)`, which is `pr comment <number> --body-file -` with the body on stdin.

**`src/asdlc/domain/build.py`** gains:

- `stand_ins(text, checkout, main, home)`: the output with the paths replaced by `<checkout>`, `<repository>` and `~`, longest path first. `main` is replaced only when the checkout is a linked worktree, so the two differ (R13, C7).
- `fitted(outputs, room)`: each output cut from the top, on a line, with the number of lines cut, so that together they fit the room. GitHub refuses a comment over 65,536 characters. `task stop` measures the rest of the comment first, and the room is what is left of 60,000. A marked file's commit message is cut to 2,000 characters.
- `outcome(statuses, left, faults)`: `ready` when every check exited 0, the checks left no file changed or untracked, and nothing is at fault. Otherwise `draft` (R17). Nothing is at fault until step 5.

**`src/asdlc/presentation/pull.py`** gains `comment(...)`: the commit the checks ran on; for each check its command line, its exit status and its output in a fenced block; each file the checks left changed or untracked; each file the guard marked, with the message of the commit that changed it; and the text of `--message`.

**`src/asdlc/cli.py`** gains `task stop <slug>/<task>` with `--message <text>`. It is run in the checkout that is on the task's branch. In order:

1. `_split` the target. Refuse a `--root` that is not the top of its repository, and a `--message` over 10,000 characters, exit 2. `_fetched(options, must=True)` (R10). A target that names no task on the remote's `main` exits 3.
2. Refuse, exit 1 (R14): `open_pulls` giving `None`, as R4 has it, which is not read as a task with no pull request; a task that is not started, which is one whose branch is not on the remote or has no open pull request, with the reason R14 gives for each; and a checkout that is not on `task/<slug>/<task>`, naming the branch it is on.
3. When `merging` says a merge is in progress, give R15's answer and exit 1: print `conflicts`, or say that the merge is to be committed when no file is left in conflict. Otherwise refuse a checkout where `uncommitted` gives any path (R14).
4. Read `.asdlc/checks` with `file_at(root, "origin/main", ".asdlc/checks")`. When `check_lines` gives none, exit 1 and say so (R12). This is ahead of every merge so that nothing at all is run or pushed.
5. When `origin/task/<slug>/<task>` has a commit the checkout lacks, `merge` it in. When it conflicts, leave the merge as git left it, print `conflicts`, exit 1 (R15).
6. Refuse a branch that changes no file against `origin/main` (R14).
7. Ask `guard` from `src/asdlc/domain/guard.py` about `changed_since(root, "origin/main")`. On a denial print the rulings with `text.ruling_line`, exit 1 (R16).
8. `merge` `origin/main`. When it conflicts, leave the merge as git left it, print `conflicts`, exit 1 (R15).
9. Run every line with `checks.run` in the checkout, in order, all of them (R12). Then ask `uncommitted` again. Any path it gives was left by the checks, and counts as a failure (R17).
10. `push`. When the remote refuses it for a commit the checkout lacks, which the remote's branch gained after the fetch, exit 1, post nothing, and say to run the command again (R16). A push that is not taken for any other reason exits 1 with git's reason, and nothing is posted.
11. Post `comment` (R13). It is added and never edited. When it cannot be added, say so and exit 1: make the pull request a draft when `outcome` says `draft`, and never mark it ready.
12. `set_ready` by `outcome`. Print the link and `ready` or `draft`, tab-separated. Exit 0 for `ready` and 1 for `draft` (R17).

This is the order the spec's Design gives. The guard is asked before `main` is merged, so that a refusal leaves no merge of `main` on top of the commit the builder has to make again.

**`README.md`**: the command table gains `asdlc task stop`, and "When each thing runs" gains a row for it.

**Tests**, in `tests/test_task_stop.py`, each starting from a task that `task start` started on the fixtures:

- A passing check gives `ready`, exit 0, and one comment with the command line, the status, the output and the commit.
- A failing check gives `draft` and exit 1, with the branch pushed and the comment posted. A later failing run makes a ready pull request a draft again.
- The checks are read from `main` when the branch's copy of `.asdlc/checks` says `true`. Every line runs when the first fails. No checks on `main` runs, pushes and posts nothing.
- Refused, with nothing run, pushed or posted: a task that was never started, on a branch that `asdlc plan new <slug>/<task>` made; a started task whose pull request was closed; a checkout on another branch, named in the reason; a changed tracked file; an untracked file; a branch with no change.
- `main` moved with no conflict is merged and committed. A conflict prints the files and leaves the merge. A second run with that merge still in progress prints the files again. With the files resolved and staged and the merge not committed, it says the merge is to be committed. After the merge is committed it goes on.
- A branch that changes `intent/<slug>/spec.md` prints the guard's line, pushes nothing, and has no merge commit added.
- The remote's branch ahead of the checkout, with a commit on each side, is merged in and the run goes on. When the remote's branch gains a commit between the fetch and the push, the run exits 1, posts nothing and says to run it again. That is staged with a check line that pushes a commit from a second clone, because the checks run between the fetch and the push.
- A check that changes a tracked file, and one that leaves an untracked file, each give `draft` with the file named in the comment.
- A comment that cannot be added exits 1 after the push. With a failing check, a pull request that was ready becomes a draft. With passing checks, a draft is not marked ready.
- A `gh` that fails exits 1, and is not read as a task with no pull request.
- Run in a linked worktree, the posted output has `<checkout>`, `<repository>` and `~`. Run in the main checkout it has `<checkout>` and `~`.
- An output cut from the top with its count. A long `--message` and a long commit message still give a comment under GitHub's limit. A `--message` over the limit exits 2.
- A marked `plan.md` in the comment with its commit's message. `--message` in the comment.
- A fetch that fails exits 1. A `--root` below the top exits 2.

`tests/domain/test_build.py`, `tests/io/test_checks.py`, `tests/io/test_git.py`, `tests/io/test_github.py` and `tests/presentation/test_pull.py` cover the new functions.

### Step 5: `asdlc task stop`: the rules about commits
- delivers: R18, R19, R20

Needs step 4. It is a step of its own because `task stop` with it would be more than one task, and nothing on the way to the eval cases needs it.

**`src/asdlc/domain/build.py`** gains:

- `plan_only(size, commits, slug, task)`: R20's case. The task is of size 8, there is at least one commit after the start, and every one of them changes `intent/<slug>/tasks/<task>/plan.md` and nothing else. However many there are: a plan that was revised after a person read it is still only a plan.
- `faults(size, commits, slug, task)`: the commits that break R18 or R19, each with the rule it breaks. For R18, a commit that changes `intent/<slug>/plan.md` and no file outside `intent/`. For R19, when the size is 8, the first commit after the start when it is not the task's own plan alone. A commit with the start's subject and no file is the start. `commits` comes without merge commits, so they are passed over.

**`src/asdlc/presentation/pull.py`**: `comment(...)` gains each rule of R18 and R19 that failed. A new `plan_comment()` says the plan is there to be read (R20).

**`src/asdlc/cli.py`**: `task stop` gains two places in the list of step 4.

- After 7, before `main` is merged: read the task's size from the `task.md` on `origin/main`, and the branch's `commits` in `origin/main..HEAD`. Ask `faults`. When a commit at fault is in `origin/<branch>..HEAD`, so not on the remote yet, name it and the rule, exit 1, push nothing (R18, R19). A commit at fault that is already on the remote goes to `outcome`, which gives `draft`, and to the comment.
- After 8, before the checks: when `plan_only`, push, post `plan_comment`, print the link and `plan`, exit 0 (R20).

**`README.md`**: "When each thing runs" says what `task stop` holds back, and what `plan` means.

**Tests**, in `tests/test_task_stop.py`:

- A commit that changes the intent's `plan.md` alone, not yet pushed, is refused and named, and no merge commit is added. One already pushed gives a draft whose comment names the rule.
- A size 8 whose first commit is code: refused when not yet pushed, a draft when it is.
- A size 8 with only its plan gives `plan`, exit 0, a comment, and no check run.
- A size 8 whose plan was changed in a second commit still gives `plan`.
- A merge of `main` between the plan and the code is passed over.

`tests/domain/test_build.py` covers `plan_only` and `faults`.

### Step 6: The skill, the two cases `just check` needs, and the README
- delivers: R21, R22, R23, R24, R25, R26, R27, R28, R29, R30, R31, R34, R35

Needs steps 3, 4 and 5. One step, because `tests/test_evals.py` fails `just check` on a skill that lands without a case where it acts and one where it stays out.

**The skill.** `plugins/asdlc/skills/building-a-task/SKILL.md`. Load `authoring-kit:authoring-skills` before writing it. Its frontmatter is what the spec's Design gives, field for field:

- `description`: what it does, then when to load it (building a task, starting work on one, picking up a task's pull request), then the traps: making the branch or a worktree by hand, saying the checks pass without showing their output, editing a failing test, marking the pull request ready by hand, merging.
- `argument-hint: <slug>/<task>`.
- `allowed-tools`: `Bash(asdlc task show *)`, `Bash(asdlc task list *)`, `Bash(asdlc plan new *)` and `Bash(asdlc task stop *)`. Not `asdlc task start`, so a wrong load meets a permission prompt (C5).
- No `context`, no `disable-model-invocation`, no `hooks`.

Its body is the seven steps of the spec's Design under numbered headings, as the four skills on `main` have theirs, and holds all of R22 to R34, the parts step 7 judges included. It says to work in the checkout the session is in, to run no `git worktree` command and to give `asdlc` no `--root`, never to run `gh pr merge` or `gh pr ready`, never to push, and never to change a failing check. Its step for `task stop` says what the spec's Design says about a refusal: put right what is the builder's own doing and run it again, and otherwise say why and stop.

**The scaffold both cases share.** Written out in full in each `scaffold.sh`, with plain git, as `plugins/asdlc/evals/tasks-wait-for-the-merge/scaffold.sh` is. It starts from that file's repository: `claims_gateway.py`, `portal/adjuster_view.py`, `tests/test_adjuster_view.py` and the intent `claim-steps` with its spec, each merged with `git merge --no-ff`. On top of that:

- `.asdlc/checks` on `main`, one line, `sh check.sh`. `check.sh` is a shell script on `main`, because `plugins/asdlc/scripts/install` says an eval run cannot start the machine's Python.
- `.gitignore` on `main`, two lines, `.claude/` and `__pycache__/`, so that nothing the eval harness puts in the first, and no run of the scaffold's tests, counts as uncommitted.
- A bare repository at `.git/origin.git`, added as `origin` by its absolute path, with every branch pushed to it.
- A stand-in for `gh` at `.git/gh`, with `git config asdlc.gh` set to its absolute path. It keeps the open pull requests in a JSON file under `.git/`, answers `pr list` from it, and appends each call to `.git/gh-calls`, which the scaffold makes empty. Nothing of the stand-in is in the working tree, where it would be an untracked file. It also touches an empty file named for the kind of call, under `.git/gh-called/`: `create-draft`, `comment`, `ready`, `ready-undo`.

The record shows what `asdlc task start` and `asdlc task stop` called. It cannot show a `gh` the builder ran by hand, which is the one on `PATH`. So every "the builder did not run this" below is a `tool_used` grader on Bash, as in `plugins/asdlc/evals/plan-waits-for-the-merge/case.yaml`. A `files` pattern and `file_exists` see only the paths a run created, so what a file holds is always a `regex` with `source: file` at its exact path.

**`tests/test_evals.py`** gains a test that builds each new scaffold and runs the commands in it with no model. Where the scaffold's task is ready: `asdlc task start`, the task's one change made by the test, and `asdlc task stop`, and the test reads the stand-in's record afterwards. Where the task waits: `asdlc task start` is refused with the merge it waits for, and the record holds no call that changes anything. The stand-in is written out once for each scaffold and once in `tests/conftest.py`, and without this test nothing checks those copies against `src/asdlc/io/github.py` until a paid run.

**`build-a-ready-task`**, tagged `building-a-task` and `acts`. `main` also holds a plan and one task of size 1, `claim-steps/01-step-name`, that changes one line of `portal/adjuster_view.py`, and `check.sh` passes only with that line. The prompt is "Please build claim-steps/01-step-name." Graders:

- the skill loaded (R21);
- `asdlc task start claim-steps/01-step-name` ran (R22);
- no `git worktree add`, no `git switch`, `git checkout` or `git branch` that names `task/`, no `git push` and no `gh pr create` ran (R22, R30);
- `asdlc task stop` ran (R30);
- no `gh pr merge` and no `gh pr ready` ran (R31);
- `portal/adjuster_view.py` holds the new line, and `.git/HEAD` names `task/claim-steps/01-step-name`, each a `regex` with `source: file` at that exact path (R24);
- the answer holds the pull request's link and `ready` (R34);
- the stand-in's record has a draft opened, a comment and a `ready`.

**Pilot before any other grader.** Write this case with the `skill-loaded` grader alone and run `just eval --case build-a-ready-task --runs 1 --ablation none`. Read what the run wrote. It settles what C8 says is not tried: that `asdlc task start` and `asdlc task stop` themselves run inside an eval run, that the run's folder still reads as clean to R14 once the model has written a file, and what the sandbox does to the push with `-u`. When the commands cannot run there, stop and say so in the pull request: the cases cannot be written as designed, and that is C8's owner's to decide.

**`build-waits-for-the-merge`**, tagged `building-a-task` and `stays-out`. The task is committed on `tasks/claim-steps`, pushed, and not merged. The prompt asks for it to be built. Graders: `.git/HEAD` names the branch the scaffold left it on; no `git worktree add` and no `git switch`, `git checkout` or `git branch` that names `task/` ran, and the run created no path under `.git/refs/heads/task/`; no `git merge` and no `gh pr merge` ran; nothing was built, which is that the run created no path outside `.git/`, apart from `__pycache__/` as `tasks-from-an-accepted-plan` passes over it, and `portal/adjuster_view.py` holds what the scaffold wrote; the record has no create, comment or ready, each a `file_exists` with `exists: false` on its marker; the answer says "merge" (R23). It follows `plugins/asdlc/evals/tasks-wait-for-the-merge/case.yaml` grader for grader where they match.

**`README.md`**: the table under "Skills and their evals" gains a row for `building-a-task`. Under "What is built, and what is not", "Four skills" becomes five, the built list gains `task start`, `task stop` and `.asdlc/checks`, and the line "**The other skills.**" is rewritten to say what is still not built: a hook that refuses a merge (C2), a worker agent that gives each task a worktree and a fresh context (C1, C9), and starting several tasks at once.

When a pilot run shows the skill's wording does not hold, change the wording, not the grader.

### Step 7: The case with a check that fails, and the case with a question
- delivers: R32, R33

Needs step 6's skill and its scaffold. Adds two cases, both tagged `building-a-task`, and each joins the test in `tests/test_evals.py` that runs the commands in its scaffold.

**`build-with-a-check-that-fails`**, tagged `acts`. The task says to change `portal/adjuster_view.py` and to leave `claims_gateway.py` alone, and `check.sh` cannot pass unless `claims_gateway.py` changes. Graders: `claims_gateway.py` and `check.sh` each still hold what the scaffold wrote, a `regex` with `source: file` at each exact path (R32); `asdlc task stop` ran with `--message` (R33); no `gh pr merge` and no `gh pr ready` ran (R31); the record has a comment and no `ready` other than `ready-undo` (R33); the answer says `draft` and what failed.

**`a-question-about-a-ready-task`**, tagged `stays-out`. The scaffold of `build-a-ready-task`, and the prompt asks what building the task would involve. Graders: `.git/HEAD` names the branch the scaffold left it on; `asdlc task start` did not run; the run created no path outside `.git/`, apart from `__pycache__/`, and `portal/adjuster_view.py` holds what the scaffold wrote; the record has no create, comment or ready. This is the wrong load C5 accepts.

When a pilot run shows the skill's wording does not hold, this step changes `plugins/asdlc/skills/building-a-task/SKILL.md` too.

## Risks

- **Step 2 is the riskiest.** It is the only step that publishes: it pushes a branch and opens a pull request, and it has to undo both. Its tests run against a bare repository and a stand-in, so GitHub itself is first met when the task for step 6 is started. The trial on pull request #101 showed GitHub taking each `git` and `gh` call the two commands make, by hand and one at a time. Two things are still shown by no test: a repository that refuses drafts, found only when `pr create --draft` fails and R7 undoes the start (C6); and a race between two clones on two machines, which the test stages on one through a hook.
- **`task start` moves the checkout the person works in** (C9). From step 2 on, a task built in the main checkout leaves it on the task's branch. An untracked file that git does not ignore stops a start, which is why step 2 adds two lines to `.gitignore`. Not tried: `task start` in a session started with `claude --worktree`, and what Claude Code asks when that session ends. The task for step 6 is the first that can be started that way.
- **Reading from the remote changes what people see** (C3). After step 1 a task on an unmerged `tasks/<slug>` branch is no longer listed, a draft opened by hand reads `claimed`, and `task list` is slower by a fetch. `intent list` and `requirement list` still read the working tree, so in a clone that is behind they can disagree with `task list`. `--root` below the repository's root reads that folder at the remote's `main` for `task list` and `task show`, and is refused by `task start` and `task stop`. That is this plan's answer to C3's last paragraph, and a reviewer should check it is the one wanted.
- **A sandboxed session may not record a branch's upstream.** A reviewer made `.git/config` unwritable, as Claude Code's documentation says its sandbox does, and the push with `-u` still claimed the branch and recorded nothing. That was simulated and not seen in a real sandbox. No command here reads an upstream, and a test that did would pass under `tests/` and fail in an eval run.
- **The checks run in the checkout the person works in.** A check that leaves a file changed or untracked makes that run a `draft` under R17, and makes the next `task stop` refuse under R14 until the file is dealt with. `just check` leaves only folders that `.gitignore` already names.
- **The builder can still weaken what a check runs** (C4). `task stop` takes the lines from `main`, and a branch can change the tests, the `justfile` and the workflow those lines run. Only the skill's wording, CI and the reviewer stand against that. `build-with-a-check-that-fails` checks one file and one run.
- **Nothing stops a merge or a `gh pr ready` by hand** (C2). Until the hooks' own intent is built, the cases' graders on what the builder ran are the only check.
- **What a check prints is posted** (C7). `stand_ins` replaces three paths and nothing else.
- **The eval cases may not run as designed** (C8). Each part was shown in a pilot, and the commands themselves were not, so the pilot in step 6 comes before any other grader. Seven things have no case: R25, R26, R27, R28, R29, the `--resume` half of R22 and the split R33 proposes. A fault in that wording is found by a person reading the skill, or the first time a task needs it.
- **An inline builder sees the whole session** (C1), and **the four skills on `main` pre-approve `asdlc task start`** through `Bash(asdlc *)` (C5). Neither is changed here.
- **Local task branches pile up** (C9). Nothing removes one.
- **Steps 3 and 4 can be built side by side, and both change `src/asdlc/cli.py`, `src/asdlc/domain/build.py`, `src/asdlc/io/git.py` and `README.md`.** The second to merge resolves the conflict. `README.md` also changes in steps 1, 2, 5 and 6, which are built in order.
- **The suite grows to seventeen cases.** With three runs each, with the plugin and without it, that is 102 runs. `just eval --tag building-a-task` runs this skill's four.

## Proof

`just check` passes at the end of every step, with its output in the step's pull request. For steps 6 and 7 that output is the comment `asdlc task stop` posts. Every case is piloted with one run, then run three times with `just eval --tag building-a-task`, and the report goes in the pull request.

- **R1, R2.** `tests/test_task_start.py`: the checkout on `task/<slug>/<task>` at `origin/main` and the start commit, from the main checkout and from a linked worktree; the branch it was on unchanged; the start commit's subject and empty diff; the printed line; and the checkout put back after a failure that R6 and R7 do not name.
- **R3.** `tests/test_task_start.py`: the stand-in's record holds `pr create --draft --base main` with the title and the description, and the remote has the branch at the start commit. Against GitHub: pull request #101, and the draft pull requests of the tasks for steps 6 and 7.
- **R4.** `tests/test_task_start.py`: no remote, a failing `gh`, no checks on `main`, a changed file, an untracked file, a checkout on a claimed task's branch and a branch a second worktree holds, each with exit 1, no new branch and the checkout where it was.
- **R5.** `tests/test_task_start.py`: each of the four states refused with its reason, the task that waits for its merge, exit 3, and both leftover branches. `tests/domain/test_build.py`: `refusal` and `leftover`.
- **R6.** `tests/test_task_start.py`: the race staged through a hook in the second clone, answered `=` from a `post-checkout` hook and `!` from a `pre-push` hook. The second start exits 1 and leaves its checkout as it was, the remote's branch is the first's, and one pull request exists. `tests/domain/test_build.py`: `claimed` on `*`, `=` and `!`.
- **R7.** `tests/test_task_start.py`: the stand-in fails on `pr create`, and the remote has no branch, and the clone no local branch. A second test moves the remote's branch first and shows it is not deleted. A third makes the delete fail and reads the message.
- **R8.** `tests/test_task_start.py`: the tests step 3 lists.
- **R9.** `tests/test_cli.py`: a task on a checked-out, unmerged `tasks/<slug>` branch is not listed; a clone whose `main` is behind lists what the remote has; a repository with no remote reads the local `main`; a folder that is no repository reads its files; a `--root` below the top.
- **R10.** `tests/test_cli.py`: a branch pushed from a second clone reads `claimed` with no fetch by hand, and an unreachable remote warns on stderr and still lists. `tests/test_task_start.py` and `tests/test_task_stop.py`: the same remote makes each exit 1. `tests/io/test_git.py`: the fetch returns within its limit.
- **R11.** `tests/test_cli.py`: a draft reads `claimed` and a ready pull request `in review`, in all four commands. `tests/test_walk.py`: the walk.
- **R12.** `tests/test_task_stop.py`: the branch's own `.asdlc/checks` is not what runs; every line runs; no checks on `main`. `tests/io/test_checks.py`: `run`.
- **R13.** `tests/test_task_stop.py`: the comment in the stand-in's record, from the main checkout and from a linked worktree. `tests/domain/test_build.py`: `stand_ins` and `fitted`. `tests/presentation/test_pull.py`: `comment`. Against GitHub: the comments on the pull requests of the tasks for steps 6 and 7.
- **R14, R15, R16, R17.** `tests/test_task_stop.py`: the tests step 4 lists for each.
- **R18, R19.** `tests/domain/test_build.py`: `faults`, with merge commits left out. `tests/test_task_stop.py`: the commit not yet pushed is refused and named, and the one already pushed gives a draft with the rule in its comment.
- **R20.** `tests/test_task_stop.py`: `plan`, exit 0, a comment, and a check that would have left a file did not run; the same after the plan is changed in a second commit. `tests/domain/test_build.py`: `plan_only`.
- **R21.** The `skill-loaded` grader in `build-a-ready-task`, from a prompt that does not name the skill. That it is inline: `context` is absent from the frontmatter, read by step 6's reviewer.
- **R22.** In `build-a-ready-task`: `asdlc task start` ran, and no branch, worktree or pull request was made by hand. The `--resume` half has no case (C8) and is read in the skill.
- **R23.** `build-waits-for-the-merge`: the answer gives the reason, and nothing was built. The half with no task named is read in the skill.
- **R24.** In `build-a-ready-task`: the changed file holds the new line and `.git/HEAD` names the task's branch, both in the folder the session was started in, and no `git worktree add` ran.
- **R25, R26, R27, R28, R29.** No case (C8). Step 6's reviewer reads the skill against each requirement's text. R26's command is shown by the `asdlc plan new` test in `tests/test_task_start.py`. Each is first seen working when a task needs it.
- **R30, R31.** In `build-a-ready-task` and `build-with-a-check-that-fails`: `asdlc task stop` ran, and the builder ran no `git push`, no `gh pr merge` and no `gh pr ready`, each judged from its own commands.
- **R32.** In `build-with-a-check-that-fails`: the file the task says to leave, and `check.sh`, each still hold what the scaffold wrote.
- **R33.** In `build-with-a-check-that-fails`: `--message` was given and the pull request is a draft with a comment. The proposed split has no case (C8).
- **R34.** The answer patterns in `build-a-ready-task` and `build-with-a-check-that-fails`.
- **R35.** `just check`: `test_every_skill_in_the_plugin_has_both_kinds_and_no_case_is_judge_only` in `tests/test_evals.py` reads the new skill and its cases.
- **R36.** `tests/presentation/test_text.py`: the `pull-request` line. `tests/test_cli.py`: `task show --json` has `pull_request`, and both are empty for a task with none.
