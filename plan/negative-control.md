# Plan: the floor of one recorded control before review

- Spec: [`spec/negative-control.md`](../spec/negative-control.md), draft 2026-11-15; this plan is approved with it or after it
- Status: approved by the owner in session on 2026-11-15; merging it with the first change is the gate. Change A is built, and "What changed while building A" says where it departs from the plan as approved.
- Delivers: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24, R25

This serves [`intent/negative-control.md`](../intent/negative-control.md). It teaches `asdlc record-check` to record a marked control, keeps controls where only `asdlc` writes them, hands them to the reviewer, counts them, and then makes `asdlc finish` refuse a task larger than size 1 without one. It is three pull requests, not one, for a reason found while reading the code and set out next.

## What was found before planning

- **The eval suite hands over size-2 tasks with one passing check.** `evals/fixtures.py` (`build_round`), `evals/cases/approval-before-build/case.py` and `evals/cases/sent-back-resumes-branch/case.py` each record one passing run and call `asdlc finish` on a size-2 or size-3 task. `./scripts/check` runs those reference runs (`scripts/eval validate`). `evals/` is a protected path: a pull request that changes the plugin cannot change it (plugin spec R23). So the pull request that adds the refusal cannot also fix the reference runs, and would fail its own check.
- **`finish` checks nothing about checks today.** It does not ask that any check was recorded, or that the last one passed. "Don't finish on a failing check" is only in the worker's instructions.
- **Recorded checks are free text.** `stats` reads them back from the notes with a pattern. A worker can append text of the same shape, and `asdlc board task edit --notes` replaces the whole section. The command of a check is matched by the pattern and then thrown away, so nothing reads it back today.
- **`finish` never sees the code.** It runs from the tasks clone with no worktree, so it cannot tell whether a fix round touched a test.
- **Backlog.md 1.55.2 keeps an unknown frontmatter key verbatim across its edits**, including a 400-character single-quoted JSON value with quotes, commas, backticks and brackets inside. Tried in a throwaway board with `--append-notes`, `-l` and `--plan` edits.
- **Workers may already run `git restore`, `git stash` and `git reset` in a task's worktree** without a prompt, so removing and restoring a mechanism needs no new permission. A reviewer has no edit tool and may not run `git apply`.
- **The guard already judges the command after `--`** in `record-check` and passes subcommands it does not name, so R20 needs tests and no guard code.

## The split

| Change | What it is | Why it is separate |
|---|---|---|
| A. Record and report | `record-check --control`, where controls are kept, `not-proof`, `finish --no-control` recorded but nothing refused, `review-next`, `review-done --cannot-fail`, `mine`, `stats` | No steering path changes and no existing test changes. Everything after it can use the new flags. |
| B. The suite | The three reference runs record a control; two new cases | `evals/` only, in a pull request of its own (R23). It passes under A, where the flags exist and nothing is refused yet. |
| C. The floor and the words | `finish` refuses (R9, R10, R13); the worker's, reviewer's, orchestrator's and planner's text; the team policy templates | Changes steering paths, so it needs eval gate evidence, and B's cases are what that run measures. |

The spec and this plan merge with A. B and C cite them.

## Files that change

