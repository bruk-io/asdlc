---
kind: spec
---
# Spec: Build a ready task into a pull request

## Requirements

R1 to R8 are about starting a task, R9 to R11 about how tasks and their states are read, R12 to R20 about stopping, R21 to R34 about the skill, R35 about the eval cases, and R36 about the link `task show` gives. This spec changes no hook.

Five words are used throughout. The **builder** is Claude with the `building-a-task` skill loaded. The **checkout** is the working tree a command is run in: the main one or a linked worktree, whoever made it. A task is **started** when its branch is on the remote with a pull request. The **checks** are the command lines in `.asdlc/checks` on the remote's `main`, one to a line. A file with no command line in it counts as missing. A **branch of the loop** is one named `intent/<slug>`, `spec/<slug>`, `plan/<slug>`, `tasks/<slug>`, `task/<slug>/<task>` or `change/<slug>`.

### R1: `asdlc task start <slug>/<task>` puts the checkout it is run in on the branch `task/<slug>/<task>`, made from the remote's `main`

It makes no worktree. The checkout may be on any branch when the command is run, and that branch is left as it was. The task's branch is made with no upstream. The command prints one line: the branch and the pull request's link.

### R2: The branch's first commit is an empty one that records when the task was started

Its subject is `Start task <slug>/<task>`, as `asdlc intent new` records the start of an intent.

### R3: `task start` pushes the branch and opens a draft pull request for it, before any work is done

