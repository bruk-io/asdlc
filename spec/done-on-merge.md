# Spec: merging a task's pull request marks the task Done

- Intent: [`intent/done-on-merge.md`](../intent/done-on-merge.md), proposed in pull request 60 and not yet accepted; this spec stacks on it
- Status: draft. Merging this file approves it. Every answer to an intent question below is marked "proposed, for the owner to confirm" and is not settled until then.
- Plan: `plan/done-on-merge.md`

A GitHub Actions workflow in the repository that holds the board runs when a pull request closes. It calls one new asdlc command, `asdlc merged`, which asks GitHub whether the pull request was really merged into the default branch and by whom, finds the task that recorded the pull request, and, when the task carries a clean review, sets it Done through the same board transaction every other asdlc write uses. A second new command, `asdlc merge-action`, prints the workflow and writes it only when asked. Nothing an agent writes is treated as evidence of a merge, and the board guard refuses `asdlc merged` in an agent's session.

The words used below: the **pull** is the pull request the workflow ran for. A task **records** a pull when the pull's URL is among the task's references, where `asdlc finish --pr` puts it. A task's **branch** is the one written on it at its first claim (`asdlc_branch`). The **merged head** is the pull's last head commit, which is not the merge commit when the merge was a squash or a rebase.

## Requirements

### What a merge does

- **R1.** When a pull is merged into the default branch of a repository that holds a shared board and has the workflow installed, every task that records the pull is decided by the workflow with no command typed by anyone, and the decision reaches the board's `main` as one commit carrying asdlc's transaction trailer.
- **R2.** The facts of the merge come only from GitHub's answer for the pull at the time of the run: `merged` is true, the base branch is the repository's default branch, who merged it (`merged_by`), the merge commit, the merged head, the head branch and the head repository. The event payload supplies only which repository and which pull to ask about. No command-line argument, pull request title, description, comment or label, commit message, or text on the board supplies any of these facts.
- **R3.** A pull closed without merging, or merged into a branch that is not the default branch, changes nothing on the board. The run exits 0 and its log says why.
- **R4.** A merged pull that no task records, and whose head branch is no task's branch, changes nothing: no commit, no comment, exit 0, one line in the log.
- **R5.** A task that is already Done, or is no longer among the board's open tasks, is left exactly as it is: no commit and no comment.

### Finding the task

- **R6.** The task is found from the pull recorded on it. The branch is a cross-check: the pull's head branch must be the task's branch, and the pull's head repository must be the repository it was merged into. When they agree the task is decided under R8 to R12.
- **R7.** When they disagree, nothing is closed. That covers a task that records the pull but has a different branch, a task whose branch is the pull's head branch but that does not record the pull, and a pull from a fork. Each case is reported in the run's log and, when the token allows, as one comment on the pull that names the task, the two values that disagree, and the manual command that closes it.

### Reviewed or not

- **R8.** A task is made Done only if, when the run decides, it is In Review and carries the `review-passed` label, which is how `asdlc review-done --verdict clean` records the latest verdict as clean.
- **R9.** A task with no verdict, a task whose latest verdict is changes requested, and a task that is not In Review keep their status. The task gains the label `merged-unreviewed` and one comment saying which pull was merged, who merged it, and which of those three reasons applies. When the token allows, the same is said in one comment on the pull, where the person who merged will see it.
- **R10.** `asdlc review-done` records on the task the commit the reviewer had checked out (`asdlc_reviewed_head`): the commit at the head of that review's worktree, `<repo>.worktrees/review-<task id>-<reviewer>` beside the task's registered repository. When that worktree is not there it records no commit and does not fail. asdlc reads the commit from git; the reviewer does not type it.
- **R11.** A clean verdict on a commit other than the merged head still makes the task Done, and the record names the reviewed commit, the merged head, and how many commits on the merged head the review did not cover, as GitHub's comparison of the two counts them. When the reviewed commit is not an ancestor of the merged head the record says the branch was rewritten after the review; when no reviewed commit was recorded, or GitHub cannot compare the two, the record says so in those words. None of these is passed over in silence.
- **R12.** A task that records more than one pull is made Done only when GitHub says every one of them is merged into its repository's default branch. Until then the task keeps its status and one comment names each pull not yet merged and its state. A recorded pull GitHub will not show the run counts as not merged.

### The record

- **R13.** A task made Done by a merge carries, on the task: the pull's URL, the login that merged it, the merge commit, the merged head, the reviewed commit and the count from R11, the reviewer who recorded the clean verdict, and a link to the workflow run. The Done commit's message names the task, the pull and the login.
- **R14.** Dependents become available as after a manual Done: with task B depending on task A, `asdlc next` skips B before A's pull is merged and offers B after the run, with no other command in between.
- **R15.** Running the command again for the same merge, with the task's verdict and its recorded pulls unchanged, makes no commit and posts no comment. If either has changed since, it decides afresh under R8 to R12, and a task it then makes Done loses the `merged-unreviewed` label.

### Writing the board