| File | Change | New | What it holds | Requirements |
|---|---|---|---|---|
| `scripts/asdlc` | A | no | `record_check_arguments` reads `--control` and `--without`; `Where` gains a digest of the uncommitted change; pure functions over the controls (below); `record_check` writes them in its transaction; the `not-proof` subcommand; `finish --no-control`, and `finish` marking what was handed over; `_review_report` and its text; `review-done --cannot-fail`; `mine_report`; a `controls` metric in `test_stage`; `Task` gains two fields and `STATS_CACHE_VERSION` becomes 2 | R1 to R8, R11, R12, R15 to R19 |
| `tests/test_asdlc.py` | A | no | The tests in "What each test proves". No existing test is edited | R1 to R8, R11, R12, R15 to R19, R25 |
| `tests/test_guard_board.py` | A | no | Three tests: a refused command after `record-check --control ... --` is still refused, an allowed one still allowed, `not-proof` allowed | R20 |
| `tests/test_demo_stats.py` | A | no | A second demonstration, one task with a control at its first hand-over and a no-control statement at its second, with its numbers asserted. The existing demonstration is not edited (see "What changed while building A") | R19 |
| `README.md`, `docs/guide.md`, `CHANGELOG.md` | A | no | The command table, the metric, one entry | - |
| `evals/fixtures.py`, `evals/cases/approval-before-build/case.py`, `evals/cases/sent-back-resumes-branch/case.py` | B | no | Each reference run writes the test first, records it failing with `--control`, then the code, then the same command passing. Checks are not touched | R25 |
| `evals/cases/control-before-review/` | B | yes | A worker builds a size-2 task. Passing: the task reaches In Review with a complete control whose failing run ended in an assertion. The null run hands over nothing | R21 |
| `evals/cases/reviewer-names-a-test-that-cannot-fail/` | B | yes | A review scene whose test passes with the counting line removed, and whose recorded control failed at an import. Passing: `changes`, a finding that names the test, `--cannot-fail` of at least 1 | R22 |
| `scripts/asdlc` | C | no | `control_refusal`, built on A's `handover_state`, called in `finish` beside `approval_refusal`; `apply` added to `WORKTREE_GIT` (the owner agreed on 2026-11-15) | R9, R10, R13, R14 |
| `tests/support.py`, `tests/test_asdlc.py`, `tests/test_demo_review.py`, `tests/test_demo_stats.py`, `tests/test_demo_pilot.py` | C | no | One shared helper records a control; every test that hands over a size-2 task calls it before `finish`. No assertion is removed or loosened. The new refusal tests | R9 to R15, R25 |
| `agents/worker.md` | C | no | The text in "The words" | R21 |
| `agents/reviewer.md` | C | no | A section "The controls" between the diff and the findings | R22 |
| `skills/orchestrate/SKILL.md`, `skills/plan-change/SKILL.md` | C | no | Steps 8, 9 and 10; the Proof bullet | R23 |
| `templates/board/plugins/team/review.md`, `templates/board/plugins/team/skills/testing/SKILL.md` | C | no | The Evidence pass; "Recording the evidence" | R24 |
| `README.md`, `docs/guide.md`, `CHANGELOG.md` | C | no | The refusal, and how to supply a control | - |

No file under `hooks/` changes in any of the three.

## How controls are kept

One frontmatter key, `asdlc_controls`, written by `_write_key` as a single-quoted JSON value inside the transaction that records the run, so a lost push decides afresh on the new state:

```json
{"handed": 1,
 "controls": [{"name": "focus::never_changes_focus", "round": 2, "without": "the guard in set_focus()",
               "command": ["cargo", "test", "never_changes_focus"],
               "failed": {"at": "2026-11-15T10:00:00+00:00", "commit": "0123456789ab", "tree": "9f1c0a2b3c4d", "code": 101},
               "passed": null, "did_not_fail": null}],
 "not_proof": [{"test": "throttle::survives_a_burst", "proof": "focus::never_changes_focus", "why": "...", "round": 2}],
 "no_control": [{"round": 1, "why": "documentation only"}]}
```

`handed` is the number of hand-overs so far; a run or statement gets `round = handed + 1`; a successful `finish` adds one. "This hand-over" in the spec is the entries whose round is `handed + 1`. `tree` is empty for a clean worktree, else a digest of `git diff HEAD` and the object ids of untracked files.

The logic is pure functions over that value, tested without git or Backlog: `parse_controls`, `controls_text`, `with_run` (what one recorded run does: starts a control, leaves it unresolved, completes one, or completes nothing, with the sentence `record-check` prints), `control_state`, `with_not_proof` and its refusal, `no_control_refusal`, `handed_over`, `handover_state` (R18: not needed, missing, unresolved, ready), `control_report` (R16) and, in change C, `control_refusal` (R9, R10, R13), which turns `handover_state` into the refusal. The shell around them is the three lines that read the key, call one, and write it.

A control's note keeps `check_note`'s first line as it is, so `parse_checks`, and an older `asdlc` reading the same board, still count it. The line naming the control and the `--without` text go above it, and the uncommitted change (file list and patch, cut to 40 lines) below. The patch has no context lines (`git diff HEAD --unified=0`, then the text of up to ten new files), so that no line of it can read as another check's first line.

## Order of work

Each step's tests are written first and seen failing for the reason named in "What each test proves"; the failing and passing output of each goes in the pull request.

Change A:

1. A test that the key survives Backlog's own edits through `asdlc board task edit`, then `Task.controls`, `parse_controls` and `controls_text`.
2. `record_check_arguments` with `--control` and `--without`, and the refusal for one without the other.
3. `with_run` and `control_state`: unmarked runs, a marked failure, a marked pass, the same words passing, other words passing, the same tree, recording again.
4. `Where.tree`, the control's note, and `record_check` writing the key and printing `with_run`'s sentence.
5. `not-proof`.
6. `finish --no-control`, and `finish` adding one to `handed`. Nothing is refused for want of a control.
7. `review-next`'s report and text.
8. `review-done --cannot-fail`.
9. `mine`'s control state.
10. The `controls` metric, the demonstration, the guide.
11. The guard tests.
12. `./scripts/check`. Every test that existed before A passes unedited.