The push sets the branch's upstream to its own branch on the remote. The pull request is against `main` and is titled `Task: <the task's title>`. Its description names the task's `task.md` and the requirements it delivers. This is what the command does with no flag.

### R4: `task start` makes nothing when it can tell beforehand that it cannot finish

Before it makes a branch it refuses, with exit 1 and the reason: a repository with no remote, a `gh` that cannot open a pull request in this repository, a remote `main` with no checks, and a checkout with uncommitted changes. An untracked file counts as uncommitted unless git ignores it, here and in R14, and the reason names the files.

### R5: `task start` starts only a task that reads as `ready`, judged from the remote alone

It fetches first. It refuses, with exit 1 and the reason, a task that is `waiting`, `claimed`, `in review` or `done`. For a task that is claimed or in review the reason gives its pull request, or says that it has none and that `--resume` opens one. A task whose `task.md` is in the checkout, or on the remote's `tasks/<slug>`, and not on the remote's `main` is refused the same way, and the reason names the merge it waits for. A target that names a task found in none of those exits 3. A local branch left by a start that was cut short before its push does not count: the command uses it again when it holds nothing but a start commit, and otherwise refuses and names it.

### R6: When one task is started from two clones, at most one start succeeds, and the other changes nothing on the remote

The push is the claim, and it counts only when it made the branch on the remote. A push the remote rejects, or answers as already up to date, lost. The start that lost puts the checkout back where it was and deletes the local branch it made, and nothing else, and names the pull request of the one that won when there is one.

### R7: When the pull request cannot be opened after the push, `task start` undoes the start

It deletes the branch from the remote only while the remote still holds this start's own commit, puts the checkout back where it was and deletes the local branch it made, says why on stderr and exits 1. When the undoing fails too, it says what is left and that `task start --resume` finishes the start.

### R8: `task start --resume` puts the checkout on the branch of a task that is already started

- It refuses a checkout with uncommitted changes, as R4 does, a task whose branch is not on the remote, and a task that is `done`. It refuses a branch that another worktree of the clone has checked out, and names that worktree.
- When the clone has no local branch for the task, it makes one from the remote's branch, with that as its upstream.
- It opens the draft pull request when the branch has none.
- It makes a pull request that was ready a draft again.
- When the remote's branch has a commit the local one lacks, it merges the remote's branch into the local one. When that merge conflicts it leaves it as git left it, prints the files in conflict and exits 1, as R15 does.

### R9: `asdlc task list`, `task show` and `task start` read which tasks exist from the `task.md` files on the remote's `main`

A task on a branch that is not merged is not listed. When the repository has no remote they read the local `main`. When `--root` is not in a repository with a `main`, they read the files there, as today.

### R10: `asdlc task list`, `task show`, `task start` and `task stop` fetch before they read

So a task started from another clone shows as `claimed` without anyone running `git fetch`. The fetch never asks for credentials and gives up after 20 seconds. When it fails the command says so on stderr, and `list` and `show` read what was last fetched. `start` and `stop` exit 1.

### R11: A task whose pull request is a draft reads as `claimed`, and as `in review` once the pull request is marked ready

This holds wherever a task's state is shown: `task list`, `task show`, `intent list` and `intent show`.

### R12: `asdlc task stop <slug>/<task>` runs the checks in the checkout it is run in

It reads `.asdlc/checks` from the remote's `main`, not from the branch. It takes no command line from whoever runs it. Each line is run through `sh -c`, in order, and all of them are run. When `main` has no checks, the command exits 1 and says so, and runs, pushes and posts nothing.

### R13: `task stop` adds one comment to the pull request, holding what each check printed

For each check the comment holds the command line, the exit status and what it printed. The output is as printed, except that the checkout's path, the main checkout's path when the checkout is a linked worktree, and the home folder are each replaced by a short stand-in. Output longer than the comment can hold is cut from the top, and the comment says how many lines were cut. The comment also holds the commit the checks ran on, each file the guard marked with the message of the commit that changed it, and the text of `--message` when one is given.

### R14: `task stop` refuses a checkout that is not on the task's branch or has uncommitted changes, and a branch that changes no file

Untracked files count as uncommitted, as R4 says. Exit 1, and nothing is run, pushed or posted. For a checkout on another branch the reason names that branch.

### R15: `task stop` merges the remote's `main` into the branch before it runs the checks

When `main` has nothing new it does nothing. When the merge is clean it commits it. When it conflicts it leaves the merge as git left it, prints the files in conflict, exits 1, and runs, pushes and posts nothing.

### R16: `task stop` pushes the branch, unless the guard denies a file the branch changed

On a denial it prints the guard's lines, exits 1, and pushes and posts nothing. Otherwise it pushes whether or not the checks passed, so the pull request shows the commit the comment is about. When the remote refuses the push because its branch has a commit the checkout lacks, the command exits 1, posts nothing, and says that `task start --resume` merges that commit in.

### R17: `task stop` marks the pull request ready for review only when every check passed, and makes it a draft when one failed

It prints the pull request's link and `ready` or `draft`. It exits 0 for `ready` and 1 for `draft`. A pull request that was ready goes back to a draft when a later `task stop` fails.

### R18: `task stop` leaves a draft when a commit on the branch changes the intent's `plan.md` and no file outside `intent/`

Merge commits are passed over.

### R19: `task stop` leaves a draft when the first commit after the start of a task of size 8 is not its own plan alone

That commit has to add `intent/<slug>/tasks/<task>/plan.md` and change nothing else. Merge commits are passed over. The size is the one in the `task.md` on the remote's `main`, here and in R20.

In R18 and R19, when the commit at fault is not on the remote yet, the command refuses as R16 does on a denial: it names the commit, exits 1 and pushes nothing, so the builder can make the commit again. When the commit is already on the remote, the comment says which rule failed, and the draft ends when a person marks it ready on GitHub or closes it.

### R20: For a task of size 8 whose branch holds only its plan, `task stop` pushes and leaves the draft for a person to read

It runs no check, adds a comment that says the plan is there to be read, prints the link and `plan`, and exits 0.

### R21: The plugin has a skill, `building-a-task`, that loads when someone asks for a task to be built or picked up

It loads on a plain request, such as "build generate-tasks/02-spike-case" or "pick up that task's pull request and resolve the conflict". Nobody has to name it. It runs inline, in the session that was asked.

### R22: The builder starts with `asdlc task start`, and makes no branch, worktree or pull request by hand

It passes `--resume` only when the person asked for a started task to be picked up. When `task start` refuses a task because it is already started and the person did not ask for that, the builder says so and does not resume it.

### R23: Given no task, or a task that `task start` refuses, the builder builds nothing and says why

With no task named it gives the tasks that read as `ready` and starts none. With a refusal it repeats the reason.

### R24: The builder works in the checkout the session is in, and changes files only there

It runs `task start` and `task stop` in that checkout and makes no worktree. A person who wants a task built apart from their own checkout starts the session in a worktree of Claude Code's, with `claude --worktree`.

### R25: The builder builds what the task's "What to build" says, and reports anything else it found instead of doing it

### R26: For a task of size 8, the builder writes the task's own plan, commits it alone, runs `asdlc task stop` and stops

It starts the plan with `asdlc plan new <slug>/<task>`. The plan talks through the risk the task names. The builder writes no code until the person has read the plan on the pull request and asks for the task to be picked up.

### R27: When the work departs from the intent's plan, the builder changes `plan.md` in the same commit as the code, and that commit's message says why

### R28: The builder changes no other document

The task's own `plan.md` and the intent's `plan.md` are the only files under `intent/` it writes. It does not edit the task's `task.md`, and it cuts no task.

### R29: When `task stop` or `task start --resume` names files in conflict, the builder resolves them on the branch and commits the merge

### R30: The builder ends with `asdlc task stop`

It does not push the branch itself: the command does.

### R31: The builder never merges a pull request, and never marks its own pull request ready by hand

It does not run `gh pr merge` or `gh pr ready`, and it pushes nothing to `main`.

### R32: When a check fails, the builder changes the code and never the check

It does not edit, skip or delete a failing test, and does not loosen a linter's configuration.

### R33: When it cannot get the checks to pass, or the task turns out bigger than its size, the builder stops and leaves the pull request a draft

It runs `task stop` with `--message`, saying what failed and what it tried, so the failing output is on the pull request. For a task that is bigger than its size the message proposes a split: which tasks, and what each would build.

### R34: The builder's answer gives the pull request's link and what `task stop` printed: `ready`, `draft` or `plan`

For a draft it says what failed.

### R35: The skill has an eval case where it must act and one where it must stay out

### R36: `asdlc task show` gives the task's pull request

A `pull-request` line holding the link, and a `pull_request` field under `--json`. Both are empty for a task with none.

## Design

Skills applied: `authoring-kit:choosing-extension-types`, `authoring-kit:authoring-skills` and `authoring-kit:authoring-hooks`.

### What is code and what is a skill

`choosing-extension-types` asks first whether the model should do a thing at all, and has the earliest answer win.

- Making the branch, recording the start, pushing, opening the pull request, merging `main` when it merges cleanly, running the checks and posting their output are each "given X, produce Y". They are the `asdlc` command (R1 to R20). The model picks the moment and does none of it by hand (R22, R30).
- What is left needs judgment: reading the task, writing the code, deciding whether a failure can be fixed, resolving a conflict, proposing a split. That is a procedure, so it is a skill (R21 to R34).
- "Never merges" is enforcement, so by the same skill it is a hook. The requester moved the hooks to an intent of their own. Here it is the skill's wording (R31, C2).

The same skill's litmus, "if you could write an assertion for it, write code", is why R14 to R20 are in the command. Each is decided from git alone.

### Where a task is built

On the checkout `task start` is run in. asdlc makes no worktree, by the owner's decision of 2026-11-19 (C9).

The first version of this spec had `task start` make a worktree for each task, under `.worktrees/`. Three findings ended that:

- An audit found that it closed off Claude Code's own worktrees.
- A review reproduced its clean-up removing a worktree it had not made.
- A pilot found that `git worktree add` is refused inside an eval run, so the skill's acting cases could not have been built.

Claude Code makes worktrees itself. Its documentation, read on 2026-11-19, says:

- `claude --worktree <name>` starts a session in `.claude/worktrees/<name>/`, on a new branch `worktree-<name>` made from the default branch on the remote.
- A subagent with `isolation: worktree` gets a worktree of its own.
- When such a session ends with the worktree on a branch other than the one Claude Code made for it, and that branch has commits of its own, the person is asked whether to keep or remove the worktree, and either answer keeps that branch and its commits.

`task start` does the same thing in such a worktree as in the main checkout: it needs a checkout with nothing uncommitted, and it moves that checkout to the task's branch. So one checkout holds one task at a time, and several tasks at once are several sessions, each started in a worktree (C9).

### The command

Two verbs from the closed set, on the noun that exists: `task start` and `task stop`. `src/asdlc/cli.py` gains both. Each takes the task's id as its one positional.

`task start <slug>/<task>` does these in order:

1. Fetch. Refuse a repository with no remote, a `gh` that cannot open a pull request here, a `main` with no checks, and a checkout with uncommitted changes (R4). Work out the task's state from the remote's `main`, the remote's branches and the pull requests, and refuse unless it is `ready` (R5).
2. Switch the checkout to a new branch, `task/<slug>/<task>`, made at the remote's `main` with `--no-track` (R1). Git carries an uncommitted change along on a switch when nothing clashes, which is why step 1 refuses one.
3. Make the empty start commit (R2), with `commit_empty` in `src/asdlc/io/git.py`.
4. Push with `git push --porcelain -u --force-with-lease=task/<slug>/<task>: origin task/<slug>/<task>`. An empty lease means "only if the remote has no such branch". The start won only when the line for the branch begins with `*`, which is a branch the push made. `=` is "up to date" and lost (R6).
5. Open the draft pull request (R3). When that fails, delete the remote's branch with a lease on this start's own commit, switch the checkout back and delete the local branch (R7).

Tried in a throwaway repository while this was revised: a branch made from `origin/main` without `--no-track` takes `origin/main` as its upstream, and a bare `git push` then fails and suggests `git push origin HEAD:main`; with `--no-track` and `-u` the upstream is the branch's own; a second push of the same commit prints `=`; the leased delete removes the branch.

Tried again on 2026-11-19 with `git switch -c` in place of a worktree. The upstream and the claiming push behave the same. A switch carries along a tracked change and an untracked file. Switching back and deleting the branch leaves the checkout as it was, from a branch and from a detached commit. A branch that another worktree has checked out is refused, with that worktree's path. When the local and the remote branch each have a commit the other lacks, the push is rejected, and after a merge of the remote's branch it is taken.

`task start --resume <slug>/<task>` does these in order:

1. Fetch, and refuse as R8 says.
2. Switch the checkout to the task's branch, making it from the remote's when the clone has none.
3. Open the draft pull request, or make a ready one a draft.
4. Merge the remote's branch in. This is last, so that a merge left in conflict still leaves the task reading `claimed`.

`task stop <slug>/<task> --message <text>` is run in the checkout that is on the task's branch, and does these in order:

1. Refuse a checkout on another branch, and uncommitted changes (R14). Fetch, and merge the remote's `main` (R15).
2. For a size 8 with only its plan: push, comment, print `plan` and stop (R20).
3. Ask the guard about the branch, and refuse on a denial (R16). Work out R18 and R19 from the branch's commits and the files each changed, and refuse when the commit at fault is not on the remote yet.
4. Read `.asdlc/checks` from the remote's `main`, run each line in the checkout, and keep its output and exit status (R12).
5. Push (R16), add the comment (R13), and mark the pull request ready or a draft (R17).

The comment is added and never edited, so a failed run stays on the pull request after a later one passes.

`.asdlc/checks` (new) holds the checks: one command line to a line, with `#` for a comment. In this repository it is the one line `just check`. It is outside `intent/`, so the guard treats it as code. A builder can change its branch's copy, and `task stop` does not read that copy.

