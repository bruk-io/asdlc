# Plan: a gate rule that tolerates the run-to-run spread

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: draft. Merging this file, after the owner approves it in session, starts the build.
- Delivers: R22 (a change merges only if the suite scores it no worse than the current release, beyond the measured run-to-run spread), R14 (the suite runs on a change to the plugin's configuration)

The first real gate run (`scripts/eval gate --all`, 3 trials, 2026-10-29) failed. Five regression cases each lost one trial of three, and a timeboxed round of fixes cleared one of them (`reviewer-full-verdict`, 2/3 to 6/6). The other four were variance (a shell denied for a session, a worker that ran `cd` against its instruction, an analyst question, a fix that left the tests red). The rule that failed them, every trial of every regression case passes, is stricter than R22: R22 asks for no worse than the current release beyond the spread, and at 3 trials a case the agent gets right nine times in ten fails the gate about a quarter of the time. A gate that fails on noise gets bypassed, or never run.

## The rule

A **regression case** fails the gate when either of these holds, and a failing case names its misses:

1. **Below the floor.** Its pass count is too low to be believable at the floor reliability of 0.8, by an exact one-sided binomial test at 5%: it fails when the chance of seeing that few passes or fewer, if its true pass rate were 0.8, is below 0.05. At 3 trials only 0/3 fails; at 5 only 0, 1 or 2 of 5; at 10, 5 of 10 or fewer.
2. **Fell from the baseline.** Pooled over the regression cases both runs have, the pass rate fell from the last passing gate's by more than 1.96 standard errors of the difference, the test the capability cases already use. With no baseline this half is skipped and the report says so.

A case that passed fewer than all its trials but clears both tests is **listed as flaky** in the report, with its failing checks, so a drift toward failure is visible before it trips the gate. Capability cases are judged as today. `scripts/eval gate` defaults to 5 trials, not 3: the test needs them, and 20 cases cost about $11.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/gate_evidence.py` | no | `judge` uses the rule above: an exact binomial tail (`math.comb`), the floor and level as named constants, a flaky list in the notes, and the pooled regression baseline test | R22 |
| `scripts/eval` | no | `gate`'s default trials becomes 5; `run` keeps 3 | R22 |
| `tests/test_gate_evidence.py` | no | The tail on known values; 0/3 fails and 2/3 passes; 4/10 fails and 7/10 passes; a pooled drop beyond noise fails and one within noise passes; the flaky list names the case and its checks; no baseline skips half 2 and says so. The existing "every trial must pass" tests change to the new rule: each one is named in the pull request with why | R22 |
| `docs/guide.md` | no | The gate's rule paragraph | - |
| `CHANGELOG.md` | no | One line | - |
| `plan/gate-rule.md` | yes | This plan | R22 |

Not here: a `--notes` argument for `asdlc review-done`, which would remove the refused here-document pattern seen in about one `reviewer-false-alarm` trial in six. It is a script change with its own question (the reviewer has no Write tool, so a notes file is no easier to make), and the scope is the rule.

## Order of work

1. Write the tail and the new `judge` with its tests; change the tests that assumed all-pass, one by one.
2. Re-judge the stored first run (`.eval-results/gate/*.json` holds each case's trials and passes) with the new rule, offline, and put the verdict in the pull request. The 3-trial report should pass: no case is 0/3 among the regression cases.
3. Run the gate for real at 5 trials on the merged `main`, record the passing report as the first baseline, and report the flaky list.
4. `./scripts/check`, one pull request.

## Risks

- **The floor is a judgement.** 0.8 is where I would call a regression case failing, not a measured number. It is a named constant, and the report prints the cases' rates so the owner can see where it sits.
- **A weaker gate lets a real regression through.** A case dropping from 100% to 70% passes the floor test at 5 trials (3.5 of 5 expected; 3/5 does not fail). The baseline half catches it only when pooled across cases. Single-case drops are caught only when they are large. This is the price of not failing on noise; more trials tighten both tests, and the flaky list keeps the middle visible.
- **The baseline is the first run that passes.** The first passing gate sets it, so it can set it low. Mitigation: the report states the baseline's rates, and the owner reads it once.
- **Changing the rule after a failure looks like moving the goalposts.** It is stated in R22 and was the owner's call after a timeboxed attempt at the other option, and this plan says why.

## Proof

- `./scripts/check` passes, its output pasted in the pull request.
- The tail and both halves are tested at the boundaries named above.
- The stored 3-trial run re-judged: verdict and flaky list in the pull request.
- A real 5-trial gate on `main` after merge: its verdict and the flaky list reported to the owner.
- No file under `evals/` changes (R23).