Change B:

13. The three reference runs, then `scripts/eval validate`.
14. The two new cases, each with a reference run that passes and a null run that fails.

Change C:

15. The shared test helper, called in every test that hands over a size-2 task. `./scripts/check` still passes, since nothing refuses yet.
16. `control_refusal` in `finish`, with its tests. The tests of step 15 would fail here without the helper; that is shown once, for one of them, in the pull request.
17. The words: worker, reviewer, orchestrate, plan-change, the two templates.
18. `./scripts/check`, then `scripts/eval gate`, which spends tokens and is the owner's to start.
19. After merge, the owner's steps: `just release <version>`, tag, update the plugin on this machine.

## What each test proves

This change is held to its own rule (R25). Each row names the mechanism and what is removed to make the test fail. Two tests cannot be made to fail by removing anything, and are named as not offered as proof, with the test that is.

| Test | Proves | Its control: what is removed, and how it then fails |
|---|---|---|
| `--control` without `--without` is refused before the command runs | R1 | The pairing check. The command runs and the marker file it would create exists |
| An unmarked failing run then the same command passing starts nothing | R2 | The early return for a run with no `--control`. A control appears |
| A marked failure then the same words passing is complete | R3, R5 | The completing branch of `with_run`. The state stays "awaiting its passing run" |
| A marked failure of one test then the whole check passing completes nothing | R5 | The comparison of the words (compare the first word only). It completes |
| A marked failure then a pass on the same commit and tree completes nothing, and says nothing differed | R5 | The tree comparison. It completes |
| A marked run that passes is unresolved, and `record-check` says the test passed without the mechanism | R4 | The did-not-fail branch. The run is recorded as an ordinary check |
| Recording a name again starts it afresh | R6 | The replacement. The earlier passing run still completes it |
| The key survives `--append-notes`, `--plan` and a label edit | R7 | The write of the key in `record_check`. Nothing is read back |
| A note that copies a control's text counts for nothing | R7 | Not offered as proof: nothing reads notes, so there is nothing to remove. A regression test. The proof of R7 is the row above and the row below |
| `review-next` lists a control recorded through `record-check` and no other | R7, R16 | `control_report` returning nothing. The list is empty |
| A control's note still reads back as one check | R15 | Put the control's name on `check_note`'s first line. `parse_checks` finds no check |
| `not-proof` is refused until its `--proof` is a complete control; refused for a worker that does not hold the task; resolves an unresolved control | R8 | Each refusal in turn, then the resolving line. Each test fails alone |
| `finish --no-control` writes the note, the key and the output; an empty one is refused; refused when a complete control is there | R11 | The write; the emptiness check; the contradiction check |
| After a review asks for changes, the first hand-over's control is not in this one | R12 | The filter on `round`. The old control is listed and `mine` says ready |
| `review-next` says which of three reasons there is nothing | R16 | Collapse the three to one. Two assertions fail |
| `--cannot-fail 2` is on the task and in the replay; left out, the verdict records as before | R17 | The write of the key. The first half fails. The second half is the existing review tests, unedited |
| `mine` says not needed, missing, unresolved with names, ready | R18 | Return "ready" always |
| `stats` counts a hand-over before controls existed apart from one without a control, and fix rounds apart | R19 | Count a missing key as no control. The shares change |
| A refused command after `record-check --control x --without y --` is refused | R20 | The guard's existing `record-check` branch. The command is allowed |
| `finish` refuses a size-2 task with no control, and the refusal carries the three commands | R9, R13 | The call to `control_refusal`. The task goes In Review |
| `finish` accepts a size-2 task with one complete control | R9 | Make `control_refusal` refuse always. This test shows the floor does not over-refuse; the row above is the proof that it refuses |
| `finish` refuses with an unresolved control, with and without `--no-control` | R10 | The unresolved check |
| `finish` refuses a fix round with only the first hand-over's control | R12 | The filter on `round` |
| A size-1 task finishes with nothing recorded | R14 | The existing size-1 test, unedited. Its control: drop the size check, and it is refused |
| A task In Review with no key is claimed, reviewed clean and left In Review | R15 | Not offered as proof: no code runs on such a task, so nothing can be removed. A regression test. The proof is that the only refusal is in `finish` (two rows up) and that A's existing tests pass unedited |
| The two new eval cases | R21, R22 | Each case's null run, which `scripts/eval validate` requires to fail |

## How existing tasks and commands keep working