`src/asdlc/io/github.py` runs the program named by the git config key `asdlc.gh`, and `gh` when the key is not set. That is the one seam the tests and the eval cases need: a scaffold cannot put a program on `PATH`, and it can set a key.

By layer:

- `src/asdlc/domain/build.py` (new) decides: whether a task can be started and the reason when it cannot, whether a push claimed the branch, R18 to R20 from a list of commits and their files, which paths to replace in an output and where to cut it, and `ready`, `draft` or `plan`. It takes data and returns data.
- `src/asdlc/io/git.py` gains the fetch with its limit, switching the checkout to a branch and back, the push, the leased delete, the merge, reading a file at a ref, the commits of a branch with the files each changed, and whether a checkout is clean.
- `src/asdlc/io/github.py` gains the pull request of a branch (number, link, draft or not), opening a draft, adding a comment, and marking ready or draft. `open_pull_branches` there gives branch names only today.
- `src/asdlc/io/checks.py` (new) runs one command line in a folder and gives back what it printed and its exit status.
- `src/asdlc/presentation/pull.py` (new) words the pull request's description and the comment. `src/asdlc/presentation/text.py` and `src/asdlc/presentation/data.py` gain the pull request on a task (R36).

### How tasks and their states are read

`_state` in `src/asdlc/domain/tasks.py` does not change: done when merged, in review when its branch has an open pull request, claimed when its branch exists, otherwise ready or waiting. What changes is what `src/asdlc/cli.py` hands it.

