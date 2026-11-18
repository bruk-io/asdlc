---
kind: spec
---
# Spec: Build a ready task into a pull request

## Requirements

R1 to R7 are about starting a task, R8 to R10 about how its state is read, R11 to R17 about stopping, R18 to R31 about the skill, R32 to R35 about the hooks, and R36 about the eval cases.

Four words are used throughout. The **builder** is Claude with the `building-a-task` skill loaded, running as R19 says. A task is **started** when its branch is on the remote with a pull request. A **check** is a command line of the repository's own that passes or fails, such as `just check`. A **branch of the loop** is one named `intent/<slug>`, `spec/<slug>`, `plan/<slug>`, `tasks/<slug>`, `task/<slug>/<task>` or `change/<slug>`.

### R1: `asdlc task start <slug>/<task>` makes the branch `task/<slug>/<task>` from the remote's `main`, in a worktree of its own

The worktree is `.worktrees/<slug>/<task>` under the repository's root. The checkout the command was run from is left on its branch, with its files as they were. The command prints one line: the worktree's path, the branch and the pull request's link.

### R2: The branch's first commit is an empty one that records when the task was started

Its subject is `Start task <slug>/<task>`, as `asdlc intent new` records the start of an intent.

### R3: `task start` pushes the branch and opens a draft pull request for it, before any work is done

The pull request is against `main` and is titled `Task: <the task's title>`. Its description names the task's `task.md` and the requirements it delivers. This is what the command does with no flag.

### R4: When the pull request cannot be opened, `task start` leaves nothing started

It deletes the branch from the remote, removes the worktree and the local branch, says why on stderr and exits 1. So a started task always has a pull request.

### R5: `task start` starts only a task that reads as `ready` on the remote

It fetches first. It refuses, with exit 1 and the reason, a task whose `task.md` is not on the remote's `main`, and a task that is `waiting`, `claimed`, `in review` or `done`. For a claimed task or one in review, the reason gives the pull request. A target that names no task exits 3.

### R6: When one task is started from two clones, at most one start succeeds

The push is the claim. It is refused when the remote already has the branch, and the start that lost removes what it made, as in R4.

### R7: `task start --resume` gives a worktree on a task that is already started, and opens no second pull request

The worktree holds the remote's branch as it is. When the task's worktree is already there, the command prints the same line and changes nothing. It refuses a task that is not `claimed` or `in review`.

### R8: `asdlc task list` and `asdlc task show` read the branches and `main` from the remote

They fetch before they read, so a task started from another clone shows as `claimed` without anyone running `git fetch`. When the repository has no remote they read what is local, as today. When the remote cannot be reached they say so on stderr and read what was last fetched.

### R9: A task whose pull request is a draft reads as `claimed`, and as `in review` once the pull request is marked ready

### R10: `asdlc task show` gives the task's pull request

A `pull-request` line holding the link, and a `pull_request` field under `--json`. Both are empty for a task with none.

### R11: `asdlc task stop <slug>/<task>` runs each `--check` in the task's worktree, and adds what each printed to the pull request, as it was printed

`--check <command line>` is repeatable, and at least one is needed. The command adds one comment to the pull request. For each check the comment holds the command line, the exit status and everything the check printed, unedited. Output longer than the comment can hold is cut from the top, and the comment says how many lines were cut. The comment also holds the commit the checks ran on, each file the guard marked with the message of the commit that changed it, and the text of `--message` when one is given.

### R12: `task stop` marks the pull request ready for review only when every check passed, and makes it a draft when one failed

It prints the pull request's link and `ready` or `draft`. It exits 0 for `ready` and 1 for `draft`. A pull request that was ready goes back to a draft when a later `task stop` fails.

### R13: `task stop` runs no check on work the pull request does not show

It refuses, with exit 1 and nothing run, a worktree with uncommitted changes, and a branch whose last commit is not on the remote.

### R14: `task stop` refuses a branch that does not hold the remote's `main`

It fetches first. When `main` has commits the branch does not, it says to merge `main` into the branch, exits 1 and runs nothing.

### R15: `task stop` leaves a draft when a commit on the branch changes the intent's `plan.md` and no file outside `intent/`

### R16: `task stop` leaves a draft when a task of size 8 did not start with a plan of its own

The first commit after the start has to add `intent/<slug>/tasks/<task>/plan.md` and change nothing else.

### R17: `task stop` leaves a draft when the guard denies a file the branch changed