- **R16.** The command changes the board only through asdlc's board transaction: decided on the current `origin/main`, pushed as one commit, and on a rejected push fetched, dropped and decided again, up to the same number of attempts as every other board write. A run that cannot push exits non-zero and leaves nothing unpushed.
- **R17.** The existing manual way keeps working unchanged: a person's `asdlc board task edit <id> -s Done` closes a task whether or not the workflow is installed, including a task labelled `merged-unreviewed`.

### Who may run it

- **R18.** `asdlc merged` takes no task id and no pull request number. It refuses, exits non-zero and changes nothing unless it is running as a GitHub Actions job for a pull request closing (`GITHUB_ACTIONS`, the event name, a readable event payload and a token are all present), the event's repository is the repository the board's `origin` names, and GitHub's own answer for the pull satisfies R2. When GitHub cannot be asked, it refuses and exits non-zero, so the run shows as failed and can be run again.
- **R19.** The board guard refuses `asdlc merged` in an agent's session, with the reason and the route (a person merges; the workflow runs it), and refuses an agent adding or removing the `merged-unreviewed` label as it does the two review labels. Everything the guard refuses today it still refuses: its existing tests pass unedited.

### Installing and switching off

- **R20.** `asdlc merge-action` prints the path of the workflow file and its whole text and changes nothing. With `--write` it writes that one file into the checkout or worktree it is run in, and commits and pushes nothing, so the workflow reaches the default branch through a pull request like any other change. No other asdlc command, including `init-board`, `register` and `doctor`, and no `just` recipe, installs it.
- **R21.** The workflow file's presence on the default branch is the only switch. A repository without it behaves exactly as today, and deleting the file turns the behaviour off.
- **R22.** The workflow runs from the default branch's copy of itself, never checks out or runs the pull request's code, asks for `contents: write` and `pull-requests: write` and nothing more, and uses no secret beyond the token GitHub gives the job. It runs asdlc as the uv script it is, from the public asdlc repository at a full commit id written into the file, with every action and the Backlog.md CLI pinned.
- **R23.** `asdlc merge-action` refuses, with the reason, in a repository whose board is a local board, and in a code repository whose board is kept in a separate tasks repository. In the second case it says exactly what that case needs (R24 in the design below) and that it is not built yet.

### The other listener

- **R24.** `scripts/github_channel.py` gains no path that changes a board: the constraint in `intent/hear-github-events.md` that its listener never marks a task Done stays true as written. The channel's page says that where the workflow is installed, the task may already be Done by the time the session hears of the merge, and that the board, not the event, says so.

## Design

### Reviewed (answers intent question 1) - proposed, for the owner to confirm

The task must carry a clean verdict when the merge is decided. No verdict or changes requested: not Done, labelled `merged-unreviewed`, with the comment of R9. A clean verdict on an earlier head: Done, with the gap written down (R11). The reason is that the person merged knowingly, and the record keeps what the review did not cover visible to anyone reading the task afterwards.

The stricter alternative: Done only when the reviewed commit is the merged head, or every commit after it is a merge of the default branch into the task's branch. Test-only commits are not a third exception in either version, since telling them apart means trusting paths in a diff and a test change can hide as much as a code change. The stricter rule costs this: every fix pushed after the clean verdict, a rebase before merging, and every task reviewed before this change shipped would land as `merged-unreviewed` and need the manual command, which is the bookkeeping the intent is trying to remove. It buys a board where Done always means the merged commit was the reviewed one. The choice is one function's return value, so changing it later is cheap; the owner picks.

**The code does not record the reviewed head today.** `review-done` writes the verdict as a label and a comment, the findings' counts, the cited policies and whether the plan matched, and no commit. So R10 is new work. The reviewer agent already reviews in a detached worktree at a fixed path and removes it only after `review-done`, so asdlc can read the commit there and the agent's text does not change; the path becomes a function in `scripts/asdlc` so the code and the agent cannot drift apart unnoticed. Reading the remote-tracking branch in the registered clone instead would be simpler, but any fetch between the reviewer's checkout and its verdict would record a newer commit than the one reviewed, which hides exactly the gap this is for. Verdicts recorded before this ships have no reviewed commit and fall under R11's "not recorded" wording, and still close.

### Installing asdlc in the action (answers intent question 2) - proposed, for the owner to confirm

The asdlc repository is public, so a workflow in any repository can check it out with the token it already has. The workflow checks out the board's repository at the default branch, checks out `bruk-io/asdlc` at a full commit id into a second folder, sets up uv, installs the pinned Backlog.md CLI with npm, sets the bot's git identity, and runs `uv run --script <that folder>/scripts/asdlc --board <the checkout> merged`. A checkout and not a single downloaded file, because `scripts/asdlc` imports `scripts/repo_slug.py`. There are no release tags yet, so the pin is a commit id: `merge-action` writes the commit its own clone is at when that commit is on the clone's `origin/main`, takes `--ref <commit id>` otherwise, and refuses a branch name. Updating the pin is a pull request that changes one line.

If the asdlc repository were ever made private, the default token could not read it from another repository; the honest answers then are a deploy key or token held as a secret, or publishing the two files as a release artefact. Neither is needed now.

### Finding the task (answers intent question 3) - proposed, for the owner to confirm