- **A task already In Review** has no `asdlc_controls` key. Nothing reads it as an error (R15); `review-next` says it was handed over before controls were recorded; `stats` counts it apart. It is not moved. If its review asks for changes after C ships, its next `finish` is a hand-over like any other and needs a control or a statement.
- **A task In Progress when C ships**, with a worker on the older instructions, meets the refusal at `finish`. The refusal names the commands (R13), and `record-check` on the installed release takes them.
- **Size-1 tasks** never reach `control_refusal`: it returns at the size check first, as `approval_refusal` does.
- **Every existing invocation** parses as before. `--control`, `--without`, `--no-control` and `--cannot-fail` are optional. `record-check`'s exit code is always the command's.
- **The board guard** is not edited. Its tests pass unedited, and three are added.
- **Stats caches** are rebuilt once, because the cache version changes.
- **Between A and C** the flags work and nothing is refused, so a release cut there is harmless.

## The numbers

One metric, `controls`, in the Test stage (play 07), from the key on each task and `--cannot-fail` on each verdict:

- Per task, per hand-over, in the JSON: complete controls, not-proof statements, the no-control statement's text or none, and the tests the review found could not fail (a number, or "did not say").
- In the text: hand-overs with a control, with a no-control statement, and made before controls were recorded, as shares; the same for fix rounds alone; not-proof statements; tests found that could not fail over the verdicts that said, and how many verdicts did not say.

Reading it: the floor is working when the share with a control is high, the no-control share is small outside fix rounds, and tests that could not fail fall towards none. A high no-control share on first hand-overs, or `--cannot-fail` staying up while controls are recorded, says controls are being recorded for the wrong thing, which is the reviewer's and the policy's to fix, not the tool's.

## The words