In R15, R16 and R17 the comment says which rule failed, as it does for a check.

### R18: The plugin has a skill, `building-a-task`, that loads when someone asks for a task to be built

It loads on a plain request, such as "build generate-tasks/02-spike-case" or "pick up that task's pull request and resolve the conflict". Nobody has to name it.

### R19: The skill runs as a fork, so the builder is given the task's id and none of the conversation

### R20: The builder starts with `asdlc task start`, and makes no branch, worktree or pull request by hand

It passes `--resume` only when it was asked to pick up a task that is already started.

### R21: Given no task, or a task that `task start` refuses, the builder builds nothing and says why

With no task named it gives the tasks that read as `ready` and starts none. With a refusal it repeats the reason, which names the merge the task waits for or the pull request it already has.

### R22: The builder changes files only in the task's worktree

### R23: The builder builds what the task's "What to build" says, and reports anything else it found instead of doing it

### R24: For a task of size 8, the builder writes the task's own plan and commits it first

It starts the plan with `asdlc plan new <slug>/<task>` in the worktree. The plan talks through the risk the task names.

### R25: When the work departs from the intent's plan, the builder changes `plan.md` in the same commit as the code, and that commit's message says why

### R26: The builder changes no other document

The task's own `plan.md` and the intent's `plan.md` are the only files under `intent/` it writes. It does not edit the task's `task.md`, and it cuts no task.

### R27: Before it stops, the builder merges the remote's `main` into the branch and resolves any conflict on the branch

It merges and does not rebase, because the branch is already pushed.

### R28: The builder ends with `asdlc task stop`, and gives it the repository's checks

The checks are the ones the task's "Done when" and the repository's own instructions name. The builder pushes with `git push` before it runs the command, so the guard judges the push.

### R29: When a check fails, the builder changes the code and never the check

It does not edit, skip or delete a failing test, loosen a linter's configuration, or give `task stop` a weaker command line than the repository names.

### R30: When it cannot get the checks to pass, or the task turns out bigger than its size, the builder stops and leaves the pull request a draft

It still runs `task stop`, so the failing output is on the pull request, and gives `--message` what failed and what it tried. For a task that is bigger than its size the message proposes a split: which tasks, and what each would build.

### R31: The builder's answer gives the pull request's link and says whether it is ready or a draft

For a draft it says what failed.

### R32: In every session and subagent, Claude Code refuses to run a `gh pr merge` of a pull request from a branch of the loop

The refusal names the pull request and its branch, and says that merging it is a person's decision.

### R33: A `gh pr merge` is also refused when the hook cannot tell which branch it would merge

That is when `asdlc` was not installed for the session, when `gh` does not answer, and when the hook fails, times out or prints nothing it can use.

### R34: The guard hook refuses a `git push` that would put a branch of the loop on `main`

A push whose destination is `main` is refused when the commits it would add hold the tip of a branch of the loop that the remote's `main` does not hold yet.

### R35: The guard hook judges the folder a push runs in when the command changes folder first

For `cd <folder> && git push` it judges the repository at `<folder>`, as it does for `git -C <folder> push`.

### R36: The skill has an eval case where it must act and one where it must stay out

## Design

Skills applied: `authoring-kit:choosing-extension-types`, `authoring-kit:authoring-skills` and `authoring-kit:authoring-hooks`.

### What is code, what is a skill and what is a hook

`choosing-extension-types` asks first whether the model should do a thing at all, and has the earliest answer win. Read against the intent's outcomes:

- Making the branch and the worktree, recording the start, pushing, opening the pull request, running the checks and copying their output are each "given X, produce Y". They are the `asdlc` command (R1 to R17). The model picks the moment and the parameters and does none of it by hand (R20, R28).
- "Never merges" has to hold whether or not the model remembers it. It is a hook (R32 to R34).
- What is left needs judgment: reading the task, writing the code, deciding whether a failure can be fixed, resolving a conflict, proposing a split. That is a procedure, so it is a skill (R18 to R31).
- None of the four differences that justify an authored agent applies. The work is one skill's body, the policy is for this one procedure, and starting several tasks at once is not part of this intent. So no agent is written here.

The same skill's litmus, "if you could write an assertion for it, write code", is why R13 to R17 are in the command and not in the skill's prose. Each is decided from git alone.

### The command