The pull recorded by `asdlc finish`, with the branch as the cross-check, as R6 and R7 say. The pull's URL on the task is text a worker supplied; the head branch is GitHub's record and the task's branch was written by asdlc at the claim. Requiring both means a worker cannot attach its task to someone else's pull request and have that merge close it. The cost is that a task finished without `--pr` is reported and not closed. The worker agent already passes `--pr`, so this should be rare; if it is not, accepting a branch match alone is the change to consider.

### A board in a separate tasks repository (answers intent question 4) - proposed, for the owner to confirm

Deferred, and R23 makes the installer say so. The merge happens in the code repository and the board is in another, and the token GitHub gives a job can write only to the repository the workflow runs in. So this case needs one credential that is not GitHub's own: a fine-grained personal access token, or a GitHub App installation token, with contents read and write on the tasks repository only, stored as a secret in each code repository, plus the tasks repository's name as a workflow variable. The workflow would live in the code repository, not in the repository the board lives in as the intent's outcome words it, because that is where the event fires.

The first version supports the board in the same repository as the code, as a shared board, fully. The reason to defer the other is proof, not difficulty: `asdlc merged` takes the board as a path and reads the repository from the pull, so it already does not care where the board is, but shipping a path that holds a long-lived write credential without one real repository to run the end-to-end check on would be shipping it untested. A local board is refused too: its commits are never pushed by asdlc, so there is no `origin/main` state for a job to decide on.

### Off switch (answers intent question 5) - proposed, for the owner to confirm

The workflow file is the switch (R20, R21). `merge-action` prints before it writes, writes one file, and leaves the commit and the pull request to a person or to a task, so the workflow arrives through the same review and merge as any change.

### How the command verifies, and what that does and does not stop

`asdlc merged` reads the repository and the pull request number from the event payload, then asks GitHub for that pull with `gh api` (through `$ASDLC_GH`, as `asdlc stats` already does) and decides only from the answer. The environment checks in R18 stop an accidental run. They do not stop a determined one: every one of those variables can be set by hand on a laptop.

What a person or agent on a laptop with a token could still do, if they set those variables and wrote a payload: run the command for a pull that GitHub itself says was merged into the default branch. The result is the same decision the workflow would have made, pushed under their own git identity and without a workflow run link. They cannot close a task whose pull is not merged, because the merge facts come from GitHub. The one way around that is pointing `$ASDLC_GH` at a program that lies, which is the same seam the tests use. So three things carry the weight, in this order: the guard refuses the command to agents outright (R19); the record of a real run links a workflow run that anyone can open (R13); and the Done commit made by the workflow is authored by the Actions bot, not by an engineer. The guard is a guardrail, as its own header says, and not a wall.

### The trigger

The workflow runs on `pull_request_target` with type `closed`, so the workflow definition and the token's write access come from the default branch and a pull request cannot change what runs. That event is only dangerous when the job checks out or runs the pull request's code, which this one never does (R22), and a test reads the template to hold it to that, as `tests/test_workflows.py` does for the review workflow.

There is no `concurrency` group. GitHub keeps one pending run per group and cancels the one before it, so three merges in a minute could lose the middle one. Runs race instead, and R16's retry settles the race, the same way two engineers' claims are settled.

### One decision, written as a difference

The decision is a pure function from the tasks, GitHub's answers and the reviewed commit to an outcome: done, unreviewed, waiting on other pulls, mismatch, or nothing. The shell applies the difference between that outcome and what the task already records, inside the transaction, so a retry decides again on the new `origin/main` and a second run finds nothing to change (R15, R16). The last outcome is kept on the task so the same comment is not posted twice.

## Areas of concern

- **Branch protection.** If the default branch requires pull requests, the job's push is rejected unless the Actions bot may bypass the rule. The run fails loudly and the manual way still works. Engineers' own board pushes meet the same rule today, so a repository with a shared board already has an answer; the docs page says what to allow. Owner: the repository's owner.
- **A pull closed without merging stays on the task.** If a task records two pulls and one is abandoned, R12 means the merge of the other never closes it, and the comment says which pull is in the way. The alternative, ignoring closed pulls, would let an abandoned half of the work pass for done. Owner: the owner, with intent question 1.
- **A merge the workflow never saw** (Actions down, the run cancelled) is not caught up. The run can be run again from GitHub, and R15 makes that safe. A sweep over recently merged pulls is left out of this version.
- **The guard is a steering path.** R19 changes `hooks/guard_board.py`, so the change cannot merge without the eval gate, which a person runs and which spends tokens. An eval case proving an agent cannot use `asdlc merged` would have to arrive in its own pull request (plugin spec R23, R24).
- **`asdlc permissions` allows asdlc's own commands by name**, so the new command is allowed by those rules and it is the guard alone that refuses it in a session.

## Out of scope

- A board in a separate tasks repository, and a local board (R23).
- Catching up on merges that happened before the workflow was installed or while it could not run.
- Any change to `asdlc stats`; it reads the new Done commits as it reads manual ones.
- Removing `merged-unreviewed` automatically when a person later closes the task by hand.
- Reopening a task when a merge is reverted.
- A new eval case, which travels in its own pull request.