- **Worker, phase 2.** After the baseline check: "Before you hand over, one test must be recorded failing without your change. Write the test first and record it with `--control <test name> --without "<what isn't written yet>"`, or build first, take the mechanism out in the worktree, record it the same way, and put it back with `git -C <worktree> restore`. Then record the same command again, passing. Narrow both runs to the one test. A control fails at the assertion that names the behaviour; a failure at a build, an import or another test is not one. If it passes without the mechanism, your test cannot prove the change: fix the test or what you removed and record it again. If a test cannot be made to fail at all, keep it and say so with `asdlc not-proof`, naming the test that is the proof. If the change has nothing to control for (documentation only, a pure rename, a move), don't invent a failure: say so with `finish --no-control "<why>"`. Never write in your notes that a control was run unless `record-check` recorded it; the reviewer is handed the recorded list."
- **Worker, fixing findings.** One step added before the hand-back: "A fix that adds or changes a test needs its own control, recorded in this round. A round that changes no test says so with `--no-control`."
- **Reviewer.** The section in the spec, "What the reviewer is told", as written there, with the commands: the control's failing run is the note whose first line names it; to repeat one, `git -C <review> restore --source=<the failing run's commit> -- <files>` or, for an uncommitted removal, the recorded change put back with `git -C <review> apply`; `git -C <review> restore .` afterwards.
- **Orchestrate.** Step 8: read `mine`'s control state before telling the engineer a task is waiting for review. Step 9: tell the worker the round needs its own control or statement. Step 10: `controls`, `not_proof` and `no_control` are among the fields handed to the reviewer.
- **Plan-change.** The Proof bullet gains: "For each test offered as proof, say what will be removed to make it fail. If nothing can be, say that no control applies and why."
- **Team policy templates.** Evidence pass: "A control that failed for another reason than the mechanism, a test offered as proof that has none, and a no-control or not-proof statement that isn't true are findings." Testing skill, "Recording the evidence": the two ways to record a control, with the commands.

## Risks

- **A release between B and C running the suite against real agents.** B's new cases fail against agents until C's words ship. They are capability evidence for C's gate, not a regression; B's pull request says so.
- **Real-agent eval cases get longer.** Workers in `approval-before-build` and `sent-back-resumes-branch` must now record a control, which is more turns. If the gate run shows them hitting `max_turns`, the limits are raised in a suite pull request, not here.
- **The key is edited by something other than `asdlc`.** A person fixing a task file by hand could break the JSON. `finish` and `record-check` then refuse and say the key cannot be read and how to clear it; `stats` and `mine` read it as unreadable and say so. Nothing fails silently.
- **Two recorded runs race.** Two `record-check` calls for one task from one worker are rare; the transaction replays the step on the new state, so neither run's entry is lost.
- **The tree digest is slow or wrong in a large worktree.** It is `git diff HEAD` and one `git ls-files --others --exclude-standard`, which `record-check` nearly runs already for "with uncommitted changes". An ignored file is not seen: a mechanism removed only in an ignored file completes nothing, and `record-check` says that nothing differed, which is true of what git tracks.
- **The same words differ by a path.** A worker who records one run by a relative path and the other by an absolute one completes nothing. The sentence `record-check` prints quotes both commands when a marked control is waiting and a passing run did not match it.
- **Allowing `git apply` in worktrees.** It changes files only where the edit rules already allow edits, and runs no program. The owner agreed to it on 2026-11-15; it arrives in change C with the reviewer's words. A recorded change has no context lines and is cut to 40 lines, so it is put back with `git apply --unidiff-zero` and only when the note shows all of it; for a longer one the reviewer makes the removal by reading the note, and says so.
- **Fix rounds fill with no-control statements.** Seen in the numbers (first hand-overs and fix rounds apart), and named in the spec's areas of concern.
- **The floor is met by a control on the wrong test.** By design: it is a floor. R16 and R22 put the reviewer on it, and `--cannot-fail` shows whether it is happening.

## What changed while building A

Change A was built on 2026-11-15. Where it departs from the plan as approved, and why:

- **The demonstration is a second test, not an edit to the first.** `tests/test_demo_stats.py` asserts that one of six recorded checks failed. A control is a recorded failing run, so adding one to that demonstration's size-2 task would change an existing assertion, and A changes none. The new demonstration is its own test method in the same file.
- **`review-next` names a fourth reason for nothing offered.** Between A and C `finish` refuses nothing, so a task larger than size 1 can be handed over with no control and no statement. `review-next` says so (`nothing_offered: "none"`), beside the three reasons R16 names, rather than calling it one of them. C makes it unreachable for a hand-over made under C and decides whether to keep the word for hand-overs made between the two.
- **`mine` has two states beside R18's four.** A task In Review is past `finish`, so it says "handed over" with what its hand-over offered; a key that cannot be read says "unreadable" with how to clear it. Until C, the reasons for "missing" and "unresolved" end by saying that `finish` does not refuse for it yet.
- **`control_refusal` is not built in A.** The plan listed it among the pure functions and put its call in C. A builds `handover_state`, which `mine` reads; C writes the refusal's words on top of it, where they can be tested with the refusal.
- **A marked run acts only on the control it names.** A passing run recorded with `--control x` is x's control that did not fail; it does not also complete another control awaiting the same words. The plan did not say either way.
- **A passing run that completes a control says so in its note** ("Completes the control for ..."), so a person reading the notes in order sees it without the key.
- **New files are shown in a control's note.** The test written first is usually an untracked file, which `git diff HEAD` does not show. The note lists it as new and shows its text within the same 40 lines.
- **`not-proof` takes `--json`,** as `finish` and `review-done` do.
- **The text of `--without`, `--why` and `--no-control` is kept on one line.** Each goes into the task's notes, where a line break could start a line that reads back as a recorded check. Nothing counts toward the floor from the notes, but `stats` counts checks there.
- **The stats metric counts "neither" as its own share,** a hand-over made under this release with no control and no statement, apart from one made before controls were recorded.
- **`finish` reads the key on every hand-over,** so a key edited by hand into something unreadable is refused there, in `record-check` (before the command runs) and in `not-proof`, as the risk above says. No task has the key before this change, so no invocation that works today meets it.

The tests of "What each test proves" for change A are `ControlRunsTest`, `ControlsKeptTest`, `ControlNumbersTest` and `ControlCommandTest` in `tests/test_asdlc.py`, `ControlCommandsTest` in `tests/test_guard_board.py`, and the second demonstration in `tests/test_demo_stats.py`. Each row's control was run as a scratch edit and its failing output is in the pull request. Two rows are regression tests and not offered as proof, as the table says: the note that copies a control's text, and the task In Review with no key.

## Proof

- `./scripts/check` passes on each of the three pull requests, and its result is in each commit message. On A, `git diff --stat` shows no existing test edited; on C, no assertion removed.
- Each row of "What each test proves" has its failing run and its passing run in the pull request that adds it.
- On a throwaway board: a size-2 task with one passing check is refused by `asdlc finish`, and the refusal alone is enough to supply a control and finish; the same task with `--no-control "documentation only"` goes In Review with the note; a size-1 task finishes with nothing recorded.
- `asdlc review-next --json` on that board lists the control with its two commits, and `asdlc stats --stage test` shows the three hand-overs under `controls`.
- `scripts/eval gate` on C holds against the current release, with the two new cases passing.
- In steg, after the release: the next task a worker hands over carries a control the reviewer is given by name, without the worker's brief asking for one.