Two verbs from the closed set, on the noun that exists: `task start` and `task stop`. `src/asdlc/cli.py` gains both. Each takes the task's id as its one positional.

`task start <slug>/<task>` does these in order, and undoes what it made when a later one fails (R4):

1. Fetch from the remote, and work out the task's state as R8 and R9 say. Refuse unless it is `ready` (R5).
2. Make `task/<slug>/<task>` at the remote's `main` in a new worktree, `.worktrees/<slug>/<task>` under the root of the main checkout, also when the command is run from inside another worktree (R1). The folder is added to `.git/info/exclude`, so no tracked file changes and the main checkout stays clean.
3. Make the empty start commit (R2), with `commit_empty` in `src/asdlc/io/git.py`.
4. Push with `git push --force-with-lease=task/<slug>/<task>: origin task/<slug>/<task>`. An empty lease means "only if the remote has no such branch", so the remote decides which of two starts wins (R6). Tried on a bare repository while this was written: the second clone's push is rejected.
5. Open the draft pull request with `gh pr create --draft` (R3).

The worktree is outside `.claude/` on purpose. `authoring-hooks` records that a write under `.claude/` is refused as a protected path in a headless run, and an eval run is headless.

`task stop <slug>/<task> --check <command line> --message <text>` finds the task's worktree and does these in order:

1. Refuse a dirty worktree and an unpushed branch (R13). Fetch, and refuse a branch that does not hold the remote's `main` (R14).
2. Work out R15, R16 and R17 from the branch's commits and the files each changed.
3. Run each check through `sh -c` in the worktree, and keep its output and exit status (R11).
4. Add the comment with `gh pr comment` (R11).
5. Mark the pull request ready with `gh pr ready` when nothing failed, and otherwise make it a draft with `gh pr ready --undo` (R12).

The comment is added and never edited, so a failed run stays on the pull request after a later one passes.

By layer:

- `src/asdlc/domain/build.py` (new) decides: whether a task can be started and the reason when it cannot, R15 and R16 from a list of commits and their files, where to cut a long output, and whether the result is `ready` or `draft`. It takes data and returns data.
- `src/asdlc/io/git.py` gains the fetch, the worktree, the push with a lease, deleting a remote branch, the commits of a branch with the files each changed, and whether a worktree is clean.
- `src/asdlc/io/github.py` gains the pull request of a branch (number, link, draft or not), opening a draft, adding a comment, and marking ready or draft. `open_pull_branches` there gives branch names only today.
- `src/asdlc/io/checks.py` (new) runs one command line in a folder and gives back what it printed and its exit status.
- `src/asdlc/presentation/pull.py` (new) words the pull request's description and the comment. `src/asdlc/presentation/text.py` and `src/asdlc/presentation/data.py` gain the pull request on a task (R10).

### How a task's state is read

`_state` in `src/asdlc/domain/tasks.py` does not change: done when merged, in review when its branch has an open pull request, claimed when its branch exists, otherwise ready or waiting. What changes is what `_tasks` in `src/asdlc/cli.py` hands it:

- It fetches with `git fetch --prune origin` first (R8). `branches` in `src/asdlc/io/git.py` already lists local and remote branches together, and `base` already prefers `origin/main`, so after a fetch both are the remote's.
- A branch whose pull request is a draft is passed as a branch that exists and not as one with an open pull request (R9). So a started task reads `claimed` until `task stop` marks it ready.

`Task` gains the pull request's link (R10). A branch made with `asdlc branch new task/<slug>/<task>` and never pushed still reads `claimed` in the clone that has it, as today. `asdlc branch new` is not changed.

### The skill

`plugins/asdlc/skills/building-a-task/SKILL.md` (new) (R18). Its frontmatter, by `authoring-skills`, where every field is a deviation to justify:

- `description`: what it does first, then when to load it, then what Claude gets wrong without it. It names the activity (building a task, starting work on one, picking up a task's pull request) and no file. The traps it names: making the branch by hand, building in the main checkout, opening the pull request only at the end, saying the checks pass without showing their output, editing a failing test, and merging.
- `context: fork` (R19). The work is self-contained with noisy intermediates, and the main conversation needs only the result, which is the case the skill gives for a fork. A fork does not inherit the conversation, which is what the outcome "given the task and nothing else" asks for (C1).
- `agent`: not set. The default, `general-purpose`, can write. A read-only type hosting this work would fail silently.
- `background: false`. The person asked for a pull request, so the turn waits for the fork's answer (R31), and a foreground fork keeps the whole tool set.
- `argument-hint: <slug>/<task>`. The body uses no argument placeholder, so the id arrives as the line the loader appends. That keeps the body right for the later agent that preloads it, where placeholders are not substituted.
- `allowed-tools`: `asdlc task start`, `asdlc task show`, `asdlc task list`, `asdlc plan new`, `asdlc document check` and `asdlc branch check`. Not `asdlc task stop`: it runs command lines the builder chose, and pre-approving it would pre-approve any command (C5). The four skills on `main` have `Bash(asdlc *)`; this one is narrower.
- `disable-model-invocation`: not set (C6). `hooks`: not set. A skill's hooks stay registered until the session ends, so the hook is the plugin's (C3).

The body is an explicit task and not guidance, because a forked body is the fork's whole prompt. With the skill loaded the builder works in this order:

1. Run `asdlc task start <slug>/<task>` (R20). On a refusal, or with no id, say why and stop (R21).
2. Read the task's `task.md`, the intent's `plan.md` and `spec.md`, and the files the task names. All of them are in the worktree.
3. For a size 8, run `asdlc plan new <slug>/<task>`, write the plan and commit it alone (R24).
4. Build what "What to build" says, in the worktree (R22, R23). When the work departs from the intent's plan, change `plan.md` in that commit and say why in its message (R25, R26).
5. Run the repository's checks while working, and fix the code when one fails (R29).
6. Fetch, merge `origin/main` into the branch and resolve any conflict (R27).
7. Push with `git -C <worktree> push`, then run `asdlc task stop <slug>/<task>` with a `--check` for each check (R28). When it prints `draft` and the failure can be fixed, fix it and run it again. When it cannot, run it once more with `--message` and stop (R30).
8. Answer with the link and `ready` or `draft` (R31).

Every command in the body names the worktree, with `git -C` or an absolute path. A subagent's `cd` does not carry to its next call.

### The hooks

`plugins/asdlc/hooks/hooks.json` gains one handler and keeps its three. Checked with the `hooktool validate --plugin` that `authoring-hooks` ships: the new block is valid, and so is the file as it stands.

- Event `PreToolUse`, matcher `Bash`, `if: Bash(gh pr merge*)`, a `command` handler that runs `asdlc hook run merge` from `${CLAUDE_PLUGIN_DATA}`, as the two guard handlers do (R32). The decision is fixed logic, so it is a `command` handler and not a `prompt` one.
- It refuses with the `permissionDecision: deny` JSON on stdout that `push_denial` in `src/asdlc/presentation/hook.py` already uses, so the reason reaches Claude.
- It sets `"onFailure": "block"`, and its shim exits 2 when `asdlc` is not installed (R33). `authoring-hooks` says exit 1 does not block, and that a gate which must not fail open sets this.
- A plugin's hooks fire inside subagents too, so the fork is covered with nothing more.

`asdlc hook run merge` is a third entry in `_HOOKS` in `src/asdlc/cli.py`. It reads the pull request the command names, or the current branch's when it names none, asks `gh pr view` for its head branch, and denies when `src/asdlc/domain/guard.py` says that is a branch of the loop.

The existing guard hook gains two things, both in `src/asdlc/domain/shell.py`, which reads a command for a push today:

- It reads a push's destination. When that is `main`, the hook denies a push whose new commits hold the tip of a branch of the loop that `origin/main` lacks (R34). Without this, `git merge` then `git push` does what `gh pr merge` was refused.
- `push_folder` reads a `cd <folder>` before the push (R35). Today `cd <worktree> && git push` is judged against the session's own folder, so a builder's push from a worktree would be judged as the main checkout's branch.

The guard's rules in `src/asdlc/domain/guard.py` for what a branch may change are not touched. `src/asdlc/io/hook.py` already reads the command and its folder.

### The eval cases

Three cases under `plugins/asdlc/evals/` (each a new `case.yaml` and `scaffold.sh`), in the format the cases there use. `tests/test_evals.py` finds them and lints what each scaffold builds. C7 says what is not known about running them.

- `build-a-ready-task` acts. `main` holds an intent, its spec, its plan and one task of size 1 that changes one function and its test. Patterns check that the changed file is under `.worktrees/` and not in the main checkout (R22), that no branch or worktree was made by hand (R20), that nothing was merged, and that the answer has `ready` or `draft` (R31).
- `build-waits-for-the-merge` stays out. The task is on `tasks/<slug>` and not on `main`. Patterns check that there is no `.worktrees/` folder, that no `task/` branch was made by hand, that nothing was merged, and that the answer says which merge the task waits for (R21).
- `build-with-a-check-that-fails` acts. The task cannot pass the repository's test without changing a test the task says to leave alone. Patterns check that the test file is unchanged (R29) and that the answer says `draft` (R30).

Besides those: `README.md` gains the two commands, the hook and the skill, and `CLAUDE.md` says four hooks where it says three.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The guard for a task's branch does not break. | The rules in `src/asdlc/domain/guard.py` for what `task/<slug>/<task>` may change are not touched. R34 and R35 add to the guard hook: R34 acts only on a push to `main`, and R35 makes the hook judge the worktree a push runs in. |
| The task states are read as they are read today. | Met in part. The five states and the rule that picks one are unchanged. R8 reads the remote first and R9 reads a draft pull request as `claimed`, which today reads `in review` (C2). |
| `asdlc branch new` does not break. | Not changed. `task start` is a new verb, and a branch made with `branch new` reads as it does today. |
| The tasks already on `main` do not break. | The task format and lint are not changed. The ten tasks on `main` are merged and read `done` from the merge commits, as today. R16 applies only when `task stop` is run. |
| Anything Claude loads lands with an eval case where it acts and one where it stays out. | R36. |
| It stays as close as it can to Anthropic's AI-native SDLC course. | Met in part. The rows below say where it follows the course, and C1 and C4 say where it departs. |
| The course's lesson on parallel sessions says "Each parallel task gets its own worktree" and "Each independent session knows nothing about the others, and the engineer steering them is the only thing they share." | R1 for the worktree. R19: a builder is given its task and knows nothing of another builder, and the remote is all they share. Not met for the engineer steering: a fork cannot be steered or asked while it works (C1). |
| The same lesson says "A subagent runs inside a single session as a scoped helper with its own context window and tool limits and suits jobs that recur in multiple tasks, such as verifying the app runs as expected." | Not met. The builder is a forked skill, which is a subagent of the session that asked, and it does the building (C1). The requester chose a skill in Q4. |
| The course's lesson on the feedback loop says "Run the tests before reporting a task complete, and show the output.", "If a test fails, fix the code, not the test." and "An agent fixing code must not be able to weaken the check on that code." | R11 and R12 for the first: the command runs the checks, copies the output, and nothing else marks the pull request ready. R29 for the second. Not met for the third: the builder is told not to, and nothing makes it unable (C4). |
| The course's lesson on plan mode says "When implementation departs from the plan, update `plan.md` in the same commit." | R25, and R15 holds the pull request as a draft when the plan changed in a commit with no code. |
| Decided already, in the generate-tasks spec: two tasks may change the same file, and a conflict is resolved on the branch that merges second, the way developers normally would. Resolving it is the builder's job. | R27, and R14 refuses to mark ready a branch that does not hold `main`. After the builder has stopped, Q6's answer applies and R7 is how a builder picks the branch up again. |
| A task of size 8 starts with a plan of its own, as the generate-tasks spec says. | R24, and R16 checks it. |
| Starting several tasks at once and choosing which to start is not part of this. That is a later piece of work. | Nothing here does either. `task start` takes one task, the skill is given one id, and with no id it starts none (R21). |

## Open questions from intent

### Q1: Should a task be linked to a pull request to show when it is in progress?
- answer: answered

From the requester, when the spec was asked for. Yes, and it is enforced by the command and is what happens with no flag. `task start` opens the draft pull request before any work (R3), and a start that cannot open one leaves nothing started (R4). The draft reads as `claimed` (R9) and `task show` gives its link (R10).

### Q2: Should `asdlc task` give a way to create a branch and a pull request from the task?
- answer: answered

From the requester. Yes: `asdlc task start` (R1 to R7). `asdlc task stop` is its other half, and is how the pull request leaves draft (R11 to R17).

### Q3: How does this work with claims? Does starting a task also push, and how does asdlc know about tasks started somewhere else?
- answer: answered

From the requester. The remote is the source of truth, and asdlc looks across every branch on it. Starting pushes (R3), and that push is the claim (R6). `task list`, `task show`, `task start` and `task stop` fetch before they read (R5, R8, R14).

### Q4: Is the builder a session of its own, a subagent, or a skill?
- answer: answered

From the requester. A skill now and an agent later. The steps are a procedure, so they are a skill (R18). The mechanics are the `asdlc` command (R1 to R17), and "never merges" is a hook (R32). A thin worker agent that preloads the skill comes with the later work on starting several tasks at once. That the skill is forked is this spec's reading of `choosing-extension-types` against the outcome "given the task and nothing else", and is not the requester's answer. C1 holds it.

### Q5: What does the builder do when the checks fail and it cannot fix them, or the task turns out bigger than its size?
- answer: answered

From the requester. It stops and reports: the pull request stays a draft with the failing output on it, the builder says what failed, and for a task bigger than its size it proposes a split (R30). It never weakens a check (R29). `task stop` decides draft or ready from the checks' exit status, so the builder cannot report a failed task as ready (R12).

### Q6: Who resolves a conflict that appears after the builder has finished, when its pull request is open and main has moved?
- answer: answered

From the requester. Whoever runs into it. That is usually the person at the merge. They resolve it on the branch themselves, or ask for the task to be picked up: the builder resumes the branch (R7, R20), merges `main` (R27) and runs `task stop` again. Nothing watches an open pull request for a conflict.

## Areas of concern

### C1: A forked builder cannot be steered or asked, and the course has the engineer steer each session
- owner: Bruk Habtu

Skills: `authoring-kit:choosing-extension-types` and `authoring-kit:authoring-skills`.

Two things in the intent pull apart. The outcome says the work is done by something that was given the task and nothing else. The course, which the intent stays close to, has parallel sessions build with the engineer steering them, and keeps subagents for helpers such as a verifier.

`choosing-extension-types` routes self-contained work that need not see the conversation to a skill with `context: fork`, and says isolation is never a reason to author an agent. `authoring-skills` adds that a fork cannot see the conversation. Only a fork gives "nothing else" when the session that asks has already talked about other things. But a fork is a subagent, it cannot ask the person a question, and the person cannot correct it while it works.

Proposed, and what R19 requires: fork. The person steers before, through the task, and after, through the pull request. Stopping with a draft and a report (R30) is how the builder hands a question back. The cost is that a wrong turn is found at the pull request and not in the conversation, and that the plan of a size 8 (R24) is read by a person only after the code is written on top of it.

The other way is an inline skill, which the person can steer, and which is "given the task and nothing else" only when the person opens a fresh session for each task. That is closer to the course and rests on the person remembering to.

### C2: A draft pull request reads as `claimed`, which is not how the states are read today
- owner: Bruk Habtu

The intent says the task states are read as they are read today. Today any open pull request on a task's branch reads `in review`. Q1's answer opens a pull request when work starts, and Q5's answer leaves a failed task as a draft. Under today's reading every started task would read `in review` from its first minute, and a person could not tell work in progress from work waiting for them.

Proposed, and what R9 requires: a draft reads `claimed` and a pull request marked ready reads `in review`. The five states and `_state` do not change. The cost is one difference from today: a draft opened by hand on a task's branch used to read `in review` and now reads `claimed`.

R8 is a second difference. `task list` now talks to the remote each time, which is slower, and prints a warning when the remote cannot be reached.

### C3: The hook that refuses a merge cannot be told which session is the builder
- owner: Bruk Habtu

Skill: `authoring-kit:authoring-hooks`.

The intent says the builder never merges. `authoring-hooks` says a plugin's hooks register when the plugin loads and fire for every session and inside every subagent, and that a skill's own hooks stay registered until the session ends. A forked skill runs as `general-purpose`, so nothing in the hook's input says "this is the builder". The hook can be for everyone or for no one.

Proposed, and what R32 requires: it refuses for every session, and only for a pull request from a branch of the loop. That is the plugin's own rule made mechanical: merging such a branch is how a person accepts it, and all four skills on `main` already say never to merge. Other pull requests are left alone. The cost is that a person who tells Claude to merge a task's pull request is refused, and merges it themselves.

The other way is to refuse only inside a subagent. That leaves the person free to ask, and leaves a skill that runs inline unguarded.

### C4: Nothing makes the builder unable to weaken a check, or to merge by a way the hook does not read
- owner: Bruk Habtu

Skills: `authoring-kit:authoring-hooks` and `authoring-kit:choosing-extension-types`.

The intent quotes "An agent fixing code must not be able to weaken the check on that code", and says it never merges. Neither can be made impossible from inside a plugin.

For the checks: a task may rightly change a test, and whether a change weakens one needs a rubric and not an assertion, so by `choosing-extension-types` it is not code. The builder also chooses the command lines it gives `task stop`. What is done: the comment shows each command line as it ran (R11), the skill says never (R29), CI runs the repository's checks on the pull request whatever the builder ran, and the reviewer sees every change to a test in the diff. A branch can still change the tests, the `justfile` and the CI workflow.

For the merge: `authoring-hooks` says an `if` filter is best effort and that a hard deny is enforced with permissions. A plugin ships no permission rules. R32 and R34 catch `gh pr merge` and a push to `main`. They do not catch a merge through `gh api`, or a squash made locally and pushed to `main`.

Proposed: accept both, and say in the README that the hard guarantees are GitHub's: a protected `main` that requires a review, and required status checks. A later intent could have the repository declare its checks in a file that `task stop` reads from `main`, so the builder no longer chooses the command lines.

### C5: `task stop` runs command lines the builder chose
- owner: Bruk Habtu

Skill: `authoring-kit:authoring-skills`.

The outcome says the pull request shows the checks' output as they were run, so the command runs them itself and copies what they print. `authoring-skills` says `allowed-tools` is scoped to exactly what the procedure needs. Pre-approving `asdlc task stop` would pre-approve whatever follows `--check`.

Proposed, and what the design does: the skill does not pre-approve `task stop`, so each call asks the person the way any command that runs the checks would. The cost is one prompt for each `task stop`, in a session that has not allowed it.

### C6: The skill pushes a branch and opens a pull request, and loads on Claude's judgment
- owner: Bruk Habtu

Skill: `authoring-kit:authoring-skills`.

`authoring-skills` says to set `disable-model-invocation` on anything that must never fire on Claude's judgment, and names side effects Claude can run on its own as a trap. This skill's first step pushes a branch and opens a draft pull request. The intent has it load when a person asks, and needs an eval case where it stays out. The later agent is to preload it, and a skill with that field set cannot be preloaded.

Proposed, and what R18 requires: the field is not set. A wrong load costs little: `task start` refuses anything but a ready task (R5), what it makes is a draft, and closing the pull request and deleting the branch undoes it.

### C7: Three things about running the eval cases are not known
- owner: Bruk Habtu

The generate-tasks spec says an eval run is one turn with no network. Not known, and the plan pilots each with one run before any grader is written:

- Whether a scaffold can give the run a remote and a `gh`. `task start` needs a remote to push to and a `gh` that opens a pull request. A bare repository on disk can stand in for the remote. A stand-in for `gh` has to be on the run's `PATH`, and a scaffold only writes files.
- Whether a grader sees the tool calls made inside a fork. The cases above read files and the answer for that reason.
- Whether a fork's permission requests are answered in a headless run.

If a run cannot start a task, `build-a-ready-task` can show only that `asdlc task start` was run and nothing was made by hand, and `build-with-a-check-that-fails` cannot be written. Then R22 to R31 are shown by building this intent's own tasks with the skill, as the earlier specs showed their last steps in a live session.

No case checks R6, R7, R24, R25, R27, or the split R30 proposes. R1 to R17 and R32 to R35 are code, and are checked by tests under `tests/` with a bare repository on disk and a stand-in `gh`.

### C8: The guard hook lets a push through when `asdlc` was not installed for the session
- owner: Bruk Habtu

Skill: `authoring-kit:authoring-hooks`.

The outcome says the change stays inside what the task allows, and that rests on the guard. `authoring-hooks` says a policy hook must exit 2 or set `onFailure: block`, because exit 1 does not block. The two guard handlers in `plugins/asdlc/hooks/hooks.json` exit 1 when `asdlc` is missing, so a builder in such a session pushes unguarded.

Proposed: leave them. Making them fail closed would refuse every push Claude makes, in any repository, whenever the install failed. The guard in CI still judges the pull request, and that one cannot be skipped. The new merge handler does fail closed (R33), because all it can refuse is a `gh pr merge`.

### C9: Nothing removes a task's worktree
- owner: Bruk Habtu

Each started task leaves `.worktrees/<slug>/<task>` and a local branch behind after its pull request is merged or closed. The intent does not ask for a cleanup and this spec adds none. A person removes one with `git worktree remove`.
