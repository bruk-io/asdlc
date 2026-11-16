# Spec: a task cannot go to review until its test has been shown to fail without the change

- Intent: [`intent/negative-control.md`](../intent/negative-control.md), accepted 2026-11-15 (#61)
- Status: draft. Merging this file approves it and starts planning.

A worker marks one recorded run as a control: the run of a named test without the mechanism it is meant to prove, which must fail. The same command, recorded passing afterwards on a different tree, completes it. `asdlc finish` refuses a task larger than size 1 until the hand-over has one complete control, or a written statement that no control applies. The reviewer is handed the controls as a list, not as notes to hunt through, and records how many tests it found that could not fail. Three decisions shape it: a control is marked on purpose and never inferred from a failing run that happened to come first; what counts is kept where only `asdlc` writes it, not in the task's free-text notes; and every hand-over is judged alone, because most of the tests that could not fail arrived in review fix rounds.

## Requirements

A **control** below is a named pair of recorded runs on one task. A **hand-over** is one successful `asdlc finish`: the first, and each one after a review asked for changes.

### Recording a control

- **R1.** `asdlc record-check` accepts `--control <name>` and `--without "<text>"` before the `--`. The name is what is being proven, usually the test's own name, as one word with no spaces or quote characters. The text says what was removed, disabled or not yet written for this run. Given one without the other, or an empty text, it refuses before the command runs and says which is missing and why both are asked for.
- **R2.** Without `--control`, `record-check` does what it does today: the same note, the same exit code, the same refusals. A failing run recorded without `--control` never starts a control, whatever is recorded after it.
- **R3.** A run recorded with `--control` that exits non-zero is the control's failing run. Its note says in its first line that it is offered as the control for `<name>`, and carries the `--without` text and what differed from the commit it ran on: the files with uncommitted changes and the change itself, cut to a fixed length. `record-check` then says what completes it: restore the mechanism and record the same command again.
- **R4.** A run recorded with `--control` that exits zero is recorded as a control that did not fail, and the control is unresolved. `record-check` says so in a sentence the worker cannot miss: the test passed without the mechanism, so either the wrong thing was removed or the test cannot prove it, and names the ways on (R6, R8). The exit code is still the command's.
- **R5.** A control is complete when, after its failing run, a run of the same command (the same words in the same order) is recorded exiting zero on a different tree: another commit, or different uncommitted changes. The passing run needs no flag. `record-check` says which control the run completed. A passing run on the same tree as the failing run completes nothing, and `record-check` says that nothing differed between the two runs.
- **R6.** Recording `--control` again under a name already in this hand-over starts that control afresh from the new run. The earlier runs stay in the notes.
- **R7.** Controls, not-proof statements (R8) and no-control statements (R11) are kept on the task in a place only `asdlc` writes (a frontmatter key, as plan approvals are), and `finish`, `review-next`, `mine` and `stats` read them only from there. Text in the task's notes never counts toward the floor, however it is worded.

### Saying a test is not the proof

- **R8.** `asdlc not-proof <task> --as <worker> --test <name> --proof <control> --why "<text>"` records that a test is kept but is not offered as proof of the change, why it cannot be made to fail without the mechanism, and which control is the proof instead. Only the worker holding the task In Progress may record it. `--proof` must name a complete control in the same hand-over, other than `--test`. It resolves an unresolved control of that name, leaves a note on the task, and never counts toward the floor.

### The floor at hand-over

- **R9.** `asdlc finish` on a task that is not `size-1` refuses unless this hand-over has at least one complete control that no not-proof statement names as its `--test`, or the worker gives a no-control statement (R11).
- **R10.** `asdlc finish` refuses while any control in this hand-over is unresolved: it did not fail (R4), or it failed and has no passing run after it (R5). It names each one. `--no-control` does not lift this refusal. It also refuses when a not-proof statement's `--proof` is no longer a complete control.
- **R11.** `asdlc finish --no-control "<why>"` hands over a task with no control in this hand-over. The statement must not be empty; it is written on the task as a note that starts "No control offered:", kept as R7 says, and printed in `finish`'s output. It is refused when this hand-over already has a complete control, since there is then nothing to state.
- **R12.** A control or a statement counts for the hand-over it was first offered in and for no later one. After a review asks for changes, the next `finish` needs a control recorded since, or its own no-control statement.
- **R13.** Each refusal under R9 and R10 says what is missing, why it is asked for in one sentence, and the exact commands that supply it: the control, the not-proof statement, and the no-control statement with the cases it is for. It says that nothing should be broken only to get past it. A worker who has read nothing else can act on it.
- **R14.** `asdlc finish` asks nothing new of a `size-1` task. `--control` may still be used on one.
- **R15.** Nothing changes for a task that is not being handed over: one already In Review or Done is not moved, relabelled or refused anything. A task with no recorded controls is read as having none, never as an error. Every invocation of `record-check`, `finish`, `review-next`, `review-done`, `mine` and `stats` that works today still parses and does the same thing, except that `finish` can now refuse under R9 and R10.

### What the reviewer is handed

- **R16.** `asdlc review-next` prints, in its JSON and its text, what this hand-over offers: each control with its name, the `--without` text, the command, and for the failing and the passing run the time, the commit and whether there were uncommitted changes; each not-proof statement; the no-control statement if there is one; and the number of earlier hand-overs. When there is nothing, it says which of three things that is: a `size-1` task, a task handed over before controls were recorded, or a no-control statement.
- **R17.** `asdlc review-done` accepts `--cannot-fail <n>`: how many tests offered as proof the review found would pass without their mechanism. It is kept on the task with the verdict's other counts. Left out, the verdict is recorded as before and counted as not saying.

### What the engineer sees

- **R18.** `asdlc mine` says for each held task whether `finish` would refuse it now for want of a control, and why: not needed, missing, unresolved (with the names), or ready.
- **R19.** `asdlc stats` reports, for each task larger than size 1 handed over in the window, per hand-over: how many complete controls it offered, how many not-proof statements, whether the no-control statement was used and its text, and how many tests the review then found could not fail (or that the review did not say). It totals them as shares of hand-overs, with first hand-overs and fix rounds apart, and counts hand-overs made before controls were recorded separately from hand-overs without one.

### The guard

- **R20.** The board guard refuses everything it refuses today. The command that follows `--` in `record-check --control ... --` is judged exactly as it is without the flags, and `not-proof` passes the guard as `record-check` does.

### What the agents are told

- **R21.** The worker's instructions say: the two cheap ways to record a control (the test recorded failing before the mechanism exists; the mechanism removed and restored after); that both runs use the same narrowed command; that a control fails at the assertion that names the behaviour, not at a build, an import or another test; what to do when a control does not fail; when the not-proof and no-control statements are honest; that each fix round needs its own; and that the notes never claim a control `record-check` did not record.
- **R22.** The reviewer's instructions say what to do with what R16 hands it, as "What the reviewer is told" below sets out, and to record `--cannot-fail`.
- **R23.** The orchestrate skill passes the controls to the reviewer, tells a worker fixing findings that the round needs its own control or statement, and reads `mine`'s control state before telling the engineer a task is ready. The plan-change skill asks that a plan's proof name, for each test offered as proof, what will be removed to make it fail, or say that no control applies and why.
- **R24.** The team review policy and testing skill that `asdlc init-board` gives a new board say what a good control is, in the Evidence pass and in "Recording the evidence". A board's own copies stay the team's to change.

### Held to its own rule

- **R25.** `./scripts/check` passes at each merge this is split into, with no assertion removed or loosened and the eval suite's protected path respected (plugin spec R23). Each test this adds names, in the plan, what is removed to make it fail.

## Design

### The floor, exactly

The tool checks only what it can see. Everything else stays the reviewer's, under the team's review policy.

| The tool checks | The tool does not check, and the reviewer judges |
|---|---|
| The worker marked the run as a control and named what it is for | That the name is the test the command runs |
| The marked run exited non-zero | That it failed at the assertion, not at a build, an import, a set-up step or another test |
| The same words exited zero in a later recorded run | That the passing run is of the final commit (the commits are shown) |
| The two runs were on different trees | That what differed is the mechanism the test claims to prove |
| The text of `--without`, `--why` and `--no-control` is not empty | That any of the three is true |
| One complete control per hand-over, and none unresolved | That every test offered as proof has one |
| The worker held the task when each was recorded | Whether a test's name says what it checks |

### A control is marked, not inferred (answers intent question 1)

A failing run followed by a passing run of the same command does not count unless the worker marked the failing run with `--control` and named the test. The evidence decides it: workers already record their tests failing before the code exists and passing after, and those failures are a compile error, "22 compile errors", or a `ModuleNotFoundError`. That is test-first evidence, not a control of a mechanism, and under "any failing run followed by a passing run" it would have satisfied the floor on nearly every task without anyone intending it, which the intent rules out.

Marking costs the worker two flags on a run it was going to record anyway. A worker who writes the test first marks that run and has its control for nothing more, provided the test fails at its assertion; a worker who builds first removes the mechanism in the worktree, records the failure, restores it (`git restore`, which workers may already run) and records the pass.

### The same command means the same words (answers intent question 2)

The passing run must be the same words in the same order as the failing run. Workers narrow the failing run to one test and run the whole check for the passing one; under this rule they narrow both, and the whole check is recorded as well, as it is today.

The reason is that the tool cannot know that a whole check includes the narrowed test. On the project the evidence comes from, the check command chooses tests from the diff, so a passing check does not say the control's test ran. Matching by a shared prefix or by test name would be the tool pretending to know. The cost is one more run of one test, seconds in most toolchains.

A control whose mechanism is switched off by the command itself (an environment variable, a build flag) cannot be recorded this way, because the two commands differ. It is recorded by making the same change in the worktree instead.

### Different trees

A failing and a passing run of the same command on the same commit with the same uncommitted changes means nothing was removed between them: a flaky test, a busy port, a file outside the repository. It is not a control of anything in the change, so it completes nothing (R5). `record-check` already records the commit and whether the tree had uncommitted changes; this adds a digest of the uncommitted change so two such trees can be told apart.

### Where it is kept (R7)

`asdlc stats` reads recorded checks back out of the task's notes today. Notes are free text: any worker can append a line shaped like a recorded check with `asdlc board task edit --append-notes`, and `--notes` replaces the section whole. In one day workers wrote in their notes that a control was run ("recorded timing out, exit 124", "each with a negative control run and reverted") when no such run was recorded, three times. So the floor reads nothing from the notes. It reads one frontmatter key that only `asdlc` writes, as `asdlc approve` does for a plan's approval; the guard already refuses hand edits to `backlog/`. Backlog.md 1.55.2 was checked to keep such a key, a long quoted value included, across its own edits.

The notes still get a note for each run and statement, so a person reading the task sees them in order.

### Tests that cannot be made to fail (R8)

Several tests on the evidence day could not be made to fail without their mechanism at all: the kernel throttled the condition away, or the ordering could not be reached end to end. The honest outcome was to keep them as regression tests and name another test as the proof. `not-proof` records that. It is not a way past the floor: it does not count toward R9, and it must name a complete control as the proof, so it cannot be recorded until a real control exists.

### The exemption (answers intent question 3; one part carries forward intent question 3)

It is called a no-control statement, given as `asdlc finish --no-control "<why>"`. It is for a change with nothing to control for: documentation only, a pure rename, a move with no behaviour change. The worker holding the task gives it. It is never silent: it is a note on the task, it is in `finish`'s output, `review-next` hands it to the reviewer by name, `mine` shows it, and `stats` counts it and prints its text.

Whether it also needs the engineer's word is carried forward to the owner, with a recommendation: no.

| Answer | What it costs |
|---|---|
| The worker states it and the reviewer judges it (recommended) | A worker can state something false. The reviewer has the diff beside the statement and the policy makes a false one Important, so it costs a review round. Nothing waits on a person. |
| The engineer records it, as they record a plan's approval | Every documentation task and every fix round with no test change stops until the engineer runs a command in their own terminal, since a worker cannot ask mid-task. It adds a fourth gate for a person, on the least risky work. |

If the numbers in R19 show the statement used on changes that had behaviour to control for, the second answer can be added later without changing what is recorded.

### Fix rounds (answers intent question 4)

Each hand-over needs its own control or its own statement (R12). Most of the findings on the evidence day arose in review fix rounds, on tests added or changed by the fix, so a control recorded for the first hand-over cannot stand for the second.

The intent asks whether a fix round needs one "when the fix adds or changes a test". The tool cannot tell whether it did: `finish` runs from the tasks clone and sees no diff, and where tests live inside source files, as in Rust, no path tells a test change from a code change. So it asks every round, and a round that changed no test says so: `--no-control "this round changed no test: reworded the refusal"`. That is one sentence, and the reviewer has the round's diff to check it against.

### Proof that is not a test (answers intent question 5)

A control is defined over a recorded command, not over a test. Any command that exits non-zero without the mechanism and zero with it can be one, and `--control` then names what is being proven: `sh -c 'steg --version | grep -q 0.2'` is a control for a version bump.

A proof that no command can show (a screenshot compared by eye, a manual run) cannot be recorded, so it goes by the no-control statement, which says that the proof is manual and what was seen with and without the change. The reviewer judges it like any other statement.

### Before a plan is approved (answers intent question 6)

No floor is added to `asdlc approve`. A plan is text, and a check on its text is met by a word. The evidence is about doing, not planning: in three of the four cases the worker had been told to show the test failing and did not, and one worker dropped a planned control saying another run covered it, which was false. A plan-time gate would have passed all of them. What changes is the plan-change skill (R23), so the control is in the plan the engineer reads, and the floor at hand-over holds whether or not it was.

### What the reviewer is told (answers intent question 7)

The reviewer agent's instructions gain one section, after the diff:

- Take the controls from the claim, not from the notes. Where the worker's notes claim a control the claim does not list, that is an Evidence finding.
- For each control, read its failing run on the task and judge two things: did it fail at the assertion that names the behaviour, and is what was removed the mechanism the test's name claims. A control that failed at a build, an import, a time-out in another part or an earlier refusal is an Important Evidence finding, even when the test is sound.
- Repeat at least one control, the one whose failure looks least like the mechanism, in the review's own worktree and never the task's: put the tree as the failing run had it, run the control's command, and restore the tree before the full check. A test that passes without its mechanism is an Important Bugs finding.
- Look for tests the change adds or alters that have no control and no not-proof statement. One complete control is the floor, not the standard; the policy decides whether each needs one.
- Judge each not-proof statement (is the named control really the proof of the same behaviour) and the no-control statement (does the diff really have nothing to control for). A false one is Important.
- Record `--cannot-fail <n>` with the verdict: the number of tests offered as proof that pass without their mechanism, `0` when none.

### Getting past it

For each requirement a worker meets, how it could be satisfied without the real thing, and whether that is acceptable.

| Requirement | Cheapest way to comply honestly | Way past without the real thing | Acceptable? |
|---|---|---|---|
| R1, R3 | Mark the test-first failing run | Mark a run that fails at a build or an import | Yes, as a floor. It is a deliberate act, not an accident, and the failing run's end is in front of the reviewer under the control's name (R16, R22). |
| R3 | Say in `--without` what was removed | Write anything | Yes. The uncommitted change is recorded beside the text, so a claim the tree contradicts is visible. |
| R4 | Fix the test, record it again | Ignore the pass | No, and it is closed: R10 refuses the hand-over until it is resolved. |
| R5 | Run the narrowed command again after restoring | A command built to fail then pass, such as a test for a file the worker then creates | Yes. It cannot happen by accident, and the command is handed to the reviewer word for word. A worker willing to do that would also write a false test. |
| R5 | - | An unrelated edit, so the trees differ | Yes, for the same reason. The rule exists to stop flaky and environmental failures counting, which it does. |
| R7 | - | Shape a note like a control | Closed: notes never count. Editing the task file by hand is refused by the guard, which is a guardrail and not a wall. |
| R8 | State it once another control is complete | Declare every awkward test not-proof | Yes. It never counts toward the floor, each one is listed for the reviewer, and R19 counts them. |
| R9 | One control | One easy control on a trivial test, none on the test that matters | Yes, by the intent's own terms: the floor is that one exists. R22 makes the reviewer look for the rest. |
| R11 | One sentence on a documentation change | The same sentence on a behaviour change | Yes, pending the owner's answer to intent question 3. It is visible in four places and judged. |
| R12 | A control on the fix's test, or one sentence | "This round changed no test" when it did | Yes. The round's diff is small and the reviewer has it. |
| R17 | - | A reviewer that never passes `--cannot-fail` | Yes. R19 counts verdicts that did not say, so silence shows. |

R13 to R15, R18 to R20 and R23 to R25 constrain the tool and its text, not the worker, and give nothing to get past.

Nothing here asks a worker to break something that works in order to pass: the marked run of a test written first breaks nothing, and where there is nothing to remove the statement exists. The refusal says so (R13).

## Areas of concern

- **The engineer's word on the exemption.** Carried forward above with both costs. It is the owner's to decide because it sets what a person must do.
- **The no-control statement may become routine in fix rounds.** A round that fixes a comment or a note has nothing to control for, and says so every time. If most fix rounds carry one, readers will stop reading them. R19 keeps first hand-overs and fix rounds apart so this shows. The alternative, asking only at the first hand-over, leaves open the place the evidence says the problem is.
- **The eval suite's reference runs hand over size-2 tasks with one passing check.** They are under the protected path, so the change that adds the refusal cannot edit them, and `./scripts/check` runs them. The floor therefore cannot arrive in one pull request; the plan proposes the order.
- **The reviewer has no edit tool.** Repeating a control means putting a tree back as the failing run had it. With the permissions a reviewer has today that is possible when the failing run was on an earlier commit (`git restore --source`), and awkward when the removal was an uncommitted edit. The plan proposes allowing `git apply` in worktrees so the recorded change can be put back; that widens what agents may run and is the owner's to accept or refuse.
- **Notes can still be replaced.** A worker can erase the output of its recorded checks with `--notes`. The controls survive, since they are kept apart, but their output would not. This is true of every recorded check today and is left as it is.
- **A worker running on older instructions.** A session keeps the plugin version it loaded. Its worker will meet the refusal at `finish` without having been told about controls, which is why R13 makes the refusal sufficient alone.

## Out of scope

- Judging whether a control is a good one. The team's review policy says what a good control is, and the reviewer applies it.
- Requiring a control for every test in a change. One per hand-over is the floor.
- A floor on plan approval (intent question 6, answered above).
- Running a control for the worker, or mutation testing of any kind.
- Three gaps seen on the same day, which are not this intent's and are written here so they are not lost:
  - A worker ran `asdlc finish` while a question to its orchestrator was unanswered.
  - A task finished too early cannot be reopened by its worker or its orchestrator, except through a review that asks for changes.
  - `asdlc record-check` refuses on a task that is In Review, so nothing can be recorded on it while it waits.
- Stopping a worker from replacing the notes section (Areas of concern).
- Recording the reviewer's repeated control on the board. The reviewer says what it repeated in its findings.
