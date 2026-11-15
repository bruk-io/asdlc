# Intent: a task cannot go to review until its test has been shown to fail without the change

- Author: Bruk Habtu
- Requested by: @bruk
- Status: draft. Merging this file accepts it.
- Date: 2026-11-15

## Problem

A worker says a test proves its change works, and the test would pass whether or not the change were there. I only find out when a reviewer removes the change and runs the test.

In one day on one project this reached review four times:

- A "never changes focus" test ran on a tree where focus had nowhere else to go.
- Its rebuilt version checked half of what its name said.
- A "refuses to call itself" test passed against the old code, because the request was refused earlier for another reason.
- A sizing test passed with the sizing step disabled, because it split one way and measured the other.

In three of the four the worker had been told in its brief to show the test failing first, and did not.

Where a worker did do it, it paid at once. One removed its fix expecting a timeout, got a pass in a hundredth of a second, and found its own test helper was masking the fault. Another did it from the start and passed review first time.

The team now has a written rule asking for this. A written rule is what was already being skipped.

## Proposed outcome

- A worker cannot hand a task of size 2 or larger back for review unless the task's recorded checks include at least one run that failed, followed later by a run of the same command that passed. The refusal says what is missing, why it is asked for, and how to supply it.
- A task whose change truly has nothing to control for (documentation only, a pure rename, a move with no behaviour change) can still be handed back, by a route that leaves a visible statement on the task of why no control applies. The reviewer then judges that statement. The route cannot be used silently.
- The reviewer is told, in what it is given for the review, which recorded failing run is offered as the control for which test, so it can judge whether the right thing was removed and repeat one.
- The numbers show, per task, whether a control was recorded, whether the exemption was used, and whether review later found a test that could not fail anyway, so I can tell whether this is working.
- It adds nothing to size-1 tasks.

## Affected users and systems

- Workers, who hand tasks back for review and record their checks on the task.
- Reviewers, and what they are given for a review.
- Engineers who read the numbers to see whether work that reaches review is proven.
- The command that hands a task back for review, the checks recorded on a task, and the metrics.
- The team's review policy, which stays the place that says what a good control is.

## Constraints

- This is a floor, not a judgement. The tool cannot know whether the right mechanism was removed, and must not pretend to. The reviewer still judges that, and the team's review policy stays the place that says what a good control is.
- It must not be satisfiable by an accident the worker did not intend to count.
- It must not make workers break things pointlessly to get past a gate. The refusal's wording and the exemption exist to prevent that.
- Existing commands keep working.
- A task already In Review when this ships is not sent back by it.
- The board guard is not weakened. Everything it refuses an agent today, it still refuses.
- The existing checks, tests and evals still pass, and none is weakened to get there.

## Open questions

- [ ] Does any failing run followed by a passing run of the same command count, or must the worker mark a run as a control (for example a flag on `record-check`) and name the test it controls for?
- [ ] How is "the same command" matched when a worker narrows the command to one test for the failing run and runs the whole check for the passing one?
- [ ] What is the exemption called, who may use it, and does it need the engineer's word?
- [ ] Does a review fix round need its own control when the fix adds or changes a test?
- [ ] How does this meet tasks whose proof is not a test at all (a manual check, a recorded command's output)?
- [ ] Should the same floor apply before a plan is approved (a plan whose proof names no control)?
- [ ] What should the reviewer agent's instructions say?