Wherever a state is shown, a branch whose pull request is a draft is passed as a branch that exists and not as one with an open pull request (R11). `_tasks` has four callers, `task list`, `task show`, `intent list` and `intent show`, and this is in `_tasks`, so the four agree. `Task` gains the pull request's link (R36).

For the four `task` commands only:

- The documents come from the remote's `main` (R9). Today `_library` reads the working tree, so a clone that has not pulled the tasks' merge lists none of them.
- They fetch first, with `git fetch --prune origin`, `GIT_TERMINAL_PROMPT=0` and a time limit (R10).
- `task start` is handed the remote's branches only (R5). `task list` and `task show` are handed local and remote branches together, as today, so a branch made with `asdlc branch new` and never pushed still reads `claimed` in the clone that has it.

`asdlc intent list`, `intent show` and `requirement list` keep reading the working tree's documents and do not fetch (C3). `asdlc branch new` is not changed.

### The skill

`plugins/asdlc/skills/building-a-task/SKILL.md` (new) (R21). Its frontmatter, by `authoring-skills`, where every field is a deviation to justify:

- `description`: what it does first, then when to load it, then what Claude gets wrong without it. It names the activity (building a task, starting work on one, picking up a task's pull request) and no file. The traps it names: making the branch or a worktree by hand, saying the checks pass without showing their output, editing a failing test, marking the pull request ready by hand, and merging.
- `context`: not set. The skill runs inline, by the requester's decision after a pilot of a fork (C1).
- `argument-hint: <slug>/<task>`.
- `allowed-tools`: `asdlc task show`, `asdlc task list`, `asdlc plan new` and `asdlc task stop`. Not `asdlc task start`: it moves the checkout to another branch, pushes, claims the task and opens a pull request, and the skill loads on Claude's judgment, so the person is asked (C5). `task stop` is pre-approved because it runs only the command lines a person merged to `main`, and pushes only to the branch of a task the person already let start.
- `disable-model-invocation`: not set (C5). `hooks`: not set.

With the skill loaded the builder works in this order:

1. Run `asdlc task start <slug>/<task>`, with `--resume` when the person asked for a started task to be picked up (R22). On a refusal, or with no id, say why and stop (R23). When `--resume` names files in conflict, resolve them and commit the merge (R29).
2. Read the task's `task.md`, the intent's `plan.md` and `spec.md`, and the files the task names.
3. For a size 8 with no plan yet: run `asdlc plan new <slug>/<task>`, write the plan, commit it alone, run `asdlc task stop` and stop (R26).
4. Build what "What to build" says (R25). When the work departs from the intent's plan, change `plan.md` in that commit and say why in its message (R27, R28).
5. Run the repository's checks while working, and fix the code when one fails (R32).
6. Commit, and run `asdlc task stop <slug>/<task>` (R30). When it names files in conflict, resolve them, commit the merge and run it again (R29). When it refuses a commit under R18 or R19, make the commit again and run it again. When it prints `draft` and the failure can be fixed, fix it and run it again. When it cannot, run it once more with `--message` and stop (R33).
7. Answer with the link and what the command printed (R34).

`task start` leaves the session's checkout on the task's branch, so the builder changes folder nowhere: every command and edit after step 1 is already in the right place (R24). The body says to make no worktree, never to merge and never to run `gh pr ready` (R22, R31).

### The eval cases

Four cases under `plugins/asdlc/evals/` (each a new `case.yaml` and `scaffold.sh`), in the format the cases there use. `tests/test_evals.py` finds them and lints what each scaffold builds.

Each scaffold makes a bare repository under `.git/` and names it `origin`, so a fetch and a push need no network. It writes a stand-in for `gh` under `.git/`, sets `asdlc.gh` to it, and puts `.asdlc/checks` on `main`. Both paths are absolute. The stand-in appends each call to a file at a fixed path, so "opened a draft", "marked ready", "the comment holds the output" and "nothing merged" are patterns on that file. The commands read through `gh` before they refuse, so a case that stays out checks for no call that changes anything: no create, comment, ready or merge. The check is a shell script, because `plugins/asdlc/scripts/install` says an eval run cannot start the machine's Python. The requester's pilot showed that graders see tool calls. A second pilot, on 2026-11-18, showed each part of this working inside an eval run (C8).

- `build-a-ready-task` acts. `main` holds an intent, its spec, its plan and one task of size 1 that changes one line of one file. Patterns check that the file holds the new line and that the checkout is on the task's branch (R1, R24), that no branch or worktree was made by hand (R22), and that the stand-in's record has a draft opened, a comment, a `ready` and no merge (R30, R31).
- `build-with-a-check-that-fails` acts. The task cannot pass the check without changing a file the task says to leave alone. Patterns check that the file is unchanged (R32), and that the record has a comment, no `pr ready` other than `pr ready --undo`, and no merge (R31, R33).
- `build-waits-for-the-merge` stays out. The task is on `tasks/<slug>` and not on `main`. Patterns check that the checkout is on the branch it started on, that no `task/` branch exists, that the record has no call that changes anything, and that the answer says the task waits for a merge, which is the reason R5 gives (R23).
- `a-question-about-a-ready-task` stays out. A task is ready, and the prompt asks what it would involve. Patterns check that the checkout is on the branch it started on, that no `task/` branch exists and that the record has no call that changes anything. This is the wrong load C5 accepts.

Besides those: `README.md` gains the two commands, the skill and `.asdlc/checks`. `.gitignore` gains `.claude/worktrees/`, where Claude Code puts its worktrees, and `.DS_Store`. Without the first, a main checkout with such a worktree under it never reads as clean to R4 and R14. Without the second, neither does a checkout on a Mac that has been opened in Finder.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The guard for a task's branch does not break. | The guard is not changed. `task stop` asks it about the branch before it pushes (R16), and CI asks it again on the pull request. |
| The task states are read as they are read today. | Met in part. The five states and the rule that picks one are unchanged. R9 and R10 read the remote for the `task` commands, and R11 reads a draft pull request as `claimed` everywhere, which today reads `in review` (C3). |
| `asdlc branch new` does not break. | Not changed. `task start` is a new verb, and a branch made with `branch new` reads as it does today. |
| The tasks already on `main` do not break. | The task format and lint are not changed. The ten tasks on `main` are merged and read `done` from the merge commits, as today. R19 applies only when `task stop` is run. |
| Anything Claude loads lands with an eval case where it acts and one where it stays out. | R35. |
| It stays as close as it can to Anthropic's AI-native SDLC course. | The rows below. C1, C2 and C4 say where it falls short. |
| The course's lesson on parallel sessions says "Each parallel task gets its own worktree" and "Each independent session knows nothing about the others, and the engineer steering them is the only thing they share." | Met in part. asdlc makes no worktree (R1, C9). A person who builds tasks side by side starts each session with `claude --worktree`, and `task start` does there what it does in the main checkout. R21: the skill runs inline, one session for each task, and the person steers it. A session knows nothing of another's, and the remote is where one sees that a task is taken (R5). |
| The same lesson says "A subagent runs inside a single session as a scoped helper with its own context window and tool limits and suits jobs that recur in multiple tasks, such as verifying the app runs as expected." | R21. The builder is the session, and no subagent builds. |
| The course's lesson on the feedback loop says "Run the tests before reporting a task complete, and show the output.", "If a test fails, fix the code, not the test." and "An agent fixing code must not be able to weaken the check on that code." | R12, R13 and R17 for the first: the command runs the checks and posts what they printed, and it marks the pull request ready only when they passed. R32 for the second. Met in part for the third: R12 takes the command lines from `main`, so the builder cannot choose a weaker one, and it can still change what those lines run (C4). |
| The course's lesson on plan mode says "When implementation departs from the plan, update `plan.md` in the same commit." | R27, and R18 holds the pull request as a draft when the plan changed in a commit with no code. |
| Decided already, in the generate-tasks spec: two tasks may change the same file, and a conflict is resolved on the branch that merges second, the way developers normally would. Resolving it is the builder's job. | R15 merges `main` and names the files in conflict, and R29 has the builder resolve them on the branch. After the builder has stopped, Q6's answer applies and R8 is how the branch is picked up again. |
| A task of size 8 starts with a plan of its own, as the generate-tasks spec says. | R26 and R20: the plan is committed and pushed alone, and a person reads it before any code. R19 checks the order. |
| Starting several tasks at once and choosing which to start is not part of this. That is a later piece of work. | Nothing here does either. `task start` takes one task, and with no task named the builder starts none (R23). |

## Open questions from intent

### Q1: Should a task be linked to a pull request to show when it is in progress?
- answer: answered

From the requester, when the spec was asked for. Yes, and it is enforced by the command and is what happens with no flag. `task start` opens the draft pull request before any work (R3), and a start that cannot open one is undone (R7). The draft reads as `claimed` (R11), and `task show` gives the link (R36).

### Q2: Should `asdlc task` give a way to create a branch and a pull request from the task?
- answer: answered

From the requester. Yes: `asdlc task start` (R1 to R8). `asdlc task stop` is its other half, and is how the pull request leaves draft (R12 to R20).

### Q3: How does this work with claims? Does starting a task also push, and how does asdlc know about tasks started somewhere else?
- answer: answered

From the requester. The remote is the source of truth, and asdlc looks across every branch on it. Starting pushes (R3), and that push is the claim (R6). The `task` commands fetch before they read (R10). The requester carried the answer through after a review: the remote is also the source of truth for which tasks exist (R9).

### Q4: Is the builder a session of its own, a subagent, or a skill?
- answer: answered

From the requester. A skill now and an agent later. The steps are a procedure, so they are a skill (R21), and the mechanics are the `asdlc` command (R1 to R20). The skill is inline, one session for each task, by the requester's decision after a pilot of a forked skill. "Never merges" is enforcement and so a hook, and the requester moved the hooks to an intent of their own (C2). A thin worker agent that preloads the skill, and gives each task a fresh context, comes with the later work on starting several tasks at once.

### Q5: What does the builder do when the checks fail and it cannot fix them, or the task turns out bigger than its size?
- answer: answered

From the requester. It stops and reports: the pull request stays a draft with the failing output on it, the builder says what failed, and for a task bigger than its size it proposes a split (R33). It never weakens a check (R32). `task stop` decides draft or ready from the checks' exit status (R17). The builder is told never to mark the pull request ready by hand (R31), and nothing in this spec stops it (C2).

### Q6: Who resolves a conflict that appears after the builder has finished, when its pull request is open and main has moved?
- answer: answered

From the requester. Whoever runs into it. That is usually the person at the merge. They resolve it on the branch themselves, or ask for the task to be picked up: the builder resumes the branch (R8, R22), `task stop` merges `main` (R15) and the builder resolves what conflicts (R29). Nothing watches an open pull request for a conflict.

## Areas of concern

### C1: An inline builder is given the task and nothing else only when the person opens a session for it
- owner: Bruk Habtu

Skills: `authoring-kit:choosing-extension-types` and `authoring-kit:authoring-skills`.

Decided by the owner, Bruk Habtu, on 2026-11-18, after a pilot. What follows says what was decided and what it costs.

The outcome says the work is done by something that was given the task and nothing else. `choosing-extension-types` offers `context: fork` for work that need not see the conversation, and a fork is the only thing that gives "nothing else" in a session that has talked about other things. The pilot showed what a fork costs here: it starts in the session's own folder, its `cd` does not carry to the next call, and the person reads the main session's rewrite of its result.

Decided, and what R21 requires: inline, one session for each task. The builder works in the session's checkout (R24), and the person can steer it. Since C9's decision the builder changes folder nowhere, so the first two of a fork's costs no longer apply. The third stands, and the decision is not reopened here. The cost is that the outcome rests on the person: a session that has already talked about other work builds with all of that in view. A fresh context for each task comes with the later worker agent. `authoring-skills` notes that a preloaded skill's `allowed-tools` does not carry into an agent, so that agent states its own.

### C2: Nothing stops the builder merging, or marking its own pull request ready by hand
- owner: Bruk Habtu

Skill: `authoring-kit:authoring-hooks`.

Decided by the owner, Bruk Habtu, on 2026-11-18. The intent says it never merges. Enforcement that must not depend on the model is a hook, and the hooks are an intent of their own: one that refuses `gh pr merge`, and the guard refusing a push that puts a branch of the loop on `main`. The guard reading the folder a push runs in lands by itself.

So in this spec "never merges" and "never marks its own pull request ready by hand" are the skill's wording (R31) and nothing more. `gh pr merge` and `gh pr ready` are each one Bash call. Until that intent is built, the eval cases' record of `gh` calls is the only check, and a person reading the pull request is the only stop.

### C3: Tasks and their states are read from the remote, which is not how they are read today
- owner: Bruk Habtu

The intent says the task states are read as they are read today. Three things change.

- A draft reads `claimed` (R11). Today any open pull request reads `in review`, and with a pull request opened at the start every task would read `in review` from its first minute. Proposed as written. The cost: a draft opened by hand on a task's branch now reads `claimed`.
- Which tasks exist comes from the remote's `main` (R9), decided by the owner on 2026-11-18. The cost: tasks on a `tasks/<slug>` branch that is checked out and not merged are no longer listed.
- The `task` commands fetch each time (R10), so they are slower, and warn when the remote cannot be reached.

`intent list`, `intent show` and `requirement list` still read the working tree's documents and do not fetch. In a clone that is behind, they can disagree with `task list` about which tasks exist. Proposed: leave them for a later change.

`asdlc task list --root examples/claims` lists the example's tasks today. That root is inside a repository with a `main`, so R9 as written reads this repository's `main` and not the example. The plan has to say what a `--root` below the repository's root reads.

### C4: The builder cannot choose a weaker check, and can still change what a check runs
- owner: Bruk Habtu

Skill: `authoring-kit:choosing-extension-types`.

The intent quotes "An agent fixing code must not be able to weaken the check on that code". R12 takes the command lines from `.asdlc/checks` on `main`, so the builder gives `task stop` none. But a task may rightly change a test, and whether a change weakens one needs a rubric and not an assertion, so by `choosing-extension-types` it is not code. A branch can still change the tests, the `justfile` and the CI workflow. What is left: the skill says never (R32), CI runs on the pull request whatever the builder ran, and the reviewer sees every such change in the diff.

Two routes to a weaker check do not show in a diff: the environment `task stop` is run with, and files git does not show. Only CI covers them.

A task whose job is to change the checks cannot pass `main`'s old lines once they stop working. It stays a draft that a person ends.

`.asdlc/checks` is also a new thing for a repository to adopt. No task can be started until it is on `main` (R4).

### C5: The skill loads on Claude's judgment, and its first step publishes
- owner: Bruk Habtu

Skill: `authoring-kit:authoring-skills`.

`authoring-skills` says to set `disable-model-invocation` on anything that must never fire on Claude's judgment. `task start` moves the checkout to another branch, pushes that branch, claims the task and opens a pull request. The intent has the skill load when a person asks, and needs a case where it stays out. The later agent is to preload it, and a skill with that field set cannot be preloaded.

Proposed, and what the design does: the field is not set, and `task start` is not pre-approved, so a wrong load meets a permission prompt before anything is published. `a-question-about-a-ready-task` measures the wrong load. The cost is one prompt for each start, in a session that has not allowed it.

The four skills on `main` have `Bash(asdlc *)`, which now pre-approves `task start` and `task stop` in a turn that loaded one of them. This spec does not change them.

### C6: A task cannot be started without GitHub
- owner: Bruk Habtu

Today `gh` is optional: without it no task reads `in review` and everything else works. Q1's answer makes the pull request part of starting, so R4 refuses a repository with no GitHub remote, a `gh` that is signed out, and a repository that cannot open drafts. Proposed: accept it. `asdlc branch new task/<slug>/<task>` still works there, with no pull request and no `task stop`.

### C7: What a check prints becomes public
- owner: Bruk Habtu

Decided by the owner, Bruk Habtu, on 2026-11-18: R13 takes the checkout's path out of the output and posts the rest as printed. Replacing the home folder as well is this spec's addition. Anything else a check prints is posted: a user name in another path, a host name, a value from the environment. A repository whose checks print such things has to quieten them itself.

### C8: Some requirements have no eval case, and the commands have not been run inside an eval
- owner: Bruk Habtu

The two things the first version of this spec did not know were tried on 2026-11-18.

- A pilot inside an eval run, with a throwaway plugin. A scaffold's remote under `.git/` takes a fetch and a push, a stand-in set through git config is run, and graders read the stand-in's record there. `git worktree add` is refused, which is one of the reasons for C9.
- A trial against GitHub, pull request #101, now closed. GitHub opens a draft pull request on a branch whose only commit is empty, which R2 and R3 rest on. The claiming push printed `*` and then `=`, and the leased delete removed the branch.

Not tried: `asdlc task start` and `task stop` themselves inside an eval run, since they are not built. One thing could stop them there: R4 refuses a checkout with an untracked file, and nobody has looked at whether an eval run's folder holds one that the scaffold did not make. The plan pilots `build-a-ready-task` with one run before any other grader is written.

No case checks R25, R26, R27, R28, R29, the `--resume` half of R22, or the split R33 proposes. R1 to R20 are code, and are checked by tests under `tests/` with a bare repository on disk and a stand-in for `gh`.

### C9: asdlc makes no worktree, so a task is built on the checkout the session is in
- owner: Bruk Habtu

Decided by the owner, Bruk Habtu, on 2026-11-19: `task start` makes the task's branch in the checkout it is run in, and worktrees are left to Claude Code. "Where a task is built", in the Design, says what ended the first version, where `task start` made a worktree for each task.

The intent's outcome is "The work is done in a worktree of its own, so several tasks can be built at once." asdlc no longer brings that about. It holds when the person starts the session with `claude --worktree`, and nothing here checks that they did. What it costs:

- A session in the main checkout moves that checkout to the task's branch and leaves it there when the task is stopped. The person switches back.
- One checkout holds one task at a time. Two tasks at once need two sessions, each started in a worktree.
- `task start` and `task stop` refuse a checkout with an untracked file that git does not ignore (R4, R14). A stray file stops a start until it is ignored or removed.
- Nothing removes a task's local branch after its pull request is merged or closed. The intent does not ask for a cleanup and this spec adds none. A worktree that Claude Code made is Claude Code's to remove.

Not tried: `task start` in a session started with `claude --worktree`, and what Claude Code asks when that session ends. The Design gives what its documentation says. Giving each task a worktree and a fresh context without the person arranging it is left for the later worker agent.
